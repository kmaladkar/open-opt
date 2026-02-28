import enum
from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

from app.models.user import User  # noqa: F401 - forward ref


class MemberRole(str, enum.Enum):
    PARENT = "parent"
    CHILD = "child"


class HouseholdMember(Base):
    __tablename__ = "household_members"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    household_id: Mapped[int] = mapped_column(ForeignKey("households.id"), nullable=False, index=True)
    role: Mapped[MemberRole] = mapped_column(
        Enum(MemberRole), nullable=False, default=MemberRole.PARENT
    )
    birth_year: Mapped[int | None] = mapped_column(Integer, nullable=True)

    household: Mapped["Household"] = relationship("Household", back_populates="members")
    user: Mapped["User"] = relationship("User", backref="household_memberships")

    def __repr__(self) -> str:
        return f"<HouseholdMember(id={self.id}, user_id={self.user_id}, household_id={self.household_id}, role={self.role})>"
