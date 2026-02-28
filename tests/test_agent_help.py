"""Agent help API tests."""

import pytest


def test_agent_help_topics(client):
    """GET /api/agent/help/topics returns list of topics."""
    r = client.get("/api/agent/help/topics")
    assert r.status_code == 200
    data = r.json()
    assert "topics" in data
    topics = data["topics"]
    assert "routing" in topics
    assert "canadian_rules" in topics
    assert "synthesis" in topics
    assert "full" in topics


def test_agent_help_default_topic(client):
    """GET /api/agent/help returns full help by default."""
    r = client.get("/api/agent/help")
    assert r.status_code == 200
    data = r.json()
    assert data["topic"] == "full"
    assert "content" in data
    assert "ROUTING" in data["content"]
    assert "CANADIAN RULES" in data["content"].upper() or "Canadian" in data["content"]


def test_agent_help_routing_topic(client):
    """GET /api/agent/help?topic=routing returns routing guidance."""
    r = client.get("/api/agent/help", params={"topic": "routing"})
    assert r.status_code == 200
    data = r.json()
    assert data["topic"] == "routing"
    assert "BANKING" in data["content"]
    assert "INVESTING" in data["content"]
    assert "VISUALIZATION" in data["content"]


def test_agent_help_canadian_rules_topic(client):
    """GET /api/agent/help?topic=canadian_rules returns Canadian rules summary."""
    r = client.get("/api/agent/help", params={"topic": "canadian_rules"})
    assert r.status_code == 200
    data = r.json()
    assert data["topic"] == "canadian_rules"
    assert "TFSA" in data["content"]
    assert "RRSP" in data["content"]
    assert "RESP" in data["content"] or "CESG" in data["content"]
