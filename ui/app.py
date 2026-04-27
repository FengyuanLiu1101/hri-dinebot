"""
DineBot Streamlit control panel (3-column redesign).

Layout
------
+----------------+----------------------------+----------------+
|  Sidebar (25%) | Robot + Floor Map + Chat   | MAS Trace (25%)|
|  (left pane)   | (50% center)               | (right pane)   |
+----------------+----------------------------+----------------+

Run with::

    streamlit run ui/app.py

Key features
------------
* Three-segment animated delivery path on an 800x580 floor map.
* Live-streaming MAS trace panel driven by a ``log_mas_trace`` listener.
* "Run Demo" button that scripts a full delivery cycle (no user input).
* Special chat triggers:
    - "STOP"                 -> robot state flips to EMERGENCY.
    - "status"               -> inline status report in chat.
    - mentions of "table N"  -> delivery animation to table N.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Project root on path so `import config.*` works when Streamlit launches
# this file directly from inside ``ui/``.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st
import streamlit.components.v1 as components

from config.agent_config import AGENT_NAME, AGENT_VERSION, ROBOT_STATES  # noqa: E402
from ui.chat_interface import (  # noqa: E402
    inject_chat_css,
    render_agent_badge,
    render_history,
    render_typing_indicator,
)
from ui.floor_map import TERRACE_TABLES, render_floor_map_html  # noqa: E402
from ui.mas_visualizer import build_trace_listener, render_panel  # noqa: E402
from ui.robot_animation import (  # noqa: E402
    compute_state,
    render_robot_html,
    target_table_from_text,
)
from utils.logger import (  # noqa: E402
    register_trace_listener,
    unregister_trace_listener,
)

st.set_page_config(
    page_title=f"{AGENT_NAME} Control Panel",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ---------------------------------------------------------------------------
# Global theming
# ---------------------------------------------------------------------------
def inject_global_css() -> None:
    st.markdown(
        """
        <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700&family=Inter:wght@400;600&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
        <style>
          .stApp {
            background:
              radial-gradient(1200px 600px at 85% -10%, #122033 0%, transparent 60%),
              radial-gradient(900px 500px at 10% 110%, #0b2220 0%, transparent 60%),
              #0d1117;
            color: #e6edf3;
          }
          header[data-testid="stHeader"] { background: transparent; }
          .block-container { padding-top: 1.5rem; padding-bottom: 1rem; max-width: 1600px; }
          h1, h2, h3, h4 { font-family: 'Orbitron', sans-serif; letter-spacing: 2px; }

          .dinebot-header {
            display: flex; align-items: center; justify-content: space-between;
            padding: 6px 2px 12px 2px;
            border-bottom: 1px solid #1a2230;
            margin-bottom: 14px;
          }
          .dinebot-header h1 {
            margin: 0; font-family: 'Orbitron', sans-serif;
            color: #00d4aa; font-size: 26px; letter-spacing: 6px;
          }
          .dinebot-header .subtitle {
            color: #8b949e; font-size: 11px; letter-spacing: 3px;
            font-family: 'Orbitron', sans-serif;
          }

          /* Sidebar panel (left column) card */
          .side-card {
            background: #161b22; border: 1px solid #222c37;
            border-radius: 14px; padding: 12px 14px; margin-bottom: 10px;
          }
          .side-title {
            font-family: 'Orbitron', sans-serif;
            letter-spacing: 3px; color: #00d4aa;
            font-size: 12px; text-transform: uppercase; margin-bottom: 8px;
          }
          .brand {
            font-family: 'Orbitron', sans-serif;
            color: #00d4aa; letter-spacing: 4px; font-size: 22px;
          }
          .brand-sub {
            color: #8b949e; font-size: 10px; letter-spacing: 3px;
            font-family: 'Orbitron', sans-serif;
          }

          .agent-pill {
            display: inline-block; padding: 6px 10px; border-radius: 8px;
            font-family: 'Orbitron', sans-serif; font-size: 10px; letter-spacing: 2px;
          }
          .agent-pill.A { background: rgba(31,111,235,0.15); color: #79b8ff; border: 1px solid rgba(31,111,235,0.5); }
          .agent-pill.B { background: rgba(0,212,170,0.15);  color: #00d4aa; border: 1px solid rgba(0,212,170,0.5); }

          .state-pill {
            display: inline-block; padding: 7px 14px; border-radius: 999px;
            font-family: 'Orbitron', sans-serif; font-size: 12px; letter-spacing: 3px;
            margin: 4px 0 6px 0;
          }
          .state-pill.IDLE        { background: rgba(0,212,170,0.15); color: #00d4aa; border: 1px solid rgba(0,212,170,0.4); }
          .state-pill.LOADING     { background: rgba(31,111,235,0.15); color: #79b8ff; border: 1px solid rgba(31,111,235,0.4); }
          .state-pill.DELIVERING  { background: rgba(31,111,235,0.20); color: #79b8ff; border: 1px solid rgba(31,111,235,0.55); }
          .state-pill.WAITING     { background: rgba(0,212,170,0.15); color: #00d4aa; border: 1px solid rgba(0,212,170,0.4); }
          .state-pill.RETURNING   { background: rgba(63,185,80,0.15); color: #3fb950; border: 1px solid rgba(63,185,80,0.4); }
          .state-pill.EMERGENCY   { background: rgba(248,81,73,0.20); color: #ff7a70; border: 1px solid rgba(248,81,73,0.55);
                                     animation: pulseR 0.8s ease-in-out infinite; }
          .state-pill.LOW_BATTERY { background: rgba(210,153,34,0.2);  color: #d29922; border: 1px solid rgba(210,153,34,0.5);
                                     animation: pulseY 1.2s ease-in-out infinite; }
          @keyframes pulseR { 0%,100% { box-shadow: 0 0 0 rgba(248,81,73,0); } 50% { box-shadow: 0 0 16px rgba(248,81,73,0.6); } }
          @keyframes pulseY { 0%,100% { box-shadow: 0 0 0 rgba(210,153,34,0); } 50% { box-shadow: 0 0 16px rgba(210,153,34,0.6); } }

          .battery-bar {
            height: 12px; background: #0d1117; border-radius: 6px; overflow: hidden;
            border: 1px solid #222c37;
          }
          .battery-fill {
            height: 100%; background: linear-gradient(90deg, #00d4aa, #3fb950);
            transition: width 0.6s ease;
          }
          .battery-fill.low { background: linear-gradient(90deg, #d29922, #f85149); }
          .metric-lbl { color: #8b949e; font-family: 'Orbitron', sans-serif;
                        font-size: 10px; letter-spacing: 2px; }
          .metric-val { color: #e6edf3; font-family: 'Orbitron', sans-serif;
                        font-size: 18px; font-weight: 700; }

          div.stButton > button {
            background: #161b22; color: #e6edf3;
            border: 1px solid rgba(0,212,170,0.4);
            border-radius: 10px;
            font-family: 'Orbitron', sans-serif; letter-spacing: 2px;
            transition: all 0.2s ease;
          }
          div.stButton > button:hover {
            background: rgba(0,212,170,0.12); border-color: #00d4aa; color: #00d4aa;
          }
          div[data-testid="stFormSubmitButton"] button {
            background: linear-gradient(135deg, #00d4aa, #1f6feb);
            color: #0d1117; font-weight: 700; border: none;
          }
          div[data-testid="stFormSubmitButton"] button:hover { filter: brightness(1.1); }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
def init_session_state() -> None:
    ss = st.session_state
    ss.setdefault("selected_agent", "A")
    ss.setdefault("messages", [])
    ss.setdefault("robot_state", "IDLE")
    ss.setdefault("current_position", "DOCK")
    ss.setdefault("target_table", None)
    ss.setdefault("battery", 100.0)
    ss.setdefault("deliveries", 0)
    ss.setdefault("last_user_msg", "")
    ss.setdefault("last_bot_msg", "")
    ss.setdefault("pending_query", None)
    ss.setdefault("mas_trace_log", [])
    ss.setdefault("session_metrics", {
        "total_queries": 0,
        "pass_count": 0,
        "retries_total": 0,
        "chunks_total": 0,
        "response_time_total": 0.0,
        "avg_response_time": 0.0,
    })
    ss.setdefault("demo_queue", [])
    ss.setdefault("map_trigger", 0)


# ---------------------------------------------------------------------------
# Agent plumbing
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner="Booting DineBot Agent A (rule-based)...")
def _get_agent_a():
    from agent_a.simple_agent import SimpleAgent
    return SimpleAgent()


@st.cache_resource(show_spinner="Booting DineBot Agent B (RAG + MAS)...")
def _get_agent_b():
    from agent_b.mas.orchestrator import Orchestrator
    return Orchestrator()


def _run_agent(agent_letter: str, query: str) -> dict:
    """Dispatch a query to the active agent; return a uniform dict."""
    if agent_letter.upper() == "A":
        agent = _get_agent_a()
        intent = agent.classify_intent(query)
        context = agent.retrieve(query, k=3)
        response = agent.generate_response(query, intent, context)
        return {
            "response": response,
            "context": context,
            "retries": 0,
            "verdict": {"status": "PASS", "feedback": "Agent A is rule-based."},
            "intent": intent,
        }
    orch = _get_agent_b()
    return orch.run_once(query)


# ---------------------------------------------------------------------------
# Chat submission + special triggers
# ---------------------------------------------------------------------------
def _is_status_query(text: str) -> bool:
    t = (text or "").strip().lower()
    return t in {"status", "what is your status", "what's your status"}


def _is_stop_trigger(text: str) -> bool:
    t = (text or "").strip().lower()
    return t in {"stop", "emergency", "halt", "!stop"}


def _handle_user_message(query: str) -> None:
    """Record a user message and either handle it locally or queue the agent."""
    query = (query or "").strip()
    if not query:
        return
    ss = st.session_state
    ss.messages.append({"role": "user", "content": query})
    ss.last_user_msg = query

    # Special: STOP immediately flips state to EMERGENCY (no agent call).
    if _is_stop_trigger(query):
        ss.robot_state = "EMERGENCY"
        ss.target_table = None
        bot = "EMERGENCY STOP acknowledged. I have halted in place and alerted staff."
        ss.messages.append({"role": "robot", "content": bot})
        ss.last_bot_msg = bot
        return

    # Special: "status" -> inline status card, no agent call.
    if _is_status_query(query):
        bot = (
            f"Status: {ss.robot_state.replace('_', ' ')} | "
            f"Battery: {ss.battery:.0f}% | "
            f"Deliveries completed: {ss.deliveries} | "
            f"Target: {('Table ' + str(ss.target_table)) if ss.target_table else 'None'}"
        )
        ss.messages.append({"role": "robot", "content": bot})
        ss.last_bot_msg = bot
        return

    # Normal path: queue the query for agent processing on next rerun.
    ss.pending_query = query


def _process_pending() -> None:
    """Run the pending query through the selected agent with live tracing."""
    ss = st.session_state
    query = ss.pending_query
    if not query:
        return
    ss.pending_query = None

    agent_letter = ss.selected_agent.upper()
    ss.mas_trace_log = []
    listener = build_trace_listener(ss.mas_trace_log)
    if agent_letter == "B":
        register_trace_listener(listener)

    started = time.time()
    try:
        result = _run_agent(agent_letter, query)
        response = result.get("response", "")
    except Exception as exc:  # noqa: BLE001
        response = (
            f"I ran into an internal problem: {exc}. "
            f"Please ask a human staff member."
        )
        result = {
            "response": response,
            "context": [],
            "retries": 0,
            "verdict": {"status": "REVISE", "feedback": str(exc)},
        }
    finally:
        if agent_letter == "B":
            unregister_trace_listener(listener)

    elapsed = time.time() - started

    ss.messages.append({"role": "robot", "content": response})
    ss.last_bot_msg = response

    # Update robot state + target table + stats.
    new_target = target_table_from_text(ss.last_user_msg)
    if new_target and new_target not in TERRACE_TABLES:
        ss.target_table = new_target
        ss.map_trigger += 1
    elif new_target in TERRACE_TABLES:
        # Refuse terrace delivery, no map animation.
        ss.target_table = None

    ss.robot_state = compute_state(
        ss.robot_state,
        last_user_msg=ss.last_user_msg,
        last_bot_msg=response,
        battery=ss.battery,
    )

    # Deliveries + battery bookkeeping.
    if ss.target_table and ss.target_table not in TERRACE_TABLES and new_target:
        ss.deliveries += 1
        ss.battery = max(0.0, ss.battery - 5.0)
    if ss.robot_state == "IDLE" and ss.battery < 100.0:
        ss.battery = min(100.0, ss.battery + 2.0)

    # Update MAS session metrics (only meaningful for Agent B).
    m = ss.session_metrics
    m["total_queries"] += 1
    m["response_time_total"] += elapsed
    m["avg_response_time"] = m["response_time_total"] / max(1, m["total_queries"])
    m["retries_total"] += int(result.get("retries") or 0)
    m["chunks_total"] += len(result.get("context") or [])
    if str(result.get("verdict", {}).get("status", "PASS")).upper() == "PASS":
        m["pass_count"] += 1


# ---------------------------------------------------------------------------
# Run Demo — scripted delivery cycle
# ---------------------------------------------------------------------------
_DEMO_SCRIPT = [
    "Hello DineBot, what can you do?",
    "Please deliver the food order to table 7",
    "status",
]


def _start_demo() -> None:
    st.session_state.demo_queue = list(_DEMO_SCRIPT)


def _advance_demo() -> None:
    ss = st.session_state
    if ss.demo_queue and ss.pending_query is None:
        next_msg = ss.demo_queue.pop(0)
        _handle_user_message(next_msg)


def _reset_session() -> None:
    ss = st.session_state
    ss.messages = []
    ss.robot_state = "IDLE"
    ss.current_position = "DOCK"
    ss.target_table = None
    ss.battery = 100.0
    ss.deliveries = 0
    ss.last_user_msg = ""
    ss.last_bot_msg = ""
    ss.pending_query = None
    ss.mas_trace_log = []
    ss.demo_queue = []
    ss.map_trigger += 1
    ss.session_metrics = {
        "total_queries": 0,
        "pass_count": 0,
        "retries_total": 0,
        "chunks_total": 0,
        "response_time_total": 0.0,
        "avg_response_time": 0.0,
    }


def _on_agent_change() -> None:
    """Clear chat on agent switch; keep session stats."""
    ss = st.session_state
    ss.messages = []
    ss.last_user_msg = ""
    ss.last_bot_msg = ""
    ss.pending_query = None
    ss.mas_trace_log = []


# ---------------------------------------------------------------------------
# Column renderers
# ---------------------------------------------------------------------------
def render_left_panel() -> None:
    ss = st.session_state
    st.markdown(
        '<div class="side-card">'
        f'<div class="brand">&#129302; {AGENT_NAME}</div>'
        f'<div class="brand-sub">v{AGENT_VERSION} &middot; HRI LAB SYSTEMS</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    with st.container():
        st.markdown('<div class="side-card">', unsafe_allow_html=True)
        st.markdown('<div class="side-title">Agent Selector</div>', unsafe_allow_html=True)
        choice = st.radio(
            "Agent",
            options=["A", "B"],
            format_func=lambda x: ("Agent A" if x == "A" else "Agent B"),
            index=0 if ss.selected_agent == "A" else 1,
            horizontal=True,
            label_visibility="collapsed",
            key="agent_radio",
            on_change=_on_agent_change,
        )
        if choice != ss.selected_agent:
            ss.selected_agent = choice
        letter = ss.selected_agent
        label = (
            "RULE-BASED | No API" if letter == "A"
            else "RAG + MAS | GPT-4o-mini"
        )
        st.markdown(
            f'<span class="agent-pill {letter}">{label}</span>',
            unsafe_allow_html=True,
        )
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if letter == "B" and (not api_key or api_key == "your_api_key_here"):
            st.warning("No OPENAI_API_KEY — Agent B is running offline-stub.")
        st.markdown("</div>", unsafe_allow_html=True)

    state = ss.robot_state
    state_desc = ROBOT_STATES.get(state, "")
    # Render the status card in three separate markdown blocks so the
    # label, the state pill, and the description never share a baseline
    # (Streamlit's markdown will otherwise sometimes inline them).
    st.markdown('<div class="side-card">', unsafe_allow_html=True)
    st.markdown(
        '<div class="side-title">Robot Status</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="state-pill {state}">{state.replace("_", " ")}</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div style="color:#8b949e;font-size:11px;margin-top:4px">{state_desc}</div>'
        "</div>",
        unsafe_allow_html=True,
    )

    battery = max(0.0, min(100.0, ss.battery))
    low_cls = "low" if battery <= 20 else ""
    target_str = f"Table {ss.target_table}" if ss.target_table else "None"
    st.markdown(
        '<div class="side-card">'
        '<div class="side-title">Battery</div>'
        f'<div class="battery-bar"><div class="battery-fill {low_cls}" '
        f'style="width:{battery:.0f}%"></div></div>'
        f'<div class="metric-val" style="font-size:14px;margin-top:4px">{battery:.0f}%</div>'
        f'<div class="side-title" style="margin-top:10px">Current Target</div>'
        f'<div class="metric-val" style="font-size:15px">{target_str}</div>'
        f'<div class="side-title" style="margin-top:10px">Deliveries Done</div>'
        f'<div class="metric-val">&#10003; {ss.deliveries}</div>'
        "</div>",
        unsafe_allow_html=True,
    )

    with st.container():
        st.markdown('<div class="side-card">', unsafe_allow_html=True)
        st.markdown('<div class="side-title">Controls</div>', unsafe_allow_html=True)
        run_demo_clicked = st.button("Run Demo", use_container_width=True, key="btn_demo")
        reset_clicked = st.button("Reset Session", use_container_width=True, key="btn_reset")
        if run_demo_clicked:
            _start_demo()
            st.rerun()
        if reset_clicked:
            _reset_session()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


def render_center_panel() -> None:
    ss = st.session_state
    robot_html = render_robot_html(ss.robot_state, ss.battery)
    components.html(robot_html, height=420, scrolling=False)

    floor_html = render_floor_map_html(
        robot_state=ss.robot_state,
        target_table=ss.target_table,
        delivery_completed=(ss.robot_state == "WAITING"),
        trigger_id=ss.map_trigger,
    )
    components.html(floor_html, height=620, scrolling=False)

    inject_chat_css()
    render_agent_badge(ss.selected_agent)
    render_history(ss.messages)
    if ss.pending_query:
        render_typing_indicator()

    with st.form(key="chat_form", clear_on_submit=True):
        user_input = st.text_input(
            "Message DineBot",
            key="chat_input",
            placeholder='Try "Deliver pizza to table 7" or type STOP',
            label_visibility="collapsed",
        )
        col_send, _ = st.columns([1, 4])
        with col_send:
            submitted = st.form_submit_button("Send", use_container_width=True)
        if submitted and user_input.strip():
            _handle_user_message(user_input)
            st.rerun()


def render_right_panel() -> None:
    ss = st.session_state
    render_panel(
        trace_log=ss.mas_trace_log,
        metrics=ss.session_metrics,
        agent_letter=ss.selected_agent,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    inject_global_css()
    init_session_state()

    st.markdown(
        f'<div class="dinebot-header">'
        f'  <h1>DINEBOT CONTROL PANEL</h1>'
        f'  <span class="subtitle">RESTAURANT DELIVERY ROBOT &middot; v{AGENT_VERSION}</span>'
        f"</div>",
        unsafe_allow_html=True,
    )

    # Advance demo queue if we are in demo mode and there's no pending work.
    if st.session_state.demo_queue and st.session_state.pending_query is None:
        _advance_demo()

    left, center, right = st.columns([1, 2, 1], gap="medium")
    with left:
        render_left_panel()
    with center:
        render_center_panel()
    with right:
        render_right_panel()

    # Process any pending query after all panels have been rendered so the
    # trace log populated by the listener is visible on the next rerun.
    if st.session_state.pending_query:
        _process_pending()
        st.rerun()

    # Continue the demo sequence automatically.
    if st.session_state.demo_queue and st.session_state.pending_query is None:
        st.rerun()


main()
