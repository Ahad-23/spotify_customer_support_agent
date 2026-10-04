"""Support agent tool: connects the autonomous worker to the SpotifyCares AI agent pipeline."""

from __future__ import annotations

import asyncio
import re
from typing import Any

from src.worker.tools.registry import ToolResult


def _clean_ticket_body(text: str) -> str:
    """Remove osTicket audit events (Created by, Closed by, Status changed) from thread body."""
    cleaned = re.sub(r"(?:^|\n)\s*(?:Created by|Closed by|Assigned to|Status changed to|Ticket Thread)[^\n]*", "", text, flags=re.I)
    cleaned = re.sub(r"^(?:[\w\s.-]+?)\s+posted\s+[^\n]*\n", "", cleaned, flags=re.I)
    return cleaned.strip()


def _parse_thread_into_turns(raw_text: str) -> tuple[str, list[dict[str, str]]]:
    """Parse raw thread text or osTicket thread entries into structured conversation turns.

    Returns:
        tuple[str, list[dict[str, str]]]: (latest_query, history)
    """
    cleaned = raw_text.strip()
    if not cleaned:
        return "", []

    # Check for osTicket post pattern: e.g. "saransh posted 10/3/26 8:31 AM" or "Admin User posted 10/3/26 8:33 AM"
    # Note: exclude audit trails like "Created by Aman Shaikh" or "Closed by Admin User"
    post_pattern = re.compile(
        r"(?:^|\n)([\w\s.-]+?)\s+(?:posted|replied|wrote)\s+(?:\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})[^\n]*\n",
        re.I,
    )

    matches = list(post_pattern.finditer(cleaned))
    if len(matches) >= 2:
        turns: list[dict[str, str]] = []
        for i, m in enumerate(matches):
            author = m.group(1).strip().lower()
            start_pos = m.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(cleaned)
            content = _clean_ticket_body(cleaned[start_pos:end_pos])

            is_staff = any(kw in author for kw in ("admin", "staff", "agent", "support", "spotify"))
            role = "agent" if is_staff else "customer"
            if content:
                turns.append({"role": role, "content": content})

        if turns:
            # Find the last customer message as current_query
            last_customer_idx = -1
            for idx in reversed(range(len(turns))):
                if turns[idx]["role"] == "customer":
                    last_customer_idx = idx
                    break

            if last_customer_idx != -1:
                latest_query = turns[last_customer_idx]["content"]
                history = turns[:last_customer_idx]
                return latest_query, history

    # Check for explicit Customer / Agent labels: e.g. "Customer: ... \n Agent: ..."
    label_pattern = re.compile(r"(?:^|\n)(Customer|User|Client|Agent|Support|Spotify):\s*", re.I)
    label_matches = list(label_pattern.finditer(cleaned))
    if len(label_matches) >= 2:
        turns = []
        for i, m in enumerate(label_matches):
            label = m.group(1).lower()
            start_pos = m.end()
            end_pos = label_matches[i + 1].start() if i + 1 < len(label_matches) else len(cleaned)
            content = _clean_ticket_body(cleaned[start_pos:end_pos])
            role = "agent" if label in ("agent", "support", "spotify") else "customer"
            if content:
                turns.append({"role": role, "content": content})

        if turns:
            last_customer_idx = -1
            for idx in reversed(range(len(turns))):
                if turns[idx]["role"] == "customer":
                    last_customer_idx = idx
                    break
            if last_customer_idx != -1:
                return turns[last_customer_idx]["content"], turns[:last_customer_idx]

    # Single message or unstructured initial ticket post
    return _clean_ticket_body(cleaned), []


RESOLUTION_CONFIRMATION_PATTERN = re.compile(
    r"\b("
    r"fixed it|that fixed it|it fixed it|"
    r"it worked|that worked|worked|works now|working now|"
    r"problem solved|issue solved|all good now|all sorted|issue resolved|"
    r"thank you that helped|thanks that helped|that helped|it helped|"
    r"thank you that worked|thanks that worked|"
    r"solved my issue|solved my problem|back to normal|"
    r"songs are back|playlists are back|playlist is back|all restored|"
    r"working fine|working great|that did the trick|it did the trick|"
    r"perfect thanks|perfect thank you|all set"
    r")\b",
    re.IGNORECASE,
)


class SupportAgentTool:
    """Invokes the core SpotifyCares support agent graph to generate resolutions.

    Uses intent classification, CBR RAG retrieval from verified troubleshooting cases,
    and solution generation (or HITL escalation) to produce the exact same customer-facing
    response generated in the chat interface.
    """

    name = "support_agent"
    description = (
        "Generate an intelligent customer support resolution for an issue using SpotifyCares RAG pipeline, "
        "knowledge retrieval, and intent reasoning. "
        "Params: query (str: customer message, thread text, or problem description)"
    )

    async def run(self, params: dict[str, Any]) -> ToolResult:
        raw_query = params.get("query") or params.get("thread") or params.get("text") or ""
        if isinstance(raw_query, list):
            # Already formatted list of messages
            messages = raw_query
            query = messages[-1].get("content", "") if messages else ""
            history = messages[:-1]
        else:
            query, history = _parse_thread_into_turns(str(raw_query))

        if not query:
            return ToolResult(
                success=False,
                output="",
                error="Missing required 'query' parameter with customer issue description",
            )

        # Check if customer's latest message explicitly confirms that troubleshooting solved the issue
        is_confirmed_resolved = bool(RESOLUTION_CONFIRMATION_PATTERN.search(query))
        if is_confirmed_resolved:
            closing_response = (
                "You're very welcome! We're so glad to hear that resolved your issue and everything is working properly. "
                "If you ever need help with anything else in the future, please feel free to reach out. Happy listening! 🎵"
            )
            return ToolResult(
                success=True,
                output=closing_response,
                metadata={
                    "is_resolved": True,
                    "ticket_reply_status": "Resolved",
                    "turn_count": len(history) + 1,
                    "requires_escalation": False,
                },
            )

        from src.agent.graph import run_support_agent

        try:
            # run_support_agent runs synchronously, execute in worker thread to avoid blocking event loop
            agent_state = await asyncio.to_thread(run_support_agent, query=query, history=history)
            response_text = agent_state.final_response.strip()
            if not response_text:
                return ToolResult(
                    success=False,
                    output="",
                    error="Support agent did not produce a response",
                )

            # Ongoing troubleshooting turn awaiting customer verification
            return ToolResult(
                success=True,
                output=response_text,
                metadata={
                    "is_resolved": False,
                    "ticket_reply_status": "Open",
                    "turn_count": len(history) + 1,
                    "requires_escalation": getattr(agent_state, "requires_escalation", False),
                },
            )
        except Exception as exc:
            return ToolResult(
                success=False,
                output="",
                error=f"Support agent reasoning failed: {type(exc).__name__}: {exc}",
            )


