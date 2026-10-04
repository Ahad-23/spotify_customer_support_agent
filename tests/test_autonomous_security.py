"""Security tests for SSRF prevention, input sanitization, and credential redaction."""

import asyncio
from unittest.mock import AsyncMock

from src.worker.executor import executor_node
from src.worker.security import is_safe_url, redact_sensitive_data
from src.worker.state import PlanStep, TaskWorkerState
from src.worker.tools.browser import BrowserTool
from src.worker.tools.http import HTTPTool
from src.worker.tools.registry import ToolRegistry, ToolResult


def test_is_safe_url_valid():
    safe, _ = is_safe_url("http://localhost:8080/scp/login.php")
    assert safe is True

    safe, _ = is_safe_url("https://example.com/api/v1")
    assert safe is True


def test_is_safe_url_blocked_schemes():
    safe, reason = is_safe_url("file:///etc/passwd")
    assert safe is False
    assert "Disallowed scheme" in reason

    safe, reason = is_safe_url("javascript:alert(1)")
    assert safe is False
    assert "Disallowed scheme" in reason

    safe, reason = is_safe_url("ftp://ftp.example.com")
    assert safe is False
    assert "Disallowed scheme" in reason


def test_is_safe_url_blocked_metadata_hosts():
    safe, reason = is_safe_url("http://169.254.169.254/latest/meta-data/")
    assert safe is False
    assert "restricted infrastructure" in reason

    safe, reason = is_safe_url("http://metadata.google.internal/computeMetadata/v1/")
    assert safe is False
    assert "restricted infrastructure" in reason


def test_is_safe_url_allowed_hosts_filter():
    allowed = {"localhost", "127.0.0.1", "osticket.internal"}
    safe, _ = is_safe_url("http://localhost:8080/tickets", allowed_hosts=allowed)
    assert safe is True

    safe, reason = is_safe_url("http://malicious-site.com/steal", allowed_hosts=allowed)
    assert safe is False
    assert "not in the allowed hosts list" in reason


def test_redact_sensitive_data():
    payload = {
        "username": "ostadmin",
        "password": "supersecretpassword",
        "headers": {
            "Authorization": "Bearer token12345",
            "Content-Type": "application/json",
        },
        "nested": [
            {"api_key": "key-999", "name": "normal_val"}
        ],
    }

    redacted = redact_sensitive_data(payload)
    assert redacted["username"] == "ostadmin"
    assert redacted["password"] == "[REDACTED]"
    assert redacted["headers"]["Authorization"] == "[REDACTED]"
    assert redacted["headers"]["Content-Type"] == "application/json"
    assert redacted["nested"][0]["api_key"] == "[REDACTED]"
    assert redacted["nested"][0]["name"] == "normal_val"


def test_browser_blocks_ssrf():
    browser = BrowserTool()
    # Mocking internal page to avoid launching headless browser for quick security test
    browser._page = AsyncMock()

    result = asyncio.run(browser.run({"action": "goto", "url": "http://169.254.169.254/secret"}))
    assert result.success is False
    assert "Security check failed" in result.error

    result = asyncio.run(browser.run({"action": "goto", "url": "file:///etc/hosts"}))
    assert result.success is False
    assert "Security check failed" in result.error


def test_http_blocks_ssrf():
    http_tool = HTTPTool()
    result = asyncio.run(http_tool.run({"method": "get", "url": "http://169.254.169.254/latest"}))
    assert result.success is False
    assert "Security check failed" in result.error


def test_executor_redacts_credentials_in_action_record():
    registry = ToolRegistry()
    mock_tool = AsyncMock()
    mock_tool.name = "browser"
    mock_tool.description = "Browser"
    mock_tool.run.return_value = ToolResult(success=True, output="Logged in")
    registry.register(mock_tool)

    state = TaskWorkerState(
        task="Login",
        plan=[
            PlanStep(
                index=0,
                description="Enter password",
                tool="browser",
                params={"action": "type", "selector": "#passwd", "password": "super_secret_value"},
            )
        ],
        step_index=0,
    )

    update = asyncio.run(executor_node(state, registry=registry))
    recorded_action = update["actions"][0]
    assert recorded_action.params["password"] == "[REDACTED]"
