"""
Live Monitor Page

Real-time transaction simulation with styled cards, live-updating metrics,
drift detection alerts, and a rolling count of flags over the last N transactions.
"""

import random
import time

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

from app.api_client import get_api_client
from app.components.metric_cards import drift_banner, metric_card
from src.fraudlens.config import (
    DRIFT_ALERT_WINDOW,
    MAX_TRANSACTION_HISTORY,
    SIMULATION_BATCH_SIZE,
    SIMULATION_FRAUD_RATE,
)

# Drift detection (lazy-loaded)
_DRIFT_DETECTOR = None


def _get_drift_detector():
    """Get or create the drift detector with reference data."""
    global _DRIFT_DETECTOR
    if _DRIFT_DETECTOR is not None:
        return _DRIFT_DETECTOR

    # Generate a reference distribution from synthetic data matching training
    # In production, this would load the actual training data from disk
    try:
        from src.fraudlens.data.loaders import DataLoader

        loader = DataLoader()
        df = loader.load()
        # Use a sample as reference
        ref_data = df[["V1", "V4", "V14", "Amount"]].sample(
            min(10000, len(df)), random_state=42
        )

        from src.fraudlens.monitoring.drift import DriftDetector

        _DRIFT_DETECTOR = DriftDetector(
            reference_data=ref_data,
            feature_names=["V1", "V4", "V14", "Amount"],
            significance_level=0.05,
        )
        return _DRIFT_DETECTOR
    except (FileNotFoundError, Exception):
        # Fallback: create detector with synthetic reference
        from src.fraudlens.monitoring.drift import DriftDetector

        ref = pd.DataFrame({f: np.random.randn(5000) for f in ["V1", "V4", "V14"]})
        ref["Amount"] = np.random.exponential(100, 5000)
        _DRIFT_DETECTOR = DriftDetector(
            reference_data=ref,
            feature_names=["V1", "V4", "V14", "Amount"],
            significance_level=0.05,
        )
        return _DRIFT_DETECTOR


def _init_session_state() -> None:
    """Initialize session state for the live monitor."""
    if "transactions" not in st.session_state:
        st.session_state.transactions = []
    if "running" not in st.session_state:
        st.session_state.running = False
    if "fraud_caught" not in st.session_state:
        st.session_state.fraud_caught = 0
    if "fraud_missed" not in st.session_state:
        st.session_state.fraud_missed = 0
    if "total_review_cost" not in st.session_state:
        st.session_state.total_review_cost = 0.0
    if "total_transactions" not in st.session_state:
        st.session_state.total_transactions = 0
    if "drift_score" not in st.session_state:
        st.session_state.drift_score = 0.0
    if "drift_details" not in st.session_state:
        st.session_state.drift_details = ""
    if "last_drift_check" not in st.session_state:
        st.session_state.last_drift_check = 0


def _generate_transaction() -> dict[str, float]:
    """Generate a synthetic transaction for simulation."""
    tx = {f"V{i}": round(random.gauss(0, 1), 4) for i in range(1, 29)}
    tx["Time"] = round(random.uniform(0, 172800), 2)
    tx["Amount"] = round(random.uniform(1, 5000), 2)

    # Occasionally inject fraud-like patterns
    if random.random() < SIMULATION_FRAUD_RATE:
        tx["V14"] = round(random.uniform(-8, -3), 4)
        tx["V4"] = round(random.uniform(3, 8), 4)
        tx["Amount"] = round(random.uniform(200, 3000), 2)

    return tx


def _predict_transaction(tx: dict[str, float]) -> dict | None:
    """Send transaction to API for prediction using shared client."""
    try:
        client = get_api_client()
        return client.predict(tx)
    except (requests.RequestException, ValueError):
        return None


def _update_metrics(result: dict) -> None:
    """Update business metrics based on prediction result."""
    st.session_state.total_transactions += 1
    if result["is_fraud"]:
        st.session_state.fraud_caught += 150.0
        st.session_state.total_review_cost += 5.0


def _run_drift_check(batch_transactions: list[dict]) -> None:
    """Run drift detection on accumulated transactions and update session state."""
    if not batch_transactions:
        return

    detector = _get_drift_detector()
    batch_df = pd.DataFrame(batch_transactions)

    # Only check features we're monitoring
    monitored = [c for c in ["V1", "V4", "V14", "Amount"] if c in batch_df.columns]
    if not monitored:
        return

    try:
        results = detector.detect_drift(batch_df[monitored])
        score = detector.get_overall_drift_score(results)
        st.session_state.drift_score = score

        # Build details string
        critical = [f for f, r in results.items() if r["alert"] == "CRITICAL"]
        warnings = [f for f, r in results.items() if r["alert"] == "WARNING"]

        parts = []
        if critical:
            parts.append(f"🔴 Critical: {', '.join(critical)}")
        if warnings:
            parts.append(f"🟡 Warning: {', '.join(warnings)}")

        drifts = ", ".join(
            f"{f} (p={r['p_value']:.4f})"
            for f, r in results.items()
            if r["alert"] in ("CRITICAL", "WARNING")
        )
        st.session_state.drift_details = drifts if drifts else "All features stable"

        st.session_state.last_drift_check = st.session_state.total_transactions
    except (ValueError, KeyError, TypeError):
        pass


def show() -> None:
    """Render the Live Monitor page."""
    _init_session_state()

    st.markdown(
        "<h1>📡 Live Monitor</h1>"
        "<p style='color: #a0a0a0; margin-top: -12px;'>"
        "Real-time transaction monitoring with fraud detection and drift alerts</p>",
        unsafe_allow_html=True,
    )

    # ─── Controls ────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    with col1:
        batch_size = st.slider("Batch Size", 1, 50, SIMULATION_BATCH_SIZE)
    with col2:
        delay = st.slider("Delay (s)", 0.1, 2.0, 0.5)
    with col3:
        if st.button(
            "▶️ Start" if not st.session_state.running else "⏹ Stop",
            use_container_width=True,
        ):
            st.session_state.running = not st.session_state.running
    with col4:
        if st.button("🔄 Reset", use_container_width=True):
            st.session_state.transactions = []
            st.session_state.fraud_caught = 0
            st.session_state.fraud_missed = 0
            st.session_state.total_review_cost = 0.0
            st.session_state.total_transactions = 0
            st.session_state.drift_score = 0.0
            st.session_state.drift_details = ""
            st.session_state.last_drift_check = 0
            st.rerun()

    # ─── Drift Alert ─────────────────────────────────────────────────
    drift_placeholder = st.empty()
    score = st.session_state.drift_score
    if score > 0:
        drift_placeholder.markdown(
            drift_banner(score, st.session_state.drift_details),
            unsafe_allow_html=True,
        )

    # ─── Top Metrics ─────────────────────────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        metric_card("Transactions", str(st.session_state.total_transactions), icon="📊")
    with m2:
        metric_card(
            "Fraud Caught",
            f"${st.session_state.fraud_caught:,.0f}",
            icon="🛑",
            color="#38ef7d",
        )
    with m3:
        metric_card(
            "Fraud Missed",
            f"${st.session_state.fraud_missed:,.0f}",
            icon="⚠️",
            color="#ff6b6b",
        )
    with m4:
        metric_card(
            "Review Costs",
            f"${st.session_state.total_review_cost:,.0f}",
            icon="💰",
            color="#f1c40f",
        )
    with m5:
        net = st.session_state.fraud_caught - st.session_state.total_review_cost
        metric_card("Net Benefit", f"${net:,.0f}", icon="✅", color="#38ef7d")

    # ─── Charts ──────────────────────────────────────────────────────
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        chart_placeholder = st.empty()

    with chart_col2:
        impact_placeholder = st.empty()

    # ─── Transaction Feed ────────────────────────────────────────────
    st.markdown("<h3>Recent Transactions</h3>", unsafe_allow_html=True)
    feed_placeholder = st.empty()

    # ─── Simulation Loop ─────────────────────────────────────────────
    if st.session_state.running:
        batch_txs = []
        for _ in range(batch_size):
            tx = _generate_transaction()
            result = _predict_transaction(tx)
            if result:
                _update_metrics(result)
                st.session_state.transactions.append(
                    {
                        "time": time.strftime("%H:%M:%S"),
                        "amount": f"${tx['Amount']:,.2f}",
                        "probability": f"{result['fraud_probability']:.1%}",
                        "status": result["decision"],
                        "is_fraud": result["is_fraud"],
                    }
                )
                batch_txs.append(tx)

            # Keep only recent history
            if len(st.session_state.transactions) > MAX_TRANSACTION_HISTORY:
                st.session_state.transactions = st.session_state.transactions[-200:]

        # Run drift check on cadence
        if (
            st.session_state.total_transactions - st.session_state.last_drift_check
            >= DRIFT_ALERT_WINDOW
        ):
            _run_drift_check(batch_txs)

        # ─── Update Charts ────────────────────────────────────────────────
        if st.session_state.transactions:
            # Probability distribution
            prob_vals = [
                float(t["probability"].rstrip("%")) / 100
                for t in st.session_state.transactions[-100:]
            ]
            fig1 = px.histogram(
                x=prob_vals,
                nbins=20,
                title="Fraud Probability Distribution (Last 100)",
                color_discrete_sequence=["#667eea"],
                labels={"x": "Fraud Probability"},
            )
            fig1.update_layout(
                plot_bgcolor="#1a1a2e",
                paper_bgcolor="#0f0f1a",
                font_color="#e0e0e0",
                showlegend=False,
            )
            chart_placeholder.plotly_chart(fig1, use_container_width=True)

            # Cumulative impact chart
            cum_caught = []
            cum_cost = []
            caught = 0
            cost = 0
            for t in st.session_state.transactions:
                if t["is_fraud"]:
                    caught += 150
                    cost += 5
                cum_caught.append(caught)
                cum_cost.append(cost)

            fig2 = go.Figure()
            fig2.add_trace(
                go.Scatter(
                    y=cum_caught,
                    name="Fraud Caught ($)",
                    line=dict(color="#38ef7d", width=2),
                    mode="lines",
                )
            )
            fig2.add_trace(
                go.Scatter(
                    y=cum_cost,
                    name="Review Costs ($)",
                    line=dict(color="#f1c40f", width=2),
                    mode="lines",
                )
            )
            fig2.update_layout(
                title="Cumulative Business Impact",
                plot_bgcolor="#1a1a2e",
                paper_bgcolor="#0f0f1a",
                font_color="#e0e0e0",
                hovermode="x unified",
            )
            impact_placeholder.plotly_chart(fig2, use_container_width=True)

        # ─── Update Feed ──────────────────────────────────────────────────
        recent = st.session_state.transactions[-20:][::-1]
        feed_html = "<div style='max-height: 400px; overflow-y: auto;'>"
        for t in recent:
            status_label = "🔴 FLAGGED" if t["is_fraud"] else "🟢 CLEARED"
            feed_html += f"""
            <div style="
                background: #1a1a2e;
                border: 1px solid {"#3a1a1a" if t["is_fraud"] else "#1a3a2a"};
                border-radius: 8px;
                padding: 8px 12px;
                margin: 4px 0;
                display: flex;
                justify-content: space-between;
                align-items: center;
            ">
                <span style="color: #a0a0a0;">{t["time"]}</span>
                <span style="color: #e0e0e0; font-weight: 600;">{t["amount"]}</span>
                <span style="color: #667eea;">{t["probability"]}</span>
                <span>{status_label}</span>
            </div>
            """
        feed_html += "</div>"
        feed_placeholder.markdown(feed_html, unsafe_allow_html=True)

        time.sleep(delay)
        st.rerun()
