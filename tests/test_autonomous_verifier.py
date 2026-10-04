"""Tests for autonomous worker verifier node."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from src.worker.state import ActionRecord, TaskWorkerState
from src.worker.tools.registry import ToolRegistry, ToolResult
from src.worker.verifier import _format_action_summary, verifier_node


def test_format_action_summary():
    state = TaskWorkerState(
        task="Test",
        actions=[
            ActionRecord(step_index=0, tool="browser", params={}, output="OK", success=True, timestamp="2026-10-03T12:00:00Z"),
            ActionRecord(step_index=1, tool="browser", params={}, output="Fail", error="err", success=False, timestamp="2026-10-03T12:00:00Z"),
        ],
    )
    summary = _format_action_summary(state)
    assert "Step 0 [browser]: OK" in summary
    assert "Step 1 [browser]: FAIL (err)" in summary


def test_verifier_node_success():
    registry = ToolRegistry()
    mock_tool = AsyncMock()
    mock_tool.name = "browser"
    mock_tool.description = "Browser tool"
    mock_tool.run.return_value = ToolResult(
        success=True,
        output="Ticket #10023: Bluetooth audio skipping, Priority: High, Dept: Audio",
        screenshot="/evidence/ticket_10023.png",
    )
    registry.register(mock_tool)

    state = TaskWorkerState(
        task="Create high priority ticket for Bluetooth audio skipping",
        goal="Ticket created with High priority in Audio department",
        actions=[
            ActionRecord(step_index=0, tool="browser", params={}, output="Ticket created", success=True, timestamp="2026-10-03T12:00:00Z")
        ],
    )

    mock_plan_resp = MagicMock()
    mock_plan_resp.choices = [
        MagicMock(message=MagicMock(content=json.dumps({
            "verification_steps": [
                {"description": "Check ticket details", "tool": "browser", "params": {"action": "read"}}
            ],
            "expected_values": {"priority": "High", "department": "Audio"},
        })))
    ]

    mock_eval_resp = MagicMock()
    mock_eval_resp.choices = [
        MagicMock(message=MagicMock(content=json.dumps({
            "passed": True,
            "details": "All fields match expected values: High priority in Audio department.",
        })))
    ]

    with patch("src.worker.verifier.litellm.completion", side_effect=[mock_plan_resp, mock_eval_resp]):
        update = asyncio.run(verifier_node(state, registry=registry))

    assert update["verified"] is True
    assert update["status"] == "completed"
    assert "/evidence/ticket_10023.png" in update["evidence"]
    assert "Audio department" in update["verification_details"]


def test_verifier_node_failure():
    registry = ToolRegistry()
    mock_tool = AsyncMock()
    mock_tool.name = "browser"
    mock_tool.description = "Browser tool"
    mock_tool.run.return_value = ToolResult(
        success=True,
        output="Ticket #10023: Priority: Low, Dept: General",
    )
    registry.register(mock_tool)

    state = TaskWorkerState(
        task="Create high priority ticket",
        goal="Ticket created with High priority",
    )

    mock_plan_resp = MagicMock()
    mock_plan_resp.choices = [
        MagicMock(message=MagicMock(content=json.dumps({
            "verification_steps": [
                {"description": "Check ticket", "tool": "browser", "params": {}}
            ],
            "expected_values": {"priority": "High"},
        })))
    ]

    mock_eval_resp = MagicMock()
    mock_eval_resp.choices = [
        MagicMock(message=MagicMock(content=json.dumps({
            "passed": False,
            "details": "Priority was Low instead of High.",
        })))
    ]

    with patch("src.worker.verifier.litellm.completion", side_effect=[mock_plan_resp, mock_eval_resp]):
        update = asyncio.run(verifier_node(state, registry=registry))

    assert update["verified"] is False
    assert update["status"] == "failed"


def test_verifier_rejects_ticket_resolution_if_ticket_still_open():
    registry = ToolRegistry()
    mock_tool = AsyncMock()
    mock_tool.name = "browser"
    mock_tool.description = "Browser tool"
    mock_tool.run.return_value = ToolResult(
        success=True,
        output="Ticket info: Status:\tOpen\nPriority:\tNormal\nTicket #370389: Reply posted successfully",
    )
    registry.register(mock_tool)

    state = TaskWorkerState(
        task="Resolve ticket #370389 with closing reply",
        goal="Resolve ticket #370389",
        actions=[
            ActionRecord(step_index=0, tool="browser", params={"action": "click"}, output="Clicked reply", success=True, timestamp="2026-10-03T12:00:00Z"),
            ActionRecord(step_index=1, tool="browser", params={"action": "type"}, output="Typed reply", success=True, timestamp="2026-10-03T12:01:00Z"),
            ActionRecord(step_index=2, tool="browser", params={"action": "click"}, output="Post Reply submitted", success=True, timestamp="2026-10-03T12:02:00Z"),
        ],
    )

    mock_plan_resp = MagicMock()
    mock_plan_resp.choices = [
        MagicMock(message=MagicMock(content=json.dumps({
            "verification_steps": [
                {"description": "Check ticket status", "tool": "browser", "params": {"action": "extract"}}
            ],
            "expected_values": {"status": "Resolved"},
        })))
    ]

    mock_eval_resp = MagicMock()
    mock_eval_resp.choices = [
        MagicMock(message=MagicMock(content=json.dumps({
            "passed": True,
            "details": "Reply was posted successfully",
        })))
    ]

    with patch("src.worker.verifier.litellm.completion", side_effect=[mock_plan_resp, mock_eval_resp]):
        update = asyncio.run(verifier_node(state, registry=registry))

    # Even though LLM falsely said passed: True, the verifier post-check MUST reject it because status is Open
    assert update["verified"] is False
    assert update["status"] == "failed"
    assert "still Open" in update["verification_details"]


def test_verifier_passes_simple_ticket_reply_on_action_trace():
    registry = ToolRegistry()
    mock_tool = AsyncMock()
    mock_tool.name = "browser"
    mock_tool.description = "Browser tool"
    mock_tool.run.return_value = ToolResult(
        success=True,
        output="Ticket header text without explicit sub-strings",
    )
    registry.register(mock_tool)

    state = TaskWorkerState(
        task="go and respond to ticket #930466",
        goal="Respond to ticket #930466 with an AI-generated reply",
        actions=[
            ActionRecord(step_index=0, tool="support_agent", params={"query": "issue"}, output="Troubleshooting steps for Spotify", success=True, timestamp="2026-10-04T11:00:00Z"),
            ActionRecord(step_index=1, tool="browser", params={"action": "type", "selector": "div[contenteditable='true']"}, output="Typed reply", success=True, timestamp="2026-10-04T11:01:00Z"),
            ActionRecord(step_index=2, tool="browser", params={"action": "click", "selector": "input[value='Post Reply']"}, output="Clicked Post Reply", success=True, timestamp="2026-10-04T11:02:00Z"),
        ],
    )

    mock_plan_resp = MagicMock()
    mock_plan_resp.choices = [
        MagicMock(message=MagicMock(content=json.dumps({
            "verification_steps": [
                {"description": "Check page", "tool": "browser", "params": {"action": "extract"}}
            ],
            "expected_values": {"last_message": "from Support containing 'Spotify'"},
        })))
    ]

    # Mock eval where LLM failed due to missing substring in extracted text
    mock_eval_resp = MagicMock()
    mock_eval_resp.choices = [
        MagicMock(message=MagicMock(content=json.dumps({
            "passed": False,
            "details": "The extracted page output does not contain explicit expected text.",
        })))
    ]

    with patch("src.worker.verifier.litellm.completion", side_effect=[mock_plan_resp, mock_eval_resp]):
        update = asyncio.run(verifier_node(state, registry=registry))

    # Should pass because the action execution trace proved support reply was generated and posted successfully
    assert update["verified"] is True
    assert update["status"] == "completed"
    assert "submitted to ticket successfully" in update["verification_details"]


