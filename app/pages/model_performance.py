"""
Model Performance Page

Interactive comparison charts and metrics from the model comparison run.
All charts are Plotly (interactive), not static images.
"""

from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.fraudlens.config import REPORTS_DIR


def _load_comparison_data() -> pd.DataFrame | None:
    """Load the model comparison CSV if it exists."""
    path = REPORTS_DIR / "model_comparison_fraud.csv"
    if path.exists():
        return pd.read_csv(path)
    # Try alternate location
    alt_path = Path("data/processed/model_comparison.csv")
    if alt_path.exists():
        return pd.read_csv(alt_path)
    return None


def show() -> None:
    """Render the Model Performance page."""
    st.markdown(
        "<h1>📊 Model Performance</h1>"
        "<p style='color: #a0a0a0; margin-top: -12px;'>"
        "Detailed model comparison, evaluation metrics, and threshold analysis</p>",
        unsafe_allow_html=True,
    )

    # ─── Load Data ─────────────────────────────────────────────────────
    comparison = _load_comparison_data()

    if comparison is None:
        st.warning(
            "No model comparison data found. "
            "Run the training pipeline first:\n"
            "```bash\npython run_pipeline.py\n```"
        )
        # Show placeholder data
        comparison = pd.DataFrame(
            {
                "Model": [
                    "XGBoost",
                    "Random Forest",
                    "Logistic Regression",
                    "LightGBM",
                    "Isolation Forest",
                ],
                "PR-AUC": [0.8810, 0.8352, 0.7159, 0.0428, 0.0981],
                "ROC-AUC": [0.9724, 0.9836, 0.9722, 0.9054, 0.9489],
                "F1": [0.7068, 0.5641, 0.6214, 0.0890, 0.1243],
                "Precision": [0.5828, 0.4112, 0.4780, 0.0470, 0.0680],
                "Recall": [0.8980, 0.8980, 0.8878, 0.8571, 0.7245],
                "Net Benefit ($)": [12445, 12130, 12140, 3655, 5430],
            }
        )

    # ─── Key Metrics ──────────────────────────────────────────────────
    best_row = comparison.iloc[0]
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            f"""
        <div style="background:#1a1a2e;border:1px solid #2a2a3e;border-radius:8px;padding:16px;">
            <span style="color:#a0a0a0;font-size:13px;">🏆 Best Model</span>
            <div style="color:#e0e0e0;font-size:24px;font-weight:700;">{best_row["Model"]}</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            f"""
        <div style="background:#1a1a2e;border:1px solid #38ef7d33;border-left:4px solid #38ef7d;border-radius:8px;padding:16px;">
            <span style="color:#a0a0a0;font-size:13px;">🎯 PR-AUC</span>
            <div style="color:#38ef7d;font-size:24px;font-weight:700;">{best_row["PR-AUC"]:.4f}</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            f"""
        <div style="background:#1a1a2e;border:1px solid #667eea33;border-left:4px solid #667eea;border-radius:8px;padding:16px;">
            <span style="color:#a0a0a0;font-size:13px;">🔄 F1 Score</span>
            <div style="color:#667eea;font-size:24px;font-weight:700;">{best_row["F1"]:.4f}</div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    with col4:
        net = best_row.get("Net Benefit ($)", 0)
        st.markdown(
            f"""
        <div style="background:#1a1a2e;border:1px solid #ff6b6b33;border-left:4px solid #ff6b6b;border-radius:8px;padding:16px;">
            <span style="color:#a0a0a0;font-size:13px;">💰 Net Benefit</span>
            <div style="color:#ff6b6b;font-size:24px;font-weight:700;">${net:,.0f}</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    # ─── Comparison Table ──────────────────────────────────────────────
    st.markdown("<h3>Model Comparison Table</h3>", unsafe_allow_html=True)
    styled = comparison.style.background_gradient(
        subset=["PR-AUC", "ROC-AUC", "F1"], cmap="RdYlGn"
    )
    st.dataframe(styled, use_container_width=True, hide_index=True)

    # ─── PR-AUC Bar Chart ────────────────────────────────────────────
    st.markdown("<h3>PR-AUC Comparison</h3>", unsafe_allow_html=True)
    fig1 = px.bar(
        comparison,
        x="Model",
        y="PR-AUC",
        color="PR-AUC",
        color_continuous_scale="RdYlGn",
        title="Precision-Recall AUC by Model",
        text="PR-AUC",
    )
    fig1.update_traces(texttemplate="%{text:.4f}", textposition="outside")
    fig1.update_layout(
        plot_bgcolor="#1a1a2e",
        paper_bgcolor="#0f0f1a",
        font_color="#e0e0e0",
        showlegend=False,
        height=400,
    )
    st.plotly_chart(fig1, use_container_width=True)

    # ─── Multi-Metric Comparison ──────────────────────────────────────
    st.markdown("<h3>Multi-Metric Comparison</h3>", unsafe_allow_html=True)

    metrics_to_plot = ["PR-AUC", "F1", "Precision", "Recall"]
    fig2 = go.Figure()
    for metric in metrics_to_plot:
        if metric in comparison.columns:
            fig2.add_trace(
                go.Bar(
                    name=metric,
                    x=comparison["Model"],
                    y=comparison[metric],
                    text=[f"{v:.3f}" for v in comparison[metric]],
                    textposition="auto",
                )
            )
    fig2.update_layout(
        title="All Metrics by Model",
        barmode="group",
        plot_bgcolor="#1a1a2e",
        paper_bgcolor="#0f0f1a",
        font_color="#e0e0e0",
        height=400,
    )
    st.plotly_chart(fig2, use_container_width=True)

    # ─── PR Curve (Placeholder) ──────────────────────────────────────
    st.markdown("<h3>Precision-Recall Curves</h3>", unsafe_allow_html=True)
    st.info(
        "PR curves will render here once a training run is complete. "
        "They'll show the precision-recall tradeoff for each model, "
        "with the area under the curve (PR-AUC) annotated."
    )

    # ─── Cost vs Threshold ────────────────────────────────────────────
    st.markdown("<h3>Cost vs. Decision Threshold</h3>", unsafe_allow_html=True)
    st.markdown(
        """
    <div style="background:#1a1a2e;border:1px solid #2a2a3e;border-radius:8px;padding:16px;margin:8px 0;">
        <p style="color:#e0e0e0;">
        The default threshold of <strong>0.5</strong> is rarely optimal for fraud detection.
        Our <strong>business cost function</strong> finds the threshold that minimizes:
        </p>
        <p style="color:#a0a0a0;font-family:monospace;">
        Total Cost = (Missed Fraud × $150) + (Flagged Transactions × $5)
        </p>
        <p style="color:#e0e0e0;">
        The optimal threshold is typically much lower than 0.5, because the cost
        of missing a fraud ($150) is 30× higher than the cost of reviewing a
        legitimate transaction ($5).
        </p>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # ─── Selection Reasoning ──────────────────────────────────────────
    st.markdown("<h3>📝 Auto-Selection Reasoning</h3>", unsafe_allow_html=True)
    st.markdown(
        f"""
    <div style="background:#1a1a2e;border:1px solid #667eea33;border-left:4px solid #667eea;border-radius:8px;padding:16px;">
        <p style="color:#e0e0e0;line-height:1.6;">
        <strong>Selection Rule:</strong> Model with highest PR-AUC is selected as best.<br><br>
        <strong>Winner:</strong> <code>{best_row["Model"]}</code> with PR-AUC of {best_row["PR-AUC"]:.4f}.<br><br>
        <strong>Why PR-AUC?</strong> With only 0.17% fraud in the dataset, ROC-AUC is misleading 
        (a random model can score 0.5+). PR-AUC evaluates performance on the minority class 
        honestly — it's the standard metric for imbalanced fraud detection.<br><br>
        <strong>Threshold:</strong> Optimized using the business cost function at $150/fraud vs $5/review.
        </p>
    </div>
    """,
        unsafe_allow_html=True,
    )
