"""Tests for autonomous worker observer node."""

import asyncio
import json
from unittest.mock import MagicMock, patch

from src.worker.observer import (
    _format_remaining_steps,
    _parse_observation,
    observer_node,
)
from src.worker.state import ActionRecord, PlanStep, TaskWorkerState


def test_parse_observation_success():
    raw = json.dumps({
        "step_succeeded": True,
        "extracted_data": {"ticket_id": "10023", "status": "Open"},
        "should_retry": False,
        "needs_user_input": False,
        "reasoning": "Ticket created with ID 10023",
    })
    obs = _parse_observation(raw)
    assert obs["step_succeeded"] is True
    assert obs["extracted_data"]["ticket_id"] == "10023"
    assert obs["should_retry"] is False


def test_parse_observation_invalid_json():
    obs = _parse_observation("broken json")
    assert obs["step_succeeded"] is False
    assert obs["should_retry"] is True


def test_format_remaining_steps():
    state = TaskWorkerState(
        task="Test",
        plan=[
            PlanStep(index=0, description="Step 0", tool="browser"),
            PlanStep(index=1, description="Step 1", tool="browser"),
            PlanStep(index=2, description="Step 2", tool="browser"),
        ],
        step_index=0,
    )
    rem = _format_remaining_steps(state)
    assert "Step 1" in rem
    assert "Step 2" in rem


def test_observer_advances_on_success():
    state = TaskWorkerState(
        task="Test",
        plan=[
            PlanStep(index=0, description="Step 0", tool="browser"),
            PlanStep(index=1, description="Step 1", tool="browser"),
        ],
        step_index=0,
        actions=[
            ActionRecord(
                step_index=0,
                tool="browser",
                params={},
                output="Navigated to page",
                success=True,
            )
        ],
    )

    mock_llm_response = MagicMock()
    mock_llm_response.choices = [
        MagicMock(message=MagicMock(content=json.dumps({
            "step_succeeded": True,
            "extracted_data": {"page": "login"},
            "should_retry": False,
            "needs_user_input": False,
            "reasoning": "Page opened",
        })))
    ]

    with patch("src.worker.observer.litellm.completion", return_value=mock_llm_response):
        update = asyncio.run(observer_node(state))

    assert update["step_index"] == 1
    assert update["plan"][0].status == "done"
    assert update["memory"]["page"] == "login"


def test_observer_triggers_verification_at_end():
    state = TaskWorkerState(
        task="Test",
        plan=[PlanStep(index=0, description="Final step", tool="browser")],
        step_index=0,
        actions=[
            ActionRecord(
                step_index=0,
                tool="browser",
                params={},
                output="Form submitted",
                success=True,
            )
        ],
    )

    mock_llm_response = MagicMock()
    mock_llm_response.choices = [
        MagicMock(message=MagicMock(content=json.dumps({
            "step_succeeded": True,
            "extracted_data": {"ticket_id": "999"},
            "should_retry": False,
            "needs_user_input": False,
        })))
    ]

    with patch("src.worker.observer.litellm.completion", return_value=mock_llm_response):
        update = asyncio.run(observer_node(state))

    assert update["status"] == "verifying"
    assert update["plan"][0].status == "done"


def test_observer_retries_on_failure():
    state = TaskWorkerState(
        task="Test",
        plan=[PlanStep(index=0, description="Click submit", tool="browser", retries=0)],
        step_index=0,
        actions=[
            ActionRecord(
                step_index=0,
                tool="browser",
                params={"action": "click", "selector": "#submit"},
                output="",
                error="Timeout",
                success=False,
            )
        ],
    )

    mock_llm_response = MagicMock()
    mock_llm_response.choices = [
        MagicMock(message=MagicMock(content=json.dumps({
            "step_succeeded": False,
            "extracted_data": {},
            "should_retry": True,
            "retry_reason": "Element timed out, retry with alternative selector",
            "alternative_params": {"action": "click", "selector": "input[type='submit']"},
            "needs_user_input": False,
        })))
    ]

    with patch("src.worker.observer.litellm.completion", return_value=mock_llm_response):
        update = asyncio.run(observer_node(state))

    assert update["plan"][0].status == "pending"
    assert update["plan"][0].retries == 1
    assert update["plan"][0].params["selector"] == "input[type='submit']"


def test_observer_requests_clarification_on_ambiguity():
    state = TaskWorkerState(
        task="Test",
        plan=[PlanStep(index=0, description="Select customer", tool="browser")],
        step_index=0,
        actions=[
            ActionRecord(
                step_index=0,
                tool="browser",
                params={},
                output="Found 3 matches for John Doe",
                success=True,
            )
        ],
    )

    mock_llm_response = MagicMock()
    mock_llm_response.choices = [
        MagicMock(message=MagicMock(content=json.dumps({
            "step_succeeded": False,
            "extracted_data": {},
            "should_retry": False,
            "needs_user_input": True,
            "user_question": "Found multiple users named John Doe. Which email should I use?",
        })))
    ]

    with patch("src.worker.observer.litellm.completion", return_value=mock_llm_response):
        update = asyncio.run(observer_node(state))

    assert update["status"] == "awaiting_user"
    assert "multiple users" in update["clarification"]


def test_observer_injects_alternative_steps_on_failure():
    state = TaskWorkerState(
        task="Search user",
        plan=[
            PlanStep(index=0, description="Type user into search", tool="browser"),
            PlanStep(index=1, description="View profile", tool="browser"),
        ],
        step_index=0,
        actions=[
            ActionRecord(
                step_index=0,
                tool="browser",
                params={"action": "type", "selector": "#search", "text": "Dev Soni"},
                output="",
                error="Selector not found",
                success=False,
            )
        ],
    )

    mock_llm_response = MagicMock()
    mock_llm_response.choices = [
        MagicMock(message=MagicMock(content=json.dumps({
            "step_succeeded": False,
            "extracted_data": {},
            "should_retry": False,
            "alternative_steps": [
                {
                    "description": "Click Dev Soni link directly in user table",
                    "tool": "browser",
                    "params": {"action": "click", "text": "Dev Soni"},
                }
            ],
            "needs_user_input": False,
            "reasoning": "Search input missing, clicking user hyperlink directly instead",
        })))
    ]

    with patch("src.worker.observer.litellm.completion", return_value=mock_llm_response):
        update = asyncio.run(observer_node(state))

    assert update["status"] == "executing"
    assert update["step_index"] == 1
    assert len(update["plan"]) == 3  # Original step 0 (skipped) + alternative step + original step 1
    assert update["plan"][0].status == "skipped"
    assert update["plan"][1].description == "Click Dev Soni link directly in user table"
    assert update["plan"][1].params["text"] == "Dev Soni"


def test_observer_exhausted_retries_does_not_fail_entire_task():
    state = TaskWorkerState(
        task="Lookup user",
        plan=[
            PlanStep(index=0, description="Search user", tool="browser", retries=3),
            PlanStep(index=1, description="Inspect profile", tool="browser"),
        ],
        step_index=0,
        actions=[
            ActionRecord(
                step_index=0,
                tool="browser",
                params={},
                output="",
                error="Search failed",
                success=False,
            )
        ],
    )

    mock_llm_response = MagicMock()
    mock_llm_response.choices = [
        MagicMock(message=MagicMock(content=json.dumps({
            "step_succeeded": False,
            "extracted_data": {},
            "should_retry": False,
            "skip_step": False,
            "needs_user_input": False,
            "reasoning": "Search failed after retries, proceed to next step",
        })))
    ]

    with patch("src.worker.observer.litellm.completion", return_value=mock_llm_response):
        update = asyncio.run(observer_node(state))

    # Does NOT fail the overall task, advances to next step
    assert update["status"] == "executing"
    assert update["step_index"] == 1
    assert update["plan"][0].status == "failed"

