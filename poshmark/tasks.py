import datetime

import pytz
import random
import time

from django.utils import timezone
from celery import shared_task, chain

from .models import PoshUser, Log, Campaign, Listing, PoshProxy
from poshmark.poshmark_client.poshmark_client import PoshMarkClient


@shared_task
def log_cleanup():
    logs = Log.objects.filter(created__lte=timezone.now()-datetime.timedelta(days=2))

    for log in logs:
        log.delete()


@shared_task
def start_campaign(campaign_id):
    campaign = Campaign.objects.get(id=campaign_id)
    proxy = PoshProxy.objects.filter(current_connections__lt=2).first()

    while proxy is None:
        time.sleep(30)
        proxy = PoshProxy.objects.filter(current_connections__lt=2).first()

    if proxy.registered_accounts >= proxy.max_accounts:
        while proxy.current_connections != 0:
            time.sleep(30)
            proxy.refresh_from_db()
        proxy.reset_ip()

    proxy.current_connections += 1
    proxy.save()

    task = advanced_sharing.delay(campaign_id, proxy.id)


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
    with PoshMarkClient(posh_user, logger) as client:
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
                if listing_titles:
                    if listing_titles['shareable_listings']:
                        for listing_title in listing_titles['shareable_listings']:
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
def advanced_sharing(campaign_id, proxy_id):
    campaign = Campaign.objects.get(id=campaign_id)
    proxy = PoshProxy.objects.get(id=proxy_id)
    posh_user = campaign.posh_user
    logger = Log(logger_type=Log.CAMPAIGN, posh_user=posh_user)
    all_campaign_listings = Listing.objects.filter(campaign__id=campaign_id)
    campaign_listings = [listing for listing in all_campaign_listings if not listing.sold]
    listed_items = 0
    logged_hour_message = False
    max_deviation = round(campaign.delay / 2)
    meet_your_posher_attempts = 0
    sold_listings = None

    campaign.status = '1'
    campaign.save()
    logger.save()

    if not campaign_listings:
        all_campaign_listings.update(sold=False)
        campaign_listings = Listing.objects.filter(campaign__id=campaign_id)

    logger.info('Starting Campaign')

    with PoshMarkClient(posh_user, logger, proxy) as client:
        now = datetime.datetime.now(pytz.utc)
        end_time = now + datetime.timedelta(days=1)
        # This outer loop is to ensure this task runs as long as the user is active and the campaign has not been stopped
        while now < end_time and posh_user.status != PoshUser.INACTIVE and campaign.status == '1' and listed_items < 1:
            campaign.refresh_from_db()
            posh_user.refresh_from_db()
            now = datetime.datetime.now(pytz.utc)
            # This inner loop is to run the task for the given hour
            while now.strftime('%I %p') in campaign.times and posh_user.status != PoshUser.INACTIVE and campaign.status == '1' and listed_items < 1:
                campaign.refresh_from_db()
                posh_user.refresh_from_db()
                now = datetime.datetime.now(pytz.utc)
                while not posh_user.is_registered and posh_user.status != PoshUser.INACTIVE and campaign.status == '1':
                    client.register()
                    posh_user.refresh_from_db()

                    if posh_user.status == PoshUser.ACTIVE:
                        client.update_profile()
                    if posh_user.status != PoshUser.INACTIVE:
                        posh_user.status = PoshUser.INUSE
                        posh_user.save()

                posh_user.refresh_from_db()
                if listed_items < 1:
                    # This will continue to check for the automatic "Meet your Posher" listing before continuing
                    while not posh_user.meet_posh and posh_user.status != PoshUser.INACTIVE and campaign.status == '1' and meet_your_posher_attempts < 3 and posh_user.is_registered:
                        campaign.refresh_from_db()
                        posh_user.refresh_from_db()
                        if client.check_listing('Meet your Posher'):
                            posh_user.meet_posh = True
                            posh_user.save()
                        else:
                            meet_your_posher_attempts += 1
                            client.sleep(60)

                    if posh_user.is_registered:
                        for listing in campaign_listings:
                            titles = client.get_all_listings()
                            all_titles = titles['shareable_listings'] + titles['sold_listings']
                            listed_item_titles = all_titles if all_titles else []
                            if listing.title not in listed_item_titles:
                                title = client.list_item()
                                client.sleep(20)
                                if title:
                                    if client.check_listing(title):
                                        if client.share_item(title):
                                            client.update_listing(title, listing)
                                            listed_items += 1
                                            break
                                        else:
                                            client.delete_listing(title)
                            else:
                                listed_items += 1
                                logger.warning(f'{listing.title} already listed, not re listing')

    proxy.refresh_from_db()
    posh_user.refresh_from_db()
    if posh_user.is_registered:
        proxy.registered_accounts += 1
        proxy.current_connections -= 1
        proxy.save()

        with PoshMarkClient(posh_user, logger) as client:
            while now < end_time and posh_user.status != PoshUser.INACTIVE and campaign.status == '1':
                campaign.refresh_from_db()
                posh_user.refresh_from_db()
                now = datetime.datetime.now(pytz.utc)
                # This inner loop is to run the task for the given hour
                while now.strftime('%I %p') in campaign.times and posh_user.status != PoshUser.INACTIVE and campaign.status == '1':
                    campaign.refresh_from_db()
                    posh_user.refresh_from_db()
                    now = datetime.datetime.now(pytz.utc)

                    listing_titles = client.get_all_listings()
                    if listing_titles:
                        if listing_titles['shareable_listings']:
                            for listing_title in listing_titles['shareable_listings']:
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
                        else:
                            sold_listings = listing_titles['sold_listings']
                            for listing_title in sold_listings:
                                listing = Listing.objects.get(title=listing_title, campaign__id=campaign_id)
                                listing.sold = True
                                listing.save()

                    if logged_hour_message:
                        logged_hour_message = False

                if not logged_hour_message and campaign.status == '1' and posh_user.status == PoshUser.INUSE:
                    logger.info(
                        f"This campaign is not set to run at {now.astimezone(pytz.timezone('US/Eastern')).strftime('%I %p')}, sleeping...")
                    logged_hour_message = True
    else:
        proxy.current_connections -= 1
        proxy.save()

    logger.info('Campaign Ended')
    campaign.refresh_from_db()
    if campaign.status == '1':
        campaign.status = '2'
        campaign.save()
        restart_task.delay(campaign.id, sold_listings)
    elif campaign.status == '3':
        campaign.status = '2'
        campaign.save()


@shared_task
def restart_task(campaign_id, sold_listings=None):
    campaign = Campaign.objects.get(id=campaign_id)
    old_posh_user = campaign.posh_user
    run_again = True

    if campaign.mode == Campaign.BASIC_SHARING:
        if campaign.auto_run:
            task = chain(basic_sharing.s(campaign_id), restart_task.s()).apply_async()
        else:
            task = basic_sharing.delay(campaign_id)
    elif campaign.mode == Campaign.ADVANCED_SHARING:
        if old_posh_user.status == PoshUser.INACTIVE and campaign.generate_users:
            new_posh_user = old_posh_user.generate_random_posh_user()

            campaign.posh_user = new_posh_user

            campaign.save()
            campaign.posh_user.status = PoshUser.INUSE
            campaign.posh_user.save()

            old_posh_user.delete()

        if sold_listings:
            run_again = False

        if run_again:
            campaign.status = '4'
            start_campaign.delay(campaign_id)
        else:
            campaign.status = '2'
        campaign.save()
