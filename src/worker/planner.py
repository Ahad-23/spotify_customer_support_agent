"""Planner node: decomposes natural language tasks into executable steps."""

from typing import Any

import litellm
from pydantic import BaseModel, Field

from src.worker.config import (
    MAX_PLAN_STEPS,
    OSTICKET_STAFF_PASS,
    OSTICKET_STAFF_USER,
    OSTICKET_URL,
    get_fallbacks,
    get_llm_model,
    safe_llm_completion,
)

from src.worker.prompts import OSTICKET_CONTEXT, PLANNER_SYSTEM, PLANNER_USER
from src.worker.state import PlanStep, TaskWorkerState
from src.worker.utils import extract_json_from_llm_response


def _analyze_support_context(task: str) -> dict[str, Any] | None:
    """Run existing intent/sentiment/device analysis when the task is support-related."""
    try:
        from src.agent.nodes import DEVICE_PATTERNS, ESCALATION_PATTERNS
        from src.agent.sentiment import analyze_customer_sentiment
        from src.data.intent_classifier import classify_intent
    except ImportError:
        return None

    intent = classify_intent(task)
    sentiment = analyze_customer_sentiment(task, history=[], previous_failed_count=0)

    devices = [name for name, pat in DEVICE_PATTERNS.items() if pat.search(task)]

    escalation_reason = None
    for pat, reason in ESCALATION_PATTERNS:
        if pat.search(task):
            escalation_reason = reason
            break

    return {
        "intent": intent,
        "sentiment": sentiment.get("sentiment", "neutral"),
        "frustration_score": sentiment.get("frustration_score", 0.0),
        "devices": devices,
        "escalation_reason": escalation_reason,
        "trigger_hitl": sentiment.get("trigger_hitl", False),
    }


def _format_support_context(ctx: dict[str, Any] | None) -> str:
    if not ctx:
        return ""
    lines = [
        "Support analysis:",
        f"  Intent: {ctx['intent']}",
        f"  Sentiment: {ctx['sentiment']} (frustration: {ctx['frustration_score']:.2f})",
    ]
    if ctx["devices"]:
        lines.append(f"  Devices: {', '.join(ctx['devices'])}")
    if ctx["escalation_reason"]:
        lines.append(f"  Escalation: {ctx['escalation_reason']}")
    return "\n".join(lines)


class PlannerStepItem(BaseModel):
    description: str = Field(default="Step", min_length=1)
    tool: str = Field(default="browser")
    params: dict[str, Any] = Field(default_factory=dict)


class PlannerOutput(BaseModel):
    goal: str = Field(min_length=1)
    needs_clarification: bool = False
    clarification_question: str | None = None
    steps: list[PlannerStepItem] = Field(default_factory=list)


def _parse_plan_response(raw: str) -> tuple[str, str | None, list[PlanStep]]:
    """Parse LLM JSON into (goal, clarification_question, steps). Validates structure via Pydantic."""
    try:
        data = extract_json_from_llm_response(raw)
    except Exception as exc:
        raise ValueError(f"Invalid JSON from planner: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object, got {type(data).__name__}")

    if not data.get("goal") or not str(data["goal"]).strip():
        raise ValueError("Planner response missing 'goal'")

    try:
        parsed = PlannerOutput.model_validate(data)
    except Exception as exc:
        raise ValueError(f"Planner schema validation failed: {exc}") from exc

    if parsed.needs_clarification:
        question = parsed.clarification_question or "Could you clarify your request?"
        return parsed.goal, str(question), []

    if not parsed.steps:
        raise ValueError("Planner response has no steps")
    if len(parsed.steps) > MAX_PLAN_STEPS:
        raise ValueError(f"Plan exceeds {MAX_PLAN_STEPS} steps ({len(parsed.steps)})")

    steps = [
        PlanStep(
            index=i,
            description=s.description,
            tool=s.tool,
            params=s.params,
        )
        for i, s in enumerate(parsed.steps)
    ]

    return parsed.goal, None, steps


async def planner_node(state: TaskWorkerState) -> dict[str, Any]:
    """Generate an execution plan from a natural language task."""
    # If resuming after user clarification with an existing plan, skip re-planning
    if state.plan and state.user_input:
        return {
            "status": "executing",
            "user_input": None,
            "clarification": None,
        }

    support_context = _analyze_support_context(state.task)

    environment = OSTICKET_CONTEXT.format(
        osticket_url=OSTICKET_URL,
        staff_user=OSTICKET_STAFF_USER,
        staff_pass=OSTICKET_STAFF_PASS,
    )

    from src.worker.tools import get_tool_descriptions

    system_prompt = PLANNER_SYSTEM.format(
        max_steps=MAX_PLAN_STEPS,
        tools=get_tool_descriptions(),
        environment=environment,
        staff_user=OSTICKET_STAFF_USER,
        staff_pass=OSTICKET_STAFF_PASS,
    )
    user_prompt = PLANNER_USER.format(
        task=state.task,
        support_context=_format_support_context(support_context),
    )

    response = safe_llm_completion(
        model=get_llm_model(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=1500,
        response_format={"type": "json_object"},
        fallbacks=get_fallbacks() or None,
    )


    raw = response.choices[0].message.content.strip()
    goal, clarification, steps = _parse_plan_response(raw)

    if clarification:
        return {
            "goal": goal,
            "status": "awaiting_user",
            "clarification": clarification,
            "support_context": support_context,
        }

    return {
        "goal": goal,
        "plan": steps,
        "status": "executing",
        "support_context": support_context,
    }
