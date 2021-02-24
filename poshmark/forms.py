import requests

from django import forms
from poshmark.models import PoshUser


class CreatePoshUser(forms.ModelForm):
    alias = forms.BooleanField(required=False, label='Create Alias')

    is_registered = forms.BooleanField(required=False, label='User is Registered')

    class Meta:
        model = PoshUser
        fields = ['profile_picture', 'header_picture', 'first_name', 'last_name', 'email', 'username', 'password',
                  'gender']

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

            new_user.status = '4'

        if self.cleaned_data['is_registered']:
            new_user.is_registered = True

        new_user.save()
