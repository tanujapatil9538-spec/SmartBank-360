from django.urls import path
from . import views

urlpatterns = [
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.register_view, name="home"),
    path("accounts/", views.accounts, name="accounts"),
    path("transactions/", views.transactions, name="transactions"),
    path("process-transaction/", views.process_transaction, name="process_transaction"),
    path("fraud-detection/", views.fraud_detection, name="fraud_detection"),
    path("loan-assessment/", views.loan_assessment, name="loan_assessment"),
]

