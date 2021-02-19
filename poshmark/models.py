import logging
import mailslurp_client
import names
import os
import random
import string

from django.db import models
from gender_guesser import detector as gender
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFill
from mailslurp_client.exceptions import ApiException


class PoshUser(models.Model):
    STATUS_CHOICES = [
        ('', 'In Use'),
        ('', 'Active'),
        ('', 'Inactive'),
    ]

    GENDER_CHOICES = [
        ('', ''),
        ('2', 'Male'),
        ('1', 'Female'),
        ('0', 'Unspecified'),
    ]

    is_active = models.BooleanField(default=True)
    is_signed_up = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    email = models.EmailField(help_text="If alias is chosen up top then put the email you wish to mask here. Otherwise "
                                        "put the email you wish to create the Posh User with.")
    username = models.CharField(max_length=20, unique=True)
    password = models.CharField(max_length=20)
    gender = models.CharField(max_length=20, choices=GENDER_CHOICES)
    profile_picture = ProcessedImageField(upload_to='profile_pictures',
                                          processors=[ResizeToFill(320, 320)],
                                          format='PNG',
                                          options={'quality': 60},
                                          blank=False)

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'

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
            number_of_aliases = api_instance.get_aliases().number_of_elements
            if number_of_aliases >= int(os.environ.get('MAX_ALIASES', '1')):
                logging.warning(f'The limit of email aliases have been met - '
                                f'Total Number of Aliases {number_of_aliases}')
                return f'[ERROR] The limit of email aliases have been met - Total Number of Aliases {number_of_aliases}'
            else:
                create_alias_options = mailslurp_client.CreateAliasOptions(email_address=master_email, name=str(self))

                try:
                    api_response = api_instance.create_alias(create_alias_options)
                except ApiException as e:
                    logging.error(f'Exception when calling AliasControllerApi->create_alias {e}\n')

                return api_response.email_address

    @staticmethod
    def generate_username(first_name, last_name):
        return f'{first_name.lower()}_{last_name.lower()}{random.randint(100, 999)}'

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
