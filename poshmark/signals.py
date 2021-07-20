import os

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from poshmark.models import PoshUser, Campaign


@receiver(post_save, sender=Campaign)
def campaign_saved(sender, instance, *args, **kwargs):
    if instance.mode == Campaign.BASIC_SHARING:
        if instance.posh_user:
            if instance.posh_user.status == PoshUser.INACTIVE:
                instance.posh_user.delete()


@receiver(post_delete, sender=PoshUser)
def posh_user_deleted(sender, instance, *args, **kwargs):
    instance.delete_alias_email()
    try:
        os.remove(f'/shared_volume/cookies/{instance.username}.pkl')
    except OSError:
        pass
