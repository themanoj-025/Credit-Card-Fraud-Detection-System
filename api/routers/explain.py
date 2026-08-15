"""
Explanation Router — /explain endpoint.

Returns SHAP values + LLM narrative for a transaction.

Resilience:
- Uses typed exceptions instead of bare except Exception
- LLM failures gracefully fall back to template narrative
- Circuit breaker prevents cascading LLM failures
"""

import logging

from fastapi import APIRouter, Depends, Request

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

        return ExplanationResponse(
            fraud_probability=result["fraud_probability"],
            decision=result["decision"],
            shap_values=shap_values,
            narrative=narrative,
        )
    except (ModelNotLoadedError, LLMServiceUnavailable):
        raise
    except Exception as e:
        logger.error("Explanation failed: %s", e)
        raise PredictionError(detail=str(e), original=e)
