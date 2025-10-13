from django.shortcuts import render

# Create your views here.
def index(request):

    return render(request, "Front_end/index.html")

def login_view(request):
    
    return render(request, "Front_End/login.html")

def chart_of_accounts(request):

    return render(request, "Front_end/accounts.html")

def journals(request):

    return render(request, "Front_end/journal.html")

def general_ledger(request):

    return render(request, "Front_end/ledger.html")

def files(request):

    return render(request, "Front_end/files.html")