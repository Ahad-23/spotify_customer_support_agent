"""
Customer sentiment and escalation analyzer for Spotify support.

Evaluates multi-turn user sentiment, frustration, and escalation signals
with in-memory caching to avoid redundant API calls.
"""

import hashlib
import json
import os
from typing import Any, Dict, List, Optional
import litellm


SENTIMENT_ANALYZER_PROMPT = """You are an expert customer experience and sentiment analyzer for Spotify Support.
Evaluate the customer's latest message in context of the conversation history.

Analyze the message across these dimensions:
1. "sentiment": One of "positive", "neutral", "frustrated", "urgent".
   - Detect subtle frustration, sarcasm (e.g. "love paying for silence", "great another useless restart"), and passive-aggression.
2. "frustration_score": Float from 0.0 (calm/happy) to 1.0 (extremely angry/furious).
3. "is_human_requested": Boolean. True if customer explicitly or implicitly asks to talk to a human, person, agent, or representative.
4. "is_repeated_failure": Boolean. True if customer states that previous troubleshooting steps, restarts, reinstalls, or automated advice did not work or failed.
5. "unhelpful_prior_answer": Boolean. True if the customer complains that the previous answer was inappropriate, irrelevant, or didn't answer their question.
6. "trigger_hitl": Boolean. True if the interaction requires escalation to a Human-in-the-Loop Tier-2 Specialist (triggered if: human requested, repeated failures, frustration_score >= 0.5, or previous answer was unhelpful).
7. "hitl_reason": Short string explanation for why human escalation was triggered, or null if trigger_hitl is false.

Respond ONLY with a valid JSON object with these exact keys:
{
  "sentiment": "frustrated",
  "frustration_score": 0.85,
  "is_human_requested": false,
  "is_repeated_failure": true,
  "unhelpful_prior_answer": false,
  "trigger_hitl": true,
  "hitl_reason": "Customer reported repeated troubleshooting failures and expressed frustration"
}
"""

# In-memory LRU cache: maps hash(query, history_len, failed_count) -> sentiment result
_SENTIMENT_CACHE: Dict[str, Dict[str, Any]] = {}
_MAX_CACHE_SIZE = 1000


def _get_cache_key(query: str, history: Optional[List[Dict[str, str]]] = None, previous_failed_count: int = 0) -> str:
    history_summary = ""
    if history:
        history_summary = "|".join(f"{m.get('role', '')}:{m.get('content', '')}" for m in history[-3:])
    raw = f"{query.strip().lower()}##{history_summary}##{previous_failed_count}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_sentiment_model() -> str:
    """Returns configured model for sentiment analysis: Groq default, Gemini/OpenAI options."""
    model = os.getenv("SENTIMENT_MODEL") or os.getenv("LLM_MODEL") or os.getenv("AGENT_MODEL")
    if model:
        return model
    if os.getenv("GROQ_API_KEY"):
        m = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        return f"groq/{m}" if not m.startswith("groq/") else m
    if os.getenv("GEMINI_API_KEY"):
        m = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        return f"gemini/{m}" if not m.startswith("gemini/") else m
    if os.getenv("OPENAI_API_KEY"):
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    return "groq/openai/gpt-oss-120b"


def analyze_customer_sentiment(
    text: str,
    history: Optional[List[Dict[str, str]]] = None,
    previous_failed_count: int = 0,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """
    Analyzes customer sentiment, frustration, and HITL escalation using an LLM call.
    Results are cached in memory for identical inputs.
    """
    if not text or not text.strip():
        return {
            "sentiment": "neutral",
            "is_frustrated": False,
            "is_repeated_failure": False,
            "is_human_requested": False,
            "unhelpful_prior_answer": False,
            "frustration_score": 0.0,
            "trigger_hitl": False,
            "hitl_reason": None,
        }

    cache_key = _get_cache_key(text, history, previous_failed_count)
    if not force_refresh and cache_key in _SENTIMENT_CACHE:
        return dict(_SENTIMENT_CACHE[cache_key])

    # Check for available LLM API keys
    has_llm_key = any(
        os.getenv(k)
        for k in [
            "GROQ_API_KEY",
            "GEMINI_API_KEY",
            "OPENAI_API_KEY",
        ]
    )

    result: Optional[Dict[str, Any]] = None

    if has_llm_key:
        try:
            model = get_sentiment_model()
            conv_context = ""
            if history:
                conv_lines = [f"{m.get('role', 'user').title()}: {m.get('content', '')}" for m in history[-4:]]
                conv_context = "Conversation History:\n" + "\n".join(conv_lines) + "\n\n"

            user_prompt = f"{conv_context}Latest Customer Message:\n\"{text.strip()}\"\nPrior Failed Troubleshooting Turns: {previous_failed_count}"

            llm_res = litellm.completion(
                model=model,
                messages=[
                    {"role": "system", "content": SENTIMENT_ANALYZER_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                max_tokens=600,
                response_format={"type": "json_object"},
            )
            raw_content = llm_res.choices[0].message.content.strip()
            data = json.loads(raw_content)

            frustration_score = float(data.get("frustration_score", 0.0))
            is_human_requested = bool(data.get("is_human_requested", False))
            is_repeated_failure = bool(data.get("is_repeated_failure", False))
            unhelpful_prior = bool(data.get("unhelpful_prior_answer", False))
            sentiment_tag = str(data.get("sentiment", "neutral")).lower()
            trigger_hitl = bool(data.get("trigger_hitl", False))
            hitl_reason = data.get("hitl_reason")

            is_frustrated = frustration_score >= 0.4 or sentiment_tag in ["frustrated", "urgent"]

            result = {
                "sentiment": sentiment_tag,
                "is_frustrated": is_frustrated,
                "is_repeated_failure": is_repeated_failure,
                "is_human_requested": is_human_requested,
                "unhelpful_prior_answer": unhelpful_prior,
                "frustration_score": round(frustration_score, 2),
                "trigger_hitl": trigger_hitl or is_human_requested or frustration_score >= 0.5,
                "hitl_reason": hitl_reason if trigger_hitl else None,
            }
        except Exception:
            result = None

    # Fallback heuristic if external LLM call is unavailable (e.g. rate-limit or air-gapped test)
    if result is None:
        lower_text = text.lower()
        human_req = any(h in lower_text for h in [
            "human", "person", "agent", "representative", "specialist", "someone real",
            "not a bot", "talk to", "speak to", "transfer me", "switch me"
        ])
        rep_fail = any(f in lower_text for f in [
            "already tried", "already did", "didn't work", "did not work", "didn't fix", "did not fix",
            "still not", "still broken", "still crashing", "still freezing", "still skipping",
            "still greyed out", "still doesn't play", "still cant", "still can't",
            "none of your", "done this", "tried everything", "steps helped", "three times", "twice"
        ])
        unhelpful = any(u in lower_text for u in [
            "didn't answer", "does not answer", "unhelpful", "useless", "irrelevant",
            "waste of", "generic", "wrong answer", "stop giving me", "makes no sense"
        ])
        frustrated = any(w in lower_text for w in [
            "angry", "furious", "hate", "terrible", "worst", "sick of", "tired of",
            "ridiculous", "garbage", "stupid", "broken", "annoying", "glitch", "bug", "fail"
        ]) or unhelpful or ("love paying" in lower_text and "silence" in lower_text)

        score = 0.0
        if frustrated:
            score += 0.5
        if rep_fail:
            score += 0.3
        if human_req:
            score += 0.2
        if previous_failed_count > 0:
            score += min(0.3, previous_failed_count * 0.15)
        score = min(1.0, round(score, 2))

        trig = human_req or rep_fail or (frustrated and score >= 0.5) or (previous_failed_count >= 2)
        reason = None
        if human_req:
            reason = "Customer explicitly requested a human representative"
        elif rep_fail:
            reason = "Repeated troubleshooting failure reported by customer"
        elif frustrated:
            reason = "Customer dissatisfaction or unhelpful automated answer detected"
        elif previous_failed_count >= 2:
            reason = "Multiple unresolved dialogue turns exceeded threshold"

        result = {
            "sentiment": "frustrated" if frustrated else "neutral",
            "is_frustrated": frustrated,
            "is_repeated_failure": rep_fail,
            "is_human_requested": human_req,
            "unhelpful_prior_answer": unhelpful,
            "frustration_score": score,
            "trigger_hitl": trig,
            "hitl_reason": reason,
        }

    # Save to in-memory cache
    if len(_SENTIMENT_CACHE) >= _MAX_CACHE_SIZE:
        _SENTIMENT_CACHE.pop(next(iter(_SENTIMENT_CACHE)))
    _SENTIMENT_CACHE[cache_key] = result

    return dict(result)


def clear_sentiment_cache():
    """Clears the in-memory sentiment cache."""
    _SENTIMENT_CACHE.clear()


def is_frustrated_query(text: str) -> bool:
    """Helper for checking if text expresses frustration."""
    return analyze_customer_sentiment(text)["is_frustrated"]


def is_repeated_troubleshooting_failure(text: str) -> bool:
    """Helper for checking if text reports a prior failure."""
    return analyze_customer_sentiment(text)["is_repeated_failure"]


def is_human_agent_requested(text: str) -> bool:
    """Helper for checking if text requests human escalation."""
    return analyze_customer_sentiment(text)["is_human_requested"]
