# Generated by Django 3.1.7 on 2021-07-25 03:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('poshmark', '0060_auto_20210725_0220'),
    ]

    operations = [
        migrations.RenameField(
            model_name='log',
            old_name='posh_user',
            new_name='description',
        ),
        migrations.AlterField(
            model_name='poshuser',
            name='gender',
            field=models.CharField(blank=True, max_length=20),
        ),
    ]