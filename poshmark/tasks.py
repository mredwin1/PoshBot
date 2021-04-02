import datetime
import pytz
import random
import time

from django.utils import timezone
from celery import shared_task

from .models import PoshUser, Log, Campaign, Listing
from poshmark.poshmark_client.poshmark_client import PoshMarkClient


@shared_task
def check_registered_posh_users():
    """Will get all unregistered users and queue them up to be registered"""
    posh_users = PoshUser.objects.filter(status=PoshUser.WREGISTER)

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
        posh_user.refresh_from_db()
        if posh_user.status == PoshUser.ACTIVE:
            client.update_profile()


@shared_task
def basic_sharing(campaign_id):
    campaign = Campaign.objects.get(id=campaign_id)
    posh_user = campaign.posh_user
    logger = Log(logger_type=Log.CAMPAIGN, posh_user=posh_user)
    logged_hour_message = False
    max_deviation = round(campaign.delay / 2)

    campaign.status = '1'
    campaign.save()
    logger.save()

    logger.info('Starting Campaign')
    with PoshMarkClient(posh_user, logger, use_proxy=False) as client:
        now = datetime.datetime.now(pytz.utc)
        end_time = now + datetime.timedelta(days=1)
        while now < end_time and posh_user.status != PoshUser.INACTIVE and campaign.status == '1':
            now = datetime.datetime.now(pytz.utc)
            while now.strftime('%I %p') in campaign.times and posh_user.status != PoshUser.INACTIVE and campaign.status == '1':
                campaign.refresh_from_db()
                posh_user.refresh_from_db()
                now = datetime.datetime.now(pytz.utc)

                listing_titles = client.get_all_listings()

                for listing_title in listing_titles:
                    pre_share_time = time.time()
                    if client.share_item(listing_title):
                        positive_negative = 1 if random.random() < 0.5 else -1
                        deviation = random.randint(0, max_deviation) * positive_negative
                        post_share_time = time.time()
                        elapsed_time = round(post_share_time - pre_share_time, 2)
                        sleep_amount = (campaign.delay - elapsed_time) + deviation

                        if elapsed_time < sleep_amount:
                            client.sleep(sleep_amount)
                    else:
                        break

                if logged_hour_message:
                    logged_hour_message = False

            if not logged_hour_message and campaign.status == '1' and posh_user.status == PoshUser.INUSE:
                logger.info(f"This campaign is not set to run at {now.astimezone(pytz.timezone('US/Eastern')).strftime('%I %p')}, sleeping...")

    logger.info('Campaign Ended')

    campaign.status = '2'
    campaign.save()


@shared_task
def advanced_sharing(campaign_id):
    campaign = Campaign.objects.get(id=campaign_id)
    posh_user = campaign.posh_user
    logger = Log(logger_type=Log.CAMPAIGN, posh_user=posh_user)
    campaign_listings = Listing.objects.filter(campaign__id=campaign_id)
    logged_hour_message = False
    fake_listing_titles = []
    posted_new_listings = False
    max_deviation = round(campaign.delay / 2)

    campaign.status = '1'
    campaign.save()
    logger.save()

    logger.info('Starting Campaign')

    now = datetime.datetime.now(pytz.utc)
    end_time = now + datetime.timedelta(days=1)
    with PoshMarkClient(posh_user, logger) as client:
        while now < end_time and posh_user.status != PoshUser.INACTIVE and campaign.status == '1' and not posted_new_listings:
            now = datetime.datetime.now(pytz.utc)
            while now.strftime('%I %p') in campaign.times and posh_user.status != PoshUser.INACTIVE and campaign.status == '1' and not posted_new_listings:
                campaign.refresh_from_db()
                posh_user.refresh_from_db()
                now = datetime.datetime.now(pytz.utc)

                while not posh_user.meet_posh:
                    if client.check_listing('Meet your Posher'):
                        posh_user.meet_posh = True
                        posh_user.save()
                    else:
                        client.sleep(60)

                listing_titles = client.get_all_listings()
                listings_to_list = [listing for listing in campaign_listings if listing.title not in listing_titles]
                while len(fake_listing_titles) != len(listings_to_list):
                    title = client.list_item()
                    client.sleep(12)
                    if client.check_listing(title):
                        if client.share_item(title):
                            fake_listing_titles.append(title)
                        else:
                            client.delete_listing(title)
                    client.sleep(random.randint(16, 30))

                for index, value in enumerate(listings_to_list):
                    client.update_listing(fake_listing_titles[index], value, 'Saks Fifth Avenue')
                    client.update_listing(value.title, value)
                    client.sleep(random.randint(16, 30))
                posted_new_listings = True

                if logged_hour_message:
                    logged_hour_message = False

            if not logged_hour_message and campaign.status == '1' and posh_user.status == PoshUser.INUSE:
                logger.info(
                    f"This campaign is not set to run at {now.astimezone(pytz.timezone('US/Eastern')).strftime('%I %p')}, sleeping...")

    with PoshMarkClient(posh_user, logger, False) as client:
        while now < end_time and posh_user.status != PoshUser.INACTIVE and campaign.status == '1':
            while now.strftime('%I %p') in campaign.times and posh_user.status != PoshUser.INACTIVE and campaign.status == '1':
                campaign.refresh_from_db()
                posh_user.refresh_from_db()
                now = datetime.datetime.now(pytz.utc)

                listing_titles = client.get_all_listings()

                for listing_title in listing_titles:
                    pre_share_time = time.time()
                    if client.share_item(listing_title):
                        positive_negative = 1 if random.random() < 0.5 else -1
                        deviation = random.randint(0, max_deviation) * positive_negative
                        post_share_time = time.time()
                        elapsed_time = round(post_share_time - pre_share_time, 2)
                        sleep_amount = (campaign.delay - elapsed_time) + deviation

                        if elapsed_time < sleep_amount:
                            client.sleep(sleep_amount)
                    else:
                        break

                if logged_hour_message:
                    logged_hour_message = False

            if not logged_hour_message and campaign.status == '1' and posh_user.status == PoshUser.INUSE:
                logger.info(f"This campaign is not set to run at {now.astimezone(pytz.timezone('US/Eastern')).strftime('%I %p')}, sleeping...")

    logger.info('Campaign Ended')

    campaign.status = '2'
    campaign.save()
