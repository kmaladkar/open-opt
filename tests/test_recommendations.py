"""Recommendations API smoke tests."""

import pytest


def test_recommendations_requires_auth(client):
    """POST /api/recommendations without auth returns 401."""
    r = client.post(
        "/api/recommendations",
        json={"question": "How should I save for retirement?"},
    )
    assert r.status_code == 401
