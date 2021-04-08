import datetime
import pytz
import random
import time

from django.utils import timezone
from celery import shared_task, chain

from .models import PoshUser, Log, Campaign, Listing
from poshmark.poshmark_client.poshmark_client import PoshMarkClient


@shared_task
def log_cleanup():
    logs = Log.objects.filter(created__lte=timezone.now()-datetime.timedelta(days=2))

    for log in logs:
        log.delete()


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
    with PoshMarkClient(posh_user, logger, False) as client:
        now = datetime.datetime.now(pytz.utc)
        end_time = (now + datetime.timedelta(days=1)).replace(hour=7, minute=55, microsecond=0)
        while now < end_time and posh_user.status != PoshUser.INACTIVE and campaign.status == '1':
            campaign.refresh_from_db()
            posh_user.refresh_from_db()
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

    if campaign.status == '1':
        return campaign_id
    elif campaign.status == '3':
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
    with PoshMarkClient(posh_user, logger, False) as client:
        client.check_ip('campaign_ip')
        while now < end_time and posh_user.status != PoshUser.INACTIVE and campaign.status == '1' and not posted_new_listings:
            campaign.refresh_from_db()
            posh_user.refresh_from_db()
            now = datetime.datetime.now(pytz.utc)
            while now.strftime('%I %p') in campaign.times and posh_user.status != PoshUser.INACTIVE and campaign.status == '1' and not posted_new_listings:
                campaign.refresh_from_db()
                posh_user.refresh_from_db()
                now = datetime.datetime.now(pytz.utc)

                if posh_user.status == PoshUser.WREGISTER:
                    client.register()
                    posh_user.refresh_from_db()
                    if posh_user.status == PoshUser.ACTIVE:
                        client.update_profile()
                    posh_user.status = PoshUser.INUSE
                    posh_user.save()

                while not posh_user.meet_posh and posh_user.status != PoshUser.INACTIVE and campaign.status == '1':
                    campaign.refresh_from_db()
                    posh_user.refresh_from_db()
                    if client.check_listing('Meet your Posher'):
                        posh_user.meet_posh = True
                        posh_user.save()
                    else:
                        client.sleep(60)

                listing_titles = client.get_all_listings()
                listings_to_list = [listing for listing in campaign_listings if listing.title not in listing_titles]
                while len(fake_listing_titles) != len(listings_to_list) and posh_user.status != PoshUser.INACTIVE and campaign.status == '1':
                    campaign.refresh_from_db()
                    posh_user.refresh_from_db()
                    title = client.list_item()
                    client.sleep(12)
                    if title:
                        if client.check_listing(title):
                            if client.share_item(title):
                                if title:
                                    fake_listing_titles.append(title)
                            else:
                                client.delete_listing(title)
                        client.sleep(random.randint(16, 30))
                if posh_user.status != PoshUser.INACTIVE and campaign.status == '1':
                    for index, value in enumerate(listings_to_list):
                        client.update_listing(fake_listing_titles[index], value, 'Saks Fifth Avenue')
                        client.update_listing(value.title, value)
                        client.sleep(random.randint(16, 30))
                    posted_new_listings = True
                else:
                    break

                if logged_hour_message:
                    logged_hour_message = False

            if not logged_hour_message and campaign.status == '1' and posh_user.status == PoshUser.INUSE:
                logger.info(
                    f"This campaign is not set to run at {now.astimezone(pytz.timezone('US/Eastern')).strftime('%I %p')}, sleeping...")
                logged_hour_message = True

    with PoshMarkClient(posh_user, logger, False) as client:
        while now < end_time and posh_user.status != PoshUser.INACTIVE and campaign.status == '1':
            campaign.refresh_from_db()
            posh_user.refresh_from_db()
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
                logged_hour_message = True

    logger.info('Campaign Ended')

    if campaign.status == '1':
        return campaign_id
    elif campaign.status == '3':
        campaign.status = '2'
        campaign.save()


@shared_task
def restart_task(*args, **kwargs):
    campaign_id = args[0]
    campaign = Campaign.objects.get(id=campaign_id)
    old_posh_user = campaign.posh_user

    if campaign.mode == Campaign.BASIC_SHARING:
        if campaign.auto_run:
            task = chain(basic_sharing.s(campaign_id), restart_task.s()).apply_async()
        else:
            task = basic_sharing.delay(campaign_id)
    elif campaign.mode == Campaign.ADVANCED_SHARING:
        if campaign.auto_run:
            if old_posh_user.status == PoshUser.INACTIVE and campaign.generate_users:
                new_posh_user = old_posh_user.generate_random_posh_user()

                campaign.posh_user = new_posh_user

                campaign.save()

            task = chain(advanced_sharing.s(campaign_id), restart_task.s()).apply_async()
        else:
            task = advanced_sharing.delay(campaign_id)
