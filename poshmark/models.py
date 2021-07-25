import logging
import os
import random
import requests
import time
import traceback
import urllib3

from django.db import models
from django.utils import timezone
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFill, Transpose
from users.models import User


class PoshUser(models.Model):
    IDLE = '1'
    INACTIVE = '2'
    RUNNING = '3'
    REGISTERING = '4'
    CREATING = '5'
    FORWARDING = '6'

    STATUS_CHOICES = [
        (IDLE, 'Idle'),
        (INACTIVE, 'Inactive'),
        (RUNNING, 'Running'),
        (REGISTERING, 'Registering'),
        (CREATING, 'Email Creation'),
        (FORWARDING, 'Email Forwarding'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True)

    date_added = models.DateField(auto_now_add=True, null=True)

    is_registered = models.BooleanField(default=False)
    email_registered = models.BooleanField(default=False, null=True)
    email_less_secure_apps_allowed = models.BooleanField(default=False, null=True)
    email_forwarding_enabled = models.BooleanField(default=False, null=True)
    profile_updated = models.BooleanField(default=False)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=30, blank=True)
    redis_id = models.CharField(max_length=40, default='')
    dob_month = models.CharField(max_length=20, default='')
    dob_day = models.CharField(max_length=20, default='')
    dob_year = models.CharField(max_length=20, default='')

    email = models.EmailField(blank=True)
    username = models.CharField(max_length=15, unique=True)
    password = models.CharField(max_length=20,
                                help_text='Must be at least 6 characters and must contain a number or symbol.')
    gender = models.CharField(max_length=20, blank=True)
    profile_picture = models.ImageField()
    header_picture = models.ImageField()

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'

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
    def generate_sign_up_info(results=1):
        months = {
            '01': 'January',
            '02': 'February',
            '03': 'March',
            '04': 'April',
            '05': 'May',
            '06': 'June',
            '07': 'July',
            '08': 'August',
            '09': 'September',
            '10': 'October',
            '11': 'November',
            '12': 'December',
        }
        user_info = {
            'first_name': '',
            'last_name': '',
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; CrOS x86_64 12871.102.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.141 Safari/537.36'
        }

        user_payload = {
            'password': 'upper,lower,number,10-12',
            'inc': 'gender,name,email,login,dob,picture,password',
            'results': str(results)
        }
        user_url = 'https://randomuser.me/api/'
        header_image_url = 'https://picsum.photos/1200/200'
        results = []

        while not PoshUser.is_english(user_info['first_name'] + user_info['last_name']):
            user_response = requests.get(user_url, params=user_payload, timeout=5, headers=headers)
            response_results = user_response.json()['results']
            for response_dict in response_results:
                header_image_response = requests.get(header_image_url, timeout=5, headers=headers)
                username = response_dict['login']['username']
                user_info = {
                    'first_name': response_dict['name']['first'],
                    'last_name': response_dict['name']['last'],
                    'gender': response_dict['gender'].capitalize(),
                    'email': f'{response_dict["email"][:-12]}',
                    'username': username if len(username) <= 12 else username[:12],
                    'password': response_dict['login']['password'],
                    'dob_month': months[response_dict['dob']['date'][5:7]],
                    'dob_day': response_dict['dob']['date'][8:10],
                    'dob_year': response_dict['dob']['date'][:4],
                    'profile_picture': response_dict['picture']['large'],
                    'header_picture': header_image_response.url,
                }

                username_test = requests.get(f'https://poshmark.com/closet/{user_info["username"]}', timeout=5)

                while username_test.status_code == requests.codes.ok:
                    user_info["username"] = PoshUser.generate_username(user_info['first_name'], user_info['last_name'])
                    username_test = requests.get(f'https://poshmark.com/closet/{user_info["username"]}', timeout=5)

                results.append(user_info)

            return results

    @staticmethod
    def create_posh_user(signup_info):
        new_posh_user = PoshUser(
            first_name=signup_info['first_name'],
            last_name=signup_info['last_name'],
            username=signup_info['username'],
            password=signup_info['password'],
            gender=signup_info['gender'],
            email=signup_info['email'],
            dob_month=signup_info['dob_month'],
            dob_day=signup_info['dob_day'],
            dob_year=signup_info['dob_year'],
            status=PoshUser.CREATING,
        )

        for picture_type in ('profile_picture', 'header_picture'):
            file_name = f'{picture_type}_{new_posh_user.username}.jpg'

            with open(file_name, 'wb') as img_temp:
                http = urllib3.PoolManager(timeout=urllib3.Timeout(connect=5))
                r = http.request('GET', signup_info[picture_type])

                img_temp.write(r.data)

            with open(file_name, 'rb') as img_temp:
                if picture_type == 'profile_picture':
                    new_posh_user.profile_picture.save(file_name, img_temp, save=True)
                else:
                    new_posh_user.header_picture.save(file_name, img_temp, save=True)

        os.remove(f'profile_picture_{new_posh_user.username}.jpg')
        os.remove(f'header_picture_{new_posh_user.username}.jpg')

        return new_posh_user

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
    def is_english(text):
        if not text:
            return False
        try:
            text.encode(encoding='utf-8').decode('ascii')
        except UnicodeDecodeError:
            return False
        else:
            return True

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
    REGISTER = '2'

    MODE_CHOICES = [
        (BASIC_SHARING, 'Basic Sharing'),
        (ADVANCED_SHARING, 'Advanced Sharing'),
        (REGISTER, 'Register'),
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
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    created_date = models.DateTimeField(editable=False)
    description = models.CharField(max_length=50, default='')

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
        return f'Log - Username: {self.campaign.title}' if self.campaign else f'Log - Email {self.description}'


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
            try:
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
            except Exception as e:
                logging.info(traceback.format_exc())

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

    def remove_connection(self, posh_user):
        connections = ProxyConnection.objects.filter(posh_user=posh_user, posh_proxy=self)
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
