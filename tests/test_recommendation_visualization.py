"""Tests for recommendation list visualization payload."""

from app.agents.subagents.visualization import run_recommendation_list_from_context
from app.schemas.recommendations import RecommendationItem


def _sample_context() -> dict:
    return {
        "accounts": [
            {
                "id": 1,
                "name": "RBC Chequing",
                "type": "chequing",
                "account_type": "chequing",
                "institution_id": "RBC",
                "balance_cents": 1_500_000,
            },
            {
                "id": 2,
                "name": "WS TFSA",
                "type": "tfsa",
                "account_type": "tfsa",
                "institution_id": "WEALTHSIMPLE",
                "balance_cents": 5_000_000,
            },
        ],
        "balances": [
            {"account_id": 1, "account_name": "RBC Chequing", "balance_cents": 1_500_000},
            {"account_id": 2, "account_name": "WS TFSA", "balance_cents": 5_000_000},
        ],
        "goals": [{"name": "Kids education", "target_amount_cents": 2_000_000}],
        "contribution_room": {
            "tfsa": {"annual_limit_cents": 700_000, "current_balance_cents": 5_000_000},
            "rrsp": {"estimated_room_cents": 1_100_000, "current_balance_cents": 4_000_000},
            "fhsa": {"estimated_room_lifetime_cents": 2_400_000},
        },
        "resp_eligibility": {"child_beneficiaries": ["Kid A"]},
        "wealthsimple_rates": {"wealthsimple_cash_cad_pct": 4},
    }


def test_auto_recommendations_include_chart_per_recommendation():
    result = run_recommendation_list_from_context(_sample_context(), include_visualization=True, min_recommendations=5)
    recs = result.get("recommendations", [])
    assert recs
    assert all("chart_spec" in rec for rec in recs)
    assert all((rec["chart_spec"] or {}).get("type") == "five_year_projection" for rec in recs)
    assert all(len((rec["chart_spec"] or {}).get("labels", [])) == 6 for rec in recs)
    notes = [(rec.get("chart_spec") or {}).get("rates_note", "") for rec in recs]
    assert all(notes)
    # Each note should be recommendation-specific, not shared boilerplate.
    assert len(set(notes)) == len(notes)


def test_recommendation_item_exposes_chart_spec_field():
    item = RecommendationItem.model_validate(
        {
            "title": "Earn more on idle cash",
            "response": "If you have idle cash, move it to higher interest savings.",
            "chart_spec": {
                "type": "five_year_projection",
                "labels": ["Now", "Year 1"],
                "series_current_dollars": [1000, 1010],
                "series_recommended_dollars": [1000, 1040],
            },
        }
    )
    assert "chart_spec" in item.model_dump()
