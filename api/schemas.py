"""
FraudLens API Schemas

Pydantic models for request validation and response serialization.
"""

import math
from typing import Any

from pydantic import BaseModel, Field, validator


class TransactionInput(BaseModel):
    """Single transaction to predict.

    Rejects NaN and Infinity values explicitly with custom validators.
    """

    Time: float = Field(..., description="Transaction time in seconds")
    Amount: float = Field(..., ge=0, description="Transaction amount ($)")
    V1: float = Field(default=0.0, description="PCA component V1")
    V2: float = Field(default=0.0, description="PCA component V2")
    V3: float = Field(default=0.0, description="PCA component V3")
    V4: float = Field(default=0.0, description="PCA component V4")
    V5: float = Field(default=0.0, description="PCA component V5")
    V6: float = Field(default=0.0, description="PCA component V6")
    V7: float = Field(default=0.0, description="PCA component V7")
    V8: float = Field(default=0.0, description="PCA component V8")
    V9: float = Field(default=0.0, description="PCA component V9")
    V10: float = Field(default=0.0, description="PCA component V10")
    V11: float = Field(default=0.0, description="PCA component V11")
    V12: float = Field(default=0.0, description="PCA component V12")
    V13: float = Field(default=0.0, description="PCA component V13")
    V14: float = Field(default=0.0, description="PCA component V14")
    V15: float = Field(default=0.0, description="PCA component V15")
    V16: float = Field(default=0.0, description="PCA component V16")
    V17: float = Field(default=0.0, description="PCA component V17")
    V18: float = Field(default=0.0, description="PCA component V18")
    V19: float = Field(default=0.0, description="PCA component V19")
    V20: float = Field(default=0.0, description="PCA component V20")
    V21: float = Field(default=0.0, description="PCA component V21")
    V22: float = Field(default=0.0, description="PCA component V22")
    V23: float = Field(default=0.0, description="PCA component V23")
    V24: float = Field(default=0.0, description="PCA component V24")
    V25: float = Field(default=0.0, description="PCA component V25")
    V26: float = Field(default=0.0, description="PCA component V26")
    V27: float = Field(default=0.0, description="PCA component V27")
    V28: float = Field(default=0.0, description="PCA component V28")

    @validator("Amount")
    def amount_must_be_finite(cls, v):
        """Validate Amount is finite and non-negative."""
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            raise ValueError("Amount must be a finite number (not NaN/Inf)")
        if isinstance(v, (int, float)) and v < 0:
            raise ValueError("Amount must be non-negative")
        return v


class BatchInput(BaseModel):
    """Batch of transactions to predict."""

    transactions: list[TransactionInput] = Field(
        ..., min_length=1, max_length=1000, description="List of transactions"
    )


class ShapFeature(BaseModel):
    """SHAP feature contribution for a prediction."""

    feature: str = Field(..., description="Feature name")
    value: float = Field(..., description="Feature value")
    shap_value: float = Field(..., description="SHAP contribution value")
    impact: str = Field(..., description="Direction of impact (increases/decreases)")


class Explanation(BaseModel):
    """SHAP explanation for a prediction."""

    summary: str = Field(..., description="Plain-English summary of why flagged")
    top_features: list[ShapFeature] = Field(
        ..., description="Top contributing features"
    )


class BusinessImpact(BaseModel):
    """Business impact analysis for a prediction."""

    estimated_loss: float = Field(..., description="Potential fraud loss ($)")
    action: str = Field(..., description="Recommended action")
    review_cost: float = Field(..., description="Cost to review this transaction ($)")


class PredictionResponse(BaseModel):
    """Response for a single prediction."""

    fraud_probability: float = Field(..., ge=0, le=1)
    decision: str = Field(..., pattern="^(FRAUD|LEGITIMATE)$")
    threshold_used: float = Field(..., ge=0, le=1)
    is_fraud: bool
    anomaly_score: float | None = Field(None, ge=0, le=1)
    explanation: Explanation | None = None
    business_impact: BusinessImpact | None = None


class BatchPredictionItem(BaseModel):
    """Individual prediction in a batch response."""

    fraud_probability: float
    decision: str
    is_fraud: bool


class BatchSummary(BaseModel):
    """Summary statistics for a batch prediction."""

    total: int
    flagged_fraud: int
    flagged_legitimate: int
    estimated_review_cost: float


class BatchResponse(BaseModel):
    """Response for batch predictions."""

    predictions: list[BatchPredictionItem]
    summary: BatchSummary


class ExplanationResponse(BaseModel):
    """Response for an explain request."""

    fraud_probability: float
    decision: str
    shap_values: dict[str, float]
    narrative: str | None = None


class SimilarCase(BaseModel):
    """A similar historical case."""

    similarity_score: float
    actual_outcome: str
    features: dict[str, float]


class CursorPagination(BaseModel):
    """Cursor-based pagination metadata."""

    next_cursor: str | None = Field(
        None, description="Cursor for the next page. Null if no more results."
    )
    has_more: bool = Field(
        False, description="Whether there are more results available"
    )
    limit: int = Field(..., description="Maximum results per page")
    total: int | None = Field(None, description="Total number of results (if known)")


class SimilarCasesResponse(BaseModel):
    """Response for similar cases retrieval with cursor pagination."""

    transaction_id: str
    similar_cases: list[SimilarCase]
    pagination: CursorPagination = Field(
        ..., description="Pagination metadata for navigating results"
    )


class ChatResponse(BaseModel):
    """Response from the analyst copilot chat."""

    response: str
    tool_calls: list[dict[str, Any]] | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    model_loaded: bool
    version: str = "2.0.0"


class FeedbackCreate(BaseModel):
    """Request to submit feedback on a prediction."""

    prediction_id: str = Field(
        ..., description="UUID of the prediction to provide feedback on"
    )
    confirmed_fraud: bool = Field(..., description="Whether the analyst confirms fraud")
    analyst_notes: str | None = Field(
        None, max_length=2000, description="Analyst notes"
    )
    reviewed_by: str | None = Field(
        None, max_length=128, description="Analyst identifier"
    )


class FeedbackResponse(BaseModel):
    """Response for a feedback submission."""

    id: str
    prediction_id: str
    confirmed_fraud: bool
    analyst_notes: str | None
    reviewed_by: str | None
    created_at: str


class FeedbackStatistics(BaseModel):
    """Feedback statistics response."""

    total_feedback: int
    confirmed_fraud: int
    confirmed_legitimate: int


class ModelInfoResponse(BaseModel):
    """Model metadata response."""

    model_type: str
    threshold: float
    n_features: int
    features: list[str]
    avg_fraud_loss: float
    review_cost: float
    pr_auc: float | None = None
