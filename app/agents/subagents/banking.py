"""Banking subagent: accounts, balances, transactions. Reads from DB and optional open banking adapter."""

from datetime import date

from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.transaction import Transaction
from app.services.open_banking import get_open_banking_adapter, OBBalance, OBTransaction


def get_household_accounts(db: Session, household_id: int) -> list[dict]:
    """Return all accounts for a household (from DB). Each account includes type, name, institution_id, balance_cents."""
    accounts = db.query(Account).filter(Account.household_id == household_id).all()
    return [
        {
            "id": a.id,
            "type": a.type.value if hasattr(a.type, "value") else str(a.type),
            "name": a.name,
            "institution_id": a.institution_id,
            "balance_cents": a.balance_cents,
            "currency": a.currency,
        }
        for a in accounts
    ]


def get_balances(
    db: Session,
    household_id: int,
    user_id: str | None = None,
    institution_id: str | None = None,
    use_open_banking: bool = False,
) -> list[dict]:
    """
    Return balances for household accounts. If use_open_banking and user_id provided,
    can merge with adapter balances (mock or real FDX). Otherwise uses DB balances.
    """
    accounts = db.query(Account).filter(Account.household_id == household_id).all()
    if institution_id:
        accounts = [a for a in accounts if a.institution_id == institution_id]
    result = [
        {
            "account_id": a.id,
            "account_name": a.name,
            "institution_id": a.institution_id,
            "balance_cents": a.balance_cents,
            "currency": a.currency,
        }
        for a in accounts
    ]
    if use_open_banking and user_id:
        adapter = get_open_banking_adapter()
        ob_balances = adapter.get_balances(user_id, institution_id)
        # Merge: could replace or augment DB balances; for mock we keep DB as source of truth
        # and use OB for additional institutions. Here we just return DB; OB can be used by caller.
        _ = ob_balances  # available for future merge logic
    return result


def get_transactions_for_account(
    db: Session,
    account_id: int,
    from_date: date | None = None,
    to_date: date | None = None,
    use_open_banking: bool = False,
    account_external_id: str | None = None,
    institution_id: str | None = None,
) -> list[dict]:
    """
    Return transactions for an account. Prefer SQLite (Transaction model); fall back to open banking adapter if requested.
    """
    q = db.query(Transaction).filter(Transaction.account_id == account_id)
    if from_date:
        q = q.filter(Transaction.date >= from_date)
    if to_date:
        q = q.filter(Transaction.date <= to_date)
    txs_db = q.order_by(Transaction.date.desc()).all()
    if txs_db:
        return [
            {
                "id": t.id,
                "amount_cents": t.amount_cents,
                "date": t.date.isoformat(),
                "description": t.description,
                "pattern": t.pattern.value if hasattr(t.pattern, "value") else str(t.pattern),
                "category": t.category.value if hasattr(t.category, "value") else str(t.category),
                "is_income": t.amount_cents > 0,
            }
            for t in txs_db
        ]
    if use_open_banking and account_external_id and institution_id:
        adapter = get_open_banking_adapter()
        txs = adapter.get_transactions(account_external_id, institution_id, from_date, to_date)
        return [
            {
                "external_id": t.external_id,
                "amount_cents": t.amount_cents,
                "date": t.date.isoformat(),
                "description": t.description,
                "is_income": t.is_income,
            }
            for t in txs
        ]
    return []
