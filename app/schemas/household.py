from pydantic import BaseModel


class HouseholdCreate(BaseModel):
    name: str


class HouseholdUpdate(BaseModel):
    name: str | None = None


class HouseholdResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class HouseholdMemberResponse(BaseModel):
    id: int
    user_id: int
    household_id: int
    role: str
    birth_year: int | None = None

    class Config:
        from_attributes = True
