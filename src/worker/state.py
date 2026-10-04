"""State definitions for the autonomous task worker."""

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

TaskStatus = Literal[
    "planning",
    "executing",
    "verifying",
    "completed",
    "failed",
    "awaiting_user",
    "done",
]

StepStatus = Literal["pending", "running", "done", "failed", "skipped"]


class PlanStep(BaseModel):
    index: int
    description: str
    tool: str
    params: dict[str, Any] = Field(default_factory=dict)
    status: StepStatus = "pending"
    result: str | None = None
    retries: int = 0
    error: str | None = None


class ActionRecord(BaseModel):
    step_index: int
    tool: str
    params: dict[str, Any] = Field(default_factory=dict)
    output: str = ""
    error: str | None = None
    success: bool = True
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    screenshot: str | None = None


class TaskWorkerState(BaseModel):
    task: str = Field(min_length=1)
    goal: str = Field(default="")
    status: TaskStatus = "planning"
    plan: list[PlanStep] = Field(default_factory=list)
    step_index: int = 0
    actions: list[ActionRecord] = Field(default_factory=list)
    memory: dict[str, Any] = Field(default_factory=dict)
    verified: bool | None = None
    verification_details: str = Field(default="")
    summary: str = Field(default="")
    evidence: list[str] = Field(default_factory=list)
    clarification: str | None = None
    user_input: str | None = None
    max_retries: int = 3
    support_context: dict[str, Any] | None = None
