from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    is_active = models.BooleanField(default=True, verbose_name='Active')
    is_superuser = models.BooleanField(default=False, verbose_name='Superuser')
    is_staff = models.BooleanField(default=False, verbose_name='Staff')

    username = models.CharField(max_length=30, verbose_name='Username', unique=True)
    email_password = models.CharField(max_length=50, verbose_name='Email Password', default='')

    master_email = models.EmailField(
        verbose_name='Master Email',
        help_text='Where all the emails for your accounts will forward to',
        default=''
    )

    accounts_to_maintain = models.IntegerField(default=0)

    objects = UserManager()

    USERNAME_FIELD = 'username'

    def __str__(self):
        return self.username
