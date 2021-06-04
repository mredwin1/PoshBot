from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from poshmark.models import PoshUser, Campaign


@receiver(post_delete, sender=PoshUser)
def posh_user_deleted(sender, instance, *args, **kwargs):
    instance.delete_alias_email()


@receiver(post_delete, sender=Campaign)
def campaign_deleted(sender, instance, *args, **kwargs):
    if instance.posh_user:
        if instance.posh_user.status == PoshUser.INUSE:
            instance.posh_user.status = PoshUser.ACTIVE
            instance.posh_user.save()


@receiver(post_save, sender=Campaign)
def campaign_saved(sender, instance, *args, **kwargs):
    import logging
    logging.info(instance.status)
    logging.info(instance.posh_user.status)