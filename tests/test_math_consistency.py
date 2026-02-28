"""Rigorous math consistency tests for projections and household aggregations."""

from datetime import date, timedelta
from itertools import permutations

from app.agents.subagents.investing import get_contribution_room
from app.agents.subagents.visualization import _balances_by_type, _project_total_series
from app.models.account import Account, AccountType
from app.models.household import Household
from app.models.household_member import HouseholdMember, MemberRole
from app.models.transaction import Transaction, TransactionCategory, TransactionPattern
from app.models.user import User
from app.services.transaction_patterns import get_transaction_patterns_for_household


def _manual_project(
    cash_dollars: float,
    invested_dollars: float,
    years: int,
    cash_rate: float,
    invested_rate: float,
    annual_invested_contribution: float,
    annual_cash_contribution: float,
    annual_cesg: float,
) -> list[float]:
    """Reference implementation for validating projection arithmetic."""
    series = [round(cash_dollars + invested_dollars, 2)]
    c_cash, c_inv = cash_dollars, invested_dollars
    for _ in range(years):
        c_cash = (c_cash + annual_cash_contribution) * (1 + cash_rate)
        c_inv = (c_inv + annual_invested_contribution + annual_cesg) * (1 + invested_rate)
        series.append(round(c_cash + c_inv, 2))
    return series


def test_project_total_series_matrix_matches_reference():
    """
    Exhaustive matrix over rates, contributions, and horizons to verify
    projection arithmetic and cumulative behavior.
    """
    cash_values = [0.0, 2500.0, 31_250.5]
    invested_values = [0.0, 20_000.0, 99_999.99]
    years_values = [1, 3, 5]
    cash_rates = [0.0, 0.005, 0.04]
    invested_rates = [0.0, 0.03, 0.05]
    annual_invested = [0.0, 1200.0, 3500.0]
    annual_cash = [0.0, 500.0]
    annual_cesg = [0.0, 250.0, 500.0]

    for cash in cash_values:
        for invested in invested_values:
            for years in years_values:
                for r_cash in cash_rates:
                    for r_inv in invested_rates:
                        for c_inv in annual_invested:
                            for c_cash in annual_cash:
                                for cesg in annual_cesg:
                                    got = _project_total_series(
                                        cash_dollars=cash,
                                        invested_dollars=invested,
                                        years=years,
                                        cash_rate=r_cash,
                                        invested_rate=r_inv,
                                        annual_invested_contribution=c_inv,
                                        annual_cash_contribution=c_cash,
                                        annual_cesg=cesg,
                                    )
                                    expected = _manual_project(
                                        cash_dollars=cash,
                                        invested_dollars=invested,
                                        years=years,
                                        cash_rate=r_cash,
                                        invested_rate=r_inv,
                                        annual_invested_contribution=c_inv,
                                        annual_cash_contribution=c_cash,
                                        annual_cesg=cesg,
                                    )
                                    assert got == expected
                                    assert len(got) == years + 1
                                    assert got[0] == round(cash + invested, 2)


def test_balances_by_type_is_permutation_invariant():
    """Account ordering should not change household cash/invested totals."""
    accounts = [
        {"id": 1, "type": "chequing", "name": "A", "balance_cents": 150_000},
        {"id": 2, "type": "savings", "name": "B", "balance_cents": 250_000},
        {"id": 3, "type": "tfsa", "name": "C", "balance_cents": 900_000},
        {"id": 4, "type": "rrsp", "name": "D", "balance_cents": 1_200_000},
    ]
    balances = [
        {"account_id": 1, "balance_cents": 150_000, "account_name": "A"},
        {"account_id": 2, "balance_cents": 250_000, "account_name": "B"},
        {"account_id": 3, "balance_cents": 900_000, "account_name": "C"},
        {"account_id": 4, "balance_cents": 1_200_000, "account_name": "D"},
    ]

    expected = (4000.0, 21000.0)
    for acc_perm in permutations(accounts):
        for bal_perm in permutations(balances):
            got = _balances_by_type(list(acc_perm), list(bal_perm))
            assert got == expected


def test_household_transaction_totals_add_up_with_signs_and_time_filter(db_session):
    """
    Validate that per-account and household cumulative totals stay consistent
    across income/expense signs, categories, patterns, and date filters.
    """
    household = Household(name="Math Test Household")
    db_session.add(household)
    db_session.flush()

    a1 = Account(
        household_id=household.id,
        type=AccountType.CHEQUING,
        name="Chequing",
        institution_id="RBC",
        balance_cents=100_000,
    )
    a2 = Account(
        household_id=household.id,
        type=AccountType.SAVINGS,
        name="Savings",
        institution_id="TD",
        balance_cents=200_000,
    )
    a3 = Account(
        household_id=household.id,
        type=AccountType.TFSA,
        name="TFSA",
        institution_id="WS",
        balance_cents=500_000,
    )
    db_session.add_all([a1, a2, a3])
    db_session.flush()

    today = date.today()
    inside = today - timedelta(days=15)
    outside = today - timedelta(days=120)
    txs = [
        # Account 1 (inside window)
        Transaction(
            account_id=a1.id,
            amount_cents=300_000,
            date=inside,
            description="Salary",
            pattern=TransactionPattern.RECURRING,
            category=TransactionCategory.SALARY,
        ),
        Transaction(
            account_id=a1.id,
            amount_cents=-120_000,
            date=inside,
            description="Rent",
            pattern=TransactionPattern.RECURRING,
            category=TransactionCategory.RENT,
        ),
        # Account 2 (inside window)
        Transaction(
            account_id=a2.id,
            amount_cents=50_000,
            date=inside,
            description="Transfer in",
            pattern=TransactionPattern.ONE_OFF,
            category=TransactionCategory.TRANSFER,
        ),
        Transaction(
            account_id=a2.id,
            amount_cents=-20_000,
            date=inside,
            description="Groceries",
            pattern=TransactionPattern.ONE_OFF,
            category=TransactionCategory.GROCERIES,
        ),
        # Account 3 (outside window, should be excluded for 90d)
        Transaction(
            account_id=a3.id,
            amount_cents=999_999,
            date=outside,
            description="Old gain",
            pattern=TransactionPattern.ONE_OFF,
            category=TransactionCategory.OTHER,
        ),
    ]
    db_session.add_all(txs)
    db_session.commit()

    result = get_transaction_patterns_for_household(db_session, household.id, days_back=90)
    accounts = result["accounts"]
    assert len(accounts) == 3

    # Invariant 1: each account net from pattern buckets equals income - expense
    for acc in accounts:
        net_from_patterns = sum(v["total_cents"] for v in acc["by_pattern"].values())
        assert net_from_patterns == acc["total_income_cents"] - acc["total_expense_cents"]

        # Invariant 2: monthly subtotals reconcile to account totals
        assert sum(acc["monthly_income_cents"].values()) == acc["total_income_cents"]
        assert sum(acc["monthly_expense_cents"].values()) == acc["total_expense_cents"]

    # Invariant 3: household totals equal sum of account totals
    total_income = sum(acc["total_income_cents"] for acc in accounts)
    total_expense = sum(acc["total_expense_cents"] for acc in accounts)
    assert result["household_total_income_cents"] == total_income
    assert result["household_total_expense_cents"] == total_expense

    # Expected numbers for inside-window transactions only:
    # income = 300000 + 50000, expense = 120000 + 20000
    assert result["household_total_income_cents"] == 350_000
    assert result["household_total_expense_cents"] == 140_000


def test_contribution_room_never_negative_across_balance_permutations(db_session):
    """Contribution room estimates should remain non-negative for all room types."""
    household = Household(name="Room Test Household")
    db_session.add(household)
    db_session.flush()

    # Generate combinations by mutating balances and verifying room constraints.
    tfsa_balances = [0, 300_000, 800_000]
    rrsp_balances = [0, 500_000, 4_000_000]
    fhsa_balances = [0, 1_000_000, 4_500_000]
    rrsp_income_values = [None, 45_000.0, 90_000.0]

    for tfsa_balance in tfsa_balances:
        for rrsp_balance in rrsp_balances:
            for fhsa_balance in fhsa_balances:
                # Reset account set per matrix point.
                db_session.query(Account).filter(Account.household_id == household.id).delete()
                db_session.add_all(
                    [
                        Account(
                            household_id=household.id,
                            type=AccountType.TFSA,
                            name="TFSA",
                            institution_id="WS",
                            balance_cents=tfsa_balance,
                        ),
                        Account(
                            household_id=household.id,
                            type=AccountType.RRSP,
                            name="RRSP",
                            institution_id="WS",
                            balance_cents=rrsp_balance,
                        ),
                        Account(
                            household_id=household.id,
                            type=AccountType.FHSA,
                            name="FHSA",
                            institution_id="WS",
                            balance_cents=fhsa_balance,
                        ),
                    ]
                )
                db_session.commit()

                for rrsp_income in rrsp_income_values:
                    room = get_contribution_room(
                        db=db_session,
                        household_id=household.id,
                        year=2025,
                        rrsp_income_18_percent=rrsp_income,
                    )
                    assert room["tfsa"]["annual_limit_cents"] >= 0
                    assert room["rrsp"]["estimated_room_cents"] >= 0
                    assert room["fhsa"]["estimated_room_lifetime_cents"] >= 0


def test_contribution_room_scales_for_multi_adult_household(db_session):
    """
    Household-level room should use household-level eligible adults, not a single-person cap.
    """
    household = Household(name="Two Parent Household")
    db_session.add(household)
    db_session.flush()

    parent_1 = User(email="p1@example.com", password_hash="x")
    parent_2 = User(email="p2@example.com", password_hash="x")
    db_session.add_all([parent_1, parent_2])
    db_session.flush()

    db_session.add_all(
        [
            HouseholdMember(
                user_id=parent_1.id,
                household_id=household.id,
                role=MemberRole.PARENT,
            ),
            HouseholdMember(
                user_id=parent_2.id,
                household_id=household.id,
                role=MemberRole.PARENT,
            ),
            Account(
                household_id=household.id,
                type=AccountType.TFSA,
                name="TFSA A",
                institution_id="WS",
                balance_cents=0,
            ),
            Account(
                household_id=household.id,
                type=AccountType.RRSP,
                name="RRSP A",
                institution_id="WS",
                balance_cents=0,
            ),
            Account(
                household_id=household.id,
                type=AccountType.FHSA,
                name="FHSA A",
                institution_id="WS",
                balance_cents=0,
            ),
        ]
    )
    db_session.commit()

    room = get_contribution_room(db=db_session, household_id=household.id, year=2025)
    # 2 adults => doubled household-level annual/lifetime estimates.
    assert room["tfsa"]["annual_limit_cents"] == 1_400_000
    assert room["rrsp"]["max_annual_cents"] == 6_498_000
    assert room["fhsa"]["annual_limit_cents"] == 1_600_000
    assert room["fhsa"]["lifetime_limit_cents"] == 8_000_000
