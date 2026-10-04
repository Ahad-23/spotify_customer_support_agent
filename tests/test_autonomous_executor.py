"""Tests for autonomous worker executor node."""

import asyncio
from unittest.mock import AsyncMock

from src.worker.executor import executor_node
from src.worker.state import PlanStep, TaskWorkerState
from src.worker.tools.registry import ToolRegistry, ToolResult


def test_executor_node_runs_step():
    registry = ToolRegistry()
    mock_tool = AsyncMock()
    mock_tool.name = "mock_browser"
    mock_tool.description = "Mock tool for tests"
    mock_tool.run.return_value = ToolResult(
        success=True,
        output="Page navigated successfully",
        screenshot="/path/to/shot1.png",
    )
    registry.register(mock_tool)

    state = TaskWorkerState(
        task="Test task",
        plan=[
            PlanStep(
                index=0,
                description="Open page",
                tool="mock_browser",
                params={"action": "navigate", "url": "http://example.com"},
            )
        ],
        step_index=0,
    )

    update = asyncio.run(executor_node(state, registry=registry))

    assert len(update["actions"]) == 1
    action = update["actions"][0]
    assert action.tool == "mock_browser"
    assert action.success is True
    assert action.output == "Page navigated successfully"
    assert action.screenshot == "/path/to/shot1.png"
    assert "/path/to/shot1.png" in update["evidence"]


def test_executor_node_handles_tool_failure():
    registry = ToolRegistry()
    mock_tool = AsyncMock()
    mock_tool.name = "mock_browser"
    mock_tool.description = "Mock tool for tests"
    mock_tool.run.return_value = ToolResult(
        success=False,
        output="",
        error="Element not found: #button",
    )
    registry.register(mock_tool)

    state = TaskWorkerState(
        task="Test task",
        plan=[
            PlanStep(
                index=0,
                description="Click missing button",
                tool="mock_browser",
                params={"action": "click", "selector": "#button"},
            )
        ],
        step_index=0,
    )

    update = asyncio.run(executor_node(state, registry=registry))

    assert len(update["actions"]) == 1
    action = update["actions"][0]
    assert action.success is False
    assert "Element not found" in action.error


def test_executor_node_past_end_of_plan():
    registry = ToolRegistry()
    state = TaskWorkerState(
        task="Test task",
        plan=[PlanStep(index=0, description="Step 1", tool="mock")],
        step_index=1,  # Past the end of plan
    )

    update = asyncio.run(executor_node(state, registry=registry))
    assert update["status"] == "verifying"


def test_executor_dynamic_ticket_status_guards():
    from src.worker.executor import _resolve_params

    # 1. When troubleshooting is in flight (is_resolved is False), prevent closing ticket
    state_open = TaskWorkerState(
        task="Troubleshoot ticket",
        memory={"is_resolved": False, "ticket_reply_status": "Open"},
    )
    params_select = {
        "action": "select",
        "selector": "select[name='reply_status_id']",
        "value": "Resolved",
    }
    resolved_open = _resolve_params(params_select, state_open)
    assert resolved_open["value"] == "Open"

    # 2. When resolution is confirmed (is_resolved is True), transition to Resolved
    state_resolved = TaskWorkerState(
        task="Troubleshoot ticket",
        memory={"is_resolved": True, "ticket_reply_status": "Resolved"},
    )
    resolved_done = _resolve_params(params_select, state_resolved)
    assert resolved_done["value"] == "Resolved"

    # 3. Dynamic template variable {ticket_reply_status} substitution
    params_tpl = {
        "action": "select",
        "selector": "select[name='reply_status_id']",
        "value": "{ticket_reply_status}",
    }
    assert _resolve_params(params_tpl, state_open)["value"] == "Open"
    assert _resolve_params(params_tpl, state_resolved)["value"] == "Resolved"


def test_executor_stores_tool_metadata():
    registry = ToolRegistry()
    mock_tool = AsyncMock()
    mock_tool.name = "mock_support"
    mock_tool.description = "Mock support tool"
    mock_tool.run.return_value = ToolResult(
        success=True,
        output="Steps to resolve",
        metadata={"is_resolved": False, "ticket_reply_status": "Open"},
    )
    registry.register(mock_tool)

    state = TaskWorkerState(
        task="Support task",
        plan=[PlanStep(index=0, description="Run support", tool="mock_support")],
        step_index=0,
    )

    update = asyncio.run(executor_node(state, registry=registry))
    assert update["memory"]["is_resolved"] is False
    assert update["memory"]["ticket_reply_status"] == "Open"


def test_executor_enforces_osticket_admin_credentials():
    from src.worker.config import OSTICKET_STAFF_PASS, OSTICKET_STAFF_USER
    from src.worker.executor import _resolve_params

    state = TaskWorkerState(task="Log into osTicket")

    # 1. Enforce username even if LLM hallucinated 'admin' or 'Admin User'
    params_user = {
        "action": "type",
        "selector": "input[name='userid']",
        "text": "Admin User",
    }
    resolved_user = _resolve_params(params_user, state)
    assert resolved_user["text"] == OSTICKET_STAFF_USER
    assert resolved_user["text"] == "ostadmin"

    # 2. Enforce password even if LLM hallucinated 'password' or 'wrongpass'
    params_pass = {
        "action": "type",
        "selector": "input[name='passwd']",
        "text": "randompassword123",
    }
    resolved_pass = _resolve_params(params_pass, state)
    assert resolved_pass["text"] == OSTICKET_STAFF_PASS
    assert resolved_pass["text"] == "Admin1"

    # 3. Template substitution for {staff_user} and {staff_pass}
    params_tpl = {
        "action": "type",
        "selector": "#some_field",
        "text": "User: {staff_user}, Pass: {staff_pass}",
    }
    resolved_tpl = _resolve_params(params_tpl, state)
    assert "User: ostadmin, Pass: Admin1" in resolved_tpl["text"]

    # 4. User search query field must not be overridden
    params_search = {
        "action": "type",
        "selector": "input[name='query']",
        "text": "Dev Soni",
    }
    resolved_search = _resolve_params(params_search, state)
    assert resolved_search["text"] == "Dev Soni"


def test_executor_resolves_with_closing_reply():
    from src.worker.executor import _resolve_params

    # 1. When ticket is marked resolved, ensure closing reply is present in reply editor
    state = TaskWorkerState(
        task="Resolve ticket #133139",
        memory={"is_resolved": True, "ticket_reply_status": "Resolved"},
    )

    params_reply = {
        "action": "type",
        "selector": "div[contenteditable='true']",
        "text": "{support_response}",
    }
    resolved = _resolve_params(params_reply, state)
    assert len(resolved["text"]) > 10
    assert any(w in resolved["text"].lower() for w in ("glad to hear", "welcome", "resolved", "listening"))


def test_executor_explicit_ticket_resolution_task_enforces_resolved_status():
    from src.worker.executor import _resolve_params

    state = TaskWorkerState(
        task="Resolve ticket #370389 with closing reply",
        goal="Ticket #370389 marked resolved with closing reply",
    )

    params_select = {
        "action": "select",
        "selector": "select[name='reply_status_id']",
        "value": "{ticket_reply_status}",
    }
    resolved_sel = _resolve_params(params_select, state)
    assert resolved_sel["value"] == "Resolved"

    params_reply = {
        "action": "type",
        "selector": "div[contenteditable='true']",
        "text": "{support_response}",
    }
    resolved_text = _resolve_params(params_reply, state)
    assert any(w in resolved_text["text"].lower() for w in ("glad", "welcome", "resolved", "listening"))




