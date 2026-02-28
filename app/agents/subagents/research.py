"""Research subagent: Canadian rules, limits, CESG/CLB, FHSA, tax loss harvesting."""

from app.data import canadian_rules as cr


def get_tfsa_limit(year: int = 2025) -> dict:
    """TFSA annual limit and note about cumulative room."""
    return {
        "year": year,
        "annual_limit_dollars": cr.tfsa_annual_limit(year),
        "note": "Cumulative room ~$109,000 (2026) for eligible since 2009; contributions count if by Dec 31; CRA My Account has room (updated ~April following year).",
    }


def get_rrsp_limit(year: int = 2025) -> dict:
    """RRSP max annual (18% of income, capped) and deadline."""
    return {
        "year": year,
        "max_annual_dollars": cr.rrsp_max_annual(year),
        "note": "18% of income, capped. No lifetime cap. Contribution deadline for prior tax year: first 60 days of following year (e.g. Mar 2, 2026 for 2025).",
    }


def get_fhsa_limits() -> dict:
    """FHSA annual and lifetime limits, eligibility (first-time buyer)."""
    return {
        "annual_limit_dollars": cr.FHSA_ANNUAL_LIMIT,
        "lifetime_limit_dollars": cr.FHSA_LIFETIME_LIMIT,
        "carry_forward_max_dollars": cr.FHSA_CARRY_FORWARD_MAX,
        "eligibility": "Canadian resident, 18+, first-time buyer (no principal residence in current or prior 4 calendar years for you or spouse/common-law partner).",
        "qualifying_withdrawal": "Tax-free for first home in Canada; must close by end of year after first qualifying withdrawal, or within 15 years of opening, or by age 71.",
    }


def get_cesg_rates(family_income: float, year: int = 2025) -> dict:
    """CESG basic and additional (income-tested) rates and thresholds."""
    low, high = cr.cesg_income_thresholds(year)
    additional_rate = cr.cesg_additional_rate(family_income, year)
    additional_max = cr.cesg_additional_max_annual(family_income, year)
    return {
        "year": year,
        "family_income": family_income,
        "basic_cesg": "20% on first $2,500/year = max $500/year per beneficiary.",
        "income_threshold_low": low,
        "income_threshold_high": high,
        "additional_cesg_rate": additional_rate,
        "additional_cesg_max_dollars": additional_max,
        "cesg_lifetime_max_per_beneficiary_dollars": cr.RESP_CESG_LIFETIME_MAX_PER_BENEFICIARY,
        "clb_lifetime_max_per_child_dollars": cr.RESP_CLB_LIFETIME_MAX_PER_CHILD,
    }


def get_superficial_loss_rules() -> dict:
    """Superficial loss rule: 61-day window, affiliated persons."""
    return {
        "window_days": cr.superficial_loss_window_days(),
        "description": "A capital loss is disallowed (superficial) if the taxpayer or an affiliated person acquires the same or identical property within 61 days (30 before or 30 after the sale).",
        "affiliated_persons": "Spouse or common-law partner; the taxpayer's RRSP, RRIF, or TFSA; certain controlled trusts or corporations.",
        "effect": "The denied loss is added to the adjusted cost base of the repurchased property.",
    }


def get_tax_loss_harvesting_rules() -> dict:
    """Tax loss harvesting: non-registered only, strategy."""
    return {
        "applies_to": "Non-registered (taxable) investment accounts only. Losses in RRSP/TFSA cannot be claimed; do not transfer losing shares into registered accounts or the loss is permanently lost.",
        "strategy": "Sell at a loss, then wait at least 30 days before repurchasing the same or identical security; or buy a different but similar investment to keep exposure while realizing the loss.",
        "use_of_losses": "Capital losses can reduce current-year gains, be carried back up to three years, or carried forward indefinitely.",
        "superficial_loss": "Respect 61-day window and affiliated-person rules (e.g. no repurchase in spouse's or own TFSA/RRSP within the window).",
    }
