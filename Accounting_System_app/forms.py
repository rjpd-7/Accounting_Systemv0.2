from django import forms
from .models import USN_Accounts, ChartOfAccounts
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

# Form for USN Accounts
class USNAccountsForm(forms.ModelForm):
    class Meta:
        model = USN_Accounts
        fields = ['usn', 'password']

# Charts of Accounts Form
class ChartOfAccountsForm(forms.ModelForm):
    class Meta:
        model = ChartOfAccounts
        fields = ['account_code', 'account_name', 'account_type']

class UpdateAccountsForm(forms.ModelForm):
    class Meta:
        model = ChartOfAccounts
        fields = ['account_name']

# User Creation Form
class UserCreationForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    role = forms.ChoiceField(choices=[
        ('admin', 'Admin'),
        ('teacher', 'Teacher'),
        ('student', 'Student'),
    ])

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'password', 'role']