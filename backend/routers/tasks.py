"""API routes for autonomous task execution."""

from __future__ import annotations

import asyncio
import logging
import re
import sys
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from src.worker.graph import run_task_worker
from src.worker.security import redact_sensitive_data
from src.worker.state import TaskWorkerState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

_TASK_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
_task_lock = asyncio.Lock()
_tasks: dict[str, dict[str, Any]] = {}


class TaskCreate(BaseModel):
    task: str = Field(min_length=1, max_length=4000)


class TaskResumeInput(BaseModel):
    user_input: str = Field(min_length=1, max_length=4000)


class TaskResponse(BaseModel):
    id: str
    status: str
    summary: str
    verified: bool | None = None
    evidence: list[str] = []
    clarification: str | None = None
    plan: list[dict[str, Any]] = []
    memory: dict[str, Any] = {}

    model_config = {"from_attributes": True}


def _run_worker_in_dedicated_loop(
    task: str,
    user_input: str | None = None,
    existing_state: dict[str, Any] | None = None,
) -> TaskWorkerState:
    """Run task worker inside a dedicated event loop with Proactor on Windows.

    Uvicorn on Windows defaults to SelectorEventLoop when running with --reload
    or multiple workers, which lacks asyncio.subprocess support required by
    Playwright. Running in a worker thread with ProactorEventLoop guarantees
    full subprocess and browser automation compatibility without blocking FastAPI.
    """
    if sys.platform == "win32":
        loop = asyncio.ProactorEventLoop()
    else:
        loop = asyncio.new_event_loop()

    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(
            run_task_worker(
                task=task,
                user_input=user_input,
                existing_state=existing_state,
            )
        )
    finally:
        try:
            # Gracefully stop LiteLLM global logging worker if bound to this loop
            try:
                from litellm.litellm_core_utils.logging_worker import GLOBAL_LOGGING_WORKER
                if GLOBAL_LOGGING_WORKER:
                    loop.run_until_complete(GLOBAL_LOGGING_WORKER.stop())
                    GLOBAL_LOGGING_WORKER._queue = None
                    GLOBAL_LOGGING_WORKER._worker_task = None
                    GLOBAL_LOGGING_WORKER._bound_loop = None
            except Exception:
                pass

            # Cancel and drain all lingering tasks before closing the loop
            pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
            for t in pending:
                t.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()
        except Exception:
            pass


async def _execute_task(task_id: str, task_text: str) -> None:
    """Execute autonomous task in the background with thread-safe state synchronization."""
    async with _task_lock:
        if task_id in _tasks:
            _tasks[task_id]["status"] = "running"

    try:
        result = await asyncio.to_thread(_run_worker_in_dedicated_loop, task=task_text)
        serialized = redact_sensitive_data(result.model_dump(mode="json"))
        serialized["id"] = task_id
        async with _task_lock:
            _tasks[task_id] = serialized
    except Exception as exc:
        logger.exception("Task %s execution failed: %s", task_id, exc)
        async with _task_lock:
            _tasks[task_id] = {
                "id": task_id,
                "status": "failed",
                "summary": f"Task execution error: {type(exc).__name__}: {exc}",
                "verified": False,
                "evidence": [],
                "plan": [],
                "memory": {},
            }


@router.post("", response_model=TaskResponse)
async def create_task(body: TaskCreate, bg: BackgroundTasks) -> dict[str, Any]:
    """Submit a natural language task for autonomous execution."""
    task_id = str(uuid.uuid4())[:8]
    initial_record = {
        "id": task_id,
        "status": "planning",
        "summary": "",
        "verified": None,
        "evidence": [],
        "plan": [],
        "memory": {},
        "task": body.task,
    }

    async with _task_lock:
        _tasks[task_id] = initial_record

    bg.add_task(_execute_task, task_id, body.task)
    return initial_record


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str) -> dict[str, Any]:
    """Poll task status and results."""
    if not _TASK_ID_REGEX.match(task_id):
        raise HTTPException(status_code=400, detail="Invalid task ID format")

    async with _task_lock:
        entry = _tasks.get(task_id)

    if entry is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"id": task_id, **entry}


@router.post("/{task_id}/resume", response_model=TaskResponse)
async def resume_task(task_id: str, body: TaskResumeInput, bg: BackgroundTasks) -> dict[str, Any]:
    """Resume a task that is awaiting user clarification."""
    if not _TASK_ID_REGEX.match(task_id):
        raise HTTPException(status_code=400, detail="Invalid task ID format")

    async with _task_lock:
        entry = _tasks.get(task_id)

    if entry is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if entry.get("status") != "awaiting_user":
        raise HTTPException(status_code=400, detail="Task is not awaiting user input")

    async def _resume(tid: str, state: dict, user_input: str) -> None:
        async with _task_lock:
            if tid in _tasks:
                _tasks[tid]["status"] = "running"

        try:
            result = await asyncio.to_thread(
                _run_worker_in_dedicated_loop,
                task=state["task"],
                user_input=user_input,
                existing_state=state,
            )
            serialized = redact_sensitive_data(result.model_dump(mode="json"))
            serialized["id"] = tid
            async with _task_lock:
                _tasks[tid] = serialized
        except Exception as exc:
            logger.exception("Task %s resume failed: %s", tid, exc)
            async with _task_lock:
                _tasks[tid] = {
                    "id": tid,
                    "status": "failed",
                    "summary": f"Resume error: {type(exc).__name__}: {exc}",
                    "verified": False,
                    "evidence": [],
                    "plan": [],
                    "memory": {},
                }

    bg.add_task(_resume, task_id, dict(entry), body.user_input)
    return {"id": task_id, **entry}
