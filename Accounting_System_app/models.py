from django.db import models
from datetime import datetime, date
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# Create your models here.

# USN Accounts Model
class USN_Accounts(models.Model):
    usn = models.TextField(max_length=None, null=True)
    password = models.TextField(max_length=None, null=True)

    class Meta:
        db_table = "usn_accounts"

# Account Groups Table
class AccountGroups(models.Model):
    
    date_created = models.DateTimeField(auto_now_add=True)
    group_name = models.TextField(max_length=None, null=False)
    group_description = models.TextField(max_length=None)

    class Meta:
        db_table = "account_groups"

# Accounts Table
class Accounts(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    account_name = models.TextField(max_length=None, null=False)
    account_descriptions = models.TextField(max_length=None)

#Accounts Group Table

class AccountGroupsTable(models.Model):
    date_created = models.DateTimeField(auto_now_add=True)
    group_name = models.TextField(max_length=None, null=False)
    group_description = models.TextField(max_length=None)

    class Meta:
        db_table = "account_groups_table"

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
    group_name = models.ForeignKey(AccountGroups, on_delete=models.RESTRICT, null=True, blank=True)

    def __str__(self):
        return self.account_name, self.account_type

    class Meta:
        db_table = "accounts_table"

# Journal Headers Table
class JournalHeader(models.Model):
    journal_date_created = models.DateTimeField(auto_now_add=True)
    entry_no = models.CharField(max_length=20, unique=True)
    entry_date = models.DateField(default=date.today)
    journal_description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.entry_no} ({self.entry_date})"

    class Meta:
        db_table = "journal_headers_table"

# Journal Entries Table
class JournalEntry(models.Model):
    journal_header = models.ForeignKey(JournalHeader, on_delete=models.CASCADE, related_name="entries", default=1)
    account = models.ForeignKey(ChartOfAccounts, on_delete=models.RESTRICT, default=1)
    debit = models.DecimalField(max_digits=15, decimal_places=5, default=0.00)
    credit = models.DecimalField(max_digits=15, decimal_places=5, default=0.00)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.account.account_name} ({self.debit} / {self.credit})"

    class Meta:
        db_table = "journal_entries_table"

# User Profiles for Admins, Teachers, Students
class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('teacher', 'Teacher'),
        ('student', 'Student'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')

    def __str__(self):
        return f"{self.user.username} ({self.role})"
    
    class Meta:
        db_table = "user_profiles"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
