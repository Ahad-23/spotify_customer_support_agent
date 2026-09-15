"""
Comprehensive unit and integration tests for LangGraph support agent workflow and state machine.
"""

import pytest
from src.agent.graph import build_support_agent, run_support_agent
from src.agent.state import SupportAgentState


def test_agent_troubleshooting_flow():
    query = "My Spotify music keeps skipping on my Anker bluetooth speaker"
    state = run_support_agent(query)

    assert isinstance(state, SupportAgentState)
    assert state.intent == "playback_audio"
    assert "Bluetooth" in state.device_info.get("platforms", [])
    assert state.requires_escalation is False
    assert len(state.retrieved_cases) > 0
    assert len(state.final_response) > 0
    assert "Spotify" in state.final_response or "support" in state.final_response.lower()


@pytest.mark.parametrize(
    "query,expected_platform",
    [
        ("Spotify won't play on my iPhone 14 with iOS 17", "iOS"),
        ("Downloaded songs missing on Samsung Galaxy tablet", "Android"),
        ("Desktop client crashes on Windows 11 PC", "Desktop Windows"),
        ("App not opening on MacBook Pro with macOS Sonoma", "Desktop Mac"),
        ("Audio stuttering on AirPods bluetooth headphones", "Bluetooth"),
        ("Cannot cast to my Chromecast on the TV", "Connect/Casting"),
    ],
)
def test_agent_device_detection(query, expected_platform):
    state = run_support_agent(query)
    detected = state.device_info.get("platforms", [])
    assert expected_platform in detected


@pytest.mark.parametrize(
    "sensitive_query,expected_reason_snippet",
    [
        ("I saw an unauthorized charge of $15 on my credit card receipt and need a refund", "billing"),
        ("Someone hacked into my account, changed my username and password", "security"),
        ("My account was compromised and email address was stolen", "security"),
        ("I was charged twice for Spotify Premium on my bank statement", "billing"),
    ],
)
def test_agent_escalation_triggers(sensitive_query, expected_reason_snippet):
    state = run_support_agent(sensitive_query)

    assert state.requires_escalation is True
    assert state.escalation_reason is not None
    assert expected_reason_snippet in state.escalation_reason.lower()
    # Sensitive billing/security queries must NOT retrieve public user cases
    assert len(state.retrieved_cases) == 0
    # Must provide secure contact channel
    assert "support.spotify.com" in state.final_response or "Direct Message" in state.final_response


def test_agent_multi_turn_history():
    turn1_query = "Spotify crashes on my Windows PC"
    state1 = run_support_agent(turn1_query)

    assert state1.intent == "app_crash_freeze"
    assert "Desktop Windows" in state1.device_info.get("platforms", [])
    assert len(state1.messages) == 2  # (cust1, agent1)

    # Turn 2 with existing history
    turn2_query = "I reinstalled it as suggested, but now it freezes on blank screen"
    state2 = run_support_agent(turn2_query, history=state1.messages)

    assert len(state2.messages) == 4  # (cust1, agent1, cust2, agent2)
    assert state2.messages[0]["content"] == turn1_query
    assert state2.messages[1]["role"] == "agent"
    assert state2.messages[2]["content"] == turn2_query
    assert state2.messages[3]["role"] == "agent"


def test_agent_graph_compilation():
    graph = build_support_agent()
    assert graph is not None
    # Verify graph node names
    node_keys = graph.nodes.keys()
    for expected_node in ["intent_analyzer", "case_retriever", "solution_generator", "escalation"]:
        assert expected_node in node_keys
