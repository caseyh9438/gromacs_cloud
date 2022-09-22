from django.contrib import admin
from .models import ServerInstance, CloudUser
# Register your models here.

admin.site.register(ServerInstance)
admin.site.register(CloudUser)