"""
Tests for the RAG Similar-Case Retrieval module.

Verifies index build/save/load round-trips correctly,
retrieve top-k returns correct count and sane similarity ordering.
"""

import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.fraudlens.llm.rag_similar_cases import SimilarCaseRetriever, create_retriever

# Fixtures


@pytest.fixture
def sample_historical_data() -> pd.DataFrame:
    """Small synthetic historical dataset for testing."""
    np.random.seed(42)
    n = 50
    data = {f"V{i}": np.random.randn(n) for i in range(1, 29)}
    data["Time"] = np.random.uniform(0, 172800, n)
    data["Amount"] = np.random.exponential(100, n)
    data["Class"] = np.random.choice([0, 1], n, p=[0.8, 0.2])
    return pd.DataFrame(data)


@pytest.fixture
def query_transaction() -> dict:
    """A query transaction similar to some fraud cases."""
    return {
        "V1": -0.5,
        "V2": 0.3,
        "V3": 1.2,
        "V4": -2.1,
        "V5": 0.7,
        "V6": -0.3,
        "V7": 0.1,
        "V8": -0.8,
        "V9": 0.4,
        "V10": -1.5,
        "V11": 0.6,
        "V12": -2.0,
        "V13": -0.2,
        "V14": -4.0,
        "V15": 0.8,
        "V16": -0.5,
        "V17": 0.3,
        "V18": -0.1,
        "V19": 0.2,
        "V20": -0.4,
        "V21": 0.1,
        "V22": -0.2,
        "V23": 0.0,
        "V24": -0.1,
        "V25": 0.3,
        "V26": -0.2,
        "V27": 0.1,
        "V28": -0.3,
        "Time": 100000.0,
        "Amount": 200.0,
    }


# Tests: Build Index


class TestBuildIndex:
    """Tests for building the FAISS index."""

    def test_build_index_success(self, sample_historical_data) -> None:
        """Test that building an index succeeds."""
        retriever = SimilarCaseRetriever()
        retriever.build_index(sample_historical_data)
        assert retriever._initialized
        assert retriever.index is not None
        assert retriever.historical_cases is not None

    def test_build_index_initialized_flag(self, sample_historical_data) -> None:
        """Test that _initialized is True after build."""
        retriever = SimilarCaseRetriever()
        assert not retriever._initialized
        retriever.build_index(sample_historical_data)
        assert retriever._initialized

    def test_build_index_stores_outcomes(self, sample_historical_data) -> None:
        """Test that historical_cases DataFrame stores outcomes."""
        retriever = SimilarCaseRetriever()
        retriever.build_index(sample_historical_data)
        assert "actual_outcome" in retriever.historical_cases.columns
        assert "is_fraud" in retriever.historical_cases.columns


# Tests: Retrieve


class TestRetrieve:
    """Tests for retrieving similar cases."""

    def test_retrieve_returns_correct_count(
        self, sample_historical_data, query_transaction
    ) -> None:
        """Test that retrieve returns top_k results."""
        retriever = SimilarCaseRetriever(top_k=3)
        retriever.build_index(sample_historical_data)
        results = retriever.retrieve(query_transaction, top_k=3)
        assert len(results) == 3

    def test_retrieve_less_than_total(self, sample_historical_data, query_transaction) -> None:
        """Test retrieving fewer results than total cases."""
        retriever = SimilarCaseRetriever()
        retriever.build_index(sample_historical_data)
        results = retriever.retrieve(query_transaction, top_k=2)
        assert len(results) == 2

    def test_retrieve_results_have_expected_keys(
        self, sample_historical_data, query_transaction
    ) -> None:
        """Test that each result has the expected fields."""
        retriever = SimilarCaseRetriever(top_k=3)
        retriever.build_index(sample_historical_data)
        results = retriever.retrieve(query_transaction, top_k=1)
        result = results[0]
        assert "similarity_score" in result
        assert "actual_outcome" in result
        assert "features" in result
        assert result["actual_outcome"] in ("confirmed_fraud", "false_positive")

    def test_retrieve_scores_are_reasonable(
        self, sample_historical_data, query_transaction
    ) -> None:
        """Test that similarity scores are between -1 and 1 (cosine/IP)."""
        retriever = SimilarCaseRetriever(top_k=3)
        retriever.build_index(sample_historical_data)
        results = retriever.retrieve(query_transaction, top_k=3)
        for r in results:
            assert -1.0 <= r["similarity_score"] <= 1.0

    def test_retrieve_raises_without_index(self, query_transaction) -> None:
        """Test that retrieve raises RuntimeError before index is built."""
        retriever = SimilarCaseRetriever()
        with pytest.raises(RuntimeError):
            retriever.retrieve(query_transaction)


# Tests: Save / Load


class TestSaveLoad:
    """Tests for saving and loading the FAISS index."""

    def test_save_load_round_trip(self, sample_historical_data, query_transaction) -> None:
        """Test that save/load round-trip preserves retrieval behavior."""
        # Build and save
        retriever1 = SimilarCaseRetriever(top_k=3)
        retriever1.build_index(sample_historical_data)
        results_before = retriever1.retrieve(query_transaction, top_k=1)
        score_before = results_before[0]["similarity_score"]

        # Save to temp dir
        with tempfile.TemporaryDirectory() as tmpdir:
            save_path = retriever1.save(tmpdir)

            # Load into new retriever
            retriever2 = SimilarCaseRetriever(top_k=3)
            retriever2.load(save_path)
            results_after = retriever2.retrieve(query_transaction, top_k=1)
            score_after = results_after[0]["similarity_score"]

        # Scores should match
        assert abs(score_before - score_after) < 0.001

    def test_save_creates_files(self, sample_historical_data) -> None:
        """Test that save creates index file and CSV."""
        retriever = SimilarCaseRetriever(top_k=3)
        retriever.build_index(sample_historical_data)
        with tempfile.TemporaryDirectory() as tmpdir:
            retriever.save(tmpdir)
            assert (Path(tmpdir) / "index.faiss").exists()
            assert (Path(tmpdir) / "historical_cases.csv").exists()

    def test_save_raises_without_index(self) -> None:
        """Test that save raises RuntimeError before index is built."""
        retriever = SimilarCaseRetriever()
        with pytest.raises(RuntimeError):
            retriever.save("/tmp/does_not_matter")

    def test_load_initializes_flag(self, sample_historical_data) -> None:
        """Test that load sets _initialized=True."""
        retriever = SimilarCaseRetriever(top_k=3)
        retriever.build_index(sample_historical_data)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = retriever.save(tmpdir)
            retriever2 = SimilarCaseRetriever()
            retriever2.load(path)
            assert retriever2._initialized


# Tests: Factory Function


class TestFactory:
    """Tests for create_retriever factory function."""

    def test_create_without_data(self) -> None:
        """Test creating retriever without historical data."""
        retriever = create_retriever()
        assert isinstance(retriever, SimilarCaseRetriever)
        assert not retriever._initialized

    def test_create_with_data(self, sample_historical_data) -> None:
        """Test creating retriever with historical data."""
        retriever = create_retriever(sample_historical_data)
        assert isinstance(retriever, SimilarCaseRetriever)
        assert retriever._initialized


# Tests: Edge Cases


class TestEdgeCases:
    """Edge cases for SimilarCaseRetriever."""

    def test_retrieve_more_than_available(
        self, sample_historical_data, query_transaction
    ) -> None:
        """Test retrieving more than available cases returns all."""
        small_data = sample_historical_data.head(2)
        retriever = SimilarCaseRetriever(top_k=10)
        retriever.build_index(small_data)
        results = retriever.retrieve(query_transaction, top_k=10)
        assert len(results) == 2  # Only 2 available

    def test_retrieve_with_missing_features(self, query_transaction) -> None:
        """Test retrieving with missing feature columns."""
        minimal_data = pd.DataFrame(
            {
                "V1": [0.0, 1.0],
                "V14": [-1.0, -5.0],
                "Time": [0.0, 100.0],
                "Amount": [50.0, 200.0],
                "Class": [0, 1],
            }
        )
        retriever = SimilarCaseRetriever(top_k=2)
        retriever.build_index(minimal_data)
        results = retriever.retrieve(query_transaction, top_k=1)
        assert len(results) == 1
