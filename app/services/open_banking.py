"""
Open banking adapter for Canada (Consumer-Driven Banking).

Abstract interface for get_accounts, get_transactions, get_balances so the app
is not tied to one provider. Designed for multiple institutions (RBC, TD, BMO,
CIBC, Scotiabank, Wealthsimple, etc.); when FDX goes live, implement per-institution
clients or use an aggregator. Until then, the mock implementation returns fixture
data. Production will require accreditation and real FDX (or equivalent) endpoints.
"""
from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass
class OBAccount:
    """Provider-agnostic account from open banking."""

    external_id: str
    institution_id: str
    name: str
    type: str  # chequing, savings, tfsa, rrsp, fhsa, resp, non_registered
    currency: str
    balance_cents: int | None = None


@dataclass
class OBTransaction:
    """Provider-agnostic transaction."""

    external_id: str
    account_external_id: str
    institution_id: str
    amount_cents: int
    date: date
    description: str
    is_income: bool | None = None


@dataclass
class OBBalance:
    """Provider-agnostic balance for an account."""

    account_external_id: str
    institution_id: str
    balance_cents: int
    currency: str
    as_of_date: date | None = None


class OpenBankingAdapter(Protocol):
    """Abstract interface for open banking. Implement per provider (e.g. FDX)."""

    def get_accounts(
        self,
        user_id: str,
        institution_id: str | None = None,
        consent_id: str | None = None,
    ) -> list[OBAccount]:
        """Return accounts for the user, optionally filtered by institution."""
        ...

    def get_transactions(
        self,
        account_external_id: str,
        institution_id: str,
        from_date: date | None = None,
        to_date: date | None = None,
        consent_id: str | None = None,
    ) -> list[OBTransaction]:
        """Return transactions for an account."""
        ...

    def get_balances(
        self,
        user_id: str,
        institution_id: str | None = None,
        consent_id: str | None = None,
    ) -> list[OBBalance]:
        """Return current balances for the user's accounts."""
        ...


# ---------------------------------------------------------------------------
# Mock implementation (sandbox until real FDX / accreditation)
# ---------------------------------------------------------------------------

_MOCK_ACCOUNTS: list[dict] = [
    {"external_id": "mock-rbc-cheq-1", "institution_id": "RBC", "name": "RBC Daily Chequing", "type": "chequing", "currency": "CAD", "balance_cents": 150000},
    {"external_id": "mock-td-sav-1", "institution_id": "TD", "name": "TD High Interest", "type": "savings", "currency": "CAD", "balance_cents": 500000},
    {"external_id": "mock-bmo-tfsa-1", "institution_id": "BMO", "name": "BMO TFSA", "type": "tfsa", "currency": "CAD", "balance_cents": 300000},
    {"external_id": "mock-bmo-rrsp-1", "institution_id": "BMO", "name": "BMO RRSP", "type": "rrsp", "currency": "CAD", "balance_cents": 800000},
    {"external_id": "mock-ws-resp-1", "institution_id": "Wealthsimple", "name": "Wealthsimple RESP", "type": "resp", "currency": "CAD", "balance_cents": 400000},
    {"external_id": "mock-cibc-cheq-1", "institution_id": "CIBC", "name": "CIBC Chequing", "type": "chequing", "currency": "CAD", "balance_cents": 80000},
    {"external_id": "mock-scotia-sav-1", "institution_id": "Scotiabank", "name": "Scotiabank Savings", "type": "savings", "currency": "CAD", "balance_cents": 200000},
    {"external_id": "mock-ws-tfsa-1", "institution_id": "Wealthsimple", "name": "Wealthsimple TFSA", "type": "tfsa", "currency": "CAD", "balance_cents": 950000},
    {"external_id": "mock-ws-rrsp-1", "institution_id": "Wealthsimple", "name": "Wealthsimple RRSP", "type": "rrsp", "currency": "CAD", "balance_cents": 1200000},
    {"external_id": "mock-ws-fhsa-1", "institution_id": "Wealthsimple", "name": "Wealthsimple FHSA", "type": "fhsa", "currency": "CAD", "balance_cents": 320000},
]

_MOCK_TRANSACTIONS: list[dict] = [
    {"external_id": "tx-1", "account_external_id": "mock-rbc-cheq-1", "institution_id": "RBC", "amount_cents": -5000, "date": "2025-02-01", "description": "Coffee", "is_income": False},
    {"external_id": "tx-2", "account_external_id": "mock-rbc-cheq-1", "institution_id": "RBC", "amount_cents": 350000, "date": "2025-02-01", "description": "Payroll", "is_income": True},
    {"external_id": "tx-3", "account_external_id": "mock-td-sav-1", "institution_id": "TD", "amount_cents": 1200, "date": "2025-02-15", "description": "Interest", "is_income": True},
]


class MockOpenBankingAdapter:
    """
    Mock adapter returning fixture accounts and transactions.
    Use until real FDX (Consumer-Driven Banking) and accreditation are in place.
    """

    def get_accounts(
        self,
        user_id: str,
        institution_id: str | None = None,
        consent_id: str | None = None,
    ) -> list[OBAccount]:
        accounts = _MOCK_ACCOUNTS
        if institution_id:
            accounts = [a for a in accounts if a["institution_id"] == institution_id]
        return [
            OBAccount(
                external_id=a["external_id"],
                institution_id=a["institution_id"],
                name=a["name"],
                type=a["type"],
                currency=a["currency"],
                balance_cents=a.get("balance_cents"),
            )
            for a in accounts
        ]

    def get_transactions(
        self,
        account_external_id: str,
        institution_id: str,
        from_date: date | None = None,
        to_date: date | None = None,
        consent_id: str | None = None,
    ) -> list[OBTransaction]:
        txs = [t for t in _MOCK_TRANSACTIONS if t["account_external_id"] == account_external_id]
        return [
            OBTransaction(
                external_id=t["external_id"],
                account_external_id=t["account_external_id"],
                institution_id=t["institution_id"],
                amount_cents=t["amount_cents"],
                date=date.fromisoformat(t["date"]) if isinstance(t["date"], str) else t["date"],
                description=t["description"],
                is_income=t.get("is_income"),
            )
            for t in txs
        ]

    def get_balances(
        self,
        user_id: str,
        institution_id: str | None = None,
        consent_id: str | None = None,
    ) -> list[OBBalance]:
        accounts = self.get_accounts(user_id, institution_id, consent_id)
        return [
            OBBalance(
                account_external_id=a.external_id,
                institution_id=a.institution_id,
                balance_cents=a.balance_cents or 0,
                currency=a.currency,
            )
            for a in accounts
        ]


def get_open_banking_adapter() -> OpenBankingAdapter:
    """Return the adapter instance (mock until FDX is live)."""
    return MockOpenBankingAdapter()
