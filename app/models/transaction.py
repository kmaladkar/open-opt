"""Transaction model for SQLite. Stores pay patterns (recurring, one-off, income/expense) per account."""

import enum
from datetime import date
from sqlalchemy import Date, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TransactionPattern(str, enum.Enum):
    """How the transaction repeats; used for pay-pattern analysis."""
    RECURRING = "recurring"
    ONE_OFF = "one_off"


class TransactionCategory(str, enum.Enum):
    """Category for grouping and understanding pay patterns."""
    SALARY = "salary"
    RENT = "rent"
    UTILITIES = "utilities"
    GROCERIES = "groceries"
    TRANSFER = "transfer"
    SUBSCRIPTION = "subscription"
    SHOPPING = "shopping"
    DINING = "dining"
    OTHER = "other"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)  # positive = credit/income, negative = debit/expense
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    pattern: Mapped[TransactionPattern] = mapped_column(
        Enum(TransactionPattern), nullable=False, default=TransactionPattern.ONE_OFF
    )
    category: Mapped[TransactionCategory] = mapped_column(
        Enum(TransactionCategory), nullable=False, default=TransactionCategory.OTHER
    )

    account: Mapped["Account"] = relationship("Account", back_populates="transactions")

    def __repr__(self) -> str:
        return f"<Transaction(id={self.id}, account_id={self.account_id}, amount_cents={self.amount_cents}, date={self.date})>"
