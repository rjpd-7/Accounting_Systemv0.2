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
        fields = ['date_created', 'account_code', 'account_name', 'account_type', 'debit_credit']