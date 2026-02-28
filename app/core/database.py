from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.models.base import Base
from app.models.user import User  # noqa: F401
from app.models.household import Household  # noqa: F401
from app.models.household_member import HouseholdMember  # noqa: F401
from app.models.account import Account  # noqa: F401
from app.models.goal import Goal  # noqa: F401 - ensure models are registered


connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=False,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
