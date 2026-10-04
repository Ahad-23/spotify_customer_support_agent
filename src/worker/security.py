"""Security guardrails for the autonomous task worker."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

_ALLOWED_SCHEMES = frozenset({"http", "https"})
_BLOCKED_HOSTS = frozenset({"169.254.169.254", "metadata.google.internal"})

_SENSITIVE_KEY_PATTERNS = re.compile(
    r"(password|passwd|secret|api_key|apikey|token|authorization|bearer|cookie|auth)",
    re.IGNORECASE,
)

_SENSITIVE_VALUE_PATTERNS = [
    re.compile(r"(gsk_[a-zA-Z0-9]{20,})"),
    re.compile(r"(sk-[a-zA-Z0-9]{20,})"),
    re.compile(r"(eyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,})"),
]

_REDACTED = "[REDACTED]"


def is_safe_url(url: str, allowed_hosts: set[str] | None = None) -> tuple[bool, str]:
    """Validate that a URL is safe for browser navigation or HTTP requests."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False, f"Invalid URL format: {url}"

    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        return False, f"Disallowed scheme '{parsed.scheme}'. Only HTTP/HTTPS allowed."

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return False, "Missing hostname in URL."

    if hostname in _BLOCKED_HOSTS:
        return False, f"Blocked host: {hostname} (restricted infrastructure)"

    if allowed_hosts and hostname not in allowed_hosts:
        return False, f"Host '{hostname}' is not in the allowed hosts list"

    return True, "URL is safe"


def redact_sensitive_data(obj: Any) -> Any:
    """Recursively redact passwords, API keys, and auth tokens from data structures."""
    if isinstance(obj, dict):
        redacted = {}
        for k, v in obj.items():
            if _SENSITIVE_KEY_PATTERNS.search(str(k)):
                redacted[k] = _REDACTED
            else:
                redacted[k] = redact_sensitive_data(v)
        return redacted

    if isinstance(obj, list):
        return [redact_sensitive_data(item) for item in obj]

    if isinstance(obj, str):
        result = obj
        for pattern in _SENSITIVE_VALUE_PATTERNS:
            result = pattern.sub(_REDACTED, result)
        return result

    return obj
