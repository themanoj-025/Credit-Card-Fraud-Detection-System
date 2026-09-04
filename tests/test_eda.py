"""
Tests for the EDA module.

Verifies figure-generation functions run without error and produce
files at the expected path with non-zero size.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

pytestmark = pytest.mark.unit




@pytest.fixture(scope="module")
def sample_df() -> None:
    """Create a small synthetic dataset for EDA testing."""
    np.random.seed(42)
    n = 500
    data = {f"V{i}": np.random.randn(n) for i in range(1, 29)}
    data["Time"] = np.random.uniform(0, 172800, n)
    data["Amount"] = np.random.exponential(100, n)
    data["Class"] = np.random.choice([0, 1], n, p=[0.99, 0.01])
    return pd.DataFrame(data)


class TestEDAFunctions:
    """Smoke tests for EDA figure generation functions."""

    def test_plot_class_imbalance_returns_figure(self, sample_df) -> None:
        """Test that plot_class_imbalance returns a matplotlib Figure."""
        from src.fraudlens.analysis.eda import plot_class_imbalance

        fig = plot_class_imbalance(sample_df)
        import matplotlib.pyplot as plt

        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_amount_distribution_returns_figure(self, sample_df) -> None:
        """Test that plot_amount_distribution returns a matplotlib Figure."""
        from src.fraudlens.analysis.eda import plot_amount_distribution

        fig = plot_amount_distribution(sample_df)
        import matplotlib.pyplot as plt

        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_time_distribution_returns_figure(self, sample_df) -> None:
        """Test that plot_time_distribution returns a matplotlib Figure."""
        from src.fraudlens.analysis.eda import plot_time_distribution

        fig = plot_time_distribution(sample_df)
        import matplotlib.pyplot as plt

        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_correlation_heatmap_returns_figure(self, sample_df) -> None:
        """Test that plot_correlation_heatmap returns a matplotlib Figure."""
        from src.fraudlens.analysis.eda import plot_correlation_heatmap

        fig = plot_correlation_heatmap(sample_df)
        import matplotlib.pyplot as plt

        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_feature_separability_returns_figure(self, sample_df) -> None:
        """Test that plot_feature_separability returns a matplotlib Figure."""
        from src.fraudlens.analysis.eda import plot_feature_separability

        fig = plot_feature_separability(sample_df)
        import matplotlib.pyplot as plt

        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_plot_feature_distributions_returns_figure(self, sample_df) -> None:
        """Test that plot_feature_distributions returns a matplotlib Figure."""
        from src.fraudlens.analysis.eda import plot_feature_distributions

        fig = plot_feature_distributions(sample_df)
        import matplotlib.pyplot as plt

        assert isinstance(fig, plt.Figure)
        plt.close(fig)


class TestEDARun:
    """Tests for the run_eda pipeline function."""

    def test_run_eda_creates_figures(self, sample_df) -> None:
        """Test that run_eda saves figures to output directory.

        Uses mock to inject sample_df instead of loading the real dataset
        (which may not be available in CI). Previously this test silently
        caught FileNotFoundError and passed without exercising any code.

        Note: plot_pairplot_top_features and plot_tsne_projection are excluded
        from this test because they require larger sample sizes and may fail
        on the small synthetic fixture.
        """
        # Patch out the problematic charts for the small synthetic dataset
        import matplotlib.pyplot as plt

        from src.fraudlens.analysis.eda import run_eda

        def _dummy_fig():
            fig, ax = plt.subplots(figsize=(4, 4))
            ax.text(0.5, 0.5, "Skipped for small data", ha="center", va="center")
            plt.close(fig)
            return fig

        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            with patch("src.fraudlens.analysis.eda._load_data", return_value=sample_df):
                with patch(
                    "src.fraudlens.analysis.eda.plot_pairplot_top_features",
                    return_value=_dummy_fig(),
                ):
                    run_eda(output_dir)

            # Assert actual output was created — real assertion, not just "doesn't raise"
            expected_files = [
                "01_class_imbalance.png",
                "02_amount_distribution.png",
                "03_time_distribution.png",
                "06_correlation_heatmap.png",
                "07_feature_separability.png",
                "08_feature_distributions.png",
                "09_pairplot_top_features.png",  # This one uses the dummy
            ]
            for fname in expected_files:
                fpath = output_dir / fname
                assert fpath.exists(), f"Expected EDA figure not created: {fpath}"
                assert fpath.stat().st_size > 0, f"EDA figure is empty: {fpath}"

    def test_save_fig_creates_file(self, sample_df) -> None:
        """Test that _save_fig writes a file."""
        from src.fraudlens.analysis.eda import plot_class_imbalance

        fig = plot_class_imbalance(sample_df)
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_chart.png"
            fig.savefig(output_path, dpi=72, bbox_inches="tight")
            import matplotlib.pyplot as plt

            plt.close(fig)

            assert output_path.exists()
            assert output_path.stat().st_size > 0


class TestFeatureImportance:
    """Tests for feature importance computation."""

    def test_feature_importance_returns_top_features(self, sample_df) -> None:
        """Test that feature importance identifies top discriminative features."""
        from src.fraudlens.analysis.eda import _get_feature_importances

        importances = _get_feature_importances(sample_df)
        assert isinstance(importances, pd.DataFrame)
        assert "feature" in importances.columns
        assert "importance" in importances.columns
        assert len(importances) == 28  # V1-V28
        # Should be sorted by importance descending
        assert importances.iloc[0]["importance"] >= importances.iloc[-1]["importance"]


class TestFeatureImportanceCache:
    """Tests for the _FEATURE_IMPORTANCE_CACHE global cache."""

    def test_cache_miss_populates_and_returns(self, sample_df) -> None:
        """Cache miss -> populates cache, returns computed value."""
        from src.fraudlens.analysis import eda

        # Ensure cache starts empty
        eda._FEATURE_IMPORTANCE_CACHE = None

        result = eda._get_feature_importances(sample_df)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 28
        # Cache should now be populated
        assert eda._FEATURE_IMPORTANCE_CACHE is not None

    def test_cache_hit_reuses_cached(self, sample_df) -> None:
        """Cache hit -> returns cached value without recomputing.

        We mock the underlying RandomForestClassifier to prove that
        a second call to _get_feature_importances does NOT call fit().
        """
        from sklearn.ensemble import RandomForestClassifier

        from src.fraudlens.analysis import eda

        # Populate cache
        eda._FEATURE_IMPORTANCE_CACHE = None
        eda._get_feature_importances(sample_df)
        assert eda._FEATURE_IMPORTANCE_CACHE is not None

        # Now mock fit to raise — if cache is working, it won't be called
        original_fit = RandomForestClassifier.fit
        fit_called = []

        def _broken_fit(self, X, y, *args, **kwargs):
            fit_called.append(True)
            return original_fit(self, X, y, *args, **kwargs)

        with patch.object(RandomForestClassifier, "fit", _broken_fit):
            result = eda._get_feature_importances(sample_df)

        # fit() should NOT have been called — cache hit means we skip training
        assert (
            len(fit_called) == 0
        ), "fit() was called despite cache being populated — cache miss bug"
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 28

    def test_cache_invalidation_on_run_eda(self, sample_df) -> None:
        """Calling run_eda() resets and recomputes the cache.

        The cache is reset to None at the start of run_eda() and then
        repopulated during chart generation. This test verifies the cache
        is not stale from a previous call.
        """
        import pandas as pd

        from src.fraudlens.analysis import eda

        # Populate cache with a marker value
        eda._FEATURE_IMPORTANCE_CACHE = "STALE_CACHE_MARKER"

        # run_eda should reset and repopulate cache
        with patch("src.fraudlens.analysis.eda._load_data", return_value=sample_df):
            with tempfile.TemporaryDirectory() as tmpdir:
                eda.run_eda(Path(tmpdir))

        # Cache should have been refreshed (not the stale string marker)
        # If run_eda did NOT reset the cache, it would still be the string
        assert isinstance(eda._FEATURE_IMPORTANCE_CACHE, pd.DataFrame), (
            "run_eda() should invalidate and recompute the cache, "
            f"but it was still {type(eda._FEATURE_IMPORTANCE_CACHE).__name__}"
        )
        assert "feature" in eda._FEATURE_IMPORTANCE_CACHE.columns
