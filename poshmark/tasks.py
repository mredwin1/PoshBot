import datetime
import pytz

from django.utils import timezone
from celery import shared_task

from .models import PoshUser, Log, Campaign, Listing
from poshmark.poshmark_client.poshmark_client import PoshMarkClient


@shared_task
def check_registered_posh_users():
    """Will get all unregistered users and queue them up to be registered"""
    posh_users = PoshUser.objects.filter(is_registered=False)

    for posh_user in posh_users:
        register_posh_user(posh_user.id)


@shared_task
def log_cleanup():
    logs = Log.objects.filter(created__lte=timezone.now()-datetime.timedelta(days=2))

    for log in logs:
        log.delete()


@shared_task
def register_posh_user(posh_user_id):
    """Registers a PoshUser to poshmark"""
    posh_user = PoshUser.objects.get(id=posh_user_id)
    logger = Log(logger_type='1', posh_user=posh_user)
    logger.save()

    with PoshMarkClient(posh_user, logger) as client:
        client.register()
        client.update_profile()


@shared_task
def basic_campaign(campaign_id):
    campaign = Campaign.objects.get(id=campaign_id)
    posh_user = campaign.posh_user
    logger = Log(logger_type='2', posh_user=posh_user)
    listings = Listing.objects.filter(campaign__id=campaign_id)

    campaign.status = '1'
    campaign.save()
    logger.save()

    with PoshMarkClient(posh_user, logger) as client:
        now = datetime.datetime.now(pytz.utc)
        while now < now.replace(hour=23, minute=50) and now.strftime('%I %p') in campaign.times and posh_user.status != '2':
            now = datetime.datetime.now(pytz.utc)
            for listing in listings:
                client.share_item(listing)
                client.sleep(campaign.delay)

    campaign.status = '2'
    campaign.save()
