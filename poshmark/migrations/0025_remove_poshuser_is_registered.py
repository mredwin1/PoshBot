# Generated by Django 3.1.7 on 2021-03-21 18:07

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('poshmark', '0024_auto_20210321_1429'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='poshuser',
            name='is_registered',
        ),
    ]