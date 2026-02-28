import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Health check: app, DB, and LLM provider connectivity/config readiness."""
    llm_provider = (getattr(settings, "llm_provider", "openai") or "openai").strip().lower()
    llm_key_configured = False
    if llm_provider == "cursor":
        llm_key_configured = bool((getattr(settings, "cursor_api_key", "") or "").strip())
    elif llm_provider == "openai":
        llm_key_configured = bool((getattr(settings, "openai_api_key", "") or "").strip())

    llm_health = {
        "provider": llm_provider,
        "configured": llm_key_configured,
    }
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        logger.warning(
            "Health check failed: database disconnected (provider=%s, configured=%s)",
            llm_provider,
            llm_key_configured,
        )
        return {"status": "unhealthy", "database": "disconnected", "llm": llm_health}

    logger.info(
        "Health check ok: database connected (provider=%s, configured=%s)",
        llm_provider,
        llm_key_configured,
    )
    return {"status": "ok", "database": "connected", "llm": llm_health}
