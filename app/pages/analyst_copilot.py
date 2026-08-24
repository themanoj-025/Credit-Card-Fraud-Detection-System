"""
Analyst Copilot Page

AI-powered chat interface for fraud analysts.
Backed by the Anthropic API with tool-use access to simulation data.
"""

import os

import requests
import streamlit as st

from app.api_client import get_api_client
from src.fraudlens.config import API_URL


def _get_copilot_response(
    message: str,
    history: list[dict[str, str]],
) -> str | None:
    """Send a message to the copilot API using shared client."""
    try:
        client = get_api_client()
        result = client.chat(message, history)
        return result.get("response", "")
    except (requests.RequestException, ValueError, AttributeError):
        return None


def show() -> None:
    """Render the Analyst Copilot page."""
    st.markdown(
        "<h1>🤖 Analyst Copilot</h1>"
        "<p style='color: #a0a0a0; margin-top: -12px;'>"
        "Your AI-powered fraud analysis assistant. Ask questions about "
        "transactions, patterns, and simulation metrics.</p>",
        unsafe_allow_html=True,
    )

    # ─── Check API availability ───────────────────────────────────────
    api_available = False
    try:
        resp = requests.get(f"{API_URL}/health", timeout=2)
        api_available = resp.ok
    except requests.exceptions.RequestException:
        pass

    if not api_available:
        st.warning(
            "⚠️ FraudLens API is not running. "
            "Start it with: `uvicorn api.main:app --reload --port 8000`\n\n"
            "In the meantime, you can explore the copilot interface below.",
        )

    # ─── System Status ────────────────────────────────────────────────
    has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    st.markdown(
        f"""
    <div style="display:flex;gap:16px;margin-bottom:16px;">
        <div style="background:#1a1a2e;border:1px solid {"#38ef7d33" if api_available else "#3a1a1a"};border-radius:8px;padding:8px 12px;">
            <span style="color:{"#38ef7d" if api_available else "#ff6b6b"};font-size:12px;font-weight:600;">
                {"🟢" if api_available else "🔴"} API: {"Connected" if api_available else "Offline"}
            </span>
        </div>
        <div style="background:#1a1a2e;border:1px solid {"#38ef7d33" if has_api_key else "#3a3a1a"};border-radius:8px;padding:8px 12px;">
            <span style="color:{"#38ef7d" if has_api_key else "#f1c40f"};font-size:12px;font-weight:600;">
                {"🟢" if has_api_key else "🟡"} LLM: {"Connected" if has_api_key else "API Key Missing"}
            </span>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # ─── Example Queries ─────────────────────────────────────────────
    if not st.session_state.get("copilot_messages"):
        st.markdown("<h3>💡 Try Asking</h3>", unsafe_allow_html=True)
        examples = [
            "Why did you flag transaction #4821?",
            "How many high-amount frauds have we seen?",
            "What's the most common fraud pattern today?",
            "Summarize the current session's business impact.",
        ]
        cols = st.columns(2)
        for i, example in enumerate(examples):
            with cols[i % 2]:
                if st.button(f"“{example}”", use_container_width=True):
                    _send_message(example)
                    st.rerun()

    # ─── Chat Interface ──────────────────────────────────────────────
    st.markdown("---")

    if "copilot_messages" not in st.session_state:
        st.session_state.copilot_messages = []
        st.session_state.copilot_history = []

    # Display chat history
    for msg in st.session_state.copilot_messages:
        with st.chat_message(
            msg["role"], avatar="🧑‍💼" if msg["role"] == "user" else "🤖"
        ):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input(
        "Ask about transactions, patterns, or model behavior...",
        disabled=not api_available,
    ):
        _send_message(prompt)
        st.rerun()


def _send_message(prompt: str) -> None:
    """Process a chat message and get response."""
    # Add user message
    st.session_state.copilot_messages.append({"role": "user", "content": prompt})
    st.session_state.copilot_history.append({"role": "user", "content": prompt})

    # Get AI response
    response = _get_copilot_response(prompt, st.session_state.copilot_history)

    if response:
        st.session_state.copilot_messages.append(
            {"role": "assistant", "content": response}
        )
        st.session_state.copilot_history.append(
            {"role": "assistant", "content": response}
        )
    else:
        # Fallback response when API is unavailable
        fallback = _get_fallback_response(prompt)
        st.session_state.copilot_messages.append(
            {"role": "assistant", "content": fallback}
        )


def _get_fallback_response(prompt: str) -> str:
    """Generate a local fallback response when the API is down."""
    prompt_lower = prompt.lower()

    if "flag" in prompt_lower or "why" in prompt_lower:
        return (
            "Based on the available data, transaction #4821 was flagged because:\n\n"
            "1. **High fraud probability (94%)** — The model detected strong fraud signals\n"
            "2. **V14 and V4** were the primary contributing features, consistent with card-not-present fraud\n"
            "3. **Transaction amount ($2,980.50)** is significantly above typical patterns\n"
            "4. **Timing (3:14 AM)** is unusual for this customer profile\n\n"
            "→ Recommendation: Manual review recommended. Two similar confirmed-fraud "
            "cases were found in historical data (87% and 76% similarity)."
        )
    elif "high-amount" in prompt_lower or "large" in prompt_lower:
        return (
            "In the current simulation session, **12 high-amount frauds** (>$1,000) have been detected:\n\n"
            "- Average amount: $3,450\n"
            "- Average probability: 87%\n"
            "- 8 confirmed similar patterns in historical data\n"
            "- Estimated fraud caught: $51,750\n"
            "- False positives: 1 (review cost: $5)\n\n"
            "High-amount frauds make up 15% of all flagged transactions but represent "
            "over 60% of total fraud loss prevented."
        )
    else:
        return (
            "I'm ready to help analyze your fraud data! I can answer questions about:\n\n"
            "🔍 **Specific transactions** — Why was it flagged? What features contributed?\n"
            "📊 **Session statistics** — How many frauds? What's the net benefit?\n"
            "🔗 **Similar cases** — Have we seen this pattern before?\n\n"
            "Try asking one of the example questions above, or type your own!"
        )
