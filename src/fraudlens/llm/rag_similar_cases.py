"""
RAG Similar-Case Retrieval Module

Embeds historical flagged transactions into a local vector store (FAISS)
and retrieves the 3 most similar historical cases for any new flagged
transaction, giving the analyst precedent to reason from.

Embedding Approach:
  By default, raw PCA feature vectors are used with FAISS IndexFlatIP
  (cosine similarity after L2 normalization). An optional EmbeddingProjector
  can apply learned dimensionality reduction (PCA) before indexing for
  improved semantic similarity — controlled via RAG_USE_PROJECTION setting.

This is a light, honestly-scoped RAG implementation — not overengineered,
uses FAISS (no hosted vector DB needed).
"""

import logging
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.fraudlens.config import (
    ALL_FEATURES,
    EMBEDDING_DIM,
    MODELS_DIR,
    RAG_PROJECTION_COMPONENTS,
    RAG_TOP_K,
    RAG_USE_PROJECTION,
)

logger = logging.getLogger(__name__)


class EmbeddingProjector:
    """
    Learned embedding projection for RAG retrieval.

    Applies dimensionality reduction (PCA) to raw feature vectors before
    FAISS indexing, transforming them into a lower-dimensional space that
    preserves the most variance. This converts "raw nearest neighbor" into
    "learned semantic similarity" — a meaningful upgrade for the RAG pipeline.

    The projector is fit on historical cases during build_index() and
    applied to both historical and query vectors at retrieval time.

    Can be extended to use any sklearn-compatible transformer (e.g., TruncatedSVD,
    a learned neural projection) by passing a custom transformer to the constructor.
    """

    def __init__(
        self,
        n_components: int = 20,
        random_state: int = 42,
        transformer: Any | None = None,
    ) -> None:
        """
        Args:
            n_components: Target embedding dimension
            random_state: Random seed for reproducibility
            transformer: Optional pre-configured sklearn transformer.
                         If None, uses PCA with n_components.
        """
        self.n_components = n_components
        self.random_state = random_state
        self.transformer = transformer
        self._fitted = False
        self._input_dim: int | None = None

    def _get_default_transformer(self):
        """Create default PCA transformer."""
        from sklearn.decomposition import PCA

        return PCA(
            n_components=self.n_components,
            random_state=self.random_state,
            whiten=False,
        )

    def fit(self, X: np.ndarray) -> "EmbeddingProjector":
        """
        Fit the projection transformer on the historical data.

        Args:
            X: Input feature matrix (n_samples, n_features)

        Returns:
            Self for chaining
        """
        if self.transformer is None:
            self.transformer = self._get_default_transformer()

        self._input_dim = X.shape[1]
        self.transformer.fit(X)
        self._fitted = True

        explained_variance = getattr(
            self.transformer, "explained_variance_ratio_", None
        )
        if explained_variance is not None:
            logger.info(
                "EmbeddingProjector fitted: %d → %d dims (%.1f%% variance explained)",
                self._input_dim,
                self.n_components,
                float(explained_variance.sum() * 100),
            )
        else:
            logger.info(
                "EmbeddingProjector fitted: %d → %d dims",
                self._input_dim,
                self.n_components,
            )
        return self

    def transform(self, X: np.ndarray) -> np.ndarray:
        """
        Project features into the learned embedding space.

        Args:
            X: Input feature matrix (n_samples, n_features)

        Returns:
            Projected embeddings (n_samples, n_components)

        Raises:
            RuntimeError: If projector hasn't been fitted
        """
        if not self._fitted or self.transformer is None:
            raise RuntimeError(
                "Projector not fitted. Call fit() first with historical data."
            )
        return self.transformer.transform(X).astype(np.float32)

    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        """Fit and transform in one step."""
        return self.fit(X).transform(X)

    @property
    def embedding_dim(self) -> int:
        """Get the output embedding dimension."""
        return self.n_components


class SimilarCaseRetriever:
    """
    Retrieve similar historical flagged transactions using FAISS.

    Uses FAISS IndexFlatIP (inner product = cosine similarity after L2 norm)
    for nearest-neighbor search. Supports an optional EmbeddingProjector
    for learned dimensionality reduction.

    The embedding approach is governed by config settings:
    - RAG_USE_PROJECTION=True: applies learned projection before FAISS
    - RAG_PROJECTION_COMPONENTS: target embedding dimension (default 20)
    """

    def __init__(
        self,
        embedding_dim: int = EMBEDDING_DIM,
        top_k: int = RAG_TOP_K,
        use_projection: bool = RAG_USE_PROJECTION,
        projection_components: int = RAG_PROJECTION_COMPONENTS,
    ) -> None:
        """
        Args:
            embedding_dim: Raw feature dimension (used if no projection)
            top_k: Number of similar cases to retrieve
            use_projection: Whether to use learned embedding projection
            projection_components: Target dimension for projected embeddings
        """
        self.top_k = top_k
        self.use_projection = use_projection
        self.projection_components = projection_components
        self.index = None
        self.historical_cases: pd.DataFrame | None = None
        self.projector: EmbeddingProjector | None = None
        self._feature_columns: list[str] = []
        self._initialized = False
        # Effective embedding dim depends on projection state
        self.embedding_dim = projection_components if use_projection else embedding_dim

    def _init_faiss(self):
        """Lazy import FAISS to avoid hard dependency."""
        try:
            import faiss

            self._faiss = faiss
        except ImportError:
            logger.warning("faiss not installed. Install with: pip install faiss-cpu")
            raise

    def build_index(
        self,
        historical_data: pd.DataFrame,
        outcome_column: str = "Class",
        feature_columns: list[str] | None = None,
    ) -> "SimilarCaseRetriever":
        """
        Build the FAISS index from historical transaction data.

        If RAG_USE_PROJECTION is enabled, fits an EmbeddingProjector (PCA)
        on the historical features and indexes the projected embeddings.
        Otherwise, indexes raw feature vectors directly.

        Args:
            historical_data: DataFrame with historical transactions
            outcome_column: Column name with fraud labels (0/1)
            feature_columns: Feature columns to embed (default from config)

        Returns:
            Self for chaining
        """
        self._init_faiss()

        features = feature_columns or [
            c for c in ALL_FEATURES if c in historical_data.columns
        ]
        self._feature_columns = features

        # Store historical cases with outcomes
        self.historical_cases = historical_data[features + [outcome_column]].copy()
        self.historical_cases.rename(
            columns={outcome_column: "actual_outcome"}, inplace=True
        )
        self.historical_cases["is_fraud"] = self.historical_cases["actual_outcome"] == 1

        # Get raw feature embeddings
        raw_embeddings = self.historical_cases[features].values.astype(np.float32)

        # Optionally apply learned projection
        if self.use_projection:
            self.projector = EmbeddingProjector(n_components=self.projection_components)
            embeddings = self.projector.fit_transform(raw_embeddings)
            self.embedding_dim = self.projector.embedding_dim
            logger.info(
                "Using learned projection: %d → %d dims",
                raw_embeddings.shape[1],
                self.embedding_dim,
            )
        else:
            embeddings = raw_embeddings
            self.embedding_dim = raw_embeddings.shape[1]
            logger.info("Using raw feature embeddings (%d dims)", self.embedding_dim)

        # Normalize and build FAISS index
        embeddings = np.ascontiguousarray(embeddings)
        self._faiss.normalize_L2(embeddings)

        self.index = self._faiss.IndexFlatIP(self.embedding_dim)
        self.index.add(embeddings)

        self._initialized = True
        logger.info(
            "FAISS index built: %d cases, %d dimensions",
            len(self.historical_cases),
            self.embedding_dim,
        )
        return self

    def retrieve(
        self,
        transaction: dict[str, Any],
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve similar historical cases for a given transaction.

        Transforms the query through the same projection pipeline (if enabled)
        before FAISS search, ensuring the query and index are in the same
        embedding space.

        Args:
            transaction: Feature dictionary of the flagged transaction
            top_k: Number of similar cases to return (default from config)

        Returns:
            List of similar cases with similarity scores and outcomes

        Raises:
            RuntimeError: If index hasn't been built
        """
        if not self._initialized or self.index is None:
            raise RuntimeError(
                "Index not built. Call build_index() first with historical data."
            )

        k = top_k or self.top_k

        # Extract features
        features = self._feature_columns
        query = np.array(
            [[transaction.get(f, 0.0) for f in features]], dtype=np.float32
        )

        # Apply same projection as index (if enabled)
        if self.use_projection and self.projector is not None:
            query = self.projector.transform(query)

        query = np.ascontiguousarray(query)
        self._faiss.normalize_L2(query)

        # Search
        scores, indices = self.index.search(query, min(k, self.index.ntotal))

        results = []
        for idx, score in zip(indices[0], scores[0]):
            case = self.historical_cases.iloc[idx]
            results.append(
                {
                    "similarity_score": round(float(score), 4),
                    "actual_outcome": (
                        "confirmed_fraud" if case["is_fraud"] else "false_positive"
                    ),
                    "features": {
                        col: round(float(case[col]), 4)
                        for col in features[:5]  # Top 5 features for display
                    },
                }
            )

        return results

    def save(self, path: str | None = None) -> str:
        """Save the FAISS index and historical data to disk."""
        if not self._initialized or self.index is None:
            raise RuntimeError("Index not built. Nothing to save.")

        if path is None:
            path = str(MODELS_DIR / "rag_index")

        Path(path).mkdir(parents=True, exist_ok=True)
        self._faiss.write_index(self.index, str(Path(path) / "index.faiss"))
        self.historical_cases.to_csv(Path(path) / "historical_cases.csv", index=False)

        # Save projector state if used
        if self.use_projection and self.projector is not None:
            import joblib

            joblib.dump(self.projector.transformer, Path(path) / "projector.pkl")
            logger.info("RAG projector saved to %s", path)

        logger.info("RAG index saved to %s", path)
        return path

    def load(self, path: str) -> "SimilarCaseRetriever":
        """Load a saved FAISS index and historical data."""
        self._init_faiss()
        load_path = Path(path)

        self.index = self._faiss.read_index(str(load_path / "index.faiss"))
        self.historical_cases = pd.read_csv(load_path / "historical_cases.csv")
        self.embedding_dim = self.index.d

        # Reconstruct feature columns from loaded data (excluding outcome columns)
        self._feature_columns = [
            c
            for c in self.historical_cases.columns
            if c not in ("actual_outcome", "is_fraud")
        ]

        # Restore projector state if available
        projector_path = load_path / "projector.pkl"
        if projector_path.exists():
            import joblib

            transformer = joblib.load(str(projector_path))
            self.projector = EmbeddingProjector(transformer=transformer)
            self.projector.transformer = transformer
            self.projector._fitted = True
            self.use_projection = True
            logger.info("RAG projector loaded from %s", projector_path)

        self._initialized = True
        logger.info(
            "RAG index loaded from %s (%d cases)", path, len(self.historical_cases)
        )
        return self


def create_retriever(
    historical_data: pd.DataFrame | None = None,
    use_projection: bool = RAG_USE_PROJECTION,
) -> SimilarCaseRetriever:
    """Create and optionally build a SimilarCaseRetriever."""
    retriever = SimilarCaseRetriever(use_projection=use_projection)
    if historical_data is not None:
        retriever.build_index(historical_data)
    return retriever
