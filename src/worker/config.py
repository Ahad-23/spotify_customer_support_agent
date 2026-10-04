"""Shared configuration for the autonomous task worker."""

from typing import Any
import os
from pathlib import Path

import dotenv
import litellm


REPO_ROOT = Path(__file__).resolve().parents[2]
dotenv.load_dotenv(REPO_ROOT / ".env")

OSTICKET_URL = os.getenv("OSTICKET_URL", "http://localhost:8088")
OSTICKET_STAFF_USER = os.getenv("OSTICKET_STAFF_USER") or os.getenv("OSTICKET_ADMIN_USER") or "ostadmin"
OSTICKET_STAFF_PASS = os.getenv("OSTICKET_STAFF_PASS") or os.getenv("OSTICKET_ADMIN_PASS") or "Admin1"

MAX_PLAN_STEPS = int(os.getenv("MAX_PLAN_STEPS", "15"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

import logging
from litellm._logging import verbose_logger

# Suppress LiteLLM logging noise and async logging workers on dedicated loops
litellm.suppress_debug_info = True
litellm.telemetry = False
litellm.num_retries = 3
litellm.turn_off_message_logging = True

verbose_logger.setLevel(logging.ERROR)
logging.getLogger("LiteLLM").setLevel(logging.ERROR)
logging.getLogger("litellm").setLevel(logging.ERROR)


def silence_litellm_async_logging() -> None:
    """Disable LiteLLM's leaky background logging worker to prevent event loop warnings on Windows."""
    try:
        from litellm.litellm_core_utils import logging_worker

        def _safe_no_op_enqueue(async_coroutine=None, *args, **kwargs):
            if async_coroutine is not None:
                try:
                    async_coroutine.close()
                except Exception:
                    pass

        logging_worker.GLOBAL_LOGGING_WORKER.start = lambda *a, **k: None
        logging_worker.GLOBAL_LOGGING_WORKER.ensure_initialized_and_enqueue = _safe_no_op_enqueue
        logging_worker.LoggingWorker.start = lambda *a, **k: None
        logging_worker.LoggingWorker.ensure_initialized_and_enqueue = staticmethod(_safe_no_op_enqueue)
    except Exception:
        pass


silence_litellm_async_logging()


def get_llm_model() -> str:
    """Resolve the LLM model: strictly defaults to groq/openai/gpt-oss-120b."""
    model = os.getenv("LLM_MODEL") or os.getenv("AGENT_MODEL") or os.getenv("GROQ_MODEL")
    if model:
        if "gpt-oss" in model and not model.startswith("groq/"):
            return f"groq/{model}"
        return model
    if os.getenv("GROQ_API_KEY"):
        return "groq/openai/gpt-oss-120b"
    if os.getenv("GEMINI_API_KEY"):
        m = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        return f"gemini/{m}" if not m.startswith("gemini/") else m
    return "groq/openai/gpt-oss-120b"


def get_fallbacks() -> list[str]:
    """Return fallback models (defaults to alternate Groq models to prevent TPM exhaustion)."""
    fb_env = os.getenv("FALLBACK_MODELS")
    current = get_llm_model()
    if fb_env:
        return [m.strip() for m in fb_env.split(",") if m.strip() and m.strip() != current]

    # Automatic fallbacks among available Groq models
    candidates = ["groq/openai/gpt-oss-20b", "groq/qwen/qwen3.8-27b"]
    return [c for c in candidates if c != current]


def safe_llm_completion(
    *,
    model: str | None = None,
    messages: list[dict[str, Any]],
    temperature: float = 0.1,
    max_tokens: int = 800,
    response_format: dict[str, Any] | None = None,
    fallbacks: list[str] | None = None,
    **kwargs: Any,
) -> Any:
    """Execute LLM completion with automatic Groq TPM rate-limit rotation and backoff."""
    import re
    import time

    primary_model = model or get_llm_model()
    models_to_try = [primary_model]
    effective_fbs = fallbacks if fallbacks is not None else get_fallbacks()
    for fb in effective_fbs:
        if fb and fb not in models_to_try:
            models_to_try.append(fb)

    # Ensure all available fast Groq models are always in the fallback chain
    for cand in ["groq/openai/gpt-oss-120b", "groq/openai/gpt-oss-20b", "groq/qwen/qwen3.8-27b"]:
        if cand not in models_to_try:
            models_to_try.append(cand)

    last_error: Exception | None = None
    kwargs_clean = dict(kwargs)
    kwargs_clean.pop("num_retries", None)
    kwargs_clean.pop("fallbacks", None)

    for cycle in range(3):
        min_wait = 3.0
        all_rate_limited = True

        for current_model in models_to_try:
            try:
                return litellm.completion(
                    model=current_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    **kwargs_clean,
                )
            except Exception as exc:
                last_error = exc
                err_str = str(exc)
                is_rate_limit = (
                    "rate_limit" in err_str.lower()
                    or "429" in err_str
                    or "RateLimitError" in type(exc).__name__
                    or "TPM" in err_str
                )

                if is_rate_limit:
                    match = re.search(r"try again in (\d+(?:\.\d+)?)s", err_str, re.I)
                    if match:
                        try:
                            min_wait = max(min_wait, float(match.group(1)) + 1.0)
                        except Exception:
                            pass
                    logging.getLogger(__name__).info(
                        "Model %s hit TPM rate limit. Immediately trying next fallback model...",
                        current_model,
                    )
                    continue  # immediately try next model in the pool!

                all_rate_limited = False
                logging.getLogger(__name__).warning(
                    "LLM call on %s failed with non-rate-limit error: %s", current_model, exc
                )

        if all_rate_limited and cycle < 2:
            logging.getLogger(__name__).warning(
                "All LLM models in pool currently rate-limited (cycle %d/3). Sleeping %.2fs before retry...",
                cycle + 1,
                min_wait,
            )
            time.sleep(min_wait)

    if last_error:
        raise last_error
    raise RuntimeError("LLM completion failed for all configured models")

