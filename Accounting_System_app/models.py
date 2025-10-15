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
    
    date_created = models.DateTimeField(auto_now_add=True)
    group_name = models.TextField(max_length=None, null=False)
    group_description = models.TextField(max_length=None)
    group_type = models.TextField(max_length=None, choices=type_choices, null=False)

    class Meta:
        db_table = "account_groups"

# Accounts Table
class Accounts(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    account_name = models.TextField(max_length=None, null=False)
    account_descriptions = models.TextField(max_length=None)

# Chart Of Accounts Table
class ChartOfAccounts(models.Model):
    account_type_choices = [
        ("Assets", "Assets"),
        ("Liabilities", "Liabilities"),
        ("Equity", "Equity"),
        ("Revenue", "Revenue"),
        ("Expenses", "Expenses"),
    ]
    
    debit_credit_choices = [
        ("Debit", "Debit"),
        ("Credit", "Credit"),
    ]

    date_created = models.DateTimeField(auto_now_add=True)
    account_code = models.CharField(unique=True, max_length=20, null=False)
    account_name = models.TextField(max_length=None, null=False)
    account_type = models.TextField(max_length=None, null=False, choices=account_type_choices)
    debit_credit = models.TextField(max_length=None, null=True, choices=debit_credit_choices)

    class Meta:
        db_table = "accounts_table"

# Journal Entries Table
class JournalEntry(models.Model):
    pass