from datetime import date
from pydantic import BaseModel


class GoalCreate(BaseModel):
    household_id: int
    type: str
    name: str
    target_amount_cents: int
    target_date: date | None = None
    linked_account_id: int | None = None


class GoalUpdate(BaseModel):
    name: str | None = None
    target_amount_cents: int | None = None
    target_date: date | None = None
    linked_account_id: int | None = None


class GoalResponse(BaseModel):
    id: int
    household_id: int
    type: str
    name: str
    target_amount_cents: int
    target_date: date | None
    linked_account_id: int | None

    class Config:
        from_attributes = True
