# Generated by Django 3.1.7 on 2021-07-10 21:33

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('poshmark', '0052_auto_20210710_2034'),
    ]

    operations = [
        migrations.AlterField(
            model_name='proxyconnection',
            name='posh_user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='poshmark.poshuser'),
        ),
    ]