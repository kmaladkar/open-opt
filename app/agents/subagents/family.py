"""Family subagent: household members, goals, RESP eligibility, CESG."""

from sqlalchemy.orm import Session

from app.models.household_member import HouseholdMember, MemberRole
from app.models.goal import Goal
from app.models.account import Account, AccountType
from app.data.canadian_rules import (
    RESP_CESG_BASIC_RATE,
    RESP_CESG_BASIC_ANNUAL_CAP_CONTRIBUTION,
    cesg_additional_rate,
    RESP_CESG_LIFETIME_MAX_PER_BENEFICIARY,
)


def get_family_members(db: Session, household_id: int) -> list[dict]:
    """Return household members with role and birth_year (for RESP/CESG age logic)."""
    members = (
        db.query(HouseholdMember)
        .filter(HouseholdMember.household_id == household_id)
        .all()
    )
    return [
        {
            "user_id": m.user_id,
            "role": m.role.value if hasattr(m.role, "value") else str(m.role),
            "birth_year": m.birth_year,
        }
        for m in members
    ]


def get_goals(db: Session, household_id: int) -> list[dict]:
    """Return goals for the household (type, name, target_amount_cents, target_date)."""
    goals = db.query(Goal).filter(Goal.household_id == household_id).all()
    return [
        {
            "id": g.id,
            "type": g.type.value if hasattr(g.type, "value") else str(g.type),
            "name": g.name,
            "target_amount_cents": g.target_amount_cents,
            "target_date": g.target_date.isoformat() if g.target_date else None,
        }
        for g in goals
    ]


def get_resp_eligibility(db: Session, household_id: int) -> dict:
    """
    Return RESP-related info: child beneficiaries, RESPs in household,
    and whether CESG is still available (beneficiary under 18).
    """
    members = (
        db.query(HouseholdMember)
        .filter(
            HouseholdMember.household_id == household_id,
            HouseholdMember.role == MemberRole.CHILD,
        )
        .all()
    )
    accounts = db.query(Account).filter(
        Account.household_id == household_id,
        Account.type == AccountType.RESP,
    ).all()
    current_year = 2025
    children = []
    for m in members:
        by = m.birth_year or 0
        children.append({
            "birth_year": m.birth_year,
            "age_end_of_year": current_year - by if by else None,
            "cesg_eligible": (current_year - by) <= 17,
        })
    return {
        "child_beneficiaries": children,
        "resp_accounts": [
            {"id": a.id, "name": a.name, "institution_id": a.institution_id, "balance_cents": a.balance_cents}
            for a in accounts
        ],
        "cesg_lifetime_max_per_beneficiary": RESP_CESG_LIFETIME_MAX_PER_BENEFICIARY * 100,
    }


def compute_resp_cesg(
    contribution_cents: int,
    family_income: float,
    year: int = 2025,
) -> dict:
    """
    Compute basic and additional CESG for a given contribution and family income.
    """
    contribution_dollars = contribution_cents / 100
    basic_cap = RESP_CESG_BASIC_ANNUAL_CAP_CONTRIBUTION
    basic_eligible = min(contribution_dollars, basic_cap)
    basic_cesg_dollars = basic_eligible * RESP_CESG_BASIC_RATE
    basic_cesg_cents = int(basic_cesg_dollars * 100)

    additional_rate = cesg_additional_rate(family_income, year)
    additional_cap_contribution = 500
    additional_eligible = min(contribution_dollars, additional_cap_contribution)
    additional_cesg_dollars = additional_eligible * additional_rate
    additional_cesg_cents = int(additional_cesg_dollars * 100)

    return {
        "contribution_cents": contribution_cents,
        "family_income": family_income,
        "year": year,
        "basic_cesg_cents": basic_cesg_cents,
        "additional_cesg_cents": additional_cesg_cents,
        "total_cesg_cents": basic_cesg_cents + additional_cesg_cents,
        "basic_rate": RESP_CESG_BASIC_RATE,
        "additional_rate": additional_rate,
    }
