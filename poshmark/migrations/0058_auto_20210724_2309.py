# Generated by Django 3.1.7 on 2021-07-24 23:09

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('poshmark', '0057_auto_20210724_2234'),
    ]

    operations = [
        migrations.AddField(
            model_name='poshuser',
            name='email_forwarding_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='poshuser',
            name='email_less_secure_apps_allowed',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='poshuser',
            name='email_registered',
            field=models.BooleanField(default=False),
        ),
    ]