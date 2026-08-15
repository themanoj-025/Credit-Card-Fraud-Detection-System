"""
Case Investigator Page

Select any flagged transaction and see:
- SHAP force plot (from real API)
- LLM plain-English narrative (from real API)
- Similar historical cases with outcomes (from real API)

Now uses the shared FraudLensAPI client — no hardcoded mock data.
"""

import random
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from app.api_client import api_call_with_spinner, get_api_client
from app.components.metric_cards import metric_card


def _generate_synthetic_transactions(n: int = 5) -> list[dict[str, Any]]:
    """Generate synthetic transactions for the selector dropdown.

    These are only used for the UI selector — every analysis call
    goes to the real API for prediction/explanation/similar-cases.
    """
    transactions = []
    for i in range(1, n + 1):
        amount = round(random.uniform(50, 5000), 2)
        tx = {f"V{i}": round(random.gauss(0, 1), 4) for i in range(1, 29)}
        tx["Time"] = round(random.uniform(0, 172800), 2)
        tx["Amount"] = amount
        # Inject fraud-like patterns for some
        if i % 3 == 1:
            tx["V14"] = round(random.uniform(-8, -3), 4)
            tx["V4"] = round(random.uniform(3, 8), 4)
        transactions.append(tx)
    return transactions


def show() -> None:
    """Render the Case Investigator page."""
    st.markdown(
        "<h1>🔍 Case Investigator</h1>"
        "<p style='color: #a0a0a0; margin-top: -12px;'>"
        "Deep-dive into flagged transactions with SHAP, LLM narratives, "
        "and similar case retrieval — all from the live API</p>",
        unsafe_allow_html=True,
    )

    # ─── Check API Availability ──────────────────────────────────────
    api = get_api_client()
    healthy = api.check_health().get("status") != "error"

    if not healthy:
        st.warning(
            "⚠️ FraudLens API is not running. "
            "The Case Investigator needs a live API to analyze transactions.\n\n"
            "Start the API with:\n"
            "```bash\nuvicorn api.main:app --reload --port 8000\n```"
        )
        # Still offer mock data as fallback
        if "use_fallback" not in st.session_state:
            st.session_state.use_fallback = st.button(
                "Use demo data (offline mode)", use_container_width=True
            )
        if not st.session_state.get("use_fallback", False):
            return

    # ─── Transaction Selection ───────────────────────────────────────
    st.markdown("<h3>Select a Transaction</h3>", unsafe_allow_html=True)

    col1, col2 = st.columns([3, 1])
    with col1:
        if "synthetic_txs" not in st.session_state:
            st.session_state.synthetic_txs = _generate_synthetic_transactions()

        selected_tx = st.selectbox(
            "Choose a transaction to analyze:",
            options=st.session_state.synthetic_txs,
            format_func=lambda x: (
                f"Transaction #{st.session_state.synthetic_txs.index(x) + 1} — "
                f"${x['Amount']:,.2f}"
            ),
        )

    with col2:
        if st.button("🔍 Analyze", use_container_width=True, type="primary"):
            st.session_state.analyze_tx = selected_tx
            # Clear previous results
            st.session_state.pop("predict_result", None)
            st.session_state.pop("explain_result", None)
            st.session_state.pop("similar_result", None)

    # ─── Analysis Results ─────────────────────────────────────────────
    if "analyze_tx" in st.session_state:
        tx = st.session_state.analyze_tx

        # ─── Real API Calls ──────────────────────────────────────────
        if "predict_result" not in st.session_state:
            result = api_call_with_spinner(
                "predict",
                tx,
                spinner_text="Running fraud prediction...",
            )
            if result:
                st.session_state.predict_result = result

        if (
            "explain_result" not in st.session_state
            and "predict_result" in st.session_state
        ):
            explain_result = api_call_with_spinner(
                "explain",
                tx,
                spinner_text="Computing SHAP explanation...",
            )
            if explain_result:
                st.session_state.explain_result = explain_result

        if (
            "similar_result" not in st.session_state
            and "predict_result" in st.session_state
        ):
            similar_result = api_call_with_spinner(
                "get_similar_cases",
                tx,
                spinner_text="Retrieving similar cases...",
            )
            if similar_result:
                st.session_state.similar_result = similar_result

        # ─── Display Results ────────────────────────────────────────
        pred = st.session_state.get("predict_result")
        if not pred:
            st.info("No prediction results yet. Click 'Analyze' to start.")
            return

        st.markdown("---")

        # Top-level verdict
        is_fraud = pred.get("is_fraud", False)
        prob = pred.get("fraud_probability", 0.0)
        verdict_color = "#ff6b6b" if is_fraud else "#38ef7d"
        verdict_text = "FRAUD FLAGGED" if is_fraud else "CLEARED"

        st.markdown(
            f"""
        <div style="
            background: #1a1a2e;
            border: 1px solid {verdict_color};
            border-left: 4px solid {verdict_color};
            border-radius: 8px;
            padding: 16px;
            margin: 8px 0;
        ">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div>
                    <span style="color: {verdict_color}; font-size: 18px; font-weight: 700;">
                        {verdict_text}
                    </span>
                    <span style="color: #a0a0a0; margin-left: 12px;">
                        Probability: {prob:.1%} | 
                        Amount: ${tx.get("Amount", 0):,.2f}
                    </span>
                </div>
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # ─── Two-Column Layout: SHAP | Narrative + Similar ───────────
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("<h3>📊 SHAP Analysis</h3>", unsafe_allow_html=True)
            explain = st.session_state.get("explain_result", {})
            shap_vals = explain.get("shap_values", {})

            if shap_vals:
                shap_df = pd.DataFrame(
                    [{"feature": k, "shap_value": v} for k, v in shap_vals.items()]
                ).sort_values("shap_value", key=abs, ascending=True)

                fig = px.bar(
                    shap_df.tail(10),
                    x="shap_value",
                    y="feature",
                    orientation="h",
                    color="shap_value",
                    color_continuous_scale=["#38ef7d", "#667eea", "#ff6b6b"],
                    title="Feature Contributions",
                    labels={"shap_value": "SHAP Value", "feature": ""},
                )
                fig.update_layout(
                    plot_bgcolor="#1a1a2e",
                    paper_bgcolor="#0f0f1a",
                    font_color="#e0e0e0",
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No SHAP values returned from API.")

            # Feature values table
            st.markdown("<h4>Feature Values (Top 15)</h4>", unsafe_allow_html=True)
            features_df = pd.DataFrame(
                [
                    {"Feature": f"V{i}", "Value": tx.get(f"V{i}", 0)}
                    for i in range(1, 16)
                ]
            )
            st.dataframe(features_df, use_container_width=True, hide_index=True)

        with col2:
            # LLM Narrative
            st.markdown("<h3>📝 Analyst Narrative</h3>", unsafe_allow_html=True)
            narrative = explain.get("narrative", "")
            if narrative:
                st.markdown(
                    f"""
                <div style="
                    background: #1a1a2e;
                    border: 1px solid #2a2a3e;
                    border-radius: 8px;
                    padding: 16px;
                    min-height: 120px;
                ">
                    <p style="color: #e0e0e0; font-size: 14px; line-height: 1.6;">
                        {narrative}
                    </p>
                </div>
                """,
                    unsafe_allow_html=True,
                )
            else:
                st.info("LLM narrative unavailable. Set ANTHROPIC_API_KEY to enable.")

            # Similar Cases (RAG)
            st.markdown("<h3>🔗 Similar Historical Cases</h3>", unsafe_allow_html=True)
            similar = st.session_state.get("similar_result", {})
            cases = similar.get("similar_cases", [])
            pagination = similar.get("pagination", {})

            for case in cases:
                outcome = case.get("actual_outcome", "unknown")
                color = "#3a1a1a" if outcome == "confirmed_fraud" else "#1a3a2a"
                label = (
                    "🔴 Confirmed Fraud"
                    if outcome == "confirmed_fraud"
                    else "🟢 False Positive"
                )
                st.markdown(
                    f"""
                <div style="
                    background: {color};
                    border: 1px solid {"#ff6b6b33" if outcome == "confirmed_fraud" else "#38ef7d33"};
                    border-radius: 8px;
                    padding: 10px 12px;
                    margin: 4px 0;
                ">
                    <span style="color: #e0e0e0; font-weight: 600;">{label}</span>
                    <span style="color: #a0a0a0; margin-left: 8px;">
                        Similarity: {case.get("similarity_score", 0):.2%}
                    </span>
                </div>
                """,
                    unsafe_allow_html=True,
                )

            if not cases:
                st.caption("No similar cases found.")

            if pagination.get("has_more"):
                st.caption(f"🔄 {pagination.get('total', 0)} total cases available")

        # Business Impact Summary
        st.markdown("---")
        st.markdown("<h3>💰 Business Impact</h3>", unsafe_allow_html=True)
        b1, b2, b3, b4 = st.columns(4)
        biz = pred.get("business_impact", {})
        with b1:
            metric_card(
                "Estimated Loss",
                f"${biz.get('estimated_loss', 0):,.0f}",
                icon="⚠️",
                color="#ff6b6b",
            )
        with b2:
            metric_card(
                "Review Cost",
                f"${biz.get('review_cost', 5.0):,.2f}",
                icon="💰",
                color="#f1c40f",
            )
        with b3:
            metric_card(
                "Anomaly Score",
                f"{pred.get('anomaly_score', 0):.2%}",
                icon="📊",
                color="#667eea",
            )
        with b4:
            metric_card(
                "Action",
                biz.get("action", "Review"),
                icon="🎯",
                color="#38ef7d",
            )
