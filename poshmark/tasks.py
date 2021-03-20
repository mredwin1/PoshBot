import datetime
import json
import os
import pytz
import random
import requests
import time

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
    data = {
        'zone':
            {
                'name': posh_user.username
            },
        'plan':
            {
                'type': 'static',
                'pool_ip_type': 'static_res',
                'ip_fallback': 1,
                'ips_type': 'shared',
                'ips': 1,
                'country': 'us'
            },
        'ips': ['any'],
        'perm': 'country'
    }

    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {os.environ["PROXY_API_KEY"]}'}

    zone_response = requests.post('https://luminati.io/api/zone', data=json.dumps(data), headers=headers)
    zone_response_json = zone_response.json()

    logger = Log(logger_type='1', posh_user=posh_user)
    logger.save()

    if zone_response.status_code != requests.codes.ok:
        logger.critical('Zone could not be created - Not registering')
    else:
        last_port = PoshUser.objects.all().order_by('proxy_port').first().proxy_port
        headers = {'Content-Type': 'application/json'}
        data = {
            'proxy':
                {
                    'port': last_port + 1 if last_port else 24000,
                    'zone': posh_user.username,
                    'proxy_type': 'persist',
                    'customer': os.environ['PROXY_CUSTOMER'],
                    'password': zone_response_json['zone']['password'][0],
                    'whitelist_ips': [],
                }
        }
        port_response = requests.post('http://lpm:22999/api/proxies', data=json.dumps(data), headers=headers)
        port_response_json = port_response.json()
        if 'errors' in port_response_json.keys():
            logger.critical('The following errors encountered while creating a port')
            for error in port_response_json['errors']:
                logger.critical(f"{error['msg']}")
        else:
            port = port_response_json['data']['port']
            posh_user.proxy_port = port
            posh_user.save()

            with PoshMarkClient(posh_user, logger) as client:
                client.register()
                client.update_profile()


@shared_task
def basic_sharing(campaign_id):
    campaign = Campaign.objects.get(id=campaign_id)
    posh_user = campaign.posh_user
    logger = Log(logger_type='2', posh_user=posh_user)

    campaign.status = '1'
    campaign.save()
    logger.save()

    logger.info('Starting Campaign')
    with PoshMarkClient(posh_user, logger) as client:
        now = datetime.datetime.now(pytz.utc)
        end_time = now + datetime.timedelta(days=1)
        logger.debug(f'Campaign Times: {campaign.times}')
        logger.debug(f'End Time: {end_time}')
        now = datetime.datetime.now(pytz.utc)
        while now < end_time and now.strftime('%I %p') in campaign.times and posh_user.status != '2' and campaign.status == '1':
            now = datetime.datetime.now(pytz.utc)
            campaign.refresh_from_db()
            logger.debug(f"Current Time: {now} Hour: {now.strftime('%I %p')} ")
            client.sleep(campaign.delay)

    logger.info('Campaign Ended')

    campaign.status = '2'
    campaign.save()


@shared_task
def advanced_sharing(campaign_id):
    campaign = Campaign.objects.get(id=campaign_id)
    posh_user = campaign.posh_user
    logger = Log(logger_type='2', posh_user=posh_user)
    listings = Listing.objects.filter(campaign__id=campaign_id)
    logged_hour_message = False
    meet_posh_attempts = 0
    fake_listing_titles = []
    fake_listings_made = False

    campaign.status = '1'
    campaign.save()
    logger.save()

    logger.info('Starting Campaign')
    with PoshMarkClient(posh_user, logger) as client:
        now = datetime.datetime.now(pytz.utc)
        end_time = now + datetime.timedelta(days=1)
        while now < end_time and posh_user.status != '2' and campaign.status == '1':

            while not posh_user.meet_posh and meet_posh_attempts < 3:
                if client.check_listing('Meet your Posher'):
                    client.posh_user.meet_posh = True
                    client.posh_user.save()
                client.sleep(60)

            while now.strftime('%I %p') in campaign.times and posh_user.status != '2' and campaign.status == '1':
                while len(fake_listing_titles) != len(listings):
                    title = client.list_item()
                    if client.check_listing(title):
                        if client.share_item(title):
                            fake_listing_titles.append(title)
                        else:
                            client.delete_listing(title)
                    client.sleep(random.randint(16, 30))

                if not fake_listings_made:
                    for index, value in enumerate(listings):
                        client.update_listing(fake_listing_titles[index], value, 'Saks Fifth Avenue')
                        client.update_listing(value.title, value)
                        client.sleep(random.randint(16, 30))
                    fake_listings_made = True

                campaign.refresh_from_db()
                now = datetime.datetime.now(pytz.utc)
                for listing in listings:
                    pre_share_time = time.time()
                    client.share_item(listing)
                    post_share_time = time.time()

                    elapsed_time = post_share_time - pre_share_time
                    if elapsed_time < campaign.delay:
                        client.sleep(campaign.delay - elapsed_time)

                if logged_hour_message:
                    logged_hour_message = False

            if not logged_hour_message and campaign.status == '1' and posh_user.status == '0':
                logger.info(f"This campaign is not set to run at {now.astimezone(pytz.timezone('US/Eastern')).strftime('%I %p')}, sleeping...")

    logger.info('Campaign Ended')

    campaign.status = '2'
    campaign.save()
