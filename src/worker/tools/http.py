"""HTTP tool for REST API interactions."""

from __future__ import annotations

import json
from typing import Any

import httpx

from src.worker.security import is_safe_url
from src.worker.tools.registry import ToolResult

_DEFAULT_TIMEOUT_SEC = 10.0


class HTTPTool:
    """Make HTTP requests to web APIs."""

    name = "http"
    description = "Make HTTP requests. Params: method (GET|POST|PUT|DELETE|PATCH), url (str), headers (dict, opt), body (dict|str, opt)"

    async def run(self, params: dict[str, Any]) -> ToolResult:
        method = params.get("method", "GET").upper()
        url = params.get("url", "")
        headers = params.get("headers", {})
        body = params.get("body")

        if not url:
            return ToolResult(success=False, output="", error="Missing 'url'")

        is_safe, reason = is_safe_url(url)
        if not is_safe:
            return ToolResult(success=False, output="", error=f"Security check failed: {reason}")

        try:
            async with httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT_SEC) as client:
                kwargs: dict[str, Any] = {"headers": headers}
                if body is not None:
                    if isinstance(body, dict):
                        kwargs["json"] = body
                    else:
                        kwargs["content"] = str(body)

                response = await client.request(method, url, **kwargs)
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    try:
                        formatted = json.dumps(response.json(), indent=2)
                    except Exception:
                        formatted = response.text
                else:
                    formatted = response.text[:2000]

                return ToolResult(
                    success=response.is_success,
                    output=f"HTTP {response.status_code}\n{formatted}",
                    error=None if response.is_success else f"HTTP {response.status_code}: {response.reason_phrase}",
                )
        except Exception as exc:
            return ToolResult(success=False, output="", error=f"Request failed: {type(exc).__name__}: {exc}")
