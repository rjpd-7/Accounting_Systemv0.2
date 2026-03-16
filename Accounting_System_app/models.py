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

# Journal Headers Table Drafts
class JournalHeaderDrafts(models.Model):
    journal_date_created = models.DateTimeField(auto_now_add=True)
    entry_no = models.CharField(max_length=20, unique=True)
    entry_date = models.DateField(default=date.today)
    journal_description = models.TextField(blank=True, null=True)
    group_name = models.ForeignKey(AccountGroups, on_delete=models.RESTRICT, null=True, blank=True)

    # track which user created this journal header
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="journal_headers_drafts",
        null=True,   # allow null temporarily for existing rows/migration
        blank=True,
    )

    def __str__(self):
        return f"{self.entry_no} ({self.entry_date})"

    class Meta:
        db_table = "journal_headers_table_drafts"

# Journal Entries Table Drafts
class JournalEntryDrafts(models.Model):
    journal_header = models.ForeignKey(JournalHeaderDrafts, on_delete=models.CASCADE, related_name="entries", default=1)
    account = models.ForeignKey(ChartOfAccounts, on_delete=models.RESTRICT, default=1)
    debit = models.DecimalField(max_digits=15, decimal_places=5, default=0.00)
    credit = models.DecimalField(max_digits=15, decimal_places=5, default=0.00)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.account.account_name} ({self.debit} / {self.credit})"

    class Meta:
        db_table = "journal_entries_table_drafts"

# Journal Headers Table
class JournalHeader(models.Model):
    journal_date_created = models.DateTimeField(auto_now_add=True)
    entry_no = models.CharField(max_length=20, unique=True)
    entry_date = models.DateField(default=date.today)
    journal_description = models.TextField(blank=True, null=True)
    group_name = models.ForeignKey(AccountGroups, on_delete=models.RESTRICT, null=True, blank=True)

    # track which user created this journal header
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="journal_headers",
        null=True,   # allow null temporarily for existing rows/migration
        blank=True,
    )

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

# Journal Collaborators - tracks shared/collaborative journals between students
class JournalCollaborator(models.Model):
    journal_header = models.ForeignKey(JournalHeader, on_delete=models.CASCADE, related_name="collaborators")
    collaborator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="collaborated_journals")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "journal_collaborators"
        unique_together = ('journal_header', 'collaborator')

    def __str__(self):
        return f"{self.collaborator.username} collaborating on {self.journal_header.entry_no}"

# Journal Draft Collaborators - tracks shared/collaborative draft journals between students
class JournalDraftCollaborator(models.Model):
    journal_header = models.ForeignKey(JournalHeaderDrafts, on_delete=models.CASCADE, related_name="collaborators")
    collaborator = models.ForeignKey(User, on_delete=models.CASCADE, related_name="collaborated_journal_drafts")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "journal_draft_collaborators"
        unique_together = ('journal_header', 'collaborator')

    def __str__(self):
        return f"{self.collaborator.username} collaborating on draft {self.journal_header.entry_no}"


class StudentSection(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    account_groups = models.ManyToManyField(AccountGroups, related_name='sections', blank=True)
    teachers = models.ManyToManyField(User, related_name='managed_sections', blank=True)

    class Meta:
        db_table = "student_sections"
        ordering = ["name"]

    def __str__(self):
        return self.name

# User Profiles for Admins, Teachers, Students
class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('teacher', 'Teacher'),
        ('student', 'Student'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    section = models.ForeignKey(StudentSection, on_delete=models.SET_NULL, null=True, blank=True, related_name='students')
    account_groups = models.ManyToManyField(AccountGroups, related_name='assigned_users', blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"
    
    class Meta:
        db_table = "user_profiles"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

# Messages Table
class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    subject = models.CharField(max_length=255, blank=True, null=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        db_table = "messages_table"
        ordering = ['-created_at']

    def __str__(self):
        return f"Message from {self.sender.username} to {self.recipient.username}"

# Message Attachments Table
class MessageAttachment(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='message_attachments/%Y/%m/%d/')
    filename = models.CharField(max_length=255)
    file_size = models.IntegerField()  # in bytes
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "message_attachments_table"

    def __str__(self):
        return f"Attachment: {self.filename}"


class TaskAssignment(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_tasks')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_tasks')
    title = models.CharField(max_length=255)
    description = models.TextField()
    deadline = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_completed = models.BooleanField(default=False)

    class Meta:
        db_table = "task_assignments_table"
        ordering = ['-created_at']

    def __str__(self):
        return f"Task from {self.sender.username} to {self.recipient.username}: {self.title}"


class TaskAttachment(models.Model):
    task = models.ForeignKey(TaskAssignment, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='task_attachments/%Y/%m/%d/')
    filename = models.CharField(max_length=255)
    file_size = models.IntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "task_attachments_table"

    def __str__(self):
        return f"Task attachment: {self.filename}"

# Journal Audit Trail - tracks all changes made to journal entries
class JournalAuditTrail(models.Model):
    CHANGE_TYPE_CHOICES = [
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('deleted', 'Deleted'),
    ]
    
    journal_header = models.ForeignKey(JournalHeader, on_delete=models.CASCADE, related_name='audit_trails', null=True, blank=True)
    journal_header_draft = models.ForeignKey(JournalHeaderDrafts, on_delete=models.CASCADE, related_name='audit_trails', null=True, blank=True)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    change_type = models.CharField(max_length=20, choices=CHANGE_TYPE_CHOICES, default='updated')
    changed_at = models.DateTimeField(auto_now_add=True)
    
    # What changed
    field_name = models.CharField(max_length=100, null=True, blank=True)  # e.g., 'entry_date', 'journal_description', 'account', 'debit', 'credit'
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    
    # For entry-level changes
    entry_id = models.IntegerField(null=True, blank=True)  # JournalEntry or JournalEntryDrafts id

    class Meta:
        db_table = "journal_audit_trail"
        ordering = ['-changed_at']

    def __str__(self):
        return f"Change to journal {self.journal_header or self.journal_header_draft} on {self.changed_at}"
