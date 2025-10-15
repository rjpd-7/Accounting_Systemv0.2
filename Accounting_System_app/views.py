from django.http import HttpResponseRedirect
from django import forms
from django.shortcuts import render, redirect
from django.urls import reverse
from .models import USN_Accounts, AccountGroups, Accounts, ChartOfAccounts
from django.contrib.auth import authenticate, login, logout
from .forms import USNAccountsForm, ChartOfAccountsForm

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

    return render(request, "Front_end/accounts.html")

# Create Account Function
def create_account(request):
    if request.method == "POST":
        pass

# Journal Entries Page
def journals(request):

    return render(request, "Front_end/journal.html")

def insert_journals(request):
    pass

# General Ledger Page
def general_ledger(request):

    return render(request, "Front_end/ledger.html")

# Files Page
def files(request):

    return render(request, "Front_end/files.html")