from django.http import HttpResponseRedirect, JsonResponse, Http404
from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import localtime, localdate
from .models import USN_Accounts, AccountGroups, Accounts, ChartOfAccounts, JournalHeaderDrafts, JournalEntryDrafts, JournalHeader, JournalEntry, Message, MessageAttachment
from django.contrib.auth import authenticate, login, logout
from .forms import USNAccountsForm, ChartOfAccountsForm, UpdateAccountsForm, UserCreationForm, MessageForm, MessageAttachmentForm
from itertools import zip_longest
from django.db.models import Sum, RestrictedError, Q, Value, DecimalField
from django.db.models.functions import Coalesce
from django.db import transaction
from django.contrib import messages
from django.core.serializers.json import DjangoJSONEncoder
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import check_password
from django.contrib.auth.models import User
from django.core.cache import cache
import json
from datetime import datetime
from decimal import Decimal
from .decorators import role_required
import io
from django.template.loader import render_to_string
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
import os
from django.core.mail import send_mail
from django.conf import settings
import random, string
# pyright: ignore[reportMissingImports]
try:
    from xhtml2pdf import pisa
except Exception:
    pisa = None

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

        # use a normalized username for counting/lockout (case-insensitive + trimmed)
        norm_username = username.lower()

        attempts_key, lockout_key = get_cache_keys(norm_username)

        # If locked out, inform user and stop before authenticate()
        if cache.get(lockout_key):
            messages.error(request, "Account locked due to multiple failed login attempts. Try again later.")
            return render(request, "Front_End/login.html")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            # Successful login -> clear counters and proceed
            cache.delete(attempts_key)
            cache.delete(lockout_key)
            login(request, user)

            # Ensure every user has a profile (defaults to student)
            from .models import UserProfile
            if not hasattr(user, "profile"):
                UserProfile.objects.create(user=user, role='student')

            messages.success(request, "Login Successful")
            role = getattr(user, "profile", None).role if getattr(user, "profile", None) else ('admin' if user.is_superuser else 'student')
            if role == "admin":
                return redirect("AccountingSystem:admin_dashboard")
            if role == "teacher":
                return redirect("AccountingSystem:teacher_dashboard")
            return redirect("AccountingSystem:student_dashboard")
        else:
            # Failed login -> increment attempts (use normalized key)
            attempts = cache.get(attempts_key, 0) + 1
            cache.set(attempts_key, attempts, ATTEMPT_WINDOW)

            remaining = MAX_ATTEMPTS - attempts
            if remaining <= 0:
                cache.set(lockout_key, True, LOCKOUT_TIME)
                cache.delete(attempts_key)
                messages.error(request, f"Too many failed attempts. Account locked for {int(LOCKOUT_TIME/60)} minutes.")
            else:
                messages.error(request, f"Invalid credentials. {remaining} attempt(s) left.")

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

    # generate temporary password
    temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))

    subject = 'Temporary Password - ACLC Accounting System'
    message = (
        f"Hello {user.username},\n\nA temporary password has been generated for your account:\n\n"
        f"{temp_password}\n\nPlease login and change your password immediately.\n\nIf you did not request this, contact support."
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
    messages.success(request, f'A temporary password has been sent to {user.email}.')
    return redirect('AccountingSystem:login_view')

# Admin Home Page
@role_required(['admin'])
def admin_dashboard(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("AccountingSystem:login_view"))
    
    total_accounts = ChartOfAccounts.objects.count()
    total_journals = JournalHeader.objects.filter(user=request.user).count() if not request.user.is_superuser else JournalHeader.objects.count()
    total_entries = JournalEntry.objects.count()
    users = User.objects.all()
    received_messages = Message.objects.filter(recipient=request.user).order_by('-created_at')
    sent_messages = Message.objects.filter(sender=request.user).order_by('-created_at')

    context = {
        'total_accounts': total_accounts,
        'total_journals': total_journals,
        'total_entries': total_entries,
        'users': users,
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
    users = User.objects.all()
    received_messages = Message.objects.filter(recipient=request.user).order_by('-created_at')
    sent_messages = Message.objects.filter(sender=request.user).order_by('-created_at')

    context = {
        'total_accounts': total_accounts,
        'total_journals': total_journals,
        'total_entries': total_entries,
        'users': users,
        'received_messages': received_messages,
        'sent_messages': sent_messages,
    }
    return render(request, "Front_End/teacher_dashboard.html", context)

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

    context = {
        'total_accounts': total_accounts,
        'total_journals': total_journals,
        'total_entries': total_entries,
        'users': users,
        'received_messages': received_messages,
        'sent_messages': sent_messages,
    }
    return render(request, "Front_End/student_dashboard.html", context)

def forbidden(request):
    return render(request, "Front_End/forbidden.html", status=403)

# Chart Of Accounts Page
def chart_of_accounts(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("AccountingSystem:login_view"))

    account_groups = AccountGroups.objects.all()
    results = ChartOfAccounts.objects.all()
    results = ChartOfAccounts.objects.order_by('-date_created', '-id')
    return render(request, "Front_End/accounts.html", {
        "account_groups": account_groups,
        "accounts" : results
    })

# Student COA Page
def chart_of_accounts_students(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("AccountingSystem:login_view"))

    account_groups = AccountGroups.objects.all()
    results = ChartOfAccounts.objects.all()
    results = ChartOfAccounts.objects.order_by('-date_created', '-id')
    return render(request, "Front_End/accounts_students.html", {
        "account_groups": account_groups,
        "accounts" : results
    })

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
    account_code_submit = request.POST['account_code']
    account_name_submit = request.POST['account_name']
    account_type_submit = request.POST['account_type']
    account_description_submit = request.POST['account_description']
    account_group_id = request.POST.get('account_group')  # may be '' when "All Groups" selected

     # Validate required fields
    if not account_name_submit:
        messages.error(request, "Account name is required.")
        return HttpResponseRedirect(reverse("AccountingSystem:accounts"))

    # Check uniqueness (case-insensitive)
    if ChartOfAccounts.objects.filter(account_name__iexact=account_name_submit).exists():
        messages.error(request, f'Account "{account_name_submit}" already exists.')
        return HttpResponseRedirect(reverse("AccountingSystem:accounts"))


    # convert posted group id to FK id (use _id to assign directly) and handle empty selection
    group_id = int(account_group_id) if account_group_id not in (None, '') else None

    account = ChartOfAccounts(
        account_code = account_code_submit,
        account_name = account_name_submit,
        account_type = account_type_submit,
        account_description = account_description_submit,
        group_name_id = group_id,
    )
    account.save()

    return HttpResponseRedirect(reverse("AccountingSystem:accounts"))

# Update Account Function to Backend
def update_account(request, id):
    selected_account = ChartOfAccounts.objects.get(pk=id)
    if request.method == "POST":
        selected_account.account_name = request.POST.get("account_name", selected_account.account_name)
        selected_account.account_description = request.POST.get("account_description", selected_account.account_description)
        selected_account.save()
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
def create_user(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()

            # Update user profile with role (created by signal)
            profile = user.profile
            profile.role = form.cleaned_data['role']
            profile.save()

            messages.success(request, f'User "{user.username}" created successfully.')
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
            user.set_password(form.cleaned_data['password'])
            user.save()

            # Update user profile with role (created by signal)
            profile = user.profile
            profile.role = form.cleaned_data['role']
            profile.save()

            messages.success(request, f'User "{user.username}" created successfully.')
            return HttpResponseRedirect(reverse("AccountingSystem:teacher_dashboard"))
        else:
            for error in form.errors.values():
                messages.error(request, error)
            return HttpResponseRedirect(reverse("AccountingSystem:teacher_dashboard"))

    return HttpResponseRedirect(reverse("AccountingSystem:teacher_dashboard"))

# Journal Entries Page
def journals(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("AccountingSystem:login_view"))
    
    account_groups = AccountGroups.objects.all()
    accounts = ChartOfAccounts.objects.all()
    
    # Fetch approved journals
    journal_entries = JournalEntry.objects.select_related('journal_header', 'account')
    approved_groups = []

    headers = JournalHeader.objects.all()
    # restrict to current user unless administrator/teacher should see all
    if not request.user.is_superuser and getattr(request.user, 'profile', None) and request.user.profile.role == 'student':
        headers = headers.filter(user=request.user)
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
    # restrict to current user unless administrator/teacher should see all
    if not request.user.is_superuser and getattr(request.user, 'profile', None) and request.user.profile.role == 'student':
        draft_headers = draft_headers.filter(user=request.user)
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

    return render(request, 'Front_end/journal.html', {
        'draft_groups': draft_groups,
        'approved_groups': approved_groups,
        'account_groups': account_groups,
        "accounts" : accounts
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

    return render(request, 'Front_end/journal_drafts.html', {
        'journal_groups': journal_drafts_groups,
        'account_groups': account_groups,
        "accounts" : accounts
        })

# Insert Journal Function to Backend
def insert_journals(request):
    if request.method == "POST":
        journal_code = request.POST["journal_code"]
        date_submit = request.POST['entry-date']
        account_group = request.POST["account_group"]
        account_ids = request.POST.getlist('account_name')
        debits = request.POST.getlist('debit')
        credits = request.POST.getlist('credit')
        description = request.POST['journal_description']

        # Creates Journal Header
        header = JournalHeaderDrafts.objects.create(
            entry_no = journal_code,
            entry_date = date_submit,
            journal_description = description,
            group_name = AccountGroups.objects.get(pk=account_group),
            user = request.user,
        ) 
        header.save()

        # Loops through the rows and create Journal Entries
        for i in range(len(account_ids)):
            account_id = account_ids[i]
            debit = debits[i] if i < len(debits) else ''
            credit = credits[i] if i < len(credits) else ''

            # Skip rows with no account or empty amounts
            if not account_id or (debit == '' and credit == ''):
                continue

            try:
                account = ChartOfAccounts.objects.get(pk=account_id)
            except ChartOfAccounts.DoesNotExist:
                continue

            journal_entry = JournalEntryDrafts.objects.create(
                journal_header=header,
                account=account,
                debit=float(debit or 0),
                credit=float(credit or 0)

            )

            journal_entry.save()
        return redirect('AccountingSystem:journals')  # or render success message

    # GET request
    #accounts = ChartOfAccounts.objects.all()
    #return render(request, 'journal_form.html', {'accounts': accounts})

# Update Journal Entry
def update_journal(request, id):
    # retrieve header only if user owns it or is superuser
    if request.user.is_superuser:
        header = get_object_or_404(JournalHeader, pk=id)
    else:
        header = get_object_or_404(JournalHeader, pk=id, user=request.user)

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

    # perform update inside transaction
    with transaction.atomic():
        # update header
        if entry_date:
            header.entry_date = entry_date
        header.journal_description = description or header.description
        header.save()

        # remove existing entries
        JournalEntry.objects.filter(journal_header=header).delete()

        # recreate entries
        for i, acc_val in enumerate(account_values):
            # get amounts for this row
            debit = parsed_debits[i] if i < len(parsed_debits) else 0.0
            credit = parsed_credits[i] if i < len(parsed_credits) else 0.0
            # skip empty rows (no account selected) or rows with no amounts
            if not acc_val or (debit == 0 and credit == 0):
                continue

            # try to resolve account by PK first, fallback to name
            account = None
            try:
                account = ChartOfAccounts.objects.get(pk=int(acc_val))
            except (ValueError, ChartOfAccounts.DoesNotExist):
                account = ChartOfAccounts.objects.filter(account_name=acc_val).first()

            # if account still not found, skip
            if not account:
                continue

            JournalEntry.objects.create(
                journal_header=header,
                account=account,
                debit=debit,
                credit=credit
            )

    # respond
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True})
    return redirect(reverse("AccountingSystem:journals"))

# Delete Journal Entry
def delete_journal(request, id):
    try:
        if request.user.is_superuser:
            journal_header = JournalHeader.objects.get(pk=id)
        else:
            journal_header = JournalHeader.objects.get(pk=id, user=request.user)
        journal_header.delete()
    except JournalHeader.DoesNotExist:
        pass
    return redirect("AccountingSystem:journals")

# General Ledger Page
def general_ledger(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("AccountingSystem:login_view"))

    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')

    account_groups = AccountGroups.objects.all()

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
    accounts_summary = ChartOfAccounts.objects.annotate(
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

    account_groups = AccountGroups.objects.all()

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
    response['Content-Disposition'] = 'attachment; filename="general_ledger.pdf"'
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
    response['Content-Disposition'] = 'attachment; filename="trial_balance.pdf"'
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

    # Optional filter by Account Group
    group_filter = Q()
    selected_group = None
    if group_id:
        try:
            selected_group = AccountGroups.objects.get(id=group_id)
            group_filter &= Q(group_name=selected_group)
        except AccountGroups.DoesNotExist:
            selected_group = None

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
        'account_groups': AccountGroups.objects.all().order_by('group_name'),
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

    # Optional filter by Account Group
    group_filter = Q()
    selected_group = None
    if group_id:
        try:
            selected_group = AccountGroups.objects.get(id=group_id)
            group_filter &= Q(group_name=selected_group)
        except AccountGroups.DoesNotExist:
            selected_group = None

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

    context = {
        'assets': assets,
        'liabilities': liabilities,
        'equity': equity,
        'total_assets': total_assets,
        'total_liabilities': total_liabilities,
        'total_equity': total_equity,
        'net_income': net_income,
        'total_equity_including_ri': total_equity_including_ri,
        'start_date': start_str,
        'end_date': end_str,
        'cost_of_sales': cost_of_sales,
        'account_groups': AccountGroups.objects.all().order_by('group_name'),
        'selected_group': selected_group,
    }

    return render(request, 'Front_End/balance_sheet.html', context)

# Individual Accounts Transaction Compilation
def ledger_account_transactions(request, account_id):
    account = get_object_or_404(ChartOfAccounts, pk=account_id)

    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')
    entries = JournalEntry.objects.select_related('journal_header').filter(account=account).order_by('journal_header__entry_date', 'journal_header__id')

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


# Trial Balance within the General Ledger
def trial_balance_json(request):
    start_str = request.GET.get('start_date')
    end_str = request.GET.get('end_date')

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

    accounts_qs = ChartOfAccounts.objects.annotate(
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

    # only allow owner or superuser to view PDF
    if request.user.is_superuser:
        header = get_object_or_404(JournalHeader, pk=id)
    else:
        header = get_object_or_404(JournalHeader, pk=id, user=request.user)
    entries = JournalEntry.objects.filter(journal_header=header).select_related('account').order_by('id')

    total_debit = sum((e.debit or 0) for e in entries)
    total_credit = sum((e.credit or 0) for e in entries)

    context = {
        'header': header,
        'entries': entries,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'ending_balance': total_debit - total_credit,
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
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
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

    # Optional filter by Account Group
    group_filter = Q()
    selected_group = None
    if group_id:
        try:
            selected_group = AccountGroups.objects.get(id=group_id)
            group_filter &= Q(group_name=selected_group)
        except AccountGroups.DoesNotExist:
            selected_group = None

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
        'account_groups': AccountGroups.objects.all().order_by('group_name'),
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
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
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

    # Optional filter by Account Group
    group_filter = Q()
    selected_group = None
    if group_id:
        try:
            selected_group = AccountGroups.objects.get(id=group_id)
            group_filter &= Q(group_name=selected_group)
        except AccountGroups.DoesNotExist:
            selected_group = None

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

    context = {
        'assets': assets,
        'liabilities': liabilities,
        'equity': equity,
        'total_assets': total_assets,
        'total_liabilities': total_liabilities,
        'total_equity': total_equity,
        'net_income': net_income,
        'total_equity_including_ri': total_equity_including_ri,
        'start_date': start_str or '',
        'end_date': end_str or '',
        'cost_of_sales': cost_of_sales,
        'account_groups': AccountGroups.objects.all().order_by('group_name'),
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
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

# Messaging Views
@require_http_methods(["GET", "POST"])
def send_message(request):
    """Send a new message with optional attachments"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    if request.method == 'POST':
        form = MessageForm(request.POST, request.FILES)
        files = request.FILES.getlist('attachments')
        
        if form.is_valid():
            message = form.save(commit=False)
            message.sender = request.user
            message.save()
            
            # Handle file attachments
            for file in files:
                if file.size > 0:
                    attachment = MessageAttachment(
                        message=message,
                        file=file,
                        filename=file.name,
                        file_size=file.size
                    )
                    attachment.save()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'success',
                    'message_id': message.id,
                    'message': 'Message sent successfully'
                })
            # Redirect back to the current dashboard
            if hasattr(request.user, 'profile'):
                role = request.user.profile.role
                if role == 'admin':
                    return redirect('AccountingSystem:admin_dashboard')
                elif role == 'teacher':
                    return redirect('AccountingSystem:teacher_dashboard')
                else:
                    return redirect('AccountingSystem:student_dashboard')
            return redirect('AccountingSystem:admin_dashboard')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'Form invalid', 'errors': form.errors}, status=400)
            # If form is invalid, redirect back with error
            return redirect('AccountingSystem:admin_dashboard')
    
    form = MessageForm()
    form.fields['recipient'].queryset = User.objects.exclude(id=request.user.id)
    return render(request, 'Front_End/send_message.html', {'form': form})

@require_http_methods(["GET"])
def get_messages(request):
    """Get messages for the current user (both sent and received)"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    # Get all messages involving the current user
    received = Message.objects.filter(recipient=request.user).order_by('-created_at')
    sent = Message.objects.filter(sender=request.user).order_by('-created_at')
    
    received_data = []
    for msg in received:
        attachments = []
        for att in msg.attachments.all():
            attachments.append({
                'id': att.id,
                'filename': att.filename,
                'file_size': att.file_size,
                'url': att.file.url
            })
        received_data.append({
            'id': msg.id,
            'sender': msg.sender.get_full_name() or msg.sender.username,
            'sender_id': msg.sender.id,
            'subject': msg.subject or 'No Subject',
            'content': msg.content,
            'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M'),
            'is_read': msg.is_read,
            'attachments': attachments,
            'type': 'received'
        })
    
    sent_data = []
    for msg in sent:
        attachments = []
        for att in msg.attachments.all():
            attachments.append({
                'id': att.id,
                'filename': att.filename,
                'file_size': att.file_size,
                'url': att.file.url
            })
        sent_data.append({
            'id': msg.id,
            'recipient': msg.recipient.get_full_name() or msg.recipient.username,
            'recipient_id': msg.recipient.id,
            'subject': msg.subject or 'No Subject',
            'content': msg.content,
            'created_at': msg.created_at.strftime('%Y-%m-%d %H:%M'),
            'attachments': attachments,
            'type': 'sent'
        })
    
    # Mark messages as read
    received.update(is_read=True)
    
    return JsonResponse({
        'received': received_data,
        'sent': sent_data,
        'unread_count': Message.objects.filter(recipient=request.user, is_read=False).count()
    })

@require_http_methods(["GET"])
def get_unread_count(request):
    """Get count of unread messages"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    unread_count = Message.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'unread_count': unread_count})

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
    
    response = HttpResponse(attachment.file.read(), content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{attachment.filename}"'
    return response

@require_http_methods(["GET"])
def get_users_api(request):
    """Get list of all users (excluding current user) for messaging"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    users = User.objects.exclude(id=request.user.id).values('id', 'username', 'first_name', 'last_name')
    users_list = []
    
    for user in users:
        full_name = f"{user['first_name']} {user['last_name']}".strip() if user['first_name'] or user['last_name'] else user['username']
        users_list.append({
            'id': user['id'],
            'username': user['username'],
            'full_name': full_name
        })
    
    return JsonResponse({'users': users_list})
