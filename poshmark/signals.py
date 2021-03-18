from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .tasks import register_posh_user
from poshmark.models import PoshUser, Campaign


@receiver(post_delete, sender=PoshUser)
def posh_user_deleted(sender, instance, *args, **kwargs):
    instance.delete_alias_email()


@receiver(post_save, sender=PoshUser)
def posh_user_saved(sender, instance, created, *args, **kwargs):
    if created and not instance.is_registered:
        register_posh_user.delay(instance.id)


@receiver(post_delete, sender=Campaign)
def campaign_deleted(sender, instance, *args, **kwargs):
    if instance.posh_user.status == PoshUser.INUSE:
        instance.posh_user.status = PoshUser.ACTIVE
        instance.posh_user.save()
