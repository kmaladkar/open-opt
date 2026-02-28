from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db

router = APIRouter()


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Health check: app and DB connectivity."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        return {"status": "unhealthy", "database": "disconnected"}
    return {"status": "ok", "database": "connected"}
