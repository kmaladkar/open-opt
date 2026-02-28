"""Investing subagent: contribution room, tax loss harvesting eligibility, products."""

from sqlalchemy.orm import Session

from app.models.account import Account, AccountType
from app.models.household_member import HouseholdMember, MemberRole
from app.data.canadian_rules import (
    tfsa_annual_limit,
    rrsp_max_annual,
    FHSA_ANNUAL_LIMIT,
    FHSA_LIFETIME_LIMIT,
    tax_loss_harvest_applies_to_account_type,
)


def get_contribution_room(
    db: Session,
    household_id: int,
    year: int = 2025,
    rrsp_income_18_percent: float | None = None,
) -> dict:
    """
    Return TFSA, RRSP, FHSA contribution room summary for the household.
    Room is estimated from limits minus current balances (simplified; real room comes from CRA).
    """
    accounts = db.query(Account).filter(Account.household_id == household_id).all()
    members = db.query(HouseholdMember).filter(HouseholdMember.household_id == household_id).all()
    eligible_adults = sum(
        1
        for m in members
        if (m.role == MemberRole.PARENT) or (getattr(m.role, "value", str(m.role)) != "child")
    )
    # Fallback for partial data: keep limits at least single-adult instead of zero.
    eligible_adults = max(1, eligible_adults)
    tfsa_balance = sum(a.balance_cents for a in accounts if a.type == AccountType.TFSA)
    rrsp_balance = sum(a.balance_cents for a in accounts if a.type == AccountType.RRSP)
    fhsa_balance = sum(a.balance_cents for a in accounts if a.type == AccountType.FHSA)

    tfsa_limit_cents = tfsa_annual_limit(year) * 100 * eligible_adults
    rrsp_max_cents = rrsp_max_annual(year) * 100 * eligible_adults
    if rrsp_income_18_percent is not None:
        rrsp_room = min(rrsp_max_cents, int(rrsp_income_18_percent * 0.18 * 100)) - rrsp_balance
    else:
        rrsp_room = rrsp_max_cents - rrsp_balance
    rrsp_room = max(0, rrsp_room)
    fhsa_annual = FHSA_ANNUAL_LIMIT * 100 * eligible_adults
    fhsa_lifetime = FHSA_LIFETIME_LIMIT * 100 * eligible_adults
    fhsa_room_lifetime = max(0, fhsa_lifetime - fhsa_balance)

    return {
        "year": year,
        "eligible_adults": eligible_adults,
        "tfsa": {
            "annual_limit_cents": tfsa_limit_cents,
            "current_balance_cents": tfsa_balance,
            "note": "Household estimate uses per-adult annual limits. Actual TFSA room from CRA My Account (cumulative) remains source of truth.",
        },
        "rrsp": {
            "max_annual_cents": rrsp_max_cents,
            "current_balance_cents": rrsp_balance,
            "estimated_room_cents": rrsp_room,
        },
        "fhsa": {
            "annual_limit_cents": fhsa_annual,
            "lifetime_limit_cents": fhsa_lifetime,
            "current_balance_cents": fhsa_balance,
            "estimated_room_lifetime_cents": fhsa_room_lifetime,
        },
    }


def tax_loss_harvesting_eligibility(db: Session, household_id: int) -> dict:
    """
    Return whether the household has non-registered accounts where tax loss harvesting
    could apply. Includes reminder about superficial loss (61-day) and affiliated persons.
    """
    accounts = db.query(Account).filter(Account.household_id == household_id).all()
    non_registered = [
        a for a in accounts
        if tax_loss_harvest_applies_to_account_type(
            a.type.value if hasattr(a.type, "value") else str(a.type)
        )
    ]
    return {
        "has_non_registered": len(non_registered) > 0,
        "accounts": [
            {"id": a.id, "name": a.name, "institution_id": a.institution_id, "balance_cents": a.balance_cents}
            for a in non_registered
        ],
        "note": "Tax loss harvesting applies only to non-registered accounts. Superficial loss rule: no same/identical purchase within 61 days (30 before + 30 after); affiliated persons include spouse, own RRSP/RRIF/TFSA.",
    }
