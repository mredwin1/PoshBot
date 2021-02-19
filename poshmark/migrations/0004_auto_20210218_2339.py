# Generated by Django 3.1.6 on 2021-02-18 23:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('poshmark', '0003_auto_20210218_2324'),
    ]

    operations = [
        migrations.AlterField(
            model_name='poshuser',
            name='email',
            field=models.EmailField(help_text='If alias is chosen up top then put the email you wish to mask here. Otherwise put the email you wish to create the Posh User with.', max_length=254),
        ),
    ]
