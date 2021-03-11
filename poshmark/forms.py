import datetime
import pytz
import random
import requests
import string

from django import forms
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
                new_user.status = '4'
            else:
                new_user.status = '3'

        elif not self.cleaned_data['alias'] or not self.cleaned_data['is_registered']:
            new_user.email = self.cleaned_data['email']
            new_user.is_email_verified = True

        if self.cleaned_data['is_registered']:
            new_user.is_registered = True
            new_user.status = '1'
        else:
            new_user.status = '4'

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

        new_listing.save()

        letters = string.ascii_lowercase

        for file_content in self.files.values():
            listing_photo = ListingPhotos(listing=new_listing)
            listing_photo.photo.save(f"{new_listing.id}_{''.join(random.choice(letters)for i in range (5))}.png", file_content, save=True)


class CreateCampaign(forms.Form):
    title = forms.CharField()
    times = forms.CharField(widget=forms.HiddenInput())
    listings = forms.CharField(widget=forms.HiddenInput())
    posh_user = forms.CharField()
    delay = forms.IntegerField()
    auto_run = forms.BooleanField(required=False)
    generate_users = forms.BooleanField(required=False)

    def __init__(self, request, *args, **kwargs):
        super(CreateCampaign, self).__init__(*args, **kwargs)
        self.request = request

    def clean(self):
        super(CreateCampaign, self).clean()

        posh_user_field = 'posh_user'
        posh_user = self.cleaned_data[posh_user_field]
        separator_index = posh_user.find(' | ')
        posh_user_id = posh_user[separator_index + 3:] if separator_index != -1 else ''

        if posh_user_id:
            self.cleaned_data[posh_user_field] = PoshUser.objects.get(id=posh_user_id)
        else:
            self.add_error(posh_user_field, 'This posh user does not exist.')

        times_field = 'times'
        times = self.cleaned_data[times_field].split(',')
        local_tz = pytz.timezone('US/Eastern')
        datetimes = []

        for time in times:
            local_time = datetime.datetime.strptime(time, '%I %p').replace(tzinfo=local_tz)
            utc_time = (local_time.astimezone(datetime.timezone.utc) + datetime.timedelta(hours=1)).strftime('%I %p')
            datetimes.append(utc_time)

        self.cleaned_data[times_field] = ','.join(datetimes)

        listings_field = 'listings'
        listing_ids = self.cleaned_data[listings_field].split(',')
        listing_objects = []

        for id in listing_ids:
            listing_objects.append(Listing.objects.get(id=int(id)))

        self.cleaned_data[listings_field] = listing_objects

        self.cleaned_data['delay'] = self.cleaned_data['delay'] * 60

    def save(self):
        new_campaign = Campaign(
            user=self.request.user,
            posh_user=self.cleaned_data['posh_user'],
            title=self.cleaned_data['title'],
            status='2',
            times=self.cleaned_data['times'],
            delay=self.cleaned_data['delay'],
            auto_run=self.cleaned_data['auto_run'],
            generate_users=self.cleaned_data['generate_users']
        )

        new_campaign.save()

        for listing in self.cleaned_data['listings']:
            new_campaign.listings.add(listing)
