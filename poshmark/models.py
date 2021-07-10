import logging
import time

import mailslurp_client
import names
import os
import random
import requests
import string

from django.db import models
from django.utils import timezone
from django_cleanup import cleanup
from gender_guesser import detector as gender
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFill, Transpose
from mailslurp_client.exceptions import ApiException
from users.models import User


@cleanup.ignore
class PoshUser(models.Model):
    IDLE = '1'
    INACTIVE = '2'
    RUNNING = '3'
    REGISTERING = '4'

    STATUS_CHOICES = [
        (IDLE, 'Idle'),
        (INACTIVE, 'Inactive'),
        (RUNNING, 'Campaign running'),
        (REGISTERING, 'Registering'),
    ]

    GENDER_CHOICES = [
        ('', ''),
        ('2', 'Male'),
        ('1', 'Female'),
        ('0', 'Unspecified'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)

    date_added = models.DateField(auto_now_add=True, null=True)

    is_email_verified = models.BooleanField(default=False)
    is_registered = models.BooleanField(default=False)
    profile_updated = models.BooleanField(default=False)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    redis_id = models.CharField(max_length=40, default='')

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

    def generate_sign_up_info(self, old_first_name=None, old_last_name=None):
        first_name = old_first_name if old_first_name else names.get_first_name()
        last_name = old_last_name if old_last_name else names.get_last_name()
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

            create_alias_options = mailslurp_client.CreateAliasOptions(email_address=master_email,
                                                                       name=str(self.username))

            try:
                api_response = api_instance.create_alias(create_alias_options)
            except ApiException as e:
                logging.error(f'Exception when calling AliasControllerApi->create_alias {e}\n')

            return api_response

    def delete_alias_email(self):
        """Using the mailslurp client it deletes it's alias email"""
        if self.alias_email_id:
            configuration = mailslurp_client.Configuration()
            configuration.api_key['x-api-key'] = os.environ['MAILSLURP_API_KEY']

            with mailslurp_client.ApiClient(configuration) as api_client:
                api_instance = mailslurp_client.AliasControllerApi(api_client)
                api_instance.delete_alias(self.alias_email_id)

    def generate_random_posh_user(self):
        signup_info = self.generate_sign_up_info(self.first_name, self.last_name)

        emails = [posh_user.email for posh_user in PoshUser.objects.filter(user=self.user)]

        if len(emails) == 1:
            last_email = emails[0]
        else:
            last_number = 0
            last_email = ''
            for email in emails:
                plus_index = email.find('+')
                at_index = email.find('@')

                if plus_index == -1:
                    pass
                else:
                    number = int(email[plus_index:at_index])

                    if number > last_number:
                        last_number = number
                        last_email = email

        plus_index = last_email.find('+')
        at_index = last_email.find('@')

        if plus_index == -1:
            new_email = f'{last_email[:at_index]}+1{last_email[at_index:]}'
        else:
            number = int(last_email[plus_index:at_index]) + 1
            new_email = f'{last_email[:plus_index + 1]}{number}{last_email[at_index:]}'

        new_posh_user = PoshUser(
            first_name=signup_info['first_name'],
            last_name=signup_info['last_name'],
            username=signup_info['username'],
            password=self.password,
            gender=self.gender,
            user=self.user,
            email=new_email,
            status=PoshUser.IDLE ,
            profile_picture=self.profile_picture,
            header_picture=self.header_picture,
        )
        new_posh_user.save()

        return new_posh_user

    def to_dict(self):
        data = {}
        for field in self._meta.get_fields():
            field_type = field.get_internal_type()
            if field_type not in ('OneToOneField', 'ForeignKey'):
                if field.name == 'profile_picture' or field.name == 'header_picture':
                    picture = field.value_from_object(self)
                    if picture:
                        data[field.name] = picture.path
                    else:
                        data[field.name] = ''
                elif field_type == 'DateField':
                    pass
                elif field_type == 'BooleanField':
                    data[field.name] = int(field.value_from_object(self))
                else:
                    data[field.name] = field.value_from_object(self)
        return data

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
        ('4', 'Starting'),
        ('5', 'Restarting'),
    ]

    BASIC_SHARING = '0'
    ADVANCED_SHARING = '1'

    MODE_CHOICES = [
        (BASIC_SHARING, 'Basic Sharing'),
        (ADVANCED_SHARING, 'Advanced Sharing'),
    ]

    mode = models.CharField(max_length=10, choices=MODE_CHOICES, default='0')
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    posh_user = models.OneToOneField(PoshUser, on_delete=models.SET_NULL, blank=True, null=True)

    title = models.CharField(max_length=30)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES)
    times = models.CharField(max_length=255)
    redis_id = models.CharField(max_length=40, default='')

    delay = models.IntegerField()
    lowest_price = models.IntegerField(blank=True, default=250)

    auto_run = models.BooleanField(default=False)
    generate_users = models.BooleanField(default=False)

    def to_dict(self):
        data = {}
        for field in self._meta.get_fields():
            field_type = field.get_internal_type()
            if field_type not in ('OneToOneField', 'ForeignKey'):
                if field_type == 'DateField':
                    pass
                elif field_type == 'BooleanField':
                    data[field.name] = int(field.value_from_object(self))
                else:
                    data[field.name] = field.value_from_object(self)
        return data

    def __str__(self):
        return f'Campaign - Title: {self.title} Username: {self.posh_user.username if self.posh_user else "None"}'


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
    redis_id = models.CharField(max_length=40, default='')

    description = models.TextField()

    sold = models.BooleanField(default=False)
    tags = models.BooleanField(default=False)

    original_price = models.IntegerField()
    listing_price = models.IntegerField()
    lowest_price = models.IntegerField(default=250)

    campaign = models.ForeignKey(Campaign, on_delete=models.SET_NULL, null=True)

    def to_dict(self):
        data = {}
        for field in self._meta.get_fields():
            field_type = field.get_internal_type()
            if field_type not in ('OneToOneField', 'ForeignKey'):
                if field_type == 'DateField':
                    pass
                elif field_type == 'BooleanField':
                    data[field.name] = int(field.value_from_object(self))
                elif field_type == 'FileField':
                    data[field.name] = field.value_from_object(self).path
                else:
                    data[field.name] = field.value_from_object(self)
        return data

    def get_photos(self):
        """Returns the paths for all the listing's photos"""
        listing_photos = ListingPhotos.objects.filter(listing=self)
        listing_photo_paths = [listing_photo.photo.path for listing_photo in listing_photos]

        return listing_photo_paths

    @staticmethod
    def get_random_listing(sold_listings):
        available_listings = Listing.objects.filter(campaign=None).exclude(title__in=sold_listings)

        if available_listings:
            return random.choice(available_listings)
        else:
            return None

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
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)
    created_date = models.DateTimeField(editable=False)
    posh_user = models.CharField(max_length=20, default='')

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
            self.created_date = timezone.now()
        return super(Log, self).save(*args, **kwargs)

    def __str__(self):
        return f'Log - Username: {self.campaign.title}'


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


class PoshProxy(models.Model):
    registration_proxy = models.BooleanField(default=False)

    ip_reset_url = models.CharField(max_length=200, default='', blank=True)

    max_accounts = models.IntegerField(default=2)
    max_connections = models.IntegerField(default=2)
    registered_accounts = models.IntegerField(default=0, blank=True)

    redis_id = models.CharField(max_length=40, default='', blank=True)

    ip = models.GenericIPAddressField()
    port = models.IntegerField()

    def reset_ip(self):
        if self.ip_reset_url:
            login_response = requests.post(
                'https://portal.proxyguys.com/login',
                data={'username': os.environ['PROXY_USERNAME'], 'password': os.environ['PROXY_PASSWORD']}
            )
            reset_response = requests.get(
                f'{self.ip_reset_url}',
                cookies=login_response.cookies
            )
            time.sleep(10)
        self.registered_accounts = 0
        self.save()

    def add_connection(self, posh_user):
        new_connection = ProxyConnection(
            posh_proxy=self,
            posh_user=posh_user,
            datetime=timezone.now()
        )
        new_connection.save()

    def to_dict(self):
        data = {}
        for field in self._meta.get_fields():
            field_type = field.get_internal_type()
            if field_type not in ('OneToOneField', 'ForeignKey'):
                if field_type == 'DateField':
                    pass
                elif field_type == 'BooleanField':
                    data[field.name] = int(field.value_from_object(self))
                else:
                    data[field.name] = field.value_from_object(self)
        return data

    @staticmethod
    def remove_connection(posh_user):
        connections = ProxyConnection.objects.filter(posh_user=posh_user)
        for connection in connections:
            connection.delete()

    def __str__(self):
        return f'Registration Proxy #{self.id}' if self.registration_proxy else f'Sharing Proxy #{self.id}'


class ProxyConnection(models.Model):
    posh_proxy = models.ForeignKey(PoshProxy, on_delete=models.CASCADE)
    posh_user = models.ForeignKey(PoshUser, on_delete=models.CASCADE, null=True)
    datetime = models.DateTimeField()

    def __str__(self):
        return f'{self.posh_user.username} on {self.posh_proxy}'
