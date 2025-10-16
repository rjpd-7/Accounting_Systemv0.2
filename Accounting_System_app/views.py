from django.http import HttpResponseRedirect
from django import forms
from django.shortcuts import render, redirect
from django.urls import reverse
from .models import USN_Accounts, AccountGroups, Accounts, ChartOfAccounts
from django.contrib.auth import authenticate, login, logout
from .forms import USNAccountsForm, ChartOfAccountsForm, UpdateAccountsForm

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

# Create Account Function
def create_account(request):
    account_code_submit = request.POST['account_code']
    account_name_submit = request.POST['account_name']
    account_type_submit = request.POST['account_type']
    account_description_submit = request.POST['account_description']
    account = ChartOfAccounts(account_code = account_code_submit, account_name = account_name_submit, account_type = account_type_submit,account_description = account_description_submit)
    account.save()

    return HttpResponseRedirect(reverse("AccountingSystem:accounts"))

# Update Account Function
def update_account(request, id):
    selected_account = ChartOfAccounts.objects.get(pk=id)
    if request.method == "POST":
        selected_account.account_name = request.POST.get("account_name", selected_account.account_name)
        selected_account.save()
        return redirect("AccountingSystem:accounts")
    
# Delete Account Function
def delete_account(request, id):
    try:
        account = ChartOfAccounts.objects.get(pk=id)
        account.delete()
    except ChartOfAccounts.DoesNotExist:
        pass
    return redirect("AccountingSystem:accounts")

# Journal Entries Page
def journals(request):
    accounts = ChartOfAccounts.objects.all()
    return render(request, "Front_end/journal.html", {
        "accounts" : accounts
    })

def insert_journals(request):
    pass

# General Ledger Page
def general_ledger(request):

    return render(request, "Front_end/ledger.html")

# Files Page
def files(request):

    return render(request, "Front_end/files.html")