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

    date_created = models.DateTimeField(auto_now_add=True)
    account_code = models.CharField(unique=True, max_length=20, null=False)
    account_name = models.CharField(max_length=255, null=False)
    account_type = models.CharField(max_length=255, null=False, choices=account_type_choices)
    account_description = models.TextField(max_length=None, null=True)

    #def __str__(self):
    #    return self.account_name, self.account_type

    class Meta:
        db_table = "accounts_table"

# Journal Headers Table
class JournalHeader(models.Model):
    journal_date_created = models.DateTimeField(auto_now_add=True)
    entry_no = models.CharField(max_length=20, unique=True)
    entry_date = models.DateField(default=date.today)

    class Meta:
        db_table = "journal_headers_table"

# Journal Entries Table
class JournalEntry(models.Model):
    journal_header = models.ForeignKey(JournalHeader, on_delete=models.CASCADE, related_name="entries", default=1)
    account = models.ForeignKey(ChartOfAccounts, on_delete=models.RESTRICT, default=1)
    debit = models.DecimalField(max_digits=15, decimal_places=5, default=0.00)
    credit = models.DecimalField(max_digits=15, decimal_places=5, default=0.00)
    description = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "journal_entries_table"