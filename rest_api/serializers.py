from rest_framework import serializers
from .models import CloudUser, ServerInstance

class CloudUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CloudUser
        fields = ["first_name", "last_name", "email"]


class ServerInstanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServerInstance
        fields = ["public_ip_address", 
                    "server_type", 
                    "create_time", 
                    "usage_hours", 
                    "password", 
                    "lab_url", 
                    "username"]