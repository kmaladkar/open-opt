import enum
from datetime import date
from sqlalchemy import Date, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class GoalType(str, enum.Enum):
    EMERGENCY = "emergency"
    EDUCATION = "education"
    RETIREMENT = "retirement"
    HOME = "home"


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    household_id: Mapped[int] = mapped_column(
        ForeignKey("households.id"), nullable=False, index=True
    )
    type: Mapped[GoalType] = mapped_column(Enum(GoalType), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    target_amount_cents: Mapped[int] = mapped_column(nullable=False)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    linked_account_id: Mapped[int | None] = mapped_column(nullable=True)

    household: Mapped["Household"] = relationship("Household", back_populates="goals")

    def __repr__(self) -> str:
        return f"<Goal(id={self.id}, household_id={self.household_id}, type={self.type}, name={self.name})>"
