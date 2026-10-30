from decimal import Decimal


def detect_fraud(amount, transaction_type, balance):
    amount = Decimal(str(amount))
    balance = Decimal(str(balance))

    risk_score = 0
    reasons = []

    if amount <= 0:
        risk_score = 100
        reasons.append("Transaction amount must be positive.")

    if amount >= Decimal("20000"):
        risk_score += 40
        reasons.append("High transaction amount.")

    if balance > 0 and amount > balance * Decimal("0.8"):
        risk_score += 40
        reasons.append("Transaction is unusually large compared with the balance.")

    if transaction_type not in ["Deposit", "Withdrawal", "Transfer"]:
        risk_score = 100
        reasons.append("Unknown transaction type.")

    risk_score = min(risk_score, 100)

    if risk_score >= 70:
        result = "High Risk"
    elif risk_score >= 40:
        result = "Review Required"
    else:
        result = "Low Risk"

    if not reasons:
        reasons.append("No configured risk rules were triggered.")

    return {
        "risk_score": risk_score,
        "result": result,
        "reasons": reasons,
    }
