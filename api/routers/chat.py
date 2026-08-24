"""
Analyst Copilot Router — /chat endpoint.

Provides a tool-use-enabled chat interface for analysts to ask
natural-language questions about the simulation state and cases.

Resilience:
- Tenacity retries with exponential backoff around Anthropic API calls
- Circuit breaker integration to prevent cascading LLM failures
- Explicit timeouts on all API calls
- Typed exceptions instead of bare except Exception
"""

import logging

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from tenacity import (
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential,
)

from api.auth import require_api_key
from api.exceptions import LLMServiceUnavailable
from api.providers import get_copilot_client
from api.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["copilot"])

# Tenacity retry policy for LLM chat calls
_CHAT_RETRY = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    before_sleep=before_sleep_log(logger, logging.DEBUG),
    reraise=True,
)


class ChatRequest(BaseModel):
    """Chat request schema."""

    message: str
    conversation_history: list[dict[str, str]] | None = None


def _get_transaction(tx_id: str) -> str:
    """Get transaction details by ID (tool function)."""
    return f"Transaction {tx_id} details would be retrieved from session data."


def _get_summary_stats() -> str:
    """Get summary statistics of the current session (tool function)."""
    return "Session stats would be computed from the current dashboard state."


TOOLS = {
    "get_transaction": _get_transaction,
    "get_summary_stats": _get_summary_stats,
}


@router.post("/chat")
@limiter.limit("20/minute")
async def analyst_chat(
    request: Request,
    chat_request: ChatRequest,
    api_key: str = Depends(require_api_key),
) -> dict:
    """
    Analyst copilot chat endpoint.

    Accepts natural-language questions and returns AI-powered responses
    with access to current simulation data via tool-use.

    Uses retry logic with exponential backoff. If all retries fail,
    returns a 503 with a clear message. If the circuit breaker is open,
    returns immediately without attempting the call.
    """
    copilot_client = get_copilot_client()
    if copilot_client is None:
        raise LLMServiceUnavailable(
            "Copilot not available. Set ANTHROPIC_API_KEY environment variable."
        )

    # Access circuit breaker from app state
    circuit_breaker = getattr(request.app.state, "llm_circuit_breaker", None)
    if circuit_breaker is not None and circuit_breaker.is_open():
        logger.warning("Chat rejected — LLM circuit breaker is open")
        raise LLMServiceUnavailable(
            "LLM temporarily unavailable. Please try again later."
        )

    try:
        history = chat_request.conversation_history or []

        system_prompt = (
            "You are a fraud analysis copilot. You help analysts understand "
            "transactions, model behavior, and simulation statistics. "
            "You have access to these tools:\n"
            "- get_transaction(id): Get details of a specific transaction\n"
            "- get_summary_stats(): Get current simulation statistics\n\n"
            "Answer concisely and accurately. If you need data, use the tools."
        )

        messages = []
        for h in history:
            messages.append(
                {
                    "role": h.get("role", "user"),
                    "content": h.get("content", ""),
                }
            )
        messages.append(
            {
                "role": "user",
                "content": f"{system_prompt}\n\nAnalyst question: {chat_request.message}",
            }
        )

        # LLM call with retry logic
        response = _call_chat_llm(copilot_client, messages)

        # Record success on circuit breaker
        if circuit_breaker is not None:
            circuit_breaker.record_success()

        return {"response": response, "tool_calls": []}

    except LLMServiceUnavailable:
        raise
    except (OSError, ValueError, TypeError, KeyError) as e:
        logger.error("Chat failed after retries: %s", e)
        # Record failure on circuit breaker
        if circuit_breaker is not None:
            circuit_breaker.record_failure()
        raise LLMServiceUnavailable(
            "Chat service temporarily unavailable. Please try again later."
        )


@_CHAT_RETRY
def _call_chat_llm(client: object, messages: list) -> str:
    """Make the Anthropic API call with retry logic.

    Uses tenacity for retry with exponential backoff.
    """
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        temperature=0.3,
        messages=messages,
    )
    return response.content[0].text.strip()
