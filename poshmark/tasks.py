import logging

from .models import PoshUser
from celery import shared_task
from poshmark.poshmark_client.poshmark_client import PoshMarkClient


@shared_task
def posh_user_sign_up(posh_user_id):
    logger = logging.getLogger(__name__)
    posh_user = PoshUser.objects.get(id=posh_user_id)

    with PoshMarkClient(posh_user, logger) as client:
        client.sign_up()
        client.update_profile()


@shared_task
def check_posh_user_signed_up():
    posh_users = PoshUser.objects.filter(is_signed_up=False)

    for posh_user in posh_users:
        logger = logging.getLogger(__name__)

        with PoshMarkClient(posh_user, logger) as client:
            client.sign_up()
            client.update_profile()
