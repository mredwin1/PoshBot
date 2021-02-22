# Generated by Django 3.1.7 on 2021-02-22 00:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('poshmark', '0007_poshuser_header_picture'),
    ]

    operations = [
        migrations.AlterField(
            model_name='poshuser',
            name='status',
            field=models.CharField(choices=[('0', 'In Use'), ('1', 'Active'), ('2', 'Inactive'), ('3', 'Waiting for alias email to be verified'), ('4', 'Waiting to be registered'), ('5', 'Registering'), ('6', 'Updating Profile')], max_length=20),
        ),
    ]
