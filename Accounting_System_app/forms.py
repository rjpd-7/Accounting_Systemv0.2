from django import forms
from .models import USN_Accounts


class USNAccountsForm(forms.ModelForm):
    class Meta:
        model = USN_Accounts
        fields = ['usn', 'password']