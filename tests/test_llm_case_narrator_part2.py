"""Tests for the LLM Case Narrator module.

Verifies fallback narrative generation, prompt construction,
and the create_case_narrator factory function.
Does NOT require an Anthropic API key — tests the fallback path. — Part 2."""

from src.fraudlens.llm.case_narrator import CaseNarrator


class TestMockedAnthropicEdgeCases:
    """Edge case tests using patched client behavior."""

    def test_timeout_falls_back_gracefully(
        self, sample_transaction, sample_shap_explanation
    ) -> None:
        """
        Mock the client's messages.create to raise a timeout exception
        and verify the narrator falls back instead of crashing.
        """
        from unittest.mock import patch

        narrator = CaseNarrator(api_key="test-key-123")

        def _raise_timeout(*args, **kwargs) -> None:
            import anthropic

            raise anthropic.APITimeoutError("Request timed out")

        with patch.object(narrator, "_client", None):
            # Patch _init_client to set up a client whose create raises
            def _setup_timeout_client() -> None:
                import anthropic

                class TimeoutMessages:
                    def create(self, *args, **kwargs) -> None:
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
    ) -> None:
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

        def _setup_empty_client() -> None:
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
    ) -> None:
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

        def _setup_malformed_client() -> None:
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
    ) -> bool:
        """
        When the circuit breaker is open, narrate() should skip the LLM call
        entirely and go directly to the fallback.
        """
        narrator = CaseNarrator(api_key="test-key-123")

        class OpenBreaker:
            def is_open(self) -> bool:
                return True

            def record_success(self) -> None:
                pass

            def record_failure(self) -> None:
                pass

        narrator.set_circuit_breaker(OpenBreaker())

        from unittest.mock import patch

        # Mock _init_client to raise - if circuit breaker works, it won't be called
        called = []

        def _should_not_call() -> None:
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

    def test_matched_case_passes(self) -> None:
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

    def test_hallucinated_feature_fails(self) -> None:
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

    def test_all_features_mentioned_passes(self) -> None:
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

    def test_no_features_mentioned_passes(self) -> None:
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

    def test_multiple_hallucinated_features_fails(self) -> None:
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
