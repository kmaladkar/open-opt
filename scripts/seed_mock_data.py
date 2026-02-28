#!/usr/bin/env python3
"""
Idempotent seed script for a single robust mock household:
- Exactly 1 family (2 parents, 2 children)
- Rich account mix and goals
- Dense transaction history across recurring + one-off patterns

Run from repo root:
  uv run python scripts/seed_mock_data.py
"""

from datetime import date, timedelta

import bcrypt
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, init_db
from app.models.account import Account, AccountType
from app.models.goal import Goal, GoalType
from app.models.household import Household
from app.models.household_member import HouseholdMember, MemberRole
from app.models.transaction import Transaction, TransactionCategory, TransactionPattern
from app.models.user import User

MOCK_EMAIL_PREFIX = "mock_"
MOCK_EMAIL_SUFFIX = "@example.com"
MOCK_PASSWORD = "mock123"

HOUSEHOLD_NAME = "Mock Alvarez Family"
HOUSEHOLD_SLUG = "alvarez_family"
MEMBERS = [
    {"role": "parent", "birth_year": 1984},
    {"role": "parent", "birth_year": 1987},
    {"role": "child", "birth_year": 2013},
    {"role": "child", "birth_year": 2017},
]
ACCOUNTS = [
    {"type": "chequing", "name": "RBC Family Chequing", "institution_id": "RBC", "balance_cents": 550_000, "owner_member_index": None},
    {"type": "savings", "name": "TD Emergency Savings", "institution_id": "TD", "balance_cents": 1_300_000, "owner_member_index": None},
    {"type": "tfsa", "name": "Wealthsimple TFSA Parent A", "institution_id": "WEALTHSIMPLE", "balance_cents": 2_800_000, "owner_member_index": 0},
    {"type": "tfsa", "name": "RBC TFSA Parent B", "institution_id": "RBC", "balance_cents": 1_900_000, "owner_member_index": 1},
    {"type": "rrsp", "name": "Wealthsimple RRSP Parent A", "institution_id": "WEALTHSIMPLE", "balance_cents": 5_400_000, "owner_member_index": 0},
    {"type": "fhsa", "name": "TD FHSA Parent B", "institution_id": "TD", "balance_cents": 950_000, "owner_member_index": 1},
    {"type": "resp", "name": "Wealthsimple RESP Family", "institution_id": "WEALTHSIMPLE", "balance_cents": 2_250_000, "owner_member_index": None},
]
GOALS = [
    {"type": "emergency", "name": "Emergency Fund", "target_amount_cents": 1_800_000},
    {"type": "education", "name": "Kids Education Fund", "target_amount_cents": 6_000_000},
    {"type": "retirement", "name": "Retirement Goal", "target_amount_cents": 25_000_000},
    {"type": "home", "name": "Home Upgrade Fund", "target_amount_cents": 9_500_000},
]


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _clear_existing_data(db: Session) -> None:
    """
    Remove all household-linked financial data and all mock users.
    Keeps non-mock users without household data.
    """
    db.query(Transaction).delete()
    db.query(Goal).delete()
    db.query(Account).delete()
    db.query(HouseholdMember).delete()
    db.query(Household).delete()
    db.query(User).filter(User.email.like(f"{MOCK_EMAIL_PREFIX}%{MOCK_EMAIL_SUFFIX}")).delete()
    db.commit()


def _tx(amount_cents: int, offset_days: int, description: str, pattern: TransactionPattern, category: TransactionCategory) -> dict:
    return {
        "amount_cents": amount_cents,
        "date_offset_days": offset_days,
        "description": description,
        "pattern": pattern,
        "category": category,
    }


def _transaction_specs_for_account(account_type: str, account_name: str) -> list[dict]:
    """
    Build robust transaction history across ~180 days.
    Includes recurring + one-off transactions and transfer flows.
    """
    specs: list[dict] = []

    if account_type == "chequing":
        for i, d in enumerate(range(5, 181, 14)):
            payroll = 330_000 if i % 2 == 0 else 305_000
            specs.append(_tx(payroll, -d, "Payroll deposit", TransactionPattern.RECURRING, TransactionCategory.SALARY))
        for d in (12, 42, 72, 102, 132, 162):
            specs.append(_tx(-248_000, -d, "Rent payment", TransactionPattern.RECURRING, TransactionCategory.RENT))
        for d in range(7, 181, 7):
            groceries = 18_500 if d % 14 else 22_000
            specs.append(_tx(-groceries, -d, "Groceries", TransactionPattern.RECURRING, TransactionCategory.GROCERIES))
        for d in (9, 39, 69, 99, 129, 159):
            specs.append(_tx(-26_000, -d, "Hydro + internet", TransactionPattern.RECURRING, TransactionCategory.UTILITIES))
        for d in (4, 34, 64, 94, 124, 154):
            specs.append(_tx(-110_000, -d, "Transfer to emergency savings", TransactionPattern.RECURRING, TransactionCategory.TRANSFER))
        for d in (17, 48, 88, 118, 147, 175):
            specs.append(_tx(-7_500, -d, "Streaming subscriptions", TransactionPattern.RECURRING, TransactionCategory.SUBSCRIPTION))
        for d in (20, 53, 81, 111, 142, 171):
            specs.append(_tx(-14_500, -d, "Family dining", TransactionPattern.ONE_OFF, TransactionCategory.DINING))
        for d in (27, 59, 90, 121, 150):
            specs.append(_tx(-35_000, -d, "School supplies / kids expenses", TransactionPattern.ONE_OFF, TransactionCategory.SHOPPING))

    elif account_type == "savings":
        for d in (4, 34, 64, 94, 124, 154):
            specs.append(_tx(110_000, -d, "Transfer from chequing", TransactionPattern.RECURRING, TransactionCategory.TRANSFER))
        for d in (30, 60, 90, 120, 150, 180):
            specs.append(_tx(4_000, -d, "Savings interest credit", TransactionPattern.RECURRING, TransactionCategory.OTHER))
        for d in (75, 165):
            specs.append(_tx(-65_000, -d, "Emergency expense", TransactionPattern.ONE_OFF, TransactionCategory.OTHER))

    elif account_type == "resp":
        for d in (15, 45, 75, 105, 135, 165):
            specs.append(_tx(42_000, -d, "RESP contribution", TransactionPattern.RECURRING, TransactionCategory.TRANSFER))
        for d in (16, 46, 76, 106, 136, 166):
            specs.append(_tx(8_400, -d, "CESG grant", TransactionPattern.RECURRING, TransactionCategory.OTHER))

    elif account_type == "tfsa":
        for d in (22, 52, 82, 112, 142, 172):
            specs.append(_tx(70_000, -d, f"{account_name} contribution", TransactionPattern.RECURRING, TransactionCategory.TRANSFER))
        for d in (26, 56, 86, 116, 146, 176):
            specs.append(_tx(2_700, -d, f"{account_name} dividend", TransactionPattern.RECURRING, TransactionCategory.OTHER))

    elif account_type == "rrsp":
        for d in (25, 55, 85, 115, 145, 175):
            specs.append(_tx(95_000, -d, "RRSP contribution", TransactionPattern.RECURRING, TransactionCategory.TRANSFER))
        for d in (40, 100, 160):
            specs.append(_tx(8_500, -d, "RRSP distribution income", TransactionPattern.ONE_OFF, TransactionCategory.OTHER))

    elif account_type == "fhsa":
        for d in (28, 58, 88, 118, 148, 178):
            specs.append(_tx(60_000, -d, "FHSA contribution", TransactionPattern.RECURRING, TransactionCategory.TRANSFER))
        for d in (63, 123, 173):
            specs.append(_tx(3_500, -d, "FHSA growth distribution", TransactionPattern.ONE_OFF, TransactionCategory.OTHER))

    return specs


def seed(db: Session) -> None:
    init_db()
    _clear_existing_data(db)

    users: list[tuple[str, User]] = []
    for i, _member in enumerate(MEMBERS):
        email = f"{MOCK_EMAIL_PREFIX}{HOUSEHOLD_SLUG}_{i}{MOCK_EMAIL_SUFFIX}"
        user = User(email=email, password_hash=_hash(MOCK_PASSWORD))
        db.add(user)
        db.flush()
        users.append((email, user))

    household = Household(name=HOUSEHOLD_NAME)
    db.add(household)
    db.flush()

    for idx, member_data in enumerate(MEMBERS):
        db.add(
            HouseholdMember(
                user_id=users[idx][1].id,
                household_id=household.id,
                role=MemberRole(member_data["role"]),
                birth_year=member_data["birth_year"],
            )
        )

    transaction_count = 0
    for acc in ACCOUNTS:
        owner_idx = acc["owner_member_index"]
        user_id = users[owner_idx][1].id if owner_idx is not None else None
        account = Account(
            household_id=household.id,
            user_id=user_id,
            type=AccountType(acc["type"]),
            name=acc["name"],
            institution_id=acc["institution_id"],
            currency="CAD",
            balance_cents=acc["balance_cents"],
        )
        db.add(account)
        db.flush()

        for spec in _transaction_specs_for_account(acc["type"], acc["name"]):
            tx_date = date.today() + timedelta(days=spec["date_offset_days"])
            db.add(
                Transaction(
                    account_id=account.id,
                    amount_cents=spec["amount_cents"],
                    date=tx_date,
                    description=spec["description"],
                    pattern=spec["pattern"],
                    category=spec["category"],
                )
            )
            transaction_count += 1

    for g in GOALS:
        db.add(
            Goal(
                household_id=household.id,
                type=GoalType(g["type"]),
                name=g["name"],
                target_amount_cents=g["target_amount_cents"],
                target_date=None,
            )
        )

    db.commit()
    print("Mock data seeded successfully.")
    print(f"Households: 1 ({HOUSEHOLD_NAME})")
    print(f"Members: {len(MEMBERS)} (2 parents, 2 children)")
    print(f"Accounts: {len(ACCOUNTS)}")
    print(f"Transactions: {transaction_count}")
    print("Mock logins (password for all: mock123):")
    for email, _ in users:
        print(f"  - {email}")


def print_logins() -> None:
    print("Mock logins (password for all: mock123):")
    for i in range(len(MEMBERS)):
        print(f"  - {MOCK_EMAIL_PREFIX}{HOUSEHOLD_SLUG}_{i}{MOCK_EMAIL_SUFFIX}")


def main() -> None:
    import sys

    if "--print-logins" in sys.argv:
        print_logins()
        return
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
