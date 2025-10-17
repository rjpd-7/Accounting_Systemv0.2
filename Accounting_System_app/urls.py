from django.urls import path
from . import views

# name of the Django app.
app_name = "AccountingSystem"

# URL configuration for Accounting_System.
urlpatterns = [
     path("", views.login_view, name="login"),
     path("index/", views.index, name="index"),
     path("login/", views.login_view, name="login"),
     path("logout/", views.logout_view, name="logout"),
     path("accounts/", views.chart_of_accounts, name="accounts"),
     path("journals/", views.journals, name="journals"),
     path("ledgers/", views.general_ledger, name="ledgers"),
     path("files/", views.files, name="files"),
     path("create_account/", views.create_account, name="create_account"),
     path("update_account/<int:id>/", views.update_account, name="update_account"),
     path("delete_account/<int:id>/", views.delete_account, name="delete_account"),
     path("insert_journals/", views.insert_journals, name="insert_journals"),
     path("get_journal/<int:id>", views.get_journal_details, name="get_journal"),
     path("update_journal/<int:id>", views.update_journal, name="update_journal"),
     path("delete_journal/<int:id>", views.delete_journal, name="delete_journal"),
]