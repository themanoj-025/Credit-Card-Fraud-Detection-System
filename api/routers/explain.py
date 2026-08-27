"""
Explanation Router — /explain endpoint.

Returns SHAP values + LLM narrative for a transaction.

Resilience:
- Uses typed exceptions instead of bare except Exception
- LLM failures gracefully fall back to template narrative
- Circuit breaker prevents cascading LLM failures
- Retry logic with exponential backoff for LLM calls
"""

import logging

from fastapi import APIRouter, Depends, Request
from tenacity import (
    before_sleep_log,
    retry,
    stop_after_attempt,
    wait_exponential,
)

from api.auth import require_api_key
from api.exceptions import (
    LLMServiceUnavailable,
    ModelNotLoadedError,
    PredictionError,
)
from api.providers import get_case_narrator, get_predictor
from api.rate_limit import limiter
from api.schemas import ExplanationResponse, TransactionInput

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["explainability"])

# Tenacity retry policy for LLM calls within narrate()
# (CaseNarrator.narrate() already has its own retry; this is a safety net
#  for the outer explain endpoint in case narrate() itself throws)
_EXPLAIN_RETRY = retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=2, min=1, max=8),
    before_sleep=before_sleep_log(logger, logging.DEBUG),
    reraise=True,
)


@router.post("/explain", response_model=ExplanationResponse)
@limiter.limit("60/minute")
async def explain_transaction(
    request: Request,
    transaction: TransactionInput,
    api_key: str = Depends(require_api_key),
) -> ExplanationResponse:
    """
    Get SHAP values and LLM narrative for a transaction.

    Pydantic validates the input (e.g., Amount >= 0) before the model check.
    If the LLM is unavailable, SHAP values are still returned without narrative.
    """
    predictor = get_predictor()
    if predictor is None or predictor.model is None:
        raise ModelNotLoadedError()

    # Access circuit breaker from app state
    circuit_breaker = getattr(request.app.state, "llm_circuit_breaker", None)
    if circuit_breaker is not None and circuit_breaker.is_open():
        logger.warning("Explain rejected — LLM circuit breaker is open")
        # Still return SHAP values, just skip LLM narrative
        result = predictor.predict_single(transaction.dict(), return_shap=True)
        shap_values = {}
        if "explanation" in result:
            for f in result["explanation"]["top_features"]:
                shap_values[f["feature"]] = f["shap_value"]
        return ExplanationResponse(
            fraud_probability=result["fraud_probability"],
            decision=result["decision"],
            shap_values=shap_values,
            narrative=None,
        )

    try:
        result = predictor.predict_single(transaction.dict(), return_shap=True)

        shap_values = {}
        if "explanation" in result:
            for f in result["explanation"]["top_features"]:
                shap_values[f["feature"]] = f["shap_value"]

        # LLM narrative — graceful fallback if unavailable
        narrative = None
        case_narrator = get_case_narrator()
        if case_narrator is not None:
            shap_features = result.get("explanation", {}).get("top_features", [])
            narrative = case_narrator.narrate(
                transaction=transaction,
                fraud_probability=result["fraud_probability"],
                shap_explanation=shap_features,
                is_fraud=result["is_fraud"],
            )
            if circuit_breaker is not None:
                circuit_breaker.record_success()

        return ExplanationResponse(
            fraud_probability=result["fraud_probability"],
            decision=result["decision"],
            shap_values=shap_values,
            narrative=narrative,
        )
    except (ModelNotLoadedError, LLMServiceUnavailable):
        raise
    except (ValueError, TypeError, KeyError, OSError) as e:
        logger.error("Explanation failed: %s", e)
        if circuit_breaker is not None:
            circuit_breaker.record_failure()
        raise PredictionError(detail=str(e), original=e)
