from django import forms
from poshmark.models import PoshUser


class CreatePoshUser(forms.ModelForm):
    alias_choices = [('1', 'Alias'), ('0', 'No Alias')]
    alias = forms.CharField(max_length=10, label=None, widget=forms.RadioSelect(choices=alias_choices))

    class Meta:
        model = PoshUser
        fields = ['profile_picture', 'first_name', 'last_name', 'email', 'username', 'password', 'gender']

    def clean(self):
        if self.cleaned_data['alias'] == '1':
            tmp_user = PoshUser()
            can_create_alias = tmp_user.check_alias_email()

            if not can_create_alias:
                self.add_error('email', 'The limit of email aliases have been met, cannot create more.')

    def save(self, commit=True):
        new_user = super(CreatePoshUser, self).save(commit=False)

        if self.cleaned_data['alias'] == '1':
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

        else:
            new_user.email = self.cleaned_data['email']
            new_user.is_email_verified = True

        new_user.save()
