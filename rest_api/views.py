from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework import permissions
from .models import ServerInstance, CloudUser
from .serializers import CloudUserSerializer, ServerInstanceSerializer
from datetime import datetime
import requests
import time
import json
import stripe
import os
import uuid
from uuid import uuid4
import math
import random
import string
import paramiko
import bcrypt
from jupyter_server.auth import passwd
from godaddypy import Client, Account
from cloud_api.settings import DEBUG

# Create your views here.


# UPDATE SERVER USAGE
class UpdateUsage(APIView):

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
       pass

    def post(self, request, *args, **kwargs):
        """
        CALCULATE & RETURN CURRENT USAGE NUMBER FOR USER &
        UPDATE STRIPE
        """
        email = requet.data.get('email')
        function_name = request.data.get('action')
        eval(f"self.{function_name}")
        user = CloudUser.objects.filter(email = email)
        usage = ServerInstance.objects.filter(user = email)
        serializer = CloudUserSerializer(usage, many = True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# TODO: CREATE NEW USER WITH EACH SERVER, GENERATE RANDOM STRING TO APPEND TO USER NAME

# LAUNCH PAPERSPACE INSTANCE
class CloudAPIView(APIView):
    """
    1. Adjust customer to be created dynamically instead of a default Playground user.Done
    1. Create template 
    2. Save snapshots (workspaces/labs). Delete subdomain when workspace is
    3. Make lab setup code more robust and reusable. Done.
    4. check servers status every minutes and start machine if shutdown. Done.
    5. Move certs folder and Jupyter_config.py to /home/teams/ folder
    6. Instal biopython, RDKit, Meeko, OpenBabel python APIs and use them in tutorial
        apt-get install coreutils
    7. Reset password after setup.
    7. Run through QA check list.
    8. Standup production API endpoint
    9. Change URLs to match production
    10. Work on GROMACS tutorial with both Python API and a Bash Script approach
    11. Make Cloud site live.
    12. Send Slack message to team and get them to QA the site. 
    
    """

    def __init__(self):
        """
        {
            "action": "create_server",
            "email": email,
            "ip_address": ip_address, if not create_server
        }
        actions: create_server, restart_server, shutdown_server
        """
        self.paperspace_token = self.set_token(type = "paperspace") 
        self.paperspace_api_endpoint = "https://api.paperspace.io/machines/createSingleMachinePublic"
        self.start_instances_url = lambda id_: f'https://api.paperspace.io/machines/{id_}/start'
        self.restart_instances_url = lambda id_: f'https://api.paperspace.io/machines/{id_}/restart'
        self.destroy_instances_url = lambda id_: f'https://api.paperspace.io/machines/{id_}/destroyMachine'
        
        self.static_template_id =  'tf153q0p'
        
        stripe.api_key = self.set_token(type = 'stripe')

        if DEBUG is False: # production mode
            stripe.api_key = self.set_token(type = 'stripe')
            self.price_id_dict = {
                "P4000": "price_1Li3EhCOoRHpRTSnQ6F2E8cE", 
                "A6000": "price_1LiCKwCOoRHpRTSnIDeHyBm1",
                "A100-80G": "price_1LiCMcCOoRHpRTSnlX3bMCLD"
            }

        else: # test mode
            stripe.api_key = self.set_token(type = 'stripe_test')
            self.price_id_dict = {
                "P4000": "price_1LiMZhCOoRHpRTSnKVKjoam7", 
                "A6000": "price_1LiMZhCOoRHpRTSnKVKjoam7", 
                "A100-80G": "price_1LiMZhCOoRHpRTSnKVKjoam7" 
            }
    
    
    def set_token(self, type: str):
        """
            THIS FUNCTION SETS THE API TOKEN FOR PAPERSPACE
        """
        with open(os.path.join(os.getcwd(), f"{type}.txt"), 'r') as file:
            token = file.readline()
        return token
    
    
    def get_server_instance(self, email: str = None, ip_address: str = None):
        import pdb

        """ IF IP AND EMAIL NOT PROVIDE DEFAULT TO POST REQUST DATA """
        ip_address = self.request.data.get('ip_address') if ip_address == None else ip_address
        email = self.request.data.get('email') if email == None else email

        server_instance = ServerInstance.objects.get(user_email = email, 
                                                    public_ip_address = ip_address, 
                                                    stopped_time = "NOT STOPPED")
        return server_instance
    
    
    def ssh_into_server(self, username: str, password: str = None, email: str = None, ip_address: str = None):

        
        email = self.request.data.get('email') if email == None else email
        ip_address = self.request.data.get('ip_address') if ip_address == None else ip_address
        server_instance = self.get_server_instance(email = email, ip_address = ip_address)
        server_password = server_instance.password if password == None else password
        ip_address = server_instance.public_ip_address
    
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # MONITOR SERVER STATUS AND CONNECT IF SERVER IS AVAILABLE
        client.connect(ip_address, username = username, password = server_password, timeout = 120)
        return client
    
    def add_subdomain_to_godaddy(self, ip_address: str, subdomain: str):
        """ 
        THIS FUNCTION CREATE A NEW 'A' RECORD WITH 
        AN INPUT SUBDOMAIN AND POINTS IT TO A DESIRED IP 
        """
        userAccount = Account(api_key = self.set_token("go_daddy_key"), 
                              api_secret = self.set_token("go_daddy_secret"))
        userClient = Client(userAccount)
        domain = "playground.bio"
        userClient.add_record(domain, {'data': ip_address, 
                                       'name': subdomain, 
                                       'ttl': 3600, 
                                       'type': 'A'})
    
    def setup_jupyter_lab(self, email: str = None, ip_address: str = None):
        import pdb

        server_instance = self.get_server_instance(email = email, ip_address = ip_address)
        ip_address = server_instance.public_ip_address
        username = server_instance.username
        
        """ GENERATE A HASH PASSWORD """
        server_password = server_instance.password
        jupyter_password = passwd(server_password)
        
        try:
            """ SSH INTO SERVER """
            client = self.ssh_into_server(email = email, ip_address = ip_address, username = username)
        except TimeoutError as error:
            print(f"\nERROR:\t{error}\n")
            time.sleep(120)
            client = self.ssh_into_server(email = email, ip_address = ip_address, username = username)

        """ GENERATE SUBDOMAIN """
        subdomain = ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(15))
        
        """ ADD DNS RECORDS TO GODADDY """
        self.add_subdomain_to_godaddy(ip_address = ip_address, subdomain = subdomain)
        
        """ GET SSL CERTS FOR FULL DOMAIN """
        full_domain = f"{subdomain}.playground.bio"
        time.sleep(45) # SLEEP TO GIVE DNS TIME. CHALLENGE ERROS OCCUR IF SLEEP ISN'T LONG ENOUGH
        sdin, sderr, sdout = client.exec_command(f'echo "{server_password}" | sudo -S -k certbot certonly -n -d {full_domain} --agree-to --standalone --email talk@insilicoservices.com')
        print(sdout.readlines())
        """ PATH TO CERT FILES """
        etc_path_to_privkey = f"/etc/letsencrypt/live/{full_domain}/privkey.pem"
        etc_path_to_fullchain = f"/etc/letsencrypt/live/{full_domain}/fullchain.pem"   

        """ SET PATH TO USER & DIRECTORY """
        user_directory = os.path.join("/home", username).replace("\\", "/")
        team_directory = os.path.join("/home", "team").replace("\\", "/")
        config_dir = team_directory
        team_pass = "HBhtBeZH"

        """ CREATE JUPYTER CONFIG PYTHON FILE """
        path_to_certs = os.path.join(config_dir, "certs").replace("\\", "/")
        path_to_fullchain = os.path.join(path_to_certs, "fullchain.pem").replace("\\", "/")
        path_to_privkey = os.path.join(path_to_certs, "privkey.pem").replace("\\", "/")
        # pdb.set_trace()

        config = [f"c.ServerApp.certfile = u'{path_to_fullchain}'\n",  
                  f"c.ServerApp.keyfile = u'{path_to_privkey}'\n",
                  f"c.ServerApp.ip = '*'\n",
                  f"c.ServerApp.password = u'{jupyter_password}'\n",
                  f"c.ServerApp.open_browser = False\n",
                  f"c.ServerApp.port = 9999\n"]

        team_client = self.ssh_into_server(username = 'team', password = team_pass, email = email, ip_address = ip_address)
        ftp = team_client.open_sftp()
        path_to_jupyter_file = os.path.join(config_dir, "jupyter_server_config.py").replace("\\", '/')
        config_file = ftp.file(path_to_jupyter_file, 'w+')
        for line in config:
            config_file.write(line)
        config_file.flush()
        ftp.close()

        sudo_command = lambda password, command: f'echo "{password}" | sudo -S -k {command}'
        
        """ MOVE THE CERTS TO A NEW DIRECTORY """
        team_client.exec_command(f'mkdir {path_to_certs}')
        team_client.exec_command(sudo_command(team_pass, f"cp {etc_path_to_privkey} {path_to_privkey}"))
        team_client.exec_command(sudo_command(team_pass, f'cp {etc_path_to_fullchain} {path_to_fullchain}'))

        """ CHANGE PERMISSIONS OF CERTS SO PROGRAMS CAN ACCESS """
        team_client.exec_command(sudo_command(team_pass, f'chmod 777 {path_to_certs}'))
        team_client.exec_command(sudo_command(team_pass, f'chmod 777 {path_to_privkey}'))
        team_client.exec_command(sudo_command(team_pass, f'chmod 777 {path_to_fullchain}'))

        """ STOP OPERATION ON PORT 9999 AND RUN JUPYTER LAB IN THE BACKGROUND """
        client.exec_command("kill -9 $(lsof -t -i:9999)")
        client.exec_command(f"nohup /usr/local/anaconda3/bin/jupyter server --config {path_to_jupyter_file}")
    
        lab_url = f"https://{full_domain}:9999/lab"
        print(username, ip_address, server_password)
        print(f"\nLAB URL:\t{lab_url}\n")

        """ SAVE LAB URL TO DATABASE """
        server_instance.lab_url = lab_url
        server_instance.save()

        """ CLOSE SSH CONNECTION """
        client.close()
        team_client.close()
        jupyter_dict = json.dumps({
            'lab_url': lab_url
        })
        return Response(jupyter_dict, status=status.HTTP_200_OK)

    
    def wait(self):
        seconds = self.request.data.get('time')
        print(f"\nWAITING {seconds} SECONDS\n")
        time.sleep(int(seconds))
        return Response(True, status=status.HTTP_200_OK)
    
    
    def create_username(self):
        user_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        username = f"playground_user{user_id}"
        return username


    def reset_server_password(self, email: str, username: str, password: str):
        client = self.ssh_into_server(email = email, username = username, ip_address = ip_address)
        client.exec_command(f'echo "{username}:{password}" | sudo chpasswd')
        client.close()
    

    def reset_jupyter_password(self):
        pass


    def create_on_start_script(self, password: str):
        """ 
        THIS FUNCTION GENERATES AND INPUTS A BASH SCRIPT STRING, 
        CREATES A STARTUP SCRIPT AND RETURNS A SCRIPT ID 
        """
        
        """ CREATE RANDOM USER NAME """
        username = self.create_username()

        """ STRING BASH SCRIPT """
        startup_script = f'#!/bin/bash\nsudo useradd -m {username}\nsudo chsh -s /bin/bash {username}\necho "{username}:{password}" | sudo chpasswd\nsudo adduser {username} sudo'
        
        """ CREATE A SCRIPT ID """
        create_script = json.dumps({"scriptName": "gromacs_on_startup",
                                    "scriptText": startup_script})

        headers = {'X-Api-Key' : self.paperspace_token, 'Content-type': 'application/json'}
        create_script_response = requests.post(url = "https://api.paperspace.io/scripts/createScript", 
                                               headers = headers, 
                                               data = create_script)
        
        script_id = json.loads(create_script_response.text)['id']

        return (script_id, username)


    def reset_password(self, email: str = None, ip_address: str = None):
        """
        echo "playground:{password}" | sudo chpasswd;
        jupyter config.py password
        database password
        """
        email = self.request.data.get('email') if email != None else email
        ip_address = self.request.data.get('ip_address') if ip_address != None else ip_address
        
        server_instance = self.get_server_instance()
        username = server_instance.username

        # server username password
        self.reset_server_password(email = email, username = username, password = password)

    def monitor_server_state(self):
        """ 
        WITH OUT CURRENT SETUP NO SERVER SHOULD EVER BE OFF
        THIS STARTS A SEVER IF ITS STATUS IS OFF 
        """

        all_servers = ServerInstance.objects.filter(stopped_time = "NOT STOPPED")

        for server_instance in all_servers:
        
            machine_id = server_instance.machine_id

            if self.server_status(machine_id = machine_id) == 'off':
                self.change_server_state(change_state = 'start')
    
    
    def all_server_status(self):

        server_status_dict = {}

        all_servers = ServerInstance.objects.filter(stopped_time = "NOT STOPPED")

        for server_instance in all_servers:
        
            ip_address = server_instance.public_ip_address
            
            server_status = self.server_status(machine_id = server_instance.machine_id)

            server_status_dict[ip_address] = server_status
        
        return Response(server_status_dict, status=status.HTTP_200_OK)
    
    
    def server_status(self, machine_id: str):
        import pdb
        headers = {'X-Api-Key' : self.paperspace_token, 'Content-type': 'application/json'}
        server_status_response =  requests.get(url = f'https://api.paperspace.io/machines/getMachinePublic?machineId={machine_id}', headers = headers)
        unpacked_server_status = json.loads(server_status_response.text)
        # pdb.set_trace()
        return unpacked_server_status['state']


    def create_server(self, subscription_item_id: str, subscription_id: str, customer_id: str, *args, **kwargs):
        import pdb
        """ THIS FUNCTION CREATES AND CONFIGURES SERVER ON PAPERSPACE """

        """ EXTACT DETAILS FROM REQUEST """
        server_type = self.request.data.get('server_type')
        email = self.request.data.get('email')

        headers = {'X-Api-Key' : self.paperspace_token, 'Content-type': 'application/json'}
        
        """ GENERATE A SERVER PASSWORD """
        password = ''.join(random.choices(string.ascii_uppercase + string.digits, k=15))

        """ CREATE CUSTOM SCRIPT TO RUN ON STARTUP """
        script_id, username = self.create_on_start_script(password = password)
        
        """ SERVER CONFIGURATION """
        server_config = json.dumps({
                            "x-api-key": self.paperspace_token,
                            "region": "East Coast (NY2)", 
                            "machineType": server_type, 
                            "size": 1000,
                            "billingType": "hourly", 
                            "machineName": email, 
                            "templateId": self.static_template_id,
                            "assignPublicIp": 'true',
                            "startOnCreate": 'true',
                            "scriptId": script_id
                            })
        
        """ CREATE SERVER """
        create_server_response = requests.post(url = self.paperspace_api_endpoint,
                                               headers = headers,
                                               data = server_config)
        
        loaded_server_response = json.loads(create_server_response.text)

        machine_id = loaded_server_response['id']
        public_ip_address = loaded_server_response['publicIpAddress']

        """ START TIMESTAMP """
        now = datetime.now()
        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")

        server_details = ServerInstance(user_email = email,
                                        server_type = server_type, 
                                        machine_id = machine_id, 
                                        create_time = dt_string,
                                        public_ip_address = public_ip_address,
                                        subscription_id = subscription_id,
                                        subscription_item_id = subscription_item_id,
                                        password = password,
                                        lab_url = 'None',
                                        workspace_token = 'None',
                                        username = username)
        server_details.save()

        """ SAVE DETAILS TO DATABASE """
        user = CloudUser.objects.get(stripe_customer_id = customer_id)
        user.server_instance.add(server_details)

        """ WAIT FOR RIGHT STATE """
        while(self.server_status(machine_id = machine_id) == "provisioning"):
            print("provisioning")
    

        """ SETUP JUPYTER LAB """
        print("SETTING UP LAB")
        time.sleep(45)
        self.setup_jupyter_lab(email = email, ip_address = public_ip_address)
    

        """ RETURN RESPONSE """
        server_dict = json.dumps({
            'user_email': email,
            'server_type': server_type,
            'create_time': dt_string,
            'public_ip_address': public_ip_address,
        })
        Response(server_dict, status=status.HTTP_200_OK)
    
    
    def change_server_state(self, state_change: str = None):
        
        state_change = self.request.data.get('state_change') if state_change != None else state_change

        def server_states(machine_id: int, state_change: str): 
            url_dictionary = {'start': f'https://api.paperspace.io/machines/{machine_id}/start',
                                'restart': f'https://api.paperspace.io/machines/{machine_id}/restart',
                                'destroy': f'https://api.paperspace.io/machines/{machine_id}/destroyMachine'}
            return url_dictionary[state_change]
        
        headers = {'X-Api-Key' : self.paperspace_token, 
                    'Content-type': 'application/json'}

        server_instance = self.get_server_instance()
        machine_id = server_instance.machine_id

        change_state_response = requests.post(url = server_states(machine_id = machine_id, state_change = state_change), 
                                              headers = headers)
        
        if state_change == 'destroy':
            server_instance.delete()
            
        Response(change_state_response.text, status=status.HTTP_200_OK)

    
    def create_customer(self, *args, **kwargs):
        """ CREATE A SINGLE STRIPE USER & SAVE TO DB"""
        email = self.request.data.get('email')

        if self.customer_in_database(email = email) is False:
            create_customer_response = stripe.Customer.create(email = email)
            customer_id = create_customer_response.id
            new_cloud_user = CloudUser(email = email, stripe_customer_id = customer_id)
            new_cloud_user.save()
            print(f"\nCREATED CUSTOMER:\t{email}\n")
        else:
            print(f"\nCUSTOMER {email} ALREADY IN DATABASE\n")
    

    def get_first_customer_with_email(self, email):
        users = CloudUser.objects.filter(email = email)
        number_of_entries_in_db = users.count()
        if number_of_entries_in_db > 1:
            # THEN INDEX QUERYSET TO GET THE FIRST INSTANCE
            first_user = users[1]
        else:
            first_user = users[0]

        return first_user
    

    def customer_in_database(self, email: str):
        try:
            CloudUser.objects.get(email = email)
            return True
        except:
            return False

    
    def get_all_servers(self):
        email = self.request.data.get('email')
        servers = ServerInstance.objects.filter(user_email = email, stopped_time = "NOT STOPPED")
        serializer = ServerInstanceSerializer(servers, many = True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    
    def begin_subscription(self, *args, **kwargs):
        """ STARTING SUBSCRIBING TO HOURLY PRICING ON SERVER """
        import pdb
        email = self.request.data.get('email')
        server_type = self.request.data.get('server_type')

        """ VERIFY PAYMENT METHOD STATUS """
        if self.check_payment_method_status() is True:

            """ CREATE SUBSCRIPTION """
            customer_id = self.get_first_customer_with_email(email = email).stripe_customer_id
            price_id  = self.price_id_dict[server_type]
            subscribe_response = stripe.Subscription.create(
                                                            customer = customer_id,
                                                            items = [{"price": price_id}])
            
            """ CREATE SERVER """
            subscription_item_id = subscribe_response['items']['data'][0]['id']
            subscription_id = subscribe_response.id
            if self.reached_server_limit() is False:
                self.create_server(subscription_item_id = subscription_item_id, subscription_id = subscription_id, customer_id = customer_id)
                return Response(True, status=status.HTTP_200_OK)
            else:
                print("\nSERVER LIMIT HAS BEEN REACHED\n")
                return Response(False, status=status.HTTP_426_UPGRADE_REQUIRED)
        else:
            print(f"\tA PAYMENT METHOD WAS NOT DETECTED FOR:\t{email}\n")
            return Response(self.check_payment_method_status(), status=status.HTTP_426_UPGRADE_REQUIRED)


    def ip_address_in_database(self, ip_address: str):
        try:
            ServerInstance.objects.get(public_ip_address = ip_address,
                                        stopped_time = 'NOT STOPPED')
            return True
        except:
            return False

    # on run setup click, check server status, 
    
    
    def check_payment_method_status_or_break(self):
        import pdb
        email = self.request.data.get('email')
        cloud_user = CloudUser.objects.get(email = email)
        stripe_customer_id = cloud_user.stripe_customer_id
        customer_response = stripe.Customer.retrieve(stripe_customer_id)
        payment_method_status = str(customer_response.default_source)
        # pdb.set_trace()
        
        if payment_method_status != 'None':
            return Response(True, status=status.HTTP_200_OK)
        else:
            # break server
            return os.nothing
    
    
    def check_payment_method_status(self):
        import pdb
        email = self.request.data.get('email')
        cloud_user = CloudUser.objects.get(email = email)
        stripe_customer_id = cloud_user.stripe_customer_id
        customer_response = stripe.Customer.retrieve(stripe_customer_id)
        payment_method_status = str(customer_response.default_source)
        # pdb.set_trace()
        
        if payment_method_status != 'None':
            return True
        else:
            return False
    

    def return_payment_method_status(self):
        payment_status = self.check_payment_method_status()
        print(payment_status)
        if payment_status is True:
            return Response(self.check_payment_method_status(), status=status.HTTP_200_OK)
        else:
            return Response(self.check_payment_method_status(), status=status.HTTP_426_UPGRADE_REQUIRED)
    
    def stop_subscription(self, *args, **kwargs):
        import pdb
        """ HALT SUBSCRIPTION ON SINGLE SERVER SHUTDOWN """
        email = self.request.data.get('email')
        ip_address = self.request.data.get('ip_address')

        # pdb.set_trace()
    
        if self.ip_address_in_database(ip_address = ip_address) is True:
            
            """ MODIFY STRIPE SUBSCRIPTION TO CANCEL AT PERIOD END. """
            server_instance = ServerInstance.objects.get(user_email = email,
                                                         public_ip_address = ip_address, 
                                                         stopped_time = "NOT STOPPED")
            
            """ UPDAGE USAGE """
            cloud_user = CloudUser.objects.get(email = email)
            self.single_update_usage(user = cloud_user)

            """ MODIFY SUBSCRIPTION """
            stripe.Subscription.modify(server_instance.subscription_id, 
                                        cancel_at_period_end = True)
            
            """ SHUTDOWN THE SERVER """
            self.change_server_state(state_change = 'destroy') # IP ADDRESS IS PULLED FROM CLASS LEVEL REQUEST OBJECT

            """ SAVE STOP TIME IN DATABASE """
            now = datetime.now()
            dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
            server_instance.stopped_time = dt_string
            server_instance.save()
            print(f"\nSUBSCRIPTION {server_instance.subscription_id} HAS BEEN MODIFIED TO CANCEL AT PERIOD END AND SERVER {ip_address} HAS BEEN SHUTDOWN.\n")
            return Response("DELETED SERVER", status=status.HTTP_200_OK)
        else:
            print(f"\nTHIS IP ADDRESS {ip_address} IS NOT OUR DATABASE.\n")
            return Response("IP ADDRESS NOT FOUND")


    def reached_server_limit(self, server_limit: int = 10):

        email = self.request.data.get('email')
        server_instance = ServerInstance.objects.filter(user_email = email, stopped_time = "NOT STOPPED")
        server_count = server_instance.count()
        
        if server_count >= server_limit:
            return True
        else:
            return False

    
    def single_update_usage(self, user, *args, **kwargs):
        """ USER IS A USER DJANGO DATABASE OBJECT THAT IS ITERATED OVER """

        """ ITERATE OVER EACH SERVER THAT USER HAS IN DB """
        for server in user.server_instance.values():

                creation_time = server['create_time']
                stopped_time = server['stopped_time']

                # IF THE SEVER HASN'T BEEN STOPPD THEN SET STOP NOW TIME TO NOW
                if stopped_time == 'NOT STOPPED':
                    now = datetime.now()
                    dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
                    stopped_time = dt_string

                # CALCULATE TOTAL USAGE HOURS
                converted_start_time = datetime.strptime(creation_time, "%d/%m/%Y %H:%M:%S")
                converted_stopped_time = datetime.strptime(stopped_time, "%d/%m/%Y %H:%M:%S")
                usage_time = converted_stopped_time - converted_start_time
                total_rounded_usage_hours = round((usage_time.seconds/60)/60)
        
                # UPDATE STRIPE WITH TOTAL USAGE HOURS
                timestamp = int(time.time())
                idempotency_key = uuid.uuid4()
                try:
                    stripe.SubscriptionItem.create_usage_record(
                        server['subscription_item_id'],
                        quantity = total_rounded_usage_hours,
                        timestamp = timestamp,
                        action = 'set', # SET OVERWRITE, INCREMENT ADDS-TO
                        idempotency_key = str(idempotency_key)
                    )
                    # pdb.set_trace()
                except stripe.error.StripeError as error:
                    print(error)
                    # print(f"Usage report failed for item ID {server.subscription_id} with idempotency key {idempotency_key} error {error.error.message}")

                # ADD TOTAL USAGE HOURS TO DB
                grab_server = ServerInstance.objects.get(subscription_item_id = server['subscription_item_id'])
                grab_server.usage_hours = total_rounded_usage_hours
                grab_server.save()
                print(f"\nUSAGE UPDATED FOR:\n\tEMAIL:\t{user.email}\n\tSERVER:\t{grab_server.public_ip_address}\n\tSUBSCRIPTION_ITEM_ID:\t{server['subscription_item_id']}\n\tUSAGE:\t{grab_server.usage_hours}\n")

    
    def update_usage(self, *args, **kwargs):
        """ UPDATE STRIPE HOURLY USAGE FOR EVERY USER/SERVERS """
        # ITERATE OVER EACH CUSTOMER
        total_users = CloudUser.objects.all()
        for user in total_users:
            self.single_update_usage(user = user)


    def get(self, request, *args, **kwargs):
        """GET IP ADDRESSES AND PASSWORDS FROM A USER"""
        return Response(json.dumps({"temp":"get"}), status=status.HTTP_200_OK)
    
    def post(self, request, *arg, **kwargs):
        import pdb
        #pdb.set_trace()
        self.request = request
        function_name = request.data.get('action')
        function_response = eval(f"self.{function_name}()")
        return function_response


    
