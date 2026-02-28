#!/usr/bin/env python3
"""
Idempotent seed script for mock households, users, accounts, and goals.
Covers Banking, Investing, Family, and Research permutations per plan §4.6.
Run from repo root: python scripts/seed_mock_data.py
"""
from datetime import date

import bcrypt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, init_db
from app.data.mock_fixtures import ALL_HOUSEHOLDS
from app.models.account import Account, AccountType
from app.models.goal import Goal, GoalType
from app.models.household import Household
from app.models.household_member import HouseholdMember, MemberRole
from app.models.user import User

MOCK_EMAIL_PREFIX = "mock_"
MOCK_EMAIL_SUFFIX = "@example.com"
MOCK_PASSWORD = "mock123"


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _slug(name: str) -> str:
    return name.replace(" ", "_").replace("'", "").lower()


def _clear_mock_data(db: Session) -> None:
    """Remove existing mock households and their mock users (idempotent)."""
    households = db.execute(
        select(Household).where(Household.name.startswith("Mock "))
    ).scalars().all()
    for row in households:
        db.delete(row[0])
    db.commit()

    users = db.execute(
        select(User).where(
            User.email.like(f"{MOCK_EMAIL_PREFIX}%{MOCK_EMAIL_SUFFIX}")
        )
    ).scalars().all()
    for row in users:
        db.delete(row[0])
    db.commit()


def seed(db: Session) -> None:
    init_db()
    _clear_mock_data(db)

    created_users: list[tuple[str, User]] = []
    for h_data in ALL_HOUSEHOLDS:
        slug = _slug(h_data["name"].replace("Mock ", ""))
        for i, m in enumerate(h_data["members"]):
            email = f"{MOCK_EMAIL_PREFIX}{slug}_{i}{MOCK_EMAIL_SUFFIX}"
            user = User(
                email=email,
                password_hash=_hash(MOCK_PASSWORD),
            )
            db.add(user)
            db.flush()
            created_users.append((email, user))

    user_index = 0
    for h_data in ALL_HOUSEHOLDS:
        household = Household(name=h_data["name"])
        db.add(household)
        db.flush()

        for m in h_data["members"]:
            _, user = created_users[user_index]
            member = HouseholdMember(
                user_id=user.id,
                household_id=household.id,
                role=MemberRole(m["role"]),
                birth_year=m.get("birth_year"),
            )
            db.add(member)
            user_index += 1

        for acc in h_data["accounts"]:
            account = Account(
                household_id=household.id,
                user_id=None,
                type=AccountType(acc["type"]),
                name=acc["name"],
                institution_id=acc["institution_id"],
                currency="CAD",
                balance_cents=acc["balance_cents"],
            )
            db.add(account)

        for g in h_data["goals"]:
            goal = Goal(
                household_id=household.id,
                type=GoalType(g["type"]),
                name=g["name"],
                target_amount_cents=g["target_amount_cents"],
                target_date=None,
            )
            db.add(goal)

    db.commit()
    print("Mock data seeded successfully.")


def main() -> None:
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
