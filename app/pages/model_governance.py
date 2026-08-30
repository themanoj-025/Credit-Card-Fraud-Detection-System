"""
Model Governance Page

Shows pending model candidates from the automated retraining pipeline,
their metrics vs current production model, and lets analysts promote
or reject candidates directly from the UI.

Key features:
- Pending candidates table with metrics and trigger reason
- Compare candidate vs production (delta indicators)
- Promote / Reject buttons with confirmation
- History of past promotions and rejections
"""

import os
from typing import Any

import streamlit as st

from app.api_client import FraudLensAPIError, get_api_client
from app.components.metric_cards import metric_card

# Constants

CANDIDATE_COLORS = {
    "candidate": {"bg": "#1a2a3a", "fg": "#667eea", "border": "#667eea33"},
    "promoted": {"bg": "#1a3a2a", "fg": "#38ef7d", "border": "#38ef7d33"},
    "rejected": {"bg": "#3a1a1a", "fg": "#ff6b6b", "border": "#ff6b6b33"},
}

TRIGGER_COLORS = {
    "drift": "#ff6b6b",
    "feedback_volume": "#f1c40f",
}


def _status_chip_html(status: str) -> str:
    """Render a status chip for candidate status."""
    c = CANDIDATE_COLORS.get(status, {"bg": "#2a2a2a", "fg": "#a0a0a0"})
    label = status.capitalize()
    return f"""
    <span style="
        background: {c["bg"]};
        color: {c["fg"]};
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
    ">{label}</span>
    """


def _trigger_chip_html(trigger: str) -> str:
    """Render a chip for the trigger type."""
    color = TRIGGER_COLORS.get(trigger, "#a0a0a0")
    return f"""
    <span style="
        background: #1a1a2e;
        color: {color};
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 12px;
        font-weight: 600;
        border: 1px solid {color}44;
    ">{trigger.replace("_", " ").title()}</span>
    """


def _delta_html(
    label: str,
    candidate_val: float | None,
    prod_val: float | None,
    fmt: str = ".4f",
) -> str:
    """Render a metrics delta with color-coded change indicator."""
    if candidate_val is None or prod_val is None:
        delta = None
    else:
        delta = candidate_val - prod_val

    val_str = f"{candidate_val:{fmt}}" if candidate_val is not None else "—"
    if delta is None:
        delta_str = "<span style='color:#555;font-size:11px;'>N/A</span>"
    elif delta > 0.001:
        delta_str = (
            f"<span style='color:#38ef7d;font-size:11px;'>▲ +{delta:{fmt}}</span>"
        )
    elif delta < -0.001:
        delta_str = (
            f"<span style='color:#ff6b6b;font-size:11px;'>▼ {delta:{fmt}}</span>"
        )
    else:
        delta_str = (
            f"<span style='color:#a0a0a0;font-size:11px;'>— {delta:{fmt}}</span>"
        )

    return f"""
    <div style="background:#1a1a2e;border:1px solid #2a2a3e;border-radius:6px;padding:8px 12px;text-align:center;">
        <div style="color:#a0a0a0;font-size:11px;margin-bottom:2px;">{label}</div>
        <div style="color:#e0e0e0;font-size:18px;font-weight:700;">{val_str}</div>
        <div>{delta_str}</div>
    </div>
    """


def _has_api_key() -> bool:
    """Check if dashboard API key is configured for admin operations."""
    return bool(os.environ.get("FRAUDLENS_DASHBOARD_API_KEY", ""))


# Main Page


def show() -> None:
    """Render the Model Governance page."""
    st.markdown(
        "<h1>🏛️ Model Governance</h1>"
        "<p style='color: #a0a0a0; margin-top: -12px;'>"
        "Review, compare, and promote model candidates from the automated "
        "retraining pipeline</p>",
        unsafe_allow_html=True,
    )

    # ─── API Key Check ───────────────────────────────────────────────────
    if not _has_api_key():
        st.warning(
            "⚠️ **Admin API key not configured.**\n\n"
            "To manage model candidates, set the "
            "`FRAUDLENS_DASHBOARD_API_KEY` environment variable with an "
            "admin-level API key.\n\n"
            "Generate a key via the API:\n"
            "```bash\n"
            "curl -X POST http://localhost:8000/v1/auth/keys \\\n"
            '  -H "X-API-Key: your-admin-key" \\\n'
            '  -H "Content-Type: application/json" \\\n'
            '  -d \'{"role": "admin"}\'\n'
            "```\n\n"
            "Then set `FRAUDLENS_DASHBOARD_API_KEY=fl_...` in your `.env` file.",
        )
        # Still show demo content
        _show_demo_content()
        return

    # ─── Tab Layout ──────────────────────────────────────────────────────
    tab_candidates, tab_history, tab_about = st.tabs(
        ["📋 Pending Candidates", "📜 History", "ℹ️ About"]
    )

    with tab_candidates:
        _show_pending_tab()

    with tab_history:
        _show_history_tab()

    with tab_about:
        _show_about_tab()


# Tab: Pending Candidates



from app.pages.governance_tabs import (  # noqa: E402
    _show_pending_tab,
    _render_candidate_card,
    _handle_promote,
    _handle_reject,
    _show_history_tab,
    _show_about_tab,
    _show_demo_content,
)
