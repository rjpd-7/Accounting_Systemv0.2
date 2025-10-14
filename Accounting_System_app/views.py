from django.shortcuts import render

# Create your views here.

# Home Page
def index(request):

    return render(request, "Front_end/index.html")

# Login Page
def login_view(request):
    
    return render(request, "Front_End/login.html")

# Accounts Page
def chart_of_accounts(request):

    return render(request, "Front_end/accounts.html")

# Journals Page
def journals(request):

    return render(request, "Front_end/journal.html")

# Ledgers Page
def general_ledger(request):

    return render(request, "Front_end/ledger.html")

# Files Page
def files(request):

    return render(request, "Front_end/files.html")