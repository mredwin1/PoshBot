import datetime
import logging
import pytz
import random
import redis
import time
import traceback

from django import db
from django.conf import settings
from django.utils import timezone
from celery import shared_task

from .models import PoshUser, Log, Campaign, Listing, ListingPhotos, PoshProxy, ProxyConnection
from poshmark.poshmark_client.poshmark_client import PoshMarkClient


def remove_proxy_connection(campaign_id, proxy_id):
    proxy = PoshProxy.objects.get(id=proxy_id)
    posh_user = PoshUser.objects.get(campaign__id=campaign_id)

    proxy.remove_connection(posh_user)


def initialize_campaign(campaign_id, proxy_id=None):
    campaign = Campaign.objects.get(id=campaign_id)
    posh_user = campaign.posh_user
    logger = Log(campaign=campaign, user=campaign.user, posh_user=campaign.posh_user.username)
    logger.save()

    if campaign.mode == Campaign.ADVANCED_SHARING:
        listing = Listing.objects.get(campaign=campaign)
    else:
        listing = None

    if proxy_id:
        proxy = PoshProxy.objects.get(id=proxy_id)
        redis_posh_proxy_id = create_redis_object(proxy)
    else:
        redis_posh_proxy_id = None

    if listing:
        redis_listing_id = create_redis_object(listing)
    else:
        redis_listing_id = None

    redis_campaign_id = create_redis_object(campaign)
    redis_posh_user_id = create_redis_object(posh_user)

    db.connections.close_all()

    return redis_campaign_id, redis_posh_user_id, redis_posh_proxy_id, redis_listing_id, logger.id


def get_redis_object_attr(object_id, field_name=None):
    r = redis.Redis(db=2, decode_responses=True, host=settings.REDIS_HOST, port=settings.REDIS_PORT)
    if field_name:
        return r.hget(object_id, field_name)
    else:
        return r.lrange(object_id, 0, -1)


def create_redis_object(instance):
    r = redis.Redis(db=2, decode_responses=True, host=settings.REDIS_HOST, port=settings.REDIS_PORT)
    instance_type = instance.__class__.__name__
    instance_id = str(random.getrandbits(32))

    r.hset(instance_id, 'instance_type', instance_type)
    r.hset(instance_id, mapping=instance.to_dict())

    if instance_type == 'Listing':
        photos_id = str(random.getrandbits(32))
        for listing_photo in instance.get_photos():
            r.lpush(photos_id, listing_photo)
        r.hset(instance_id, 'photos', photos_id)

    instance.redis_id = instance_id
    instance.save()

    return instance_id


def update_redis_object(object_id, fields):
    r = redis.Redis(db=2, decode_responses=True, host=settings.REDIS_HOST, port=settings.REDIS_PORT)

    if r.hgetall(object_id):
        r.hset(object_id, mapping=fields)

        fields_id = str(random.getrandbits(32))

        # Creates an entry with a unique id and store the value that was updated and the value it got updated to
        r.hset(fields_id, mapping=fields)

        # This maps the updated entry to the object it belongs to
        r.hset('updated', object_id, fields_id)


def log_to_redis(log_id, fields):
    random.seed(444)

    r = redis.Redis(db=1, decode_responses=True, host=settings.REDIS_HOST, port=settings.REDIS_PORT)

    redis_message = {
        'log_id': log_id,
    }

    for key, value in fields.items():
        redis_message[key] = value

    message_id = random.getrandbits(32)

    r.hset(f'Message:{message_id}', mapping=redis_message)


@shared_task
def redis_log_reader():
    try:
        r = redis.Redis(db=1, decode_responses=True, host=settings.REDIS_HOST, port=settings.REDIS_PORT)

        while True:
            for message_id in r.keys():
                log_id = r.hget(message_id, 'log_id')
                log_level = r.hget(message_id, 'level')
                log_message = r.hget(message_id, 'message')

                log = Log.objects.get(id=log_id)

                if log_level == 'CRITICAL':
                    log.critical(log_message)
                elif log_level == 'ERROR':
                    log.error(log_message)
                elif log_level == 'WARNING':
                    log.warning(log_message)
                elif log_level == 'INFO':
                    log.info(log_message)
                elif log_level == 'DEBUG':
                    log.debug(log_message)

                message_keys = r.hkeys(message_id)
                r.hdel(message_id, *message_keys)
    except Exception as e:
        logging.info(traceback.format_exc())
        redis_log_reader.delay()


@shared_task
def redis_instance_reader():
    try:
        r = redis.Redis(db=2, decode_responses=True, host=settings.REDIS_HOST, port=settings.REDIS_PORT)
        instance_types = {
            'PoshUser': PoshUser,
            'Campaign': Campaign,
            'Listing': Listing,
            'PoshProxy': PoshProxy
        }
        while True:
            updated_key = r.hgetall('updated')

            for object_id, fields_id in updated_key.items():
                instance_type = r.hget(object_id, 'instance_type')
                instance_id = r.hget(object_id, 'id')
                model = instance_types[instance_type]

                instance = model.objects.get(id=instance_id)
                fields_to_update = r.hgetall(fields_id)

                updated_fields = []
                for field_name, field_value in fields_to_update.items():
                    updated_fields.append(field_name)
                    setattr(instance, field_name, field_value)

                instance.save()

                r.hdel(fields_id, *updated_fields)
                r.hdel('updated', object_id)
    except Exception as e:
        logging.info(traceback.format_exc())
        redis_instance_reader.delay()


@shared_task
def log_cleanup():
    logs = Log.objects.filter(created_date__lte=timezone.now()-datetime.timedelta(days=2))

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
                    elapsed_time = (now - connection.datetime).seconds
                    if elapsed_time > 900:
                        deleted = True
                        broken_campaign = Campaign.objects.get(posh_user=connection.posh_user)
                        broken_campaign.status = '5'
                        broken_campaign.save()
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
    redis_campaign_id, redis_posh_user_id, proxy_id, listing_id, logger_id = initialize_campaign(campaign_id)
    logged_hour_message = False
    max_deviation = round(int(get_redis_object_attr(redis_campaign_id, 'delay')) / 2)
    now = datetime.datetime.now(pytz.utc)
    end_time = now + datetime.timedelta(days=1)
    sent_offer = False

    update_redis_object(redis_campaign_id, {'status': '1'})
    update_redis_object(redis_posh_user_id, {'status': PoshUser.RUNNING})

    log_to_redis(str(logger_id), {'level': 'INFO', 'message': 'Campaign Started'})

    with PoshMarkClient(redis_posh_user_id, redis_campaign_id, logger_id, log_to_redis, get_redis_object_attr, update_redis_object) as client:
        posh_user_status = get_redis_object_attr(redis_posh_user_id, 'status')
        campaign_status = get_redis_object_attr(redis_campaign_id, 'status')
        while now < end_time and posh_user_status != PoshUser.INACTIVE and campaign_status == '1':
            now = datetime.datetime.now(pytz.utc)
            posh_user_status = get_redis_object_attr(redis_posh_user_id, 'status')
            campaign_status = get_redis_object_attr(redis_campaign_id, 'status')
            campaign_delay = get_redis_object_attr(redis_campaign_id, 'delay')
            campaign_times = get_redis_object_attr(redis_campaign_id, 'times').split(',')
            # This inner loop is to run the task for the given hour
            while now.strftime('%I %p') in campaign_times and posh_user_status != PoshUser.INACTIVE and campaign_status == '1':
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
                            sleep_amount = (campaign_delay - elapsed_time) + deviation

                            if elapsed_time < sleep_amount:
                                client.sleep(sleep_amount)
                    elif not listing_titles['shareable_listings'] and not listing_titles['sold_listings'] and not listing_titles['reserved_listings']:
                        update_redis_object(redis_posh_user_id, {'status': PoshUser.INACTIVE})

                if logged_hour_message:
                    logged_hour_message = False

            if not logged_hour_message and campaign_status == '1' and posh_user_status == PoshUser.RUNNING:
                log_message = f"This campaign is not set to run at {now.astimezone(pytz.timezone('US/Eastern')).strftime('%I %p')}, sleeping..."
                log_to_redis(str(logger_id), {'level': 'WARNING', 'message': log_message})
                logged_hour_message = True

    log_to_redis(str(logger_id), {'level': 'INFO', 'message': 'Campaign Ended'})

    posh_user_status = get_redis_object_attr(redis_posh_user_id, 'status')
    campaign_status = get_redis_object_attr(redis_campaign_id, 'status')

    update_redis_object(redis_campaign_id, {'status': '2'})

    if posh_user_status != PoshUser.INACTIVE:
        update_redis_object(redis_posh_user_id, {'status': PoshUser.IDLE})

    if campaign_status == '1' or campaign_status == '5':
        restart_task.delay(campaign_id)


@shared_task
def advanced_sharing(campaign_id, proxy_id):
    redis_campaign_id, redis_posh_user_id, redis_proxy_id, redis_listing_id, logger_id = initialize_campaign(campaign_id, proxy_id)
    listed_item = False
    logged_hour_message = False
    sent_offer = False
    max_deviation = round(int(get_redis_object_attr(redis_campaign_id, 'delay')) / 2)
    now = datetime.datetime.now(pytz.utc)
    end_time = now + datetime.timedelta(days=1)

    if get_redis_object_attr(redis_posh_user_id, 'status') != PoshUser.INACTIVE:
        update_redis_object(redis_campaign_id, {'status': '1'})
        update_redis_object(redis_posh_user_id, {'status': PoshUser.REGISTERING})

    log_to_redis(str(logger_id), {'level': 'INFO', 'message': 'Campaign Started'})

    with PoshMarkClient(redis_posh_user_id, redis_campaign_id, logger_id, log_to_redis, get_redis_object_attr, update_redis_object, redis_proxy_id) as proxy_client:
        posh_user_status = get_redis_object_attr(redis_posh_user_id, 'status')
        campaign_status = get_redis_object_attr(redis_campaign_id, 'status')
        while now < end_time and posh_user_status != PoshUser.INACTIVE and campaign_status == '1' and not listed_item:
            now = datetime.datetime.now(pytz.utc)
            posh_user_status = get_redis_object_attr(redis_posh_user_id, 'status')
            campaign_status = get_redis_object_attr(redis_campaign_id, 'status')
            campaign_times = get_redis_object_attr(redis_campaign_id, 'times').split(',')
            # This inner loop is to run the task for the given hour
            while now.strftime('%I %p') in campaign_times and posh_user_status != PoshUser.INACTIVE and campaign_status == '1' and not listed_item:
                now = datetime.datetime.now(pytz.utc)
                posh_user_status = get_redis_object_attr(redis_posh_user_id, 'status')
                campaign_status = get_redis_object_attr(redis_campaign_id, 'status')
                posh_user_is_registered = int(get_redis_object_attr(redis_posh_user_id, 'is_registered'))
                while not posh_user_is_registered and posh_user_status != PoshUser.INACTIVE and campaign_status == '1':
                    proxy_client.register()
                    posh_user_is_registered = int(get_redis_object_attr(redis_posh_user_id, 'is_registered'))
                    posh_user_status = get_redis_object_attr(redis_posh_user_id, 'status')
                    campaign_status = get_redis_object_attr(redis_campaign_id, 'status')

                posh_user_profile_updated = int(get_redis_object_attr(redis_posh_user_id, 'profile_updated'))
                while posh_user_is_registered and not posh_user_profile_updated and posh_user_status != PoshUser.INACTIVE and campaign_status == '1':
                    proxy_client.update_profile()
                    posh_user_is_registered = int(get_redis_object_attr(redis_posh_user_id, 'is_registered'))
                    posh_user_status = get_redis_object_attr(redis_posh_user_id, 'status')
                    campaign_status = get_redis_object_attr(redis_campaign_id, 'status')
                    posh_user_profile_updated = int(get_redis_object_attr(redis_posh_user_id, 'profile_updated'))
                meet_your_posh_retries = 0
                if posh_user_is_registered:
                    listing_title = get_redis_object_attr(redis_listing_id, 'title')
                    listing_found = proxy_client.check_listing(listing_title)
                    while not listing_found and posh_user_status != PoshUser.INACTIVE and campaign_status == '1' and not listed_item:
                        posh_user_status = get_redis_object_attr(redis_posh_user_id, 'status')
                        campaign_status = get_redis_object_attr(redis_campaign_id, 'status')
                        while not proxy_client.check_listing('Meet your Posher') and posh_user_status != PoshUser.INACTIVE and campaign_status == '1':
                            meet_your_posh_retries += 1
                            proxy_client.sleep(30)
                        if meet_your_posh_retries > 8:
                            log_to_redis(str(logger_id), {'level': 'ERROR', 'message': f'Meet your posher did not come up after {meet_your_posh_retries}. Setting the user inactive.'})
                            update_redis_object(redis_posh_user_id, {'status': PoshUser.INACTIVE})
                        else:
                            posh_user_first_name = get_redis_object_attr(redis_posh_user_id, 'first_name')
                            proxy_client.update_listing(f'Meet your Posher, {posh_user_first_name}', redis_listing_id)
                            proxy_client.update_listing(listing_title, redis_listing_id, True)
                            listed_item = True
                    else:
                        if not listed_item and listing_found:
                            listed_item = True
                            log_to_redis(str(logger_id), {'level': 'WARNING', 'message': f'{listing_title} already listed, not re listing'})

    remove_proxy_connection(campaign_id, proxy_id)

    if get_redis_object_attr(redis_posh_user_id, 'status') != PoshUser.INACTIVE:
        update_redis_object(redis_posh_user_id, {'status': PoshUser.RUNNING})

    if int(get_redis_object_attr(redis_posh_user_id, 'is_registered')):
        update_redis_object(redis_proxy_id, {'registered_accounts': int(get_redis_object_attr(redis_proxy_id, 'registered_accounts')) + 1})
        with PoshMarkClient(redis_posh_user_id, redis_campaign_id, logger_id, log_to_redis, get_redis_object_attr, update_redis_object) as no_proxy_client:
            posh_user_status = get_redis_object_attr(redis_posh_user_id, 'status')
            campaign_status = get_redis_object_attr(redis_campaign_id, 'status')
            while now < end_time and posh_user_status != PoshUser.INACTIVE and campaign_status == '1':
                now = datetime.datetime.now(pytz.utc)
                posh_user_status = get_redis_object_attr(redis_posh_user_id, 'status')
                campaign_status = get_redis_object_attr(redis_campaign_id, 'status')
                campaign_delay = int(get_redis_object_attr(redis_campaign_id, 'delay'))
                campaign_times = get_redis_object_attr(redis_campaign_id, 'times').split(',')
                # This inner loop is to run the task for the given hour
                while now.strftime('%I %p') in campaign_times and posh_user_status != PoshUser.INACTIVE and campaign_status == '1':
                    now = datetime.datetime.now(pytz.utc)
                    posh_user_status = get_redis_object_attr(redis_posh_user_id, 'status')
                    campaign_status = get_redis_object_attr(redis_campaign_id, 'status')

                    listing_titles = no_proxy_client.get_all_listings()
                    if listing_titles:
                        if listing_titles['shareable_listings']:
                            for listing_title in listing_titles['shareable_listings']:
                                if '[FKE]' in listing_title:
                                    update_redis_object(redis_campaign_id, {'status': '5'})
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
                                    sleep_amount = (campaign_delay - elapsed_time) + deviation

                                    if elapsed_time < sleep_amount:
                                        no_proxy_client.sleep(sleep_amount)
                        elif not listing_titles['shareable_listings'] and not listing_titles['sold_listings'] and not listing_titles['reserved_listings']:
                            update_redis_object(redis_posh_user_id, {'status': PoshUser.INACTIVE})

                    if logged_hour_message:
                        logged_hour_message = False

                if not logged_hour_message and campaign_status == '1' and posh_user_status == PoshUser.RUNNING:
                    log_to_redis(str(logger_id), {'level': 'WARNING', 'message': f"This campaign is not set to run at {now.astimezone(pytz.timezone('US/Eastern')).strftime('%I %p')}, sleeping..."})
                    logged_hour_message = True

    if get_redis_object_attr(redis_posh_user_id, 'status') != PoshUser.INACTIVE:
        update_redis_object(redis_posh_user_id, {'status': PoshUser.IDLE})

    log_to_redis(str(logger_id), {'level': 'INFO', 'message': 'Campaign Ended'})

    campaign_status = get_redis_object_attr(redis_campaign_id, 'status')
    if campaign_status == '1' or campaign_status == '5':
        update_redis_object(redis_campaign_id, {'status': '2'})
        restart_task.delay(get_redis_object_attr(redis_campaign_id, 'id'))
    elif campaign_status == '3':
        update_redis_object(redis_campaign_id, {'status': '2'})


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
            campaign.posh_user.status = PoshUser.IDLE
            campaign.posh_user.save()

            old_posh_user.delete()
        elif old_posh_user.status == PoshUser.INACTIVE:
            run_again = False

        if run_again:
            campaign.status = '4'
            campaign.save()
            start_campaign.delay(campaign_id)
        else:
            campaign.status = '2'
            campaign.save()
