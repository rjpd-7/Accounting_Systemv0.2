from django.http import HttpResponseRedirect, JsonResponse, Http404, FileResponse
from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import localtime, localdate
from .models import USN_Accounts, AccountGroups, Accounts, ChartOfAccounts, JournalHeaderDrafts, JournalEntryDrafts, JournalHeader, JournalEntry, Message, MessageAttachment, TaskAssignment, TaskAttachment, TaskSubmission, TaskSubmissionAttachment, JournalCollaborator, JournalDraftCollaborator, StudentSection, UserProfile, JournalAuditTrail
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from .forms import USNAccountsForm, ChartOfAccountsForm, UpdateAccountsForm, UserCreationForm, MessageForm, MessageAttachmentForm, TaskAssignmentForm, TaskAttachmentForm
from itertools import zip_longest
from django.db.models import Sum, RestrictedError, Q, Value, DecimalField, Max, Count
from django.db.models.functions import Coalesce
from django.db import transaction, IntegrityError
from django.contrib import messages
from django.core.serializers.json import DjangoJSONEncoder
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
from django.core.cache import cache
import json
import re
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from .decorators import role_required
import io
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
import os
from django.core.mail import send_mail
from django.conf import settings
from django.core.files.base import ContentFile
import random, string
from uuid import uuid4
import mimetypes


def _build_attachment_response(file_field, filename):
    """Return a file response that previews PDFs inline and downloads other files."""
    resolved_name = filename or os.path.basename(getattr(file_field, 'name', '') or '')
    content_type, _ = mimetypes.guess_type(resolved_name)
    is_pdf = (content_type == 'application/pdf') or resolved_name.lower().endswith('.pdf')

    return FileResponse(
        file_field,
        as_attachment=not is_pdf,
        filename=resolved_name,
        content_type=content_type or 'application/octet-stream',
    )


def get_system_base_url(request=None):
    """
    Resolve a usable absolute base URL for links included in email notifications.
    """
    if request is not None and hasattr(request, 'build_absolute_uri'):
        return request.build_absolute_uri('/').rstrip('/')

    configured_url = getattr(settings, 'SYSTEM_BASE_URL', '').strip()
    if configured_url:
        return configured_url.rstrip('/')

    allowed_hosts = getattr(settings, 'ALLOWED_HOSTS', [])
    for host in allowed_hosts:
        if host and host not in ['*', 'localhost', '127.0.0.1']:
            return f"https://{host}"

    return 'http://127.0.0.1:8000'


def clear_temporary_password_state(user):
    profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'role': 'student'})
    profile.temporary_password_expires_at = None
    profile.requires_password_change = False
    profile.save(update_fields=['temporary_password_expires_at', 'requires_password_change'])
    return profile


def mark_temporary_password(user):
    profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'role': 'student'})
    expiry_minutes = max(1, int(getattr(settings, 'TEMP_PASSWORD_EXPIRY_MINUTES', 5)))
    profile.temporary_password_expires_at = timezone.now() + timedelta(minutes=expiry_minutes)
    profile.requires_password_change = True
    profile.save(update_fields=['temporary_password_expires_at', 'requires_password_change'])
    return profile


def is_temporary_password_expired(profile):
    if not profile.requires_password_change or not profile.temporary_password_expires_at:
        return False
    return timezone.now() >= profile.temporary_password_expires_at


def get_user_role(user):
    if user.is_superuser:
        return 'admin'
    profile = getattr(user, 'profile', None)
    return profile.role if profile else 'student'


def get_post_login_redirect_name(user):
    role = get_user_role(user)
    if role == 'admin':
        return 'AccountingSystem:admin_dashboard'
    if role == 'teacher':
        return 'AccountingSystem:teacher_dashboard'
    return 'AccountingSystem:student_dashboard'


def get_post_login_redirect_url(user):
    return reverse(get_post_login_redirect_name(user))


# Helper function to send credentials email to new user
def send_credentials_email(user, password):
    """
    Send account credentials to the newly created user's email.
    """
    if not user.email:
        return False, 'No email address provided for this user.'
    
    subject = 'Your ACLC Accounting System Account Credentials'
    login_url = f"{get_system_base_url()}{reverse('AccountingSystem:login_view')}"
    message = f"""
Hello {user.first_name or user.username},

Your account has been created in the ACLC Accounting System.

Account Details:
- Username: {user.username}
- Password: {password}
- Email: {user.email}

Login URL: {login_url}

For security, please change your password after your first login.

Best regards,
ACLC Accounting System
    """
    
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        return True, ''
    except Exception as e:
        print(f"Error sending email to {user.email}: {str(e)}")
        return False, str(e)

# Helper function to generate next account code (thread-safe)
def get_next_account_code(account_type):
    """
    Generate next account code based on type with database-level locking
    to prevent duplicate codes in concurrent scenarios.
    """
    type_prefixes = {
        "Assets": 100000,
        "Liabilities": 200000,
        "Equity": 300000,
        "Revenue": 400000,
        "Expenses": 500000,
    }
    
    prefix = type_prefixes.get(account_type, 100000)
    
    # Use transaction and select_for_update() to ensure atomicity.
    # This prevents race conditions when multiple users request codes simultaneously.
    with transaction.atomic():
        # Lock all accounts of this type and derive the next sequence from existing code digits.
        accounts = ChartOfAccounts.objects.filter(
            account_type=account_type
        ).select_for_update().values_list('account_code', flat=True)
        
        max_number = 0
        for code in accounts:
            try:
                match = re.search(r'(\d+)$', str(code))
                if not match:
                    continue
                num = int(match.group(1)) - prefix
                if num > max_number:
                    max_number = num
            except (ValueError, TypeError):
                pass
        
        next_code = str(prefix + max_number + 1)
    
    return next_code

def get_account_groups_for_section(section):
    """
    Get all account groups available to a section.
    Account groups come from all teachers/admins managing that section.
    """
    if not section:
        return AccountGroups.objects.none()
    
    # Get all teachers managing this section
    teachers = section.teachers.all()
    
    if not teachers.exists():
        # No teachers assigned to this section
        return AccountGroups.objects.none()
    
    # Collect all account groups from all teachers managing this section
    account_group_ids = set()
    for teacher in teachers:
        if hasattr(teacher, 'profile'):
            teacher_groups = teacher.profile.account_groups.values_list('id', flat=True)
            account_group_ids.update(teacher_groups)
    
    # Return distinct account groups
    return AccountGroups.objects.filter(id__in=account_group_ids)

# Helper function to generate next journal code (thread-safe with atomic locking)
def get_next_journal_code():
    """Generate next journal code in format JE-XXXXXXXXXX"""
    from django.db import transaction
    
    with transaction.atomic():
        # Lock journal rows and derive the sequence from the numeric suffix of entry_no.
        draft_codes = JournalHeaderDrafts.objects.select_for_update().values_list('entry_no', flat=True)
        approved_codes = JournalHeader.objects.select_for_update().values_list('entry_no', flat=True)

        max_number = 0
        for code in list(draft_codes) + list(approved_codes):
            match = re.search(r'(\d+)$', str(code))
            if match:
                max_number = max(max_number, int(match.group(1)))

        next_number = str(max_number + 1).zfill(10)
        return f'JE-{next_number}'

# API endpoint to get next account code
@require_http_methods(["GET"])
def get_next_account_code_api(request):
    """API endpoint to get next account code for a given type"""
    account_type = request.GET.get('type', 'Assets')
    if account_type not in ["Assets", "Liabilities", "Equity", "Revenue", "Expenses"]:
        return JsonResponse({'success': False, 'error': 'Invalid account type'}, status=400)
    
    next_code = get_next_account_code(account_type)
    return JsonResponse({'success': True, 'code': next_code})

# API endpoint to get next journal code
@require_http_methods(["GET"])
def get_next_journal_code_api(request):
    """API endpoint to get next journal code"""
    next_code = get_next_journal_code()
    return JsonResponse({'success': True, 'code': next_code})


def broadcast_journal_realtime_update(action, journal_code='', created_by=''):
    """Broadcast journal list/code updates to connected WebSocket clients."""
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync

        channel_layer = get_channel_layer()
        next_code = get_next_journal_code()

        async_to_sync(channel_layer.group_send)(
            'journal_code_updates',
            {
                'type': 'journal_feed_updated',
                'action': action,
                'journal_code': journal_code,
                'next_code': next_code,
                'created_by': created_by,
            }
        )

        # Keep existing journal-code preview behavior for create events.
        if action == 'created':
            async_to_sync(channel_layer.group_send)(
                'journal_code_updates',
                {
                    'type': 'journal_created',
                    'journal_code': journal_code,
                    'next_code': next_code,
                    'created_by': created_by,
                }
            )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to broadcast journal realtime update: {e}")

# pyright: ignore[reportMissingImports]
try:
    from xhtml2pdf import pisa
except Exception:
    pisa = None

# Helper function to log audit trail
def log_audit_trail(journal_header=None, journal_header_draft=None, changed_by=None, change_type='updated', field_name=None, old_value=None, new_value=None, entry_id=None):
    """Log changes to journal entries in audit trail"""
    try:
        JournalAuditTrail.objects.create(
            journal_header=journal_header,
            journal_header_draft=journal_header_draft,
            changed_by=changed_by,
            change_type=change_type,
            field_name=field_name,
            old_value=str(old_value) if old_value is not None else None,
            new_value=str(new_value) if new_value is not None else None,
            entry_id=entry_id
        )
    except Exception as e:
        print(f"Error logging audit trail: {e}")


def _to_decimal(value):
    if value in (None, '', 'NaN'):
        return Decimal('0')
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0')


def _validate_account_balance_for_rows(entry_rows, exclude_header_id=None):
    """
    Validate that journal rows will not make any account go below zero
    based on account normal balance:
      - Assets/Expenses: balance = debit - credit
      - Liabilities/Equity/Revenue: balance = credit - debit
    """
    if not entry_rows:
        return True, ''

    account_effects = {}
    account_objects = {}

    for row in entry_rows:
        account = row.get('account')
        if not account:
            continue

        debit = _to_decimal(row.get('debit'))
        credit = _to_decimal(row.get('credit'))
        if debit == 0 and credit == 0:
            continue

        account_objects[account.id] = account
        effect = account_effects.setdefault(account.id, {'debit': Decimal('0'), 'credit': Decimal('0')})
        effect['debit'] += debit
        effect['credit'] += credit

    if not account_effects:
        return True, ''

    balances_qs = JournalEntry.objects.filter(account_id__in=account_effects.keys())
    if exclude_header_id is not None:
        balances_qs = balances_qs.exclude(journal_header_id=exclude_header_id)

    existing_balances = {}
    for row in balances_qs.values('account_id').annotate(total_debit=Sum('debit'), total_credit=Sum('credit')):
        existing_balances[row['account_id']] = {
            'debit': row['total_debit'] or Decimal('0'),
            'credit': row['total_credit'] or Decimal('0'),
        }

    debit_normal_types = {'Assets', 'Expenses'}

    for account_id, movement in account_effects.items():
        account = account_objects.get(account_id)
        if not account:
            continue

        current = existing_balances.get(account_id, {'debit': Decimal('0'), 'credit': Decimal('0')})
        current_debit = _to_decimal(current['debit'])
        current_credit = _to_decimal(current['credit'])

        if account.account_type in debit_normal_types:
            current_balance = current_debit - current_credit
            movement_effect = movement['debit'] - movement['credit']
            required_reduction = movement['credit'] - movement['debit']
        else:
            current_balance = current_credit - current_debit
            movement_effect = movement['credit'] - movement['debit']
            required_reduction = movement['debit'] - movement['credit']

        projected_balance = current_balance + movement_effect

        if projected_balance < 0:
            if 'cash' in account.account_name.lower() and required_reduction > 0 and current_balance <= 0:
                return False, f'The journal cannot go through because cash account "{account.account_name}" is empty.'

            return False, (
                f'The journal cannot go through because account "{account.account_name}" '
                f'has insufficient balance (available: {current_balance}, needed: {required_reduction if required_reduction > 0 else Decimal("0")}).'
            )

    return True, ''


def _validate_unique_accounts_for_rows(entry_rows):
    """Ensure each account appears at most once in a journal payload."""
    seen = set()
    duplicates = []

    for row in entry_rows or []:
        account = row.get('account') if isinstance(row, dict) else None
        if not account:
            continue
        if account.id in seen:
            duplicates.append(account.account_name)
        else:
            seen.add(account.id)

    if duplicates:
        unique_names = sorted(set(duplicates))
        return False, f'Duplicate account selection is not allowed: {", ".join(unique_names)}.'

    return True, ''


def _build_account_balance_map(accounts_queryset):
    account_list = list(accounts_queryset)
    if not account_list:
        return {}

    account_ids = [account.id for account in account_list]
    balances = {
        str(account.id): {
            'account_name': account.account_name,
            'account_type': account.account_type,
            'available_balance': 0.0,
        }
        for account in account_list
    }

    journal_totals = JournalEntry.objects.filter(account_id__in=account_ids).values('account_id').annotate(
        total_debit=Sum('debit'),
        total_credit=Sum('credit')
    )

    debit_normal_types = {'Assets', 'Expenses'}

    for row in journal_totals:
        account_id = str(row['account_id'])
        account_data = balances.get(account_id)
        if not account_data:
            continue

        total_debit = _to_decimal(row['total_debit'])
        total_credit = _to_decimal(row['total_credit'])
        if account_data['account_type'] in debit_normal_types:
            available_balance = total_debit - total_credit
        else:
            available_balance = total_credit - total_debit

        account_data['available_balance'] = float(available_balance)

    return balances

# Create your views here.

# Home Page
def index(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("AccountingSystem:login_view"))
    
    total_accounts = ChartOfAccounts.objects.count()
    # students (and non-superusers) only count their own journals
    total_journals = JournalHeader.objects.filter(user=request.user).count() if not request.user.is_superuser else JournalHeader.objects.count()
    total_entries = JournalEntry.objects.count()

    context = {
        'total_accounts': total_accounts,
        'total_journals': total_journals,
        'total_entries': total_entries,
    }
    return render(request, "Front_End/index.html", context)

# Login Page
def login_view(request):
    MAX_ATTEMPTS = 3
    ATTEMPT_WINDOW = 15 * 60   # seconds
    LOCKOUT_TIME = 5 * 60      # seconds

    def get_cache_keys(norm_username):
        return (f"login_attempts:{norm_username}", f"login_lockout:{norm_username}")

    if request.method == "POST":
        raw_username = request.POST.get("usn", "")
        username = (raw_username or "").strip()
        password = request.POST.get("password", "")

        # Validate empty fields
        if not username:
            messages.error(request, "Please enter a username.")
            return render(request, "Front_End/login.html")
        
        if not password:
            messages.error(request, "Please enter a password.")
            return render(request, "Front_End/login.html")

        # use a normalized username for counting/lockout (case-insensitive + trimmed)
        norm_username = username.lower()

        attempts_key, lockout_key = get_cache_keys(norm_username)

        # If locked out, inform user and stop before authenticate()
        if cache.get(lockout_key):
            messages.error(request, "Account locked due to multiple failed login attempts. Try again later.")
            return render(request, "Front_End/login.html")

        # Check if username exists first
        try:
            user_exists = User.objects.get(username=username)
            username_found = True
        except User.DoesNotExist:
            user_exists = None
            username_found = False

        user = authenticate(request, username=username, password=password)
        if user is not None:
            # Successful login -> clear counters and proceed
            cache.delete(attempts_key)
            cache.delete(lockout_key)
            profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'role': 'student'})

            if is_temporary_password_expired(profile):
                user.set_unusable_password()
                user.save(update_fields=['password'])
                clear_temporary_password_state(user)
                messages.error(request, 'Your temporary password has expired. Request a new one and use it within 5 minutes.')
                return render(request, "Front_End/login.html")

            # Block students with no assigned section from logging in
            if profile.role == "student" and profile.section is None:
                messages.error(request, "You are not assigned to a section yet. You cannot log in to the system.")
                return render(request, "Front_End/login.html")

            login(request, user)

            if profile.requires_password_change:
                messages.warning(request, 'You must change your temporary password before continuing.')
                return redirect('AccountingSystem:force_password_change')

            messages.success(request, "Login Successful")
            return redirect(get_post_login_redirect_name(user))
        else:
            # Failed login -> increment attempts (use normalized key)
            attempts = cache.get(attempts_key, 0) + 1
            cache.set(attempts_key, attempts, ATTEMPT_WINDOW)

            remaining = MAX_ATTEMPTS - attempts
            
            # Provide specific error messages
            if not username_found:
                # Username doesn't exist
                error_message = f"Username '{username}' does not exist."
            else:
                # Username exists but password is wrong
                error_message = f"Invalid password for user '{username}'."
            
            if remaining <= 0:
                cache.set(lockout_key, True, LOCKOUT_TIME)
                cache.delete(attempts_key)
                messages.error(request, f"{error_message} Account locked for {int(LOCKOUT_TIME/60)} minutes due to multiple failed attempts.")
            else:
                messages.error(request, f"{error_message} {remaining} attempt(s) remaining.")

            return render(request, "Front_End/login.html")

    return render(request, "Front_End/login.html")

# Directs to Login Page once logged out.
def logout_view(request):
    logout(request)
    messages.success(request, "Logout Successful")
    return render(request, "Front_End/login.html")


# Forgot password: accepts username, generates temporary password, emails user
def forgot_password(request):
    if request.method != 'POST':
        return redirect('AccountingSystem:login_view')

    username = (request.POST.get('fp_username') or '').strip()
    if not username:
        messages.error(request, 'Please enter your username.')
        return redirect('AccountingSystem:login_view')

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        messages.error(request, 'Username not found.')
        return redirect('AccountingSystem:login_view')

    if not user.email:
        messages.error(request, 'No email associated with this account. Contact administrator.')
        return redirect('AccountingSystem:login_view')

    profile = getattr(user, 'profile', None)
    if user.is_superuser or (profile and profile.role == 'admin'):
        messages.error(request, 'Administrator accounts cannot request temporary passwords. Contact another administrator for a manual reset.')
        return redirect('AccountingSystem:login_view')

    # generate temporary password
    temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    expiry_minutes = max(1, int(getattr(settings, 'TEMP_PASSWORD_EXPIRY_MINUTES', 5)))

    login_url = f"{get_system_base_url(request)}{reverse('AccountingSystem:login_view')}"
    subject = 'Temporary Password - ACLC Accounting System'
    message = (
        f"Hello {user.username},\n\nA temporary password has been generated for your account:\n\n"
        f"{temp_password}\n\nThis temporary password expires in {expiry_minutes} minutes. Please login and change your password immediately.\n"
        f"Login URL: {login_url}\n\nIf you did not request this, contact support."
    )
    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com')

    # Try to send the email first. Only change the stored password if email was sent.
    try:
        send_mail(subject, message, from_email, [user.email], fail_silently=False)
    except Exception as e:
        # Email failed — log details and keep the existing password unchanged
        print(f"Failed to send email to {user.email}: {e}")
        print(f"Temporary password (not applied) for {user.username}: {temp_password}")
        messages.error(request, 'Unable to send email with temporary password. The temporary password was logged to the server console.')
        return redirect('AccountingSystem:login_view')

    # Email sent successfully — apply the temporary password
    user.set_password(temp_password)
    user.save()
    mark_temporary_password(user)
    messages.success(request, f'A temporary password has been sent to {user.email}.')
    return redirect('AccountingSystem:login_view')


def force_password_change_view(request):
    if not request.user.is_authenticated:
        return redirect('AccountingSystem:login_view')

    profile, _ = UserProfile.objects.get_or_create(user=request.user, defaults={'role': 'student'})
    if is_temporary_password_expired(profile):
        request.user.set_unusable_password()
        request.user.save(update_fields=['password'])
        clear_temporary_password_state(request.user)
        logout(request)
        messages.error(request, 'Your temporary password expired before you changed it. Request a new temporary password.')
        return redirect('AccountingSystem:login_view')

    if not profile.requires_password_change:
        return redirect(get_post_login_redirect_name(request.user))

    context = {
        'expiry_minutes': max(1, int(getattr(settings, 'TEMP_PASSWORD_EXPIRY_MINUTES', 5))),
        'redirect_url': get_post_login_redirect_url(request.user),
    }
    return render(request, 'Front_End/force_password_change.html', context)

# Admin Home Page
@role_required(['admin'])
def admin_dashboard(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("AccountingSystem:login_view"))
    
    total_accounts = ChartOfAccounts.objects.count()
    total_journals = JournalHeader.objects.filter(user=request.user).count() if not request.user.is_superuser else JournalHeader.objects.count()
    total_entries = JournalEntry.objects.count()
    users = User.objects.all()
    students = User.objects.filter(profile__role='student').select_related('profile', 'profile__section').order_by('last_name', 'first_name', 'username')
    teachers = User.objects.filter(profile__role='teacher').select_related('profile').order_by('first_name', 'last_name', 'username')
    sections = StudentSection.objects.all().prefetch_related('account_groups', 'teachers').annotate(student_count=Count('students')).order_by('name')
    account_groups = AccountGroups.objects.all().order_by('group_name')
    received_messages = Message.objects.filter(recipient=request.user).order_by('-created_at')
    sent_messages = Message.objects.filter(sender=request.user).order_by('-created_at')
    
    # Get sections managed by this admin
    admin_managed_sections = request.user.managed_sections.all()
    # Get account groups assigned to this admin
    admin_account_groups = request.user.profile.account_groups.all()

    context = {
        'total_accounts': total_accounts,
        'total_journals': total_journals,
        'total_entries': total_entries,
        'users': users,
        'students': students,
        'teachers': teachers,
        'sections': sections,
        'account_groups': account_groups,
        'admin_managed_sections': admin_managed_sections,
        'admin_account_groups': admin_account_groups,
        'received_messages': received_messages,
        'sent_messages': sent_messages,
    }
    return render(request, "Front_End/admin_dashboard.html", context)

# Teacher Home Page
@role_required(['teacher'])
def teacher_dashboard(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("AccountingSystem:login_view"))
    
    total_accounts = ChartOfAccounts.objects.count()
    total_journals = JournalHeader.objects.filter(user=request.user).count() if not request.user.is_superuser else JournalHeader.objects.count()
    total_entries = JournalEntry.objects.count()
    
    # Get sections managed by this teacher (with student counts)
    teacher_managed_sections = request.user.managed_sections.all().annotate(student_count=Count('students')).order_by('name')
    
    # Show only the teacher's managed sections plus unassigned students
    # Students can be: in one of teacher's managed sections, or unassigned
    students = User.objects.filter(
        Q(profile__role='student') & (
            Q(profile__section__in=teacher_managed_sections) | 
            Q(profile__section__isnull=True)
        )
    ).select_related('profile', 'profile__section').order_by('last_name', 'first_name', 'username')
    
    # Show all sections created (as context for filtering)
    all_sections = StudentSection.objects.all().prefetch_related('account_groups').order_by('name')
    
    account_groups = AccountGroups.objects.all().order_by('group_name')
    received_messages = Message.objects.filter(recipient=request.user).order_by('-created_at')
    sent_messages = Message.objects.filter(sender=request.user).order_by('-created_at')
    
    # Get account groups assigned to this teacher
    teacher_account_groups = request.user.profile.account_groups.all()

    context = {
        'total_accounts': total_accounts,
        'total_journals': total_journals,
        'total_entries': total_entries,
        'students': students,
        'sections': all_sections,
        'account_groups': account_groups,
        'teacher_managed_sections': teacher_managed_sections,
        'teacher_account_groups': teacher_account_groups,
        'selected_section': '',
        'received_messages': received_messages,
        'sent_messages': sent_messages,
    }
    return render(request, "Front_End/teacher_dashboard.html", context)


@role_required(['teacher'])
@require_http_methods(["POST"])
def create_student_section(request):
    section_name = (request.POST.get('section_name') or '').strip()

    if not section_name:
        messages.error(request, "Section name is required.")
        return redirect('AccountingSystem:teacher_dashboard')

    if StudentSection.objects.filter(name__iexact=section_name).exists():
        messages.error(request, f'Section "{section_name}" already exists.')
        return redirect('AccountingSystem:teacher_dashboard')

    StudentSection.objects.create(name=section_name)
    messages.success(request, f'Section "{section_name}" created successfully.')
    return redirect('AccountingSystem:teacher_dashboard')


@role_required(['admin'])
@require_http_methods(["POST"])
def admin_create_student_section(request):
    section_name = (request.POST.get('section_name') or '').strip()

    if not section_name:
        error_message = "Section name is required."
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': error_message}, status=400)
        messages.error(request, error_message)
        return redirect('AccountingSystem:admin_dashboard')

    if StudentSection.objects.filter(name__iexact=section_name).exists():
        error_message = f'Section "{section_name}" already exists.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': error_message}, status=400)
        messages.error(request, error_message)
        return redirect('AccountingSystem:admin_dashboard')

    section = StudentSection.objects.create(name=section_name)
    success_message = f'Section "{section_name}" created successfully.'
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': success_message,
            'section_id': section.id,
            'section_name': section.name,
        })

    messages.success(request, success_message)
    return redirect('AccountingSystem:admin_dashboard')
@role_required(['admin'])
@require_http_methods(["POST"])
def admin_rename_student_section(request):
    section_id = request.POST.get('section_id')
    new_section_name = (request.POST.get('new_section_name') or '').strip()

    if not section_id:
        error_message = 'Please select a section to rename.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': error_message}, status=400)
        messages.error(request, error_message)
        return redirect('AccountingSystem:admin_dashboard')

    if not new_section_name:
        error_message = 'New section name is required.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': error_message}, status=400)
        messages.error(request, error_message)
        return redirect('AccountingSystem:admin_dashboard')

    section = get_object_or_404(StudentSection, id=section_id)

    if StudentSection.objects.filter(name__iexact=new_section_name).exclude(id=section.id).exists():
        error_message = f'Section "{new_section_name}" already exists.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': error_message}, status=400)
        messages.error(request, error_message)
        return redirect('AccountingSystem:admin_dashboard')

    old_name = section.name
    section.name = new_section_name
    section.save(update_fields=['name'])

    # Student assignments remain intact because only the section name is changed.
    success_message = f'Section renamed from "{old_name}" to "{new_section_name}".'
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': success_message,
            'section_id': section.id,
            'old_name': old_name,
            'new_name': new_section_name,
        })

    messages.success(request, success_message)
    return redirect('AccountingSystem:admin_dashboard')

@role_required(['admin'])
@require_http_methods(["POST"])
def admin_advance_section_students(request):
    from_section_id = request.POST.get('from_section_id')
    to_section_id = request.POST.get('to_section_id')

    if not from_section_id or not to_section_id:
        error_message = 'Please select both current section and next section.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': error_message}, status=400)
        messages.error(request, error_message)
        return redirect('AccountingSystem:admin_dashboard')

    if str(from_section_id) == str(to_section_id):
        error_message = 'Current section and next section must be different.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': error_message}, status=400)
        messages.error(request, error_message)
        return redirect('AccountingSystem:admin_dashboard')

    from_section = get_object_or_404(StudentSection, id=from_section_id)
    to_section = get_object_or_404(StudentSection, id=to_section_id)

    # Move all students in one bulk update while keeping each student profile intact.
    moved_count = UserProfile.objects.filter(role='student', section=from_section).update(section=to_section)

    if moved_count == 0:
        info_message = f'No students were found in "{from_section.name}" to advance.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': info_message,
                'moved_count': moved_count,
                'from_section_id': from_section.id,
                'to_section_id': to_section.id,
            })
        messages.info(request, info_message)
    else:
        success_message = f'Changed {moved_count} student(s) from "{from_section.name}" to "{to_section.name}" successfully.'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': success_message,
                'moved_count': moved_count,
                'from_section_id': from_section.id,
                'to_section_id': to_section.id,
            })
        messages.success(request, success_message)

    return redirect('AccountingSystem:admin_dashboard')
@role_required(['admin'])
@require_http_methods(["POST"])
def admin_assign_student_sections_bulk(request):
    assignments = request.POST
    # Convert section IDs from POST (strings) to integers
    section_ids = {int(v) for k, v in assignments.items() if k.startswith('section_for_') and v}

    valid_sections = {
        section.id: section
        for section in StudentSection.objects.filter(id__in=section_ids)
    }

    updated_count = 0
    for key, section_id in assignments.items():
        if not key.startswith('section_for_'):
            continue

        student_id = key.replace('section_for_', '')
        try:
            student = User.objects.select_related('profile').get(id=student_id, profile__role='student')
        except User.DoesNotExist:
            continue

        if section_id:
            try:
                section_id_int = int(section_id)
            except ValueError:
                continue
            target_section = valid_sections.get(section_id_int)
        else:
            target_section = None

        if student.profile.section_id != (target_section.id if target_section else None):
            student.profile.section = target_section
            student.profile.save(update_fields=['section'])
            updated_count += 1

    success_message = f'Section assignments saved for {updated_count} student(s).'
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': success_message,
            'updated_count': updated_count,
        })

    messages.success(request, success_message)
    return redirect('AccountingSystem:admin_dashboard')


@role_required(['admin'])
@require_http_methods(["POST"])
def admin_assign_account_groups_to_section(request):
    section_id = request.POST.get('section_id')
    
    if not section_id:
        messages.error(request, "Section is required.")
        return redirect('AccountingSystem:admin_dashboard')
    
    section = get_object_or_404(StudentSection, id=section_id)
    
    # Get all selected account group IDs from the form
    selected_group_ids = request.POST.getlist('account_groups')
    
    # Clear existing assignments and set new ones
    section.account_groups.clear()
    if selected_group_ids:
        groups = AccountGroups.objects.filter(id__in=selected_group_ids)
        section.account_groups.set(groups)
        messages.success(request, f'{len(selected_group_ids)} account group(s) assigned to section {section.name}.')
    else:
        messages.success(request, f'All account groups removed from section {section.name}.')
    
    return redirect('AccountingSystem:admin_dashboard')

@role_required(['teacher'])
@require_http_methods(["POST"])
def assign_student_sections_bulk(request):
    """
    Assign students to sections. Teachers can only assign students to their managed sections.
    """
    teacher = request.user
    teacher_managed_sections = teacher.managed_sections.all()
    teacher_managed_section_ids = set(teacher_managed_sections.values_list('id', flat=True))
    
    assignments = request.POST
    # Convert section IDs from POST (strings) to integers
    section_ids = {int(v) for k, v in assignments.items() if k.startswith('section_for_') and v}

    # Only allow sections that the teacher manages (intersection of both sets)
    valid_section_ids = section_ids & teacher_managed_section_ids
    valid_sections = {
        section.id: section
        for section in StudentSection.objects.filter(id__in=valid_section_ids)
    }

    updated_count = 0
    for key, section_id in assignments.items():
        if not key.startswith('section_for_'):
            continue

        student_id = key.replace('section_for_', '')
        try:
            student = User.objects.select_related('profile').get(id=student_id, profile__role='student')
        except User.DoesNotExist:
            continue

        # Allow unassigning (empty section_id) or assigning to teacher's managed sections
        if section_id:
            try:
                section_id_int = int(section_id)
            except ValueError:
                continue
            
            if section_id_int not in valid_sections:
                # Teacher trying to assign to a section they don't manage
                continue
            target_section = valid_sections[section_id_int]
        else:
            # Allow unassigning students
            target_section = None

        if student.profile.section_id != (target_section.id if target_section else None):
            student.profile.section = target_section
            student.profile.save(update_fields=['section'])
            updated_count += 1

    success_message = f'Section assignments saved for {updated_count} student(s).'
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': success_message,
            'updated_count': updated_count,
        })

    messages.success(request, success_message)
    return redirect('AccountingSystem:teacher_dashboard')


@role_required(['teacher'])
@require_http_methods(["POST"])
def assign_account_groups_to_section(request):
    section_id = request.POST.get('section_id')
    
    if not section_id:
        messages.error(request, "Section is required.")
        return redirect('AccountingSystem:teacher_dashboard')
    
    section = get_object_or_404(StudentSection, id=section_id)
    
    # Get all selected account group IDs from the form
    selected_group_ids = request.POST.getlist('account_groups')
    
    # Clear existing assignments and set new ones
    section.account_groups.clear()
    if selected_group_ids:
        groups = AccountGroups.objects.filter(id__in=selected_group_ids)
        section.account_groups.set(groups)
        messages.success(request, f'{len(selected_group_ids)} account group(s) assigned to section {section.name}.')
    else:
        messages.success(request, f'All account groups removed from section {section.name}.')
    
    return redirect('AccountingSystem:teacher_dashboard')

@role_required(['teacher'])
@require_http_methods(["POST"])
def assign_teacher_to_sections(request):
    """
    Allow teachers to assign themselves to manage multiple sections.
    """
    teacher = request.user
    
    # Get all selected section IDs from the form
    selected_section_ids = request.POST.getlist('section_ids')
    
    # Get all StudentSection objects
    all_sections = StudentSection.objects.all()
    
    # Remove teacher from all sections first, then add to selected ones
    for section in all_sections:
        section.teachers.remove(teacher)
    
    # Add teacher to selected sections
    if selected_section_ids:
        selected_sections = StudentSection.objects.filter(id__in=selected_section_ids)
        for section in selected_sections:
            section.teachers.add(teacher)
        messages.success(request, f'You have been assigned to {len(selected_section_ids)} section(s).')
    else:
        messages.success(request, 'You have been removed from all sections.')
    
    return redirect('AccountingSystem:teacher_dashboard')

@role_required(['admin'])
@require_http_methods(["POST"])
def assign_admin_to_sections(request):
    """
    Allow admins to assign themselves to manage multiple sections.
    """
    admin = request.user
    
    # Get all selected section IDs from the form
    selected_section_ids = request.POST.getlist('section_ids')
    
    # Get all StudentSection objects
    all_sections = StudentSection.objects.all()
    
    # Remove admin from all sections first, then add to selected ones
    for section in all_sections:
        section.teachers.remove(admin)
    
    # Add admin to selected sections
    if selected_section_ids:
        selected_sections = StudentSection.objects.filter(id__in=selected_section_ids)
        for section in selected_sections:
            section.teachers.add(admin)
        messages.success(request, f'You have been assigned to {len(selected_section_ids)} section(s).')
    else:
        messages.success(request, 'You have been removed from all sections.')
    
    return redirect('AccountingSystem:admin_dashboard')

@role_required(['admin'])
@require_http_methods(["POST"])
def admin_assign_teachers_to_sections(request):
    """
    Allow admins to assign teachers to manage multiple sections.
    Teachers can be assigned to multiple sections, and students will see
    only their assigned section and unassigned students.
    """
    # Read checked boxes. Expected key format: teacher_<teacher_id>_section_<section_id>
    teacher_sections = {}
    for key in request.POST.keys():
        if not key.startswith('teacher_'):
            continue

        parts = key.split('_')
        if len(parts) != 4 or parts[0] != 'teacher' or parts[2] != 'section':
            continue

        try:
            teacher_id = int(parts[1])
            section_id = int(parts[3])
        except ValueError:
            continue

        teacher_sections.setdefault(teacher_id, set()).add(section_id)

    all_sections = StudentSection.objects.all()
    all_teachers = User.objects.filter(profile__role='teacher')

    # Remove only teacher-role assignments; keep admin assignments intact.
    for section in all_sections:
        existing_teachers = section.teachers.filter(profile__role='teacher')
        if existing_teachers.exists():
            section.teachers.remove(*existing_teachers)

    assignments_count = 0
    for teacher_id, section_ids in teacher_sections.items():
        teacher = all_teachers.filter(id=teacher_id).first()
        if not teacher:
            continue

        sections = StudentSection.objects.filter(id__in=section_ids)
        for section in sections:
            section.teachers.add(teacher)
            assignments_count += 1
    
    if assignments_count > 0:
        messages.success(request, f'{assignments_count} teacher-section assignment(s) saved successfully.')
    else:
        messages.info(request, 'No teachers were assigned to sections.')
    
    return redirect('AccountingSystem:admin_dashboard')

@role_required(['teacher'])
@require_http_methods(["POST"])
def assign_account_groups_to_teacher(request):
    """
    Allow teachers to assign account groups to themselves.
    Sections they manage will automatically inherit these account groups.
    """
    teacher = request.user
    
    # Get all selected account group IDs from the form
    selected_group_ids = request.POST.getlist('account_group_ids')
    
    # Clear existing assignments and set new ones
    teacher.profile.account_groups.clear()
    if selected_group_ids:
        groups = AccountGroups.objects.filter(id__in=selected_group_ids)
        teacher.profile.account_groups.set(groups)
        success_message = f'{len(selected_group_ids)} account group(s) assigned to you. Your managed sections will automatically have access to these groups.'
    else:
        success_message = 'All account groups removed from your profile.'

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': success_message})

    messages.success(request, success_message)
    return redirect('AccountingSystem:teacher_dashboard')

@role_required(['admin'])
@require_http_methods(["POST"])
def assign_account_groups_to_admin(request):
    """
    Allow admins to assign account groups to themselves.
    Sections they manage will automatically inherit these account groups.
    """
    admin = request.user
    
    # Get all selected account group IDs from the form
    selected_group_ids = request.POST.getlist('account_group_ids')
    
    # Clear existing assignments and set new ones
    admin.profile.account_groups.clear()
    if selected_group_ids:
        groups = AccountGroups.objects.filter(id__in=selected_group_ids)
        admin.profile.account_groups.set(groups)
        messages.success(request, f'{len(selected_group_ids)} account group(s) assigned to you. Your managed sections will automatically have access to these groups.')
    else:
        messages.success(request, 'All account groups removed from your profile.')
    
    return redirect('AccountingSystem:admin_dashboard')

# Student Home Page
@role_required(['student'])
def student_dashboard(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("AccountingSystem:login_view"))
    
    total_accounts = ChartOfAccounts.objects.count()
    total_journals = JournalHeader.objects.filter(user=request.user).count() if not request.user.is_superuser else JournalHeader.objects.count()
    total_entries = JournalEntry.objects.count()
    users = User.objects.all()
    received_messages = Message.objects.filter(recipient=request.user).order_by('-created_at')
    sent_messages = Message.objects.filter(sender=request.user).order_by('-created_at')

    # Get student's section information
    student_section = None
    section_teachers = []
    section_students = []
    
    if hasattr(request.user, 'profile') and request.user.profile.section:
        student_section = request.user.profile.section
        # Get teachers managing this section
        section_teachers = student_section.teachers.all().order_by('first_name', 'last_name', 'username')
        # Get fellow students in the same section (excluding current user)
        section_students = User.objects.filter(
            profile__section=student_section,
            profile__role='student'
        ).exclude(id=request.user.id).order_by('first_name', 'last_name', 'username')

    context = {
        'total_accounts': total_accounts,
        'total_journals': total_journals,
        'total_entries': total_entries,
        'users': users,
        'received_messages': received_messages,
        'sent_messages': sent_messages,
        'student_section': student_section,
        'section_teachers': section_teachers,
        'section_students': section_students,
    }
    return render(request, "Front_End/student_dashboard.html", context)

def forbidden(request):
    return render(request, "Front_End/forbidden.html", status=403)

# Chart Of Accounts Page
def chart_of_accounts(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("AccountingSystem:login_view"))

    # Filter accounts based on user role and their assigned account groups
    if hasattr(request.user, 'profile'):
        user_profile = request.user.profile
        
        if user_profile.role == 'admin':
            # Admins see all account groups and accounts
            account_groups = AccountGroups.objects.all()
            results = ChartOfAccounts.objects.all().order_by('-date_created', '-id')
        elif user_profile.role == 'teacher':
            # Teachers see only their assigned account groups
            account_groups = user_profile.account_groups.all()
            if account_groups.exists():
                # Show only accounts in their assigned groups
                results = ChartOfAccounts.objects.filter(
                    group_name__in=account_groups
                ).order_by('-date_created', '-id')
            else:
                # Teacher has no assigned groups - show no accounts
                results = ChartOfAccounts.objects.none()
        else:
            # Fallback (shouldn't happen as students use different view)
            account_groups = AccountGroups.objects.all()
            results = ChartOfAccounts.objects.all().order_by('-date_created', '-id')
    else:
        # No profile - show all (fallback)
        account_groups = AccountGroups.objects.all()
        results = ChartOfAccounts.objects.all().order_by('-date_created', '-id')
    
    return render(request, "Front_End/accounts.html", {
        "account_groups": account_groups,
        "accounts" : results
    })

# Student COA Page
def chart_of_accounts_students(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("AccountingSystem:login_view"))

    # Get user's section and filter account groups/accounts accordingly
    user_section = None
    if hasattr(request.user, 'profile') and request.user.profile.section:
        user_section = request.user.profile.section
        # Get account groups from teachers managing this section
        account_groups = get_account_groups_for_section(user_section)
        # Only show accounts in those groups
        results = ChartOfAccounts.objects.filter(
            group_name__in=account_groups
        ).order_by('-date_created', '-id')
    else:
        # Student not assigned to a section - show no accounts
        account_groups = AccountGroups.objects.none()
        results = ChartOfAccounts.objects.none()
    
    return render(request, "Front_End/accounts_students.html", {
        "account_groups": account_groups,
        "accounts": results,
        "user_section": user_section,
    })


def _render_accounts_pdf(filename, accounts, title):
    """Render a Chart of Accounts PDF response from the provided queryset."""
    context = {
        "report_title": title,
        "accounts": accounts,
        "date_now": localtime().strftime('%B %d, %Y at %I:%M %p'),
    }

    html = render_to_string('Front_End/accounts_pdf.html', context)

    if pisa is None:
        return HttpResponse('PDF generation library not installed. Install xhtml2pdf.', status=500)

    result = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.BytesIO(html.encode('utf-8')), dest=result)

    if pisa_status.err:
        return HttpResponse('Error generating PDF', status=500)

    response = HttpResponse(result.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


def chart_of_accounts_pdf(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("AccountingSystem:login_view"))

    if hasattr(request.user, 'profile'):
        user_profile = request.user.profile

        if user_profile.role == 'admin':
            accounts = ChartOfAccounts.objects.all().order_by('-date_created', '-id')
        elif user_profile.role == 'teacher':
            account_groups = user_profile.account_groups.all()
            if account_groups.exists():
                accounts = ChartOfAccounts.objects.filter(
                    group_name__in=account_groups
                ).order_by('-date_created', '-id')
            else:
                accounts = ChartOfAccounts.objects.none()
        else:
            accounts = ChartOfAccounts.objects.all().order_by('-date_created', '-id')
    else:
        accounts = ChartOfAccounts.objects.all().order_by('-date_created', '-id')

    return _render_accounts_pdf('chart_of_accounts.pdf', accounts, 'Chart of Accounts')


def chart_of_accounts_students_pdf(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("AccountingSystem:login_view"))

    user_section = None
    if hasattr(request.user, 'profile') and request.user.profile.section:
        user_section = request.user.profile.section
        account_groups = get_account_groups_for_section(user_section)
        accounts = ChartOfAccounts.objects.filter(
            group_name__in=account_groups
        ).order_by('-date_created', '-id')
    else:
        accounts = ChartOfAccounts.objects.none()

    return _render_accounts_pdf('student_chart_of_accounts.pdf', accounts, 'Student Chart of Accounts')

# Create Account Group Function to Backend
def create_group(request):
    if request.method == "POST":
        group_name = request.POST.get('group_name', '').strip()
        group_description = request.POST.get('group_description', '').strip()

        if not group_name:
            messages.error(request, "Group name is required.")
            return HttpResponseRedirect(reverse("AccountingSystem:accounts"))

        if AccountGroups.objects.filter(group_name__iexact=group_name).exists():
            messages.error(request, f'Group "{group_name}" already exists.')
            return HttpResponseRedirect(reverse("AccountingSystem:accounts"))

        AccountGroups.objects.create(
            group_name=group_name,
            group_description=group_description
        )
        messages.success(request, "Account Group created successfully.")
        return HttpResponseRedirect(reverse("AccountingSystem:accounts"))

# Create Account Function to Backend
def create_account(request):
    account_name_submit = request.POST.get('account_name', '').strip()
    account_type_submit = request.POST.get('account_type', '').strip()
    account_description_submit = request.POST.get('account_description', '').strip()
    account_group_id = request.POST.get('account_group')
    
    if not account_name_submit:
        messages.error(request, "Account name is required.")
        return HttpResponseRedirect(reverse("AccountingSystem:accounts"))

    valid_types = ["Assets", "Liabilities", "Equity", "Revenue", "Expenses"]
    if account_type_submit not in valid_types:
        messages.error(request, "Invalid account type.")
        return HttpResponseRedirect(reverse("AccountingSystem:accounts"))

    # Convert posted group id to FK id and handle empty selection.
    group_id = int(account_group_id) if account_group_id not in (None, '') else None

    # Generate account code on submit in a transaction.
    # We intentionally do not trust the client-preview code from AJAX.
    max_attempts = 3
    for _ in range(max_attempts):
        try:
            with transaction.atomic():
                duplicate_name_exists = ChartOfAccounts.objects.filter(
                    account_name__iexact=account_name_submit,
                    group_name_id=group_id
                ).exists()

                if duplicate_name_exists:
                    group_name = AccountGroups.objects.get(id=group_id).group_name if group_id else "Unassigned"
                    messages.error(request, f'Account "{account_name_submit}" already exists in group "{group_name}".')
                    return HttpResponseRedirect(reverse("AccountingSystem:accounts"))

                final_account_code = get_next_account_code(account_type_submit)

                ChartOfAccounts.objects.create(
                    account_code=final_account_code,
                    account_name=account_name_submit,
                    account_type=account_type_submit,
                    account_description=account_description_submit,
                    group_name_id=group_id,
                )

                # Broadcast to WebSocket clients that an account was created
                # so they can update their preview codes in real-time
                try:
                    from channels.layers import get_channel_layer
                    from asgiref.sync import async_to_sync
                    
                    channel_layer = get_channel_layer()
                    next_code = get_next_account_code(account_type_submit)
                    
                    async_to_sync(channel_layer.group_send)(
                        'account_code_updates',
                        {
                            'type': 'account_created',
                            'account_type': account_type_submit,
                            'account_code': final_account_code,
                            'next_code': next_code
                        }
                    )
                except Exception as e:
                    # Don't fail account creation if broadcast fails
                    print(f"Failed to broadcast account creation: {e}")

                messages.success(request, f'Account "{account_name_submit}" created successfully.')
                return HttpResponseRedirect(reverse("AccountingSystem:accounts"))
        except IntegrityError:
            # Retry if a concurrent insert took the same generated code.
            continue

    return render(
        request,
        "Front_End/forbidden.html",
        {
            "error_title": "Account Code Already Exists",
            "error_message": "The account code generated for this account is already used.",
            "error_hint": "Please go back to Accounts and submit again to generate a fresh account code.",
            "error_back_url": reverse("AccountingSystem:accounts"),
            "error_back_label": "Back to Accounts",
        },
        status=409,
    )

# Update Account Function to Backend
def update_account(request, id):
    selected_account = ChartOfAccounts.objects.get(pk=id)
    if request.method == "POST":
        new_account_name = request.POST.get("account_name", selected_account.account_name).strip()
        
        # Check uniqueness within the same account group (case-insensitive)
        # Exclude the current account from the check
        if new_account_name and new_account_name.lower() != selected_account.account_name.lower():
            duplicate_exists = ChartOfAccounts.objects.filter(
                account_name__iexact=new_account_name,
                group_name_id=selected_account.group_name_id
            ).exclude(id=id).exists()
            
            if duplicate_exists:
                group_name = selected_account.group_name.group_name if selected_account.group_name else "Unassigned"
                messages.error(request, f'Account "{new_account_name}" already exists in group "{group_name}".')
                return redirect("AccountingSystem:accounts")
        
        selected_account.account_name = new_account_name
        selected_account.account_description = request.POST.get("account_description", selected_account.account_description)
        selected_account.save()
        messages.success(request, f'Account "{selected_account.account_name}" updated successfully.')
        return redirect("AccountingSystem:accounts")
    
# Delete Account Function to Backend
def delete_account(request, id):
    try:
        account = ChartOfAccounts.objects.get(pk=id)
        account.delete()
    except RestrictedError:
        messages.error(request, "Cannot delete this account because it is linked to existing journal entries.")
    except ChartOfAccounts.DoesNotExist:
        messages.error(request, "Account not found")
    return redirect("AccountingSystem:accounts")

# Create User Function for Admin
@require_http_methods(["POST"])
def check_username_email_availability(request):
    """
    AJAX endpoint to check if username or email is already taken.
    Returns JSON with availability status.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username', '').strip()
            email = data.get('email', '').strip()
            
            response = {
                'username_available': True,
                'email_available': True,
                'username_message': '',
                'email_message': ''
            }
            
            # Check username availability
            if username and len(username) >= 3:
                if User.objects.filter(username__iexact=username).exists():
                    response['username_available'] = False
                    response['username_message'] = 'This username is already taken.'
            
            # Check email availability
            if email and '@' in email:
                if User.objects.filter(email__iexact=email).exists():
                    response['email_available'] = False
                    response['email_message'] = 'This email is already registered.'
            
            return JsonResponse(response)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@require_http_methods(["POST"])
def create_user(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            password = form.cleaned_data['password']
            user.set_password(password)
            user.save()

            # Update user profile with role (created by signal)
            profile = user.profile
            profile.role = form.cleaned_data['role']
            profile.save()

            # Send credentials email
            email_sent, email_error = send_credentials_email(user, password)
            if email_sent:
                messages.success(request, f'User "{user.username}" created successfully. Credentials sent to {user.email}.')
            else:
                messages.warning(request, f'User "{user.username}" created but email could not be sent to {user.email}. Reason: {email_error or "Unknown SMTP error"}')
            return HttpResponseRedirect(reverse("AccountingSystem:admin_dashboard"))
        else:
            for error in form.errors.values():
                messages.error(request, error)
            return HttpResponseRedirect(reverse("AccountingSystem:admin_dashboard"))

    return HttpResponseRedirect(reverse("AccountingSystem:admin_dashboard"))

# Create User Function for Teachers
def teacher_create_user(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            password = form.cleaned_data['password']
            user.set_password(password)
            user.save()

            # Update user profile with role (created by signal)
            profile = user.profile
            profile.role = form.cleaned_data['role']
            profile.save()

            # Send credentials email
            email_sent, email_error = send_credentials_email(user, password)
            if email_sent:
                messages.success(request, f'User "{user.username}" created successfully. Credentials sent to {user.email}.')
            else:
                messages.warning(request, f'User "{user.username}" created but email could not be sent to {user.email}. Reason: {email_error or "Unknown SMTP error"}')
            return HttpResponseRedirect(reverse("AccountingSystem:teacher_dashboard"))
        else:
            for error in form.errors.values():
                messages.error(request, error)
            return HttpResponseRedirect(reverse("AccountingSystem:teacher_dashboard"))

    return HttpResponseRedirect(reverse("AccountingSystem:teacher_dashboard"))

# Toggle User Active Status
@require_http_methods(["POST"])
def toggle_user_active(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        
        if not user_id:
            return JsonResponse({'success': False, 'error': 'User ID is required'}, status=400)
        
        user = User.objects.get(id=user_id)
        
        # Prevent deactivating yourself
        if user.id == request.user.id:
            return JsonResponse({'success': False, 'error': 'You cannot deactivate your own account'}, status=400)
        
        # Toggle the active status
        user.is_active = not user.is_active
        user.save()
        
        status_text = 'activated' if user.is_active else 'deactivated'
        return JsonResponse({'success': True, 'message': f'User {user.username} has been {status_text}', 'is_active': user.is_active})
    
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# Change User Password
@require_http_methods(["POST"])
def change_user_password(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        new_password = data.get('new_password')
        
        if not user_id or not new_password:
            return JsonResponse({'success': False, 'error': 'User ID and new password are required'}, status=400)
        
        if len(new_password) < 8:
            return JsonResponse({'success': False, 'error': 'Password must be at least 8 characters long'}, status=400)
        
        user = User.objects.get(id=user_id)
        user.set_password(new_password)
        user.save()
        mark_temporary_password(user)
        
        # Send email notification to user about password change
        if user.email:
            try:
                admin_name = request.user.get_full_name() or request.user.username
                subject = f'Your Password Has Been Changed'
                login_url = f"{get_system_base_url(request)}{reverse('AccountingSystem:login_view')}"
                message = f"""
Dear {user.first_name or user.username},

An administrator has reset your password in the Accounting System.

Your New Temporary Password:
{new_password}

Changed By: {admin_name}
Change Date: {localdate().strftime('%B %d, %Y')}

IMPORTANT: For security reasons, please login immediately and change this password to something only you know. You will be prompted to change it on your next login.
This temporary password expires in {getattr(settings, 'TEMP_PASSWORD_EXPIRY_MINUTES', 5)} minutes.
Login URL: {login_url}

If you did not request this password change, please contact your administrator immediately.

Best regards,
Accounting System
                """
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=True
                )
            except Exception as e:
                # Log the error but don't interrupt the password change
                print(f"Error sending password change email to {user.email}: {str(e)}")
        
        return JsonResponse({'success': True, 'message': f'Password for {user.username} has been changed successfully'})
    
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# Change Own Password
@require_http_methods(["POST"])
def change_own_password(request):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    try:
        data = json.loads(request.body)
        current_password = data.get('current_password')
        new_password = data.get('new_password')
        
        if not current_password or not new_password:
            return JsonResponse({'success': False, 'error': 'Current password and new password are required'}, status=400)
        
        # Verify current password
        user = request.user
        if not user.check_password(current_password):
            return JsonResponse({'success': False, 'error': 'Current password is incorrect'}, status=400)
        
        if len(new_password) < 8:
            return JsonResponse({'success': False, 'error': 'Password must be at least 8 characters long'}, status=400)
        
        if current_password == new_password:
            return JsonResponse({'success': False, 'error': 'New password must be different from current password'}, status=400)
        
        # Set new password
        user.set_password(new_password)
        user.save()
        clear_temporary_password_state(user)
        
        # Update session to prevent logout
        update_session_auth_hash(request, user)
        
        return JsonResponse({
            'success': True,
            'message': 'Password changed successfully',
            'redirect_url': get_post_login_redirect_url(user),
        })
    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# Update User
@require_http_methods(["POST"])
def update_user(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        email = data.get('email', '').strip()
        role = data.get('role', '').strip()
        
        if not user_id:
            return JsonResponse({'success': False, 'error': 'User ID is required'}, status=400)
        
        user = User.objects.get(id=user_id)
        
        # Prevent editing yourself
        if user.id == request.user.id:
            return JsonResponse({'success': False, 'error': 'You cannot edit your own account'}, status=400)
        
        # Update user fields
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        if email:
            user.email = email
        
        user.save()
        
        # Update role if provided
        if role and hasattr(user, 'profile'):
            user.profile.role = role
            user.profile.save()
        
        return JsonResponse({'success': True, 'message': f'User {user.username} has been updated successfully'})
    
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# Delete User
@require_http_methods(["POST"])
def delete_user(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)
    
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        
        if not user_id:
            return JsonResponse({'success': False, 'error': 'User ID is required'}, status=400)
        
        user = User.objects.get(id=user_id)
        
        # Prevent deleting yourself
        if user.id == request.user.id:
            return JsonResponse({'success': False, 'error': 'You cannot delete your own account'}, status=400)
        
        username = user.username
        user.delete()
        
        return JsonResponse({'success': True, 'message': f'User {username} has been deleted successfully'})
    
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'User not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

# Journal Entries Page
def journals(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("AccountingSystem:login_view"))
    
    # Filter account groups and accounts based on user role and section
    if hasattr(request.user, 'profile') and request.user.profile.role == 'student':
        user_section = request.user.profile.section
        if user_section:
            # Get account groups from teachers managing this section
            account_groups = get_account_groups_for_section(user_section)
            # Only show accounts in those groups
            accounts = ChartOfAccounts.objects.filter(group_name__in=account_groups)
        else:
            # Student not assigned to a section - show no accounts
            account_groups = AccountGroups.objects.none()
            accounts = ChartOfAccounts.objects.none()
    else:
        # Admin/Teacher sees all
        account_groups = AccountGroups.objects.all()
        accounts = ChartOfAccounts.objects.all()
    
    # Fetch approved journals
    journal_entries = JournalEntry.objects.select_related('journal_header', 'account')
    approved_groups = []

    headers = JournalHeader.objects.all()
    
    # Filter based on user role
    user_role = getattr(request.user.profile, 'role', None) if hasattr(request.user, 'profile') else None
    
    if user_role == 'student':
        # Students see their own journals + journals they collaborate on
        from .models import JournalCollaborator
        headers = headers.filter(
            Q(user=request.user) | Q(collaborators__collaborator=request.user)
        ).distinct()
    elif user_role == 'teacher':
        # Teachers see journals from students in sections they manage + their own journals + collaborations
        from .models import JournalCollaborator
        managed_sections = request.user.managed_sections.all()
        if managed_sections.exists():
            headers = headers.filter(
                Q(user=request.user) |  # Own journals
                Q(collaborators__collaborator=request.user) |  # Collaborations
                Q(user__profile__role='student', user__profile__section__in=managed_sections)  # Students in managed sections
            ).distinct()
        else:
            # Teacher with no sections sees only own journals + collaborations
            headers = headers.filter(
                Q(user=request.user) | Q(collaborators__collaborator=request.user)
            ).distinct()
    # Admin sees all journals (no filtering)
    
    headers = headers.order_by('-journal_date_created', '-id')

    for header in headers:
        entries = journal_entries.filter(journal_header=header)
        totals = entries.aggregate(
            total_debit=Sum('debit'),
            total_credit=Sum('credit')
        )

        approved_groups.append({
            'header': header,
            'entries': entries,
            'total_debit': totals['total_debit'] or 0,
            'total_credit': totals['total_credit'] or 0
        })

    # Fetch draft journals
    journal_entries_drafts = JournalEntryDrafts.objects.select_related('journal_header', 'account')
    draft_groups = []

    draft_headers = JournalHeaderDrafts.objects.all()
    
    # Filter based on user role (same logic as approved journals)
    if user_role == 'student':
        # Students see their own draft journals + draft journals they collaborate on
        from .models import JournalDraftCollaborator
        draft_headers = draft_headers.filter(
            Q(user=request.user) | Q(collaborators__collaborator=request.user)
        ).distinct()
    elif user_role == 'teacher':
        # Teachers see draft journals from students in sections they manage + their own + collaborations
        from .models import JournalDraftCollaborator
        managed_sections = request.user.managed_sections.all()
        if managed_sections.exists():
            draft_headers = draft_headers.filter(
                Q(user=request.user) |  # Own draft journals
                Q(collaborators__collaborator=request.user) |  # Draft collaborations
                Q(user__profile__role='student', user__profile__section__in=managed_sections)  # Students in managed sections
            ).distinct()
        else:
            # Teacher with no sections sees only own draft journals + collaborations
            draft_headers = draft_headers.filter(
                Q(user=request.user) | Q(collaborators__collaborator=request.user)
            ).distinct()
    # Admin sees all draft journals (no filtering)
    
    draft_headers = draft_headers.order_by('-journal_date_created', '-id')

    for header in draft_headers:
        entries = journal_entries_drafts.filter(journal_header=header)
        totals = entries.aggregate(
            total_debit=Sum('debit'),
            total_credit=Sum('credit')
        )

        draft_groups.append({
            'header': header,
            'entries': entries,
            'total_debit': totals['total_debit'] or 0,
            'total_credit': totals['total_credit'] or 0
        })

    # Sort by user id so {% regroup %} consolidates all drafts per user into one group
    draft_groups_by_user = sorted(draft_groups, key=lambda x: x['header'].user_id)
    account_balances_json = json.dumps(_build_account_balance_map(accounts), cls=DjangoJSONEncoder)

    return render(request, 'Front_End/journal.html', {
        'draft_groups': draft_groups,
        'draft_groups_by_user': draft_groups_by_user,
        'approved_groups': approved_groups,
        'account_groups': account_groups,
        "accounts" : accounts,
        'account_balances_json': account_balances_json,
        })

# Journal Drafts Page
def journals_drafts(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("AccountingSystem:login_view"))
    
    account_groups = AccountGroups.objects.all()
    accounts = ChartOfAccounts.objects.all()
    journal_entries_drafts = JournalEntryDrafts.objects.select_related('journal_header', 'account')
    journal_drafts_groups = []

    headers = JournalHeaderDrafts.objects.all()
    # restrict to current user unless administrator/teacher should see all
    if not request.user.is_superuser and getattr(request.user, 'profile', None) and request.user.profile.role == 'student':
        headers = headers.filter(user=request.user)
    headers = headers.order_by('-journal_date_created', '-id')

    for header in headers:
        entries = journal_entries_drafts.filter(journal_header=header)
        totals = entries.aggregate(
            total_debit=Sum('debit'),
            total_credit=Sum('credit')
        )

        journal_drafts_groups.append({
            'header': header,
            'entries': entries,
            'total_debit': totals['total_debit'] or 0,
            'total_credit': totals['total_credit'] or 0
        })

    return render(request, 'Front_End/journal_drafts.html', {
        'journal_groups': journal_drafts_groups,
        'account_groups': account_groups,
        "accounts" : accounts
        })

# Insert Journal Function to Backend
def insert_journals(request):
    if request.method == "POST":
        journal_code = request.POST.get("journal_code", '').strip()
        date_submit = request.POST['entry-date']
        account_group = request.POST["account_group"]
        account_ids = request.POST.getlist('account_name')
        
        debits = request.POST.getlist('debit')
        credits = request.POST.getlist('credit')
        description = request.POST['journal_description']

        # Never trust placeholder/invalid client values; generate server-side when needed.
        is_valid_code = bool(re.match(r'^JE-\d{10}$', journal_code))
        if (not journal_code) or (journal_code in {"Loading...", "Error", "Error loading code"}) or (not is_valid_code):
            journal_code = get_next_journal_code()

        prepared_rows = []
        for i in range(len(account_ids)):
            account_id = account_ids[i]
            debit = debits[i] if i < len(debits) else ''
            credit = credits[i] if i < len(credits) else ''

            if not account_id or (debit == '' and credit == ''):
                continue

            try:
                account = ChartOfAccounts.objects.get(pk=account_id)
            except ChartOfAccounts.DoesNotExist:
                continue

            prepared_rows.append({
                'account': account,
                'debit': _to_decimal(debit),
                'credit': _to_decimal(credit),
            })

        is_unique_valid, unique_error = _validate_unique_accounts_for_rows(prepared_rows)
        if not is_unique_valid:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': unique_error}, status=400)
            messages.error(request, unique_error)
            return redirect('AccountingSystem:journals')

        is_balance_valid, balance_error = _validate_account_balance_for_rows(prepared_rows)
        if not is_balance_valid:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': balance_error}, status=400)
            messages.error(request, balance_error)
            return redirect('AccountingSystem:journals')

        try:
            with transaction.atomic():
                # Creates Journal Header
                header = JournalHeaderDrafts.objects.create(
                    entry_no=journal_code,
                    entry_date=date_submit,
                    journal_description=description,
                    group_name=AccountGroups.objects.get(pk=account_group),
                    user=request.user,
                )

                # Log journal header creation
                log_audit_trail(
                    journal_header_draft=header,
                    changed_by=request.user,
                    change_type='created',
                    field_name='journal_created',
                    new_value=f'Journal {journal_code} created'
                )

                # Loops through the rows and create Journal Entries
                for row in prepared_rows:
                    account = row['account']
                    debit = row['debit']
                    credit = row['credit']

                    journal_entry = JournalEntryDrafts.objects.create(
                        journal_header=header,
                        account=account,
                        debit=debit,
                        credit=credit

                    )

                    # Log journal entry creation
                    log_audit_trail(
                        journal_header_draft=header,
                        changed_by=request.user,
                        change_type='created',
                        field_name='entry_created',
                        new_value=f'{account.account_name} (D:{debit}, C:{credit})',
                        entry_id=journal_entry.id
                    )
        except IntegrityError:
            return render(
                request,
                "Front_End/forbidden.html",
                {
                    "error_title": "Journal Code Already Exists",
                    "error_message": "The journal code you tried to save is already used.",
                    "error_hint": "Please go back, reopen the Add Journal form, and try again to get a fresh journal code.",
                },
                status=409,
            )
        
        broadcast_journal_realtime_update(
            action='created',
            journal_code=journal_code,
            created_by=request.user.get_full_name() or request.user.username,
        )
            
        return redirect('AccountingSystem:journals')  # or render success message

    # GET request
    #accounts = ChartOfAccounts.objects.all()
    #return render(request, 'journal_form.html', {'accounts': accounts})

# Update Journal Entry
def update_journal(request, id):
    # retrieve header only if user owns it, is admin/teacher, or is a collaborator
    user_role = getattr(request.user.profile, 'role', None) if hasattr(request.user, 'profile') else None
    
    if user_role == 'admin':
        header = get_object_or_404(JournalHeader, pk=id)
    else:
        # Check if user is the owner or a collaborator
        try:
            header = JournalHeader.objects.get(pk=id, user=request.user)
        except JournalHeader.DoesNotExist:
            # Check if user is a collaborator
            try:
                header = get_object_or_404(JournalHeader, pk=id, collaborators__collaborator=request.user)
            except:
                # Check if teacher can access this student's journal
                if user_role == 'teacher':
                    header = JournalHeader.objects.get(pk=id)
                    student_section = header.user.profile.section if hasattr(header.user, 'profile') else None
                    managed_sections = request.user.managed_sections.all()
                    if not (student_section and student_section in managed_sections):
                        messages.error(request, "You can only edit journals from students in your managed sections.")
                        return redirect(reverse("AccountingSystem:journals"))
                else:
                    raise

    if request.method != "POST":
        return redirect(reverse("AccountingSystem:journals"))  # adjust name

    # collect posted rows (names used in your update modal)
    account_values = request.POST.getlist('edit_account_name')
    debits = request.POST.getlist('edit_debit')
    credits = request.POST.getlist('edit_credit')

    # header fields
    entry_date = request.POST.get('edit_entry-date') or request.POST.get('entry_date')
    description = request.POST.get('edit_journal_description') or request.POST.get('journal_description')

    # sanitize amounts and compute totals
    total_debit = 0
    total_credit = 0
    parsed_debits = []
    parsed_credits = []
    for d in debits:
        val = float(d) if d not in (None, '', 'NaN') else 0.0
        parsed_debits.append(val)
        total_debit += val
    for c in credits:
        val = float(c) if c not in (None, '', 'NaN') else 0.0
        parsed_credits.append(val)
        total_credit += val

    # validation
    if total_debit == 0:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Please enter amount!'})
        return redirect(reverse("AccountingSystem:journals"))

    if round(total_debit, 2) != round(total_credit, 2):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Total Debit and Credit must be equal!'})
        # set a message or handle as needed
        return redirect(reverse("AccountingSystem:journals"))

    prepared_rows = []
    for i, acc_val in enumerate(account_values):
        debit = parsed_debits[i] if i < len(parsed_debits) else 0.0
        credit = parsed_credits[i] if i < len(parsed_credits) else 0.0
        if not acc_val or (debit == 0 and credit == 0):
            continue

        account = None
        try:
            account = ChartOfAccounts.objects.get(pk=int(acc_val))
        except (ValueError, ChartOfAccounts.DoesNotExist):
            account = ChartOfAccounts.objects.filter(account_name=acc_val).first()

        if not account:
            continue

        prepared_rows.append({
            'account': account,
            'debit': _to_decimal(debit),
            'credit': _to_decimal(credit),
        })

    is_unique_valid, unique_error = _validate_unique_accounts_for_rows(prepared_rows)
    if not is_unique_valid:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': unique_error}, status=400)
        messages.error(request, unique_error)
        return redirect(reverse("AccountingSystem:journals"))

    is_balance_valid, balance_error = _validate_account_balance_for_rows(prepared_rows, exclude_header_id=header.id)
    if not is_balance_valid:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': balance_error}, status=400)
        messages.error(request, balance_error)
        return redirect(reverse("AccountingSystem:journals"))

    # perform update inside transaction
    with transaction.atomic():
        # Store old values for audit trail
        old_entry_date = header.entry_date
        old_description = header.journal_description
        old_entries = list(JournalEntry.objects.filter(journal_header=header).values('id', 'account__account_name', 'debit', 'credit'))
        
        # update header
        if entry_date:
            header.entry_date = entry_date
        header.journal_description = description or header.description
        header.save()
        
        # Log header changes
        if old_entry_date != header.entry_date:
            log_audit_trail(
                journal_header=header,
                changed_by=request.user,
                change_type='updated',
                field_name='entry_date',
                old_value=old_entry_date,
                new_value=header.entry_date
            )
        if old_description != header.journal_description:
            log_audit_trail(
                journal_header=header,
                changed_by=request.user,
                change_type='updated',
                field_name='journal_description',
                old_value=old_description,
                new_value=header.journal_description
            )

        # remove existing entries
        JournalEntry.objects.filter(journal_header=header).delete()

        # recreate entries
        for row in prepared_rows:
            account = row['account']
            debit = row['debit']
            credit = row['credit']

            new_entry = JournalEntry.objects.create(
                journal_header=header,
                account=account,
                debit=debit,
                credit=credit
            )
            
            # Log entry creation
            log_audit_trail(
                journal_header=header,
                changed_by=request.user,
                change_type='updated',
                field_name='entry_added',
                new_value=f'{account.account_name} (D:{debit}, C:{credit})',
                entry_id=new_entry.id
            )

    # respond
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        broadcast_journal_realtime_update(
            action='updated',
            journal_code=header.entry_no,
            created_by=request.user.get_full_name() or request.user.username,
        )
        return JsonResponse({'success': True})
    broadcast_journal_realtime_update(
        action='updated',
        journal_code=header.entry_no,
        created_by=request.user.get_full_name() or request.user.username,
    )
    return redirect(reverse("AccountingSystem:journals"))

# Delete Journal Entry
def delete_journal(request, id):
    user_role = getattr(request.user.profile, 'role', None) if hasattr(request.user, 'profile') else None
    
    try:
        if user_role == 'admin':
            journal_header = JournalHeader.objects.get(pk=id)
        elif user_role == 'teacher':
            # Teacher can delete their own journals or students' journals from managed sections
            try:
                journal_header = JournalHeader.objects.get(pk=id, user=request.user)
            except JournalHeader.DoesNotExist:
                # Check if it's a student's journal in a managed section
                journal_header = JournalHeader.objects.get(pk=id)
                student_section = journal_header.user.profile.section if hasattr(journal_header.user, 'profile') else None
                managed_sections = request.user.managed_sections.all()
                if not (student_section and student_section in managed_sections):
                    messages.error(request, "You can only delete journals from students in your managed sections.")
                    return redirect("AccountingSystem:journals")
        else:
            journal_header = JournalHeader.objects.get(pk=id, user=request.user)
        deleted_code = journal_header.entry_no
        journal_header.delete()
        broadcast_journal_realtime_update(
            action='deleted',
            journal_code=deleted_code,
            created_by=request.user.get_full_name() or request.user.username,
        )
        messages.success(request, "Journal deleted successfully.")
    except JournalHeader.DoesNotExist:
        messages.error(request, "Journal not found.")
    return redirect("AccountingSystem:journals")

# Get Journal Audit Trail History
def get_journal_history(request, id):
    """API endpoint to get audit trail history for a journal"""
    user_role = getattr(request.user.profile, 'role', None) if hasattr(request.user, 'profile') else None
    
    try:
        if user_role == 'admin':
            header = JournalHeader.objects.get(pk=id)
        else:
            # Check if user is the owner or a collaborator
            try:
                header = JournalHeader.objects.get(pk=id, user=request.user)
            except JournalHeader.DoesNotExist:
                try:
                    header = get_object_or_404(JournalHeader, pk=id, collaborators__collaborator=request.user)
                except:
                    # Check if teacher can access this student's journal
                    if user_role == 'teacher':
                        header = JournalHeader.objects.get(pk=id)
                        student_section = header.user.profile.section if hasattr(header.user, 'profile') else None
                        managed_sections = request.user.managed_sections.all()
                        if not (student_section and student_section in managed_sections):
                            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
                    else:
                        raise
    except JournalHeader.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Journal not found'}, status=404)
    
    # Get audit trails for this journal
    audit_trails = JournalAuditTrail.objects.filter(journal_header=header).order_by('-changed_at')
    
    history = []
    for trail in audit_trails:
        # Display first and last name, fallback to username if names not available
        if trail.changed_by:
            full_name = f"{trail.changed_by.first_name} {trail.changed_by.last_name}".strip()
            changed_by_display = full_name if full_name else trail.changed_by.username
        else:
            changed_by_display = 'System'
            
        history.append({
            'id': trail.id,
            'changed_by': changed_by_display,
            'change_type': trail.get_change_type_display(),
            'changed_at': localtime(trail.changed_at).strftime('%Y-%m-%d %H:%M:%S'),
            'field_name': trail.field_name,
            'old_value': trail.old_value,
            'new_value': trail.new_value,
        })
    
    return JsonResponse({'success': True, 'history': history})

# Get Journal Draft Audit Trail History
def get_journal_draft_history(request, id):
    """API endpoint to get audit trail history for a draft journal"""
    user_role = getattr(request.user.profile, 'role', None) if hasattr(request.user, 'profile') else None
    
    try:
        if user_role == 'admin':
            header = JournalHeaderDrafts.objects.get(pk=id)
        else:
            # Check if user is the owner or a collaborator
            try:
                header = JournalHeaderDrafts.objects.get(pk=id, user=request.user)
            except JournalHeaderDrafts.DoesNotExist:
                try:
                    header = get_object_or_404(JournalHeaderDrafts, pk=id, collaborators__collaborator=request.user)
                except:
                    # Check if teacher can access this student's draft journal
                    if user_role == 'teacher':
                        header = JournalHeaderDrafts.objects.get(pk=id)
                        student_section = header.user.profile.section if hasattr(header.user, 'profile') else None
                        managed_sections = request.user.managed_sections.all()
                        if not (student_section and student_section in managed_sections):
                            return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)
                    else:
                        raise
    except JournalHeaderDrafts.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Journal not found'}, status=404)
    
    # Get audit trails for this journal
    audit_trails = JournalAuditTrail.objects.filter(journal_header_draft=header).order_by('-changed_at')
    
    history = []
    for trail in audit_trails:
        # Display first and last name, fallback to username if names not available
        if trail.changed_by:
            full_name = f"{trail.changed_by.first_name} {trail.changed_by.last_name}".strip()
            changed_by_display = full_name if full_name else trail.changed_by.username
        else:
            changed_by_display = 'System'
            
        history.append({
            'id': trail.id,
            'changed_by': changed_by_display,
            'change_type': trail.get_change_type_display(),
            'changed_at': localtime(trail.changed_at).strftime('%Y-%m-%d %H:%M:%S'),
            'field_name': trail.field_name,
            'old_value': trail.old_value,
            'new_value': trail.new_value,
        })
    
    return JsonResponse({'success': True, 'history': history})

# Approve Journal Draft Function - moves draft to approved journals
def approve_journal_draft(request, id):
    # only admins and teachers can approve
    user_role = getattr(request.user, 'profile', None).role if getattr(request.user, 'profile', None) else None
    if user_role not in ['admin', 'teacher']:
        error_msg = "You do not have permission to approve journals."
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': error_msg}, status=403)
        messages.error(request, error_msg)
        return redirect("AccountingSystem:journals")
    
    try:
        # get the draft header
        draft_header = JournalHeaderDrafts.objects.get(pk=id)
        
        # If teacher, verify they manage the student's section
        if user_role == 'teacher':
            student_section = draft_header.user.profile.section if hasattr(draft_header.user, 'profile') else None
            managed_sections = request.user.managed_sections.all()
            if not (student_section and student_section in managed_sections):
                error_msg = "You can only approve journals from students in your managed sections."
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': error_msg}, status=403)
                messages.error(request, error_msg)
                return redirect("AccountingSystem:journals")

        draft_entries = list(JournalEntryDrafts.objects.filter(journal_header=draft_header).select_related('account'))
        prepared_rows = [
            {
                'account': draft_entry.account,
                'debit': draft_entry.debit,
                'credit': draft_entry.credit,
            }
            for draft_entry in draft_entries
        ]
        is_balance_valid, balance_error = _validate_account_balance_for_rows(prepared_rows)
        if not is_balance_valid:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': balance_error}, status=400)
            messages.error(request, balance_error)
            return redirect("AccountingSystem:journals")
        
        with transaction.atomic():
            approved_header, created = JournalHeader.objects.get_or_create(
                entry_no=draft_header.entry_no,
                defaults={
                    'entry_date': draft_header.entry_date,
                    'journal_description': draft_header.journal_description,
                    'group_name': draft_header.group_name,
                    'user': draft_header.user,
                }
            )

            if created:
                # Log the approval in the new approved journal
                log_audit_trail(
                    journal_header=approved_header,
                    changed_by=request.user,
                    change_type='updated',
                    field_name='journal_approved',
                    new_value=f'Journal approved from draft {draft_header.entry_no}'
                )

                # copy all draft entries to approved entries
                for draft_entry in draft_entries:
                    JournalEntry.objects.create(
                        journal_header=approved_header,
                        account=draft_entry.account,
                        debit=draft_entry.debit,
                        credit=draft_entry.credit,
                        description=draft_entry.description
                    )

            # Remove the draft copy (entries cascade via FK)
            draft_header.delete()

        broadcast_journal_realtime_update(
            action='approved',
            journal_code=approved_header.entry_no,
            created_by=request.user.get_full_name() or request.user.username,
        )
        
        # Send email notification to journal creator
        creator = draft_header.user
        if creator and creator.email:
            try:
                approver_name = request.user.get_full_name() or request.user.username
                journals_url = f"{get_system_base_url(request)}{reverse('AccountingSystem:journals')}"
                subject = f'Journal Entry Approved: {draft_header.entry_no}'
                message = f"""
Dear {creator.first_name or creator.username},

Your journal entry has been approved!

Journal Details:
- Journal Code: {draft_header.entry_no}
- Entry Date: {draft_header.entry_date}
- Description: {draft_header.journal_description or 'N/A'}
- Approved By: {approver_name}
- Approval Date: {localdate().strftime('%B %d, %Y')}

You can now view the approved journal in the Accounting System.
Journals URL: {journals_url}

Best regards,
Accounting System
                """
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [creator.email],
                    fail_silently=True
                )
            except Exception as e:
                # Log the error but don't interrupt the approval process
                print(f"Error sending approval email to {creator.email}: {str(e)}")
        
        success_msg = (
            f'Journal {draft_header.entry_no} has been approved successfully.'
            if created else
            f'Journal {draft_header.entry_no} was already approved. Draft copy was removed.'
        )
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': success_msg})
        messages.success(request, success_msg)
    except JournalHeaderDrafts.DoesNotExist:
        error_msg = 'Draft journal not found.'
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': error_msg}, status=404)
        messages.error(request, error_msg)
    
    return redirect("AccountingSystem:journals")

# Approve All Journal Drafts for a Specific User
def approve_all_user_drafts(request, user_id):
    # only admins and teachers can approve
    user_role = getattr(request.user, 'profile', None).role if getattr(request.user, 'profile', None) else None
    if user_role not in ['admin', 'teacher']:
        error_msg = "You do not have permission to approve journals."
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': error_msg}, status=403)
        messages.error(request, error_msg)
        return redirect("AccountingSystem:journals")
    
    try:
        # Get the user whose drafts we're approving
        target_user = User.objects.get(pk=user_id)
        
        # Get all draft headers for this user
        draft_headers = JournalHeaderDrafts.objects.filter(user=target_user)
        
        # If teacher, verify they manage the student's section
        if user_role == 'teacher':
            student_section = target_user.profile.section if hasattr(target_user, 'profile') else None
            managed_sections = request.user.managed_sections.all()
            if not (student_section and student_section in managed_sections):
                error_msg = "You can only approve journals from students in your managed sections."
                if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': error_msg}, status=403)
                messages.error(request, error_msg)
                return redirect("AccountingSystem:journals")
        
        if not draft_headers.exists():
            error_msg = f'No draft journals found for {target_user.get_full_name() or target_user.username}.'
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': error_msg}, status=404)
            messages.warning(request, error_msg)
            return redirect("AccountingSystem:journals")
        
        approved_count = 0
        approved_codes = []
        
        # Approve each draft
        for draft_header in draft_headers:
            try:
                draft_entries = list(JournalEntryDrafts.objects.filter(journal_header=draft_header).select_related('account'))
                prepared_rows = [
                    {
                        'account': draft_entry.account,
                        'debit': draft_entry.debit,
                        'credit': draft_entry.credit,
                    }
                    for draft_entry in draft_entries
                ]
                is_balance_valid, balance_error = _validate_account_balance_for_rows(prepared_rows)
                if not is_balance_valid:
                    raise ValueError(f'Cannot approve {draft_header.entry_no}: {balance_error}')

                with transaction.atomic():
                    approved_header, created = JournalHeader.objects.get_or_create(
                        entry_no=draft_header.entry_no,
                        defaults={
                            'entry_date': draft_header.entry_date,
                            'journal_description': draft_header.journal_description,
                            'group_name': draft_header.group_name,
                            'user': draft_header.user,
                        }
                    )

                    if created:
                        # Log the approval
                        log_audit_trail(
                            journal_header=approved_header,
                            changed_by=request.user,
                            change_type='updated',
                            field_name='journal_approved',
                            new_value=f'Journal approved from draft {draft_header.entry_no} (bulk approval)'
                        )

                        # copy all draft entries to approved entries
                        for draft_entry in draft_entries:
                            JournalEntry.objects.create(
                                journal_header=approved_header,
                                account=draft_entry.account,
                                debit=draft_entry.debit,
                                credit=draft_entry.credit,
                                description=draft_entry.description
                            )

                    # Remove the draft copy (entries cascade via FK)
                    draft_header.delete()
                
                approved_count += 1
                approved_codes.append(approved_header.entry_no)
                
            except Exception as e:
                print(f"Error approving journal {draft_header.entry_no}: {str(e)}")
                continue
        
        # Broadcast realtime update after all approvals
        if approved_count > 0:
            broadcast_journal_realtime_update(
                action='approved',
                journal_code=f'{approved_count} journals',
                created_by=request.user.get_full_name() or request.user.username,
            )
            
            # Send email notification to journal creator
            if target_user and target_user.email:
                try:
                    approver_name = request.user.get_full_name() or request.user.username
                    journals_url = f"{get_system_base_url(request)}{reverse('AccountingSystem:journals')}"
                    subject = f'{approved_count} Journal Entries Approved'
                    message = f"""
Dear {target_user.first_name or target_user.username},

{approved_count} of your journal entries have been approved!

Approved Journal Codes:
{', '.join(approved_codes)}

Approved By: {approver_name}
Approval Date: {localdate().strftime('%B %d, %Y')}

You can now view the approved journals in the Accounting System.
Journals URL: {journals_url}

Best regards,
Accounting System
                    """
                    send_mail(
                        subject,
                        message,
                        settings.DEFAULT_FROM_EMAIL,
                        [target_user.email],
                        fail_silently=True
                    )
                except Exception as e:
                    print(f"Error sending bulk approval email to {target_user.email}: {str(e)}")
        
        success_msg = f'{approved_count} journal(s) approved successfully for {target_user.get_full_name() or target_user.username}.'
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True, 
                'message': success_msg,
                'approved_count': approved_count,
                'approved_codes': approved_codes
            })
        messages.success(request, success_msg)
        
    except User.DoesNotExist:
        error_msg = 'User not found.'
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': error_msg}, status=404)
        messages.error(request, error_msg)
    except Exception as e:
        error_msg = f'Error approving journals: {str(e)}'
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': error_msg}, status=500)
        messages.error(request, error_msg)
    
    return redirect("AccountingSystem:journals")

# Update Journal Draft Function
def update_journal_draft(request, id):
    # retrieve header only if user owns it, is admin/teacher, or is a collaborator
    user_role = getattr(request.user.profile, 'role', None) if hasattr(request.user, 'profile') else None
    
    if user_role == 'admin':
        header = get_object_or_404(JournalHeaderDrafts, pk=id)
    else:
        # Check if user is the owner or a collaborator
        try:
            header = JournalHeaderDrafts.objects.get(pk=id, user=request.user)
        except JournalHeaderDrafts.DoesNotExist:
            # Check if user is a collaborator
            try:
                from django.db.models import Q
                header = get_object_or_404(JournalHeaderDrafts, pk=id, collaborators__collaborator=request.user)
            except:
                # Check if teacher can access this student's draft journal
                if user_role == 'teacher':
                    header = JournalHeaderDrafts.objects.get(pk=id)
                    student_section = header.user.profile.section if hasattr(header.user, 'profile') else None
                    managed_sections = request.user.managed_sections.all()
                    if not (student_section and student_section in managed_sections):
                        messages.error(request, "You can only edit draft journals from students in your managed sections.")
                        return redirect(reverse("AccountingSystem:journals"))
                else:
                    raise

    if request.method != "POST":
        return redirect(reverse("AccountingSystem:journals"))

    # collect posted rows (names used in your update modal)
    account_values = request.POST.getlist('edit_account_name')
    debits = request.POST.getlist('edit_debit')
    credits = request.POST.getlist('edit_credit')

    # header fields
    entry_date = request.POST.get('edit_entry-date') or request.POST.get('entry_date')
    description = request.POST.get('edit_journal_description') or request.POST.get('journal_description')

    # sanitize amounts and compute totals
    total_debit = 0
    total_credit = 0
    parsed_debits = []
    parsed_credits = []
    for d in debits:
        val = float(d) if d not in (None, '', 'NaN') else 0.0
        parsed_debits.append(val)
        total_debit += val
    for c in credits:
        val = float(c) if c not in (None, '', 'NaN') else 0.0
        parsed_credits.append(val)
        total_credit += val

    # validation
    if total_debit == 0:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Please enter amount!'})
        return redirect(reverse("AccountingSystem:journals"))

    if round(total_debit, 2) != round(total_credit, 2):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Total Debit and Credit must be equal!'})
        return redirect(reverse("AccountingSystem:journals"))

    prepared_rows = []
    for i, acc_val in enumerate(account_values):
        debit = parsed_debits[i] if i < len(parsed_debits) else 0.0
        credit = parsed_credits[i] if i < len(parsed_credits) else 0.0
        if not acc_val or (debit == 0 and credit == 0):
            continue

        account = None
        try:
            account = ChartOfAccounts.objects.get(pk=int(acc_val))
        except (ValueError, ChartOfAccounts.DoesNotExist):
            account = ChartOfAccounts.objects.filter(account_name=acc_val).first()

        if not account:
            continue

        prepared_rows.append({
            'account': account,
            'debit': _to_decimal(debit),
            'credit': _to_decimal(credit),
        })

    is_unique_valid, unique_error = _validate_unique_accounts_for_rows(prepared_rows)
    if not is_unique_valid:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': unique_error}, status=400)
        messages.error(request, unique_error)
        return redirect(reverse("AccountingSystem:journals"))

    is_balance_valid, balance_error = _validate_account_balance_for_rows(prepared_rows)
    if not is_balance_valid:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': balance_error}, status=400)
        messages.error(request, balance_error)
        return redirect(reverse("AccountingSystem:journals"))

    # perform update inside transaction
    with transaction.atomic():
        # Store old values for audit trail
        old_entry_date = header.entry_date
        old_description = header.journal_description
        old_entries = list(JournalEntryDrafts.objects.filter(journal_header=header).values('id', 'account__account_name', 'debit', 'credit'))
        
        # update header
        if entry_date:
            header.entry_date = entry_date
        header.journal_description = description or header.description
        header.save()
        
        # Log header changes
        if old_entry_date != header.entry_date:
            log_audit_trail(
                journal_header_draft=header,
                changed_by=request.user,
                change_type='updated',
                field_name='entry_date',
                old_value=old_entry_date,
                new_value=header.entry_date
            )
        if old_description != header.journal_description:
            log_audit_trail(
                journal_header_draft=header,
                changed_by=request.user,
                change_type='updated',
                field_name='journal_description',
                old_value=old_description,
                new_value=header.journal_description
            )

        # remove existing entries
        JournalEntryDrafts.objects.filter(journal_header=header).delete()

        # recreate entries
        for row in prepared_rows:
            account = row['account']
            debit = row['debit']
            credit = row['credit']

            new_entry = JournalEntryDrafts.objects.create(
                journal_header=header,
                account=account,
                debit=debit,
                credit=credit
            )
            
            # Log entry creation
            log_audit_trail(
                journal_header_draft=header,
                changed_by=request.user,
                change_type='updated',
                field_name='entry_added',
                new_value=f'{account.account_name} (D:{debit}, C:{credit})',
                entry_id=new_entry.id
            )

    # respond
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        broadcast_journal_realtime_update(
            action='updated_draft',
            journal_code=header.entry_no,
            created_by=request.user.get_full_name() or request.user.username,
        )
        return JsonResponse({'success': True})
    broadcast_journal_realtime_update(
        action='updated_draft',
        journal_code=header.entry_no,
        created_by=request.user.get_full_name() or request.user.username,
    )
    return redirect(reverse("AccountingSystem:journals"))

# Delete Journal Draft Function
def delete_journal_draft(request, id):
    user_role = getattr(request.user.profile, 'role', None) if hasattr(request.user, 'profile') else None
    
    try:
        if user_role == 'admin':
            journal_header = JournalHeaderDrafts.objects.get(pk=id)
        elif user_role == 'teacher':
            # Teacher can delete their own draft journals or students' draft journals from managed sections
            try:
                journal_header = JournalHeaderDrafts.objects.get(pk=id, user=request.user)
            except JournalHeaderDrafts.DoesNotExist:
                # Check if it's a student's draft journal in a managed section
                journal_header = JournalHeaderDrafts.objects.get(pk=id)
                student_section = journal_header.user.profile.section if hasattr(journal_header.user, 'profile') else None
                managed_sections = request.user.managed_sections.all()
                if not (student_section and student_section in managed_sections):
                    messages.error(request, "You can only delete draft journals from students in your managed sections.")
                    return redirect("AccountingSystem:journals")
        else:
            journal_header = JournalHeaderDrafts.objects.get(pk=id, user=request.user)
        deleted_code = journal_header.entry_no
        journal_header.delete()
        broadcast_journal_realtime_update(
            action='deleted_draft',
            journal_code=deleted_code,
            created_by=request.user.get_full_name() or request.user.username,
        )
        messages.success(request, "Draft journal deleted successfully.")
    except JournalHeaderDrafts.DoesNotExist:
        messages.error(request, "Draft journal not found.")
    return redirect("AccountingSystem:journals")

# Add Collaborator to Draft Journal
def add_collaborator_draft(request, id):
    if request.method == "POST":
        # Only journal owner can add collaborators
        try:
            journal_header = JournalHeaderDrafts.objects.get(pk=id, user=request.user)
        except JournalHeaderDrafts.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'You can only add collaborators to your own journals.'}, status=403)
        
        # Handle JSON request body for single or bulk add
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = {}

        collaborator_ids = data.get('collaborator_ids')
        collaborator_id = data.get('collaborator_id')

        if collaborator_ids is None:
            collaborator_ids = request.POST.getlist('collaborator_ids')
        if not collaborator_ids and collaborator_id is None:
            collaborator_id = request.POST.get('collaborator_id')

        if collaborator_ids is None:
            collaborator_ids = []
        if collaborator_id and not collaborator_ids:
            collaborator_ids = [collaborator_id]

        try:
            collaborator_ids = [int(cid) for cid in collaborator_ids if cid]
        except (TypeError, ValueError):
            return JsonResponse({'success': False, 'message': 'Invalid collaborator selection.'}, status=400)

        if not collaborator_ids:
            return JsonResponse({'success': False, 'message': 'Please select at least one collaborator.'}, status=400)

        sharer_section_id = getattr(getattr(request.user, 'profile', None), 'section_id', None)
        if not sharer_section_id:
            return JsonResponse({'success': False, 'message': 'You must be assigned to a section to share journals.'}, status=400)

        existing_ids = set(
            JournalDraftCollaborator.objects.filter(journal_header=journal_header)
            .values_list('collaborator_id', flat=True)
        )

        eligible_students = User.objects.filter(
            id__in=collaborator_ids,
            profile__role='student',
            profile__section_id=sharer_section_id
        ).exclude(id=request.user.id)

        added_count = 0
        skipped_count = 0
        for collaborator in eligible_students:
            if collaborator.id in existing_ids:
                skipped_count += 1
                continue
            JournalDraftCollaborator.objects.create(journal_header=journal_header, collaborator=collaborator)
            added_count += 1

        if added_count == 0:
            return JsonResponse({'success': False, 'message': 'Selected students are already collaborators or not eligible.'})

        message = f'Added {added_count} collaborator(s).'
        if skipped_count:
            message += f' Skipped {skipped_count} already shared.'
        return JsonResponse({'success': True, 'message': message, 'added_count': added_count, 'skipped_count': skipped_count})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=400)

# Remove Collaborator from Draft Journal
def remove_collaborator_draft(request, id, collaborator_id):
    try:
        journal_header = JournalHeaderDrafts.objects.get(pk=id, user=request.user)
        JournalDraftCollaborator.objects.filter(journal_header=journal_header, collaborator_id=collaborator_id).delete()
        messages.success(request, "Collaborator removed.")
    except JournalHeaderDrafts.DoesNotExist:
        messages.error(request, "Journal not found or you don't have permission.")
    
    return redirect("AccountingSystem:journals")

# Add Collaborator to Approved Journal
def add_collaborator(request, id):
    if request.method == "POST":
        # Only journal owner can add collaborators
        try:
            journal_header = JournalHeader.objects.get(pk=id, user=request.user)
        except JournalHeader.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'You can only add collaborators to your own journals.'}, status=403)
        
        # Handle JSON request body for single or bulk add
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            data = {}

        collaborator_ids = data.get('collaborator_ids')
        collaborator_id = data.get('collaborator_id')

        if collaborator_ids is None:
            collaborator_ids = request.POST.getlist('collaborator_ids')
        if not collaborator_ids and collaborator_id is None:
            collaborator_id = request.POST.get('collaborator_id')

        if collaborator_ids is None:
            collaborator_ids = []
        if collaborator_id and not collaborator_ids:
            collaborator_ids = [collaborator_id]

        try:
            collaborator_ids = [int(cid) for cid in collaborator_ids if cid]
        except (TypeError, ValueError):
            return JsonResponse({'success': False, 'message': 'Invalid collaborator selection.'}, status=400)

        if not collaborator_ids:
            return JsonResponse({'success': False, 'message': 'Please select at least one collaborator.'}, status=400)

        sharer_section_id = getattr(getattr(request.user, 'profile', None), 'section_id', None)
        if not sharer_section_id:
            return JsonResponse({'success': False, 'message': 'You must be assigned to a section to share journals.'}, status=400)

        existing_ids = set(
            JournalCollaborator.objects.filter(journal_header=journal_header)
            .values_list('collaborator_id', flat=True)
        )

        eligible_students = User.objects.filter(
            id__in=collaborator_ids,
            profile__role='student',
            profile__section_id=sharer_section_id
        ).exclude(id=request.user.id)

        added_count = 0
        skipped_count = 0
        for collaborator in eligible_students:
            if collaborator.id in existing_ids:
                skipped_count += 1
                continue
            JournalCollaborator.objects.create(journal_header=journal_header, collaborator=collaborator)
            added_count += 1

        if added_count == 0:
            return JsonResponse({'success': False, 'message': 'Selected students are already collaborators or not eligible.'})

        message = f'Added {added_count} collaborator(s).'
        if skipped_count:
            message += f' Skipped {skipped_count} already shared.'
        return JsonResponse({'success': True, 'message': message, 'added_count': added_count, 'skipped_count': skipped_count})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=400)

# Remove Collaborator from Approved Journal
def remove_collaborator(request, id, collaborator_id):
    try:
        journal_header = JournalHeader.objects.get(pk=id, user=request.user)
        JournalCollaborator.objects.filter(journal_header=journal_header, collaborator_id=collaborator_id).delete()
        messages.success(request, "Collaborator removed.")
    except JournalHeader.DoesNotExist:
        messages.error(request, "Journal not found or you don't have permission.")
    
    return redirect("AccountingSystem:journals")

# Get available collaborators (students only, AJAX)
def get_available_collaborators(request, journal_id, is_draft):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    try:
        if is_draft == 'true':
            journal_header = JournalHeaderDrafts.objects.get(pk=journal_id, user=request.user)
            current_collaborators = JournalDraftCollaborator.objects.filter(journal_header=journal_header).values_list('collaborator_id', flat=True)
        else:
            journal_header = JournalHeader.objects.get(pk=journal_id, user=request.user)
            current_collaborators = JournalCollaborator.objects.filter(journal_header=journal_header).values_list('collaborator_id', flat=True)
        
        sharer_section_id = getattr(getattr(request.user, 'profile', None), 'section_id', None)
        section_id = request.GET.get('section_id')

        # Get all students except current user and existing collaborators
        available_students = User.objects.filter(
            profile__role='student'
        ).exclude(id=request.user.id).exclude(id__in=current_collaborators)

        if sharer_section_id:
            available_students = available_students.filter(profile__section_id=sharer_section_id)
        else:
            available_students = available_students.none()

        if section_id:
            available_students = available_students.filter(profile__section_id=section_id)

        available_students = available_students.values(
            'id',
            'username',
            'first_name',
            'last_name',
            'profile__section_id',
            'profile__section__name'
        )

        sharer_section_name = ''
        if sharer_section_id:
            sharer_section_name = StudentSection.objects.filter(id=sharer_section_id).values_list('name', flat=True).first() or ''

        return JsonResponse({
            'collaborators': list(available_students),
            'sharer_section_id': sharer_section_id,
            'sharer_section_name': sharer_section_name,
            'current': list(current_collaborators)
        })
    except (JournalHeaderDrafts.DoesNotExist, JournalHeader.DoesNotExist):
        return JsonResponse({'error': 'Journal not found'}, status=404)

# General Ledger
def general_ledger(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("AccountingSystem:login_view"))

    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')

    # Filter account groups based on user role and their assignments
    allowed_group_ids = None  # None means no filtering (shouldn't happen with this logic)
    
    if hasattr(request.user, 'profile'):
        user_profile = request.user.profile
        
        if user_profile.role == 'student':
            # Students: get account groups from their assigned section
            user_section = user_profile.section
            if user_section:
                account_groups = get_account_groups_for_section(user_section)
                allowed_group_ids = list(account_groups.values_list('id', flat=True))
            else:
                account_groups = AccountGroups.objects.none()
                allowed_group_ids = []
        elif user_profile.role == 'admin':
            # Admins: see all account groups
            account_groups = AccountGroups.objects.all()
            allowed_group_ids = None  # None means no filtering
        else:
            # Teachers: get their assigned account groups
            user_account_groups = user_profile.account_groups.all()
            account_groups = user_account_groups
            allowed_group_ids = list(user_account_groups.values_list('id', flat=True))
    else:
        account_groups = AccountGroups.objects.all()
        allowed_group_ids = None

    # build a Q filter for JournalEntry -> JournalHeader.entry_date
    date_q = Q()
    try:
        if start_str:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            date_q &= Q(journalentry__journal_header__entry_date__gte=start_date)
        if end_str:
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
            date_q &= Q(journalentry__journal_header__entry_date__lte=end_date)
    except (ValueError, TypeError):
        # ignore invalid dates and treat as no filter
        start_str = end_str = None
        date_q = Q()

    # annotate accounts with sums filtered by date_q
    accounts_query = ChartOfAccounts.objects
    
    # Filter by account groups (applies to students, admins, and teachers)
    if allowed_group_ids is not None:
        accounts_query = accounts_query.filter(group_name_id__in=allowed_group_ids)
    
    accounts_summary = accounts_query.annotate(
    total_debit=Coalesce(Sum('journalentry__debit'), Value(0), output_field=DecimalField()),
    total_credit=Coalesce(Sum('journalentry__credit'), Value(0), output_field=DecimalField()),
).order_by('group_name__id', 'account_code')

    ledger_rows = []
    total_debit = 0
    total_credit = 0

    for acc in accounts_summary:
        debit = float(acc.total_debit or 0)
        credit = float(acc.total_credit or 0)
        balance = debit - credit
        ledger_rows.append({
            'account': acc,
            'debit': debit,
            'credit': credit,
            'balance': balance,
        })
        total_debit += debit
        total_credit += credit

    # Group ledger rows by account group
    grouped_ledger = {}
    for row in ledger_rows:
        group_id = row['account'].group_name_id if row['account'].group_name_id else None
        group_name = row['account'].group_name.group_name if row['account'].group_name else 'Unassigned'
        
        if group_id not in grouped_ledger:
            grouped_ledger[group_id] = {
                'group_name': group_name,
                'entries': [],
                'debit': 0,
                'credit': 0,
                'balance': 0,
            }
        
        grouped_ledger[group_id]['entries'].append(row)
        grouped_ledger[group_id]['debit'] += row['debit']
        grouped_ledger[group_id]['credit'] += row['credit']
        grouped_ledger[group_id]['balance'] += row['balance']

    context = {
        'general_ledger': ledger_rows,
        'grouped_ledger': grouped_ledger,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'ending_balance': total_debit - total_credit,
        'start_date': start_str,
        'end_date': end_str,
        'account_groups': account_groups,
    }
    return render(request, "Front_End/ledger.html", context)

# General Ledger PDF
def general_ledger_pdf(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("AccountingSystem:login_view"))

    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')

    current_date_time = localtime().date()
    # Format date and time as a string for PDF (xhtml2pdf has limited template filter support)
    formatted_date_time = current_date_time.strftime('%B %d, %Y at %I:%M %p')

    # Filter account groups based on user role and section
    if hasattr(request.user, 'profile') and request.user.profile.role == 'student':
        user_section = request.user.profile.section
        if user_section:
            # Get account groups from teachers managing this section
            account_groups = get_account_groups_for_section(user_section)
            allowed_group_ids = list(account_groups.values_list('id', flat=True))
        else:
            account_groups = AccountGroups.objects.none()
            allowed_group_ids = []
    elif hasattr(request.user, 'profile') and request.user.profile.role == 'teacher':
        # Teachers see only their assigned account groups
        account_groups = request.user.profile.account_groups.all()
        allowed_group_ids = list(account_groups.values_list('id', flat=True))
    elif hasattr(request.user, 'profile') and request.user.profile.role == 'admin':
        # Admins see all account groups
        account_groups = AccountGroups.objects.all()
        allowed_group_ids = None  # None means no filtering
    else:
        account_groups = AccountGroups.objects.all()
        allowed_group_ids = None  # None means no filtering

    start_date = end_date = None
    try:
        if start_str:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        if end_str:
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        start_date = end_date = None

    date_filter = Q()
    if start_date:
        date_filter &= Q(journalentry__journal_header__entry_date__gte=start_date)
    if end_date:
        date_filter &= Q(journalentry__journal_header__entry_date__lte=end_date)

    accounts_qs = ChartOfAccounts.objects.annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    ).order_by('group_name__id', 'account_code')

    # Filter by allowed account groups
    if allowed_group_ids is not None:
        accounts_qs = accounts_qs.filter(group_name_id__in=allowed_group_ids)

    ledger_rows = []
    total_debit = 0
    total_credit = 0

    for acc in accounts_qs:
        debit = float(acc.total_debit or 0)
        credit = float(acc.total_credit or 0)
        balance = debit - credit
        ledger_rows.append({
            'account': acc,
            'debit': debit,
            'credit': credit,
            'balance': balance,
        })
        total_debit += debit
        total_credit += credit

    # Group ledger rows by account group
    grouped_ledger = {}
    for row in ledger_rows:
        group_id = row['account'].group_name_id if row['account'].group_name_id else None
        group_name = row['account'].group_name.group_name if row['account'].group_name else 'Unassigned'
        
        if group_id not in grouped_ledger:
            grouped_ledger[group_id] = {
                'group_name': group_name,
                'entries': [],
                'debit': 0,
                'credit': 0,
                'balance': 0,
            }
        
        grouped_ledger[group_id]['entries'].append(row)
        grouped_ledger[group_id]['debit'] += row['debit']
        grouped_ledger[group_id]['credit'] += row['credit']
        grouped_ledger[group_id]['balance'] += row['balance']

    context = {
        'general_ledger': ledger_rows,
        'grouped_ledger': grouped_ledger,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'ending_balance': total_debit - total_credit,
        'start_date': start_str,
        'end_date': end_str,
        'account_groups': account_groups,
        'date_now': formatted_date_time,
    }

    html = render_to_string('Front_End/ledger_pdf.html', context)

    if pisa is None:
        return HttpResponse('PDF generation library not installed. Install xhtml2pdf.', status=500)

    result = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.BytesIO(html.encode('utf-8')), dest=result)

    if pisa_status.err:
        return HttpResponse('Error generating PDF', status=500)

    response = HttpResponse(result.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="general_ledger.pdf"'
    return response

# Trial Balance Function
def trial_balance(request):
    ledger_entries = JournalEntry.objects.all()

    context = {
    'general_ledger': ledger_entries,   # list of ledger rows
    'total_debit': sum(e.debit for e in ledger_entries),
    'total_credit': sum(e.credit for e in ledger_entries),
    'ending_balance': sum(e.debit - e.credit for e in ledger_entries),
}

    return render(request, "Front_End/balance.html", context)


# Trial Balance PDF
def trial_balance_pdf(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("AccountingSystem:login_view"))

    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')
    group_id = request.GET.get('account_group')

    start_date = end_date = None
    try:
        if start_str:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        if end_str:
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        start_date = end_date = None

    date_filter = Q()
    if start_date:
        date_filter &= Q(journalentry__journal_header__entry_date__gte=start_date)
    if end_date:
        date_filter &= Q(journalentry__journal_header__entry_date__lte=end_date)

    # Filter by student's section if applicable
    group_ids = None
    if hasattr(request.user, 'profile') and request.user.profile.role == 'student':
        user_section = request.user.profile.section
        if user_section:
            # Get account groups from teachers managing this section
            account_groups = get_account_groups_for_section(user_section)
            group_ids = list(account_groups.values_list('id', flat=True))
        else:
            # Student not in a section - return no data
            accounts = []
            total_debit = total_credit = 0.0
            ending_balance = 0.0

    # Build account query
    accounts_query = ChartOfAccounts.objects
    if group_ids is not None:
        accounts_query = accounts_query.filter(group_name_id__in=group_ids)
    
    # Further filter by selected account group if provided
    if group_id:
        try:
            accounts_query = accounts_query.filter(group_name_id=int(group_id))
        except (ValueError, TypeError):
            pass
    
    accounts_qs = accounts_query.annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    ).order_by('account_code')

    accounts = []
    total_debit = 0.0
    total_credit = 0.0

    for acc in accounts_qs:
        td = float(acc.total_debit or 0)
        tc = float(acc.total_credit or 0)
        bal = td - tc
        accounts.append({
            'id': acc.id,
            'code': getattr(acc, 'account_code', ''),
            'name': getattr(acc, 'account_name', ''),
            'total_debit': td,
            'total_credit': tc,
            'balance': bal,
        })
        total_debit += td
        total_credit += tc

    context = {
        'accounts': accounts,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'ending_balance': total_debit - total_credit,
        'start_date': start_str,
        'end_date': end_str,
    }

    html = render_to_string('Front_End/balance_pdf.html', context)

    if pisa is None:
        return HttpResponse('PDF generation library not installed. Install xhtml2pdf.', status=500)

    result = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.BytesIO(html.encode('utf-8')), dest=result)

    if pisa_status.err:
        return HttpResponse('Error generating PDF', status=500)

    response = HttpResponse(result.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="trial_balance.pdf"'
    return response


# Income Statement
def income_statement(request):
    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')
    group_id = request.GET.get('group_id')
    cost_of_sales_str = request.GET.get('cost_of_sales', '0')

    # Parse cost of sales
    try:
        cost_of_sales = float(cost_of_sales_str) if cost_of_sales_str else 0.0
    except (ValueError, TypeError):
        cost_of_sales = 0.0

    start_date = end_date = None
    try:
        if start_str:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        if end_str:
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        start_date = end_date = None

    date_filter = Q()
    if start_date:
        date_filter &= Q(journalentry__journal_header__entry_date__gte=start_date)
    if end_date:
        date_filter &= Q(journalentry__journal_header__entry_date__lte=end_date)

    account_groups = AccountGroups.objects.all().order_by('group_name')
    if hasattr(request.user, 'profile'):
        if request.user.profile.role == 'student':
            user_section = request.user.profile.section
            if user_section:
                # Get account groups from teachers managing this section
                account_groups = get_account_groups_for_section(user_section).order_by('group_name')
            else:
                account_groups = AccountGroups.objects.none()
        elif request.user.profile.role == 'teacher':
            # Teachers can only access their assigned account groups
            account_groups = request.user.profile.account_groups.all().order_by('group_name')

    # Optional filter by Account Group
    group_filter = Q()
    if hasattr(request.user, 'profile') and request.user.profile.role in ['student', 'teacher']:
        group_filter &= Q(group_name__in=account_groups)

    selected_group = None
    if group_id:
        selected_group = account_groups.filter(id=group_id).first()
        if selected_group:
            group_filter &= Q(group_name=selected_group)

    # Revenues: normally credit balances (credit - debit)
    revenue_filter = Q(account_type='Revenue') & group_filter
    revenue_qs = ChartOfAccounts.objects.filter(revenue_filter).annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    ).order_by('account_code')

    # Expenses: normally debit balances (debit - credit)
    expense_filter = Q(account_type='Expenses') & group_filter
    expense_qs = ChartOfAccounts.objects.filter(expense_filter).annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    ).order_by('account_code')

    # Identify Cost of Goods Sold accounts (by name keywords) and compute COGS separately
    cogs_filter = Q(account_type='Expenses') & group_filter
    cogs_qs = ChartOfAccounts.objects.filter(cogs_filter).filter(
        Q(account_name__icontains='cost of goods') | Q(account_name__icontains='cogs')
    ).annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    )

    cogs_ids = [c.id for c in cogs_qs]

    revenues = []
    total_revenues = 0.0
    for acc in revenue_qs:
        amt = float((acc.total_credit or 0) - (acc.total_debit or 0))
        revenues.append({'account': acc, 'amount': amt})
        total_revenues += amt

    expenses = []
    total_expenses = 0.0
    # exclude COGS accounts from the general expenses list to show them separately
    for acc in expense_qs.exclude(id__in=cogs_ids):
        amt = float((acc.total_debit or 0) - (acc.total_credit or 0))
        expenses.append({'account': acc, 'amount': amt})
        total_expenses += amt

    # compute total COGS
    total_cogs = 0.0
    cogs = []
    for acc in cogs_qs:
        amt = float((acc.total_debit or 0) - (acc.total_credit or 0))
        cogs.append({'account': acc, 'amount': amt})
        total_cogs += amt

    # Gross profit (revenues less COGS and cost of sales) and net income (revenues less expenses and COGS)
    net_revenues_after_cost = total_revenues - cost_of_sales
    gross_profit = net_revenues_after_cost - total_cogs
    net_income = net_revenues_after_cost - (total_expenses + total_cogs)

    context = {
        'revenues': revenues,
        'expenses': expenses,
        'total_revenues': total_revenues,
        'net_revenues_after_cost': net_revenues_after_cost,
        'total_expenses': total_expenses,
        'cogs': cogs,
        'total_cogs': total_cogs,
        'gross_profit': gross_profit,
        'net_income': net_income,
        'start_date': start_str,
        'end_date': end_str,
        'account_groups': account_groups,
        'selected_group': selected_group,
        'cost_of_sales': cost_of_sales,
    }

    return render(request, 'Front_End/income_statement.html', context)


# Balance Sheet
def balance_sheet(request):
    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')
    group_id = request.GET.get('group_id')
    cost_of_sales_str = request.GET.get('cost_of_sales', '0')

    # Parse cost of sales
    cost_of_sales = 0.0
    try:
        cost_of_sales = float(cost_of_sales_str) if cost_of_sales_str else 0.0
    except (ValueError, TypeError):
        cost_of_sales = 0.0

    start_date = end_date = None
    try:
        if start_str:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        if end_str:
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        start_date = end_date = None

    date_filter = Q()
    if start_date:
        date_filter &= Q(journalentry__journal_header__entry_date__gte=start_date)
    if end_date:
        date_filter &= Q(journalentry__journal_header__entry_date__lte=end_date)

    account_groups = AccountGroups.objects.all().order_by('group_name')
    if hasattr(request.user, 'profile'):
        if request.user.profile.role == 'student':
            user_section = request.user.profile.section
            if user_section:
                # Get account groups from teachers managing this section
                account_groups = get_account_groups_for_section(user_section).order_by('group_name')
            else:
                account_groups = AccountGroups.objects.none()
        elif request.user.profile.role == 'teacher':
            # Teachers can only access their assigned account groups
            account_groups = request.user.profile.account_groups.all().order_by('group_name')

    # Optional filter by Account Group
    group_filter = Q()
    if hasattr(request.user, 'profile') and request.user.profile.role in ['student', 'teacher']:
        group_filter &= Q(group_name__in=account_groups)

    selected_group = None
    if group_id:
        selected_group = account_groups.filter(id=group_id).first()
        if selected_group:
            group_filter &= Q(group_name=selected_group)

    assets_filter = Q(account_type='Assets') & group_filter
    assets_qs = ChartOfAccounts.objects.filter(assets_filter).annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    ).order_by('account_code')

    liabilities_filter = Q(account_type='Liabilities') & group_filter
    liabilities_qs = ChartOfAccounts.objects.filter(liabilities_filter).annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    ).order_by('account_code')

    equity_filter = Q(account_type='Equity') & group_filter
    equity_qs = ChartOfAccounts.objects.filter(equity_filter).annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    ).order_by('account_code')

    assets = []
    total_assets = 0.0
    for acc in assets_qs:
        amt = float((acc.total_debit or 0) - (acc.total_credit or 0))
        assets.append({'account': acc, 'amount': amt})
        total_assets += amt

    liabilities = []
    total_liabilities = 0.0
    for acc in liabilities_qs:
        amt = float((acc.total_credit or 0) - (acc.total_debit or 0))
        liabilities.append({'account': acc, 'amount': amt})
        total_liabilities += amt

    equity = []
    total_equity = 0.0
    for acc in equity_qs:
        amt = float((acc.total_credit or 0) - (acc.total_debit or 0))
        equity.append({'account': acc, 'amount': amt})
        total_equity += amt

    # include current period net income in equity as retained earnings
    # compute revenues and expenses similarly
    revenue_sum = 0.0
    exp_sum = 0.0
    rev_filter = Q(account_type='Revenue') & group_filter
    rev_qs = ChartOfAccounts.objects.filter(rev_filter).annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    )
    for a in rev_qs:
        revenue_sum += float((a.total_credit or 0) - (a.total_debit or 0))

    exp_filter = Q(account_type='Expenses') & group_filter
    exp_qs = ChartOfAccounts.objects.filter(exp_filter).annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    )
    for a in exp_qs:
        exp_sum += float((a.total_debit or 0) - (a.total_credit or 0))

    net_income = revenue_sum - cost_of_sales - exp_sum

    total_equity_including_ri = total_equity + net_income
    total_liabilities_and_equity = total_liabilities + total_equity_including_ri

    context = {
        'assets': assets,
        'liabilities': liabilities,
        'equity': equity,
        'total_assets': total_assets,
        'total_liabilities': total_liabilities,
        'total_equity': total_equity,
        'net_income': net_income,
        'total_equity_including_ri': total_equity_including_ri,
        'total_liabilities_and_equity': total_liabilities_and_equity,
        'start_date': start_str,
        'end_date': end_str,
        'cost_of_sales': cost_of_sales,
        'account_groups': account_groups,
        'selected_group': selected_group,
    }

    return render(request, 'Front_End/balance_sheet.html', context)

# Individual Accounts Transaction Compilation
def ledger_account_transactions(request, account_id):
    account = get_object_or_404(ChartOfAccounts, pk=account_id)

    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')
    entries = JournalEntry.objects.select_related('journal_header', 'journal_header__user', 'journal_header__user__profile').filter(account=account)
    
    # Filter based on user role
    user_role = getattr(request.user.profile, 'role', None) if hasattr(request.user, 'profile') else None
    
    if user_role == 'student':
        # Students see only their own journal entries + collaborations
        entries = entries.filter(
            Q(journal_header__user=request.user) | 
            Q(journal_header__collaborators__collaborator=request.user)
        ).distinct()
    elif user_role == 'teacher':
        # Teachers see entries from students in their managed sections + their own + collaborations
        managed_sections = request.user.managed_sections.all()
        if managed_sections.exists():
            entries = entries.filter(
                Q(journal_header__user=request.user) |
                Q(journal_header__collaborators__collaborator=request.user) |
                Q(journal_header__user__profile__role='student', journal_header__user__profile__section__in=managed_sections)
            ).distinct()
        else:
            # Teacher with no sections sees only own entries + collaborations
            entries = entries.filter(
                Q(journal_header__user=request.user) |
                Q(journal_header__collaborators__collaborator=request.user)
            ).distinct()
    # Admin sees all entries (no filtering)
    
    entries = entries.order_by('journal_header__entry_date', 'journal_header__id')

    try:
        if start_str:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            entries = entries.filter(journal_header__entry_date__gte=start_date)
        if end_str:
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
            entries = entries.filter(journal_header__entry_date__lte=end_date)
    except (ValueError, TypeError):
        # ignore invalid dates and do not filter
        pass

    transactions = []
    for e in entries:
        transactions.append({
            'journal_header_id': e.journal_header.id if e.journal_header else None,
            'entry_no': e.journal_header.entry_no if e.journal_header else '',
            'entry_date': e.journal_header.entry_date.isoformat() if e.journal_header and e.journal_header.entry_date else '',
            'description': e.journal_header.journal_description if e.journal_header else '',
            'debit': float(e.debit or 0),
            'credit': float(e.credit or 0),
        })

    return JsonResponse({
        'success': True,
        'account': {
            'id': account.id,
            'code': account.account_code,
            'name': account.account_name,
            'type': account.account_type,
        },
        'transactions': transactions
    })


def _get_ledger_allowed_group_ids_for_user(user):
    """Return list of allowed group IDs for teachers/students; None means unrestricted (admin)."""
    if not hasattr(user, 'profile'):
        return None

    user_profile = user.profile
    if user_profile.role == 'student':
        user_section = user_profile.section
        if user_section:
            account_groups = get_account_groups_for_section(user_section)
            return list(account_groups.values_list('id', flat=True))
        return []

    if user_profile.role == 'admin':
        return None

    user_account_groups = user_profile.account_groups.all()
    return list(user_account_groups.values_list('id', flat=True))


def _next_month_label(month_label):
    year, month = month_label.split('-')
    y = int(year)
    m = int(month) + 1
    if m > 12:
        m = 1
        y += 1
    return f"{y}-{str(m).zfill(2)}"


def _linear_regression_forecast(values, steps):
    if not values or steps <= 0:
        return []

    n = len(values)
    if n == 1:
        return [values[0]] * steps

    sum_x = 0.0
    sum_y = 0.0
    sum_xy = 0.0
    sum_xx = 0.0

    for i, value in enumerate(values):
        x = float(i)
        y = float(value)
        sum_x += x
        sum_y += y
        sum_xy += x * y
        sum_xx += x * x

    denominator = (n * sum_xx) - (sum_x * sum_x)
    slope = 0.0 if denominator == 0 else ((n * sum_xy) - (sum_x * sum_y)) / denominator
    intercept = (sum_y - (slope * sum_x)) / n

    predictions = []
    for i in range(steps):
        x = float(n + i)
        predictions.append((slope * x) + intercept)
    return predictions


@require_http_methods(["GET"])
def ledger_group_forecast(request, group_id):
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Authentication required.'}, status=401)

    group = get_object_or_404(AccountGroups, pk=group_id)

    allowed_group_ids = _get_ledger_allowed_group_ids_for_user(request.user)
    if allowed_group_ids is not None and group_id not in allowed_group_ids:
        return JsonResponse({'success': False, 'error': 'You are not allowed to access this account group.'}, status=403)

    projection_months = request.GET.get('projection_months', '3')
    try:
        projection_months = int(projection_months)
    except (TypeError, ValueError):
        projection_months = 3
    projection_months = max(1, min(projection_months, 12))

    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')

    accounts = list(
        ChartOfAccounts.objects.filter(group_name_id=group_id).order_by('account_code', 'id')
    )

    entries = JournalEntry.objects.select_related(
        'account',
        'journal_header',
        'journal_header__user',
        'journal_header__user__profile'
    ).filter(account__in=accounts)

    user_role = getattr(request.user.profile, 'role', None) if hasattr(request.user, 'profile') else None
    if user_role == 'student':
        entries = entries.filter(
            Q(journal_header__user=request.user) |
            Q(journal_header__collaborators__collaborator=request.user)
        ).distinct()
    elif user_role == 'teacher':
        managed_sections = request.user.managed_sections.all()
        if managed_sections.exists():
            entries = entries.filter(
                Q(journal_header__user=request.user) |
                Q(journal_header__collaborators__collaborator=request.user) |
                Q(journal_header__user__profile__role='student', journal_header__user__profile__section__in=managed_sections)
            ).distinct()
        else:
            entries = entries.filter(
                Q(journal_header__user=request.user) |
                Q(journal_header__collaborators__collaborator=request.user)
            ).distinct()

    try:
        if start_str:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            entries = entries.filter(journal_header__entry_date__gte=start_date)
        if end_str:
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
            entries = entries.filter(journal_header__entry_date__lte=end_date)
    except (ValueError, TypeError):
        pass

    monthly_by_account = {acc.id: {} for acc in accounts}
    all_history_months = set()

    for entry in entries:
        if not entry.journal_header or not entry.journal_header.entry_date:
            continue

        month_label = entry.journal_header.entry_date.strftime('%Y-%m')
        net_value = float(entry.debit or 0) - float(entry.credit or 0)

        if entry.account_id not in monthly_by_account:
            monthly_by_account[entry.account_id] = {}
        monthly_by_account[entry.account_id][month_label] = monthly_by_account[entry.account_id].get(month_label, 0.0) + net_value
        all_history_months.add(month_label)

    history_labels = sorted(list(all_history_months))
    projection_labels = []

    if history_labels:
        current_label = history_labels[-1]
        for _ in range(projection_months):
            current_label = _next_month_label(current_label)
            projection_labels.append(current_label)

    accounts_payload = []
    for acc in accounts:
        account_months = monthly_by_account.get(acc.id, {})
        historical = [round(account_months.get(label, 0.0), 2) for label in history_labels]

        projected = []
        if history_labels:
            projected = [round(value, 2) for value in _linear_regression_forecast(historical, len(projection_labels))]

        projected_by_month = []
        for idx, month in enumerate(projection_labels):
            projected_by_month.append({
                'month': month,
                'value': projected[idx] if idx < len(projected) else 0.0,
            })

        accounts_payload.append({
            'account_id': acc.id,
            'account_code': acc.account_code,
            'account_name': acc.account_name,
            'historical': historical,
            'projected': projected,
            'projected_by_month': projected_by_month,
        })

    return JsonResponse({
        'success': True,
        'group': {
            'id': group.id,
            'name': group.group_name,
        },
        'history_labels': history_labels,
        'projection_labels': projection_labels,
        'labels': history_labels + projection_labels,
        'projection_months': projection_months,
        'has_history': bool(history_labels),
        'accounts': accounts_payload,
    })


# Trial Balance within the General Ledger
def trial_balance_json(request):
    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')
    group_id = request.GET.get('account_group')

    start_date = end_date = None
    try:
        if start_str:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        if end_str:
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        start_date = end_date = None

    # build date filter for annotations
    date_filter = Q()
    if start_date:
        date_filter &= Q(journalentry__journal_header__entry_date__gte=start_date)
    if end_date:
        date_filter &= Q(journalentry__journal_header__entry_date__lte=end_date)

    # Filter by student's section if applicable
    group_ids = None
    if hasattr(request.user, 'profile') and request.user.profile.role == 'student':
        user_section = request.user.profile.section
        if user_section:
            # Get account groups from teachers managing this section
            account_groups = get_account_groups_for_section(user_section)
            group_ids = list(account_groups.values_list('id', flat=True))
        else:
            # Student not in a section - return empty
            return JsonResponse({'success': True, 'start_date': start_str, 'end_date': end_str, 'accounts': []})

    # Start with all accounts or filtered by student's section
    accounts_qs = ChartOfAccounts.objects
    if group_ids is not None:
        accounts_qs = accounts_qs.filter(group_name_id__in=group_ids)
    
    # Further filter by selected account group if provided
    if group_id:
        try:
            accounts_qs = accounts_qs.filter(group_name_id=int(group_id))
        except (ValueError, TypeError):
            pass
    
    accounts_qs = accounts_qs.annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    ).order_by('account_code')

    result = []
    for acc in accounts_qs:
        # get transactions for this account in date range
        tx_qs = JournalEntry.objects.select_related('journal_header').filter(account=acc)
        if start_date:
            tx_qs = tx_qs.filter(journal_header__entry_date__gte=start_date)
        if end_date:
            tx_qs = tx_qs.filter(journal_header__entry_date__lte=end_date)
        tx_qs = tx_qs.order_by('journal_header__entry_date', 'journal_header__id')

        transactions = []
        for e in tx_qs:
            transactions.append({
                'journal_header_id': e.journal_header.id if e.journal_header else None,
                'entry_no': getattr(e.journal_header, 'entry_no', '') if e.journal_header else '',
                'entry_date': e.journal_header.entry_date.isoformat() if e.journal_header and e.journal_header.entry_date else None,
                'description': getattr(e.journal_header, 'journal_description', '') if e.journal_header else '',
                'debit': float(e.debit or 0),
                'credit': float(e.credit or 0),
            })

        result.append({
            'id': acc.id,
            'code': getattr(acc, 'account_code', ''),
            'name': getattr(acc, 'account_name', ''),
            'type': getattr(acc, 'account_type', ''),
            'description': getattr(acc, 'account_description', ''),
            'total_debit': float(acc.total_debit or 0),
            'total_credit': float(acc.total_credit or 0),
            'balance': float((acc.total_debit or 0) - (acc.total_credit or 0)),
            'transactions': transactions,
        })

    return JsonResponse({'success': True, 'start_date': start_str, 'end_date': end_str, 'accounts': result})

# Journal Entries PDF
def journal_pdf(request, id):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("AccountingSystem:login_view"))

    # Check both draft and approved journals, allowing owner, collaborators, admin, or teachers for their students
    header = None
    entries = None
    is_draft = False
    
    user_role = getattr(request.user.profile, 'role', None) if hasattr(request.user, 'profile') else None
    
    # Helper function to check if teacher can access student's journal
    def teacher_can_access(journal_user):
        if user_role != 'teacher':
            return False
        if not hasattr(journal_user, 'profile') or journal_user.profile.role != 'student':
            return False
        student_section = journal_user.profile.section
        if not student_section:
            return False
        managed_sections = request.user.managed_sections.all()
        return student_section in managed_sections
    
    if user_role == 'admin':
        # Admin can view any journal
        try:
            header = JournalHeader.objects.get(pk=id)
            entries = JournalEntry.objects.filter(journal_header=header).select_related('account').order_by('id')
        except JournalHeader.DoesNotExist:
            try:
                header = JournalHeaderDrafts.objects.get(pk=id)
                entries = JournalEntryDrafts.objects.filter(journal_header=header).select_related('account').order_by('id')
                is_draft = True
            except JournalHeaderDrafts.DoesNotExist:
                return HttpResponse('Journal not found', status=404)
    else:
        # Check if user is owner of approved journal
        try:
            header = JournalHeader.objects.get(pk=id, user=request.user)
            entries = JournalEntry.objects.filter(journal_header=header).select_related('account').order_by('id')
        except JournalHeader.DoesNotExist:
            # Check if user is collaborator on approved journal
            try:
                header = JournalHeader.objects.get(pk=id, collaborators__collaborator=request.user)
                entries = JournalEntry.objects.filter(journal_header=header).select_related('account').order_by('id')
            except JournalHeader.DoesNotExist:
                # Check if teacher can access this student's approved journal
                teacher_accessible = False
                if user_role == 'teacher':
                    try:
                        header = JournalHeader.objects.get(pk=id)
                        if teacher_can_access(header.user):
                            entries = JournalEntry.objects.filter(journal_header=header).select_related('account').order_by('id')
                            teacher_accessible = True
                    except JournalHeader.DoesNotExist:
                        pass
                
                if not teacher_accessible:
                    # Check if user is owner of draft journal
                    try:
                        header = JournalHeaderDrafts.objects.get(pk=id, user=request.user)
                        entries = JournalEntryDrafts.objects.filter(journal_header=header).select_related('account').order_by('id')
                        is_draft = True
                    except JournalHeaderDrafts.DoesNotExist:
                        # Check if user is collaborator on draft journal
                        try:
                            header = JournalHeaderDrafts.objects.get(pk=id, collaborators__collaborator=request.user)
                            entries = JournalEntryDrafts.objects.filter(journal_header=header).select_related('account').order_by('id')
                            is_draft = True
                        except JournalHeaderDrafts.DoesNotExist:
                            # Check if teacher can access this student's draft journal
                            if user_role == 'teacher':
                                try:
                                    header = JournalHeaderDrafts.objects.get(pk=id)
                                    if teacher_can_access(header.user):
                                        entries = JournalEntryDrafts.objects.filter(journal_header=header).select_related('account').order_by('id')
                                        is_draft = True
                                    else:
                                        return HttpResponse('Journal not found or you do not have permission to view it', status=404)
                                except JournalHeaderDrafts.DoesNotExist:
                                    return HttpResponse('Journal not found or you do not have permission to view it', status=404)
                            else:
                                return HttpResponse('Journal not found or you do not have permission to view it', status=404)
    
    total_debit = sum((e.debit or 0) for e in entries)
    total_credit = sum((e.credit or 0) for e in entries)

    context = {
        'header': header,
        'entries': entries,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'ending_balance': total_debit - total_credit,
        'is_draft': is_draft,
    }

    html = render_to_string('Front_End/journal_pdf.html', context)

    if pisa is None:
        return HttpResponse('PDF generation library not installed. Install xhtml2pdf.', status=500)

    result = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.BytesIO(html.encode('utf-8')), dest=result)

    if pisa_status.err:
        return HttpResponse('Error generating PDF', status=500)

    filename = f"journal_{header.entry_no or header.id}.pdf"
    response = HttpResponse(result.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


# Income Statement PDF
def income_statement_pdf(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("AccountingSystem:login_view"))

    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')
    group_id = request.GET.get('group_id')
    cost_of_sales_str = request.GET.get('cost_of_sales', '0')

    # Parse cost of sales
    try:
        cost_of_sales = float(cost_of_sales_str) if cost_of_sales_str else 0.0
    except (ValueError, TypeError):
        cost_of_sales = 0.0

    start_date = end_date = None
    try:
        if start_str:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        if end_str:
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        start_date = end_date = None

    date_filter = Q()
    if start_date:
        date_filter &= Q(journalentry__journal_header__entry_date__gte=start_date)
    if end_date:
        date_filter &= Q(journalentry__journal_header__entry_date__lte=end_date)

    account_groups = AccountGroups.objects.all().order_by('group_name')
    if hasattr(request.user, 'profile'):
        if request.user.profile.role == 'student':
            user_section = request.user.profile.section
            if user_section:
                # Get account groups from teachers managing this section
                account_groups = get_account_groups_for_section(user_section).order_by('group_name')
            else:
                account_groups = AccountGroups.objects.none()
        elif request.user.profile.role == 'teacher':
            # Teachers can only access their assigned account groups
            account_groups = request.user.profile.account_groups.all().order_by('group_name')

    # Optional filter by Account Group
    group_filter = Q()
    if hasattr(request.user, 'profile') and request.user.profile.role in ['student', 'teacher']:
        group_filter &= Q(group_name__in=account_groups)

    selected_group = None
    if group_id:
        selected_group = account_groups.filter(id=group_id).first()
        if selected_group:
            group_filter &= Q(group_name=selected_group)

    # Revenues: normally credit balances (credit - debit)
    revenue_filter = Q(account_type='Revenue') & group_filter
    revenue_qs = ChartOfAccounts.objects.filter(revenue_filter).annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    ).order_by('account_code')

    # Expenses: normally debit balances (debit - credit)
    expense_filter = Q(account_type='Expenses') & group_filter
    expense_qs = ChartOfAccounts.objects.filter(expense_filter).annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    ).order_by('account_code')

    revenues = []
    total_revenues = 0.0
    for acc in revenue_qs:
        amt = float((acc.total_credit or 0) - (acc.total_debit or 0))
        revenues.append({'account': acc, 'amount': amt})
        total_revenues += amt

    expenses = []
    total_expenses = 0.0
    for acc in expense_qs:
        amt = float((acc.total_debit or 0) - (acc.total_credit or 0))
        expenses.append({'account': acc, 'amount': amt})
        total_expenses += amt

    # Identify and compute COGS separately (exclude from expenses list)
    cogs_filter = Q(account_type='Expenses') & group_filter
    cogs_qs = ChartOfAccounts.objects.filter(cogs_filter).filter(
        Q(account_name__icontains='cost of goods') | Q(account_name__icontains='cogs')
    ).annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    )
    cogs_ids = [c.id for c in cogs_qs]

    # rebuild expenses excluding COGS
    expenses = []
    total_expenses = 0.0
    for acc in expense_qs.exclude(id__in=cogs_ids):
        amt = float((acc.total_debit or 0) - (acc.total_credit or 0))
        expenses.append({'account': acc, 'amount': amt})
        total_expenses += amt

    cogs = []
    total_cogs = 0.0
    for acc in cogs_qs:
        amt = float((acc.total_debit or 0) - (acc.total_credit or 0))
        cogs.append({'account': acc, 'amount': amt})
        total_cogs += amt

    gross_profit = total_revenues - total_cogs - cost_of_sales
    net_revenues_after_cost = total_revenues - cost_of_sales
    net_income = net_revenues_after_cost - (total_expenses + total_cogs)

    context = {
        'revenues': revenues,
        'expenses': expenses,
        'total_revenues': total_revenues,
        'net_revenues_after_cost': net_revenues_after_cost,
        'total_expenses': total_expenses,
        'cogs': cogs,
        'total_cogs': total_cogs,
        'gross_profit': gross_profit,
        'net_income': net_income,
        'start_date': start_str or '',
        'end_date': end_str or '',
        'account_groups': account_groups,
        'selected_group': selected_group,
        'cost_of_sales': cost_of_sales,
    }

    html = render_to_string('Front_End/income_statement_pdf.html', context)

    if pisa is None:
        return HttpResponse('PDF generation library not installed. Install xhtml2pdf.', status=500)

    result = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.BytesIO(html.encode('utf-8')), dest=result)

    if pisa_status.err:
        return HttpResponse('Error generating PDF', status=500)

    filename = "income_statement.pdf"
    response = HttpResponse(result.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


# Balance Sheet PDF
def balance_sheet_pdf(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("AccountingSystem:login_view"))

    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')
    group_id = request.GET.get('group_id')
    cost_of_sales_str = request.GET.get('cost_of_sales', '0')

    # Parse cost of sales
    cost_of_sales = 0.0
    try:
        cost_of_sales = float(cost_of_sales_str) if cost_of_sales_str else 0.0
    except (ValueError, TypeError):
        cost_of_sales = 0.0

    start_date = end_date = None
    try:
        if start_str:
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
        if end_str:
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        start_date = end_date = None

    date_filter = Q()
    if start_date:
        date_filter &= Q(journalentry__journal_header__entry_date__gte=start_date)
    if end_date:
        date_filter &= Q(journalentry__journal_header__entry_date__lte=end_date)

    account_groups = AccountGroups.objects.all().order_by('group_name')
    if hasattr(request.user, 'profile'):
        if request.user.profile.role == 'student':
            user_section = request.user.profile.section
            if user_section:
                # Get account groups from teachers managing this section
                account_groups = get_account_groups_for_section(user_section).order_by('group_name')
            else:
                account_groups = AccountGroups.objects.none()
        elif request.user.profile.role == 'teacher':
            # Teachers can only access their assigned account groups
            account_groups = request.user.profile.account_groups.all().order_by('group_name')

    # Optional filter by Account Group
    group_filter = Q()
    if hasattr(request.user, 'profile') and request.user.profile.role in ['student', 'teacher']:
        group_filter &= Q(group_name__in=account_groups)

    selected_group = None
    if group_id:
        selected_group = account_groups.filter(id=group_id).first()
        if selected_group:
            group_filter &= Q(group_name=selected_group)

    assets_filter = Q(account_type='Assets') & group_filter
    assets_qs = ChartOfAccounts.objects.filter(assets_filter).annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    ).order_by('account_code')

    liabilities_filter = Q(account_type='Liabilities') & group_filter
    liabilities_qs = ChartOfAccounts.objects.filter(liabilities_filter).annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    ).order_by('account_code')

    equity_filter = Q(account_type='Equity') & group_filter
    equity_qs = ChartOfAccounts.objects.filter(equity_filter).annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    ).order_by('account_code')

    assets = []
    total_assets = 0.0
    for acc in assets_qs:
        amt = float((acc.total_debit or 0) - (acc.total_credit or 0))
        assets.append({'account': acc, 'amount': amt})
        total_assets += amt

    liabilities = []
    total_liabilities = 0.0
    for acc in liabilities_qs:
        amt = float((acc.total_credit or 0) - (acc.total_debit or 0))
        liabilities.append({'account': acc, 'amount': amt})
        total_liabilities += amt

    equity = []
    total_equity = 0.0
    for acc in equity_qs:
        amt = float((acc.total_credit or 0) - (acc.total_debit or 0))
        equity.append({'account': acc, 'amount': amt})
        total_equity += amt

    # include current period net income in equity as retained earnings
    revenue_sum = 0.0
    exp_sum = 0.0
    rev_filter = Q(account_type='Revenue') & group_filter
    rev_qs = ChartOfAccounts.objects.filter(rev_filter).annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    )
    for a in rev_qs:
        revenue_sum += float((a.total_credit or 0) - (a.total_debit or 0))

    exp_filter = Q(account_type='Expenses') & group_filter
    exp_qs = ChartOfAccounts.objects.filter(exp_filter).annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    )
    for a in exp_qs:
        exp_sum += float((a.total_debit or 0) - (a.total_credit or 0))

    net_income = revenue_sum - cost_of_sales - exp_sum
    total_equity_including_ri = total_equity + net_income
    total_liabilities_and_equity = total_liabilities + total_equity_including_ri

    context = {
        'assets': assets,
        'liabilities': liabilities,
        'equity': equity,
        'total_assets': total_assets,
        'total_liabilities': total_liabilities,
        'total_equity': total_equity,
        'net_income': net_income,
        'total_equity_including_ri': total_equity_including_ri,
        'total_liabilities_and_equity': total_liabilities_and_equity,
        'start_date': start_str or '',
        'end_date': end_str or '',
        'cost_of_sales': cost_of_sales,
        'account_groups': account_groups,
        'selected_group': selected_group,
    }

    html = render_to_string('Front_End/balance_sheet_pdf.html', context)

    if pisa is None:
        return HttpResponse('PDF generation library not installed. Install xhtml2pdf.', status=500)

    result = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.BytesIO(html.encode('utf-8')), dest=result)

    if pisa_status.err:
        return HttpResponse('Error generating PDF', status=500)

    filename = "balance_sheet.pdf"
    response = HttpResponse(result.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response

# Messaging Views
def _get_user_section_ids(user):
    """Return section IDs connected to a user based on role."""
    if not getattr(user, 'is_authenticated', False) or not hasattr(user, 'profile'):
        return set()

    role = user.profile.role
    if role == 'student':
        return {user.profile.section_id} if user.profile.section_id else set()

    if role in ('teacher', 'admin'):
        return set(user.managed_sections.values_list('id', flat=True))

    return set()


def _get_connected_users_queryset(user):
    """
    Enforce messaging scope based on handled sections:
    - Teacher/Admin: students in sections they manage, plus all teachers/admins (even without sections).
    - Student: only teachers/admins who manage the student's section.
    - Any user: users they are directly connected to through journal collaboration (draft or approved).
    """
    def _get_journal_collaboration_user_ids(current_user):
        # Approved journals where current user is a collaborator.
        approved_shared_journal_ids = list(
            JournalCollaborator.objects.filter(collaborator=current_user)
            .values_list('journal_header_id', flat=True)
        )

        collaborator_ids = set(
            JournalCollaborator.objects.filter(journal_header__user=current_user)
            .values_list('collaborator_id', flat=True)
        )
        owner_ids = set(
            JournalCollaborator.objects.filter(collaborator=current_user)
            .values_list('journal_header__user_id', flat=True)
        )
        peer_collaborator_ids = set(
            JournalCollaborator.objects.filter(journal_header_id__in=approved_shared_journal_ids)
            .exclude(collaborator=current_user)
            .values_list('collaborator_id', flat=True)
        )

        # Draft journals where current user is a collaborator.
        draft_shared_journal_ids = list(
            JournalDraftCollaborator.objects.filter(collaborator=current_user)
            .values_list('journal_header_id', flat=True)
        )

        draft_collaborator_ids = set(
            JournalDraftCollaborator.objects.filter(journal_header__user=current_user)
            .values_list('collaborator_id', flat=True)
        )
        draft_owner_ids = set(
            JournalDraftCollaborator.objects.filter(collaborator=current_user)
            .values_list('journal_header__user_id', flat=True)
        )
        draft_peer_collaborator_ids = set(
            JournalDraftCollaborator.objects.filter(journal_header_id__in=draft_shared_journal_ids)
            .exclude(collaborator=current_user)
            .values_list('collaborator_id', flat=True)
        )

        allowed_ids = (
            collaborator_ids
            | owner_ids
            | peer_collaborator_ids
            | draft_collaborator_ids
            | draft_owner_ids
            | draft_peer_collaborator_ids
        )
        allowed_ids.discard(current_user.id)
        return allowed_ids

    section_ids = _get_user_section_ids(user)
    role = user.profile.role if hasattr(user, 'profile') else None
    base_queryset = User.objects.none()

    if role == 'admin':
        # Admins can message all users in the system (except themselves).
        base_queryset = User.objects.exclude(id=user.id).distinct()

    elif role == 'teacher':
        # Teachers can always message other teachers/admins,
        # plus students in their managed sections (if any).
        if section_ids:
            base_queryset = User.objects.exclude(id=user.id).filter(
                Q(profile__role='student', profile__section_id__in=section_ids) |
                Q(profile__role__in=['teacher', 'admin'])
            ).distinct()
        else:
            # Teacher with no sections can still message other teachers/admins.
            base_queryset = User.objects.exclude(id=user.id).filter(
                profile__role__in=['teacher', 'admin']
            ).distinct()

    elif role == 'student':
        if not section_ids:
            # Students without a section can message all admins for help
            base_queryset = User.objects.exclude(id=user.id).filter(
                profile__role='admin'
            ).distinct()
        else:
            # Students can message all admins (for administrative help),
            # plus teachers who manage their section,
            # plus journal collaborators handled below.
            base_queryset = User.objects.exclude(id=user.id).filter(
                Q(profile__role='admin') |
                Q(profile__role='teacher', managed_sections__id__in=section_ids)
            ).distinct()

    collaboration_ids = _get_journal_collaboration_user_ids(user)
    allowed_ids = set(base_queryset.values_list('id', flat=True)) | collaboration_ids

    if not allowed_ids:
        return User.objects.none()

    return User.objects.exclude(id=user.id).filter(id__in=allowed_ids).distinct()


@require_http_methods(["GET", "POST"])
def send_message(request):
    """Send a new message to one or more connected users with optional attachments."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)

    def _redirect_to_dashboard():
        if hasattr(request.user, 'profile'):
            role = request.user.profile.role
            if role == 'admin':
                return redirect('AccountingSystem:admin_dashboard')
            if role == 'teacher':
                return redirect('AccountingSystem:teacher_dashboard')
            return redirect('AccountingSystem:student_dashboard')
        return redirect('AccountingSystem:admin_dashboard')

    if request.method == 'POST':
        files = request.FILES.getlist('attachments')

        subject = (request.POST.get('subject') or '').strip()
        content = (request.POST.get('content') or '').strip()

        # Backward compatibility: accept both single and multi recipient payloads.
        selected_recipient_ids = request.POST.getlist('recipients') or request.POST.getlist('recipient')

        if not content and not files:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'Message text or at least one attachment is required.'}, status=400)
            messages.error(request, 'Message text or at least one attachment is required.')
            return _redirect_to_dashboard()

        if not selected_recipient_ids:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'Please select at least one recipient.'}, status=400)
            messages.error(request, 'Please select at least one recipient.')
            return _redirect_to_dashboard()

        try:
            selected_recipient_ids = [int(recipient_id) for recipient_id in selected_recipient_ids if str(recipient_id).strip()]
        except (TypeError, ValueError):
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'Invalid recipient selection.'}, status=400)
            messages.error(request, 'Invalid recipient selection.')
            return _redirect_to_dashboard()

        selected_recipient_ids = list(set(selected_recipient_ids))

        allowed_recipient_ids = set(
            _get_connected_users_queryset(request.user).values_list('id', flat=True)
        )
        valid_recipient_ids = [recipient_id for recipient_id in selected_recipient_ids if recipient_id in allowed_recipient_ids]

        if not valid_recipient_ids:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'Selected recipients are not connected to your sections.'}, status=403)
            messages.error(request, 'You can only message users connected to your sections.')
            return _redirect_to_dashboard()

        created_message_ids = []
        with transaction.atomic():
            recipients = User.objects.filter(id__in=valid_recipient_ids)
            for recipient in recipients:
                message = Message.objects.create(
                    sender=request.user,
                    recipient=recipient,
                    subject=subject,
                    content=content,
                )
                created_message_ids.append(message.id)

                # Duplicate each attachment per recipient message.
                for file in files:
                    if file.size > 0:
                        file.seek(0)
                        attachment = MessageAttachment(
                            message=message,
                            filename=file.name,
                            file_size=file.size,
                        )
                        attachment.file.save(file.name, ContentFile(file.read()), save=True)

        skipped_count = len(selected_recipient_ids) - len(valid_recipient_ids)
        success_message = f'Message sent to {len(valid_recipient_ids)} recipient(s).'
        if skipped_count > 0:
            success_message += f' Skipped {skipped_count} invalid recipient(s).'

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success',
                'message_ids': created_message_ids,
                'message': success_message,
            })

        messages.success(request, success_message)
        return _redirect_to_dashboard()

    form = MessageForm()
    form.fields['recipient'].queryset = _get_connected_users_queryset(request.user)
    return render(request, 'Front_End/send_message.html', {'form': form})

@require_http_methods(["GET"])
def get_messages(request):
    """Get messages for the current user (both sent and received)"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)

    def _serialize_message(msg, message_type):
        attachments = []
        for att in msg.attachments.all():
            attachments.append({
                'id': att.id,
                'filename': att.filename,
                'file_size': att.file_size,
                'url': att.file.url,
                'download_url': reverse('AccountingSystem:download_attachment', kwargs={'attachment_id': att.id})
            })

        return {
            'id': msg.id,
            'sender': msg.sender.get_full_name() or msg.sender.username,
            'sender_id': msg.sender.id,
            'recipient': msg.recipient.get_full_name() or msg.recipient.username,
            'recipient_id': msg.recipient.id,
            'subject': msg.subject or 'No Subject',
            'content': msg.content,
            'created_at': localtime(msg.created_at).strftime('%Y-%m-%d %H:%M'),
            'is_read': msg.is_read,
            'attachments': attachments,
            'type': message_type
        }
    
    connected_user_ids = list(_get_connected_users_queryset(request.user).values_list('id', flat=True))

    # Only include messages with currently connected users
    received = Message.objects.filter(
        recipient=request.user,
        sender_id__in=connected_user_ids,
    ).order_by('-created_at')
    sent = Message.objects.filter(
        sender=request.user,
        recipient_id__in=connected_user_ids,
    ).order_by('-created_at')
    
    received_data = [_serialize_message(msg, 'received') for msg in received]
    sent_data = [_serialize_message(msg, 'sent') for msg in sent]

    # Archive keeps all user-related messages (independent of section changes).
    archive_qs = Message.objects.filter(
        Q(sender=request.user) | Q(recipient=request.user)
    ).order_by('-created_at')
    archive_data = []
    for msg in archive_qs:
        archive_type = 'received' if msg.recipient_id == request.user.id else 'sent'
        archive_data.append(_serialize_message(msg, archive_type))
    
    # Mark messages as read
    received.update(is_read=True)
    
    return JsonResponse({
        'received': received_data,
        'sent': sent_data,
        'archive': archive_data,
        'unread_count': Message.objects.filter(
            recipient=request.user,
            is_read=False,
        ).count()
    })

@require_http_methods(["GET"])
def get_unread_count(request):
    """Get count of unread messages"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    unread_count = Message.objects.filter(
        recipient=request.user,
        is_read=False,
    ).count()
    return JsonResponse({'unread_count': unread_count})

@require_http_methods(["GET"])
def get_dashboard_notifications(request):
    """Return dashboard notification counters for messages and tasks."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)

    unread_messages = Message.objects.filter(
        recipient=request.user,
        is_read=False,
    ).count()

    pending_tasks = TaskAssignment.objects.filter(
        recipient=request.user,
        is_completed=False,
    ).count()

    total_unread = unread_messages + pending_tasks

    latest_unread_messages = Message.objects.filter(
        recipient=request.user,
        is_read=False,
    ).select_related('sender').order_by('-created_at')[:5]

    latest_pending_tasks = TaskAssignment.objects.filter(
        recipient=request.user,
        is_completed=False,
    ).select_related('sender').order_by('-created_at')[:5]

    latest_notifications = []
    for msg in latest_unread_messages:
        latest_notifications.append({
            'type': 'message',
            'label': 'New message',
            'title': msg.sender.get_full_name() or msg.sender.username,
            'subtitle': msg.subject or 'No Subject',
            'created_at': localtime(msg.created_at).strftime('%Y-%m-%d %H:%M'),
            'created_at_epoch': int(msg.created_at.timestamp()),
            'target': 'messages',
        })

    for task in latest_pending_tasks:
        latest_notifications.append({
            'type': 'task',
            'label': 'New task',
            'title': task.title,
            'subtitle': f"From {task.sender.get_full_name() or task.sender.username}",
            'created_at': localtime(task.created_at).strftime('%Y-%m-%d %H:%M'),
            'created_at_epoch': int(task.created_at.timestamp()),
            'target': 'tasks',
        })

    latest_notifications.sort(key=lambda item: item.get('created_at_epoch', 0), reverse=True)
    latest_notifications = latest_notifications[:5]

    return JsonResponse({
        'unread_messages': unread_messages,
        'pending_tasks': pending_tasks,
        'total_unread': total_unread,
        'has_notifications': total_unread > 0,
        'latest_notifications': latest_notifications,
    })

@require_http_methods(["POST"])
def delete_message(request, message_id):
    """Delete a message"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    message = get_object_or_404(Message, id=message_id)
    
    # Only allow sender to delete sent messages or recipient to delete received messages
    if message.sender == request.user or message.recipient == request.user:
        message.delete()
        return JsonResponse({'status': 'success', 'message': 'Message deleted'})
    
    return JsonResponse({'error': 'Permission denied'}, status=403)

@require_http_methods(["GET"])
def download_attachment(request, attachment_id):
    """Download a message attachment"""
    if not request.user.is_authenticated:
        return HttpResponse('Unauthorized', status=401)
    
    attachment = get_object_or_404(MessageAttachment, id=attachment_id)
    message = attachment.message
    
    # Check if user has access
    if message.sender != request.user and message.recipient != request.user:
        return HttpResponse('Forbidden', status=403)

    if not attachment.file or not attachment.file.name:
        return HttpResponse('File not available on site (missing file reference).', status=404)

    if not attachment.file.storage.exists(attachment.file.name):
        return HttpResponse('File not available on site (file not found on server).', status=404)

    attachment.file.open('rb')
    return _build_attachment_response(attachment.file, attachment.filename)

@require_http_methods(["GET"])
def get_users_api(request):
    """Get list of connected users for messaging."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    users = _get_connected_users_queryset(request.user).select_related('profile', 'profile__section').prefetch_related('managed_sections')
    users_list = []
    
    for user in users:
        full_name = f"{user.first_name} {user.last_name}".strip() if user.first_name or user.last_name else user.username
        role = getattr(user.profile, 'role', '') if hasattr(user, 'profile') else ''

        # Students have one section; teacher/admin may handle multiple sections.
        section_names = []
        if role == 'student' and user.profile.section:
            section_names = [user.profile.section.name]
        elif role in ('teacher', 'admin'):
            section_names = list(user.managed_sections.values_list('name', flat=True))

        users_list.append({
            'id': user.id,
            'username': user.username,
            'full_name': full_name,
            'role': role,
            'sections': section_names,
        })
    
    return JsonResponse({'users': users_list})


@role_required(['teacher'])
@require_http_methods(["GET"])
def get_teacher_task_students_api(request):
    """Get students in sections managed by the current teacher for task assignment."""
    managed_section_ids = request.user.managed_sections.values_list('id', flat=True)
    students = User.objects.filter(
        profile__role='student',
        profile__section_id__in=managed_section_ids,
    ).select_related('profile', 'profile__section').order_by('last_name', 'first_name', 'username')

    student_list = []
    for student in students:
        full_name = f"{student.first_name} {student.last_name}".strip() or student.username
        student_list.append({
            'id': student.id,
            'username': student.username,
            'full_name': full_name,
            'section': student.profile.section.name if student.profile.section else '',
        })

    return JsonResponse({'students': student_list})


@role_required(['teacher'])
@require_http_methods(["POST"])
def send_task(request):
    """Send a task with deadline to one or more students managed by the teacher."""
    files = request.FILES.getlist('attachments')

    title = (request.POST.get('title') or '').strip()
    description = (request.POST.get('description') or '').strip()
    deadline_raw = (request.POST.get('deadline') or '').strip()
    selected_recipient_ids = request.POST.getlist('recipients')

    if not title:
        return JsonResponse({'error': 'Task title is required.'}, status=400)
    if not description:
        return JsonResponse({'error': 'Task description is required.'}, status=400)
    if not deadline_raw:
        return JsonResponse({'error': 'Deadline is required.'}, status=400)
    if not selected_recipient_ids:
        return JsonResponse({'error': 'Please select at least one student.'}, status=400)

    parsed_deadline = None
    for deadline_format in ('%Y-%m-%dT%H:%M', '%Y-%m-%d'):
        try:
            parsed_deadline = datetime.strptime(deadline_raw, deadline_format)
            break
        except ValueError:
            continue

    if parsed_deadline is None:
        return JsonResponse({'error': 'Invalid deadline format.'}, status=400)

    if timezone.is_naive(parsed_deadline):
        deadline = timezone.make_aware(parsed_deadline, timezone.get_current_timezone())
    else:
        deadline = parsed_deadline

    if deadline <= timezone.now():
        return JsonResponse({'error': 'Deadline cannot be in the past.'}, status=400)

    try:
        selected_recipient_ids = [int(recipient_id) for recipient_id in selected_recipient_ids if str(recipient_id).strip()]
    except (TypeError, ValueError):
        return JsonResponse({'error': 'Invalid student selection.'}, status=400)

    selected_recipient_ids = list(set(selected_recipient_ids))

    managed_section_ids = request.user.managed_sections.values_list('id', flat=True)
    valid_recipient_ids = list(
        User.objects.filter(
            id__in=selected_recipient_ids,
            profile__role='student',
            profile__section_id__in=managed_section_ids,
        ).values_list('id', flat=True)
    )

    if not valid_recipient_ids:
        return JsonResponse({'error': 'Selected students are not under your managed sections.'}, status=403)

    created_task_ids = []
    batch_key = uuid4().hex
    with transaction.atomic():
        recipients = User.objects.filter(id__in=valid_recipient_ids)
        for recipient in recipients:
            task = TaskAssignment.objects.create(
                sender=request.user,
                recipient=recipient,
                batch_key=batch_key,
                title=title,
                description=description,
                deadline=deadline,
            )
            created_task_ids.append(task.id)

            for file in files:
                if file.size > 0:
                    file.seek(0)
                    attachment = TaskAttachment(
                        task=task,
                        filename=file.name,
                        file_size=file.size,
                    )
                    attachment.file.save(file.name, ContentFile(file.read()), save=True)

    skipped_count = len(selected_recipient_ids) - len(valid_recipient_ids)
    success_message = f'Task sent to {len(valid_recipient_ids)} student(s).'
    if skipped_count > 0:
        success_message += f' Skipped {skipped_count} invalid student(s).'

    return JsonResponse({
        'status': 'success',
        'task_ids': created_task_ids,
        'message': success_message,
    })


@require_http_methods(["GET"])
def get_tasks(request):
    """Get tasks for current user (sent and received)."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)

    block_unsubmit_after_deadline = bool(getattr(settings, 'TASK_BLOCK_UNSUBMIT_AFTER_DEADLINE', False))
    allow_late_submission = bool(getattr(settings, 'TASK_ALLOW_LATE_SUBMISSION', False))

    def _serialize_task(task, task_type):
        attachments = []
        for att in task.attachments.all():
            attachments.append({
                'id': att.id,
                'filename': att.filename,
                'file_size': att.file_size,
                'url': att.file.url,
                'download_url': reverse('AccountingSystem:download_task_attachment', kwargs={'attachment_id': att.id})
            })

        submission_payload = None
        try:
            submission = task.submission
            submission_attachments = []
            for submission_attachment in submission.attachments.all():
                submission_attachments.append({
                    'id': submission_attachment.id,
                    'filename': submission_attachment.filename,
                    'file_size': submission_attachment.file_size,
                    'url': submission_attachment.file.url,
                    'download_url': reverse(
                        'AccountingSystem:download_task_submission_attachment',
                        kwargs={'attachment_id': submission_attachment.id}
                    )
                })

            submission_payload = {
                'submitted_by': submission.submitted_by.get_full_name() or submission.submitted_by.username,
                'submitted_by_id': submission.submitted_by_id,
                'submitted_at': localtime(submission.submitted_at).strftime('%Y-%m-%d %H:%M'),
                'comment': submission.comment or '',
                'attachments': submission_attachments,
            }
        except TaskSubmission.DoesNotExist:
            submission_payload = None

        deadline_local = localtime(task.deadline)
        is_deadline_passed = task.deadline < timezone.now()
        has_submission = submission_payload is not None
        unsubmit_blocked_by_deadline = bool(block_unsubmit_after_deadline and is_deadline_passed)

        return {
            'id': task.id,
            'batch_key': task.batch_key or f'legacy-{task.id}',
            'sender': task.sender.get_full_name() or task.sender.username,
            'sender_id': task.sender.id,
            'recipient': task.recipient.get_full_name() or task.recipient.username,
            'recipient_id': task.recipient.id,
            'title': task.title,
            'description': task.description,
            'deadline': deadline_local.strftime('%Y-%m-%d %H:%M'),
            'deadline_date': deadline_local.strftime('%Y-%m-%d'),
            'deadline_iso': deadline_local.strftime('%Y-%m-%dT%H:%M'),
            'created_at': localtime(task.created_at).strftime('%Y-%m-%d %H:%M'),
            'is_completed': task.is_completed,
            'is_deadline_passed': is_deadline_passed,
            'is_overdue': (not task.is_completed) and is_deadline_passed,
            'allow_late_submission': allow_late_submission,
            'submission_closed_by_deadline': bool(is_deadline_passed and not allow_late_submission),
            'can_submit_now': bool((not has_submission) and (allow_late_submission or not is_deadline_passed)),
            'attachments': attachments,
            'has_submission': has_submission,
            'submission': submission_payload,
            'block_unsubmit_after_deadline': block_unsubmit_after_deadline,
            'unsubmit_blocked_by_deadline': unsubmit_blocked_by_deadline,
            'can_unsubmit': bool(has_submission and not unsubmit_blocked_by_deadline),
            'type': task_type,
        }

    def _serialize_sent_task_group(tasks):
        representative_task = tasks[0]
        representative_payload = _serialize_task(representative_task, 'sent')

        recipients = []
        submitted_count = 0
        for grouped_task in tasks:
            submitted = hasattr(grouped_task, 'submission')
            if submitted:
                submitted_count += 1

            submission_attachments = []
            if submitted:
                for submission_attachment in grouped_task.submission.attachments.all():
                    submission_attachments.append({
                        'id': submission_attachment.id,
                        'filename': submission_attachment.filename,
                        'file_size': submission_attachment.file_size,
                        'download_url': reverse(
                            'AccountingSystem:download_task_submission_attachment',
                            kwargs={'attachment_id': submission_attachment.id}
                        )
                    })

            recipients.append({
                'task_id': grouped_task.id,
                'student_name': grouped_task.recipient.get_full_name() or grouped_task.recipient.username,
                'student_id': grouped_task.recipient_id,
                'is_submitted': submitted,
                'submitted_at': localtime(grouped_task.submission.submitted_at).strftime('%Y-%m-%d %H:%M') if submitted else '',
                'submission_comment': grouped_task.submission.comment if submitted and grouped_task.submission.comment else '',
                'submission_attachments': submission_attachments,
            })

        representative_payload.update({
            'id': representative_task.id,
            'batch_key': representative_task.batch_key or f'legacy-{representative_task.id}',
            'recipient': f'{len(recipients)} student(s)',
            'recipients': recipients,
            'recipient_count': len(recipients),
            'submitted_count': submitted_count,
            'pending_count': len(recipients) - submitted_count,
            'all_submitted': len(recipients) > 0 and submitted_count == len(recipients),
        })
        return representative_payload

    received = TaskAssignment.objects.filter(recipient=request.user).order_by('-created_at')
    sent = TaskAssignment.objects.filter(sender=request.user).order_by('-created_at')

    grouped_sent = []
    sent_groups = {}
    for task in sent:
        group_key = task.batch_key or f'legacy-{task.id}'
        if group_key not in sent_groups:
            sent_groups[group_key] = []
            grouped_sent.append(group_key)
        sent_groups[group_key].append(task)

    return JsonResponse({
        'received': [_serialize_task(task, 'received') for task in received],
        'sent': [_serialize_sent_task_group(sent_groups[group_key]) for group_key in grouped_sent],
    })


@role_required(['student'])
@require_http_methods(["POST"])
def submit_task(request, task_id):
    """Submit student work for a received task and mark it completed."""
    task = get_object_or_404(TaskAssignment, id=task_id, recipient=request.user)

    allow_late_submission = bool(getattr(settings, 'TASK_ALLOW_LATE_SUBMISSION', False))
    if (not allow_late_submission) and task.deadline <= timezone.now():
        return JsonResponse({'error': 'Cannot submit because the deadline has passed.'}, status=400)

    if hasattr(task, 'submission'):
        return JsonResponse({'error': 'You have already submitted this task.'}, status=400)

    submission_files = request.FILES.getlist('submission_files')
    comment = (request.POST.get('comment') or '').strip()

    if not submission_files:
        return JsonResponse({'error': 'Please attach at least one file before turning in.'}, status=400)

    with transaction.atomic():
        submission = TaskSubmission.objects.create(
            task=task,
            submitted_by=request.user,
            comment=comment,
        )

        for file in submission_files:
            if file.size > 0:
                file.seek(0)
                attachment = TaskSubmissionAttachment(
                    submission=submission,
                    filename=file.name,
                    file_size=file.size,
                )
                attachment.file.save(file.name, ContentFile(file.read()), save=True)

        task.is_completed = True
        task.save(update_fields=['is_completed', 'updated_at'])

    return JsonResponse({
        'status': 'success',
        'message': 'Task submitted successfully.',
        'submitted_at': localtime(submission.submitted_at).strftime('%Y-%m-%d %H:%M'),
    })


@role_required(['student'])
@require_http_methods(["POST"])
def unsubmit_task(request, task_id):
    """Remove a student's submission and reopen the task."""
    task = get_object_or_404(TaskAssignment, id=task_id, recipient=request.user)

    block_unsubmit_after_deadline = bool(getattr(settings, 'TASK_BLOCK_UNSUBMIT_AFTER_DEADLINE', False))
    if block_unsubmit_after_deadline and task.deadline < timezone.now():
        return JsonResponse({'error': 'Cannot unsubmit after the deadline has passed.'}, status=400)

    try:
        submission = task.submission
    except TaskSubmission.DoesNotExist:
        return JsonResponse({'error': 'No submission found for this task.'}, status=400)

    with transaction.atomic():
        submission.delete()
        task.is_completed = False
        task.save(update_fields=['is_completed', 'updated_at'])

    return JsonResponse({
        'status': 'success',
        'message': 'Submission removed. You can submit again.',
    })


@require_http_methods(["POST"])
def delete_task(request, task_id):
    """Delete a task if user is sender or recipient."""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)

    task = get_object_or_404(TaskAssignment, id=task_id)
    if task.sender_id != request.user.id and task.recipient_id != request.user.id:
        return JsonResponse({'error': 'Permission denied'}, status=403)

    if task.sender_id == request.user.id and task.batch_key:
        deleted_count, _ = TaskAssignment.objects.filter(sender=request.user, batch_key=task.batch_key).delete()
        return JsonResponse({'status': 'success', 'message': f'Task batch deleted ({deleted_count} record(s) removed).'})

    task.delete()
    return JsonResponse({'status': 'success', 'message': 'Task deleted'})


@require_http_methods(["GET"])
def download_task_attachment(request, attachment_id):
    """Download a task attachment."""
    if not request.user.is_authenticated:
        return HttpResponse('Unauthorized', status=401)

    attachment = get_object_or_404(TaskAttachment, id=attachment_id)
    task = attachment.task

    if task.sender_id != request.user.id and task.recipient_id != request.user.id:
        return HttpResponse('Forbidden', status=403)

    if not attachment.file or not attachment.file.name:
        return HttpResponse('File not available on site (missing file reference).', status=404)

    if not attachment.file.storage.exists(attachment.file.name):
        return HttpResponse('File not available on site (file not found on server).', status=404)

    attachment.file.open('rb')
    return _build_attachment_response(attachment.file, attachment.filename)


@require_http_methods(["GET"])
def download_task_submission_attachment(request, attachment_id):
    """Download a task submission attachment."""
    if not request.user.is_authenticated:
        return HttpResponse('Unauthorized', status=401)

    attachment = get_object_or_404(TaskSubmissionAttachment, id=attachment_id)
    task = attachment.submission.task

    if task.sender_id != request.user.id and task.recipient_id != request.user.id:
        return HttpResponse('Forbidden', status=403)

    if not attachment.file or not attachment.file.name:
        return HttpResponse('File not available on site (missing file reference).', status=404)

    if not attachment.file.storage.exists(attachment.file.name):
        return HttpResponse('File not available on site (file not found on server).', status=404)

    attachment.file.open('rb')
    return _build_attachment_response(attachment.file, attachment.filename)
