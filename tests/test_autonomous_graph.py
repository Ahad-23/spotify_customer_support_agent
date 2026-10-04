"""Tests for autonomous worker LangGraph state machine and routing."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from src.worker.graph import (
    _route_after_execution,
    _route_after_observation,
    _route_after_planning,
    build_task_worker_graph,
)
from src.worker.state import PlanStep, TaskWorkerState
from src.worker.tools.registry import ToolRegistry, ToolResult


def test_route_after_planning():
    state_executing = TaskWorkerState(task="test", status="executing")
    assert _route_after_planning(state_executing) == "executor"

    state_awaiting = TaskWorkerState(task="test", status="awaiting_user", clarification="Clarify?")
    assert _route_after_planning(state_awaiting) == "__end__"


def test_route_after_observation():
    state_verifying = TaskWorkerState(task="test", status="verifying")
    assert _route_after_observation(state_verifying) == "verifier"

    state_failed = TaskWorkerState(task="test", status="failed")
    assert _route_after_observation(state_failed) == "reporter"

    state_awaiting = TaskWorkerState(task="test", status="awaiting_user")
    assert _route_after_observation(state_awaiting) == "__end__"

    state_exec = TaskWorkerState(task="test", status="executing")
    assert _route_after_observation(state_exec) == "executor"


def test_full_graph_mock_run():
    """Verify that the full LangGraph compiles and completes through the cycles."""
    registry = ToolRegistry()
    mock_tool = AsyncMock()
    mock_tool.name = "mock_tool"
    mock_tool.description = "Test tool"
    mock_tool.run.return_value = ToolResult(
        success=True,
        output="Action completed OK",
        screenshot="/shots/test.png",
    )
    registry.register(mock_tool)

    compiled_graph = build_task_worker_graph(registry)

    # Planner response
    planner_resp = MagicMock()
    planner_resp.choices = [
        MagicMock(message=MagicMock(content=json.dumps({
            "goal": "Test goal",
            "needs_clarification": False,
            "steps": [
                {"description": "Step 1", "tool": "mock_tool", "params": {}},
            ],
        })))
    ]

    # Observer response
    observer_resp = MagicMock()
    observer_resp.choices = [
        MagicMock(message=MagicMock(content=json.dumps({
            "step_succeeded": True,
            "extracted_data": {"key": "val"},
            "should_retry": False,
            "needs_user_input": False,
        })))
    ]

    # Verifier plan response
    verifier_plan_resp = MagicMock()
    verifier_plan_resp.choices = [
        MagicMock(message=MagicMock(content=json.dumps({
            "verification_steps": [
                {"description": "Verify step", "tool": "mock_tool", "params": {}}
            ],
            "expected_values": {"key": "val"},
        })))
    ]

    # Verifier eval response
    verifier_eval_resp = MagicMock()
    verifier_eval_resp.choices = [
        MagicMock(message=MagicMock(content=json.dumps({
            "passed": True,
            "details": "Verified successfully",
        })))
    ]

    llm_side_effects = [
        planner_resp,
        observer_resp,
        verifier_plan_resp,
        verifier_eval_resp,
    ]

    async def _run():
        with (
            patch("src.worker.planner._analyze_support_context", return_value=None),
            patch("litellm.completion", side_effect=llm_side_effects),
        ):
            initial = TaskWorkerState(task="Execute sample task")
            final_state_dict = await compiled_graph.ainvoke(initial.model_dump())
            return TaskWorkerState(**final_state_dict)

    final_state = asyncio.run(_run())

    assert final_state.status == "completed"
    assert final_state.verified is True
    assert "Execution Summary" in final_state.summary
    assert "/shots/test.png" in final_state.evidence
