from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.goal import Goal, GoalType
from app.models.household_member import HouseholdMember
from app.schemas.goal import GoalCreate, GoalResponse, GoalUpdate

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


@router.get("", response_model=list[GoalResponse])
def list_goals(
    household_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    household_ids = [
        m.household_id
        for m in db.query(HouseholdMember)
        .filter(HouseholdMember.user_id == current_user.id)
        .all()
    ]
    q = db.query(Goal).filter(Goal.household_id.in_(household_ids))
    if household_id is not None:
        _ensure_household_member(db, current_user.id, household_id)
        q = q.filter(Goal.household_id == household_id)
    return q.all()


@router.post("", response_model=GoalResponse, status_code=201)
def create_goal(
    body: GoalCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_household_member(db, current_user.id, body.household_id)
    goal = Goal(
        household_id=body.household_id,
        type=GoalType(body.type),
        name=body.name,
        target_amount_cents=body.target_amount_cents,
        target_date=body.target_date,
        linked_account_id=body.linked_account_id,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


@router.get("/{goal_id}", response_model=GoalResponse)
def get_goal(
    goal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = db.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    _ensure_household_member(db, current_user.id, goal.household_id)
    return goal


@router.patch("/{goal_id}", response_model=GoalResponse)
def update_goal(
    goal_id: int,
    body: GoalUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = db.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    _ensure_household_member(db, current_user.id, goal.household_id)
    if body.name is not None:
        goal.name = body.name
    if body.target_amount_cents is not None:
        goal.target_amount_cents = body.target_amount_cents
    if body.target_date is not None:
        goal.target_date = body.target_date
    if body.linked_account_id is not None:
        goal.linked_account_id = body.linked_account_id
    db.commit()
    db.refresh(goal)
    return goal


@router.delete("/{goal_id}", status_code=204)
def delete_goal(
    goal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    goal = db.get(Goal, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    _ensure_household_member(db, current_user.id, goal.household_id)
    db.delete(goal)
    db.commit()
