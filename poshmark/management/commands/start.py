import logging
import os
import socket
import sys
import time

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db.utils import OperationalError

from users.models import User
from poshmark.models import Campaign, ProxyConnection, PoshUser, Log
from poshmark.tasks import redis_log_reader, redis_instance_reader


class Command(BaseCommand):
    help = 'An alternative to runserver which will run migrate and collectstatic beforehand'

    def handle(self, *args, **options):
        # Attempt to connect to the database socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        attempts_left = 10
        while attempts_left:
            try:
                # Ignore 'incomplete startup packet'
                s.connect((os.environ['SQL_HOST'], int(os.environ['SQL_PORT'])))
                s.shutdown(socket.SHUT_RDWR)
                logging.info('Database is ready.')
                break
            except socket.error:
                attempts_left -= 1
                logging.warning('Database not ready yet, retrying.')
                time.sleep(2)
        else:
            logging.error('Database could not be found, exiting.')
            sys.exit('Database not found')

        attempts_left = 5
        while attempts_left:
            try:
                logging.info('Trying to run migrations...')
                call_command("migrate")
                logging.info('Migrations complete')
                break
            except OperationalError as error:
                if error.args[0] == 'FATAL:  the database system is starting up\n':
                    attempts_left -= 1
                    logging.warning('Cannot run migrations because the database system is starting up, retrying.')
                    time.sleep(0.5)
                else:
                    sys.exit(f'Migrations unsuccessful. Error: {error.args}')
        else:
            logging.error('Migrations could not be run, exiting.')
            sys.exit('Migrations unsuccessful')

        if not User.objects.filter(username=os.environ['SUPER_USERNAME']).exists():
            User.objects.create_superuser(
                username=os.environ['SUPER_USERNAME'],
                password=os.environ['SUPER_PASSWORD'],
            )
            logging.info('Superuser created.')
        else:
            logging.info('Superuser already created, skipping that step.')

        logging.info('Running collectstatic...')
        call_command("collectstatic", interactive=False, clear=True)

        logging.info('Setting all campaigns to IDLE status')
        campaigns = Campaign.objects.exclude(status=2)
        for campaign in campaigns:
            campaign.status = '2'
            campaign.save()

        logging.info('Setting all Posh Users to IDLE status')
        posh_users = PoshUser.objects.exclude(status__in=(PoshUser.INACTIVE, PoshUser.CREATING, PoshUser.FORWARDING))
        for posh_user in posh_users:
            posh_user.status = PoshUser.IDLE
            posh_user.save()

        posh_users_to_delete = PoshUser.objects.filter(status__in=(PoshUser.CREATING, PoshUser.FORWARDING))
        for posh_user_to_delete in posh_users_to_delete:
            logs = Log.objects.filter(description=posh_user_to_delete.email)

            for log in logs:
                log.delete()

            posh_user_to_delete.delete()

        logging.info('Removing all proxy connections')
        connections = ProxyConnection.objects.all()
        connections.delete()

        logging.info('Starting redis log reader...')
        redis_log_reader.delay()

        logging.info('Starting redis instance reader...')
        redis_instance_reader.delay()

        logging.info('Starting server...')
        os.system("gunicorn --preload -b 0.0.0.0:80 PoshBot.wsgi:application --threads 8 -w 4")
        exit()
