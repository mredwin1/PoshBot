# Generated by Django 3.1.7 on 2021-07-25 02:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('poshmark', '0059_auto_20210725_0118'),
    ]

    operations = [
        migrations.AlterField(
            model_name='poshuser',
            name='status',
            field=models.CharField(choices=[('1', 'Idle'), ('2', 'Inactive'), ('3', 'Campaign running'), ('4', 'Registering'), ('5', 'Email Creation'), ('6', 'Email Forwarding')], max_length=20),
        ),
    ]