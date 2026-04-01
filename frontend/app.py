"""
Real Estate Advisory — Streamlit Frontend
Connects to FastAPI backend at BACKEND_URL (default http://localhost:8000)
"""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv
import requests
import streamlit as st

load_dotenv(Path(__file__).parent / ".env")
BACKEND = os.getenv("BACKEND_URL", "http://localhost:8000")

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RE Advisory",
    page_icon="🏘️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* Dark gradient background */
.stApp { background: linear-gradient(135deg, #0f0c29, #302b63, #24243e); }

/* Sidebar */
section[data-testid="stSidebar"] {
    background: rgba(255,255,255,0.04);
    border-right: 1px solid rgba(255,255,255,0.08);
}

/* Cards */
.card {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px;
    padding: 1.2rem 1.5rem;
    margin-bottom: 1rem;
    backdrop-filter: blur(10px);
}
.card-accent { border-left: 4px solid #7c3aed; }

/* Recommendation badge */
.badge {
    display: inline-block;
    padding: 0.3rem 1rem;
    border-radius: 999px;
    font-weight: 700;
    font-size: 0.9rem;
    letter-spacing: 0.05em;
}
.badge-buy    { background:#065f46; color:#6ee7b7; }
.badge-avoid  { background:#7f1d1d; color:#fca5a5; }
.badge-consider { background:#78350f; color:#fcd34d; }
.badge-needsmore { background:#1e3a5f; color:#93c5fd; }

/* Confidence bar */
.conf-bar-wrap { background:rgba(255,255,255,0.08); border-radius:999px; height:10px; }
.conf-bar { border-radius:999px; height:10px; background:linear-gradient(90deg,#7c3aed,#06b6d4); }

/* Agent cards */
.agent-header { display:flex; align-items:center; gap:0.5rem; margin-bottom:0.5rem; }
.agent-name { font-weight:600; font-size:1rem; }
.conf-pill {
    font-size:0.72rem; padding:0.15rem 0.55rem; border-radius:999px; font-weight:600;
}
.conf-high   { background:#065f46; color:#6ee7b7; }
.conf-medium { background:#78350f; color:#fcd34d; }
.conf-low    { background:#7f1d1d; color:#fca5a5; }

/* Disagree highlight */
.dissent-tag {
    font-size:0.72rem; background:rgba(239,68,68,0.2); color:#fca5a5;
    border:1px solid rgba(239,68,68,0.4); border-radius:6px; padding:0.1rem 0.4rem;
    margin-left:0.3rem;
}

/* Risk item */
.risk-item {
    background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.3);
    border-radius:8px; padding:0.35rem 0.8rem; margin-bottom:0.4rem; font-size:0.88rem;
}

/* Domain tag */
.domain-tag {
    display:inline-block; background:rgba(124,58,237,0.2); color:#c4b5fd;
    border:1px solid rgba(124,58,237,0.4); border-radius:999px;
    padding:0.15rem 0.55rem; font-size:0.75rem; margin-right:0.3rem; font-weight:500;
}

/* Follow-up button override */
div[data-testid="stButton"] > button {
    background: rgba(124,58,237,0.15) !important;
    color: #c4b5fd !important;
    border: 1px solid rgba(124,58,237,0.4) !important;
    border-radius: 999px !important;
    font-size: 0.82rem !important;
    padding: 0.25rem 0.8rem !important;
    transition: all 0.2s;
}
div[data-testid="stButton"] > button:hover {
    background: rgba(124,58,237,0.35) !important;
    border-color: #7c3aed !important;
}

/* Scrollable debate box */
.debate-box {
    background: rgba(0,0,0,0.2);
    border-radius: 10px;
    padding: 0.8rem 1rem;
    font-size: 0.85rem;
    max-height: 280px;
    overflow-y: auto;
    white-space: pre-wrap;
    line-height: 1.6;
    color: rgba(255,255,255,0.82);
}
.round-label {
    font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em;
    text-transform: uppercase; color: #7c3aed; margin-bottom: 0.3rem;
}

/* History row */
.history-row {
    background: rgba(255,255,255,0.04); border-radius: 10px;
    padding: 0.6rem 1rem; margin-bottom: 0.5rem; font-size: 0.85rem;
}
</style>
""",
    unsafe_allow_html=True,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _post(path: str, payload: dict) -> dict | None:
    try:
        r = requests.post(f"{BACKEND}{path}", json=payload, timeout=300)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Backend error: {e}")
        return None


def _get(path: str, params: dict | None = None) -> dict | None:
    try:
        r = requests.get(f"{BACKEND}{path}", params=params or {}, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Backend error: {e}")
        return None


def _badge(rec: str) -> str:
    cls = {
        "Buy": "badge-buy",
        "Avoid": "badge-avoid",
        "Consider": "badge-consider",
        "Needs more info": "badge-needsmore",
    }.get(rec, "badge-needsmore")
    return f'<span class="badge {cls}">{rec}</span>'


def _conf_pill(conf: str) -> str:
    cls = {"high": "conf-high", "medium": "conf-medium", "low": "conf-low"}.get(conf, "conf-medium")
    return f'<span class="conf-pill {cls}">{conf.upper()}</span>'


def _push_followup(q: str) -> None:
    st.session_state["query_input"] = q
    st.session_state["auto_submit"] = True


# ── Login screen ───────────────────────────────────────────────────────────────

def render_login() -> None:
    st.markdown(
        "<h1 style='text-align:center;font-size:2.6rem;font-weight:700;"
        "background:linear-gradient(90deg,#7c3aed,#06b6d4);-webkit-background-clip:text;"
        "-webkit-text-fill-color:transparent;'>🏘️ RE Advisory</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='text-align:center;color:rgba(255,255,255,0.55);margin-bottom:2rem;'>"
        "Multi-Agent Real Estate Advisory System · Powered by Open-Source LLMs</p>",
        unsafe_allow_html=True,
    )
    col = st.columns([1, 2, 1])[1]
    with col:
        with st.form("login_form"):
            username = st.text_input(
                "Username", placeholder="e.g. priya_investor", key="login_username"
            )
            submitted = st.form_submit_button("Enter Advisory Panel →", use_container_width=True)
        if submitted:
            if not username.strip():
                st.error("Please enter a username.")
            else:
                st.session_state["username"] = username.strip()
                st.rerun()


# ── Sidebar profile ────────────────────────────────────────────────────────────

def render_sidebar(username: str) -> None:
    with st.sidebar:
        st.markdown(f"### 👤 {username}")
        st.caption("Profile persists across sessions")
        st.divider()

        # Load current profile
        data = _get(f"/profile/{username}") or {}

        with st.form("profile_form"):
            st.markdown("**💰 Budget (₹ Lakhs)**")
            col1, col2 = st.columns(2)
            with col1:
                bmin = st.number_input(
                    "Min", value=float(data.get("budget_min") or 0) / 1e5,
                    min_value=0.0, step=5.0, format="%.0f"
                )
            with col2:
                bmax = st.number_input(
                    "Max", value=float(data.get("budget_max") or 0) / 1e5,
                    min_value=0.0, step=5.0, format="%.0f"
                )

            purpose = st.selectbox(
                "Purpose",
                ["investment", "self_use", "commercial"],
                index=["investment", "self_use", "commercial"].index(
                    data.get("purpose") or "investment"
                ),
            )
            risk = st.selectbox(
                "Risk Appetite",
                ["low", "medium", "high"],
                index=["low", "medium", "high"].index(data.get("risk_appetite") or "medium"),
            )
            timeline = st.number_input(
                "Timeline (months)", value=int(data.get("timeline_months") or 6),
                min_value=1, max_value=120,
            )
            locs_raw = st.text_input(
                "Preferred cities (comma-separated)",
                value=", ".join(data.get("location_preference") or []),
            )
            prop_type = st.text_input(
                "Property type", value=data.get("preferred_property_type") or ""
            )
            existing = st.number_input(
                "Existing properties", value=int(data.get("existing_properties") or 0),
                min_value=0,
            )
            citizenship = st.text_input(
                "Citizenship status", value=data.get("citizenship_status") or ""
            )
            loan_known = st.checkbox(
                "Loan eligibility assessed?", value=bool(data.get("loan_eligibility_known"))
            )

            saved = st.form_submit_button("💾 Save Profile", use_container_width=True)

        if saved:
            payload = {
                "username": username,
                "budget_min": bmin * 1e5 if bmin else None,
                "budget_max": bmax * 1e5 if bmax else None,
                "location_preference": [x.strip() for x in locs_raw.split(",") if x.strip()],
                "purpose": purpose,
                "risk_appetite": risk,
                "timeline_months": int(timeline),
                "preferred_property_type": prop_type or None,
                "existing_properties": int(existing),
                "citizenship_status": citizenship or None,
                "loan_eligibility_known": loan_known,
            }
            res = _post("/profile", payload)
            if res:
                st.success("Profile saved!")

        st.divider()
        if st.button("🚪 Log out", use_container_width=True):
            del st.session_state["username"]
            st.session_state.pop("result", None)
            st.rerun()


# ── Results renderer ───────────────────────────────────────────────────────────

def render_results(result: dict) -> None:
    rec = result.get("recommendation", "Needs more info")
    cs = result.get("confidence_score", 1)
    domains = result.get("active_domains", [])

    # ── Header row
    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown(f"**Recommendation:** {_badge(rec)}", unsafe_allow_html=True)
        domain_tags = "".join(f'<span class="domain-tag">{d}</span>' for d in domains)
        st.markdown(f"<div style='margin-top:0.5rem;'>Active domains: {domain_tags}</div>",
                    unsafe_allow_html=True)
    with c2:
        st.markdown(f"**Confidence: {cs}/10**")
        pct = int(cs / 10 * 100)
        st.markdown(
            f'<div class="conf-bar-wrap"><div class="conf-bar" style="width:{pct}%"></div></div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="card card-accent">', unsafe_allow_html=True)
    st.markdown(f"**📋 Summary**\n\n{result.get('summary','')}")
    st.markdown("</div>", unsafe_allow_html=True)

    # ── Tabs
    tab_insights, tab_agents, tab_risks, tab_followup = st.tabs(
        ["🔑 Key Insights", "🤝 Agent Debates", "⚠️ Risks", "❓ Follow-ups"]
    )

    # Key Insights
    with tab_insights:
        ki = result.get("key_insights", {})
        domain_icons = {
            "market": "🏠", "investment": "📈", "legal": "⚖️",
            "financial": "🏦", "construction": "🏗️",
        }
        for domain, icon in domain_icons.items():
            val = ki.get(domain, "")
            if val:
                st.markdown(f"**{icon} {domain.title()}**")
                st.markdown(
                    f'<div class="card" style="padding:0.8rem 1rem;">{val}</div>',
                    unsafe_allow_html=True,
                )

    # Agent debates
    with tab_agents:
        agent_rounds = result.get("agent_rounds", [])
        agent_views_map = {
            av["agent"]: av for av in result.get("agent_views", [])
        }
        if not agent_rounds:
            st.info("No agent debate data available.")
        for ar in agent_rounds:
            name = ar["agent_name"]
            emoji = ar.get("emoji", "🤖")
            conf = ar.get("confidence", "medium")
            av = agent_views_map.get(name, {})
            dissents = av.get("dissents_from", [])

            dissent_html = "".join(
                f'<span class="dissent-tag">⚡ Disagrees with {d}</span>' for d in dissents
            )

            with st.expander(f"{emoji} {name}  ·  confidence: {conf.upper()}"):
                st.markdown(
                    f'<div class="agent-header">'
                    f'{_conf_pill(conf)}{dissent_html}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                # Key points
                kps = av.get("key_points", [])
                if kps:
                    st.markdown("**Key points:**")
                    for kp in kps:
                        st.markdown(f"• {kp}")

                st.markdown('<div class="round-label">Round 1 — Independent Analysis</div>',
                            unsafe_allow_html=True)
                st.markdown(
                    f'<div class="debate-box">{ar.get("round1", "")}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown('<div class="round-label" style="margin-top:0.8rem;">Round 2 — Debate Reaction</div>',
                            unsafe_allow_html=True)
                st.markdown(
                    f'<div class="debate-box">{ar.get("round2", "")}</div>',
                    unsafe_allow_html=True,
                )

    # Risks
    with tab_risks:
        risks = result.get("risks", [])
        if not risks:
            st.success("No significant risks flagged.")
        for r in risks:
            st.markdown(f'<div class="risk-item">⚠️ {r}</div>', unsafe_allow_html=True)

    # Follow-ups
    with tab_followup:
        st.markdown("**Click any question to auto-fill the query box:**")
        fuqs = result.get("follow_up_questions", [])
        for fuq in fuqs:
            if st.button(f"→ {fuq}", key=f"fuq_{fuq[:40]}"):
                _push_followup(fuq)
        if not fuqs:
            st.info("No follow-up questions generated.")


# ── History panel ──────────────────────────────────────────────────────────────

def render_history(username: str) -> None:
    data = _get(f"/history/{username}", {"limit": 10}) or {}
    sessions = data.get("sessions", [])
    if not sessions:
        st.info("No analysis history yet. Run your first query!")
        return
    for s in sessions:
        out = s.get("output", {})
        rec = out.get("recommendation", "?")
        cs = out.get("confidence_score", "?")
        ts = s.get("created_at", "")[:16].replace("T", " ")
        q = s.get("query", "")[:80]
        st.markdown(
            f'<div class="history-row">'
            f'<span style="color:rgba(255,255,255,0.45);font-size:0.75rem;">{ts}</span><br>'
            f'<b>{q}{"..." if len(s.get("query",""))>80 else ""}</b><br>'
            f'{_badge(rec)} &nbsp; <span style="color:rgba(255,255,255,0.5);font-size:0.8rem;">Confidence {cs}/10</span>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ── Main app ───────────────────────────────────────────────────────────────────

def main() -> None:
    if "username" not in st.session_state:
        render_login()
        return

    username = st.session_state["username"]
    render_sidebar(username)

    # Header
    st.markdown(
        "<h1 style='font-size:2rem;font-weight:700;"
        "background:linear-gradient(90deg,#7c3aed,#06b6d4);-webkit-background-clip:text;"
        "-webkit-text-fill-color:transparent;'>🏘️ Real Estate Advisory Panel</h1>",
        unsafe_allow_html=True,
    )
    st.caption(
        "5 AI experts debate your query in 2 rounds · Powered by Open-Source LLMs via Ollama"
    )

    main_tab, history_tab = st.tabs(["🔍 Analyze", "📜 History"])

    with main_tab:
        # Query input
        default_q = st.session_state.pop("query_input", "")
        auto_submit = st.session_state.pop("auto_submit", False)

        query = st.text_area(
            "Your real estate query",
            value=default_q,
            placeholder=(
                "Should I buy a 2-BHK in Pune for rental investment? "
                "Budget ₹90L, want stable cash flow within 6 months."
            ),
            height=120,
            key="query_input_box",
        )

        col_btn, col_hint = st.columns([1, 3])
        with col_btn:
            run = st.button("🚀 Run Advisory Panel", use_container_width=True)

        if run or auto_submit:
            if not query.strip():
                st.warning("Please enter a real estate query.")
            else:
                with st.spinner(
                    "🤝 5 experts are debating your query across 2 rounds — please wait..."
                ):
                    result = _post("/analyze", {"query": query, "username": username})

                if result:
                    st.session_state["result"] = result

        if "result" in st.session_state:
            st.divider()
            render_results(st.session_state["result"])

    with history_tab:
        render_history(username)


if __name__ == "__main__":
    main()
