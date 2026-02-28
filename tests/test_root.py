"""Root and app info endpoints."""

import pytest


def test_root_returns_app_info(client):
    """GET / returns app name and doc links."""
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data["app"] == "Open Opt"
    assert "docs" in data
    assert "health" in data
