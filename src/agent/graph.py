"""
LangGraph StateGraph builder for the SpotifyCares support workflow.
"""

from pathlib import Path
import sys
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from langgraph.graph import END, START, StateGraph

from src.agent.nodes import (
    case_retriever_node,
    escalation_node,
    hitl_escalation_node,
    intent_analyzer_node,
    solution_generator_node,
)
from src.agent.state import SupportAgentState


def route_after_analysis(state: SupportAgentState) -> str:
    """
    Decides whether to escalate to security/billing, escalate to HITL, or retrieve troubleshooting cases.
    """
    if state.requires_escalation:
        return "escalation"
    if state.is_hitl:
        return "hitl_escalation"
    return "case_retriever"


def route_after_retrieval(state: SupportAgentState) -> str:
    """
    Evaluates RAG retrieval confidence.
    If match score is below threshold or no cases were retrieved, reroutes to HITL escalation.
    """
    if not state.rag_threshold_passed or not state.retrieved_cases:
        return "hitl_escalation"
    return "solution_generator"


def build_support_agent():
    """
    Builds and compiles the LangGraph state machine.
    """
    workflow = StateGraph(SupportAgentState)

    # 1. Add nodes
    workflow.add_node("intent_analyzer", intent_analyzer_node)
    workflow.add_node("case_retriever", case_retriever_node)
    workflow.add_node("solution_generator", solution_generator_node)
    workflow.add_node("escalation", escalation_node)
    workflow.add_node("hitl_escalation", hitl_escalation_node)

    # 2. Add edges
    workflow.add_edge(START, "intent_analyzer")

    workflow.add_conditional_edges(
        "intent_analyzer",
        route_after_analysis,
        {
            "escalation": "escalation",
            "hitl_escalation": "hitl_escalation",
            "case_retriever": "case_retriever",
        },
    )

    workflow.add_conditional_edges(
        "case_retriever",
        route_after_retrieval,
        {
            "hitl_escalation": "hitl_escalation",
            "solution_generator": "solution_generator",
        },
    )
    workflow.add_edge("solution_generator", END)
    workflow.add_edge("escalation", END)
    workflow.add_edge("hitl_escalation", END)


    return workflow.compile()


# Precompiled agent singleton
support_agent = build_support_agent()


def run_support_agent(
    query: str,
    history: Optional[List[Dict[str, str]]] = None,
) -> SupportAgentState:
    """
    Executes a single customer turn through the support agent graph.
    """
    messages = list(history or [])
    messages.append({"role": "customer", "content": query})

    initial_state = SupportAgentState(
        messages=messages,
        current_query=query,
    )

    result_dict = support_agent.invoke(initial_state)
    return SupportAgentState(**result_dict)


if __name__ == "__main__":
    test_query = "Why do my downloaded songs keep disappearing when I switch to offline mode on my android?"
    print(f"Executing support agent for query: '{test_query}'\n")
    state = run_support_agent(test_query)
    print(f"Intent: {state.intent}")
    print(f"Escalation: {state.requires_escalation}")
    print(f"Top Case Score: {state.confidence_score}")
    print(f"\nResponse:\n{state.final_response}")
