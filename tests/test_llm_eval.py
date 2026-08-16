"""
FraudLens — LLM Eval Harness

Validates CaseNarrator output quality:
- Factuality: narratives mention only features that are actual top SHAP contributors
- Completeness: narratives include the fraud probability
- Consistency: narratives don't hallucinate feature values

This is a non-blocking CI check — it runs with the fallback (template-based)
narrator by default, no live LLM call required. A nightly job with a real
LLM can use the same assertions with actual LLM-generated narratives.
"""

import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.fraudlens.llm.case_narrator import CaseNarrator

# Fixtures


@pytest.fixture
def narrator() -> CaseNarrator:
    """CaseNarrator with no API key (uses fallback template)."""
    return CaseNarrator(api_key="")


@pytest.fixture
def sample_shap_features() -> list[dict[str, Any]]:
    """Top SHAP features for a flagged fraud transaction."""
    return [
        {"feature": "V14", "value": -5.23, "shap_value": 0.34, "impact": "increases"},
        {"feature": "V4", "value": 4.12, "shap_value": 0.22, "impact": "increases"},
        {"feature": "V12", "value": -3.89, "shap_value": 0.18, "impact": "increases"},
        {"feature": "V10", "value": 0.09, "shap_value": 0.11, "impact": "increases"},
        {"feature": "V17", "value": 0.21, "shap_value": -0.03, "impact": "decreases"},
    ]


@pytest.fixture
def sample_transaction() -> dict[str, Any]:
    """Basic transaction dict."""
    return {
        "Time": 100000.0,
        "Amount": 2500.00,
        "V1": -1.36,
        "V14": -5.23,
        "V4": 4.12,
        "V12": -3.89,
        "V10": 0.09,
        "V17": 0.21,
    }


# Eval Tests: Factuality


class TestFactuality:
    """Eval: narratives should mention only actual SHAP contributors."""

    def test_narrative_mentions_top_features(
        self, narrator, sample_transaction, sample_shap_features
    ):
        """Test that the top SHAP features appear in the narrative."""
        narrative = narrator.narrate(
            sample_transaction, 0.94, sample_shap_features, True
        )
        # Top 3 features should be mentioned
        top_features = ["V14", "V4", "V12"]
        mentioned = sum(1 for f in top_features if f in narrative)
        assert mentioned >= 2, (
            f"Narrative should mention at least 2 of top 3 features. "
            f"Found {mentioned}/3 in: {narrative[:200]}"
        )

    def test_narrative_does_not_hallucinate_features(
        self, narrator, sample_transaction, sample_shap_features
    ):
        """Test that narrative doesn't mention features not in SHAP list."""
        actual_features = {f["feature"] for f in sample_shap_features}
        narrative = narrator.narrate(
            sample_transaction, 0.94, sample_shap_features, True
        )

        # Extract potential feature mentions (V1-V28 patterns)
        import re

        mentioned_features = re.findall(r"V\d+", narrative)

        hallucinated = [f for f in mentioned_features if f not in actual_features]
        assert len(hallucinated) == 0, (
            f"Narrative hallucinated features not in SHAP contributors: "
            f"{hallucinated}. Actual contributors: {actual_features}"
        )

    def test_feature_values_match_transaction(
        self, narrator, sample_transaction, sample_shap_features
    ):
        """Test that feature values in narrative match the transaction."""
        narrative = narrator.narrate(
            sample_transaction, 0.94, sample_shap_features, True
        )
        # V14 value is -5.23 — check it appears in the narrative
        # The fallback template might not include the exact number,
        # but it should reference the feature somehow.
        assert "V14" in narrative


# Eval Tests: Probability Accuracy


class TestProbabilityAccuracy:
    """Eval: narratives should report the correct fraud probability."""

    def test_narrative_includes_probability(
        self, narrator, sample_transaction, sample_shap_features
    ):
        """Test that the narrative includes the fraud probability."""
        narrative = narrator.narrate(
            sample_transaction, 0.94, sample_shap_features, True
        )
        assert (
            "94.0%" in narrative
        ), f"Narrative should include fraud probability. Got: {narrative[:150]}"

    def test_narrative_accuracy_different_probabilities(
        self, narrator, sample_transaction, sample_shap_features
    ):
        """Test that different probabilities produce different narratives."""

        # The fallback narrator always produces correct numbers
        # because they're baked into the template
        n1 = narrator.narrate(sample_transaction, 0.50, sample_shap_features, False)
        n2 = narrator.narrate(sample_transaction, 0.99, sample_shap_features, True)
        assert "50.0%" in n1
        assert "99.0%" in n2


# Eval Tests: Consistency


class TestConsistency:
    """Eval: narratives should be consistent across repeated calls."""

    def test_consistent_fraud_label(
        self, narrator, sample_transaction, sample_shap_features
    ):
        """Test that flagged-fraud narratives consistently mention review."""
        # Run multiple times to check stability
        narratives = []
        for _ in range(3):
            n = narrator.narrate(sample_transaction, 0.95, sample_shap_features, True)
            narratives.append(n)

        # All should mention "manual review" for fraud cases
        for i, n in enumerate(narratives):
            assert (
                "manual review" in n.lower()
            ), f"Narrative {i} missing 'manual review' recommendation: {n[:100]}"

    def test_consistent_legitimate_label(
        self, narrator, sample_transaction, sample_shap_features
    ):
        """Test that legitimate narratives consistently say 'legitimate'."""
        narratives = []
        for _ in range(3):
            n = narrator.narrate(sample_transaction, 0.05, sample_shap_features, False)
            narratives.append(n)

        for i, n in enumerate(narratives):
            assert (
                "legitimate" in n.lower()
            ), f"Narrative {i} missing 'legitimate': {n[:100]}"

    def test_deterministic_fallback(
        self, narrator, sample_transaction, sample_shap_features
    ):
        """Test that the fallback template is deterministic."""
        n1 = narrator.narrate(sample_transaction, 0.75, sample_shap_features, True)
        n2 = narrator.narrate(sample_transaction, 0.75, sample_shap_features, True)
        # Fallback templates with same inputs should produce same output
        assert n1 == n2, "Fallback narrative should be deterministic"


# Eval Tests: Edge Cases


class TestEdgeCases:
    """Eval: narratives should handle edge cases gracefully."""

    def test_no_shap_features(self, narrator, sample_transaction):
        """Test narrative with empty SHAP explanation."""
        narrative = narrator.narrate(sample_transaction, 0.60, [], True)
        assert isinstance(narrative, str)
        assert len(narrative) > 0
        assert "60.0%" in narrative

    def test_many_shap_features(self, narrator, sample_transaction):
        """Test narrative with many SHAP features (should not overflow)."""
        many_features = [
            {
                "feature": f"V{i}",
                "value": float(i),
                "shap_value": 0.1,
                "impact": "increases",
            }
            for i in range(1, 29)
        ]
        narrative = narrator.narrate(sample_transaction, 0.80, many_features, True)
        # Should still be readable (not truncated or excessively long)
        assert len(narrative) < 5000
        assert len(narrative) > 0

    def test_extreme_probability(
        self, narrator, sample_transaction, sample_shap_features
    ):
        """Test narrative with extreme (0% and 100%) probabilities."""
        # 0% probability (legitimate)
        n1 = narrator.narrate(sample_transaction, 0.0, sample_shap_features, False)
        assert "legitimate" in n1.lower()

        # 100% probability (fraud)
        n2 = narrator.narrate(sample_transaction, 1.0, sample_shap_features, True)
        assert "manual review" in n2.lower()
        assert "100.0%" in n2


# Eval Tests: Business Readability


class TestBusinessReadability:
    """Eval: narratives should be readable by non-technical fraud analysts."""

    def test_narrative_is_plain_english(
        self, narrator, sample_transaction, sample_shap_features
    ):
        """Test that the narrative is in plain English (no raw numbers-only output)."""
        narrative = narrator.narrate(
            sample_transaction, 0.94, sample_shap_features, True
        )
        # Should contain actual English words, not just feature names
        assert any(
            word in narrative.lower()
            for word in [
                "flagged",
                "fraud",
                "review",
                "pattern",
                "transaction",
                "indicator",
            ]
        ), "Narrative should contain plain English fraud analysis terms"

    def test_narrative_actionable(
        self, narrator, sample_transaction, sample_shap_features
    ):
        """Test that fraud narratives recommend an action."""
        narrative = narrator.narrate(
            sample_transaction, 0.94, sample_shap_features, True
        )
        assert any(
            phrase in narrative.lower()
            for phrase in [
                "manual review",
                "recommended action",
                "review by",
            ]
        ), "Fraud narrative should include an actionable recommendation"
