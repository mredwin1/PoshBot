from django import forms
from poshmark.models import PoshUser


class CreatePoshUser(forms.ModelForm):
    alias_choices = [('1', 'Alias'), ('0', 'No Alias')]
    alias = forms.CharField(max_length=10, label=None, widget=forms.RadioSelect(choices=alias_choices))

    class Meta:
        model = PoshUser
        fields = ['profile_picture', 'first_name', 'last_name', 'email', 'username', 'password', 'gender']
