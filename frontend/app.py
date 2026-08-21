"""
Real Estate Advisory — Streamlit Frontend
Connects to FastAPI backend at BACKEND_URL (default http://localhost:8000)
"""
from __future__ import annotations

import os
import json
import time
from html import escape
from pathlib import Path
from typing import Any, Iterator

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

/* Live stream */
.stream-panel {
    background: rgba(0,0,0,0.22);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px;
    padding: 0.85rem 1rem;
    margin: 0.6rem 0 1rem 0;
    max-height: 320px;
    overflow-y: auto;
}
.stream-event {
    padding: 0.5rem 0;
    border-bottom: 1px solid rgba(255,255,255,0.08);
    font-size: 0.88rem;
    line-height: 1.45;
}
.stream-event:last-child { border-bottom: 0; }
.stream-label { color: #93c5fd; font-weight: 700; margin-right: 0.35rem; }
.cache-hit-badge {
    display: inline-block;
    background: rgba(6,182,212,0.16);
    color: #67e8f9;
    border: 1px solid rgba(6,182,212,0.42);
    border-radius: 999px;
    padding: 0.35rem 0.8rem;
    margin: 0.4rem 0 0.8rem 0;
    font-weight: 800;
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


def _decode_sse(event_name: str | None, data_lines: list[str]) -> dict[str, Any] | None:
    if not data_lines:
        return None

    raw_data = "\n".join(data_lines).strip()
    if not raw_data:
        return None

    data = json.loads(raw_data)
    if isinstance(data, dict) and "event" in data and "data" in data and event_name is None:
        return {"event": data["event"], "data": data["data"]}
    return {"event": event_name or "message", "data": data}


def _stream_analyze(payload: dict) -> Iterator[dict[str, Any]]:
    received_any = False

    for attempt in range(2):
        event_name: str | None = None
        data_lines: list[str] = []

        try:
            with requests.post(
                f"{BACKEND}/analyze",
                json=payload,
                stream=True,
                timeout=(10, 300),
            ) as response:
                response.raise_for_status()

                for raw_line in response.iter_lines(decode_unicode=True):
                    if raw_line is None:
                        continue
                    if isinstance(raw_line, bytes):
                        raw_line = raw_line.decode("utf-8")

                    line = raw_line.strip()
                    if not line:
                        decoded = _decode_sse(event_name, data_lines)
                        if decoded:
                            received_any = True
                            yield decoded
                        event_name = None
                        data_lines = []
                        continue

                    if line.startswith(":"):
                        continue
                    if line.startswith("event:"):
                        event_name = line.removeprefix("event:").strip()
                    elif line.startswith("data:"):
                        data_lines.append(line.removeprefix("data:").strip())

                decoded = _decode_sse(event_name, data_lines)
                if decoded:
                    yield decoded
                return

        except requests.exceptions.RequestException as exc:
            if not received_any and attempt == 0:
                yield {
                    "event": "retrying",
                    "data": {"message": f"Connection interrupted ({exc}). Retrying once..."},
                }
                time.sleep(1.2)
                continue
            yield {
                "event": "error",
                "data": {"message": f"Streaming connection failed: {exc}"},
            }
            return
        except json.JSONDecodeError as exc:
            yield {
                "event": "error",
                "data": {"message": f"Invalid SSE payload from backend: {exc}"},
            }
            return


def _short(text: Any, limit: int = 260) -> str:
    clean = " ".join(str(text or "").split())
    if len(clean) <= limit:
        return clean
    return clean[: limit - 3].rstrip() + "..."


def _event_message(event: dict[str, Any]) -> tuple[str, str]:
    event_type = event.get("event", "message")
    data = event.get("data") or {}

    if event_type == "classification":
        return (
            "Classification",
            f"Domains: {', '.join(data.get('domains', []))} | Experts: {', '.join(data.get('agents', []))}",
        )
    if event_type == "orchestration_start":
        return "OAISS", data.get("message", "Expert debate started.")
    if event_type == "agent_start":
        return f"Round {data.get('round', '?')}", data.get("message", "Agent started.")
    if event_type == "agent_round1":
        return "Round 1 complete", f"{data.get('emoji', '')} {data.get('agent_name', 'Agent')}: {_short(data.get('response'))}"
    if event_type == "debate_start":
        queue = ", ".join(data.get("queue", [])) or "No additional debate agents"
        return "Round 2", queue
    if event_type == "agent_round2":
        return "Debate turn", f"{data.get('emoji', '')} {data.get('agent_name', 'Agent')}: {_short(data.get('response'))}"
    if event_type == "handoff":
        return "Handoff", data.get("message", "Agent handoff requested.")
    if event_type == "consensus":
        return "Consensus", data.get("message", data.get("reason", "Consensus reached."))
    if event_type == "aggregator_start":
        return "Synthesis", data.get("message", "Synthesizing final recommendation.")
    if event_type == "cache_hit":
        return "Cache", data.get("message", "Instant semantic cache hit.")
    if event_type == "retrying":
        return "Retrying", data.get("message", "Retrying connection.")
    if event_type == "error":
        return "Error", data.get("message", "Streaming failed.")
    if event_type == "final_result":
        return "Complete", "Final recommendation ready."
    return event_type.replace("_", " ").title(), _short(data)


def _render_stream_events(events: list[dict[str, Any]], placeholder: Any) -> None:
    rows = []
    for event in events[-14:]:
        label, detail = _event_message(event)
        rows.append(
            f'<div class="stream-event"><span class="stream-label">{escape(label)}</span>'
            f"{escape(detail)}</div>"
        )
    placeholder.markdown(
        f'<div class="stream-panel">{"".join(rows)}</div>',
        unsafe_allow_html=True,
    )


def _run_streaming_analysis(query: str, username: str) -> tuple[dict | None, bool]:
    events: list[dict[str, Any]] = []
    final_result: dict | None = None
    cache_hit = False
    feed = st.empty()

    with st.status("Contacting advisory engine...", expanded=True) as status:
        for event in _stream_analyze({"query": query, "username": username}):
            event_type = event.get("event", "message")
            data = event.get("data") or {}
            events.append(event)
            _render_stream_events(events, feed)

            if event_type == "cache_hit":
                cache_hit = True
                status.update(label="⚡ Instant Semantic Cache Hit", state="complete")
                status.write(data.get("message", "Served from semantic cache."))
            elif event_type == "retrying":
                status.update(label="Connection interrupted. Retrying...", state="running")
                status.write(data.get("message", "Retrying once..."))
            elif event_type == "classification":
                status.update(label="Query classified", state="running")
                status.write(data.get("message", "Domain classification complete."))
            elif event_type == "agent_start":
                status.update(label=data.get("message", "Agent analysis started."), state="running")
            elif event_type in {"agent_round1", "agent_round2", "handoff", "consensus"}:
                label, detail = _event_message(event)
                status.write(f"{label}: {detail}")
            elif event_type == "aggregator_start":
                status.update(label="Synthesizing expert consensus...", state="running")
                status.write(data.get("message", "Synthesizing final recommendation."))
            elif event_type == "final_result":
                final_result = data
                status.update(label="Analysis complete", state="complete")
                break
            elif event_type == "error":
                status.update(label="Analysis failed", state="error")
                st.error(data.get("message", "Streaming failed."))
                break

        if final_result is None and not any(e.get("event") == "error" for e in events):
            status.update(label="Analysis ended before a final result arrived", state="error")
            st.error("The backend stream closed before sending final_result.")

    if cache_hit:
        st.markdown(
            '<div class="cache-hit-badge">⚡ Instant Semantic Cache Hit</div>',
            unsafe_allow_html=True,
        )

    return final_result, cache_hit


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
    prev_q = st.session_state.get("last_query", "").strip()
    if prev_q and not any(phrase in q.lower() for phrase in ["regarding", "follow-up", "in reference to"]):
        full_query = f"Follow-up regarding '{prev_q}':\n{q}"
    else:
        full_query = q
    st.session_state["pending_query"] = full_query
    st.session_state["auto_submit"] = True
    st.rerun()


# ── Login screen ───────────────────────────────────────────────────────────────

def render_login() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500&display=swap');
        
        /* Hide Streamlit Header, Footer, and Sidebar */
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        [data-testid="collapsedControl"] {display: none;}
        
        /* App Background with subtle real estate image and dark overlay */
        .stApp {
            background: linear-gradient(rgba(15, 23, 42, 0.85), rgba(30, 27, 75, 0.95)), 
                        url('https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?q=80&w=2070&auto=format&fit=crop') no-repeat center center fixed !important;
            background-size: cover !important;
            color: white;
        }
        
        /* Glassmorphism Card on the middle column */
        [data-testid="stHorizontalBlock"]:first-of-type > [data-testid="column"]:nth-of-type(2) {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border-radius: 24px;
            border: 1px solid rgba(255, 255, 255, 0.15);
            padding: 3rem 2rem;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.5);
            display: flex;
            flex-direction: column;
            align-items: center;
            margin-top: 12vh;
        }
        
        /* Typography & Logo */
        @keyframes shimmer {
            0% { background-position: -200% center; }
            100% { background-position: 200% center; }
        }
        
        .logo-container {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 16px;
            margin-bottom: 0.8rem;
        }

        .logo-mark {
            width: 52px;
            height: 52px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.25);
            box-shadow: 0 0 25px rgba(125, 211, 252, 0.35);
            backdrop-filter: blur(8px);
        }

        .login-title {
            font-size: 3.2rem;
            font-weight: 800;
            font-family: 'Inter', 'Roboto', sans-serif;
            background: linear-gradient(90deg, #ffffff 0%, #e0f2fe 30%, #7dd3fc 50%, #e0f2fe 70%, #ffffff 100%);
            background-size: 200% auto;
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-align: center;
            letter-spacing: -1px;
            animation: shimmer 6s linear infinite;
            filter: drop-shadow(0px 2px 4px rgba(0,0,0,0.6));
            margin: 0;
        }
        
        .login-subtitle {
            font-size: 0.85rem;
            font-weight: 500;
            color: rgba(255, 255, 255, 0.7);
            margin-bottom: 2.8rem;
            letter-spacing: 1.5px;
            text-align: center;
            text-transform: uppercase;
            line-height: 1.6;
        }
        
        /* Google Button Style Override */
        .stButton>button {
            width: 100%;
            border-radius: 4px;
            height: 44px;
            font-weight: 500;
            font-family: 'Roboto', sans-serif;
            background: white !important;
            color: #3c4043 !important;
            border: 1px solid #dadce0 !important;
            transition: background-color 0.2s ease, box-shadow 0.2s ease;
        }
        .stButton>button:hover {
            background: #f8f9fa !important;
            box-shadow: 0 1px 2px 0 rgba(60,64,67,0.30), 0 1px 3px 1px rgba(60,64,67,0.15) !important;
            color: #3c4043 !important;
            border: 1px solid #dadce0 !important;
            transform: none !important;
        }
        
        /* Divider */
        .divider {
            width: 100%;
            height: 1px;
            background: rgba(255,255,255,0.1);
            margin: 2.5rem 0 1.5rem 0;
        }
        
        /* Features Row Badges */
        .feature-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            gap: 0.8rem;
            cursor: pointer;
            transition: transform 0.3s ease;
        }
        .feature-item:hover {
            transform: translateY(-5px);
        }
        .icon-container {
            width: 56px;
            height: 56px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 16px;
            background: linear-gradient(135deg, rgba(255,255,255,0.1), rgba(255,255,255,0.02));
            border: 1px solid rgba(255,255,255,0.2);
            box-shadow: 0 4px 15px rgba(255, 255, 255, 0.05);
            font-size: 26px;
            text-shadow: 0 2px 4px rgba(0,0,0,0.4);
            transition: all 0.3s ease;
        }
        .feature-item:hover .icon-container {
            box-shadow: 0 8px 25px rgba(255, 255, 255, 0.15);
            border-color: rgba(255,255,255,0.4);
        }
        .feature-text {
            font-size: 0.75rem;
            font-weight: 500;
            color: #f8fafc;
            text-transform: uppercase;
            letter-spacing: 1px;
            text-align: center;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    col = st.columns([1, 1.2, 1])[1]
    with col:
        st.markdown(
            """
            <div class="logo-container">
                <div class="logo-mark">
                    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <rect x="4" y="2" width="16" height="20" rx="2" ry="2"/>
                        <path d="M9 22v-4h6v4"/>
                        <path d="M8 6h.01M16 6h.01M12 6h.01M8 10h.01M16 10h.01M12 10h.01M8 14h.01M16 14h.01M12 14h.01"/>
                    </svg>
                </div>
                <div class="login-title">RE Advisory</div>
            </div>
            """, 
            unsafe_allow_html=True
        )
        st.markdown('<div class="login-subtitle">Enterprise Real Estate Advisory System <br> Powered by Open-Source AI</div>', unsafe_allow_html=True)
        
        st.markdown(
            "<p style='color: #e2e8f0; font-size: 0.95rem; margin-bottom: 1.2rem; text-align: center; font-weight: 500;'>Sign in securely to your workspace</p>", 
            unsafe_allow_html=True
        )
        
        if st.button("G  Continue with Google", use_container_width=True):
            st.login()
            
        st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
        
        # Value Proposition Features
        f1, f2, f3 = st.columns(3)
        with f1:
            st.markdown(
                """
                <div class="feature-item">
                    <div class="icon-container">🏢</div>
                    <div class="feature-text">SMART<br>PORTFOLIOS</div>
                </div>
                """, unsafe_allow_html=True
            )
        with f2:
            st.markdown(
                """
                <div class="feature-item">
                    <div class="icon-container">🤖</div>
                    <div class="feature-text">AI<br>ADVISORY</div>
                </div>
                """, unsafe_allow_html=True
            )
        with f3:
            st.markdown(
                """
                <div class="feature-item">
                    <div class="icon-container">📊</div>
                    <div class="feature-text">MARKET<br>INSIGHTS</div>
                </div>
                """, unsafe_allow_html=True
            )


# ── Sidebar profile ────────────────────────────────────────────────────────────

def render_sidebar(username: str) -> None:
    with st.sidebar:
        st.markdown(f"### 👤 {username}")
        st.caption("Profile persists across sessions")
        st.divider()

        # Load current profile
        data = _get(f"/profile/{username}") or {}

        with st.form("profile_form"):
            st.markdown("**💰 Budget (₹ Rupees)**")
            col1, col2 = st.columns(2)
            with col1:
                bmin = st.number_input(
                    "Min", value=float(data.get("budget_min") or 0),
                    min_value=0.0, step=10000.0, format="%.0f"
                )
            with col2:
                bmax = st.number_input(
                    "Max", value=float(data.get("budget_max") or 0),
                    min_value=0.0, step=10000.0, format="%.0f"
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
                "budget_min": bmin if bmin else None,
                "budget_max": bmax if bmax else None,
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
            st.logout()


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
        for i, fuq in enumerate(fuqs):
            if st.button(f"→ {fuq}", key=f"fuq_{i}_{abs(hash(fuq))}"):
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
    if not st.user.is_logged_in:  # type: ignore[attr-defined]
        render_login()
        return

    username = st.user.email  # type: ignore[attr-defined]
    st.session_state["username"] = username
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
        if "pending_query" in st.session_state:
            st.session_state["query_input_box"] = st.session_state.pop("pending_query")

        auto_submit = st.session_state.pop("auto_submit", False)

        query = st.text_area(
            "Your real estate query",
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
                st.session_state["last_query"] = query
                result, cache_hit = _run_streaming_analysis(query, username)
                if result:
                    st.session_state["result"] = result
                    st.session_state["last_cache_hit"] = cache_hit

        if "result" in st.session_state:
            st.divider()
            if st.session_state.get("last_cache_hit"):
                st.markdown(
                    '<div class="cache-hit-badge">⚡ Instant Semantic Cache Hit</div>',
                    unsafe_allow_html=True,
                )
            render_results(st.session_state["result"])

    with history_tab:
        render_history(username)


if __name__ == "__main__":
    main()
