from django.db import models
from datetime import datetime, date

# Create your models here.

# USN Accounts Model
class USN_Accounts(models.Model):
    usn = models.TextField(max_length=None, null=True)
    password = models.TextField(max_length=None, null=True)

    class Meta:
        db_table = "usn_accounts"

# Account Groups Table
class AccountGroups(models.Model):
    type_choices = [
        ("Debit", "Debit"),
        ("Credit", "Credit"),
    ]
    
    date_created = models.DateTimeField(default=datetime.today)
    group_name = models.TextField(max_length=None, null=False)
    group_description = models.TextField(max_length=None)
    group_type = models.TextField(max_length=None, choices=type_choices, null=False)

    class Meta:
        db_table = "account_groups"

# Accounts Table
class Accounts(models.Model):
    date_created = models.DateTimeField(default=datetime.today)
    account_name = models.TextField(max_length=None, null=False)
    account_descriptions = models.TextField(max_length=None)

# Chart Of Accounts Table
