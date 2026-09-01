"""
FraudLens — LLM Cost Tracking

Tracks Anthropic API costs per-call and provides aggregate views.
Costs are computed from usage tokens reported in Anthropic responses
using a config-driven price table.

Usage:
    from src.fraudlens.llm.cost_tracker import cost_tracker
    cost = cost_tracker.record_call(model="claude-sonnet-4-20250514",
                                     input_tokens=500, output_tokens=200,
                                     endpoint="narrate")
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Price Table (per 1M tokens)
# Config-driven: update here when Anthropic changes pricing.
# Source: https://docs.anthropic.com/en/docs/about-claude/models
PRICING_TABLE: dict[str, dict[str, float]] = {
    "claude-sonnet-4-20250514": {
        "input_per_1m": 3.00,
        "output_per_1m": 15.00,
    },
    "claude-3-5-sonnet-20241022": {
        "input_per_1m": 3.00,
        "output_per_1m": 15.00,
    },
    "claude-3-haiku-20240307": {
        "input_per_1m": 0.25,
        "output_per_1m": 1.25,
    },
    "claude-3-opus-20240229": {
        "input_per_1m": 15.00,
        "output_per_1m": 75.00,
    },
}

# Default pricing for unknown models
_DEFAULT_PRICING = {"input_per_1m": 3.00, "output_per_1m": 15.00}


@dataclass
class CallRecord:
    """A single LLM API call record."""

    timestamp: float
    model: str
    endpoint: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    status: str = "success"


@dataclass
class DailySummary:
    """Aggregate cost summary for a day."""

    date: str
    total_cost_usd: float
    total_calls: int
    total_input_tokens: int
    total_output_tokens: int
    by_model: dict[str, float] = field(default_factory=dict)
    by_endpoint: dict[str, float] = field(default_factory=dict)


class CostTracker:
    """
    Thread-safe LLM cost tracker.

    Records per-call costs and provides aggregate views for:
    - Today's spend
    - This month's spend
    - Per-model breakdown
    - Per-endpoint breakdown
    """

    def __init__(self, pricing_table: dict | None = None) -> None:
        self._pricing = pricing_table or PRICING_TABLE
        self._records: list[CallRecord] = []
        self._lock = threading.Lock()

    def compute_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """
        Compute the cost of a single LLM call.

        Args:
            model: Model identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            Cost in USD
        """
        pricing = self._pricing.get(model, _DEFAULT_PRICING)
        input_cost = (input_tokens / 1_000_000) * pricing["input_per_1m"]
        output_cost = (output_tokens / 1_000_000) * pricing["output_per_1m"]
        return round(input_cost + output_cost, 8)

    def record_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        endpoint: str = "unknown",
        status: str = "success",
    ) -> float:
        """
        Record an LLM API call and return its computed cost.

        Args:
            model: Model identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            endpoint: API endpoint that triggered the call
            status: "success" or "error"

        Returns:
            Cost in USD
        """
        cost = self.compute_cost(model, input_tokens, output_tokens)

        record = CallRecord(
            timestamp=time.time(),
            model=model,
            endpoint=endpoint,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            status=status,
        )

        with self._lock:
            self._records.append(record)

        logger.info(
            "LLM call: model=%s endpoint=%s tokens=%d/%d cost=$%.6f",
            model,
            endpoint,
            input_tokens,
            output_tokens,
            cost,
        )
        return cost

    def get_today_summary(self) -> DailySummary:
        """Get cost summary for today."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return self._get_summary_since(today_start.timestamp())

    def get_month_summary(self) -> DailySummary:
        """Get cost summary for this month."""
        month_start = datetime.now().replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        return self._get_summary_since(month_start.timestamp())

    def get_total_summary(self) -> DailySummary:
        """Get total cost summary since tracking started."""
        return self._get_summary_since(0)

    def _get_summary_since(self, since_timestamp: float) -> DailySummary:
        """Compute aggregate summary for records after a given timestamp."""
        with self._lock:
            records = [r for r in self._records if r.timestamp >= since_timestamp]

        total_cost = sum(r.cost_usd for r in records)
        total_calls = len(records)
        total_input = sum(r.input_tokens for r in records)
        total_output = sum(r.output_tokens for r in records)

        by_model: dict[str, float] = {}
        by_endpoint: dict[str, float] = {}
        for r in records:
            by_model[r.model] = by_model.get(r.model, 0) + r.cost_usd
            by_endpoint[r.endpoint] = by_endpoint.get(r.endpoint, 0) + r.cost_usd

        return DailySummary(
            date=datetime.now().strftime("%Y-%m-%d"),
            total_cost_usd=round(total_cost, 6),
            total_calls=total_calls,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            by_model=by_model,
            by_endpoint=by_endpoint,
        )

    def to_dict(self, summary: DailySummary | None = None) -> dict:
        """Convert summary to a JSON-serializable dict."""
        if summary is None:
            summary = self.get_today_summary()
        return {
            "date": summary.date,
            "total_cost_usd": summary.total_cost_usd,
            "total_calls": summary.total_calls,
            "total_input_tokens": summary.total_input_tokens,
            "total_output_tokens": summary.total_output_tokens,
            "by_model": summary.by_model,
            "by_endpoint": summary.by_endpoint,
        }

    def get_pending_records(self) -> list[CallRecord]:
        """
        Get all pending (in-memory) records that haven't been persisted yet.

        Returns a copy of the records list. Used by the admin API to
        flush records to the database.
        """
        with self._lock:
            return list(self._records)

    def clear_pending(self) -> None:
        """Clear in-memory records after they've been persisted to DB.

        Only clears records older than 1 minute to avoid losing records
        that were just added but not yet available in a DB query.
        """
        cutoff = time.time() - 60  # 1 minute ago
        with self._lock:
            self._records = [r for r in self._records if r.timestamp > cutoff]

    def get_period_summary_dict(self, period: str = "today") -> dict[str, Any]:
        """
        Get summary as a JSON-serializable dict (from in-memory data).

        Args:
            period: "today", "month", or "total"

        Returns:
            Dict with total_cost_usd, total_calls, total_input_tokens,
            total_output_tokens, by_model, by_endpoint
        """
        if period == "month":
            summary = self.get_month_summary()
        elif period == "total":
            summary = self.get_total_summary()
        else:
            summary = self.get_today_summary()
        return self.to_dict(summary)

    @staticmethod
    def merge_summaries(
        memory_summary: dict[str, Any],
        db_summary: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Merge in-memory and database summaries for a complete picture.

        DB provides historical data (survives restarts).
        In-memory provides recent data (not yet flushed).
        """
        combined = dict(db_summary)
        combined["total_cost_usd"] = round(
            db_summary.get("total_cost_usd", 0)
            + memory_summary.get("total_cost_usd", 0),
            6,
        )
        combined["total_calls"] = db_summary.get("total_calls", 0) + memory_summary.get(
            "total_calls", 0
        )
        combined["total_input_tokens"] = db_summary.get(
            "total_input_tokens", 0
        ) + memory_summary.get("total_input_tokens", 0)
        combined["total_output_tokens"] = db_summary.get(
            "total_output_tokens", 0
        ) + memory_summary.get("total_output_tokens", 0)

        # Merge by_model dicts
        by_model = dict(db_summary.get("by_model", {}))
        for model, cost in memory_summary.get("by_model", {}).items():
            by_model[model] = round(by_model.get(model, 0) + cost, 6)
        combined["by_model"] = by_model

        # Merge by_endpoint dicts
        by_endpoint = dict(db_summary.get("by_endpoint", {}))
        for endpoint, cost in memory_summary.get("by_endpoint", {}).items():
            by_endpoint[endpoint] = round(by_endpoint.get(endpoint, 0) + cost, 6)
        combined["by_endpoint"] = by_endpoint

        return combined


# Singleton

cost_tracker = CostTracker()
