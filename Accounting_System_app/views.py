from django.http import HttpResponseRedirect
from django import forms
from django.shortcuts import render, redirect
from django.urls import reverse
from .models import USN_Accounts, AccountGroups, Accounts, ChartOfAccounts
from django.contrib.auth import authenticate, login, logout
from .forms import USNAccountsForm

# Create your views here.
def index(request):

    return render(request, "Front_end/index.html")

def login_view(request):
    
    return render(request, "Front_End/login.html")

def logout_view(request):
    
    return render(request, "Front_End/login.html")

def chart_of_accounts(request):

    return render(request, "Front_end/accounts.html")

def journals(request):

    return render(request, "Front_end/journal.html")

def general_ledger(request):

    return render(request, "Front_end/ledger.html")

def files(request):

    return render(request, "Front_end/files.html")