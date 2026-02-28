from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.account import Account, AccountType
from app.models.household_member import HouseholdMember
from app.schemas.account import AccountCreate, AccountResponse
from app.services.transaction_patterns import get_transaction_patterns_for_account

router = APIRouter()


def _ensure_household_member(db: Session, user_id: int, household_id: int) -> None:
    m = (
        db.query(HouseholdMember)
        .filter(
            HouseholdMember.user_id == user_id,
            HouseholdMember.household_id == household_id,
        )
        .first()
    )
    if not m:
        raise HTTPException(status_code=404, detail="Household not found")


@router.get("", response_model=list[AccountResponse])
def list_accounts(
    household_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if household_id is not None:
        _ensure_household_member(db, current_user.id, household_id)
        return db.query(Account).filter(Account.household_id == household_id).all()
    household_ids = [
        m.household_id
        for m in db.query(HouseholdMember).filter(HouseholdMember.user_id == current_user.id).all()
    ]
    if not household_ids:
        return db.query(Account).filter(Account.user_id == current_user.id).all()
    q = db.query(Account).filter(
            or_(
                Account.user_id == current_user.id,
                Account.household_id.in_(household_ids),
            )
        )
    return q.all()


@router.post("", response_model=AccountResponse, status_code=201)
def create_account(
    body: AccountCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.household_id is not None:
        _ensure_household_member(db, current_user.id, body.household_id)
    account = Account(
        household_id=body.household_id,
        user_id=body.user_id if body.user_id else (current_user.id if not body.household_id else None),
        type=AccountType(body.type),
        name=body.name,
        institution_id=body.institution_id,
        external_id=body.external_id,
        currency=body.currency,
        balance_cents=body.balance_cents,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


@router.get("/{account_id}", response_model=AccountResponse)
def get_account(
    account_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.household_id:
        _ensure_household_member(db, current_user.id, account.household_id)
    elif account.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Account not found")
    return account


@router.get("/{account_id}/transaction_patterns")
def get_account_transaction_patterns(
    account_id: int,
    days_back: int = 90,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pay patterns for this account: recurring vs one-off, by category, monthly income/expense (from SQLite)."""
    account = db.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    if account.household_id:
        _ensure_household_member(db, current_user.id, account.household_id)
    elif account.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Account not found")
    return get_transaction_patterns_for_account(db, account_id, days_back=days_back)
