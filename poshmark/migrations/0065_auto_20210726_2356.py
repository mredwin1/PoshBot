# Generated by Django 3.1.7 on 2021-07-26 23:56

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('poshmark', '0064_auto_20210725_0835'),
    ]

    operations = [
        migrations.AlterField(
            model_name='poshuser',
            name='email_forwarding_enabled',
            field=models.BooleanField(default=False, null=True),
        ),
        migrations.AlterField(
            model_name='poshuser',
            name='email_less_secure_apps_allowed',
            field=models.BooleanField(default=False, null=True),
        ),
        migrations.AlterField(
            model_name='poshuser',
            name='email_registered',
            field=models.BooleanField(default=False, null=True),
        ),
        migrations.AlterField(
            model_name='poshuser',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
    ]