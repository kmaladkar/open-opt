from fastapi import APIRouter, Depends, HTTPException
from fastapi import status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.household import Household
from app.models.household_member import HouseholdMember, MemberRole
from app.schemas.household import (
    HouseholdCreate,
    HouseholdResponse,
    HouseholdUpdate,
    HouseholdMemberResponse,
)
from app.services.transaction_patterns import get_transaction_patterns_for_household

router = APIRouter()


@router.get("", response_model=list[HouseholdResponse])
def list_households(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    memberships = (
        db.query(HouseholdMember)
        .filter(HouseholdMember.user_id == current_user.id)
        .all()
    )
    household_ids = [m.household_id for m in memberships]
    households = db.query(Household).filter(Household.id.in_(household_ids)).all()
    return households


@router.post("", response_model=HouseholdResponse, status_code=status.HTTP_201_CREATED)
def create_household(
    body: HouseholdCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    household = Household(name=body.name)
    db.add(household)
    db.flush()
    member = HouseholdMember(
        user_id=current_user.id,
        household_id=household.id,
        role=MemberRole.PARENT,
    )
    db.add(member)
    db.commit()
    db.refresh(household)
    return household


@router.get("/{household_id}", response_model=HouseholdResponse)
def get_household(
    household_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_member(db, current_user.id, household_id)
    household = db.get(Household, household_id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")
    return household


@router.patch("/{household_id}", response_model=HouseholdResponse)
def update_household(
  household_id: int,
  body: HouseholdUpdate,
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
):
    _ensure_member(db, current_user.id, household_id)
    household = db.get(Household, household_id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")
    if body.name is not None:
        household.name = body.name
    db.commit()
    db.refresh(household)
    return household


@router.delete("/{household_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_household(
    household_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_member(db, current_user.id, household_id)
    household = db.get(Household, household_id)
    if not household:
        raise HTTPException(status_code=404, detail="Household not found")
    db.delete(household)
    db.commit()


@router.get("/{household_id}/members", response_model=list[HouseholdMemberResponse])
def list_household_members(
    household_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_member(db, current_user.id, household_id)
    members = (
        db.query(HouseholdMember)
        .filter(HouseholdMember.household_id == household_id)
        .all()
    )
    return members


@router.get("/{household_id}/transaction_patterns")
def get_household_transaction_patterns(
    household_id: int,
    days_back: int = 90,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Pay patterns across all household accounts: by account, category, recurring vs one-off (from SQLite)."""
    _ensure_member(db, current_user.id, household_id)
    return get_transaction_patterns_for_household(db, household_id, days_back=days_back)


def _ensure_member(db: Session, user_id: int, household_id: int) -> None:
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
