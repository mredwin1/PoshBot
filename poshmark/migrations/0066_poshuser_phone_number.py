# Generated by Django 3.1.7 on 2021-07-29 01:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('poshmark', '0065_auto_20210726_2356'),
    ]

    operations = [
        migrations.AddField(
            model_name='poshuser',
            name='phone_number',
            field=models.CharField(default='', max_length=20),
        ),
    ]
