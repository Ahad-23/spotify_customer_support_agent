"""Observer node: interprets action results and decides what to do next."""

import json
from typing import Any

import litellm
from pydantic import BaseModel, Field

from src.worker.config import get_fallbacks, get_llm_model, safe_llm_completion
from src.worker.prompts import OBSERVER_SYSTEM, OBSERVER_USER
from src.worker.state import PlanStep, TaskWorkerState
from src.worker.utils import extract_json_from_llm_response




class ObserverOutput(BaseModel):
    step_succeeded: bool = False
    extracted_data: dict[str, Any] = Field(default_factory=dict)
    should_retry: bool = False
    retry_reason: str | None = None
    alternative_params: dict[str, Any] | None = None
    alternative_steps: list[dict[str, Any]] | None = None
    skip_step: bool = False
    needs_user_input: bool = False
    user_question: str | None = None
    reasoning: str = Field(default="")


def _parse_observation(raw: str) -> dict[str, Any]:
    """Parse LLM observation JSON with robust extraction, Pydantic validation, and safe failure defaults."""
    try:
        data = extract_json_from_llm_response(raw)
        if isinstance(data, dict):
            parsed = ObserverOutput.model_validate(data)
            return parsed.model_dump()
    except Exception:
        pass

    return {
        "step_succeeded": False,
        "extracted_data": {},
        "should_retry": True,
        "retry_reason": "Failed to parse observer response",
        "alternative_params": None,
        "alternative_steps": None,
        "skip_step": False,
        "needs_user_input": False,
        "user_question": None,
        "reasoning": raw[:200] if isinstance(raw, str) else "",
    }


def _format_remaining_steps(state: TaskWorkerState) -> str:
    remaining = state.plan[state.step_index + 1:]
    if not remaining:
        return "(none — this was the last step)"
    return "\n".join(f"  {s.index}: {s.description}" for s in remaining)


async def observer_node(state: TaskWorkerState) -> dict[str, Any]:
    """Interpret the last action result and decide what to do next."""
    if not state.actions:
        return {"status": "failed", "summary": "No actions recorded to observe"}

    last_action = state.actions[-1]
    step = state.plan[state.step_index]

    user_prompt = OBSERVER_USER.format(
        step_index=step.index,
        step_description=step.description,
        tool=last_action.tool,

        params=json.dumps(last_action.params, default=str),
        success=last_action.success,
        output=last_action.output[:1000],
        error=last_action.error or "None",
        memory=json.dumps(state.memory, default=str),
        remaining=_format_remaining_steps(state),
    )

    response = safe_llm_completion(
        model=get_llm_model(),
        messages=[
            {"role": "system", "content": OBSERVER_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
        max_tokens=600,
        response_format={"type": "json_object"},
        fallbacks=get_fallbacks() or None,
    )

    obs = _parse_observation(response.choices[0].message.content.strip())


    updated_memory = {**state.memory, **obs.get("extracted_data", {})}
    updated_plan = list(state.plan)

    # 1. Step succeeded
    if obs.get("step_succeeded"):
        updated_plan[state.step_index] = step.model_copy(
            update={"status": "done", "result": last_action.output[:500]}
        )
        next_index = state.step_index + 1
        if next_index >= len(updated_plan):
            return {
                "plan": updated_plan,
                "step_index": next_index,
                "memory": updated_memory,
                "status": "verifying",
            }
        return {
            "plan": updated_plan,
            "step_index": next_index,
            "memory": updated_memory,
            "status": "executing",
        }

    # 2. Step failed — check if user input is strictly required
    if obs.get("needs_user_input"):
        updated_plan[state.step_index] = step.model_copy(update={"status": "failed"})
        return {
            "plan": updated_plan,
            "memory": updated_memory,
            "status": "awaiting_user",
            "clarification": obs.get("user_question") or "The agent needs your input to continue.",
        }

    # 3. Step failed — real-time alternative steps injected by observer
    alt_steps = obs.get("alternative_steps")
    if alt_steps and isinstance(alt_steps, list) and len(alt_steps) > 0:
        updated_plan[state.step_index] = step.model_copy(
            update={
                "status": "skipped",
                "error": f"Adapted: {obs.get('reasoning', '')[:150]}",
            }
        )
        # Construct and insert alternative PlanSteps right after current step
        new_steps = []
        for i, raw_s in enumerate(alt_steps):
            new_steps.append(
                PlanStep(
                    index=state.step_index + 1 + i,
                    description=str(raw_s.get("description") or f"Alternative step {i+1}"),
                    tool=str(raw_s.get("tool") or "browser"),
                    params=raw_s.get("params") or {},
                )
            )
        # Splice into plan
        updated_plan = (
            updated_plan[:state.step_index + 1]
            + new_steps
            + updated_plan[state.step_index + 1:]
        )
        # Re-index all steps
        for idx, s in enumerate(updated_plan):
            updated_plan[idx] = s.model_copy(update={"index": idx})

        return {
            "plan": updated_plan,
            "step_index": state.step_index + 1,
            "memory": updated_memory,
            "status": "executing",
        }

    # 4. Step failed — retry with alternative parameters if retries remain
    if obs.get("should_retry") and step.retries < state.max_retries:
        new_params = obs.get("alternative_params") or step.params
        updated_plan[state.step_index] = step.model_copy(
            update={
                "status": "pending",
                "retries": step.retries + 1,
                "params": new_params,
                "error": obs.get("retry_reason") or "Retrying with updated parameters",
            }
        )
        return {"plan": updated_plan, "memory": updated_memory, "status": "executing"}

    # 5. Retries exhausted or step non-critical/skipped — DO NOT fail the entire task!
    # Mark current step failed or skipped, and continue executing remaining steps.
    step_status = "skipped" if obs.get("skip_step") else "failed"
    step_error = obs.get("reasoning", "")[:200] or obs.get("retry_reason") or last_action.error or "Step failed"
    updated_plan[state.step_index] = step.model_copy(
        update={"status": step_status, "error": step_error}
    )

    next_index = state.step_index + 1
    if next_index >= len(updated_plan):
        # Reached the end of plan -> let verifier independently validate goal achievement
        return {
            "plan": updated_plan,
            "step_index": next_index,
            "memory": updated_memory,
            "status": "verifying",
        }

    # Advance to next step and keep executing
    return {
        "plan": updated_plan,
        "step_index": next_index,
        "memory": updated_memory,
        "status": "executing",
    }

