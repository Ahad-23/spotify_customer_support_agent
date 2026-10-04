"""Unit tests for the enhanced BrowserTool with press, submit, aliases, and resilient fallbacks."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.worker.tools.browser import BrowserTool, _ACTION_ALIASES, _VALID_ACTIONS


def test_valid_actions_and_aliases():
    assert "press" in _VALID_ACTIONS
    assert "submit" in _VALID_ACTIONS
    assert "wait" in _VALID_ACTIONS
    assert "hover" in _VALID_ACTIONS
    assert "goto" in _VALID_ACTIONS
    assert "click" in _VALID_ACTIONS
    assert "type" in _VALID_ACTIONS

    assert _ACTION_ALIASES["navigate"] == "goto"
    assert _ACTION_ALIASES["press_key"] == "press"
    assert _ACTION_ALIASES["submit_form"] == "submit"
    assert _ACTION_ALIASES["fill"] == "type"
    assert _ACTION_ALIASES["sleep"] == "wait"


@pytest.mark.anyio
async def test_browser_action_inference_press():
    tool = BrowserTool()
    tool._page = MagicMock()
    tool._page.keyboard.press = AsyncMock()
    tool._page.wait_for_load_state = AsyncMock()

    # When action is empty but key is provided
    result = await tool.run({"key": "Enter"})
    assert result.success is True
    assert "Pressed key 'Enter'" in result.output
    tool._page.keyboard.press.assert_awaited_with("Enter")


@pytest.mark.anyio
async def test_browser_action_alias_resolution():
    tool = BrowserTool()
    tool._page = MagicMock()
    tool._page.keyboard.press = AsyncMock()
    tool._page.wait_for_load_state = AsyncMock()

    # When action is an alias like 'press_key'
    result = await tool.run({"action": "press_key", "key": "Tab"})
    assert result.success is True
    assert "Pressed key 'Tab'" in result.output


@pytest.mark.anyio
async def test_browser_submit_fallback():
    tool = BrowserTool()
    tool._page = MagicMock()
    loc = MagicMock()
    loc.count = AsyncMock(return_value=1)
    loc.is_visible = AsyncMock(return_value=True)
    loc.click = AsyncMock()
    first_loc = MagicMock()
    first_loc.count = AsyncMock(return_value=1)
    first_loc.is_visible = AsyncMock(return_value=True)
    first_loc.click = AsyncMock()
    loc.first = first_loc

    tool._page.locator = MagicMock(return_value=loc)
    tool._page.wait_for_load_state = AsyncMock()

    result = await tool.run({"action": "submit"})
    assert result.success is True
    assert "Submitted form" in result.output


@pytest.mark.anyio
async def test_browser_wait_action():
    tool = BrowserTool()
    tool._page = MagicMock()
    tool._page.wait_for_timeout = AsyncMock()

    result = await tool.run({"action": "wait", "ms": 500})
    assert result.success is True
    assert "Waited 500ms" in result.output
    tool._page.wait_for_timeout.assert_awaited_with(500)


@pytest.mark.anyio
async def test_browser_select_status():
    tool = BrowserTool()
    tool._page = MagicMock()
    loc = MagicMock()
    loc.count = AsyncMock(return_value=1)
    loc.select_option = AsyncMock()
    loc.first = loc

    tool._page.locator = MagicMock(return_value=loc)

    result = await tool.run({"action": "select", "selector": "select[name='reply_status_id']", "value": "Resolved"})
    assert result.success is True
    assert "Selected 'Resolved'" in result.output

