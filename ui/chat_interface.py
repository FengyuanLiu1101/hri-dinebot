"""
Chat UI helpers for the DineBot Streamlit app.

Renders the chat bubbles (user on the right, robot on the left with a
custom mini-robot SVG avatar consistent with the main robot design),
a three-dot typing indicator, and an agent badge (A or B).
"""

from __future__ import annotations

from html import escape
from typing import Any

import streamlit as st

# ---------------------------------------------------------------------------
# Mini robot SVG avatar (matches the main robot head)
# ---------------------------------------------------------------------------
_ROBOT_AVATAR_SVG = (
    "<svg viewBox='0 0 40 40' xmlns='http://www.w3.org/2000/svg'>"
    "  <rect x='8' y='10' width='24' height='22' rx='6'"
    "        fill='#0f141b' stroke='#00d4aa' stroke-width='2'/>"
    "  <circle cx='15' cy='20' r='3' fill='#00d4aa'/>"
    "  <circle cx='25' cy='20' r='3' fill='#00d4aa'/>"
    "  <line x1='15' y1='10' x2='14' y2='5' stroke='#00d4aa' stroke-width='2'/>"
    "  <circle cx='14' cy='4' r='1.5' fill='#00d4aa'/>"
    "  <line x1='25' y1='10' x2='26' y2='5' stroke='#00d4aa' stroke-width='2'/>"
    "  <circle cx='26' cy='4' r='1.5' fill='#00d4aa'/>"
    "  <rect x='12' y='26' width='16' height='3' rx='1' fill='#00d4aa' opacity='0.6'/>"
    "</svg>"
)

_USER_AVATAR_SVG = (
    "<svg viewBox='0 0 40 40' xmlns='http://www.w3.org/2000/svg'>"
    "  <circle cx='20' cy='15' r='7' fill='none' stroke='#79b8ff' stroke-width='2'/>"
    "  <path d='M 6 34 C 8 26, 32 26, 34 34' fill='none'"
    "        stroke='#79b8ff' stroke-width='2' stroke-linecap='round'/>"
    "</svg>"
)


def inject_chat_css() -> None:
    """Inject chat-specific CSS (call once per render)."""
    st.markdown(
        """
        <style>
          .dinebot-chat {
            display: flex; flex-direction: column;
            gap: 10px;
            max-height: 360px;
            min-height: 120px;
            overflow-y: auto;
            padding: 8px 6px;
            background: #0d1117;
            border: 1px solid #222c37;
            border-radius: 14px;
          }
          .bubble-row { display: flex; align-items: flex-end; gap: 10px; animation: fadein 0.35s ease-out; }
          .bubble-row.user { flex-direction: row-reverse; }
          .bubble {
            max-width: 78%; padding: 10px 14px; border-radius: 14px;
            font-family: 'Inter', sans-serif; font-size: 14px; line-height: 1.45;
            white-space: pre-wrap; word-break: break-word;
            box-shadow: 0 6px 18px rgba(0,0,0,0.25);
          }
          .bubble.robot {
            background: #161b22; color: #e6edf3;
            border-left: 3px solid #00d4aa;
            border-bottom-left-radius: 4px;
          }
          .bubble.user {
            background: linear-gradient(135deg, #1f6feb, #1158c7);
            color: #ffffff; border-bottom-right-radius: 4px;
          }
          .avatar {
            width: 38px; height: 38px; min-width: 38px;
            border-radius: 50%;
            display: inline-flex; align-items: center; justify-content: center;
            background: #0d1117; border: 1px solid #222c37;
            overflow: hidden;
          }
          .avatar svg { width: 28px; height: 28px; }
          .avatar.robot { border-color: rgba(0,212,170,0.5); }
          .avatar.user  { border-color: rgba(31,111,235,0.5); }

          .agent-badge {
            display: inline-block;
            padding: 4px 10px; border-radius: 999px;
            font-family: 'Orbitron', sans-serif; font-size: 11px;
            letter-spacing: 2px; text-transform: uppercase; margin-bottom: 8px;
          }
          .agent-badge.A { background: rgba(31,111,235,0.15); color: #79b8ff;
                           border: 1px solid rgba(31,111,235,0.4); }
          .agent-badge.B { background: rgba(0,212,170,0.15);  color: #00d4aa;
                           border: 1px solid rgba(0,212,170,0.4); }

          .typing {
            display: inline-flex; gap: 4px; padding: 10px 14px;
            background: #161b22; border-radius: 14px;
            border-left: 3px solid #00d4aa;
          }
          .typing span {
            width: 6px; height: 6px; border-radius: 50%;
            background: #00d4aa; opacity: 0.5;
            animation: typing 1.2s infinite ease-in-out;
          }
          .typing span:nth-child(2) { animation-delay: 0.15s; }
          .typing span:nth-child(3) { animation-delay: 0.30s; }

          @keyframes typing {
            0%,80%,100% { opacity: 0.3; transform: translateY(0); }
            40%         { opacity: 1;   transform: translateY(-3px); }
          }
          @keyframes fadein {
            from { opacity: 0; transform: translateY(6px); }
            to   { opacity: 1; transform: translateY(0); }
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_agent_badge(agent_letter: str) -> None:
    """Render the A/B agent badge above the chat history."""
    letter = agent_letter.upper()
    label = (
        "Agent A - Rule-Based | No API"
        if letter == "A"
        else "Agent B - RAG + MAS | GPT-4o-mini"
    )
    st.markdown(
        f'<span class="agent-badge {letter}">{label}</span>',
        unsafe_allow_html=True,
    )


def _bubble(role: str, content: str) -> str:
    role_cls = "user" if role == "user" else "robot"
    avatar_svg = _USER_AVATAR_SVG if role == "user" else _ROBOT_AVATAR_SVG
    safe = escape(content or "").replace("\n", "<br/>")
    return (
        f'<div class="bubble-row {role_cls}">'
        f'  <div class="avatar {role_cls}">{avatar_svg}</div>'
        f'  <div class="bubble {role_cls}">{safe}</div>'
        f"</div>"
    )


def render_history(messages: list[dict[str, Any]]) -> None:
    """Render the full chat history as stacked bubbles."""
    if not messages:
        st.markdown(
            '<div class="dinebot-chat" style="align-items:center;justify-content:center;color:#8b949e">'
            '<div style="padding:20px;text-align:center">'
            "Say hello to DineBot &middot; try <b>\"Deliver pizza to table 7\"</b>"
            '</div></div>',
            unsafe_allow_html=True,
        )
        return
    parts = ['<div class="dinebot-chat" id="dinebot-chat">']
    for m in messages:
        parts.append(_bubble(m.get("role", "robot"), m.get("content", "")))
    parts.append("</div>")
    # Auto-scroll to bottom on each render.
    parts.append(
        "<script>(function(){var el=document.getElementById('dinebot-chat');"
        "if(el){el.scrollTop=el.scrollHeight;}})();</script>"
    )
    st.markdown("".join(parts), unsafe_allow_html=True)


def render_typing_indicator() -> None:
    """Render the animated three-dot typing indicator."""
    st.markdown(
        '<div class="bubble-row robot">'
        f'  <div class="avatar robot">{_ROBOT_AVATAR_SVG}</div>'
        '  <div class="typing"><span></span><span></span><span></span></div>'
        "</div>",
        unsafe_allow_html=True,
    )


__all__ = [
    "inject_chat_css",
    "render_agent_badge",
    "render_history",
    "render_typing_indicator",
]
