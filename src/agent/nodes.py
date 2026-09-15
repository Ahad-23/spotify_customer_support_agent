"""
LangGraph nodes for SpotifyCares support workflow.
"""

import os
from pathlib import Path
import re
import sys
import dotenv
import litellm

from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))



from src.agent.prompts import (
    ESCALATION_PROMPT,
    SOLUTION_GENERATION_PROMPT,
    SPOTIFY_SYSTEM_PROMPT,
)
from src.agent.state import SupportAgentState
from src.data.intent_classifier import classify_intent
from src.rag.retriever import CaseRetriever

dotenv.load_dotenv(REPO_ROOT / ".env")

# Precompile device and escalation patterns
DEVICE_PATTERNS = {
    "iOS": re.compile(r"\b(iphone|ipad|ios|apple watch)\b", re.I),
    "Android": re.compile(r"\b(android|samsung|galaxy|pixel|oneplus|xiaomi|tablet)\b", re.I),
    "Desktop Windows": re.compile(r"\b(windows|pc|laptop|desktop|win10|win11)\b", re.I),
    "Desktop Mac": re.compile(r"\b(mac|macbook|macos|imac)\b", re.I),
    "Bluetooth": re.compile(r"\b(bluetooth|speaker|headphones|airpods|headset)\b", re.I),
    "Connect/Casting": re.compile(r"\b(chromecast|alexa|echo|sonos|smart tv|roku|firestick|ps4|ps5|xbox)\b", re.I),
}

ESCALATION_PATTERNS = [
    (
        re.compile(
            r"\b(refund|unauthorized.*?(?:charge|transaction|payment|fee)|double charge|duplicate charge|charged twice|charged again|bank account|billing dispute)\b",
            re.I,
        ),
        "Billing transaction requiring private account backend",
    ),
    (
        re.compile(
            r"\b(hacked|stolen account|stolen|unauthorized(?: login| access)?|fraud|compromised|account taken over)\b",
            re.I,
        ),
        "Security and account integrity issue",
    ),
    (
        re.compile(
            r"\b(password reset link not received|locked out of email)\b",
            re.I,
        ),
        "Authentication lock requiring identity verification",
    ),
]



# Singleton retriever instance
_retriever: Optional[CaseRetriever] = None


def get_retriever() -> CaseRetriever:
    global _retriever
    if _retriever is None:
        _retriever = CaseRetriever()
    return _retriever


from src.agent.sentiment import analyze_customer_sentiment


def intent_analyzer_node(state: SupportAgentState) -> Dict[str, Any]:
    """
    Analyzes the customer query:
    1. Classifies the issue intent (preserves active intent on follow-up failure turns).
    2. Extracts device and environment signals.
    3. Evaluates customer sentiment and frustration for Human-in-the-Loop (HITL) routing.
    4. Checks for sensitive billing / security escalation triggers.
    """
    query = state.current_query or (state.messages[-1]["content"] if state.messages else "")

    # 1. Classify intent (inherit from dialogue history if current turn is a follow-up)
    new_intent = classify_intent(query)
    intent = new_intent
    if intent == "general_inquiry":
        for m in reversed(state.messages):
            if m.get("role") == "customer":
                prior_int = classify_intent(m.get("content", ""))
                if prior_int != "general_inquiry":
                    intent = prior_int
                    break

    # 2. Extract device info (current turn + dialogue history)
    detected_devices = list(state.device_info.get("platforms", []))
    for m in state.messages:
        msg_text = m.get("content", "")
        for dev_name, pattern in DEVICE_PATTERNS.items():
            if pattern.search(msg_text) and dev_name not in detected_devices:
                detected_devices.append(dev_name)
    for dev_name, pattern in DEVICE_PATTERNS.items():
        if pattern.search(query) and dev_name not in detected_devices:
            detected_devices.append(dev_name)

    # 3. Analyze customer sentiment & frustration using LLM contextual engine
    prior_failures = state.failed_attempts
    sentiment = analyze_customer_sentiment(
        query,
        history=state.messages,
        previous_failed_count=prior_failures,
    )
    is_hitl = sentiment["trigger_hitl"]
    frustration_score = sentiment["frustration_score"]
    sentiment_label = sentiment["sentiment"]
    failed_attempts = prior_failures + (1 if (sentiment["is_repeated_failure"] or sentiment.get("unhelpful_prior_answer")) else 0)

    # 4. Check for static security / billing escalation triggers
    requires_escalation = False
    escalation_reason = None
    for pattern, reason in ESCALATION_PATTERNS:
        if pattern.search(query):
            requires_escalation = True
            escalation_reason = reason
            break

    # If HITL was triggered and no security escalation, set HITL reason
    if is_hitl and not requires_escalation:
        escalation_reason = sentiment["hitl_reason"]

    return {
        "current_query": query,
        "intent": intent,
        "device_info": {"platforms": detected_devices},
        "requires_escalation": requires_escalation,
        "is_hitl": is_hitl,
        "sentiment": sentiment_label,
        "frustration_score": frustration_score,
        "failed_attempts": failed_attempts,
        "escalation_reason": escalation_reason,
    }


RAG_CONFIDENCE_THRESHOLD = float(os.getenv("RAG_CONFIDENCE_THRESHOLD", "20.0"))


def case_retriever_node(state: SupportAgentState) -> Dict[str, Any]:
    """
    Queries Elasticsearch for historical cases with matching problem descriptions.
    Evaluates match score against RAG_CONFIDENCE_THRESHOLD.
    """
    if state.requires_escalation or state.is_hitl:
        return {"retrieved_cases": [], "confidence_score": 0.0, "rag_threshold_passed": False}

    retriever = get_retriever()
    # First attempt: search with intent filter
    matches = retriever.retrieve(
        query=state.current_query,
        top_k=3,
        intent_filter=state.intent if state.intent != "general_inquiry" else None,
    )

    # Fallback attempt: if filtered search produced 0 matches, search without filter
    if not matches:
        matches = retriever.retrieve(query=state.current_query, top_k=3)

    cases_dicts = [m.to_dict() for m in matches]
    best_res = matches[0].resolution if matches else ""
    top_score = matches[0].score if matches else 0.0

    threshold = float(os.getenv("RAG_CONFIDENCE_THRESHOLD", "20.0"))
    threshold_passed = bool(matches and top_score >= threshold)
    is_hitl = state.is_hitl or (not threshold_passed)
    reason = state.escalation_reason
    if not threshold_passed and not reason:
        reason = f"Low knowledge-base confidence ({top_score:.2f} < {threshold}) - specialized inquiry"

    return {
        "retrieved_cases": cases_dicts,
        "best_resolution": best_res,
        "confidence_score": top_score,
        "rag_threshold_passed": threshold_passed,
        "is_hitl": is_hitl,
        "escalation_reason": reason,
    }


def solution_generator_node(state: SupportAgentState) -> Dict[str, Any]:
    """
    Synthesizes an empathetic, actionable SpotifyCares response based on retrieved case evidence.
    """
    # Build evidence text from retrieved cases
    evidence_lines = []
    for i, c in enumerate(state.retrieved_cases, 1):
        evidence_lines.append(
            f"Case #{i} (Score: {c.get('score', 0):.2f}):\n"
            f"  Customer Problem: {c.get('customer_problem')}\n"
            f"  Proven Resolution: {c.get('resolution')}\n"
        )
    case_evidence = "\n".join(evidence_lines) if evidence_lines else "No specific historical match found."

    prompt_content = SOLUTION_GENERATION_PROMPT.format(
        customer_query=state.current_query,
        intent=state.intent,
        case_evidence=case_evidence,
    )

    # Check for available LLM API keys (Groq default, Gemini/OpenAI options)
    has_llm_key = any(
        os.getenv(k)
        for k in [
            "GROQ_API_KEY",
            "GEMINI_API_KEY",
            "OPENAI_API_KEY",
        ]
    )

    response_text = ""
    if has_llm_key:
        try:
            # Determine model: Groq is default, Gemini and OpenAI are options
            model = os.getenv("LLM_MODEL") or os.getenv("AGENT_MODEL")
            if not model:
                if os.getenv("GROQ_API_KEY"):
                    groq_m = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
                    model = f"groq/{groq_m}" if not groq_m.startswith("groq/") else groq_m
                elif os.getenv("GEMINI_API_KEY"):
                    gem_m = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
                    model = f"gemini/{gem_m}" if not gem_m.startswith("gemini/") else gem_m
                elif os.getenv("OPENAI_API_KEY"):
                    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
                else:
                    model = "groq/openai/gpt-oss-120b"

            llm_res = litellm.completion(
                model=model,
                messages=[
                    {"role": "system", "content": SPOTIFY_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt_content},
                ],
                temperature=0.3,
                max_tokens=800,
            )
            response_text = llm_res.choices[0].message.content.strip()
        except Exception:
            # Fall back to template synthesis on error
            response_text = ""

    # Intelligent template synthesis fallback (zero external API key needed)
    if not response_text:
        if state.best_resolution:
            # Clean up resolution if it starts with greetings
            clean_sol = state.best_resolution
            for prefix in ["Hi there!", "Hey there!", "Hi!", "Hey!"]:
                if clean_sol.startswith(prefix):
                    clean_sol = clean_sol[len(prefix) :].strip()

            response_text = (
                f"Hey there! Thanks for reaching out to Spotify Support. Let's get this sorted for you.\n\n"
                f"Based on similar historical issues with {state.intent.replace('_', ' ')}, here are the recommended steps to try:\n"
                f"- {clean_sol}\n\n"
                f"Does that make a difference? If you're still having trouble, let us know your exact device and app version so we can investigate further!"
            )
        else:
            response_text = (
                "Hey there! Thanks for reaching out to Spotify Support.\n\n"
                "Could you let us know what device, operating system, and Spotify version you're currently using? "
                "Also, does restarting your device or logging out and back in help at all? Keep us posted!"
            )


    updated_messages = list(state.messages)
    updated_messages.append({"role": "agent", "content": response_text})

    return {
        "final_response": response_text,
        "messages": updated_messages,
    }


def escalation_node(state: SupportAgentState) -> Dict[str, Any]:
    """
    Handles issues that require private verification or official secure support.
    """
    reason = state.escalation_reason or "Account-specific issue"
    response_text = (
        f"Hi there! Because this involves {reason.lower()}, we cannot safely handle account or payment details in a public message.\n\n"
        f"Please head over to our secure support portal: https://support.spotify.com/contact-spotify-anonymous/ "
        f"or send us a private Direct Message with your account email address. Our dedicated team will take a look for you right away!"
    )

    updated_messages = list(state.messages)
    updated_messages.append({"role": "agent", "content": response_text})

    return {
        "final_response": response_text,
        "messages": updated_messages,
    }


def hitl_escalation_node(state: SupportAgentState) -> Dict[str, Any]:
    """
    Handles Human-In-The-Loop (HITL) escalation when:
    1. Customer reports troubleshooting failed or unhelpful answers.
    2. Customer is frustrated or dissatisfied (LLM sentiment analysis).
    3. Customer explicitly asks to speak with a human agent.
    4. RAG retrieval match confidence falls below threshold.
    
    Creates a structured handoff ticket so the customer never repeats themselves.
    """
    import time
    ticket_id = f"SPOTIFY-T2-{int(time.time())}"
    reason = state.escalation_reason or "Customer requested human specialist assistance"
    platforms = state.device_info.get("platforms", [])

    is_low_rag = not state.rag_threshold_passed or "confidence" in reason.lower()
    if is_low_rag:
        priority = "Standard"
    elif state.frustration_score >= 0.6 or state.failed_attempts >= 2:
        priority = "Urgent"
    else:
        priority = "High"

    ticket = {
        "ticket_id": ticket_id,
        "case_intent": state.intent,
        "customer_query": state.current_query,
        "platforms": platforms,
        "sentiment": state.sentiment,
        "frustration_level": "High" if state.frustration_score >= 0.5 else "Moderate",
        "failed_attempts": state.failed_attempts,
        "rag_confidence": round(state.confidence_score, 2),
        "escalation_reason": reason,
        "priority": priority,
        "conversation_turns": len(state.messages),
    }

    platform_str = ", ".join(platforms) if platforms else "your device"

    if is_low_rag:
        response_text = (
            f"Thanks for reaching out! Because your inquiry involves a specialized scenario that doesn't have "
            f"a verified automated solution in our knowledge base, I've routed your case to our Tier-2 Technical Specialists.\n\n"
            f"[Handoff Ticket: {ticket_id} | Priority: {priority}]\n"
            f"I've attached your device information ({platform_str}) and query details to the ticket so you won't have to repeat yourself.\n\n"
            f"A human specialist is reviewing your case now. You can also DM us referencing ticket {ticket_id} for live assistance!"
        )
    else:
        response_text = (
            f"We hear you, and we're truly sorry for the hassle this has caused. "
            f"Since standard troubleshooting hasn't resolved this for you, I've escalated your case directly to our Tier-2 Human Specialist team.\n\n"
            f"[Handoff Ticket: {ticket_id} | Priority: {priority}]\n"
            f"I've attached your full case history, including your device details ({platform_str}) "
            f"and the steps you've already attempted, so you won't have to repeat yourself.\n\n"
            f"A senior representative is reviewing your case right now. You can also send us a private Direct Message quoting ticket {ticket_id} for immediate priority assistance!"
        )

    updated_messages = list(state.messages)
    updated_messages.append({"role": "agent", "content": response_text})

    return {
        "final_response": response_text,
        "messages": updated_messages,
        "is_hitl": True,
        "requires_escalation": True,
        "escalation_reason": reason,
        "handoff_ticket": ticket,
        "retrieved_cases": state.retrieved_cases if is_low_rag else [],
    }

