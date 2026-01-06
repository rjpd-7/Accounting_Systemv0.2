from django.urls import path
from . import views

# name of the Django app.
app_name = "AccountingSystem"

# URL configuration for Accounting_System.
urlpatterns = [
     path("", views.login_view, name="login_view"),
     path("index/", views.index, name="index"),
     path("login/", views.login_view, name="login"),
     path("logout/", views.logout_view, name="logout"),
     path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
     path('dashboard/teacher/', views.teacher_dashboard, name='teacher_dashboard'),
     path('dashboard/student/', views.student_dashboard, name='student_dashboard'),
     path('forbidden/', views.forbidden, name='forbidden'),
     path("accounts/", views.chart_of_accounts, name="accounts"),
     path("accounts_students/", views.chart_of_accounts_students, name="accounts_students"),
     path("journals/", views.journals, name="journals"),
     path("ledgers/", views.general_ledger, name="ledgers"),
     path("income-statement/", views.income_statement, name="income_statement"),
     path("balance-sheet/", views.balance_sheet, name="balance_sheet"),
     path("ledgers/download_pdf/", views.general_ledger_pdf, name="ledgers_pdf"),
     path("trial-balance/pdf/", views.trial_balance_pdf, name="trial_balance_pdf"),
     path("balance/", views.trial_balance, name="balance"),
     path('create_group/', views.create_group, name='create_group'),
     path("create_account/", views.create_account, name="create_account"),
     path("update_account/<int:id>/", views.update_account, name="update_account"),
     path("delete_account/<int:id>/", views.delete_account, name="delete_account"),
     path("insert_journals/", views.insert_journals, name="insert_journals"),
     path("update_journal/<int:id>/", views.update_journal, name="update_journal"),
     path("delete_journal/<int:id>/", views.delete_journal, name="delete_journal"),
     path("ledger/account/<int:account_id>/transactions/", views.ledger_account_transactions, name="ledger_account_transactions"),
     path('trial-balance/json/', views.trial_balance_json, name='trial_balance_json'),
     path('journal_pdf/<int:id>/', views.journal_pdf, name='journal_pdf'),
]