# Generated by Django 3.1.7 on 2021-05-21 03:01

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('poshmark', '0037_remove_poshproxy_ip_reset_url'),
    ]

    operations = [
        migrations.RenameField(
            model_name='poshproxy',
            old_name='uuid',
            new_name='ip_reset_url',
        ),
    ]