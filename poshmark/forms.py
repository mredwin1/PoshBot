import datetime
import pytz
import random
import requests
import string

from django import forms
from django.core.files.base import ContentFile
from poshmark.models import PoshUser, Listing, ListingPhotos, Campaign


class CreatePoshUser(forms.ModelForm):
    alias = forms.BooleanField(required=False, label='Create Alias')

    is_registered = forms.BooleanField(required=False, label='User is Registered')

    class Meta:
        model = PoshUser
        fields = ['profile_picture', 'header_picture', 'first_name', 'last_name', 'email', 'username', 'password',
                  'gender']

    def __init__(self, request, *args, **kwargs):
        super(CreatePoshUser, self).__init__(*args, **kwargs)
        self.request = request

        self.fields['profile_picture'].required = False
        self.fields['header_picture'].required = False
        self.fields['first_name'].required = False
        self.fields['last_name'].required = False
        self.fields['email'].required = False
        self.fields['gender'].required = False

    def clean(self):
        if not self.cleaned_data['is_registered']:
            if self.cleaned_data['alias']:
                tmp_user = PoshUser()
                can_create_alias = tmp_user.check_alias_email()

                if not can_create_alias:
                    self.add_error('email', 'The limit of email aliases have been met, cannot create more.')

            response = requests.get(f'https://poshmark.com/closet/{self.cleaned_data["username"]}')

            if response.status_code == requests.codes.ok:
                self.add_error('username', 'This username already exists, please pick another.')

            symbols = '[@_!#$%^&*()<>?/\|}{~:]'
            password = self.cleaned_data['password']
            meets_criteria = False

            for character in password:
                if character.isdigit() or character in symbols:
                    meets_criteria = True
                    break

            if not meets_criteria or len(password) < 6:
                self.add_error('password', 'Password does not meet requirements')
        else:
            response = requests.get(f'https://poshmark.com/closet/{self.cleaned_data["username"]}')

            if response.status_code != requests.codes.ok:
                self.add_error('username', 'This PoshUser does not exists. '
                                           'Please sign up at poshmark.com or deselect the registered checkbox.')

    def save(self, commit=True):
        new_user = super(CreatePoshUser, self).save(commit=False)

        new_user.user = self.request.user

        if self.cleaned_data['alias'] and not self.cleaned_data['is_registered']:
            masked_email = self.cleaned_data['email']
            alias = new_user.generate_email(masked_email)
            new_user.email = alias.email_address
            new_user.is_email_verified = alias.is_verified
            new_user.alias_email_id = alias.id
            new_user.masked_email = alias.masked_email_address

            if alias.is_verified:
                new_user.status = PoshUser.ACTIVE
            else:
                new_user.status = PoshUser.WALIAS

        elif not self.cleaned_data['alias'] or not self.cleaned_data['is_registered']:
            new_user.email = self.cleaned_data['email']
            new_user.is_email_verified = True
            new_user.status = PoshUser.ACTIVE
        else:
            new_user.status = PoshUser.ACTIVE

        new_user.is_registered = self.cleaned_data['is_registered']

        new_user.save()


class CreateListing(forms.Form):
    categories_select = [
        ('Women', 'Women'),
        ('Men', 'Men'),
        ('Kids', 'Kids'),
        ('Home', 'Home'),
        ('Pets', 'Pets'),
    ]

    title = forms.CharField()
    description = forms.CharField()
    main_category = forms.CharField()
    secondary_category = forms.CharField()
    subcategory = forms.CharField(required=False)
    size = forms.CharField()
    tags = forms.BooleanField(widget=forms.HiddenInput(), required=False)
    brand = forms.CharField()
    original_price = forms.IntegerField()
    listing_price = forms.IntegerField()

    def __init__(self, request, *args, **kwargs):
        super(CreateListing, self).__init__(*args, **kwargs)
        self.request = request
        
    def save(self):
        new_listing = Listing(
            title=self.cleaned_data['title'],
            description=self.cleaned_data['description'],
            category=f"{self.cleaned_data['main_category']} {self.cleaned_data['secondary_category']}",
            subcategory=self.cleaned_data['subcategory'],
            size=self.cleaned_data['size'],
            brand=self.cleaned_data['brand'],
            tags=True if self.cleaned_data['tags'] == 'true' else False,
            original_price=int(self.cleaned_data['original_price']),
            listing_price=int(self.cleaned_data['listing_price']),
            user=self.request.user,
        )

        letters = string.ascii_lowercase

        new_listing.cover_photo.save(f"{new_listing.id}_{''.join(random.choice(letters)for i in range (5))}.png", ContentFile(self.files['cover_photo'].read()), save=True)

        for file_content in self.files.getlist('other_photos'):
            listing_photo = ListingPhotos(listing=new_listing)
            listing_photo.photo.save(f"{new_listing.id}_{''.join(random.choice(letters)for i in range (5))}.png", ContentFile(file_content.read()), save=True)


class CreateCampaign(forms.Form):
    title = forms.CharField()
    times = forms.CharField(widget=forms.HiddenInput())
    listings = forms.CharField(widget=forms.HiddenInput(), required=False)
    posh_user = forms.IntegerField(widget=forms.HiddenInput())
    mode = forms.CharField(initial='')
    delay = forms.FloatField()
    auto_run = forms.BooleanField(required=False)
    generate_users = forms.BooleanField(required=False)

    def __init__(self, request, *args, **kwargs):
        super(CreateCampaign, self).__init__(*args, **kwargs)
        self.request = request

    def clean(self):
        super(CreateCampaign, self).clean()

        posh_user_field = 'posh_user'
        if posh_user_field in self.cleaned_data.keys():
            posh_user_id = self.cleaned_data[posh_user_field]

            if posh_user_id:
                self.cleaned_data[posh_user_field] = PoshUser.objects.get(id=posh_user_id)
            else:
                self.add_error(posh_user_field, 'This posh user does not exist.')
        else:
            pass

        times_field = 'times'
        if times_field in self.cleaned_data.keys():
            times = self.cleaned_data[times_field].split(',')
            local_tz = pytz.timezone('US/Eastern')
            datetimes = []

            for time in times:
                local_time = datetime.datetime.strptime(time, '%I %p').replace(tzinfo=local_tz)
                utc_time = local_time.astimezone(datetime.timezone.utc).strftime('%I %p')
                datetimes.append(utc_time)

            self.cleaned_data[times_field] = ','.join(datetimes)
        else:
            pass

        if self.cleaned_data['mode'] != Campaign.BASIC_SHARING:
            listings_field = 'listings'
            if listings_field in self.cleaned_data.keys():
                listing_ids = self.cleaned_data[listings_field].split(',')
                listing_objects = []

                for listing_id in listing_ids:
                    listing_objects.append(Listing.objects.get(id=int(listing_id)))

                self.cleaned_data[listings_field] = listing_objects
            else:
                self.add_error(listings_field, 'This field is required.')

        title_field = 'title'
        try:
            campaign = Campaign.objects.get(title=self.cleaned_data[title_field], user=self.request.user)
            self.add_error(title_field, 'Campaign title taken, choose another title')
        except Campaign.DoesNotExist:
            pass

        self.cleaned_data['delay'] = round(self.cleaned_data['delay'] * 60, 2)

    def save(self):
        new_campaign = Campaign(
            user=self.request.user,
            posh_user=self.cleaned_data['posh_user'],
            title=self.cleaned_data['title'],
            status='2',
            times=self.cleaned_data['times'],
            delay=self.cleaned_data['delay'],
            auto_run=self.cleaned_data['auto_run'],
            generate_users=self.cleaned_data['generate_users'],
            mode=self.cleaned_data['mode'],
        )

        new_campaign.save()

        new_campaign.posh_user.status = PoshUser.INUSE
        new_campaign.posh_user.save(update_fields=['status'])

        for listing in self.cleaned_data['listings']:
            listing.campaign = new_campaign
            listing.save()


class CreateBasicCampaignForm(forms.Form):
    title = forms.CharField(label='Title')
    delay = forms.FloatField(label='Delay')
    username = forms.CharField(label='Username')
    password = forms.CharField(label='Password')

    def __init__(self, request, *args, **kwargs):
        super(CreateBasicCampaignForm, self).__init__(*args, **kwargs)
        self.request = request

    def clean(self):
        super(CreateBasicCampaignForm, self).clean()

        title_field = 'title'
        try:
            campaign = Campaign.objects.get(title=self.cleaned_data[title_field], user=self.request.user)
            self.add_error(title_field, 'Campaign title taken, choose another title')
        except Campaign.DoesNotExist:
            pass

        username_field = 'username'
        try:
            posh_user = PoshUser.objects.get(username=self.cleaned_data['username'])
            if posh_user.status != PoshUser.ACTIVE:
                self.add_error(username_field, 'This PoshUser is in the system and is not active.')
        except PoshUser.DoesNotExist:
            response = requests.get(f'https://poshmark.com/closet/{self.cleaned_data[username_field]}')
            if response.status_code != requests.codes.ok:
                self.add_error(username_field, 'This  PoshUser does not exists. '
                                               'Please sign up at poshmark.com or add it as a PoshUser.')

        self.cleaned_data['delay'] = round(self.cleaned_data['delay'] * 60, 2)

    def save(self):
        try:
            posh_user = PoshUser.objects.get(username=self.cleaned_data['username'])
        except PoshUser.DoesNotExist:
            posh_user = PoshUser(
                username=self.cleaned_data['username'],
                password=self.cleaned_data['password'],
                user=self.request.user,
                status=PoshUser.INUSE
            )
            posh_user.save()

        new_campaign = Campaign(
            user=self.request.user,
            posh_user=posh_user,
            title=self.cleaned_data['title'],
            status='2',
            times='12 AM,01 AM,02 AM,03 AM,04 AM,05 AM,06 AM,07 AM,08 AM,09 AM,10 AM,11 AM,12 PM,01 PM,02 PM,03 PM,'
                  '04 PM,05 PM,06 PM,07 PM,08 PM,09 PM,10 PM,11 PM',
            delay=self.cleaned_data['delay'],
            mode=Campaign.BASIC_SHARING,
            auto_run=True,
        )

        new_campaign.save()


class EditCampaignForm(CreateCampaign):
    def __init__(self, request, campaign, *args, **kwargs):
        super(EditCampaignForm, self).__init__(request, *args, **kwargs)
        self.request = request
        self.campaign = campaign

        listings = Listing.objects.filter(campaign=campaign)
        listings_list = [str(listing.id) for listing in listings]

        import logging
        logging.info(campaign)
        logging.info(listings)
        logging.info(listings_list)

        self.fields['title'].initial = campaign.title
        self.fields['times'].initial = campaign.times
        self.fields['listings'].initial = ','.join(listings_list)
        if campaign.posh_user:
            self.fields['posh_user'].initial = campaign.posh_user.id
        self.fields['mode'].initial = campaign.mode
        self.fields['delay'].initial = round(campaign.delay / 60, 2)
        self.fields['auto_run'].initial = campaign.auto_run
        self.fields['generate_users'].initial = campaign.generate_users

    def clean(self):
        super(CreateCampaign, self).clean()

        posh_user_field = 'posh_user'
        if posh_user_field in self.cleaned_data.keys():
            posh_user_id = self.cleaned_data[posh_user_field]

            if posh_user_id:
                self.cleaned_data[posh_user_field] = PoshUser.objects.get(id=posh_user_id)
            else:
                self.add_error(posh_user_field, 'This posh user does not exist.')
        else:
            pass

        times_field = 'times'
        if times_field in self.cleaned_data.keys():
            times = self.cleaned_data[times_field].split(',')
            local_tz = pytz.timezone('US/Eastern')
            datetimes = []

            for time in times:
                local_time = datetime.datetime.strptime(time, '%I %p').replace(tzinfo=local_tz)
                utc_time = local_time.astimezone(datetime.timezone.utc).strftime('%I %p')
                datetimes.append(utc_time)

            self.cleaned_data[times_field] = ','.join(datetimes)
        else:
            pass

        listings_field = 'listings'
        if self.cleaned_data['mode'] != Campaign.BASIC_SHARING and listings_field in self.changed_data:
            if listings_field in self.cleaned_data.keys():
                listing_ids = self.cleaned_data[listings_field].split(',')
                listing_objects = []

                for listing_id in listing_ids:
                    listing_objects.append(Listing.objects.get(id=int(listing_id)))

                self.cleaned_data[listings_field] = listing_objects
            else:
                self.add_error(listings_field, 'This field is required.')

        self.cleaned_data['delay'] = round(self.cleaned_data['delay'] * 60, 2)

    def save(self):
        self.campaign.posh_user = self.cleaned_data['posh_user']
        self.campaign.title = self.cleaned_data['title']
        self.campaign.times = self.cleaned_data['times']
        self.campaign.delay = self.cleaned_data['delay']
        self.campaign.auto_run = self.cleaned_data['auto_run']
        self.campaign.generate_users = self.cleaned_data['generate_users']
        self.campaign.mode = self.cleaned_data['mode']

        self.campaign.posh_user.status = PoshUser.INUSE
        self.campaign.posh_user.save()
        self.campaign.save()

        if self.cleaned_data['listings']:
            old_listings = Listing.objects.filter(campaign=self.campaign)
            for old_listing in old_listings:
                old_listing.campaign = None
                old_listing.save()

            for listing in self.cleaned_data['listings']:
                listing.campaign = self.campaign
                listing.save()
