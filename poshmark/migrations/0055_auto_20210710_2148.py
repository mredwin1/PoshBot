# Generated by Django 3.1.7 on 2021-07-10 21:48

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('poshmark', '0054_auto_20210710_2142'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='proxyconnection',
            name='posh_user',
        ),
        migrations.AddField(
            model_name='proxyconnection',
            name='posh_user',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='poshmark.poshuser'),
        ),
    ]
