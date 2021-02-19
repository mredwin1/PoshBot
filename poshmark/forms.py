from django import forms
from poshmark.models import PoshUser


class CreatePoshUser(forms.ModelForm):
    class Meta:
        model = PoshUser
        fields = ['profile_picture', 'first_name', 'last_name', 'email', 'username', 'password', 'gender']
