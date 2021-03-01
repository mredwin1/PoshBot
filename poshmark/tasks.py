from .models import PoshUser, Log
from celery import shared_task
from poshmark.poshmark_client.poshmark_client import PoshMarkClient


@shared_task
def register_posh_user(posh_user_id):
    """Registers a PoshUser to poshmark"""
    posh_user = PoshUser.objects.get(id=posh_user_id)
    logger = Log(logger_type='1', posh_user=posh_user)

    with PoshMarkClient(posh_user, logger) as client:
        client.register()
        client.update_profile()


@shared_task
def check_registered_posh_users():
    """Will get all unregistered users and queue them up to be registered"""
    posh_users = PoshUser.objects.filter(is_registered=False)

    for posh_user in posh_users:
        register_posh_user(posh_user.id)
