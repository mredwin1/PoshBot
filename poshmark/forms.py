import datetime
import pytz
import random
import requests
import string

from django import forms
from django.core.files.base import ContentFile
from poshmark.models import PoshUser, Listing, ListingPhotos, Campaign


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
    lowest_price = forms.IntegerField()

    def __init__(self, request, *args, **kwargs):
        super(CreateListing, self).__init__(*args, **kwargs)
        self.request = request

    def clean(self):
        super(CreateListing, self).clean()

        self.cleaned_data['category'] = f"{self.cleaned_data['main_category']} {self.cleaned_data['secondary_category']}"
        self.cleaned_data['tags'] = True if self.cleaned_data['tags'] == 'true' else False

    def save(self):
        new_listing = Listing(
            title=self.cleaned_data['title'],
            description=self.cleaned_data['description'],
            category=self.cleaned_data['category'],
            subcategory=self.cleaned_data['subcategory'],
            size=self.cleaned_data['size'],
            brand=self.cleaned_data['brand'],
            tags=self.cleaned_data['tags'],
            original_price=self.cleaned_data['original_price'],
            listing_price=self.cleaned_data['listing_price'],
            lowest_price=self.cleaned_data['lowest_price'],
            user=self.request.user,
        )

        letters = string.ascii_lowercase

        new_listing.cover_photo.save(f"{new_listing.id}_{''.join(random.choice(letters)for i in range (5))}.png", ContentFile(self.files['cover_photo'].read()), save=True)

        for file_content in self.files.getlist('other_photos'):
            listing_photo = ListingPhotos(listing=new_listing)
            listing_photo.photo.save(f"{new_listing.id}_{''.join(random.choice(letters)for i in range (5))}.png", ContentFile(file_content.read()), save=True)


class EditListingForm(CreateListing):
    def __init__(self, request, listing, *args, **kwargs):
        super(EditListingForm, self).__init__(request, *args, **kwargs)
        self.request = request
        self.listing = listing

        index = listing.category.find(' ')
        main_category = listing.category[:index]
        secondary_category = listing.category[index + 1:]

        self.fields['title'].initial = listing.title
        self.fields['size'].initial = listing.size
        self.fields['brand'].initial = listing.brand
        self.fields['main_category'].initial = main_category
        self.fields['secondary_category'].initial = secondary_category
        self.fields['subcategory'].initial = listing.subcategory
        self.fields['description'].initial = listing.description
        self.fields['tags'].initial = listing.tags
        self.fields['original_price'].initial = listing.original_price
        self.fields['listing_price'].initial = listing.listing_price
        self.fields['lowest_price'].initial = listing.lowest_price

    def save(self):
        self.listing.title = self.cleaned_data['title']
        self.listing.size = self.cleaned_data['size']
        self.listing.brand = self.cleaned_data['brand']
        self.listing.category = self.cleaned_data['category']
        self.listing.subcategory = self.cleaned_data['subcategory']
        self.listing.description = self.cleaned_data['description']
        self.listing.tags = self.cleaned_data['tags']
        self.listing.original_price = self.cleaned_data['original_price']
        self.listing.listing_price = self.cleaned_data['listing_price']
        self.listing.lowest_price = self.cleaned_data['lowest_price']

        self.listing.save()

        if 'cover_photo' in self.files.keys():
            self.listing.cover_photo.delete()
            letters = string.ascii_lowercase

            self.listing.cover_photo.save(f"{self.listing.id}_{''.join(random.choice(letters)for i in range (5))}.png", ContentFile(self.files['cover_photo'].read()), save=True)

        if self.files.getlist('other_photos'):
            listing_photos = ListingPhotos.objects.filter(listing=self.listing)
            for listing_photo in listing_photos:
                listing_photo.delete()

            for file_content in self.files.getlist('other_photos'):
                listing_photo = ListingPhotos(listing=self.listing)
                listing_photo.photo.save(f"{self.listing.id}_{''.join(random.choice(letters)for i in range (5))}.png", ContentFile(file_content.read()), save=True)


class CreateCampaign(forms.Form):
    title = forms.CharField()
    times = forms.CharField()
    listings = forms.CharField(required=False)
    posh_user = forms.IntegerField(required=False)
    posh_username = forms.CharField(required=False)
    posh_password = forms.CharField(required=False)
    mode = forms.CharField(initial='')
    delay = forms.FloatField()
    auto_run = forms.BooleanField(required=False)
    generate_users = forms.BooleanField(required=False)
    lowest_price = forms.IntegerField(required=False)

    def __init__(self, request, *args, **kwargs):
        super(CreateCampaign, self).__init__(*args, **kwargs)
        self.request = request

    def clean(self):
        super(CreateCampaign, self).clean()

        posh_user_field = 'posh_user'
        posh_username_field = 'posh_username'
        posh_password_field = 'posh_password'
        if self.cleaned_data[posh_user_field] and not (self.cleaned_data['posh_username'] and self.cleaned_data['posh_password']):
            posh_user_id = self.cleaned_data[posh_user_field]

            if posh_user_id:
                self.cleaned_data[posh_user_field] = PoshUser.objects.get(id=posh_user_id)
            else:
                self.add_error(posh_user_field, 'This posh user does not exist.')

        if posh_username_field and posh_password_field in self.cleaned_data.keys() and not self.cleaned_data[posh_user_field]:
            try:
                posh_user = PoshUser.objects.get(username=self.cleaned_data['posh_username'])
                if posh_user.status == PoshUser.INACTIVE:
                    self.add_error(posh_username_field, 'This PoshUser is in the system and is not active.')
                else:
                    self.add_error(posh_username_field, 'This PoshUser is in the system.')
            except PoshUser.DoesNotExist:
                response = requests.get(f'https://poshmark.com/closet/{self.cleaned_data[posh_username_field]}')
                if response.status_code != requests.codes.ok:
                    self.add_error(posh_username_field, 'This PoshUser does not exist. '
                                                  'Please sign up at poshmark.com or add it as a PoshUser.')
        times_field = 'times'
        if self.cleaned_data[times_field]:
            times = self.cleaned_data[times_field].split(',')
            local_tz = pytz.timezone('US/Eastern')
            datetimes = []

            for time in times:
                local_time = datetime.datetime.strptime(time, '%I %p').replace(tzinfo=local_tz)
                utc_time = local_time.astimezone(datetime.timezone.utc).strftime('%I %p')
                datetimes.append(utc_time)

            self.cleaned_data[times_field] = ','.join(datetimes)

        if self.cleaned_data['mode'] == Campaign.ADVANCED_SHARING:
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

        if 'delay' in self.cleaned_data.keys():
            self.cleaned_data['delay'] = round(self.cleaned_data['delay'] * 60, 2)

        if self.cleaned_data['lowest_price'] is None:
            self.cleaned_data['lowest_price'] = 0

    def save(self):
        if self.cleaned_data['posh_user']:
            posh_user = self.cleaned_data['posh_user']
        else:
            posh_user = PoshUser(
                username=self.cleaned_data['posh_username'],
                password=self.cleaned_data['posh_password'],
                user=self.request.user,
                is_registered=True,
                status=PoshUser.IDLE
            )
            posh_user.save()

        new_campaign = Campaign(
            user=self.request.user,
            posh_user=posh_user,
            title=self.cleaned_data['title'],
            status='2',
            times=self.cleaned_data['times'],
            delay=self.cleaned_data['delay'],
            auto_run=self.cleaned_data['auto_run'],
            generate_users=self.cleaned_data['generate_users'],
            mode=self.cleaned_data['mode'],
            lowest_price=self.cleaned_data['lowest_price'],
        )

        new_campaign.save()

        if self.cleaned_data['mode'] == Campaign.ADVANCED_SHARING:
            for listing in self.cleaned_data['listings']:
                listing.campaign = new_campaign
                listing.save()


class CreateBasicCampaignForm(forms.Form):
    title = forms.CharField(label='Title')
    delay = forms.FloatField(label='Delay')
    lowest_price = forms.IntegerField(label='Lowest Price')
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
            if posh_user.status == PoshUser.INACTIVE:
                self.add_error(username_field, 'This PoshUser is in the system and is not active.')
            else:
                self.add_error(username_field, 'This PoshUser is in the system.')
        except PoshUser.DoesNotExist:
            response = requests.get(f'https://poshmark.com/closet/{self.cleaned_data[username_field]}')
            if response.status_code != requests.codes.ok:
                self.add_error(username_field, 'This PoshUser does not exist. '
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
                status=PoshUser.IDLE,
                is_registered=True
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
            lowest_price=self.cleaned_data['lowest_price']
        )

        new_campaign.save()


class EditCampaignForm(CreateCampaign):
    def __init__(self, request, campaign, *args, **kwargs):
        super(EditCampaignForm, self).__init__(request,  *args, **kwargs)
        self.request = request
        self.campaign = campaign

        listings = Listing.objects.filter(campaign=campaign)
        listings_list = [str(listing.id) for listing in listings]

        times = campaign.times.split(',')
        local_tz = pytz.timezone('US/Eastern')
        datetimes = []

        for time in times:
            local_time = datetime.datetime.strptime(time, '%I %p').replace(tzinfo=local_tz)
            utc_time = local_time.astimezone(datetime.timezone.utc).strftime('%I %p')
            datetimes.append(utc_time)

        self.fields['title'].initial = campaign.title
        self.fields['times'].initial = ','.join(datetimes)
        self.fields['listings'].initial = ','.join(listings_list)
        if campaign.posh_user:
            self.fields['posh_user'].initial = campaign.posh_user.id
        self.fields['mode'].initial = campaign.mode
        self.fields['delay'].initial = round(campaign.delay / 60, 2)
        self.fields['auto_run'].initial = campaign.auto_run
        self.fields['generate_users'].initial = campaign.generate_users
        self.fields['lowest_price'].initial = campaign.lowest_price

    def clean(self):
        posh_user_field = 'posh_user'
        posh_username_field = 'posh_username'
        posh_password_field = 'posh_password'
        if self.cleaned_data[posh_user_field] and not (self.cleaned_data['posh_username'] and self.cleaned_data['posh_password']):
            posh_user_id = self.cleaned_data[posh_user_field]

            if posh_user_id:
                self.cleaned_data[posh_user_field] = PoshUser.objects.get(id=posh_user_id)
            else:
                self.add_error(posh_user_field, 'This posh user does not exist.')

        if posh_username_field and posh_password_field in self.cleaned_data.keys() and not self.cleaned_data[posh_user_field]:
            try:
                posh_user = PoshUser.objects.get(username=self.cleaned_data['posh_username'])
                if posh_user.status == PoshUser.INACTIVE:
                    self.add_error(posh_username_field, 'This PoshUser is in the system and is not active.')
                else:
                    self.add_error(posh_username_field, 'This PoshUser is in the system.')
            except PoshUser.DoesNotExist:
                response = requests.get(f'https://poshmark.com/closet/{self.cleaned_data[posh_username_field]}')
                if response.status_code != requests.codes.ok:
                    self.add_error(posh_username_field, 'This PoshUser does not exist. '
                                                        'Please sign up at poshmark.com or add it as a PoshUser.')

        times_field = 'times'
        if times_field in self.cleaned_data[times_field]:
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
        if self.cleaned_data['mode'] != Campaign.BASIC_SHARING:
            if listings_field in self.cleaned_data.keys():
                listing_ids = self.cleaned_data[listings_field].split(',')
                listing_objects = []

                for listing_id in listing_ids:
                    if listing_id:
                        listing_objects.append(Listing.objects.get(id=int(listing_id)))

                self.cleaned_data[listings_field] = listing_objects
            else:
                self.add_error(listings_field, 'This field is required.')

        self.cleaned_data['delay'] = round(self.cleaned_data['delay'] * 60, 2)

        if self.cleaned_data['lowest_price'] is None:
            self.cleaned_data['lowest_price'] = 0

    def save(self):
        if self.cleaned_data['posh_user']:
            posh_user = self.cleaned_data['posh_user']
        else:
            posh_user = PoshUser(
                username=self.cleaned_data['posh_username'],
                password=self.cleaned_data['posh_password'],
                user=self.request.user,
                is_registered=True
            )
            posh_user.save()

        if self.campaign.posh_user:
            self.campaign.posh_user.status = PoshUser.IDLE
            self.campaign.posh_user.save()

        self.campaign.posh_user = posh_user
        self.campaign.title = self.cleaned_data['title']
        self.campaign.times = self.cleaned_data['times']
        self.campaign.delay = self.cleaned_data['delay']
        self.campaign.auto_run = self.cleaned_data['auto_run']
        self.campaign.generate_users = self.cleaned_data['generate_users']
        self.campaign.mode = self.cleaned_data['mode']
        self.campaign.lowest_price = self.cleaned_data['lowest_price']

        self.campaign.save()

        old_listings = Listing.objects.filter(campaign=self.campaign)
        for old_listing in old_listings:
            old_listing.campaign = None
            old_listing.save()

        if self.cleaned_data['listings']:
            for listing in self.cleaned_data['listings']:
                listing.campaign = self.campaign
                listing.save()
