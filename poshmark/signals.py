from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from poshmark.models import PoshUser, Campaign, Listing
from poshmark.tasks import update_redis_object


# @receiver(post_save, sender=PoshUser)
# def posh_user_saved(sender, instance, *args, **kwargs):
#     if instance.redis_id:
#         update_redis_object(instance.redis_id, instance.to_dict())


@receiver(post_save, sender=Campaign)
def campaign_saved(sender, instance, *args, **kwargs):
    if instance.mode == Campaign.BASIC_SHARING:
        if instance.posh_user:
            if instance.posh_user.status == PoshUser.INACTIVE:
                instance.posh_user.delete()

    # if instance.redis_id:
    #     update_redis_object(instance.redis_id, instance.to_dict())


# @receiver(post_save, sender=Listing)
# def listing_saved(sender, instance, *args, **kwargs):
#     if instance.redis_id:
#         update_redis_object(instance.redis_id, instance.to_dict())


@receiver(post_delete, sender=PoshUser)
def posh_user_deleted(sender, instance, *args, **kwargs):
    instance.delete_alias_email()
