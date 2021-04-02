import json
import logging
import mailslurp_client
import names
import os
import random
import requests
import string

from django.db import models
from django.utils import timezone
from gender_guesser import detector as gender
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFill, Transpose
from mailslurp_client.exceptions import ApiException
from users.models import User


class PoshUser(models.Model):
    INUSE = '0'
    ACTIVE = '1'
    INACTIVE = '2'
    WALIAS = '3'
    WREGISTER = '4'
    REGISTERING = '5'
    UPROFILE = '6'

    STATUS_CHOICES = [
        (INUSE, 'In Use'),
        (ACTIVE, 'Active'),
        (INACTIVE, 'Inactive'),
        (WALIAS, 'Waiting for alias email to be verified'),
        (WREGISTER, 'Waiting to be registered'),
        (WREGISTER, 'Registering'),
        (UPROFILE, 'Updating Profile'),
    ]

    GENDER_CHOICES = [
        ('', ''),
        ('2', 'Male'),
        ('1', 'Female'),
        ('0', 'Unspecified'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)

    proxy_port = models.IntegerField(null=True)

    date_added = models.DateField(auto_now_add=True, null=True)

    is_email_verified = models.BooleanField(default=False)
    meet_posh = models.BooleanField(default=False)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True,
                              help_text="If alias is chosen up top then put the email you wish to mask here. Otherwise "
                                        "put the email you wish to create the Posh User with.")
    masked_email = models.EmailField(default="", blank=True)
    alias_email_id = models.CharField(max_length=100, default="", blank=True)
    username = models.CharField(max_length=15, unique=True)
    password = models.CharField(max_length=20,
                                help_text='Must be at least 6 characters and must contain a number or symbol.')
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES, blank=True)
    profile_picture = ProcessedImageField(
        processors=[
            Transpose(),
            ResizeToFill(200, 200)
        ],
        format='PNG',
        options={'quality': 60},
        blank=True
    )
    header_picture = ProcessedImageField(
        processors=[
            Transpose(),
            ResizeToFill(1200, 200)
        ],
        format='PNG',
        options={'quality': 60},
        blank=True
    )

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'

    def get_gender(self):
        """Returns gender string from code"""
        genders = {
            '2': 'Male',
            '1': 'Female',
            '0': 'Unspecified',
        }

        return genders[self.gender]

    def generate_sign_up_info(self):
        first_name = names.get_first_name()
        last_name = names.get_last_name()
        username = self.generate_username(first_name, last_name)
        password = self.generate_password()
        user_gender = self.guess_gender(first_name)

        signup_info = {
            'first_name': first_name,
            'last_name': last_name,
            'username': username,
            'password': password,
            'gender': user_gender
        }

        return signup_info

    def generate_email(self, master_email):
        """Using the mailslurp library it will generate a random email as an alias to a given email. It also checks to
        ensure you have more aliases to assign"""
        configuration = mailslurp_client.Configuration()
        configuration.api_key['x-api-key'] = os.environ['MAILSLURP_API_KEY']

        with mailslurp_client.ApiClient(configuration) as api_client:
            api_instance = mailslurp_client.AliasControllerApi(api_client)

            create_alias_options = mailslurp_client.CreateAliasOptions(email_address=master_email, name=str(self.username))

            try:
                api_response = api_instance.create_alias(create_alias_options)
            except ApiException as e:
                logging.error(f'Exception when calling AliasControllerApi->create_alias {e}\n')

            return api_response

    def generate_proxy_port(self, logger):
        data = {
            'zone':
                {
                    'name': self.username
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

        if zone_response.status_code != requests.codes.ok:
            logger.critical('Zone could not be created - Not registering')
        else:
            last_user = PoshUser.objects.all().order_by('proxy_port').last()
            last_port = last_user.proxy_port if last_user else None
            headers = {'Content-Type': 'application/json'}
            data = {
                'proxy':
                    {
                        'port': last_port + 1 if last_port else 24000,
                        'zone': self.username,
                        'proxy_type': 'persist',
                        'customer': os.environ['PROXY_CUSTOMER'],
                        'password': zone_response_json['zone']['password'][0],
                        'whitelist_ips': ["0.0.0.0/0"],
                        'country': 'us',
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
                self.proxy_port = port

            self.save()

    def delete_alias_email(self):
        """Using the mailslurp client it deletes it's alias email"""
        if self.alias_email_id:
            configuration = mailslurp_client.Configuration()
            configuration.api_key['x-api-key'] = os.environ['MAILSLURP_API_KEY']

            with mailslurp_client.ApiClient(configuration) as api_client:
                api_instance = mailslurp_client.AliasControllerApi(api_client)
                api_instance.delete_alias(self.alias_email_id)

    @staticmethod
    def check_alias_email():
        """Using the mailslurp client it checks if we the account has anymore aliases to create"""
        configuration = mailslurp_client.Configuration()
        configuration.api_key['x-api-key'] = os.environ['MAILSLURP_API_KEY']

        with mailslurp_client.ApiClient(configuration) as api_client:
            api_instance = mailslurp_client.AliasControllerApi(api_client)
            number_of_aliases = api_instance.get_aliases().number_of_elements
            if number_of_aliases >= int(os.environ.get('MAX_ALIASES', '1')):
                logging.warning(f'The limit of email aliases have been met - '
                                f'Total Number of Aliases {number_of_aliases}')
                return False
            else:
                return True

    def check_email_verified(self):
        """Using the mailslurp client to check if an alias is verified"""
        configuration = mailslurp_client.Configuration()
        configuration.api_key['x-api-key'] = os.environ['MAILSLURP_API_KEY']

        with mailslurp_client.ApiClient(configuration) as api_client:
            api_instance = mailslurp_client.AliasControllerApi(api_client)
            if self.alias_email_id:
                alias = api_instance.get_alias(self.alias_email_id)

                return alias.is_verified
            else:
                return True

    @staticmethod
    def generate_username(first_name, last_name):
        username = f'{first_name.lower()}_{last_name.lower()}'
        username_length = len(username)

        if username_length > 12:
            username = username[:(12 - username_length)]

        random_int = random.randint(100, 999)
        response = requests.get(f'https://poshmark.com/closet/{username}{random_int}')

        while response.status_code == requests.codes.ok:
            random_int = random.randint(100, 999)
            response = requests.get(f'https://poshmark.com/closet/{username}{random_int}')

        return f'{username}{random_int}'

    @staticmethod
    def generate_password():
        password_characters = string.ascii_letters + string.digits + string.punctuation
        password = ''.join(random.choice(password_characters) for i in range(10))

        return password

    @staticmethod
    def guess_gender(name):
        """Using the gender-guesser library will try to guess the gender based on the first name, if it does not find
        a good answer it sets it to Unspecified"""
        detector = gender.Detector()

        genders = {
            'male': '2',
            'mostly_male': '2',
            'female': '1',
            'mostly_female': '1',
            'andy': '0',
            'unknown': '0',
        }

        return genders[detector.get_gender(name)]

    def __str__(self):
        return f'Posh User - Username: {self.username}'


class Campaign(models.Model):
    STATUS_CHOICES = [
        ('1', 'Running'),
        ('2', 'Idle'),
        ('3', 'Stopping'),
    ]

    BASIC_SHARING = '0'
    ADVANCED_SHARING = '1'

    MODE_CHOICES = [
        (BASIC_SHARING, 'Basic Sharing'),
        (ADVANCED_SHARING, 'Advanced Sharing'),
    ]

    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default='0')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    posh_user = models.OneToOneField(PoshUser, on_delete=models.CASCADE)

    title = models.CharField(max_length=30)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES)
    times = models.CharField(max_length=255)

    delay = models.IntegerField()

    auto_run = models.BooleanField(default=False)
    generate_users = models.BooleanField(default=False)

    def __str__(self):
        return f'Campaign - Title: {self.title} Username: {self.posh_user.username}'


class Listing(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    cover_photo = ProcessedImageField(
        processors=[
            Transpose(),
            ResizeToFill(1000, 1000)
        ],
        format='PNG',
        options={'quality': 60},
        blank=True
    )

    title = models.CharField(max_length=50)
    size = models.CharField(max_length=20)
    brand = models.CharField(max_length=30)
    category = models.CharField(max_length=30)
    subcategory = models.CharField(max_length=30)

    description = models.TextField()

    tags = models.BooleanField(default=False)

    original_price = models.IntegerField()
    listing_price = models.IntegerField()

    campaign = models.ForeignKey(Campaign, on_delete=models.SET_NULL, null=True)

    def get_photos(self):
        """Returns the paths for all the listing's photos"""
        listing_photos = ListingPhotos.objects.filter(listing=self)
        listing_photo_paths = [listing_photo.photo.path for listing_photo in listing_photos]

        return listing_photo_paths

    def __str__(self):
        return self.title


class ListingPhotos(models.Model):
    photo = ProcessedImageField(
        processors=[
            Transpose(),
            ResizeToFill(1000, 1000)
        ],
        format='PNG',
        options={'quality': 60},
        blank=True
    )
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE)


class Log(models.Model):
    OTHER = '0'
    REGISTRATION = '1'
    CAMPAIGN = '2'

    REASON_CHOICES = [
        (OTHER, 'Other'),
        (REGISTRATION, 'Registration'),
        (CAMPAIGN, 'Campaign'),
    ]

    logger_type = models.CharField(max_length=10, choices=REASON_CHOICES)
    posh_user = models.ForeignKey(PoshUser, on_delete=models.CASCADE)
    created = models.DateTimeField(editable=False)

    @staticmethod
    def get_time():
        return timezone.now()

    def log(self, message, log_level=None):
        timestamp = self.get_time()
        log_entries = LogEntry.objects.filter(logger=self).order_by('timestamp')

        if len(log_entries) >= 1000:
            last_log = log_entries.first()
            last_log.delete()

        log_entry = LogEntry(
            level=log_level if log_level else LogEntry.NOTSET,
            logger=self,
            timestamp=timestamp,
            message=message
        )

        log_entry.save()

    def critical(self, message):
        self.log(message, LogEntry.CRITICAL)

    def error(self, message):
        self.log(message, LogEntry.ERROR)

    def warning(self, message):
        self.log(message, LogEntry.WARNING)

    def info(self, message):
        self.log(message, LogEntry.INFO)

    def debug(self, message):
        self.log(message, LogEntry.DEBUG)

    def save(self, *args, **kwargs):
        """On save, update timestamps"""
        if not self.id:
            self.created = timezone.now()
        return super(Log, self).save(*args, **kwargs)

    def __str__(self):
        logger_types = {
            self.OTHER: 'Other',
            self.REGISTRATION: 'Registration',
            self.CAMPAIGN: 'Campaign'
        }
        return f'Log - Username: {self.posh_user.username} Type: {logger_types[self.logger_type]}'


class LogEntry(models.Model):
    CRITICAL = 50
    ERROR = 40
    WARNING = 30
    INFO = 20
    DEBUG = 10
    NOTSET = 0

    LOG_LEVELS = [
        (NOTSET, ''),
        (DEBUG, 'DEBUG'),
        (INFO, 'INFO'),
        (WARNING, 'WARNING'),
        (ERROR, 'ERROR'),
        (CRITICAL, 'CRITICAL'),
    ]

    level = models.IntegerField()
    logger = models.ForeignKey(Log, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    message = models.TextField()
