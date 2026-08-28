"""
LLM Case Narrator Module

Translates SHAP values and transaction features into plain-English
analyst-readable narratives using an LLM.

Resilience features:
- Tenacity retries (exponential backoff) around Anthropic API calls
- Circuit breaker integration to prevent cascading failures
- Honest fallback narrative when LLM unavailable
- Explicit timeout on all LLM calls
"""

import json
import logging
import os
from typing import Any

from tenacity import (
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential,
)

from src.fraudlens.config import LLM_MAX_TOKENS, LLM_MODEL, LLM_TEMPERATURE
from src.fraudlens.llm.cost_tracker import cost_tracker

logger = logging.getLogger(__name__)

# Tenacity retry policy for LLM calls
# Retry up to 3 times with exponential backoff (2s, 4s, 8s)
_LLM_RETRY = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=2, max=10),
    before_sleep=before_sleep_log(logger, logging.DEBUG),
    reraise=True,
)


class CaseNarrator:
    """
    Generate plain-English narratives for flagged transactions.

    Takes SHAP values and transaction features, sends them to an LLM,
    and returns a short analyst-readable explanation.

    Resilience:
    - Retries LLM calls up to 3 times with exponential backoff
    - Checks the circuit breaker before making LLM calls
    - Falls back to an honest template-based narrative when LLM unavailable
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = LLM_MODEL,
        max_tokens: int = LLM_MAX_TOKENS,
        temperature: float = LLM_TEMPERATURE,
    ) -> None:
        """
        Args:
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            model: LLM model identifier
            max_tokens: Maximum tokens in the response
            temperature: LLM temperature (lower = more deterministic)
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = None
        self._circuit_breaker = None  # Set by main.py's lifespan

    def set_circuit_breaker(self, breaker: Any) -> None:
        """Set the circuit breaker instance (called during app initialization)."""
        self._circuit_breaker = breaker

    def _init_client(self) -> Any:
        """Initialize the Anthropic client."""
        try:
            from anthropic import Anthropic

            self._client = Anthropic(api_key=self.api_key)
        except ImportError:
            logger.error(
                "anthropic package not installed. Install with: pip install anthropic"
            )
            raise

    def narrate(
        self,
        transaction: dict[str, Any],
        fraud_probability: float,
        shap_explanation: list[dict[str, Any]],
        is_fraud: bool,
    ) -> str:
        """
        Generate a natural-language narrative for a flagged transaction.

        Uses retry logic with exponential backoff for LLM calls.
        Falls back to an honest template-based narrative if LLM unavailable.

        Args:
            transaction: The raw transaction features
            fraud_probability: Model's fraud probability score
            shap_explanation: List of top SHAP features with values
            is_fraud: Whether the transaction was flagged as fraud

        Returns:
            Plain-English narrative string
        """
        if not self.api_key:
            return self._fallback_narrative(
                shap_explanation, fraud_probability, is_fraud
            )

        # Check circuit breaker before attempting LLM call
        if self._circuit_breaker is not None and self._circuit_breaker.is_open():
            logger.warning("Circuit breaker open — skipping LLM call")
            return self._fallback_narrative(
                shap_explanation, fraud_probability, is_fraud
            )

        self._init_client()
        prompt = self._build_prompt(
            transaction, fraud_probability, shap_explanation, is_fraud
        )

        try:
            response = self._call_llm_with_response(prompt)
            if self._circuit_breaker is not None:
                self._circuit_breaker.record_success()

            # Track cost from response usage
            if hasattr(response, "usage") and response.usage is not None:
                input_tok = getattr(response.usage, "input_tokens", 0)
                output_tok = getattr(response.usage, "output_tokens", 0)
                cost_tracker.record_call(
                    model=self.model,
                    input_tokens=input_tok,
                    output_tokens=output_tok,
                    endpoint="narrate",
                )

            narrative = response.content[0].text.strip()
            logger.info("LLM narrative generated (%d chars)", len(narrative))
            return narrative
        except (RuntimeError, ValueError, OSError) as e:
            logger.warning("LLM call failed after retries: %s", e)
            if self._circuit_breaker is not None:
                self._circuit_breaker.record_failure()
            return self._fallback_narrative(
                shap_explanation, fraud_probability, is_fraud
            )

    def _call_llm_with_response(self, prompt: str) -> Any:
        """Make the LLM call with tenacity retry logic, returning the full response."""

        @_LLM_RETRY
        def _do_call() -> Any:
            return self._client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )

        return _do_call()

    def _build_prompt(
        self,
        transaction: dict[str, Any],
        probability: float,
        shap_explanation: list[dict[str, Any]],
        is_fraud: bool,
    ) -> str:
        """Build the prompt for the LLM."""
        top_features = shap_explanation[:5]
        features_str = json.dumps(top_features, indent=2)
        amount = transaction.get("Amount", "N/A")
        time_val = transaction.get("Time", "N/A")
        hour = (
            round((float(time_val) % 86400) / 3600, 1) if time_val != "N/A" else "N/A"
        )

        return f"""You are a fraud analysis assistant. Given transaction details and SHAP values, write a short, plain-English paragraph explaining this transaction.

Transaction details:
- Amount: ${amount}
- Time: {hour} hours since first transaction
- Fraud Probability: {probability:.1%}
- Flagged as Fraud: {is_fraud}

Top contributing features (SHAP analysis):
{features_str}

Write 2-3 sentences explaining:
1. What about this transaction is unusual
2. Which features contributed most to the decision
3. Whether this matches known fraud patterns

Be specific, concise, and avoid technical jargon. Write as if for a non-technical fraud analyst."""

    def _fallback_narrative(
        self,
        shap_explanation: list[dict[str, Any]],
        fraud_probability: float,
        is_fraud: bool,
    ) -> str:
        """Generate an honest template-based narrative when LLM is unavailable.

        The narrative clearly states that it's an automated summary, not
        an LLM-generated narrative, so analysts are not misled by a
        confident-sounding but generic fraud story.
        """
        top = shap_explanation[:3] if shap_explanation else []
        top_features_str = ", ".join(
            f"{f['feature']} ({f.get('value', f.get('shap_value', 0)):.2f}, {f['impact']})"
            for f in top
        )

        prefix = "[Automated summary — narrative generation unavailable] "

        if is_fraud:
            narrative = (
                prefix + f"Transaction flagged as potentially fraudulent "
                f"({fraud_probability:.1%} confidence). "
                f"Top indicators: {top_features_str}. "
                f"Recommended action: manual review by a fraud analyst."
            )
        else:
            narrative = (
                prefix + f"Transaction appears legitimate "
                f"({1 - fraud_probability:.1%} confidence). "
                f"No strong fraud indicators detected."
            )

        return narrative


def create_case_narrator() -> CaseNarrator:
    """Create a CaseNarrator instance (reads API key from environment)."""
    return CaseNarrator()
