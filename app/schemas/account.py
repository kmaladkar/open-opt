from pydantic import BaseModel


class AccountCreate(BaseModel):
    household_id: int | None = None
    user_id: int | None = None
    type: str
    name: str
    institution_id: str = "mock"
    external_id: str | None = None
    currency: str = "CAD"
    balance_cents: int = 0


class AccountResponse(BaseModel):
    id: int
    household_id: int | None
    user_id: int | None
    type: str
    name: str
    institution_id: str
    currency: str
    balance_cents: int

    class Config:
        from_attributes = True
