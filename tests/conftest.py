"""
Pytest fixtures for Open Opt. Uses an in-memory SQLite DB so tests don't touch dev data.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.database import get_db
from app.models.base import Base
from app.models.user import User  # noqa: F401
from app.models.household import Household  # noqa: F401
from app.models.household_member import HouseholdMember  # noqa: F401
from app.models.account import Account  # noqa: F401
from app.models.goal import Goal  # noqa: F401
from app.models.transaction import Transaction  # noqa: F401


# In-memory SQLite for tests
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session")
def test_db_engine():
    """Create tables once per test session."""
    Base.metadata.create_all(bind=test_engine)
    return test_engine


@pytest.fixture
def db_session(test_db_engine):
    """Fresh DB session per test (transaction rollback or new session)."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(test_db_engine):
    """FastAPI TestClient with in-memory DB. Import app after override to avoid circular import."""
    from app.main import app

    app.dependency_overrides[get_db] = override_get_db
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
