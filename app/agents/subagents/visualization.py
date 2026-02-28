"""
Recommendation Visualization agent (parent of recommendation flow).
Invokes GenAI for recommendation content, produces narrative and chart specs (Wealthsimple-style).
Main agent delegates here for all recommendation intents; do not call GenAI recommendation directly from main agent.
"""

from sqlalchemy.orm import Session

from app.agents.subagents import (
    get_household_accounts,
    get_balances,
    get_contribution_room,
    get_family_members,
    get_goals,
    get_resp_eligibility,
)
from app.data.wealthsimple_products import get_savings_rate_comparison
from app.data.canadian_rules import (
    tfsa_annual_limit,
    FHSA_ANNUAL_LIMIT,
    RESP_CESG_BASIC_RATE,
    cesg_additional_rate,
)
from app.core.config import settings


def _gather_context(db: Session, household_id: int) -> dict:
    """Gather household, accounts, goals, and rules for the recommendation prompt."""
    accounts = get_household_accounts(db, household_id)
    balances = get_balances(db, household_id)
    room = get_contribution_room(db, household_id)
    members = get_family_members(db, household_id)
    goals = get_goals(db, household_id)
    resp = get_resp_eligibility(db, household_id)
    ws = get_savings_rate_comparison()
    return {
        "accounts": accounts,
        "balances": balances,
        "contribution_room": room,
        "members": members,
        "goals": goals,
        "resp_eligibility": resp,
        "wealthsimple_rates": ws,
    }


def _build_prompt(context: dict) -> str:
    """Build the GenAI prompt for narrative recommendations."""
    accs = context.get("accounts", [])
    goals_list = context.get("goals", [])
    room = context.get("contribution_room", {})
    resp = context.get("resp_eligibility", {})
    ws = context.get("wealthsimple_rates", {})

    prompt = """You are a Canadian financial advisor. Based on the following household data, provide short, educational recommendations: "best ways to save" and "how to invest income and idle cash." Use plain language. Reference TFSA, RRSP, RESP, FHSA, and emergency savings where relevant.

Household data:
- Accounts (type, name, institution, balance_cents): """
    prompt += str(accs)[:1500] + "\n- Goals: " + str(goals_list)[:800]
    prompt += "\n- Contribution room summary (TFSA/RRSP/FHSA): " + str(room)[:600]
    prompt += "\n- RESP/CESG eligibility: " + str(resp)[:400]
    prompt += "\n- Wealthsimple Cash rate (ongoing): " + str(ws.get("wealthsimple_cash_cad_pct", 4)) + "%"
    prompt += """

Rules: Compare ongoing rates (not just promo). When moving funds from another bank to Wealthsimple would improve outcomes, say so explicitly (e.g. "Moving your RBC savings to Wealthsimple Cash could earn 4% vs 0.5%—approximately $X more per year"). Frame so both the user and Wealthsimple benefit when it's the best option. Use "consider", "suggest"; do not imply execution of trades. Keep response under 400 words."""

    return prompt


def _call_llm(prompt: str) -> str:
    """Call OpenAI for recommendation narrative. Returns template text if no API key."""
    if not (getattr(settings, "openai_api_key", None) and settings.openai_api_key.strip()):
        return (
            "Consider maxing your RESP contributions to get the 20% CESG match (up to $500 per beneficiary per year). "
            "Top up TFSA for tax-free growth ($7,000/year limit). Use RRSP for retirement and FHSA if you're a first-time home buyer. "
            "If you have savings at a big bank earning low interest, moving that balance to Wealthsimple Cash could earn around 4% ongoing—compare to your current rate. "
            "This is educational guidance; check CRA My Account for your exact TFSA/RRSP room."
        )
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
        )
        return (r.choices[0].message.content or "").strip()
    except Exception as e:
        return f"[LLM error: {e}.] " + _call_llm.__doc__ or "Use the template recommendations above."


def _build_chart_spec(context: dict, narrative: str) -> dict | None:
    """
    Produce a Wealthsimple-style chart spec (e.g. before/after interest or goal progress).
    Frontend can render with Chart.js, Recharts, or Plotly.
    """
    balances = context.get("balances", [])
    goals_list = context.get("goals", [])
    if not balances and not goals_list:
        return None
    # Before/after interest comparison: assume one savings account at 0.5% vs Wealthsimple 4%
    savings_accounts = [b for b in balances if "savings" in (b.get("account_name") or "").lower() or "chequing" in (b.get("account_name") or "").lower()]
    total_cents = sum(b.get("balance_cents", 0) for b in savings_accounts)
    if total_cents > 0:
        total_dollars = total_cents / 100
        low_rate = 0.005
        high_rate = 0.04
        interest_low_1y = total_dollars * low_rate
        interest_high_1y = total_dollars * high_rate
        return {
            "type": "before_after_interest",
            "title": "Potential interest: current vs Wealthsimple Cash (4%)",
            "labels": ["Current (0.5%)", "Wealthsimple Cash (4%)"],
            "values_cents": [int(interest_low_1y * 100), int(interest_high_1y * 100)],
            "values_dollars": [round(interest_low_1y, 2), round(interest_high_1y, 2)],
            "period": "1 year",
            "total_balance_cents": total_cents,
        }
    # Goal progress: simple bar
    if goals_list:
        return {
            "type": "goal_progress",
            "title": "Goals",
            "goals": [
                {"name": g.get("name"), "target_amount_cents": g.get("target_amount_cents"), "target_date": g.get("target_date")}
                for g in goals_list[:5]
            ],
        }
    return None


def run_recommendation_visualization(
    db: Session,
    household_id: int,
    include_visualization: bool = True,
) -> dict:
    """
    Main entry: gather context, call GenAI for narrative, optionally produce chart spec.
    Returns { "narrative": str, "chart_spec": dict | None }.
    """
    context = _gather_context(db, household_id)
    prompt = _build_prompt(context)
    narrative = _call_llm(prompt)
    chart_spec = _build_chart_spec(context, narrative) if include_visualization else None
    return {"narrative": narrative, "chart_spec": chart_spec}
