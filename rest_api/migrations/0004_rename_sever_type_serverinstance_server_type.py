# Generated by Django 3.2.15 on 2022-09-15 18:48

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('rest_api', '0003_auto_20220915_0237'),
    ]

    operations = [
        migrations.RenameField(
            model_name='serverinstance',
            old_name='sever_type',
            new_name='server_type',
        ),
    ]