"""
Unit and integration tests for Human-in-the-Loop (HITL) escalation,
frustration detection, repeated troubleshooting failure, and agent handoff tickets.
"""

import pytest
from src.agent.graph import run_support_agent
from src.agent.sentiment import (
    analyze_customer_sentiment,
    clear_sentiment_cache,
    is_frustrated_query,
    is_human_agent_requested,
    is_repeated_troubleshooting_failure,
)
from src.agent.state import SupportAgentState


@pytest.fixture(autouse=True)
def reset_sentiment_cache():
    clear_sentiment_cache()


@pytest.mark.parametrize(
    "query",
    [
        "This is ridiculous, your app is completely useless!",
        "I am so angry and sick of this stupid bug",
        "Worst customer support ever, nothing is working!",
        "Terrible service, I have been dealing with this for 3 days",
    ],
)
def test_frustration_detection(query):
    assert is_frustrated_query(query) is True


@pytest.mark.parametrize(
    "query",
    [
        "I already tried that and it didn't work at all",
        "I already did the clean reinstall and restarted, still crashing",
        "None of your steps helped, still having the same problem",
        "I've done this three times already, it still doesn't play",
        "That didn't fix it, songs are still greyed out",
    ],
)
def test_repeated_troubleshooting_failure_detection(query):
    assert is_repeated_troubleshooting_failure(query) is True


@pytest.mark.parametrize(
    "query",
    [
        "Can I please talk to a human agent?",
        "Transfer me to a real representative right now",
        "Let me speak to a person, not a bot",
        "I need a real customer support agent",
    ],
)
def test_human_agent_request_detection(query):
    assert is_human_agent_requested(query) is True


def test_sentiment_analyzer_metrics():
    # Normal query
    s_normal = analyze_customer_sentiment("My songs keep skipping on bluetooth speaker")
    assert s_normal["is_frustrated"] is False
    assert s_normal["is_repeated_failure"] is False
    assert s_normal["is_human_requested"] is False
    assert s_normal["frustration_score"] < 0.3

    # Frustrated repeated failure query
    s_frustrated = analyze_customer_sentiment("I already tried that and it didn't work! This is ridiculous, transfer me to a human!")
    assert s_frustrated["is_frustrated"] is True
    assert s_frustrated["is_repeated_failure"] is True
    assert s_frustrated["is_human_requested"] is True
    assert s_frustrated["frustration_score"] >= 0.7


def test_agent_escalates_on_repeated_failure():
    # Turn 1: Customer presents problem -> Agent suggests steps
    turn1 = "Spotify music keeps skipping on my bluetooth speaker"
    state1 = run_support_agent(turn1)
    assert state1.is_hitl is False
    assert state1.requires_escalation is False

    # Turn 2: Customer reports the troubleshooting failed
    turn2 = "I already did that and restarted my device, but it still didn't work at all!"
    state2 = run_support_agent(turn2, history=state1.messages)

    assert state2.is_hitl is True
    assert state2.handoff_ticket is not None
    assert "troubleshooting failed" in state2.escalation_reason.lower() or "repeated" in state2.escalation_reason.lower()
    assert state2.handoff_ticket["case_intent"] == "playback_audio"
    assert "human" in state2.final_response.lower() or "specialist" in state2.final_response.lower()


def test_agent_escalates_on_explicit_human_request():
    turn = "Can you connect me to a real representative please? I need to speak to someone."
    state = run_support_agent(turn)

    assert state.is_hitl is True
    assert state.handoff_ticket is not None
    assert "human" in state.escalation_reason.lower() or "representative" in state.escalation_reason.lower()
    assert state.handoff_ticket["priority"] in ["High", "Urgent"]


def test_agent_escalates_on_high_frustration():
    turn = "This is the worst app ever, I am so angry and tired of this ridiculous glitch!"
    state = run_support_agent(turn)

    assert state.is_hitl is True
    assert state.frustration_score >= 0.5
    assert state.handoff_ticket is not None
    assert state.handoff_ticket["priority"] in ["High", "Urgent"]


def test_sentiment_caching():
    from src.agent.sentiment import analyze_customer_sentiment, _SENTIMENT_CACHE, clear_sentiment_cache
    clear_sentiment_cache()

    query = "My offline music is disappearing randomly on my phone"
    res1 = analyze_customer_sentiment(query)
    cache_len_after_1 = len(_SENTIMENT_CACHE)
    assert cache_len_after_1 > 0

    # Second call should hit the cache
    res2 = analyze_customer_sentiment(query)
    assert res1 == res2
    assert len(_SENTIMENT_CACHE) == cache_len_after_1


def test_sarcasm_and_unhelpful_answer_escalation():
    from src.agent.sentiment import analyze_customer_sentiment
    turn = "Love paying $15 a month for silence. That didn't answer my question at all, stop giving me generic advice."
    res = analyze_customer_sentiment(turn)
    assert res["is_frustrated"] is True
    assert res["trigger_hitl"] is True


def test_rag_confidence_threshold_routing(monkeypatch):
    """
    If RAG confidence threshold is set high (e.g. 50.0) or match is low,
    the workflow routes to hitl_escalation instead of generating a solution.
    """
    monkeypatch.setenv("RAG_CONFIDENCE_THRESHOLD", "50.0")
    query = "How to configure Spotify on a smart microwave with custom linux firmware"
    state = run_support_agent(query)

    assert state.is_hitl is True
    assert state.rag_threshold_passed is False
    assert state.handoff_ticket is not None
    assert "confidence" in state.escalation_reason.lower() or "specialized" in state.escalation_reason.lower()
    assert "Tier-2" in state.final_response or "specialist" in state.final_response.lower()

