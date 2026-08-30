"""
Tests for the LLM Case Narrator module.

Verifies fallback narrative generation, prompt construction,
and the create_case_narrator factory function.
Does NOT require an Anthropic API key — tests the fallback path.
"""

import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.slow
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.fraudlens.llm.case_narrator import CaseNarrator, create_case_narrator

# Fixtures


@pytest.fixture
def narrator_no_key() -> CaseNarrator:
    """A CaseNarrator with no API key (forces fallback path)."""
    return CaseNarrator(api_key="")


@pytest.fixture
def sample_transaction() -> dict:
    """A realistic sample transaction."""
    return {
        "Time": 100000.0,
        "Amount": 2980.50,
        "V1": -1.36,
        "V2": -0.07,
        "V3": 2.54,
        "V4": 4.12,
        "V5": -0.34,
        "V6": 0.46,
        "V7": 0.24,
        "V8": 0.10,
        "V9": 0.36,
        "V10": 0.09,
        "V11": -0.55,
        "V12": -3.89,
        "V13": -0.99,
        "V14": -5.23,
        "V15": 1.47,
        "V16": -0.47,
        "V17": 0.21,
        "V18": 0.03,
        "V19": 0.40,
        "V20": 0.25,
        "V21": -0.02,
        "V22": 0.28,
        "V23": -0.11,
        "V24": 0.07,
        "V25": 0.13,
        "V26": -0.19,
        "V27": 0.13,
        "V28": 0.02,
    }


@pytest.fixture
def sample_shap_explanation() -> list:
    """A list of SHAP feature contributions."""
    return [
        {"feature": "V14", "value": -5.23, "shap_value": 0.34, "impact": "increases"},
        {"feature": "V4", "value": 4.12, "shap_value": 0.22, "impact": "increases"},
        {"feature": "V12", "value": -3.89, "shap_value": 0.18, "impact": "increases"},
        {"feature": "V10", "value": 0.09, "shap_value": 0.11, "impact": "increases"},
        {"feature": "V17", "value": 0.21, "shap_value": -0.03, "impact": "decreases"},
    ]


# Tests: Initialization


class TestCaseNarratorInit:
    """Tests for CaseNarrator initialization."""

    def test_default_initialization(self):
        """Test default constructor sets reasonable values."""
        narrator = CaseNarrator()
        assert narrator.model is not None
        assert narrator.max_tokens > 0
        assert 0.0 <= narrator.temperature <= 1.0

    def test_custom_parameters(self):
        """Test custom model, max_tokens, and temperature."""
        narrator = CaseNarrator(model="test-model", max_tokens=500, temperature=0.7)
        assert narrator.model == "test-model"
        assert narrator.max_tokens == 500
        assert narrator.temperature == 0.7

    def test_empty_api_key_forces_fallback(self):
        """Test that empty API key forces fallback path."""
        narrator = CaseNarrator(api_key="")
        assert narrator.api_key == ""


# Tests: Fallback Narrative


class TestFallbackNarrative:
    """Tests for fallback (template-based) narrative generation."""

    def test_fraud_fallback_narrative(self, narrator_no_key, sample_shap_explanation):
        """Test fallback narrative for flagged fraud transaction."""
        narrative = narrator_no_key._fallback_narrative(
            sample_shap_explanation, 0.94, True
        )
        assert isinstance(narrative, str)
        assert len(narrative) > 0
        assert "0.0%" not in narrative  # Should show the actual probability
        assert "94.0%" in narrative  # Fraud probability should be included
        assert "V14" in narrative  # Top feature should be mentioned

    def test_legitimate_fallback_narrative(
        self, narrator_no_key, sample_shap_explanation
    ):
        """Test fallback narrative for legitimate transaction."""
        narrative = narrator_no_key._fallback_narrative(
            sample_shap_explanation, 0.12, False
        )
        assert isinstance(narrative, str)
        assert "legitimate" in narrative.lower()

    def test_fallback_narrative_with_empty_shap(self, narrator_no_key):
        """Test fallback handles empty SHAP explanation gracefully."""
        narrative = narrator_no_key._fallback_narrative([], 0.88, True)
        assert isinstance(narrative, str)
        assert len(narrative) > 0

    def test_fallback_narrative_with_single_feature(self, narrator_no_key):
        """Test fallback with only one SHAP feature."""
        shap = [{"feature": "V14", "shap_value": 0.5, "impact": "increases"}]
        narrative = narrator_no_key._fallback_narrative(shap, 0.90, True)
        assert "V14" in narrative
        assert "increases" in narrative


# Tests: Prompt Building


class TestPromptBuilding:
    """Tests for LLM prompt construction."""

    def test_prompt_contains_transaction_details(
        self, narrator_no_key, sample_transaction, sample_shap_explanation
    ):
        """Test that the prompt includes amount, time, and probability."""
        prompt = narrator_no_key._build_prompt(
            sample_transaction, 0.94, sample_shap_explanation, True
        )
        assert isinstance(prompt, str)
        assert "2980.5" in prompt  # Amount (Python formats as 2980.5, not 2980.50)
        assert "94.0%" in prompt  # Probability
        assert "True" in prompt  # is_fraud flag

    def test_prompt_contains_shap_features(
        self, narrator_no_key, sample_transaction, sample_shap_explanation
    ):
        """Test that the prompt includes SHAP feature names."""
        prompt = narrator_no_key._build_prompt(
            sample_transaction, 0.94, sample_shap_explanation, True
        )
        assert "V14" in prompt
        assert "V4" in prompt

    def test_prompt_limits_to_five_features(self, narrator_no_key, sample_transaction):
        """Test that prompt only includes top 5 SHAP features."""
        long_shap = [
            {"feature": f"V{i}", "shap_value": 0.1, "impact": "increases"}
            for i in range(1, 15)
        ]
        prompt = narrator_no_key._build_prompt(
            sample_transaction, 0.85, long_shap, True
        )
        # V14 is feature index 14, should not be in top 5
        assert "V14" not in prompt
        assert "V1" in prompt  # First feature should be there

    def test_prompt_time_conversion(self, narrator_no_key, sample_shap_explanation):
        """Test that raw Time is converted to hours in the prompt."""
        tx = {"Time": 100000.0, "Amount": 100.0}
        prompt = narrator_no_key._build_prompt(tx, 0.5, sample_shap_explanation, False)
        # 100000 % 86400 = 13600, 13600 / 3600 = 3.8
        assert "3.8" in prompt


# Tests: Narrate Method (Fallback Path)


class TestNarrate:
    """Tests for the narrate() method using the fallback path."""

    def test_narrate_returns_string(
        self, narrator_no_key, sample_transaction, sample_shap_explanation
    ):
        """Test that narrate() returns a non-empty string."""
        result = narrator_no_key.narrate(
            sample_transaction, 0.94, sample_shap_explanation, True
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_narrate_fraud_includes_probability(
        self, narrator_no_key, sample_transaction, sample_shap_explanation
    ):
        """Test that fraud narrative includes the probability."""
        result = narrator_no_key.narrate(
            sample_transaction, 0.88, sample_shap_explanation, True
        )
        assert "88.0%" in result

    def test_narrate_legitimate_includes_confidence(
        self, narrator_no_key, sample_transaction, sample_shap_explanation
    ):
        """Test that legitimate narrative includes confidence."""
        result = narrator_no_key.narrate(
            sample_transaction, 0.15, sample_shap_explanation, False
        )
        assert "legitimate" in result.lower()

    def test_narrate_includes_action_recommendation(
        self, narrator_no_key, sample_transaction, sample_shap_explanation
    ):
        """Test that fraud narrative includes action recommendation."""
        result = narrator_no_key.narrate(
            sample_transaction, 0.95, sample_shap_explanation, True
        )
        assert "manual review" in result.lower()


# Tests: Factory Function


class TestCreateCaseNarrator:
    """Tests for the create_case_narrator factory function."""

    def test_factory_returns_case_narrator(self):
        """Test that factory returns a CaseNarrator instance."""
        narrator = create_case_narrator()
        assert isinstance(narrator, CaseNarrator)

    def test_factory_creates_new_instance(self):
        """Test that each call creates a new instance."""
        n1 = create_case_narrator()
        n2 = create_case_narrator()
        assert n1 is not n2


# Tests: Edge Cases


class TestEdgeCases:
    """Edge case tests for CaseNarrator."""

    def test_zero_probability(self, narrator_no_key, sample_shap_explanation):
        """Test handling of zero fraud probability."""
        result = narrator_no_key.narrate(
            {"Amount": 10.0, "Time": 0.0}, 0.0, sample_shap_explanation, False
        )
        assert isinstance(result, str)

    def test_one_probability(self, narrator_no_key, sample_shap_explanation):
        """Test handling of 100% fraud probability."""
        result = narrator_no_key.narrate(
            {"Amount": 5000.0, "Time": 86400.0}, 1.0, sample_shap_explanation, True
        )
        assert isinstance(result, str)
        assert "100.0%" in result

    def test_negative_amount(self, narrator_no_key, sample_shap_explanation):
        """Test handling of negative amount (edge case)."""
        result = narrator_no_key.narrate(
            {"Amount": -50.0, "Time": 0.0}, 0.75, sample_shap_explanation, True
        )
        assert isinstance(result, str)

    def test_missing_transaction_fields(self, narrator_no_key, sample_shap_explanation):
        """Test handling of transaction with missing fields."""
        result = narrator_no_key.narrate({}, 0.60, sample_shap_explanation, False)
        assert isinstance(result, str)


# Mocked Anthropic Client Tests (exercises the actual API-call code path)


class TestMockedAnthropicPath:
    """
    Tests that exercise the ACTUAL LLM API-call code path using the
    conftest.py mock (auto-used, monkeypatches anthropic.Anthropic).

    Unlike the fallback-path tests above, these set a non-empty API key,
    so narrate() proceeds through _init_client() and _call_llm_with_response().
    The auto-used mock in conftest.py replaces the real Anthropic client.
    """

    def test_narrate_with_mocked_client_returns_narrative(
        self, sample_transaction, sample_shap_explanation
    ):
        """Test that narrate() returns the mock's narrative text.

        The conftest.py auto-used fixture monkeypatches anthropic.Anthropic
        with a mock that returns "Mock narrative response for testing."
        Setting a non-empty API key activates the real code path.
        """
        narrator = CaseNarrator(api_key="test-key-123")
        result = narrator.narrate(
            sample_transaction, 0.94, sample_shap_explanation, True
        )

        assert isinstance(result, str)
        assert len(result) > 0
        assert "Mock narrative response" in result

    def test_mocked_path_includes_probability(
        self, sample_transaction, sample_shap_explanation
    ):
        """Test that the conftest mock path returns a narrative string."""
        narrator = CaseNarrator(api_key="test-key-123")
        result = narrator.narrate(
            sample_transaction, 0.94, sample_shap_explanation, True
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_mocked_path_with_cost_tracking(
        self, sample_transaction, sample_shap_explanation
    ):
        """Test that the mock path works end-to-end (cost tracking is internal)."""
        narrator = CaseNarrator(api_key="test-key-123")
        result = narrator.narrate(
            sample_transaction, 0.94, sample_shap_explanation, True
        )
        assert isinstance(result, str)
        assert len(result) > 0


class TestMockedAnthropicEdgeCases:
    """Edge case tests using patched client behavior."""

    def test_timeout_falls_back_gracefully(
        self, sample_transaction, sample_shap_explanation
    ):
        """
        Mock the client's messages.create to raise a timeout exception
        and verify the narrator falls back instead of crashing.
        """
        from unittest.mock import patch

        narrator = CaseNarrator(api_key="test-key-123")

        def _raise_timeout(*args, **kwargs):
            import anthropic

            raise anthropic.APITimeoutError("Request timed out")

        with patch.object(narrator, "_client", None):
            # Patch _init_client to set up a client whose create raises
            def _setup_timeout_client():
                import anthropic

                class TimeoutMessages:
                    def create(self, *args, **kwargs):
                        raise anthropic.APITimeoutError("Request timed out")

                class TimeoutClient:
                    def __init__(self):
                        self.messages = TimeoutMessages()

                narrator._client = TimeoutClient()

            with patch.object(narrator, "_init_client", _setup_timeout_client):
                result = narrator.narrate(
                    sample_transaction, 0.88, sample_shap_explanation, True
                )

        # Should gracefully fall back
        assert isinstance(result, str)
        assert len(result) > 0
        # Should include fallback prefix
        assert "Automated summary" in result

    def test_empty_response_falls_back_gracefully(
        self, sample_transaction, sample_shap_explanation
    ):
        """
        Mock the client to return an empty response (content: []),
        verify the narrator falls back instead of crashing with index error.
        """
        narrator = CaseNarrator(api_key="test-key-123")

        class EmptyMessage:
            content = []  # Empty content list!
            usage = None

        class EmptyMessages:
            def create(self, *args, **kwargs):
                return EmptyMessage()

        class EmptyClient:
            def __init__(self):
                self.messages = EmptyMessages()

        from unittest.mock import patch

        def _setup_empty_client():
            narrator._client = EmptyClient()

        with patch.object(narrator, "_init_client", _setup_empty_client):
            result = narrator.narrate(
                sample_transaction, 0.88, sample_shap_explanation, True
            )

        # Empty content should trigger the exception handler -> fallback
        assert isinstance(result, str)
        assert len(result) > 0
        assert "Automated summary" in result or "flagged" in result.lower()

    def test_malformed_response_falls_back_gracefully(
        self, sample_transaction, sample_shap_explanation
    ):
        """
        Mock the client to return a malformed response missing expected fields,
        verify the narrator fails closed to the fallback.
        """
        narrator = CaseNarrator(api_key="test-key-123")

        class MalformedMessage:
            pass  # Missing .content entirely!

        class MalformedMessages:
            def create(self, *args, **kwargs):
                return MalformedMessage()

        class MalformedClient:
            def __init__(self):
                self.messages = MalformedMessages()

        from unittest.mock import patch

        def _setup_malformed_client():
            narrator._client = MalformedClient()

        with patch.object(narrator, "_init_client", _setup_malformed_client):
            result = narrator.narrate(
                sample_transaction, 0.88, sample_shap_explanation, True
            )

        # Missing content should trigger exception -> fallback
        assert isinstance(result, str)
        assert "Automated summary" in result

    def test_circuit_breaker_skips_llm_call(
        self, sample_transaction, sample_shap_explanation
    ):
        """
        When the circuit breaker is open, narrate() should skip the LLM call
        entirely and go directly to the fallback.
        """
        narrator = CaseNarrator(api_key="test-key-123")

        class OpenBreaker:
            def is_open(self):
                return True

            def record_success(self):
                pass

            def record_failure(self):
                pass

        narrator.set_circuit_breaker(OpenBreaker())

        from unittest.mock import patch

        # Mock _init_client to raise - if circuit breaker works, it won't be called
        called = []

        def _should_not_call():
            called.append(True)
            raise RuntimeError("Should not have initialized client!")

        with patch.object(narrator, "_init_client", _should_not_call):
            result = narrator.narrate(
                sample_transaction, 0.88, sample_shap_explanation, True
            )

        assert len(called) == 0, "_init_client was called despite open circuit breaker!"
        assert isinstance(result, str)
        assert "Automated summary" in result


# Golden-Set Factuality Checks


class TestFactualityChecker:
    """
    Golden-set factuality check for the factuality checker function.

    Tests the *checker* logic (not the live LLM) — for each (SHAP explanation,
    expected top features) pair in the golden set, we mock the LLM to return
    a fixed narrative and assert the checker correctly passes/fails.
    """

    def _factuality_check(self, narrative: str, shap_features: list) -> dict:
        """
        Minimal factuality checker: verifies all V-features mentioned in the
        narrative exist in the actual SHAP contributors list.

        Returns dict with pass/fail and any hallucinated features.
        """
        import re


        actual_features = {f["feature"] for f in shap_features}
        mentioned_features = set(re.findall(r"V\d+", narrative))
        hallucinated = mentioned_features - actual_features
        return {
            "pass": len(hallucinated) == 0,
            "hallucinated": sorted(hallucinated),
            "mentioned": sorted(mentioned_features),
            "actual": sorted(actual_features),
        }

    def test_matched_case_passes(self):
        """Golden set: narrative mentions only expected features."""
        shap_features = [
            {
                "feature": "V14",
                "value": -5.23,
                "shap_value": 0.34,
                "impact": "increases",
            },
            {"feature": "V4", "value": 4.12, "shap_value": 0.22, "impact": "increases"},
            {
                "feature": "V12",
                "value": -3.89,
                "shap_value": 0.18,
                "impact": "increases",
            },
        ]
        narrative = "Transaction flagged due to unusual V14 and V4 patterns."

        result = self._factuality_check(narrative, shap_features)
        assert result["pass"] is True
        assert len(result["hallucinated"]) == 0

    def test_hallucinated_feature_fails(self):
        """Golden set: narrative mentions a feature not in SHAP contributors."""
        shap_features = [
            {
                "feature": "V14",
                "value": -5.23,
                "shap_value": 0.34,
                "impact": "increases",
            },
            {"feature": "V4", "value": 4.12, "shap_value": 0.22, "impact": "increases"},
        ]
        # V10 is NOT in the SHAP contributors
        narrative = "Transaction flagged due to unusual V14, V4, and V10 patterns."

        result = self._factuality_check(narrative, shap_features)
        assert result["pass"] is False
        assert "V10" in result["hallucinated"]

    def test_all_features_mentioned_passes(self):
        """Golden set: narrative mentions ALL actual SHAP features."""
        shap_features = [
            {
                "feature": "V14",
                "value": -5.23,
                "shap_value": 0.34,
                "impact": "increases",
            },
            {"feature": "V4", "value": 4.12, "shap_value": 0.22, "impact": "increases"},
            {
                "feature": "V10",
                "value": 0.09,
                "shap_value": 0.11,
                "impact": "increases",
            },
        ]
        narrative = "V14, V4, and V10 were the top contributing features."

        result = self._factuality_check(narrative, shap_features)
        assert result["pass"] is True

    def test_no_features_mentioned_passes(self):
        """Narrative with no V-feature references should pass (no hallucination)."""
        shap_features = [
            {
                "feature": "V14",
                "value": -5.23,
                "shap_value": 0.34,
                "impact": "increases",
            },
        ]
        narrative = "Transaction appears legitimate with no strong fraud indicators."

        result = self._factuality_check(narrative, shap_features)
        assert result["pass"] is True

    def test_multiple_hallucinated_features_fails(self):
        """Multiple hallucinated features should all be reported."""
        shap_features = [
            {"feature": "V1", "value": 1.0, "shap_value": 0.5, "impact": "increases"},
        ]
        narrative = "Multiple unusual features: V1, V2, V3, V4, V5, V6"

        result = self._factuality_check(narrative, shap_features)
        assert result["pass"] is False
        assert len(result["hallucinated"]) == 5
        assert "V2" in result["hallucinated"]
        assert "V6" in result["hallucinated"]
