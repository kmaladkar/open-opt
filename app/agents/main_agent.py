"""
Main agent (team lead): routes questions to subagents and synthesizes answers.
Uses LangGraph StateGraph. For recommendation intents, delegates to Visualization agent only.
"""

import os
from typing import Literal, TypedDict

from langgraph.graph import StateGraph, END
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
    tax_loss_harvesting_eligibility,
)
from app.agents.subagents.test_debug import run_test_debug, run_test_writer, run_qa
from app.agents.subagents.visualization import run_recommendation_visualization


class AgentState(TypedDict, total=False):
    question: str
    household_id: int
    user_id: int
    intent: Literal["general", "recommendation"]
    banking_data: dict
    investing_data: dict
    family_data: dict
    research_data: dict
    response: str
    chart_spec: dict | None  # from Visualization agent for recommendations API
    db: Session  # passed at invoke, not serialized
    test_debug_data: dict


def _get_db(state: AgentState) -> Session | None:
    return state.get("db")


def route_node(state: AgentState) -> AgentState:
    """Set intent: recommendation, test_debug, or general."""
    q = (state.get("question") or "").lower()
    recommendation_keywords = [
        "recommend", "best way to save", "how to invest", "what should i do",
        "suggest", "advice", "best options", "move to wealthsimple",
    ]
    test_debug_keywords = [
        "write test", "run test", "debug", "fix failing", "pytest", "add tests",
        "verify", "reproduce bug", "qa", "coverage", "regression test",
    ]
    if any(k in q for k in recommendation_keywords):
        return {"intent": "recommendation"}
    if any(k in q for k in test_debug_keywords):
        return {"intent": "test_debug"}
    return {"intent": "general"}


def call_banking_node(state: AgentState) -> AgentState:
    db = _get_db(state)
    if not db or state.get("household_id") is None:
        return {"banking_data": {"error": "Missing db or household_id"}}
    hid = state["household_id"]
    accounts = get_household_accounts(db, hid)
    balances = get_balances(db, hid)
    return {"banking_data": {"accounts": accounts, "balances": balances}}


def call_investing_node(state: AgentState) -> AgentState:
    db = _get_db(state)
    if not db or state.get("household_id") is None:
        return {"investing_data": {"error": "Missing db or household_id"}}
    room = get_contribution_room(db, state["household_id"])
    th = tax_loss_harvesting_eligibility(db, state["household_id"])
    return {"investing_data": {"contribution_room": room, "tax_loss_harvesting": th}}


def call_family_node(state: AgentState) -> AgentState:
    db = _get_db(state)
    if not db or state.get("household_id") is None:
        return {"family_data": {"error": "Missing db or household_id"}}
    members = get_family_members(db, state["household_id"])
    goals = get_goals(db, state["household_id"])
    resp = get_resp_eligibility(db, state["household_id"])
    return {"family_data": {"members": members, "goals": goals, "resp_eligibility": resp}}


def call_research_node(state: AgentState) -> AgentState:
    return {
        "research_data": {
            "tfsa": get_tfsa_limit(2025),
            "rrsp": get_rrsp_limit(2025),
            "fhsa": get_fhsa_limits(),
            "superficial_loss": get_superficial_loss_rules(),
        }
    }


def synthesize_node(state: AgentState) -> AgentState:
    """Build a text response from subagent data. (No LLM in main agent; that's in Visualization.)"""
    parts = []
    if state.get("banking_data") and "accounts" in (state.get("banking_data") or {}):
        b = state["banking_data"]
        parts.append(f"Accounts: {len(b.get('accounts', []))} accounts; balances available.")
    if state.get("investing_data"):
        parts.append("Contribution room and tax-loss harvesting eligibility gathered.")
    if state.get("family_data"):
        parts.append("Household members, goals, and RESP eligibility gathered.")
    if state.get("research_data"):
        parts.append("Canadian rules (TFSA, RRSP, FHSA, superficial loss) loaded.")
    response = " ".join(parts) if parts else "No data gathered. Ask for recommendations to get personalized advice, or ask about accounts, goals, or Canadian rules."
    return {"response": response}


def route_next(state: AgentState) -> Literal["call_banking", "visualization", "call_test_debug"]:
    """After route: visualization for recommendation, call_test_debug for tests/debug, else call_banking."""
    if state.get("intent") == "recommendation":
        return "visualization"
    if state.get("intent") == "test_debug":
        return "call_test_debug"
    return "call_banking"


def call_test_debug_node(state: AgentState) -> AgentState:
    """Run Test & Debug, Test Writer, or QA based on question; return summary in response."""
    q = state.get("question") or ""
    workspace = state.get("workspace_root") or os.getcwd()
    if "qa" in q.lower() or "verify" in q.lower() or "reproduce" in q.lower():
        out = run_qa(q, workspace)
    elif "write test" in q.lower() or "coverage" in q.lower() or "regression" in q.lower():
        out = run_test_writer(q, workspace)
    else:
        out = run_test_debug(q, workspace)
    return {"test_debug_data": out, "response": out.get("summary", "")}


def visualization_node(state: AgentState) -> AgentState:
    """
    Recommendation Visualization agent: parent of recommendation flow.
    Calls GenAI for narrative and produces chart spec (Wealthsimple-style).
    """
    db = _get_db(state)
    household_id = state.get("household_id")
    if not db or household_id is None:
        return {"response": "Missing db or household_id for recommendations.", "chart_spec": None}
    out = run_recommendation_visualization(db, household_id, include_visualization=True)
    return {"response": out["narrative"], "chart_spec": out.get("chart_spec")}


def build_main_agent_graph():
    """Build and compile the main agent LangGraph graph."""
    graph = StateGraph(AgentState)

    graph.add_node("route", route_node)
    graph.add_node("call_banking", call_banking_node)
    graph.add_node("call_investing", call_investing_node)
    graph.add_node("call_family", call_family_node)
    graph.add_node("call_research", call_research_node)
    graph.add_node("synthesize", synthesize_node)
    graph.add_node("visualization", visualization_node)
    graph.add_node("call_test_debug", call_test_debug_node)

    graph.set_entry_point("route")

    graph.add_conditional_edges("route", route_next, path_map={
        "call_banking": "call_banking",
        "visualization": "visualization",
        "call_test_debug": "call_test_debug",
    })
    graph.add_edge("call_banking", "call_investing")
    graph.add_edge("call_investing", "call_family")
    graph.add_edge("call_family", "call_research")
    graph.add_edge("call_research", "synthesize")
    graph.add_edge("synthesize", END)

    graph.add_edge("visualization", END)
    graph.add_edge("call_test_debug", END)

    return graph.compile()


# Singleton compiled graph
_main_graph = None


def get_main_agent_graph():
    global _main_graph
    if _main_graph is None:
        _main_graph = build_main_agent_graph()
    return _main_graph


def run_main_agent(
    question: str,
    household_id: int,
    user_id: int,
    db: Session,
) -> dict:
    """
    Run the main agent. Returns {"response": str, "chart_spec": dict | None}.
    chart_spec is set when intent is recommendation (from Visualization agent).
    """
    graph = get_main_agent_graph()
    initial: AgentState = {
        "question": question,
        "household_id": household_id,
        "user_id": user_id,
        "db": db,
        "banking_data": {},
        "investing_data": {},
        "family_data": {},
        "research_data": {},
    }
    result = graph.invoke(initial)
    return {
        "response": result.get("response") or "",
        "chart_spec": result.get("chart_spec"),
    }
