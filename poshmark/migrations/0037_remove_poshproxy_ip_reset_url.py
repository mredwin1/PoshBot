# Generated by Django 3.1.7 on 2021-05-21 02:56

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('poshmark', '0036_poshproxy_uuid'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='poshproxy',
            name='ip_reset_url',
        ),
    ]
