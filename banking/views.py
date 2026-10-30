import uuid
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect
from django.db import transaction
from django.db.models import Sum
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from .models import BankAccount, Transaction
from .fraud_detector import detect_fraud

@login_required
def home(request):
    total_accounts = BankAccount.objects.filter(user=request.user, is_active=True).count()

    total_balance = BankAccount.objects.filter(
        user=request.user, is_active=True
    ).aggregate(total=Sum("balance"))["total"] or Decimal("0.00")

    total_deposits = Transaction.objects.filter(
        account__user=request.user,
        transaction_type="Deposit",
        status="Completed"
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    total_withdrawals = Transaction.objects.filter(
        account__user=request.user,
        transaction_type="Withdrawal",
        status="Completed"
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    recent_transactions = Transaction.objects.filter(account__user=request.user).select_related(
        "account", "account__user"
    ).order_by("-timestamp")[:5]

    context = {
        "total_accounts": total_accounts,
        "total_balance": total_balance,
        "total_deposits": total_deposits,
        "total_withdrawals": total_withdrawals,
        "recent_transactions": recent_transactions,
    }

    return render(request, "banking/home.html", context)

@login_required
def accounts(request):
    account_list = BankAccount.objects.filter(user=request.user).select_related("user").order_by("account_number")
    return render(request, "banking/accounts.html", {"accounts": account_list})

@login_required
def transactions(request):
    transaction_list = Transaction.objects.filter(account__user=request.user).select_related(
        "account", "account__user"
    ).order_by("-timestamp")

    return render(
        request,
        "banking/transactions.html",
        {"transactions": transaction_list},
    )

@login_required
def fraud_detection(request):
    result = None
    error = None

    if request.method == "POST":
        try:
            amount = Decimal(request.POST.get("amount", ""))
            balance = Decimal(request.POST.get("balance", ""))
            transaction_type = request.POST.get("transaction_type", "")

            if not amount.is_finite() or not balance.is_finite():
                raise ValueError("Enter valid numbers.")

            if amount <= 0 or balance < 0:
                raise ValueError("Amount must be positive and balance cannot be negative.")

            if transaction_type not in ("Deposit", "Withdrawal", "Transfer"):
                raise ValueError("Select a valid transaction type.")

            result = detect_fraud(amount, transaction_type, balance)

        except (InvalidOperation, TypeError, ValueError):
            error = "Enter a valid positive amount and a non-negative balance."

    return render(
        request,
        "banking/fraud.html",
        {"result": result, "error": error},
    )

@login_required
def loan_assessment(request):
    result = None
    error = None

    if request.method == "POST":
        try:
            monthly_income = Decimal(request.POST.get("monthly_income", ""))
            monthly_emi = Decimal(request.POST.get("monthly_emi", ""))
            loan_amount = Decimal(request.POST.get("loan_amount", ""))
            credit_score = int(request.POST.get("credit_score", ""))

            if not all(value.is_finite() for value in (
                monthly_income, monthly_emi, loan_amount
            )):
                raise ValueError

            if monthly_income <= 0 or monthly_emi < 0 or loan_amount <= 0:
                raise ValueError

            if not 300 <= credit_score <= 900:
                raise ValueError

            emi_ratio = monthly_emi / monthly_income

            reasons = []
            eligible = True

            if credit_score < 650:
                eligible = False
                reasons.append("Credit score is below the demo threshold of 650.")

            if emi_ratio > Decimal("0.5"):
                eligible = False
                reasons.append("Existing monthly EMI is more than 50% of monthly income.")

            if eligible:
                reasons.append("The inputs meet the configured demo eligibility rules.")

            result = {
                "eligible": eligible,
                "emi_ratio": round(emi_ratio * 100, 2),
                "reasons": reasons,
            }

        except (InvalidOperation, TypeError, ValueError):
            error = (
                "Enter valid values. Income and loan amount must be positive, "
                "EMI cannot be negative, and credit score must be between 300 and 900."
            )

    return render(
        request,
        "banking/loans.html",
        {"result": result, "error": error},
    )

@login_required
@require_POST
def process_transaction(request):
    account_number = request.POST.get("account_number", "").strip()
    transaction_type = request.POST.get("transaction_type", "").strip()

    try:
        amount = Decimal(request.POST.get("amount", ""))
    except (InvalidOperation, TypeError):
        messages.error(request, "Please enter a valid amount.")
        return redirect("accounts")

    if not amount.is_finite() or amount <= 0:
        messages.error(request, "Amount must be greater than zero.")
        return redirect("accounts")

    if transaction_type not in ("Deposit", "Withdrawal"):
        messages.error(request, "Choose Deposit or Withdrawal.")
        return redirect("accounts")

    try:
        with transaction.atomic():
            account = BankAccount.objects.get(
                account_number=account_number,
                user=request.user,
                is_active=True,
            )

            if transaction_type == "Withdrawal" and amount > account.balance:
                messages.error(request, "Insufficient balance.")
                return redirect("accounts")

            if transaction_type == "Withdrawal":
                risk = detect_fraud(
                    amount,
                    transaction_type,
                    account.balance,
                )

                if risk["risk_score"] >= 70:
                    messages.error(
                        request,
                        f"Withdrawal blocked: {risk['result']}. "
                        f"Risk score: {risk['risk_score']}/100. "
                        f"Reasons: {' '.join(risk['reasons'])}",
                    )
                    return redirect("accounts")

            if transaction_type == "Deposit":
                account.balance += amount
            else:
                account.balance -= amount

            account.save(update_fields=["balance"])

            Transaction.objects.create(
                account=account,
                transaction_type=transaction_type,
                amount=amount,
                status="Completed",
            )

        messages.success(
            request,
            f"{transaction_type} of ₹{amount:.2f} completed successfully.",
        )

    except BankAccount.DoesNotExist:
        messages.error(request, "Account not found or inactive.")

    return redirect("accounts")


def register_view(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()

                account_number = f"SB360{uuid.uuid4().hex[:12].upper()}"

                BankAccount.objects.create(
                    user=user,
                    account_number=account_number,
                    account_type="Savings",
                    balance=0,
                    is_active=True
                )

            messages.success(
                request,
                "Registration successful. Your bank account has been created. Please log in."
            )
            return redirect("login")
    else:
        form = UserCreationForm()

    return render(request, "banking/register.html", {"form": form})


def login_view(request):
    error = None

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("home")
        error = "Invalid username or password."

    return render(request, "banking/login.html", {"error": error})


@require_POST
def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("login")
