import asyncio
from unittest.mock import MagicMock, patch

from src.worker.tools.support_agent import SupportAgentTool


def test_support_agent_tool_success():
    tool = SupportAgentTool()
    assert tool.name == "support_agent"

    mock_state = MagicMock()
    mock_state.final_response = "We have investigated your subscription billing issue."

    with patch("src.agent.graph.run_support_agent", return_value=mock_state):
        res = asyncio.run(tool.run({"query": "I stopped my premium subscription and was still billed"}))
        assert res.success is True
        assert "subscription billing issue" in res.output
        assert res.error is None


def test_support_agent_tool_missing_query():
    tool = SupportAgentTool()
    res = asyncio.run(tool.run({}))
    assert res.success is False
    assert "Missing required 'query'" in res.error


def test_support_agent_tool_multiturn_thread():
    tool = SupportAgentTool()

    raw_thread = (
        "saransh posted 10/3/26 8:31 AM\n"
        "I had a playlist with around 200 songs that I created a few months ago, but it suddenly disappeared.\n\n"
        "Admin User posted 10/3/26 8:33 AM\n"
        "Hey there! Can you check if logging out > restarting > logging back in helps?\n\n"
        "saransh posted 10/3/26 8:40 AM\n"
        "I tried restarting and relogging, but it is still missing. My phone is iPhone 13 running iOS 17."
    )

    mock_state = MagicMock()
    mock_state.final_response = "Thanks for following up! Since logging out and restarting didn't solve it on your iPhone 13, let's try step 2: checking Spotify offline storage and toggling offline mode."

    with patch("src.agent.graph.run_support_agent", return_value=mock_state) as mock_run:
        res = asyncio.run(tool.run({"query": raw_thread}))
        assert res.success is True
        assert "iPhone 13" in res.output
        mock_run.assert_called_once()
        _, kwargs = mock_run.call_args
        assert "iPhone 13" in kwargs.get("query", "")
        assert len(kwargs.get("history", [])) == 2
        assert res.metadata["is_resolved"] is False
        assert res.metadata["ticket_reply_status"] == "Open"


def test_support_agent_tool_resolution_confirmation():
    tool = SupportAgentTool()

    raw_thread = (
        "saransh posted 10/3/26 8:31 AM\n"
        "I had a playlist with around 200 songs that I created a few months ago, but it suddenly disappeared.\n\n"
        "Admin User posted 10/3/26 8:33 AM\n"
        "Hey there! Can you check if logging out > restarting > logging back in helps?\n\n"
        "saransh posted 10/3/26 8:40 AM\n"
        "That worked, thank you! The songs are back now."
    )

    res = asyncio.run(tool.run({"query": raw_thread}))
    assert res.success is True
    assert res.metadata["is_resolved"] is True
    assert res.metadata["ticket_reply_status"] == "Resolved"
    assert "glad to hear" in res.output.lower() or "welcome" in res.output.lower()


def test_support_agent_tool_short_confirmation():
    tool = SupportAgentTool()
    res = asyncio.run(tool.run({"query": "that worked, thanks!"}))
    assert res.success is True
    assert res.metadata["is_resolved"] is True
    assert res.metadata["ticket_reply_status"] == "Resolved"



