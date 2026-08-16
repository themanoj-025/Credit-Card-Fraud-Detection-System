"""
Reusable UI Components for FraudLens Dashboard.

Custom metric cards with icons, rounded corners, and delta indicators.
Built to match the dark-mode fraud-ops tool aesthetic.
"""

import streamlit as st


def metric_card(
    label: str,
    value: str,
    delta: str | None = None,
    icon: str = "",
    color: str = "#38ef7d",
    help_text: str | None = None,
) -> None:
    """
    Render a styled metric card with icon, value, and optional delta.

    Args:
        label: Short label for the metric
        value: Primary value to display
        delta: Optional change indicator string
        icon: Emoji or icon prefix
        color: Accent color for the card border/highlight
        help_text: Optional tooltip text
    """
    card_html = f"""
    <div style="
        background: #1a1a2e;
        border: 1px solid {color}33;
        border-left: 4px solid {color};
        border-radius: 8px;
        padding: 16px;
        margin: 4px 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    ">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <span style="color: #a0a0a0; font-size: 13px; font-weight: 500;">
                {icon} {label}
            </span>
            {'<span style="color: #555; cursor: help;" title="' + help_text + '">ⓘ</span>' if help_text else ""}
        </div>
        <div style="
            color: {"#e0e0e0" if "red" not in color else "#ff6b6b"};
            font-size: 28px;
            font-weight: 700;
            margin-top: 4px;
            font-family: 'Inter', sans-serif;
        ">
            {value}
        </div>
        {f'<div style="color: {color}; font-size: 13px; margin-top: 2px;">{delta}</div>' if delta else ""}
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


def status_chip(status: str) -> str:
    """
    Render a colored status chip (Cleared / Under Review / Flagged).

    Args:
        status: One of "CLEARED", "UNDER_REVIEW", "FLAGGED"

    Returns:
        HTML string for the chip
    """
    colors = {
        "CLEARED": {"bg": "#1a3a2a", "fg": "#38ef7d"},
        "UNDER_REVIEW": {"bg": "#3a3a1a", "fg": "#f1c40f"},
        "FLAGGED": {"bg": "#3a1a1a", "fg": "#ff6b6b"},
        "FRAUD": {"bg": "#3a1a1a", "fg": "#ff6b6b"},
        "LEGITIMATE": {"bg": "#1a3a2a", "fg": "#38ef7d"},
    }
    c = colors.get(status.upper(), {"bg": "#2a2a2a", "fg": "#a0a0a0"})
    return f"""
    <span style="
        background: {c["bg"]};
        color: {c["fg"]};
        padding: 3px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
        font-family: 'Inter', sans-serif;
    ">{status}</span>
    """


def drift_banner(score: float, details: str = "") -> str:
    """
    Generate a drift alert banner HTML.

    Args:
        score: Drift score between 0 and 1
        details: Comma-separated list of drifted features with p-values

    Returns:
        HTML string for the banner
    """
    explanation = (
        '<p style="color: #a0a0a0; font-size: 12px; margin-top: 6px;">'
        "<strong>What is drift?</strong> When transaction patterns change over time, "
        "the model's predictions may become less accurate. Drift detection compares "
        "incoming transactions to the training data using a KS-test. "
        "If the distribution of a feature shifts significantly (p < 0.05), it's flagged. "
        "This helps you decide when to retrain the model.</p>"
    )

    if score > 0.3:
        return f"""
        <div style="
            background: #3a1a1a;
            border: 1px solid #ff6b6b;
            border-radius: 8px;
            padding: 12px 16px;
            margin: 8px 0;
            color: #ff6b6b;
            font-weight: 600;
        ">
            🔴 <strong>Data Drift Detected</strong> (score: {score:.2f}) — Model retraining is recommended
            <br><span style="font-weight: 400; font-size: 13px; color: #ff6b6bcc;">{details}</span>
            {explanation}
        </div>
        """
    elif score > 0.1:
        return f"""
        <div style="
            background: #3a3a1a;
            border: 1px solid #f1c40f;
            border-radius: 8px;
            padding: 12px 16px;
            margin: 8px 0;
            color: #f1c40f;
            font-weight: 600;
        ">
            🟡 <strong>Mild Drift Detected</strong> (score: {score:.2f}) — Monitor closely
            <br><span style="font-weight: 400; font-size: 13px; color: #f1c40fcc;">{details}</span>
            {explanation}
        </div>
        """
    return ""
