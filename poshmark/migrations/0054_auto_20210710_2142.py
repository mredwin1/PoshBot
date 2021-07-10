# Generated by Django 3.1.7 on 2021-07-10 21:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('poshmark', '0053_auto_20210710_2133'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='proxyconnection',
            name='posh_user',
        ),
        migrations.AddField(
            model_name='proxyconnection',
            name='posh_user',
            field=models.ManyToManyField(to='poshmark.PoshUser'),
        ),
    ]
