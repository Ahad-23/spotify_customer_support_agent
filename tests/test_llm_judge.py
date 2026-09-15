"""
Comprehensive unit and contract tests for LLM-as-a-judge evaluation suite.
"""

import pytest
from src.agent.graph import run_support_agent
from src.eval.llm_judge import LLMJudge, GOLDEN_EVAL_CASES, JudgeEvaluation


import os

@pytest.fixture(scope="module")
def judge():
    j = LLMJudge()
    if not os.getenv("LIVE_EVAL"):
        j.has_llm_key = False
    return j


def test_llm_judge_suite_full(judge):
    evaluations = judge.evaluate_all(GOLDEN_EVAL_CASES)
    assert len(evaluations) == len(GOLDEN_EVAL_CASES)

    for ev in evaluations:
        assert isinstance(ev, JudgeEvaluation)
        assert 1 <= ev.relevance <= 5
        assert 1 <= ev.groundedness <= 5
        assert 1 <= ev.brand_voice <= 5
        assert 1 <= ev.actionability <= 5
        assert ev.escalation_correct is True, f"Escalation mismatched for: {ev.query}"
        assert ev.overall_score >= 3.5, f"Score below 3.5 for: {ev.query}"
        assert ev.passed is True, f"Case did not pass: {ev.query} - {ev.reasoning}"

    pass_rate = sum(1 for e in evaluations if e.passed) / len(evaluations)
    assert pass_rate == 1.0


@pytest.mark.parametrize(
    "case_idx,expected_cat",
    [
        (0, "Playback / Bluetooth"),
        (1, "Offline Storage"),
        (2, "App Crash"),
        (3, "Device Casting"),
        (4, "Account Security (Escalation)"),
        (5, "Billing Dispute (Escalation)"),
        (6, "HITL / Frustration Escalation"),
        (7, "HITL / Human Agent Request"),
    ],
)
def test_llm_judge_individual_cases(judge, case_idx, expected_cat):
    case = GOLDEN_EVAL_CASES[case_idx]
    assert case["category"] == expected_cat

    state = run_support_agent(case["query"])
    result = judge.judge_interaction(
        query=case["query"],
        category=case["category"],
        state=state,
        should_escalate=case["should_escalate"],
    )

    assert result.passed is True
    assert result.escalation_correct is True
    assert result.overall_score >= 4.0
