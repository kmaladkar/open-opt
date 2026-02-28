import enum
from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AccountType(str, enum.Enum):
    CHEQUING = "chequing"
    SAVINGS = "savings"
    TFSA = "tfsa"
    RRSP = "rrsp"
    FHSA = "fhsa"
    RESP = "resp"
    NON_REGISTERED = "non_registered"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    household_id: Mapped[int | None] = mapped_column(
        ForeignKey("households.id"), nullable=True, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    type: Mapped[AccountType] = mapped_column(Enum(AccountType), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    institution_id: Mapped[str] = mapped_column(String(64), nullable=False, default="mock")
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CAD")
    balance_cents: Mapped[int] = mapped_column(default=0, nullable=False)

    household: Mapped["Household | None"] = relationship(
        "Household", back_populates="accounts"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="account", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Account(id={self.id}, type={self.type}, name={self.name}, institution_id={self.institution_id})>"
