"""
Prediction Router — /predict and /predict/batch endpoints.

Handles single and batch fraud predictions with anomaly scores.
Performance-v1: SHAP only computed when ?explain=true is explicitly
requested, BackgroundTasks for async SHAP, vectorized prediction path.
"""

import logging

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request

from api.auth import require_api_key
from api.providers import get_anomaly_detector, get_predictor
from api.rate_limit import limiter
from api.schemas import (
    BatchInput,
    BatchPredictionItem,
    BatchResponse,
    BatchSummary,
    BusinessImpact,
    Explanation,
    PredictionResponse,
    ShapFeature,
    TransactionInput,
)
from src.fraudlens.config import AVG_FRAUD_LOSS, REVIEW_COST

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["predictions"])


@router.post("/predict", response_model=PredictionResponse)
@limiter.limit("100/minute")
async def predict_single(
    request: Request,
    transaction: TransactionInput,
    background_tasks: BackgroundTasks,
    explain: bool = Query(
        False,
        description="Compute SHAP explanation (slow). Off by default for performance.",
    ),
    api_key: str = Depends(require_api_key),
) -> PredictionResponse:
    """
    Predict fraud probability for a single transaction.

    By default SHAP explanation is skipped for performance.
    Pass ?explain=true to get the full SHAP breakdown.
    Returns fraud probability, anomaly score, and business impact.
    """
    pred = get_predictor()
    if pred is None or pred.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        tx_dict = transaction.dict()

        # Use cache-enabled, vectorized prediction path
        if explain:
            result = pred.predict_single(tx_dict, return_shap=True, use_cache=True)
        else:
            # Fast path — no SHAP, cached
            result = pred.predict_single(tx_dict, return_shap=False, use_cache=True)

            # Auto-queue background SHAP for high-risk transactions
            # Client gets fast response; SHAP is computed asynchronously
            if result["is_fraud"]:
                background_tasks.add_task(pred._compute_shap_async, tx_dict, result)

        # Get anomaly score from Isolation Forest (vectorized numpy path)
        anomaly_score = None
        try:
            anomaly_det = get_anomaly_detector()
            if anomaly_det is not None:
                raw_model = (
                    anomaly_det.model if hasattr(anomaly_det, "model") else anomaly_det
                )
                if raw_model is not None:
                    tx_array = pred._vectorize_transaction(transaction.dict())
                    scores = raw_model.score_samples(tx_array)
                    min_s, max_s = scores.min(), scores.max()
                    probas = 1 - (scores - min_s) / (max_s - min_s + 1e-10)
                    anomaly_score = round(float(probas[0]), 4)
        except Exception as anomaly_err:
            logger.warning("Anomaly score computation failed: %s", anomaly_err)

        # Build response
        explanation = None
        if "explanation" in result:
            explanation = Explanation(
                summary=result["explanation"]["summary"],
                top_features=[
                    ShapFeature(**f) for f in result["explanation"]["top_features"]
                ],
            )

        business = BusinessImpact(
            estimated_loss=AVG_FRAUD_LOSS,
            action="FLAG for manual review" if result["is_fraud"] else "AUTO-APPROVE",
            review_cost=REVIEW_COST,
        )

        return PredictionResponse(
            fraud_probability=result["fraud_probability"],
            decision=result["decision"],
            threshold_used=result["threshold_used"],
            is_fraud=result["is_fraud"],
            anomaly_score=anomaly_score,
            explanation=explanation,
            business_impact=business,
        )
    except Exception as e:
        logger.error("Prediction failed: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Model prediction failed: {str(e)}"
        )


@router.post("/predict/batch", response_model=BatchResponse)
@limiter.limit("30/minute")
async def predict_batch(
    request: Request,
    batch: BatchInput,
    api_key: str = Depends(require_api_key),
) -> BatchResponse:
    """
    Predict fraud for multiple transactions (faster, no SHAP).

    Returns a summary with counts and estimated review costs.
    """
    pred = get_predictor()
    if pred is None or pred.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        transactions = [t.dict() for t in batch.transactions]
        X = pd.DataFrame(transactions)

        # Reorder columns to match model's expected feature order
        # TransactionInput defines Time/Amount before V1-V28, but model
        # expects V1-V28 first. This prevents train/serve skew.
        if pred.feature_names:
            missing = [f for f in pred.feature_names if f not in X.columns]
            if missing:
                raise HTTPException(
                    status_code=422, detail=f"Missing features: {missing}"
                )
            X = X[pred.feature_names]

        results = pred.predict_batch(X)

        predictions = []
        flagged_fraud = 0
        for _, row in results.iterrows():
            predictions.append(
                BatchPredictionItem(
                    fraud_probability=round(float(row["fraud_probability"]), 4),
                    decision=row["decision"],
                    is_fraud=bool(row["prediction"]),
                )
            )
            if row["prediction"]:
                flagged_fraud += 1

        summary = BatchSummary(
            total=len(predictions),
            flagged_fraud=flagged_fraud,
            flagged_legitimate=len(predictions) - flagged_fraud,
            estimated_review_cost=round(flagged_fraud * REVIEW_COST, 2),
        )

        return BatchResponse(predictions=predictions, summary=summary)
    except Exception as e:
        logger.error("Batch prediction failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
