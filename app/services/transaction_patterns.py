"""
Pay-pattern analysis: aggregate transactions from SQLite by pattern (recurring/one-off),
category, and time to help understand spending and income.
"""

from collections import defaultdict
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.transaction import Transaction, TransactionCategory, TransactionPattern


def get_transaction_patterns_for_account(
    db: Session, account_id: int, days_back: int = 90
) -> dict[str, Any]:
    """
    Summarize pay patterns for an account from SQLite transactions.
    Returns recurring vs one-off, by category, monthly income/expense.
    """
    since = date.today() - timedelta(days=days_back)
    txs = (
        db.query(Transaction)
        .filter(Transaction.account_id == account_id, Transaction.date >= since)
        .order_by(Transaction.date.desc())
        .all()
    )

    by_pattern = defaultdict(lambda: {"count": 0, "total_cents": 0})
    by_category = defaultdict(lambda: {"count": 0, "total_cents": 0})
    income_cents = 0
    expense_cents = 0
    monthly_income: dict[str, int] = defaultdict(int)
    monthly_expense: dict[str, int] = defaultdict(int)

    for t in txs:
        key_p = t.pattern.value if hasattr(t.pattern, "value") else str(t.pattern)
        key_c = t.category.value if hasattr(t.category, "value") else str(t.category)
        by_pattern[key_p]["count"] += 1
        by_pattern[key_p]["total_cents"] += t.amount_cents
        by_category[key_c]["count"] += 1
        by_category[key_c]["total_cents"] += t.amount_cents
        month_key = t.date.strftime("%Y-%m")
        if t.amount_cents > 0:
            income_cents += t.amount_cents
            monthly_income[month_key] += t.amount_cents
        else:
            expense_cents += abs(t.amount_cents)
            monthly_expense[month_key] += abs(t.amount_cents)

    return {
        "account_id": account_id,
        "days_back": days_back,
        "transaction_count": len(txs),
        "by_pattern": dict(by_pattern),
        "by_category": dict(by_category),
        "total_income_cents": income_cents,
        "total_expense_cents": expense_cents,
        "monthly_income_cents": dict(monthly_income),
        "monthly_expense_cents": dict(monthly_expense),
    }


def get_transaction_patterns_for_household(
    db: Session, household_id: int, days_back: int = 90
) -> dict[str, Any]:
    """
    Summarize pay patterns across all accounts in a household (SQLite).
    """
    accounts = db.query(Account).filter(Account.household_id == household_id).all()
    by_account: list[dict[str, Any]] = []
    total_income_cents = 0
    total_expense_cents = 0

    for acc in accounts:
        pat = get_transaction_patterns_for_account(db, acc.id, days_back)
        pat["account_name"] = acc.name
        pat["account_type"] = acc.type.value if hasattr(acc.type, "value") else str(acc.type)
        by_account.append(pat)
        total_income_cents += pat["total_income_cents"]
        total_expense_cents += pat["total_expense_cents"]

    return {
        "household_id": household_id,
        "days_back": days_back,
        "accounts": by_account,
        "household_total_income_cents": total_income_cents,
        "household_total_expense_cents": total_expense_cents,
    }
