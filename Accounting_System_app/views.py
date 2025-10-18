from django.http import HttpResponseRedirect, JsonResponse, Http404
from django import forms
from django.shortcuts import render, redirect
from django.urls import reverse
from .models import USN_Accounts, AccountGroups, Accounts, ChartOfAccounts, JournalHeader, JournalEntry
from django.contrib.auth import authenticate, login, logout
from .forms import USNAccountsForm, ChartOfAccountsForm, UpdateAccountsForm
from itertools import zip_longest
from django.db.models import Sum, RestrictedError
from django.contrib import messages

# Create your views here.

# Home Page
def index(request):

    return render(request, "Front_end/index.html")

# Login Page
def login_view(request):
    
    return render(request, "Front_End/login.html")

# Directs to Login Page once logged out.
def logout_view(request):
    
    return render(request, "Front_End/login.html")

# Chart Of Accounts Page
def chart_of_accounts(request):
    results = ChartOfAccounts.objects.all()
    return render(request, "Front_End/accounts.html", {
        "accounts" : results
    })

# Create Account Function to Backend
def create_account(request):
    account_code_submit = request.POST['account_code']
    account_name_submit = request.POST['account_name']
    account_type_submit = request.POST['account_type']
    account_description_submit = request.POST['account_description']
    account = ChartOfAccounts(
        account_code = account_code_submit, 
        account_name = account_name_submit, 
        account_type = account_type_submit, 
        account_description = account_description_submit
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
        messages.error(request, "Cannot delete this account because it is linked to journal entries.")
    
    except ChartOfAccounts.DoesNotExist:
        messages.error(request, "Account not found")
    return redirect("AccountingSystem:accounts")

# Journal Entries Page
def journals(request):
    accounts = ChartOfAccounts.objects.all()
    journal_entries = JournalEntry.objects.select_related('journal_header', 'account')
    journal_groups = []

    headers = JournalHeader.objects.all()

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
        "accounts" : accounts
        })

# Insert Journal Function to Backend
def insert_journals(request):
    if request.method == "POST":
        journal_code = request.POST["journal_code"]
        date_submit = request.POST['entry-date']
        account_ids = request.POST.getlist('account_name')
        debits = request.POST.getlist('debit')
        credits = request.POST.getlist('credit')
        description = request.POST['journal_description']

        # Creates Journal Header
        header = JournalHeader.objects.create(
            entry_no = journal_code,
            entry_date = date_submit,
            journal_description = description,
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

# Get Journal Details
def get_journal_details(request, header_id):
    try:
        header = JournalHeader.objects.get(id=header_id)
    except JournalHeader.DoesNotExist:
        raise Http404("Journal not found")

    entries = JournalEntry.objects.filter(journal_header=header)

    data = {
        "id": header.id,
        "journal_code": header.journal_code,
        "entry_date": header.entry_date.strftime("%Y-%m-%d") if header.entry_date else "",
        "description": header.description or "",
        "entries": []
    }

    for e in entries:
        data["entries"].append({
            "id": e.id,
            "account_id": e.account.id if e.account else "",
            "account_name": e.account.account_name if e.account else "",
            "account_type": e.account.account_type if e.account else "",
            "debit": float(e.debit or 0),
            "credit": float(e.credit or 0),
        })

    return JsonResponse(data)

# Update Journal Entry
def update_journal(request, id):
    pass

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

    return render(request, "Front_end/ledger.html")

# Files Page
def files(request):

    return render(request, "Front_end/files.html")