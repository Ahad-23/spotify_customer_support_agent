"""
Agent state definitions for SpotifyCares LangGraph workflow.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SupportAgentState(BaseModel):
    """
    Typed state object passed between nodes in the LangGraph support workflow.
    """
    messages: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Full conversation history: [{'role': 'customer'|'agent', 'content': str}]"
    )
    current_query: str = Field(
        default="",
        description="Latest customer message being processed"
    )
    intent: str = Field(
        default="general_inquiry",
        description="Classified problem intent"
    )
    device_info: Dict[str, Any] = Field(
        default_factory=dict,
        description="Detected device, OS, or connectivity details"
    )
    retrieved_cases: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Top historical resolved cases retrieved from Elasticsearch"
    )
    best_resolution: str = Field(
        default="",
        description="Extracted or synthesized actionable resolution"
    )
    final_response: str = Field(
        default="",
        description="Synthesized SpotifyCares response to the customer"
    )
    requires_escalation: bool = Field(
        default=False,
        description="True if the issue involves private account data, security, or billing dispute"
    )
    escalation_reason: Optional[str] = Field(
        default=None,
        description="Reason for escalation to human agent or secure DM"
    )
    confidence_score: float = Field(
        default=0.0,
        description="Retrieval / resolution confidence score"
    )
    rag_threshold_passed: bool = Field(
        default=True,
        description="True if RAG retrieval match score met confidence threshold"
    )
    sentiment: str = Field(
        default="neutral",
        description="Detected sentiment: positive, neutral, frustrated, or urgent"
    )
    frustration_score: float = Field(
        default=0.0,
        description="Detected customer frustration intensity (0.0 to 1.0)"
    )
    failed_attempts: int = Field(
        default=0,
        description="Number of times customer stated troubleshooting failed in this session"
    )
    is_hitl: bool = Field(
        default=False,
        description="True if customer is routed to Human-In-The-Loop support"
    )
    handoff_ticket: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Structured ticket summary for human tier-2 representative handoff"
    )

