"""
FraudLens — Enhanced Exploratory Data Analysis (Stage 2)

Generates all EDA visualizations and saves them to reports/figures/ for
reuse in the README, Streamlit dashboard, and notebooks.

Outputs:
  reports/figures/
    ├── 01_class_imbalance.png        — Bar chart of class distribution
    ├── 02_amount_distribution.png    — Amount distribution by class
    ├── 03_time_distribution.png      — Time distribution by class
    ├── 04_tsne_projection.png        — t-SNE 2D projection (V1-V28)
    ├── 05_umap_projection.png        — UMAP 2D projection (V1-V28)
    ├── 06_correlation_heatmap.png    — Feature correlation heatmap
    ├── 07_feature_separability.png   — Top feature box plots by class
    ├── 08_feature_distributions.png  — Top 9 feature distributions
    └── 09_pairplot_top_features.png  — Pairplot of top 4 features
"""

import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

matplotlib.use("Agg")
sns.set_style("whitegrid")

from src.fraudlens.config import FIGURES_DIR, PCA_FEATURES, REPORTS_DIR
from src.fraudlens.data.loaders import DataLoader

logger = logging.getLogger(__name__)

# Style Configuration

COLORS = {"legitimate": "#2ecc71", "fraud": "#e74c3c"}
LABELS = {0: "Legitimate", 1: "Fraud"}
DPI = 150

# Cache for RF feature importance (computed once, reused across charts)
_FEATURE_IMPORTANCE_CACHE = None


def _load_data() -> pd.DataFrame:
    """Load the credit card fraud dataset."""
    loader = DataLoader()
    df = loader.load()
    stats = loader.get_basic_stats()
    print(f"\nDataset: {df.shape[0]:,} transactions, {df.shape[1]} columns")
    print(f"Fraud rate: {stats['fraud_rate_pct']:.4f}% ({stats['n_fraud']:,} frauds)")
    return df


def _save_fig(fig: plt.Figure, name: str, output_dir: Path = FIGURES_DIR) -> None:
    """Save a figure to reports/figures/."""
    path = output_dir / name
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [OK] Saved: {path}")


def plot_class_imbalance(df: pd.DataFrame) -> plt.Figure:
    """Chart 1: Class imbalance bar chart."""
    fig, ax = plt.subplots(figsize=(10, 6))
    class_counts = df["Class"].value_counts()

    bars = ax.bar(
        [LABELS[0], LABELS[1]],
        class_counts.values,
        color=[COLORS["legitimate"], COLORS["fraud"]],
        edgecolor="white",
        linewidth=1.5,
        width=0.6,
    )

    # Annotate bars
    for bar, count in zip(bars, class_counts.values):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(class_counts.values) * 0.01,
            f"{count:,}\n({count / len(df) * 100:.3f}%)",
            ha="center",
            va="bottom",
            fontsize=13,
            fontweight="bold",
        )

    ax.set_title("Class Distribution", fontsize=18, fontweight="bold", pad=20)
    ax.set_ylabel("Number of Transactions", fontsize=14)
    ax.set_ylim(0, max(class_counts.values) * 1.15)
    ax.tick_params(axis="both", labelsize=12)

    # Add annotation about imbalance ratio
    ratio = class_counts[0] / class_counts[1]
    ax.text(
        0.5,
        0.92,
        f"Imbalance Ratio: {ratio:.0f}:1 (Legitimate : Fraud)",
        transform=ax.transAxes,
        fontsize=12,
        ha="center",
        color="#555",
        style="italic",
    )

    plt.tight_layout()
    return fig


def plot_amount_distribution(df: pd.DataFrame) -> plt.Figure:
    """Chart 2: Amount distribution by class (histogram + box plot)."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    # Histogram
    ax1 = axes[0]
    for cls, label in LABELS.items():
        subset = df[df["Class"] == cls]["Amount"]
        color = COLORS["legitimate"] if cls == 0 else COLORS["fraud"]
        ax1.hist(
            subset,
            bins=100,
            alpha=0.7,
            color=color,
            label=f"{label} (n={len(subset):,})",
            density=True,
        )
    ax1.set_xlabel("Transaction Amount ($)", fontsize=13)
    ax1.set_ylabel("Density", fontsize=13)
    ax1.set_title("Amount Distribution by Class", fontsize=15, fontweight="bold")
    ax1.legend(fontsize=11)
    ax1.set_xlim(0, 1000)  # Focus on majority of data

    # Box plot
    ax2 = axes[1]
    bp_data = [
        df[df["Class"] == 0]["Amount"].clip(upper=500),
        df[df["Class"] == 1]["Amount"].clip(upper=500),
    ]
    bp = ax2.boxplot(
        bp_data, tick_labels=[LABELS[0], LABELS[1]], patch_artist=True, widths=0.5
    )
    bp["boxes"][0].set_facecolor(COLORS["legitimate"])
    bp["boxes"][1].set_facecolor(COLORS["fraud"])
    ax2.set_title(
        "Amount Distribution (Box Plot, capped at $500)", fontsize=15, fontweight="bold"
    )
    ax2.set_ylabel("Transaction Amount ($)", fontsize=13)

    # Add statistics annotations
    for cls, label in LABELS.items():
        subset = df[df["Class"] == cls]["Amount"]
        stats_text = f"{label}\nMean: ${subset.mean():.2f}\nMedian: ${subset.median():.2f}\nMax: ${subset.max():,.2f}"
        ax2.annotate(
            stats_text,
            xy=(cls + 1, subset.median()),
            xytext=(cls + 1.3, min(subset.clip(upper=500).max(), 450)),
            fontsize=10,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.8),
        )

    plt.tight_layout()
    return fig


def plot_time_distribution(df: pd.DataFrame) -> plt.Figure:
    """Chart 3: Time distribution by class."""
    fig, axes = plt.subplots(1, 2, figsize=(16, 6))

    for cls, label in LABELS.items():
        ax = axes[cls]
        subset = df[df["Class"] == cls]["Time"] / 3600  # Convert to hours
        color = COLORS["legitimate"] if cls == 0 else COLORS["fraud"]
        ax.hist(subset, bins=48, alpha=0.8, color=color, edgecolor="white")
        ax.set_xlabel("Time (hours)", fontsize=13)
        ax.set_ylabel("Frequency", fontsize=13)
        ax.set_title(
            f"{label} Transactions Over Time (n={len(subset):,})",
            fontsize=15,
            fontweight="bold",
        )
        ax.axvline(x=12, color="gray", linestyle="--", alpha=0.5, label="Noon")
        ax.legend(fontsize=11)

    plt.tight_layout()
    return fig


def plot_tsne_projection(df: pd.DataFrame, sample_size: int = 10000) -> plt.Figure:
    """Chart 4: t-SNE 2D projection of V1-V28 colored by class."""
    from sklearn.manifold import TSNE

    # Sample for speed
    if len(df) > sample_size:
        fraud_idx = df[df["Class"] == 1].index
        legit_idx = (
            df[df["Class"] == 0]
            .sample(n=sample_size - len(fraud_idx), random_state=42)
            .index
        )
        sample_idx = sorted(np.concatenate([fraud_idx, legit_idx]))
        df_sample = df.loc[sample_idx]
    else:
        df_sample = df

    print(f"  Running t-SNE on {len(df_sample):,} samples...")
    X = df_sample[PCA_FEATURES].fillna(0).values
    y = df_sample["Class"].values

    tsne = TSNE(
        n_components=2,
        random_state=42,
        perplexity=30,
        max_iter=1000,
        verbose=0,
        learning_rate="auto",
    )
    X_tsne = tsne.fit_transform(X)

    fig, ax = plt.subplots(figsize=(12, 10))
    for cls in [0, 1]:
        mask = y == cls
        color = COLORS["legitimate"] if cls == 0 else COLORS["fraud"]
        label = LABELS[cls]
        ax.scatter(
            X_tsne[mask, 0],
            X_tsne[mask, 1],
            c=color,
            label=f"{label} (n={mask.sum():,})",
            alpha=0.6,
            s=5 if cls == 0 else 20,
            edgecolors="none",
        )

    ax.set_title("t-SNE Projection of V1-V28 Features", fontsize=18, fontweight="bold")
    ax.set_xlabel("t-SNE Component 1", fontsize=13)
    ax.set_ylabel("t-SNE Component 2", fontsize=13)
    ax.legend(fontsize=12, markerscale=3)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    return fig


def plot_umap_projection(df: pd.DataFrame, sample_size: int = 10000) -> plt.Figure:
    """Chart 5: UMAP 2D projection of V1-V28 colored by class."""
    try:
        import umap

        # Sample for speed
        if len(df) > sample_size:
            fraud_idx = df[df["Class"] == 1].index
            legit_idx = (
                df[df["Class"] == 0]
                .sample(n=sample_size - len(fraud_idx), random_state=42)
                .index
            )
            sample_idx = sorted(np.concatenate([fraud_idx, legit_idx]))
            df_sample = df.loc[sample_idx]
        else:
            df_sample = df

        print(f"  Running UMAP on {len(df_sample):,} samples...")
        X = df_sample[PCA_FEATURES].fillna(0).values
        y = df_sample["Class"].values

        reducer = umap.UMAP(
            n_components=2, random_state=42, n_neighbors=30, min_dist=0.1
        )
        X_umap = reducer.fit_transform(X)

        fig, ax = plt.subplots(figsize=(12, 10))
        for cls in [0, 1]:
            mask = y == cls
            color = COLORS["legitimate"] if cls == 0 else COLORS["fraud"]
            label = LABELS[cls]
            ax.scatter(
                X_umap[mask, 0],
                X_umap[mask, 1],
                c=color,
                label=f"{label} (n={mask.sum():,})",
                alpha=0.6,
                s=5 if cls == 0 else 20,
                edgecolors="none",
            )

        ax.set_title(
            "UMAP Projection of V1-V28 Features", fontsize=18, fontweight="bold"
        )
        ax.set_xlabel("UMAP Component 1", fontsize=13)
        ax.set_ylabel("UMAP Component 2", fontsize=13)
        ax.legend(fontsize=12, markerscale=3)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        return fig
    except ImportError:
        print("  [SKIP] UMAP not installed. Install with: pip install umap-learn")
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(
            0.5,
            0.5,
            "UMAP not available\nInstall: pip install umap-learn",
            ha="center",
            va="center",
            fontsize=14,
            transform=ax.transAxes,
        )
        return fig


def plot_correlation_heatmap(df: pd.DataFrame) -> plt.Figure:
    """Chart 6: Correlation heatmap of V1-V28 features."""
    corr = df[PCA_FEATURES].corr()

    fig, ax = plt.subplots(figsize=(14, 12))
    mask = np.triu(np.ones_like(corr, dtype=bool), k=1)
    cmap = sns.diverging_palette(250, 10, as_cmap=True)

    sns.heatmap(
        corr,
        mask=mask,
        cmap=cmap,
        center=0,
        square=True,
        linewidths=0.5,
        cbar_kws={"shrink": 0.75},
        ax=ax,
        vmin=-1,
        vmax=1,
        xticklabels=True,
        yticklabels=True,
    )

    ax.set_title(
        "Feature Correlation Heatmap (V1-V28)", fontsize=18, fontweight="bold", pad=20
    )
    ax.tick_params(axis="both", labelsize=8)
    plt.xticks(rotation=90)
    plt.yticks(rotation=0)

    plt.tight_layout()
    return fig


def _get_feature_importances(df: pd.DataFrame) -> pd.DataFrame:
    """Compute feature importances once and cache for reuse across charts."""
    global _FEATURE_IMPORTANCE_CACHE
    if _FEATURE_IMPORTANCE_CACHE is not None:
        return _FEATURE_IMPORTANCE_CACHE

    from sklearn.ensemble import RandomForestClassifier

    print("  Computing feature importances (RF, cached)...")
    X = df[PCA_FEATURES].fillna(0).values
    y = df["Class"].values

    rf = RandomForestClassifier(n_estimators=100, random_state=42, n_jobs=-1)
    rf.fit(X, y)
    _FEATURE_IMPORTANCE_CACHE = pd.DataFrame(
        {
            "feature": PCA_FEATURES,
            "importance": rf.feature_importances_,
        }
    ).sort_values("importance", ascending=False)

    return _FEATURE_IMPORTANCE_CACHE


def plot_feature_separability(df: pd.DataFrame) -> plt.Figure:
    """Chart 7: Single-feature separability check — box plots of top 6 features."""
    importances = _get_feature_importances(df)
    top_features = importances.head(6)["feature"].tolist()
    print(f"  Top features: {top_features}")
    print(f"  Top features: {top_features}")

    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.flatten()

    for idx, feature in enumerate(top_features):
        ax = axes[idx]
        legit_vals = df[df["Class"] == 0][feature]
        fraud_vals = df[df["Class"] == 1][feature]

        bp = ax.boxplot(
            [legit_vals, fraud_vals],
            tick_labels=[LABELS[0], LABELS[1]],
            patch_artist=True,
            widths=0.5,
        )
        bp["boxes"][0].set_facecolor(COLORS["legitimate"])
        bp["boxes"][1].set_facecolor(COLORS["fraud"])
        bp["medians"][0].set_color("white")
        bp["medians"][1].set_color("white")

        ax.set_title(
            f"{feature} (importance={importances.iloc[idx]['importance']:.4f})",
            fontsize=13,
            fontweight="bold",
        )
        ax.tick_params(axis="x", labelsize=10)
        ax.grid(True, alpha=0.3)

    fig.suptitle(
        "Top 6 Features — Class Separability", fontsize=16, fontweight="bold", y=1.02
    )
    plt.tight_layout()
    return fig


def plot_feature_distributions(df: pd.DataFrame) -> plt.Figure:
    """Chart 8: Distribution of top 9 features by class."""
    importances = _get_feature_importances(df)
    top_9 = importances.head(9)["feature"].tolist()

    fig, axes = plt.subplots(3, 3, figsize=(18, 15))
    axes = axes.flatten()

    for idx, feature in enumerate(top_9):
        ax = axes[idx]
        for cls in [0, 1]:
            subset = df[df["Class"] == cls][feature]
            color = COLORS["legitimate"] if cls == 0 else COLORS["fraud"]
            ax.hist(
                subset, bins=50, alpha=0.6, color=color, label=LABELS[cls], density=True
            )
        ax.set_title(feature, fontsize=14, fontweight="bold")
        ax.tick_params(axis="both", labelsize=10)
        if idx == 0:
            ax.legend(fontsize=11)

    fig.suptitle(
        "Top 9 Feature Distributions by Class", fontsize=16, fontweight="bold", y=1.02
    )
    plt.tight_layout()
    return fig


def plot_pairplot_top_features(df: pd.DataFrame, sample_size: int = 5000) -> plt.Figure:
    """Chart 9: Pairplot of top 4 features colored by class."""
    importances = _get_feature_importances(df)

    # Sample for speed
    if len(df) > sample_size:
        fraud_idx = df[df["Class"] == 1].index
        legit_idx = (
            df[df["Class"] == 0]
            .sample(n=sample_size - len(fraud_idx), random_state=42)
            .index
        )
        sample_idx = sorted(np.concatenate([fraud_idx, legit_idx]))
        df_sample = df.loc[sample_idx]
    else:
        df_sample = df

    top_4 = importances.head(4)["feature"].tolist()

    print(f"  Generating pairplot of {top_4}...")
    df_plot = df_sample[top_4 + ["Class"]].copy()
    df_plot["Class"] = df_plot["Class"].map(LABELS)

    # Derive pairplot palette from existing COLORS/LABELS (avoid duplicating hex values)
    pairplot_colors = {v: COLORS[v.lower()] for v in LABELS.values()}
    _g = sns.pairplot(
        df_plot,
        hue="Class",
        palette=pairplot_colors,
        diag_kind="kde",
        plot_kws={"alpha": 0.5, "s": 10, "edgecolor": "none"},
        diag_kws={"alpha": 0.6},
        height=2.5,
    )
    # Capture figure from current pyplot state (compatible across seaborn versions)
    fig = plt.gcf()
    fig.suptitle("Pairplot of Top 4 Features", fontsize=16, fontweight="bold", y=1.02)

    return fig


# Main Pipeline


def run_eda(output_dir: Path = FIGURES_DIR) -> None:
    """
    Run the complete EDA pipeline, saving all figures.

    Args:
        output_dir: Directory to save figures to
    """
    global _FEATURE_IMPORTANCE_CACHE
    _FEATURE_IMPORTANCE_CACHE = None  # Reset cache

    print("=" * 70)
    print("  FRAUDLENS — Enhanced Exploratory Data Analysis")
    print("=" * 70)

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\nOutput directory: {output_dir}\n")

    # Load data
    try:
        df = _load_data()
    except FileNotFoundError as e:
        print(f"\n  ❌ {e}")
        print(
            "  Download the dataset from: https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud"
        )
        print("  Place it at: data/raw/creditcard.csv")
        return

    # Basic info
    print(f"\n  Columns: {list(df.columns)}")
    print(f"  Missing values: {df.isnull().sum().sum()}")
    print(f"  Memory: {df.memory_usage(deep=True).sum() / 1024**2:.1f} MB\n")

    # ─── Generate all charts ────────────────────────────────────────
    charts = [
        ("01_class_imbalance.png", plot_class_imbalance(df)),
        ("02_amount_distribution.png", plot_amount_distribution(df)),
        ("03_time_distribution.png", plot_time_distribution(df)),
        ("04_tsne_projection.png", plot_tsne_projection(df)),
        ("05_umap_projection.png", plot_umap_projection(df)),
        ("06_correlation_heatmap.png", plot_correlation_heatmap(df)),
        ("07_feature_separability.png", plot_feature_separability(df)),
        ("08_feature_distributions.png", plot_feature_distributions(df)),
        ("09_pairplot_top_features.png", plot_pairplot_top_features(df)),
    ]

    for name, fig in charts:
        _save_fig(fig, name, output_dir)

    # ─── Summary ─────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print(f"  EDA COMPLETE — {len(charts)} charts saved to {output_dir}")
    print(f"{'=' * 70}")
    print("\n  Generated charts:")
    for name, _ in charts:
        path = output_dir / name
        size_kb = path.stat().st_size / 1024 if path.exists() else 0
        print(f"    📊 {name} ({size_kb:.0f} KB)")

    # Save a summary of findings
    summary = {
        "n_transactions": len(df),
        "n_fraud": int(df["Class"].sum()),
        "n_legitimate": int(len(df) - df["Class"].sum()),
        "fraud_rate_pct": round(df["Class"].mean() * 100, 4),
        "features": list(df.columns),
        "charts_generated": [name for name, _ in charts],
    }

    import json

    summary_path = REPORTS_DIR / "eda_summary.json"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n  Summary saved to: {summary_path}")
    print()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    run_eda()
