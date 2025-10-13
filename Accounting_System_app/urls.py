from django.urls import path
from . import views

# name of the Django app.
app_name = "AccountingSystem"

# URL configuration for Accounting_System.
urlpatterns = [
     path("", views.login_view, name="login"),
     path("index/", views.index, name="index"),
     path("login/", views.login_view, name="login"),
     path("accounts/", views.chart_of_accounts, name="accounts"),
     path("journals/", views.journals, name="journals"),
     path("ledgers/", views.general_ledger, name="ledgers"),
     path("files/", views.files, name="files"),
]