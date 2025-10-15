from django import forms
from .models import USN_Accounts, ChartOfAccounts

# Form for USN Accounts
class USNAccountsForm(forms.ModelForm):
    class Meta:
        model = USN_Accounts
        fields = ['usn', 'password']

# Charts of Accounts Form
class ChartOfAccountsForm(forms.ModelForm):
    class Meta:
        model = ChartOfAccounts
        fields = ['account_code', 'account_name', 'account_type', 'debit_credit']

class UpdateAccountsForm(forms.ModelForm):
    class Meta:
        model = ChartOfAccounts
        fields = ['account_name']