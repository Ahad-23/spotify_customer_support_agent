"""
FastAPI backend for SpotifyCares support UI.

Wraps run_support_agent() — does not modify agent/LLM logic.
"""

from contextlib import asynccontextmanager
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import logging
import litellm
from litellm._logging import verbose_logger

litellm.suppress_debug_info = True
litellm.telemetry = False
litellm.num_retries = 3
litellm.turn_off_message_logging = True

# Suppress logging_worker and litellm verbose warnings on event loop changes
verbose_logger.setLevel(logging.ERROR)
logging.getLogger("LiteLLM").setLevel(logging.ERROR)
logging.getLogger("litellm").setLevel(logging.ERROR)
from src.worker.config import silence_litellm_async_logging
silence_litellm_async_logging()

from backend.database import init_db
from backend.routers import agents, sessions, tasks, ws


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="SpotifyCares Support API",
    description="Chat API with HITL handoff for customer support",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r".*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router)
app.include_router(agents.router)
app.include_router(tasks.router)
app.include_router(ws.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


frontend_dist = REPO_ROOT / "frontend-web" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
