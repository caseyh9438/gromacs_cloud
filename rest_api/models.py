from django.db import models
from django.contrib.auth.models import User
# Create your models here.

class ServerInstance(models.Model):
    user_email = models.CharField(max_length = 35, blank = True)
    server_type = models.CharField(max_length = 35)
    create_time = models.CharField(max_length = 50)
    stopped_time = models.CharField(max_length = 50, default = 'NOT STOPPED')
    machine_id = models.CharField(max_length = 15, blank = True)
    public_ip_address = models.CharField(max_length = 15, blank = True)
    subscription_id = models.CharField(max_length = 50, blank = True)
    subscription_item_id = models.CharField(max_length = 50, blank = True)
    usage_hours = models.IntegerField(blank = True, default = 0)
    password = models.CharField(max_length = 35, blank = True)
    lab_url = models.CharField(max_length = 250, blank=True)
    workspace_token = models.CharField(max_length = 250, blank = True)
    username = models.CharField(max_length = 50, blank = True)

class CloudUser(models.Model):
    first_name = models.CharField(max_length = 35, blank = True)
    last_name = models.CharField(max_length = 35, blank = True)
    email = models.CharField(max_length = 35)
    server_instance = models.ManyToManyField(ServerInstance)
    stripe_customer_id = models.CharField(max_length = 35, blank = True)
