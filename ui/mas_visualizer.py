"""
Multi-Agent System live visualisation panel.

Three things are rendered here, stacked vertically in the right column:

1. A vertical pipeline diagram with the three sub-agents plus the final
   response box. Each box can be in one of four visual states:
   ``idle`` / ``active`` / ``done`` / ``warn``. A retry card appears
   between the Generator and Critic when the Critic returns ``REVISE``.
2. A terminal-style live trace log, streaming every event that
   ``utils.logger.log_mas_trace`` emits during the current query.
3. A session metrics strip (totals, PASS rate, avg retries, chunks, etc.).

The panel is driven by ``st.session_state.mas_trace_log`` — the UI's
``trace_listener`` callback appends one dict per event, and this module
renders from that list.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from html import escape
from typing import Any

import streamlit as st


# ---------------------------------------------------------------------------
# Step-name routing: classify raw trace events into pipeline phases + colors
# ---------------------------------------------------------------------------
_RETRIEVER_STEPS = {
    "retriever_init", "retriever_query", "retriever_empty",
    "retriever_embedding", "retriever_result", "retriever_chunk",
    "retriever_output", "retriever",
}
_GENERATOR_STEPS = {
    "generator_init", "generator_build", "generator_prompt",
    "generator_call", "generator_response", "generator_error",
}
_CRITIC_STEPS = {
    "critic_init", "critic_start", "critic_check",
    "critic_prompt", "critic_verdict", "critic_error",
}
_ORCHESTRATOR_STEPS = {
    "orchestrator_init", "orchestrator_step", "orchestrator",
    "critic_retry", "final",
}


def _phase_of(step_name: str) -> str:
    if step_name in _RETRIEVER_STEPS:
        return "retriever"
    if step_name in _GENERATOR_STEPS:
        return "generator"
    if step_name in _CRITIC_STEPS:
        return "critic"
    return "orchestrator"


# ---------------------------------------------------------------------------
# Trace event helpers (public - used by app.py to register a listener)
# ---------------------------------------------------------------------------
def build_trace_listener(
    trace_log: list[dict[str, Any]]
) -> "callable":
    """Return a ``log_mas_trace`` listener that appends to ``trace_log``."""

    def _listener(step_name: str, content: str) -> None:
        trace_log.append(
            {
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "step": step_name,
                "phase": _phase_of(step_name),
                "content": str(content),
            }
        )

    return _listener


# ---------------------------------------------------------------------------
# Pipeline diagram
# ---------------------------------------------------------------------------
def _derive_pipeline_states(
    trace_log: list[dict[str, Any]]
) -> tuple[dict[str, str], int, dict]:
    """Infer the per-agent visual state from the current trace log.

    Returns
    -------
    states : dict[str, str]
        Mapping of agent key -> "idle" / "active" / "done" / "warn".
    retries : int
        Number of critic REVISE verdicts observed.
    verdict : dict
        Last critic verdict dict ({"status", "feedback"}) or empty.
    """
    seen_phases: list[str] = [e["phase"] for e in trace_log]
    has_final = any(e["step"] == "final" for e in trace_log)
    states: dict[str, str] = {
        "retriever": "idle",
        "generator": "idle",
        "critic": "idle",
        "final": "idle",
    }
    if "retriever" in seen_phases:
        states["retriever"] = "active"
    if "generator" in seen_phases:
        states["retriever"] = "done"
        states["generator"] = "active"
    if "critic" in seen_phases:
        states["retriever"] = "done"
        states["generator"] = "done"
        states["critic"] = "active"

    retries = 0
    verdict: dict = {}
    for event in trace_log:
        if event["step"] == "critic_verdict":
            try:
                verdict = json.loads(event["content"])
            except Exception:  # noqa: BLE001
                verdict = {}
        if event["step"] == "critic_retry":
            retries += 1

    if verdict.get("status") == "PASS":
        states["critic"] = "done"
        states["final"] = "done" if has_final else "active"
    elif verdict.get("status") == "REVISE":
        states["critic"] = "warn"

    if has_final:
        for k in ("retriever", "generator", "critic"):
            if states[k] == "active":
                states[k] = "done"
        if states["final"] == "idle":
            states["final"] = "done"

    return states, retries, verdict


def _pipeline_box(
    key: str, icon: str, title: str, sub: str, state: str
) -> str:
    cls = f"mas-box mas-{key} mas-{state}"
    spinner = (
        '<span class="mas-spinner"></span>' if state == "active" else ""
    )
    check = '<span class="mas-check">&#10003;</span>' if state == "done" else ""
    return (
        f'<div class="{cls}">'
        f'  <div class="mas-box-head"><span class="mas-icon">{icon}</span>'
        f'    <span class="mas-title">{title}</span>{spinner}{check}'
        f'  </div>'
        f'  <div class="mas-sub">{sub}</div>'
        f"</div>"
    )


def _connector(active: bool) -> str:
    cls = "mas-connector active" if active else "mas-connector"
    return f'<div class="{cls}"><span></span><span></span><span></span></div>'


def _retry_card(retries: int, verdict: dict) -> str:
    feedback = escape(str(verdict.get("feedback", "Response needs revision.")))
    return (
        '<div class="mas-retry-card">'
        f'  <div class="mas-retry-title">&#9888; CRITIC REQUESTED REVISION</div>'
        f'  <div class="mas-retry-reason">Reason: {feedback}</div>'
        f'  <div class="mas-retry-count">Retry {retries} / 2 &mdash; Regenerating...</div>'
        '</div>'
    )


def render_pipeline(trace_log: list[dict[str, Any]]) -> None:
    """Render the vertical pipeline diagram."""
    states, retries, verdict = _derive_pipeline_states(trace_log)
    show_retry = retries > 0 and verdict.get("status") != "PASS"

    blocks: list[str] = []
    blocks.append(_pipeline_box(
        "retriever", "&#128269;", "RETRIEVER AGENT",
        "Searching knowledge base...", states["retriever"],
    ))
    blocks.append(_connector(states["generator"] != "idle"))
    blocks.append(_pipeline_box(
        "generator", "&#9997;&#65039;", "GENERATOR AGENT",
        "Generating draft response...", states["generator"],
    ))
    if show_retry:
        blocks.append(_retry_card(retries, verdict))
    blocks.append(_connector(states["critic"] != "idle"))
    blocks.append(_pipeline_box(
        "critic", "&#129488;", "CRITIC AGENT",
        "Evaluating safety and accuracy...", states["critic"],
    ))
    blocks.append(_connector(states["final"] != "idle"))
    blocks.append(_pipeline_box(
        "final", "&#128172;", "FINAL RESPONSE",
        "Delivered to user.", states["final"],
    ))

    st.markdown(
        '<div class="mas-pipeline">' + "".join(blocks) + "</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Terminal-style trace log
# ---------------------------------------------------------------------------
_PHASE_ICON = {
    "retriever": "&#128269;",
    "generator": "&#9997;&#65039;",
    "critic": "&#129488;",
    "orchestrator": "&#128172;",
}
_STEP_LABEL = {
    "retriever_query":      "Retriever: Query received",
    "retriever_embedding":  "Retriever: Embedding / scoring",
    "retriever_result":     "Retriever: Retrieval complete",
    "retriever_chunk":      "Retriever:   -",
    "retriever_output":     "Retriever: Chunks ready",
    "retriever_init":       "Retriever: Boot",
    "generator_build":      "Generator: Building prompt",
    "generator_prompt":     "Generator: Prompt composed",
    "generator_call":       "Generator: Calling LLM",
    "generator_response":   "Generator: Draft response generated",
    "generator_init":       "Generator: Boot",
    "critic_start":         "Critic: Evaluating draft",
    "critic_check":         "Critic:   -",
    "critic_prompt":        "Critic: Prompt composed",
    "critic_verdict":       "Critic: Verdict issued",
    "critic_init":          "Critic: Boot",
    "critic_retry":         "Orchestrator: Retry triggered",
    "final":                "Final: Response delivered to user",
    "orchestrator_init":    "Orchestrator: Ready",
    "orchestrator_step":    "Orchestrator: Pipeline started",
    "orchestrator":         "Orchestrator: Note",
}


def _format_event(event: dict[str, Any]) -> tuple[str, str, str]:
    """Return ``(label, colored_content, phase)`` for one trace event."""
    step = event["step"]
    phase = event["phase"]
    content = event["content"]

    # Collapse long prompts so the terminal stays tidy.
    if step in {"generator_prompt", "critic_prompt"}:
        content = f"(prompt length = {len(content)} chars)"
    if step == "critic_verdict":
        try:
            parsed = json.loads(content)
            status = str(parsed.get("status", "")).upper()
            fb = parsed.get("feedback", "")
            badge = "PASS" if status == "PASS" else "REVISE"
            content = f"Verdict -> {badge} | {fb}"
        except Exception:  # noqa: BLE001
            pass
    if step == "retriever_chunk":
        # Preview chunks are already truncated upstream; clean newlines.
        content = content.replace("\n", " ")

    label = _STEP_LABEL.get(step, f"{phase}: {step}")
    return label, content, phase


def render_trace_terminal(trace_log: list[dict[str, Any]]) -> None:
    """Render the colored terminal with every trace event."""
    lines_html: list[str] = []
    if not trace_log:
        lines_html.append(
            '<div class="trace-line muted">'
            '[--:--:--] Waiting for next query...'
            '</div>'
        )
    for event in trace_log:
        label, content, phase = _format_event(event)
        ts = escape(event.get("timestamp", "--:--:--"))
        safe_label = escape(label)
        safe_content = escape(content)
        verdict_badge = ""
        if event["step"] == "critic_verdict":
            if "PASS" in content:
                verdict_badge = '<span class="badge-pass">PASS</span>'
            elif "REVISE" in content:
                verdict_badge = '<span class="badge-revise">REVISE</span>'
        lines_html.append(
            f'<div class="trace-line phase-{phase}">'
            f'  <span class="trace-ts">[{ts}]</span> '
            f'  <span class="trace-icon">{_PHASE_ICON[phase]}</span> '
            f'  <span class="trace-label">{safe_label}</span>'
            f'  <span class="trace-content"> &mdash; {safe_content}</span>'
            f'  {verdict_badge}'
            f'</div>'
        )
    st.markdown(
        '<div class="trace-terminal">' + "".join(lines_html) + "</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Metrics strip
# ---------------------------------------------------------------------------
def render_metrics(metrics: dict[str, Any]) -> None:
    """Render the session metrics bar at the bottom of the right column."""
    total = int(metrics.get("total_queries", 0))
    pass_count = int(metrics.get("pass_count", 0))
    retries_total = int(metrics.get("retries_total", 0))
    chunks_total = int(metrics.get("chunks_total", 0))
    avg_rt = float(metrics.get("avg_response_time", 0.0))

    pass_rate = (pass_count / total * 100.0) if total else 0.0
    avg_retries = (retries_total / total) if total else 0.0

    st.markdown(
        '<div class="mas-metrics">'
        f'  <div class="mm"><div class="mm-lbl">Queries</div><div class="mm-val">{total}</div></div>'
        f'  <div class="mm"><div class="mm-lbl">Avg retries</div><div class="mm-val">{avg_retries:.1f}</div></div>'
        f'  <div class="mm"><div class="mm-lbl">PASS rate</div><div class="mm-val">{pass_rate:.0f}%</div></div>'
        f'  <div class="mm"><div class="mm-lbl">Avg time</div><div class="mm-val">{avg_rt:.1f}s</div></div>'
        f'  <div class="mm"><div class="mm-lbl">Chunks</div><div class="mm-val">{chunks_total}</div></div>'
        '</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# CSS injector (call once per render)
# ---------------------------------------------------------------------------
def inject_mas_css() -> None:
    st.markdown(
        """
        <style>
          .mas-panel-title {
            font-family: 'Orbitron', sans-serif;
            letter-spacing: 4px;
            color: #00d4aa;
            font-size: 14px;
            margin-bottom: 10px;
            text-transform: uppercase;
          }
          .mas-pipeline {
            display: flex; flex-direction: column; gap: 6px;
            margin-bottom: 14px;
            width: 100%;
          }
          .mas-box {
            background: #161b22; border: 1px solid #222c37;
            border-radius: 12px; padding: 10px 12px;
            transition: all 0.3s ease;
            position: relative;
            width: 100%; max-width: 100%;
            box-sizing: border-box;
            overflow: hidden;
          }
          .mas-box-head {
            display: flex; align-items: center; gap: 8px;
            font-family: 'Orbitron', sans-serif; font-size: 12px;
            color: #e6edf3; letter-spacing: 2px;
            min-width: 0;
          }
          .mas-icon { font-size: 16px; flex-shrink: 0; }
          .mas-title {
            flex: 1; min-width: 0;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }
          .mas-sub {
            font-size: 11px; color: #8b949e; margin-top: 4px;
            overflow: hidden; text-overflow: ellipsis;
            word-wrap: break-word;
          }

          .mas-retriever.mas-active   { border-color: #00d4aa; box-shadow: 0 0 0 2px rgba(0,212,170,0.25); }
          .mas-generator.mas-active   { border-color: #1f6feb; box-shadow: 0 0 0 2px rgba(31,111,235,0.3); }
          .mas-critic.mas-active      { border-color: #d29922; box-shadow: 0 0 0 2px rgba(210,153,34,0.3); }
          .mas-final.mas-active       { border-color: #3fb950; box-shadow: 0 0 0 2px rgba(63,185,80,0.3); }
          .mas-active { animation: masPulse 1.4s ease-in-out infinite; }
          .mas-done    { border-color: rgba(63,185,80,0.55); background: #142018; }
          .mas-warn    { border-color: rgba(248,81,73,0.6); background: #1f1414; animation: masShake 0.3s ease-in-out 2; }

          .mas-spinner {
            width: 12px; height: 12px; border-radius: 50%;
            border: 2px solid rgba(0,212,170,0.25);
            border-top-color: #00d4aa;
            animation: spin 0.8s linear infinite;
          }
          .mas-check { color: #3fb950; font-weight: 800; }

          .mas-connector {
            align-self: center; height: 22px; width: 4px; border-radius: 4px;
            background: #222c37; position: relative; overflow: hidden;
          }
          .mas-connector.active { background: #0d2a26; }
          .mas-connector.active span {
            position: absolute; left: 0; width: 4px; height: 6px;
            background: #00d4aa; border-radius: 3px;
            animation: flow 1.1s linear infinite;
          }
          .mas-connector.active span:nth-child(2) { animation-delay: 0.3s; }
          .mas-connector.active span:nth-child(3) { animation-delay: 0.6s; }

          .mas-retry-card {
            border: 1px solid rgba(248,81,73,0.6);
            background: linear-gradient(180deg, rgba(248,81,73,0.1), rgba(248,81,73,0.02));
            color: #ffc8c3; padding: 10px 12px; border-radius: 10px;
            margin: 4px 0;
            animation: masShake 0.35s ease-in-out 3;
          }
          .mas-retry-title    { font-family: 'Orbitron', sans-serif; font-size: 12px; letter-spacing: 2px; color: #ff7a70; }
          .mas-retry-reason   { font-size: 11px; margin-top: 4px; color: #e6edf3; }
          .mas-retry-count    { font-size: 11px; margin-top: 4px; color: #f85149; font-weight: 700; }

          .trace-terminal {
            background: #0d1117;
            border: 1px solid #222c37;
            border-radius: 10px;
            padding: 10px 12px;
            max-height: 340px;
            overflow-y: auto;
            font-family: 'Fira Code', 'Courier New', monospace;
            font-size: 11.5px;
            line-height: 1.55;
            white-space: pre-wrap;
          }
          .trace-line { animation: traceIn 0.25s ease-out; }
          .trace-line.muted { color: #6e7681; font-style: italic; }
          .trace-ts      { color: #6e7681; }
          .trace-icon    { margin: 0 4px; }
          .trace-label   { font-weight: 600; }
          .trace-content { color: #c9d1d9; }
          .phase-retriever    .trace-label { color: #58a6ff; }
          .phase-generator    .trace-label { color: #7ee787; }
          .phase-critic       .trace-label { color: #e3b341; }
          .phase-orchestrator .trace-label { color: #e6edf3; }
          .badge-pass {
            background: rgba(63,185,80,0.18); color: #3fb950;
            padding: 1px 6px; border-radius: 4px; margin-left: 6px;
            font-weight: 800; font-size: 10px;
          }
          .badge-revise {
            background: rgba(248,81,73,0.18); color: #f85149;
            padding: 1px 6px; border-radius: 4px; margin-left: 6px;
            font-weight: 800; font-size: 10px;
          }

          .mas-metrics {
            display: grid;
            grid-template-columns: repeat(5, minmax(80px, 1fr));
            gap: 6px; margin-top: 10px;
          }
          .mm {
            background: #161b22; border: 1px solid #222c37;
            border-radius: 8px; padding: 6px 4px; text-align: center;
            min-width: 80px;
            overflow: hidden;
          }
          .mm-lbl {
            color: #8b949e; font-family: 'Orbitron', sans-serif;
            font-size: 9px; letter-spacing: 2px;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
          }
          .mm-val {
            color: #00d4aa; font-family: 'Orbitron', sans-serif;
            font-size: 16px; font-weight: 700; margin-top: 2px;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
          }

          @keyframes masPulse  { 0%,100% { transform: translateY(0); }
                                 50%     { transform: translateY(-2px); } }
          @keyframes masShake  { 0%,100% { transform: translateX(0); }
                                 25% { transform: translateX(-3px); }
                                 75% { transform: translateX(3px); } }
          @keyframes spin      { from { transform: rotate(0deg); }
                                 to   { transform: rotate(360deg); } }
          @keyframes flow      { 0% { top: -8px; opacity: 0; }
                                 30% { opacity: 1; }
                                 100% { top: 100%; opacity: 0; } }
          @keyframes traceIn   { from { opacity: 0; transform: translateY(4px); }
                                 to   { opacity: 1; transform: translateY(0); } }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Orchestrating render
# ---------------------------------------------------------------------------
def render_panel(
    trace_log: list[dict[str, Any]] | None,
    metrics: dict[str, Any] | None,
    agent_letter: str,
) -> None:
    """Render the full right-panel for the given agent.

    When Agent A is active the panel shows a simple explanatory card
    instead of the MAS trace, since Agent A has no sub-agents.
    """
    inject_mas_css()
    st.markdown(
        '<div class="mas-panel-title">MAS Live Trace</div>',
        unsafe_allow_html=True,
    )

    if agent_letter.upper() == "A":
        st.markdown(
            '<div class="mas-box mas-done">'
            '<div class="mas-box-head"><span class="mas-icon">&#9889;</span>'
            '<span class="mas-title">AGENT A (RULE-BASED)</span></div>'
            '<div class="mas-sub">No Multi-Agent System in rule-based mode. '
            'Switch to Agent B to see the live retriever / generator / critic pipeline.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        return

    render_pipeline(trace_log or [])
    st.markdown(
        '<div class="mas-panel-title" style="margin-top:12px">Trace Log</div>',
        unsafe_allow_html=True,
    )
    render_trace_terminal(trace_log or [])

    st.markdown(
        '<div class="mas-panel-title" style="margin-top:12px">Session Metrics</div>',
        unsafe_allow_html=True,
    )
    render_metrics(metrics or {})


__all__ = [
    "build_trace_listener",
    "render_panel",
    "render_pipeline",
    "render_trace_terminal",
    "render_metrics",
    "inject_mas_css",
]
