"""Health API tests."""

import pytest


def test_health_ok(client):
    """GET /api/health returns ok when DB is connected."""
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"


def test_health_returns_json(client):
    """Health response is JSON."""
    r = client.get("/api/health")
    assert r.headers["content-type"].startswith("application/json")
