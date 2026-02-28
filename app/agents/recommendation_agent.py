"""
Recommendation agent: queries the database via tools, then retrieves recommendations
and visualizes them (narrative + chart spec).

Flow: run query tools → build context → get recommendations (LLM) → visualize (chart spec).
All DB access goes through explicit tools so the agent "creates the queries" for retrieval.
"""

from typing import Any, Callable

from sqlalchemy.orm import Session

from app.agents.subagents import (
    get_household_accounts,
    get_balances,
    get_contribution_room,
    get_family_members,
    get_goals,
    get_resp_eligibility,
    get_tfsa_limit,
    get_rrsp_limit,
    get_fhsa_limits,
    get_superficial_loss_rules,
)
from app.agents.subagents.visualization import (
    run_recommendation_from_context,
    run_recommendation_list_from_context,
)
from app.data.wealthsimple_products import get_savings_rate_comparison
from app.services.transaction_patterns import get_transaction_patterns_for_household


# ---------------------------------------------------------------------------
# Tools: each tool queries the DB and returns data for the recommendation context.
# The agent invokes these to "create the queries" for retrieval.
# ---------------------------------------------------------------------------

def tool_query_accounts(db: Session, household_id: int) -> list[dict]:
    """Query: list all accounts for the household (type, name, institution, balance)."""
    return get_household_accounts(db, household_id)


def tool_query_balances(db: Session, household_id: int) -> list[dict]:
    """Query: current balances for all household accounts."""
    return get_balances(db, household_id)


def tool_query_goals(db: Session, household_id: int) -> list[dict]:
    """Query: household goals (emergency, education, retirement, home)."""
    return get_goals(db, household_id)


def tool_query_family_members(db: Session, household_id: int) -> list[dict]:
    """Query: household members (role, birth_year) for RESP/eligibility."""
    return get_family_members(db, household_id)


def tool_query_transaction_patterns(db: Session, household_id: int, days_back: int = 90) -> dict:
    """Query: pay patterns (income/expense, recurring vs one-off) across household accounts."""
    return get_transaction_patterns_for_household(db, household_id, days_back=days_back)


def tool_query_contribution_room(db: Session, household_id: int) -> dict:
    """Query: TFSA/RRSP/FHSA contribution room summary."""
    return get_contribution_room(db, household_id)


def tool_query_resp_eligibility(db: Session, household_id: int) -> dict:
    """Query: RESP and CESG eligibility for the household."""
    return get_resp_eligibility(db, household_id)


def tool_query_canadian_rules() -> dict:
    """Query: Canadian limits (TFSA, RRSP, FHSA) and superficial loss rules (no DB)."""
    return {
        "tfsa_limit": get_tfsa_limit(2025),
        "rrsp_limit": get_rrsp_limit(2025),
        "fhsa_limits": get_fhsa_limits(),
        "superficial_loss_rules": get_superficial_loss_rules(),
    }


def tool_query_wealthsimple_rates() -> dict:
    """Query: Wealthsimple product snapshot for rate comparison (no DB)."""
    return get_savings_rate_comparison()


# Registry of tools for documentation / programmatic use.
# Each entry: name, description, function(db, household_id, **kwargs) or function(**kwargs)
RECOMMENDATION_AGENT_TOOLS: list[dict[str, Any]] = [
    {"name": "query_accounts", "description": "List all accounts for the household", "fn": tool_query_accounts},
    {"name": "query_balances", "description": "Current balances for household accounts", "fn": tool_query_balances},
    {"name": "query_goals", "description": "Household goals (emergency, education, retirement, home)", "fn": tool_query_goals},
    {"name": "query_family_members", "description": "Household members for RESP/eligibility", "fn": tool_query_family_members},
    {"name": "query_transaction_patterns", "description": "Pay patterns (income/expense, recurring) across accounts", "fn": tool_query_transaction_patterns},
    {"name": "query_contribution_room", "description": "TFSA/RRSP/FHSA contribution room", "fn": tool_query_contribution_room},
    {"name": "query_resp_eligibility", "description": "RESP and CESG eligibility", "fn": tool_query_resp_eligibility},
    {"name": "query_canadian_rules", "description": "Canadian limits and tax rules", "fn": lambda db, h: tool_query_canadian_rules()},
    {"name": "query_wealthsimple_rates", "description": "Wealthsimple rates for comparison", "fn": lambda db, h: tool_query_wealthsimple_rates()},
]


def gather_context_via_tools(db: Session, household_id: int, days_back: int = 90) -> dict:
    """
    Run all query tools and merge results into a single context dict.
    This is the "agent" step that creates and executes the queries for retrieval.
    """
    context = {}
    context["accounts"] = tool_query_accounts(db, household_id)
    context["balances"] = tool_query_balances(db, household_id)
    context["goals"] = tool_query_goals(db, household_id)
    context["members"] = tool_query_family_members(db, household_id)
    context["transaction_patterns"] = tool_query_transaction_patterns(db, household_id, days_back=days_back)
    context["contribution_room"] = tool_query_contribution_room(db, household_id)
    context["resp_eligibility"] = tool_query_resp_eligibility(db, household_id)
    context["canadian_rules"] = tool_query_canadian_rules()
    context["wealthsimple_rates"] = tool_query_wealthsimple_rates()
    return context


def run_recommendation_agent(
    db: Session,
    household_id: int,
    question: str = "",
    include_visualization: bool = True,
    days_back: int = 90,
) -> dict:
    """
    Run the recommendation agent: query DB via tools → build context → get recommendations → visualize.

    Returns { "response": str, "chart_spec": dict | None }.
    """
    # 1. Create queries and retrieve data (tools)
    context = gather_context_via_tools(db, household_id, days_back=days_back)
    context["question"] = (question or "").strip()
    # 2. Get recommendations (LLM) and visualize (chart spec)
    result = run_recommendation_from_context(context, include_visualization=include_visualization)
    return {
        "response": result["narrative"],
        "chart_spec": result.get("chart_spec"),
    }


def run_auto_recommendations_list(
    db: Session,
    household_id: int,
    include_visualization: bool = True,
    days_back: int = 90,
    min_recommendations: int = 5,
) -> dict:
    """
    Run the recommendation agent to produce a list of 5+ recommendations (title + response)
    and one chart spec. Used by GET /api/recommendations/auto.
    Returns { "recommendations": [ { "title", "response" }, ... ], "chart_spec": dict | None }.
    """
    context = gather_context_via_tools(db, household_id, days_back=days_back)
    context["question"] = ""
    result = run_recommendation_list_from_context(
        context,
        include_visualization=include_visualization,
        min_recommendations=min_recommendations,
    )
    return {
        "recommendations": result.get("recommendations", []),
        "chart_spec": result.get("chart_spec"),
    }
