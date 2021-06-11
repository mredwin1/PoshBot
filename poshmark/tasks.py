import datetime
import logging
import pytz
import random
import time

from django.utils import timezone
from django.db.models import Q
from celery import shared_task, chain

from .models import PoshUser, Log, Campaign, Listing, PoshProxy, ProxyConnection
from poshmark.poshmark_client.poshmark_client import PoshMarkClient


@shared_task
def log_cleanup():
    logs = Log.objects.filter(created__lte=timezone.now()-datetime.timedelta(days=2))

    for log in logs:
        log.delete()


@shared_task
def start_campaign(campaign_id):
    selected_proxy = None

    while not selected_proxy:
        proxies = PoshProxy.objects.all()
        for proxy in proxies:
            connections = ProxyConnection.objects.filter(posh_proxy=proxy)
            if len(connections) < proxy.max_connections:
                selected_proxy = proxy
            else:
                now = timezone.now()
                deleted = False
                for connection in connections:
                    if (now - connection.datetime).seconds > 900:
                        deleted = True
                        connection.delete()
                if not deleted:
                    time.sleep(30)

    if selected_proxy.registered_accounts >= selected_proxy.max_accounts:
        connections = ProxyConnection.objects.filter(posh_proxy=selected_proxy)

        while connections:
            time.sleep(30)
            connections = ProxyConnection.objects.filter(posh_proxy=selected_proxy)

        selected_proxy.reset_ip()

    campaign = Campaign.objects.get(id=campaign_id)
    if campaign.status == '4':
        selected_proxy.add_connection(campaign.posh_user)
        advanced_sharing.delay(campaign_id, selected_proxy.id)
    else:
        logging.error('This campaign does not have status starting, cannot start.')


@shared_task
def basic_sharing(campaign_id):
    campaign = Campaign.objects.get(id=campaign_id)
    posh_user = campaign.posh_user
    logger = Log(logger_type=Log.CAMPAIGN, posh_user=posh_user, user=posh_user.user)
    logged_hour_message = False
    max_deviation = round(campaign.delay / 2)
    now = datetime.datetime.now(pytz.utc)
    end_time = now + datetime.timedelta(days=1)
    sent_offer = False
    campaign.status = '1'
    campaign.save()
    logger.save()

    logger.info('Starting Campaign')
    with PoshMarkClient(posh_user, campaign, logger) as client:
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
                            client.share_item(listing_title)
                            client.check_offers(listing_title=listing_title)

                            if not sent_offer and now > end_time.replace(hour=11, minute=0, second=0):
                                sent_offer = client.send_offer_to_likers(listing_title=listing_title)

                            positive_negative = 1 if random.random() < 0.5 else -1
                            deviation = random.randint(0, max_deviation) * positive_negative
                            post_share_time = time.time()
                            elapsed_time = round(post_share_time - pre_share_time, 2)
                            sleep_amount = (campaign.delay - elapsed_time) + deviation

                            if elapsed_time < sleep_amount:
                                client.sleep(sleep_amount)
                    elif not listing_titles['shareable_listings'] and not listing_titles['sold_listings'] and not listing_titles['reserved_listings']:
                        posh_user.status = PoshUser.INACTIVE
                        posh_user.save()

                if logged_hour_message:
                    logged_hour_message = False

            if not logged_hour_message and campaign.status == '1' and posh_user.status == PoshUser.INUSE:
                logger.info(
                    f"This campaign is not set to run at {now.astimezone(pytz.timezone('US/Eastern')).strftime('%I %p')}, sleeping...")
                logged_hour_message = True

    logger.info('Campaign Ended')

    campaign.refresh_from_db()
    if campaign.status == '1' or campaign.status == '5':
        campaign.status = '2'
        campaign.save()
        restart_task.delay(campaign.id)
    elif campaign.status == '3':
        campaign.status = '2'
        campaign.save()


@shared_task
def advanced_sharing(campaign_id, proxy_id):
    campaign = Campaign.objects.get(id=campaign_id)
    proxy = PoshProxy.objects.get(id=proxy_id)
    posh_user = campaign.posh_user
    logger = Log(logger_type=Log.CAMPAIGN, posh_user=posh_user, user=posh_user.user)
    campaign_listings = Listing.objects.filter(campaign__id=campaign_id)
    listed_items = 0
    logged_hour_message = False
    sent_offer = False
    max_deviation = round(campaign.delay / 2)

    campaign.status = '1'
    campaign.save()
    logger.save()

    logger.info('Starting Campaign')

    with PoshMarkClient(posh_user, campaign, logger, proxy) as proxy_client:
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
                    proxy_client.register()
                    posh_user.refresh_from_db()

                    if posh_user.status == PoshUser.ACTIVE:
                        proxy_client.update_profile()
                    if posh_user.status != PoshUser.INACTIVE:
                        posh_user.status = PoshUser.INUSE
                        posh_user.save()

                posh_user.refresh_from_db()
                if posh_user.is_registered:
                    for listing in campaign_listings:
                        listing_found = proxy_client.check_listing(listing.title)
                        while not listing_found and posh_user.status != PoshUser.INACTIVE and campaign.status == '1' and listed_items < 1:
                            campaign.refresh_from_db()
                            posh_user.refresh_from_db()
                            title = proxy_client.list_item()
                            if title:
                                proxy_client.update_listing(title, listing)
                                listed_items += 1
                        else:
                            if listed_items < 1 and listing_found:
                                listed_items += 1
                                logger.warning(f'{listing.title} already listed, not re listing')

    proxy.remove_connection(posh_user)
    
    posh_user.refresh_from_db()
    if posh_user.is_registered:
        proxy.refresh_from_db()
        proxy.registered_accounts += 1
        proxy.save()

        with PoshMarkClient(posh_user, campaign, logger) as no_proxy_client:
            while now < end_time and posh_user.status != PoshUser.INACTIVE and campaign.status == '1':
                campaign.refresh_from_db()
                posh_user.refresh_from_db()
                now = datetime.datetime.now(pytz.utc)
                # This inner loop is to run the task for the given hour
                while now.strftime('%I %p') in campaign.times and posh_user.status != PoshUser.INACTIVE and campaign.status == '1':
                    campaign.refresh_from_db()
                    posh_user.refresh_from_db()
                    now = datetime.datetime.now(pytz.utc)

                    listing_titles = no_proxy_client.get_all_listings()
                    if listing_titles:
                        if listing_titles['shareable_listings']:
                            for listing_title in listing_titles['shareable_listings']:
                                if '[FKE]' in listing_title:
                                    campaign.refresh_from_db()
                                    campaign.status = '5'
                                    campaign.save()
                                    break
                                else:
                                    pre_share_time = time.time()
                                    no_proxy_client.share_item(listing_title)

                                    current_listing = Listing.objects.get(title=listing_title)
                                    no_proxy_client.check_offers(listing=current_listing)

                                    if not sent_offer and now > end_time.replace(hour=11, minute=0, second=0):
                                        sent_offer = no_proxy_client.send_offer_to_likers(listing=current_listing)

                                    positive_negative = 1 if random.random() < 0.5 else -1
                                    deviation = random.randint(0, max_deviation) * positive_negative
                                    post_share_time = time.time()
                                    elapsed_time = round(post_share_time - pre_share_time, 2)
                                    sleep_amount = (campaign.delay - elapsed_time) + deviation

                                    if elapsed_time < sleep_amount:
                                        no_proxy_client.sleep(sleep_amount)
                        elif not listing_titles['shareable_listings'] and not listing_titles['sold_listings'] and not listing_titles['reserved_listings']:
                            posh_user.status = PoshUser.INACTIVE
                            posh_user.save()

                    if logged_hour_message:
                        logged_hour_message = False

                if not logged_hour_message and campaign.status == '1' and posh_user.status == PoshUser.INUSE:
                    logger.info(
                        f"This campaign is not set to run at {now.astimezone(pytz.timezone('US/Eastern')).strftime('%I %p')}, sleeping...")
                    logged_hour_message = True

    logger.info('Campaign Ended')
    campaign.refresh_from_db()
    if campaign.status == '1' or campaign.status == '5':
        campaign.status = '2'
        campaign.save()
        restart_task.delay(campaign.id)
    elif campaign.status == '3':
        campaign.status = '2'
        campaign.save()


@shared_task
def restart_task(campaign_id):
    campaign = Campaign.objects.get(id=campaign_id)
    old_posh_user = campaign.posh_user
    run_again = True

    if campaign.mode == Campaign.BASIC_SHARING:
        basic_sharing.delay(campaign_id)
    elif campaign.mode == Campaign.ADVANCED_SHARING:
        if old_posh_user.status == PoshUser.INACTIVE and campaign.generate_users:
            new_posh_user = old_posh_user.generate_random_posh_user()

            campaign.posh_user = new_posh_user

            campaign.save()
            campaign.posh_user.status = PoshUser.INUSE
            campaign.posh_user.save()

            old_posh_user.delete()
        elif old_posh_user.status == PoshUser.INACTIVE:
            run_again = False

        if run_again:
            campaign.status = '4'
            start_campaign.delay(campaign_id)
        else:
            campaign.status = '2'
        campaign.save()
