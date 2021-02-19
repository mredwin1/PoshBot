import logging

from django.db.models.signals import post_delete
from django.dispatch import receiver

from poshmark.models import PoshUser


@receiver(post_delete, sender=PoshUser)
def delete_alias_email(sender, instance, *args, **kwargs):
    instance.delete_alias_email()
    logging.info(f'Alias email for {instance.username} deleted')