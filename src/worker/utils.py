"""Utilities for JSON extraction and resilience in LLM responses."""

from __future__ import annotations

import json
import re
from typing import Any


def extract_json_from_llm_response(raw: str | Any) -> dict[str, Any]:
    """Extract and parse JSON from an LLM response string.

    Handles:
    - Standard JSON objects
    - Markdown code fences (```json ... ``` or ``` ... ```)
    - Leading / trailing conversational text
    - Pydantic BaseModel instances or pre-parsed dicts
    """
    if isinstance(raw, dict):
        return raw

    if not isinstance(raw, str):
        if hasattr(raw, "model_dump"):
            return raw.model_dump()
        raw = str(raw)

    text = raw.strip()
    if not text:
        raise ValueError("Empty LLM response received")

    # 1. Try direct json.loads
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. Extract from markdown code blocks ```json ... ``` or ``` ... ```
    code_block_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if code_block_match:
        block_content = code_block_match.group(1).strip()
        try:
            data = json.loads(block_content)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            pass

    # 3. Extract the first balanced JSON object from { to }
    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        candidate = text[start_idx : end_idx + 1]
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            pass

    raise ValueError(f"Could not extract valid JSON object from LLM response: {text[:300]}")
