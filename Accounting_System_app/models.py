from django.db import models
from datetime import datetime, date

# Create your models here.

# USN Accounts Table
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

class Accounts(models.Model):
    date_created = models.DateTimeField(default=datetime.today)
    account_name = models.TextField(max_length=None, null=False)
    account_descriptions = models.TextField(max_length=None)

    # DB Table is accounting_system_app_accounts

class ChartOfAccounts(models.Model):
    account_type_choices = [
        ("Assets", "Assets")
        ("Liabilities", "Liabilities")
        ("Equity", "Equity")
        ("Revenue", "Revenue")
        ("Expenses", "Expenses")
    ]
    
    date_created = models.DateTimeField(default=datetime.today)
    account_code = models.IntegerField(unique=True, max_length=6)
    account_name = models.TextField(max_length=None, null=False)
    account_type = models.TextField(max_length=None, null=False, choices=account_type_choices)

    class Meta:
        db_table = "accounts_table"

class JournalEntries(models.Model):
    pass