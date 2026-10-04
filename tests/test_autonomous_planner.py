"""Tests for autonomous worker planner node."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.worker.config import MAX_PLAN_STEPS
from src.worker.planner import (
    _analyze_support_context,
    _format_support_context,
    _parse_plan_response,
    planner_node,
)
from src.worker.state import PlanStep, TaskWorkerState


def test_parse_plan_response_valid():
    sample_json = json.dumps({
        "goal": "Create a high-priority ticket for Bluetooth audio skipping",
        "needs_clarification": False,
        "steps": [
            {
                "description": "Navigate to osTicket login",
                "tool": "browser",
                "params": {"action": "navigate", "url": "http://localhost:8080/scp/login.php"},
            },
            {
                "description": "Log into staff panel",
                "tool": "browser",
                "params": {"action": "fill", "selector": "#userid", "value": "ostadmin"},
            },
        ],
    })

    goal, clar, steps = _parse_plan_response(sample_json)
    assert goal == "Create a high-priority ticket for Bluetooth audio skipping"
    assert clar is None
    assert len(steps) == 2
    assert steps[0].tool == "browser"
    assert steps[0].index == 0
    assert steps[1].index == 1


def test_parse_plan_response_clarification():
    sample_json = json.dumps({
        "goal": "Resolve unspecified customer issue",
        "needs_clarification": True,
        "clarification_question": "What is the customer's email address and specific error?",
    })

    goal, clar, steps = _parse_plan_response(sample_json)
    assert clar == "What is the customer's email address and specific error?"
    assert len(steps) == 0


def test_parse_plan_response_invalid_json():
    with pytest.raises(ValueError, match="Invalid JSON"):
        _parse_plan_response("not valid json at all")


def test_parse_plan_response_missing_goal():
    sample_json = json.dumps({
        "needs_clarification": False,
        "steps": [{"description": "Step 1", "tool": "browser", "params": {}}],
    })
    with pytest.raises(ValueError, match="missing 'goal'"):
        _parse_plan_response(sample_json)


def test_parse_plan_response_exceeds_max_steps():
    raw_steps = [{"description": f"Step {i}", "tool": "browser"} for i in range(MAX_PLAN_STEPS + 5)]
    sample_json = json.dumps({"goal": "Too long", "steps": raw_steps})
    with pytest.raises(ValueError, match="exceeds"):
        _parse_plan_response(sample_json)


def test_analyze_support_context():
    task = "Spotify is skipping songs on my Samsung Galaxy with Bluetooth speaker"
    ctx = _analyze_support_context(task)
    assert ctx is not None
    assert "devices" in ctx
    assert len(ctx["devices"]) > 0
    formatted = _format_support_context(ctx)
    assert "Support analysis:" in formatted
    assert "Intent:" in formatted


def test_planner_node_success():
    import asyncio
    state = TaskWorkerState(task="Create support ticket for john@example.com about bluetooth skipping")

    mock_llm_response = MagicMock()
    mock_llm_response.choices = [
        MagicMock(message=MagicMock(content=json.dumps({
            "goal": "Create support ticket for john@example.com",
            "needs_clarification": False,
            "steps": [
                {"description": "Navigate to osTicket", "tool": "browser", "params": {"action": "navigate"}},
            ],
        })))
    ]

    with patch("src.worker.planner.litellm.completion", return_value=mock_llm_response):
        result = asyncio.run(planner_node(state))

    assert result["goal"] == "Create support ticket for john@example.com"
    assert result["status"] == "executing"
    assert len(result["plan"]) == 1
    assert result["plan"][0].description == "Navigate to osTicket"


def test_planner_node_needs_clarification():
    import asyncio
    state = TaskWorkerState(task="Create ticket")

    mock_llm_response = MagicMock()
    mock_llm_response.choices = [
        MagicMock(message=MagicMock(content=json.dumps({
            "goal": "Create unknown ticket",
            "needs_clarification": True,
            "clarification_question": "Who is this ticket for and what is the issue?",
        })))
    ]

    with patch("src.worker.planner.litellm.completion", return_value=mock_llm_response):
        result = asyncio.run(planner_node(state))

    assert result["status"] == "awaiting_user"
    assert "Who is this ticket for" in result["clarification"]
