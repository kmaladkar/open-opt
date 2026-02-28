"""
API for main agent help. Exposes routing, Canadian rules, and synthesis guidance
so the main agent (or debugging tools) can request help by topic.
"""

from fastapi import APIRouter

from app.agents.help import TOPICS, get_help

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/help/topics")
def list_help_topics():
    """List available help topics the main agent can request."""
    return {"topics": TOPICS}


@router.get("/help")
def agent_help(topic: str = "full"):
    """
    Get guidance for the main agent. Use when the agent needs help with
    routing, Canadian rules, synthesis, recommendation flow, or test/debug routing.
    """
    return {"topic": topic, "content": get_help(topic)}
