"""
FraudLens — Streamlit Dashboard

A production-grade fraud-ops monitoring tool with 4 pages:
1. Live Monitor — Real-time transaction simulation
2. Case Investigator — SHAP + LLM + RAG case analysis
3. Model Performance — Comparison charts and metrics
4. Analyst Copilot — AI-powered chat assistant
"""

import sys
from pathlib import Path

import streamlit as st

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Page config must be the first Streamlit command
st.set_page_config(
    page_title="FraudLens",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Inject dark theme
with open(Path(__file__).parent / "assets" / "theme.css", encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px;">
            <span style="font-size: 32px;">🛡️</span>
            <div>
                <span style="font-size: 22px; font-weight: 700; color: #f0f0f0;">FraudLens</span>
                <br>
                <span style="font-size: 12px; color: #667eea; font-weight: 500;">FRAUD DETECTION PLATFORM</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown(
        '<span style="color: #a0a0a0; font-size: 13px;">Navigation</span>',
        unsafe_allow_html=True,
    )

    # Custom page navigation
    pages = {
        "Live Monitor": "📡",
        "Case Investigator": "🔍",
        "Model Performance": "📊",
        "Model Governance": "🏛️",
        "Analyst Copilot": "🤖",
    }

    if "page" not in st.session_state:
        st.session_state.page = "Live Monitor"

    for page_name, icon in pages.items():
        selected = st.session_state.page == page_name
        btn_style = (
            "background: #2a2a3e; border-color: #667eea; color: #fff;"
            if selected
            else "background: transparent; border-color: transparent; color: #a0a0a0;"
        )
        if st.sidebar.button(
            f"{icon} {page_name}",
            key=f"nav_{page_name}",
            use_container_width=True,
        ):
            st.session_state.page = page_name
            st.rerun()

    if st.session_state.page != "Analyst Copilot":
        st.markdown("---")
        st.markdown(
            '<span style="color: #555; font-size: 12px;">⚙️ Simulation Controls</span>',
            unsafe_allow_html=True,
        )

    # ─── LLM Spend Today ────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        '<span style="color: #a0a0a0; font-size: 13px;">🤖 LLM Usage</span>',
        unsafe_allow_html=True,
    )
    try:
        from src.fraudlens.llm.cost_tracker import cost_tracker

        today = cost_tracker.get_today_summary()
        cost_color = "#ff6b6b" if today.total_cost_usd > 1.0 else "#38ef7d"
        st.markdown(
            f"""
        <div style="background:#1a1a2e;border:1px solid #2a2a3e;border-radius:8px;padding:10px 12px;margin:4px 0;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span style="color:#a0a0a0;font-size:12px;">Today's Spend</span>
                <span style="color:{cost_color};font-size:18px;font-weight:700;">
                    ${today.total_cost_usd:.4f}
                </span>
            </div>
            <div style="display:flex;justify-content:space-between;margin-top:6px;">
                <span style="color:#555;font-size:11px;">{
                today.total_calls
            } calls</span>
                <span style="color:#555;font-size:11px;">
                    {today.total_input_tokens + today.total_output_tokens:,} tokens
                </span>
            </div>
            <div style="margin-top:4px;">
                {
                " ".join(
                    f'<span style="background:#2a2a3e;color:#a0a0a0;padding:1px 6px;border-radius:4px;font-size:10px;margin:1px;">{m} ${c:.4f}</span>'
                    for m, c in sorted(today.by_model.items())
                )
            }
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )
    except Exception:
        pass

    st.markdown("---")
    st.markdown(
        """
        <div style="font-size: 12px; color: #555; text-align: center;">
            Python, XGBoost, SHAP, FastAPI, Streamlit
        </div>
        """,
        unsafe_allow_html=True,
    )

# Page Router
page = st.session_state.page

if page == "Live Monitor":
    from app.pages.live_monitor import show

    show()
elif page == "Case Investigator":
    from app.pages.case_investigator import show

    show()
elif page == "Model Performance":
    from app.pages.model_performance import show

    show()
elif page == "Model Governance":
    from app.pages.model_governance import show

    show()
elif page == "Analyst Copilot":
    from app.pages.analyst_copilot import show

    show()
