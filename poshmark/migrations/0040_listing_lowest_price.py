# Generated by Django 3.1.7 on 2021-06-05 22:28

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('poshmark', '0039_auto_20210524_0235'),
    ]

    operations = [
        migrations.AddField(
            model_name='listing',
            name='lowest_price',
            field=models.IntegerField(default=250),
        ),
    ]
