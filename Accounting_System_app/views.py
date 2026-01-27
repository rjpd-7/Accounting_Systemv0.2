from django.http import HttpResponseRedirect, JsonResponse, Http404
from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import localtime, localdate
from .models import USN_Accounts, AccountGroups, Accounts, ChartOfAccounts, JournalHeader, JournalEntry
from django.contrib.auth import authenticate, login, logout
from .forms import USNAccountsForm, ChartOfAccountsForm, UpdateAccountsForm
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
    total_journals = JournalHeader.objects.count()
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

# Admin Home Page
@role_required(['admin'])
def admin_dashboard(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("AccountingSystem:login_view"))
    
    total_accounts = ChartOfAccounts.objects.count()
    total_journals = JournalHeader.objects.count()
    total_entries = JournalEntry.objects.count()

    context = {
        'total_accounts': total_accounts,
        'total_journals': total_journals,
        'total_entries': total_entries,
    }
    return render(request, "Front_End/admin_dashboard.html", context)

# Teacher Home Page
@role_required(['teacher'])
def teacher_dashboard(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("AccountingSystem:login_view"))
    
    total_accounts = ChartOfAccounts.objects.count()
    total_journals = JournalHeader.objects.count()
    total_entries = JournalEntry.objects.count()

    context = {
        'total_accounts': total_accounts,
        'total_journals': total_journals,
        'total_entries': total_entries,
    }
    return render(request, "Front_End/teacher_dashboard.html", context)

# Student Home Page
@role_required(['student'])
def student_dashboard(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("AccountingSystem:login_view"))
    
    total_accounts = ChartOfAccounts.objects.count()
    total_journals = JournalHeader.objects.count()
    total_entries = JournalEntry.objects.count()

    context = {
        'total_accounts': total_accounts,
        'total_journals': total_journals,
        'total_entries': total_entries,
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
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        role = request.POST.get('role')

        # Validate required fields
        if not all([first_name, last_name, username, email, password, role]):
            messages.error(request, "All fields are required.")
            return HttpResponseRedirect(reverse("AccountingSystem:admin_dashboard"))

        # Check if username already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" already exists.')
            return HttpResponseRedirect(reverse("AccountingSystem:admin_dashboard"))

        # Check if email already exists
        if User.objects.filter(email=email).exists():
            messages.error(request, f'Email "{email}" already exists.')
            return HttpResponseRedirect(reverse("AccountingSystem:admin_dashboard"))

        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        # Update user profile with role (created by signal)
        from .models import UserProfile
        profile = user.profile
        profile.role = role
        profile.save()

        messages.success(request, f'User "{username}" created successfully.')
        return HttpResponseRedirect(reverse("AccountingSystem:admin_dashboard"))

    return HttpResponseRedirect(reverse("AccountingSystem:admin_dashboard"))

# Create User Function for Teachers
def teacher_create_user(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        role = request.POST.get('role')

        # Validate required fields
        if not all([first_name, last_name, username, email, password, role]):
            messages.error(request, "All fields are required.")
            return HttpResponseRedirect(reverse("AccountingSystem:teacher_dashboard"))

        # Check if username already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, f'Username "{username}" already exists.')
            return HttpResponseRedirect(reverse("AccountingSystem:teacher_dashboard"))

        # Check if email already exists
        if User.objects.filter(email=email).exists():
            messages.error(request, f'Email "{email}" already exists.')
            return HttpResponseRedirect(reverse("AccountingSystem:teacher_dashboard"))

        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        # Update user profile with role (created by signal)
        from .models import UserProfile
        profile = user.profile
        profile.role = role
        profile.save()

        messages.success(request, f'User "{username}" created successfully.')
        return HttpResponseRedirect(reverse("AccountingSystem:teacher_dashboard"))

    return HttpResponseRedirect(reverse("AccountingSystem:teacher_dashboard"))

# Journal Entries Page
def journals(request):
    if not request.user.is_authenticated:
        return HttpResponseRedirect(reverse("AccountingSystem:login_view"))
    
    account_groups = AccountGroups.objects.all()
    accounts = ChartOfAccounts.objects.all()
    journal_entries = JournalEntry.objects.select_related('journal_header', 'account')
    journal_groups = []

    headers = JournalHeader.objects.all()
    headers = JournalHeader.objects.order_by('-journal_date_created', '-id')

    for header in headers:
        entries = journal_entries.filter(journal_header=header)
        totals = entries.aggregate(
            total_debit=Sum('debit'),
            total_credit=Sum('credit')
        )

        journal_groups.append({
            'header': header,
            'entries': entries,
            'total_debit': totals['total_debit'] or 0,
            'total_credit': totals['total_credit'] or 0
        })

    return render(request, 'Front_end/journal.html', {
        'journal_groups': journal_groups,
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
        header = JournalHeader.objects.create(
            entry_no = journal_code,
            entry_date = date_submit,
            journal_description = description,
            group_name = AccountGroups.objects.get(pk=account_group),
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

            journal_entry = JournalEntry.objects.create(
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
    header = get_object_or_404(JournalHeader, pk=id)

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
        journal_header = JournalHeader.objects.get(pk=id)
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

    # Revenues: normally credit balances (credit - debit)
    revenue_qs = ChartOfAccounts.objects.filter(account_type='Revenue').annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    ).order_by('account_code')

    # Expenses: normally debit balances (debit - credit)
    expense_qs = ChartOfAccounts.objects.filter(account_type='Expenses').annotate(
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

    net_income = total_revenues - total_expenses

    context = {
        'revenues': revenues,
        'expenses': expenses,
        'total_revenues': total_revenues,
        'total_expenses': total_expenses,
        'net_income': net_income,
        'start_date': start_str,
        'end_date': end_str,
    }

    return render(request, 'Front_End/income_statement.html', context)


# Balance Sheet
def balance_sheet(request):
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

    assets_qs = ChartOfAccounts.objects.filter(account_type='Assets').annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    ).order_by('account_code')

    liabilities_qs = ChartOfAccounts.objects.filter(account_type='Liabilities').annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    ).order_by('account_code')

    equity_qs = ChartOfAccounts.objects.filter(account_type='Equity').annotate(
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
    rev_qs = ChartOfAccounts.objects.filter(account_type='Revenue').annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    )
    for a in rev_qs:
        revenue_sum += float((a.total_credit or 0) - (a.total_debit or 0))

    exp_qs = ChartOfAccounts.objects.filter(account_type='Expenses').annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    )
    for a in exp_qs:
        exp_sum += float((a.total_debit or 0) - (a.total_credit or 0))

    net_income = revenue_sum - exp_sum

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

    header = get_object_or_404(JournalHeader, pk=id)
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

    # Revenues: normally credit balances (credit - debit)
    revenue_qs = ChartOfAccounts.objects.filter(account_type='Revenue').annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    ).order_by('account_code')

    # Expenses: normally debit balances (debit - credit)
    expense_qs = ChartOfAccounts.objects.filter(account_type='Expenses').annotate(
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

    net_income = total_revenues - total_expenses

    context = {
        'revenues': revenues,
        'expenses': expenses,
        'total_revenues': total_revenues,
        'total_expenses': total_expenses,
        'net_income': net_income,
        'start_date': start_str or '',
        'end_date': end_str or '',
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

    assets_qs = ChartOfAccounts.objects.filter(account_type='Assets').annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    ).order_by('account_code')

    liabilities_qs = ChartOfAccounts.objects.filter(account_type='Liabilities').annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    ).order_by('account_code')

    equity_qs = ChartOfAccounts.objects.filter(account_type='Equity').annotate(
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
    rev_qs = ChartOfAccounts.objects.filter(account_type='Revenue').annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    )
    for a in rev_qs:
        revenue_sum += float((a.total_credit or 0) - (a.total_debit or 0))

    exp_qs = ChartOfAccounts.objects.filter(account_type='Expenses').annotate(
        total_debit=Coalesce(Sum('journalentry__debit', filter=date_filter), Value(0), output_field=DecimalField()),
        total_credit=Coalesce(Sum('journalentry__credit', filter=date_filter), Value(0), output_field=DecimalField()),
    )
    for a in exp_qs:
        exp_sum += float((a.total_debit or 0) - (a.total_credit or 0))

    net_income = revenue_sum - exp_sum
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
