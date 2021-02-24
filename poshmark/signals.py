import logging

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .tasks import register_posh_user
from poshmark.models import PoshUser


@receiver(post_delete, sender=PoshUser)
def delete_alias_email(sender, instance, *args, **kwargs):
    instance.delete_alias_email()
    logging.info(f'Alias email for {instance.username} deleted')


@receiver(post_save, sender=PoshUser)
def register_posh_user(sender, instance, created, *args, **kwargs):
    if created and not instance.is_registered:
        register_posh_user.delay(instance.id)

