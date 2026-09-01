"""
Drift Detection Module

Monitors incoming transaction distributions against training data
to detect concept drift and data drift that may degrade model performance.
Surfaced as alert banners in the Live Monitor dashboard.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

from src.fraudlens.config import DRIFT_THRESHOLD

logger = logging.getLogger(__name__)


class DriftDetector:
    """
    Detect data drift between training data and incoming transactions.

    Uses Kolmogorov-Smirnov test for continuous features.
    Drift is surfaced directly in the UI as alert banners.

    Alert Levels:
    - OK: p-value > significance_level (no significant drift)
    - WARNING: p-value <= significance_level (mild drift)
    - CRITICAL: p-value <= 0.01 (significant drift, retrain model)
    """

    def __init__(
        self,
        reference_data: pd.DataFrame,
        feature_names: list[str] | None = None,
        significance_level: float = DRIFT_THRESHOLD,
    ) -> None:
        """
        Args:
            reference_data: Training data to use as reference distribution
            feature_names: List of feature names to monitor
            significance_level: p-value threshold for drift detection
        """
        self.reference_data = reference_data
        self.feature_names = feature_names or list(reference_data.columns)
        self.significance_level = significance_level
        self.drift_history: list[dict] = []
        self._compute_reference_stats()

    def _compute_reference_stats(self) -> None:
        """Pre-compute reference distribution statistics."""
        self.ref_stats: dict[str, dict] = {}
        for col in self.feature_names:
            if col in self.reference_data.columns:
                s = self.reference_data[col]
                self.ref_stats[col] = {
                    "mean": float(s.mean()),
                    "std": float(s.std()),
                    "min": float(s.min()),
                    "max": float(s.max()),
                    "median": float(s.median()),
                }

    def detect_drift(self, new_data: pd.DataFrame) -> dict[str, dict]:
        """
        Run drift detection on new data.

        Args:
            new_data: New transaction data to compare against reference

        Returns:
            Dictionary with drift results per feature
        """
        results: dict[str, dict] = {}

        for col in self.feature_names:
            if col not in new_data.columns or col not in self.reference_data.columns:
                continue

            ref_values = self.reference_data[col].dropna().values
            new_values = new_data[col].dropna().values

            if len(new_values) == 0 or len(ref_values) == 0:
                continue

            ks_stat, p_value = stats.ks_2samp(ref_values, new_values)

            if p_value <= 0.01:
                alert = "CRITICAL"
            elif p_value <= self.significance_level:
                alert = "WARNING"
            else:
                alert = "OK"

            ref_mean = float(np.mean(ref_values))
            new_mean = float(np.mean(new_values))
            mean_shift_pct = abs(new_mean - ref_mean) / (abs(ref_mean) + 1e-10) * 100

            results[col] = {
                "ks_statistic": round(float(ks_stat), 4),
                "p_value": round(float(p_value), 6),
                "alert": alert,
                "ref_mean": round(ref_mean, 4),
                "new_mean": round(new_mean, 4),
                "mean_shift_pct": round(mean_shift_pct, 2),
            }

        critical = [f for f, r in results.items() if r["alert"] == "CRITICAL"]
        warnings = [f for f, r in results.items() if r["alert"] == "WARNING"]

        if critical:
            logger.warning("CRITICAL drift detected in: %s", critical)
        if warnings:
            logger.info("WARNING drift detected in: %s", warnings)

        self.drift_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "n_samples": len(new_data),
                "n_critical": len(critical),
                "n_warnings": len(warnings),
                "results": results,
            }
        )

        return results

    def get_overall_drift_score(self, results: dict[str, dict]) -> float:
        """Compute an overall drift score (0 = no drift, 1 = severe drift)."""
        if not results:
            return 0.0

        n_critical = sum(1 for r in results.values() if r["alert"] == "CRITICAL")
        n_warning = sum(1 for r in results.values() if r["alert"] == "WARNING")
        n_total = len(results)

        score = (n_critical * 2 + n_warning) / (n_total * 2)
        return round(min(score, 1.0), 4)

    def generate_report(self, results: dict[str, dict]) -> str:
        """Generate a human-readable drift report."""
        overall_score = self.get_overall_drift_score(results)

        lines = [
            "=" * 60,
            "  DATA DRIFT REPORT",
            "=" * 60,
            f"  Timestamp:       {datetime.now().isoformat()}",
            f"  Reference size:  {len(self.reference_data)}",
            f"  Overall Score:   {overall_score:.2f} (0=no drift, 1=severe)",
            f"  Status:          {'CRITICAL' if overall_score > 0.3 else 'WARNING' if overall_score > 0.1 else 'OK'}",
        ]

        critical = {f: r for f, r in results.items() if r["alert"] == "CRITICAL"}
        warnings = {f: r for f, r in results.items() if r["alert"] == "WARNING"}

        if critical:
            lines.append("\nCRITICAL DRIFT:")
            for feat, r in critical.items():
                lines.append(
                    f"  {feat}: KS={r['ks_statistic']:.4f}, "
                    f"p={r['p_value']:.6f}, shift={r['mean_shift_pct']:.1f}%"
                )

        if warnings:
            lines.append("\nWARNINGS:")
            for feat, r in warnings.items():
                lines.append(
                    f"  {feat}: KS={r['ks_statistic']:.4f}, "
                    f"p={r['p_value']:.6f}, shift={r['mean_shift_pct']:.1f}%"
                )

        ok_count = sum(1 for r in results.values() if r["alert"] == "OK")
        lines.append(f"\nOK: {ok_count}/{len(results)} features stable")

        if overall_score > 0.3:
            lines.append("\nRECOMMENDATION: Model retraining may be needed!")
        elif overall_score > 0.1:
            lines.append("\nRECOMMENDATION: Monitor closely, drift is emerging.")
        else:
            lines.append("\nRECOMMENDATION: No action needed.")

        return "\n".join(lines)

    def save_report(
        self, results: dict[str, dict], path: str = "reports/drift_report.json"
    ) -> None:
        """Save drift report to JSON file."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "overall_score": self.get_overall_drift_score(results),
            "n_features_tested": len(results),
            "results": results,
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(report, f, indent=2, default=str)
        logger.info("Drift report saved to %s", path)


def simulate_drift(
    reference: pd.DataFrame, drift_magnitude: float = 0.5
) -> pd.DataFrame -> None:
    """
    Simulate data drift by shifting distributions.

    Args:
        reference: Reference (training) data
        drift_magnitude: How much to shift (0 = no drift, 1 = huge)

    Returns:
        Simulated drifted data
    """
    drifted = reference.copy()
    shift_features = ["V1", "V4", "V14", "Amount"]
    for col in shift_features:
        if col in drifted.columns:
            mean_shift = drifted[col].std() * drift_magnitude
            drifted[col] = drifted[col] + mean_shift * np.random.choice([-1, 1])
    return drifted
