"""Model governance tab functions — extracted from model_governance.py."""

from __future__ import annotations

import json
import streamlit as st
from typing import Any
def _show_pending_tab() -> None:
    """Show pending candidates with promote/reject actions."""
    client = get_api_client()

    # ─── Summary Stats ──────────────────────────────────────────────
    try:
        all_candidates = client.get_candidates(limit=100)
        pending_count = all_candidates.get("pending", 0)
        promoted_count = all_candidates.get("promoted", 0)
        rejected_count = all_candidates.get("rejected", 0)
        total = all_candidates.get("total", 0)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            metric_card(
                "Total Candidates",
                str(total),
                icon="📦",
                color="#667eea",
            )
        with col2:
            metric_card(
                "Pending Review",
                str(pending_count),
                icon="⏳",
                color="#f1c40f",
            )
        with col3:
            metric_card(
                "Promoted",
                str(promoted_count),
                icon="✅",
                color="#38ef7d",
            )
        with col4:
            metric_card(
                "Rejected",
                str(rejected_count),
                icon="❌",
                color="#ff6b6b",
            )

        # ─── Filter Controls ────────────────────────────────────────
        filter_col, refresh_col = st.columns([3, 1])
        with filter_col:
            status_filter = st.selectbox(
                "Filter by status",
                options=["candidate", "promoted", "rejected", None],
                format_func=lambda x: "All Candidates" if x is None else x.capitalize(),
                key="gov_status_filter",
            )
        with refresh_col:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()

        # ─── Fetch Candidates ───────────────────────────────────────
        if status_filter is not None:
            candidates = client.get_candidates(status_filter=status_filter)
        else:
            candidates = all_candidates

        candidate_list = candidates.get("candidates", [])

        if not candidate_list:
            st.info(
                "✨ No model candidates found. "
                "Candidates appear here after the automated retraining "
                "trigger runs the training pipeline."
            )
            return

        # ─── Render Each Candidate ──────────────────────────────────
        for i, cand in enumerate(candidate_list):
            _render_candidate_card(client, cand, i)

    except FraudLensAPIError as e:
        st.error(f"❌ API Error: {e}")
    except (ValueError, KeyError) as e:
        st.error(f"❌ Unexpected error: {e}")


def _render_candidate_card(client: Any, cand: dict[str, Any], index: int) -> None:
    """Render a single candidate as an expandable card with actions."""
    version = cand.get("model_version", "unknown")
    trigger = cand.get("trigger", "unknown")
    trigger_detail = cand.get("trigger_detail", "")
    status = cand.get("status", "candidate")
    pr_auc = cand.get("pr_auc")
    f1 = cand.get("f1_score")
    precision = cand.get("precision")
    recall = cand.get("recall")
    cand.get("threshold")
    created_at = cand.get("created_at", "")
    mlflow_run_id = cand.get("mlflow_run_id")

    # Fetch comparison data
    production_data = None
    is_pending = status == "candidate"

    if is_pending:
        try:
            compare = client.compare_candidate(version)
            production_data = compare.get("current_production")
            compare.get("metrics_delta")
        except FraudLensAPIError:
            pass

    # ─── Expandable Card ────────────────────────────────────────────
    status_color = CANDIDATE_COLORS.get(status, {}).get("fg", "#a0a0a0")
    border_color = CANDIDATE_COLORS.get(status, {}).get("border", "#2a2a3e")
    trigger_color = TRIGGER_COLORS.get(trigger, "#a0a0a0")

    expand_label = (
        f"**{version}** — "
        f"{_status_chip_html(status)} "
        f"{_trigger_chip_html(trigger)}"
        f"{'  🎯 PR-AUC: ' + f'{pr_auc:.4f}' if pr_auc else ''}"
    )

    with st.expander(expand_label, expanded=is_pending):
        # ─── Two-column layout ──────────────────────────────────────
        meta_col, metrics_col = st.columns([1, 2])

        with meta_col:
            st.markdown(
                f"""
            <div style="background:#1a1a2e;border:1px solid {border_color};border-radius:8px;padding:12px;">
                <h4 style="color:#e0e0e0;margin:0 0 8px 0;">{version}</h4>
                <table style="width:100%;font-size:13px;">
                    <tr><td style="color:#a0a0a0;">Trigger</td>
                        <td style="color:{trigger_color};font-weight:600;">{trigger.replace("_", " ").title()}</td></tr>
                    <tr><td style="color:#a0a0a0;">Detail</td>
                        <td style="color:#e0e0e0;">{trigger_detail or "—"}</td></tr>
                    <tr><td style="color:#a0a0a0;">Status</td>
                        <td style="color:{status_color};">{status.title()}</td></tr>
                    <tr><td style="color:#a0a0a0;">Created</td>
                        <td style="color:#e0e0e0;">{created_at[:10] if created_at else "—"}</td></tr>
                    <tr><td style="color:#a0a0a0;">MLflow Run</td>
                        <td style="color:#e0e0e0;font-size:11px;">{mlflow_run_id or "—"}</td></tr>
                </table>
            </div>
            """,
                unsafe_allow_html=True,
            )

        with metrics_col:
            # ─── Metrics Grid ───────────────────────────────────────
            st.markdown("<div style='display:flex;gap:8px;'>", unsafe_allow_html=True)
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(
                    _delta_html(
                        "PR-AUC",
                        pr_auc,
                        production_data.get("pr_auc") if production_data else None,
                    ),
                    unsafe_allow_html=True,
                )
            with m2:
                st.markdown(
                    _delta_html(
                        "F1",
                        f1,
                        production_data.get("f1_score") if production_data else None,
                    ),
                    unsafe_allow_html=True,
                )
            with m3:
                st.markdown(
                    _delta_html(
                        "Precision",
                        precision,
                        production_data.get("precision") if production_data else None,
                    ),
                    unsafe_allow_html=True,
                )
            with m4:
                st.markdown(
                    _delta_html(
                        "Recall",
                        recall,
                        production_data.get("recall") if production_data else None,
                    ),
                    unsafe_allow_html=True,
                )

            # ─── Production Model Info ──────────────────────────────
            if production_data:
                prod_version = production_data.get("model_version", "unknown")
                st.caption(f"📊 Comparing against production model: **{prod_version}**")

            # ─── Action Buttons (only for pending candidates) ───────
            if is_pending:
                st.markdown("<br>", unsafe_allow_html=True)
                _action_col1, action_col2, action_col3 = st.columns([2, 1, 1])

                with action_col2:
                    promote_key = f"promote_{version}_{index}"
                    if st.button(
                        "✅ Promote to Production",
                        key=promote_key,
                        use_container_width=True,
                        type="primary",
                    ):
                        _handle_promote(client, version)

                with action_col3:
                    reject_key = f"reject_{version}_{index}"
                    if st.button(
                        "❌ Reject",
                        key=reject_key,
                        use_container_width=True,
                    ):
                        _handle_reject(client, version)


def _handle_promote(client: Any, version: str) -> None:
    """Handle promote action with confirmation and feedback."""
    with st.spinner(f"Promoting {version} to production..."):
        try:
            result = client.promote_candidate(version)
            if result.get("success"):
                msg = result.get("message", f"Model {version} promoted successfully.")
                st.success(f"✅ {msg}")
                # Signal re-fetch on next render
                st.session_state["gov_force_refresh"] = True
                st.rerun()
            else:
                st.error(
                    f"❌ Promotion failed: {result.get('message', 'Unknown error')}"
                )
        except FraudLensAPIError as e:
            if e.status_code == 409:
                st.warning(f"⚠️ Candidate already processed: {e}")
            else:
                st.error(f"❌ Promotion failed: {e}")
        except (ValueError, KeyError) as e:
            st.error(f"❌ Unexpected error: {e}")


def _handle_reject(client: Any, version: str) -> None:
    """Handle reject action with confirmation and feedback."""
    with st.spinner(f"Rejecting {version}..."):
        try:
            result = client.reject_candidate(version)
            if result.get("success"):
                st.info(f"📋 Candidate {version} rejected.")
                st.session_state["gov_force_refresh"] = True
                st.rerun()
            else:
                st.error(
                    f"❌ Rejection failed: {result.get('message', 'Unknown error')}"
                )
        except FraudLensAPIError as e:
            if e.status_code == 409:
                st.warning(f"⚠️ Candidate already processed: {e}")
            else:
                st.error(f"❌ Rejection failed: {e}")
        except (ValueError, KeyError) as e:
            st.error(f"❌ Unexpected error: {e}")


# Tab: History


def _show_history_tab() -> None:
    """Show history of promoted and rejected candidates."""
    client = get_api_client()

    try:
        promoted = client.get_candidates(status_filter="promoted", limit=50)
        rejected = client.get_candidates(status_filter="rejected", limit=50)

        promoted_list = promoted.get("candidates", [])
        rejected_list = rejected.get("candidates", [])

        if not promoted_list and not rejected_list:
            st.info("No promotion or rejection history yet.")
            return

        # ─── Promoted History ───────────────────────────────────────
        if promoted_list:
            st.markdown("<h3>✅ Promoted to Production</h3>", unsafe_allow_html=True)
            for p in promoted_list:
                v = p.get("model_version", "?")
                t = p.get("trigger", "?")
                pa = p.get("pr_auc", "—")
                pt = (p.get("promoted_at") or p.get("created_at", ""))[:10]
                st.markdown(
                    f"""
                <div style="background:#1a3a2a;border:1px solid #38ef7d33;border-radius:8px;padding:10px 14px;margin:4px 0;">
                    <span style="color:#38ef7d;font-weight:600;">{v}</span>
                    <span style="color:#a0a0a0;margin:0 12px;">triggered by {t}</span>
                    <span style="color:#e0e0e0;">PR-AUC: {pa}</span>
                    <span style="color:#555;float:right;">{pt}</span>
                </div>
                """,
                    unsafe_allow_html=True,
                )

        # ─── Rejected History ────────────────────────────────────────
        if rejected_list:
            st.markdown(
                "<h3 style='margin-top:24px;'>❌ Rejected</h3>", unsafe_allow_html=True
            )
            for r in rejected_list:
                v = r.get("model_version", "?")
                t = r.get("trigger", "?")
                pa = r.get("pr_auc", "—")
                ct = (r.get("created_at") or "")[:10]
                detail = r.get("trigger_detail", "")[:80]
                st.markdown(
                    f"""
                <div style="background:#3a1a1a;border:1px solid #ff6b6b33;border-radius:8px;padding:10px 14px;margin:4px 0;">
                    <span style="color:#ff6b6b;font-weight:600;">{v}</span>
                    <span style="color:#a0a0a0;margin:0 12px;">{t} · {detail}</span>
                    <span style="color:#e0e0e0;">PR-AUC: {pa}</span>
                    <span style="color:#555;float:right;">{ct}</span>
                </div>
                """,
                    unsafe_allow_html=True,
                )

    except FraudLensAPIError as e:
        st.error(f"❌ API Error: {e}")


# Tab: About


def _show_about_tab() -> None:
    """Show information about the model governance workflow."""
    st.markdown(
        """
    <div style="background:#1a1a2e;border:1px solid #2a2a3e;border-radius:8px;padding:20px;">

    <h3 style="color:#e0e0e0;">🏛️ Model Governance Workflow</h3>

    <p style="color:#a0a0a0;line-height:1.6;">
    The automated retraining pipeline monitors two conditions:
    </p>

    <div style="display:flex;gap:16px;margin:16px 0;">
        <div style="background:#1a1a2e;border:1px solid #ff6b6b44;border-radius:8px;padding:12px;flex:1;">
            <span style="color:#ff6b6b;font-size:18px;">📊</span>
            <h4 style="color:#e0e0e0;margin:4px 0;">Drift Trigger</h4>
            <p style="color:#a0a0a0;font-size:13px;">
            When feature distributions shift significantly (KS-test p < 0.01),
            the retraining pipeline is triggered.
            </p>
        </div>
        <div style="background:#1a1a2e;border:1px solid #f1c40f44;border-radius:8px;padding:12px;flex:1;">
            <span style="color:#f1c40f;font-size:18px;">💬</span>
            <h4 style="color:#e0e0e0;margin:4px 0;">Feedback Volume</h4>
            <p style="color:#a0a0a0;font-size:13px;">
            When N+ confirmed feedback labels accumulate, retraining is
            triggered to incorporate the new ground truth.
            </p>
        </div>
    </div>

    <h4 style="color:#e0e0e0;">No Auto-Promotion</h4>
    <p style="color:#a0a0a0;line-height:1.6;">
    The automated pipeline <strong>never auto-promotes</strong> models to production.
    Every candidate must be reviewed and approved by a human via this dashboard.
    This ensures that model quality is verified before serving traffic.
    </p>

    <h4 style="color:#e0e0e0;">Review Process</h4>
    <ol style="color:#a0a0a0;line-height:1.8;">
        <li><strong>Check metrics:</strong> Compare the candidate's PR-AUC, F1, Precision,
        and Recall against the current production model.</li>
        <li><strong>Review deltas:</strong> Green ▲ means the candidate improves on that
        metric; red ▼ means it's worse.</li>
        <li><strong>Promote:</strong> If metrics are satisfactory, click "Promote to
        Production" to swap traffic to the new model.</li>
        <li><strong>Reject:</strong> If the candidate is worse or unnecessary, click
        "Reject" to archive it.</li>
        <li><strong>Restart:</strong> After promotion, restart the API to load the new
        model artifact.</li>
    </ol>
    </div>
    """,
        unsafe_allow_html=True,
    )


# Demo Content (when no API key)


def _show_demo_content() -> None:
    """Show demo content when no admin API key is configured."""
    st.markdown("<h3>📋 Demo Preview</h3>", unsafe_allow_html=True)

    candidates = [
        {
            "model_version": "v20260722_143022",
            "trigger": "drift",
            "trigger_detail": "Drift trigger: 3 CRITICAL drift events in 7d (threshold: 3)",
            "pr_auc": 0.8821,
            "f1_score": 0.7082,
            "precision": 0.5841,
            "recall": 0.8995,
            "threshold": 0.0295,
            "status": "candidate",
            "created_at": "2026-07-22T14:30:22",
            "mlflow_run_id": "abc123def456",
        },
        {
            "model_version": "v20260721_091500",
            "trigger": "feedback_volume",
            "trigger_detail": "Feedback volume trigger: 150 new feedback labels (threshold: 100)",
            "pr_auc": 0.8805,
            "f1_score": 0.7049,
            "precision": 0.5802,
            "recall": 0.8970,
            "threshold": 0.0301,
            "status": "promoted",
            "created_at": "2026-07-21T09:15:00",
            "promoted_at": "2026-07-21T10:30:00",
        },
        {
            "model_version": "v20260720_162100",
            "trigger": "drift",
            "trigger_detail": "Drift trigger: 4 CRITICAL drift events in 7d (threshold: 3)",
            "pr_auc": 0.8650,
            "f1_score": 0.6901,
            "precision": 0.5620,
            "recall": 0.8900,
            "threshold": 0.0320,
            "status": "rejected",
            "created_at": "2026-07-20T16:21:00",
        },
    ]

    for cand in candidates:
        status = cand.get("status", "candidate")
        pr_auc = cand.get("pr_auc")
        is_pending = status == "candidate"
        pr_auc_str = f"  🎯 PR-AUC: {pr_auc:.4f}" if pr_auc else ""

        with st.expander(
            f"**{cand['model_version']}** — "
            f"{_status_chip_html(status)} "
            f"{_trigger_chip_html(cand['trigger'])}"
            f"{pr_auc_str}",
            expanded=is_pending,
        ):
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown(
                    _delta_html("PR-AUC", cand["pr_auc"], 0.8810),
                    unsafe_allow_html=True,
                )
            with m2:
                st.markdown(
                    _delta_html("F1", cand["f1_score"], 0.7068),
                    unsafe_allow_html=True,
                )
            with m3:
                st.markdown(
                    _delta_html("Precision", cand["precision"], 0.5828),
                    unsafe_allow_html=True,
                )
            with m4:
                st.markdown(
                    _delta_html("Recall", cand["recall"], 0.8980),
                    unsafe_allow_html=True,
                )

            st.caption(
                "📊 Comparing against production model: **XGBoost (0.8810 PR-AUC)**"
            )

            if is_pending:
                st.info(
                    "🔑 Set `FRAUDLENS_DASHBOARD_API_KEY` to enable promote/reject actions."
                )
