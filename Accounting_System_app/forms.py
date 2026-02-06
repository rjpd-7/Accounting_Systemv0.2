from django import forms
from .models import USN_Accounts, ChartOfAccounts, Message, MessageAttachment
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
    confirm_password = forms.CharField(widget=forms.PasswordInput)
    role = forms.ChoiceField(choices=[
        ('admin', 'Admin'),
        ('teacher', 'Teacher'),
        ('student', 'Student'),
    ])

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'password', 'confirm_password', 'role']

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match.")

        return cleaned_data

# Message Form
class MessageForm(forms.ModelForm):
    recipient = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Send to"
    )
    
    class Meta:
        model = Message
        fields = ['recipient', 'subject', 'content']
        widgets = {
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Subject (optional)'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Type your message...'}),
        }

# Message Attachment Form
class MessageAttachmentForm(forms.ModelForm):
    class Meta:
        model = MessageAttachment
        fields = ['file']
        widgets = {
            'file': forms.FileInput(attrs={'class': 'form-control', 'accept': '*/*'})
        }