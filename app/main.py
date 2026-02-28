import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.database import get_db, init_db
from app.core.config import settings
from app.api import health, auth, households, accounts, goals, agent_help, recommendations

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    provider = (getattr(settings, "llm_provider", "openai") or "openai").strip().lower()
    if provider == "cursor":
        key_ok = bool((getattr(settings, "cursor_api_key", "") or "").strip())
    else:
        key_ok = bool((getattr(settings, "openai_api_key", "") or "").strip())
    logger.info("Open Opt startup complete (llm_provider=%s, api_key_configured=%s)", provider, key_ok)
    yield


app = FastAPI(
    title="Open Opt",
    description="Wealthsimple-style family finance app with open banking and AI recommendations",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(households.router, prefix="/api/households", tags=["households"])
app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"])
app.include_router(goals.router, prefix="/api/goals", tags=["goals"])
app.include_router(recommendations.router, prefix="/api/recommendations", tags=["recommendations"])
app.include_router(agent_help.router, prefix="/api")

STATIC_DIR = Path(__file__).resolve().parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def root():
    return {"app": "Open Opt", "docs": "/docs", "health": "/api/health", "app_ui": "/app"}


@app.get("/app")
def app_ui():
    """Serve the family dashboard and recommendations UI."""
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        return {"error": "Frontend not found"}
    return FileResponse(index_path)
