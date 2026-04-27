"""
Animated DineBot SVG renderer (robot only).

The restaurant floor map lives in :mod:`ui.floor_map`; this module is now
focused purely on the cute delivery robot and its per-state CSS keyframe
animations, exactly as specified in the project brief.

Exports
-------
* :data:`ROBOT_STATES`        – canonical state list.
* :func:`compute_state`        – infer the next robot state from chat text.
* :func:`render_robot_html`    – return a self-contained HTML block for
  :func:`streamlit.components.v1.html`.
* :func:`target_table_from_text` – extract ``table <N>`` from a message.
"""

from __future__ import annotations

import re
from textwrap import dedent

from utils.table_parser import (
    is_servable_table,
    mentioned_table_number,
    target_table_from_text as parse_target_table,
)

ROBOT_STATES: list[str] = [
    "IDLE",
    "LOADING",
    "DELIVERING",
    "WAITING",
    "RETURNING",
    "EMERGENCY",
    "LOW_BATTERY",
]


def compute_state(
    current_state: str,
    last_user_msg: str = "",
    last_bot_msg: str = "",
    battery: float = 100.0,
) -> str:
    """Infer the robot's next state from recent chat content.

    Rules (first match wins):
      * User types STOP / emergency / fire / spill / obstacle -> EMERGENCY.
      * Battery <= 20% -> LOW_BATTERY (unless in EMERGENCY).
      * Bot response contains "arrived" / "waiting" -> WAITING.
      * Bot response contains "returning" / "back to dock" -> RETURNING.
      * User or bot mentions "loading" / "kitchen" -> LOADING.
      * User mentions deliver / bring / "table N" -> DELIVERING.
      * Otherwise stay in the current state (default IDLE).
    """
    u = (last_user_msg or "").lower().strip()
    b = (last_bot_msg or "").lower()

    emergency_keywords = (
        "stop", "emergency", "fire", "spill", "obstacle",
        "collision", "evacuate", "danger",
    )
    # Require a whole-word match for "stop" so "stop by" / "shop stop" still
    # trigger but single words like "stopped" do not accidentally fire.
    if any(re.search(rf"\b{kw}\b", u) for kw in emergency_keywords):
        return "EMERGENCY"

    if battery <= 20:
        return "LOW_BATTERY"

    if "arrived" in b or "waiting for" in b:
        return "WAITING"
    if "returning" in b or "back to dock" in b or "return to dock" in b:
        return "RETURNING"
    if "loading" in b or "loading" in u or "at the kitchen" in b:
        return "LOADING"

    deliver_keywords = (
        "deliver", "bring", "carry", "take to table", "send to table",
    )
    mentioned_table = mentioned_table_number(u)
    if mentioned_table is not None:
        if is_servable_table(mentioned_table):
            return "DELIVERING"
        return current_state or "IDLE"

    if any(kw in u for kw in deliver_keywords):
        return "DELIVERING"

    return current_state or "IDLE"


def target_table_from_text(text: str) -> int | None:
    """Pull a table number from a message; ``None`` if absent or out of range."""
    return parse_target_table(text)


def _robot_svg(state: str, battery: float) -> str:
    """Return the cute delivery robot SVG with state-driven CSS hooks."""
    battery_pct = max(0.0, min(100.0, float(battery)))
    battery_w = int(round(40 * (battery_pct / 100.0)))
    battery_color = (
        "#3fb950" if battery_pct > 50
        else "#d29922" if battery_pct > 20
        else "#f85149"
    )
    state_label = state.replace("_", " ")
    return dedent(
        f"""
        <svg viewBox="0 0 360 360" class="robot-svg" preserveAspectRatio="xMidYMid meet">
          <defs>
            <linearGradient id="chassis" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#1f2a36"/>
              <stop offset="100%" stop-color="#0f141b"/>
            </linearGradient>
            <radialGradient id="eyeGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stop-color="#ffffff" stop-opacity="0.9"/>
              <stop offset="100%" stop-color="#00d4aa" stop-opacity="0.0"/>
            </radialGradient>
            <!-- Clip the chest screen so the STATE label can never spill out. -->
            <clipPath id="chestClip">
              <rect x="112" y="182" width="136" height="56" rx="8"/>
            </clipPath>
          </defs>

          <ellipse cx="180" cy="340" rx="110" ry="10" fill="#000" opacity="0.45"/>

          <g class="robot-body">
            <g class="antenna">
              <line x1="140" y1="50" x2="130" y2="20" stroke="#00d4aa" stroke-width="3"/>
              <circle cx="130" cy="18" r="5" fill="#00d4aa"/>
              <line x1="220" y1="50" x2="230" y2="20" stroke="#00d4aa" stroke-width="3"/>
              <circle cx="230" cy="18" r="5" fill="#00d4aa"/>
            </g>

            <g class="tray">
              <rect x="90" y="60" width="180" height="16" rx="6"
                    fill="#00d4aa" stroke="#0d1117" stroke-width="2"/>
              <rect x="110" y="50" width="40" height="14" rx="3" fill="#f85149" opacity="0.85"/>
              <rect x="160" y="50" width="40" height="14" rx="3" fill="#d29922" opacity="0.85"/>
              <rect x="210" y="50" width="40" height="14" rx="3" fill="#3fb950" opacity="0.85"/>
            </g>

            <rect x="110" y="76" width="140" height="70" rx="18"
                  fill="url(#chassis)" stroke="#00d4aa" stroke-width="2"/>

            <g class="eyes">
              <circle cx="150" cy="112" r="16" fill="#0d1117" stroke="#00d4aa" stroke-width="2"/>
              <circle cx="210" cy="112" r="16" fill="#0d1117" stroke="#00d4aa" stroke-width="2"/>
              <circle cx="150" cy="112" r="20" fill="url(#eyeGlow)" class="eye-glow"/>
              <circle cx="210" cy="112" r="20" fill="url(#eyeGlow)" class="eye-glow"/>
              <circle cx="150" cy="112" r="6" fill="#00d4aa" class="pupil pupil-left"/>
              <circle cx="210" cy="112" r="6" fill="#00d4aa" class="pupil pupil-right"/>
              <rect x="134" y="108" width="32" height="8" class="eye-lid eye-lid-left" fill="#0d1117"/>
              <rect x="194" y="108" width="32" height="8" class="eye-lid eye-lid-right" fill="#0d1117"/>
            </g>

            <rect x="160" y="146" width="40" height="12" fill="#1f2a36" stroke="#00d4aa" stroke-width="1"/>
            <rect x="80" y="158" width="200" height="140" rx="22"
                  fill="url(#chassis)" stroke="#00d4aa" stroke-width="2"/>

            <rect x="110" y="180" width="140" height="60" rx="10"
                  fill="#0d1117" stroke="#00d4aa" stroke-width="2"/>
            <g clip-path="url(#chestClip)">
              <text x="180" y="202" text-anchor="middle" dominant-baseline="central"
                    font-family="Orbitron, sans-serif" font-size="10"
                    fill="#00d4aa" letter-spacing="2">STATE</text>
              <text x="180" y="222" text-anchor="middle" dominant-baseline="central"
                    font-family="Orbitron, sans-serif" font-size="11"
                    fill="#e6edf3" letter-spacing="1"
                    class="screen-state">{state_label}</text>
            </g>

            <g class="battery-badge" transform="translate(138,250)">
              <rect x="0" y="0" width="44" height="16" rx="3" fill="none"
                    stroke="#30363d" stroke-width="2"/>
              <rect x="44" y="5" width="4" height="6" fill="#30363d"/>
              <rect x="2" y="2" width="{battery_w}" height="12" rx="2"
                    fill="{battery_color}" class="battery-fill"/>
              <text x="58" y="13" font-family="Orbitron, sans-serif" font-size="11"
                    fill="#e6edf3">{int(battery_pct)}%</text>
            </g>

            <g class="door">
              <rect x="100" y="272" width="160" height="22" rx="4"
                    fill="#161b22" stroke="#00d4aa" stroke-width="1"/>
              <line x1="180" y1="274" x2="180" y2="292" stroke="#00d4aa" stroke-width="1"/>
            </g>

            <rect x="60" y="180" width="18" height="70" rx="8"
                  fill="#1f2a36" stroke="#00d4aa" stroke-width="1"/>
            <rect x="282" y="180" width="18" height="70" rx="8"
                  fill="#1f2a36" stroke="#00d4aa" stroke-width="1"/>

            <g class="wheels">
              <circle cx="120" cy="310" r="22" fill="#0d1117" stroke="#00d4aa" stroke-width="3"/>
              <line x1="120" y1="290" x2="120" y2="330" stroke="#00d4aa" stroke-width="2" class="wheel-spoke"/>
              <line x1="100" y1="310" x2="140" y2="310" stroke="#00d4aa" stroke-width="2" class="wheel-spoke"/>
              <circle cx="240" cy="310" r="22" fill="#0d1117" stroke="#00d4aa" stroke-width="3"/>
              <line x1="240" y1="290" x2="240" y2="330" stroke="#00d4aa" stroke-width="2" class="wheel-spoke"/>
              <line x1="220" y1="310" x2="260" y2="310" stroke="#00d4aa" stroke-width="2" class="wheel-spoke"/>
            </g>
          </g>
        </svg>
        """
    ).strip()


def render_robot_html(state: str, battery: float = 100.0) -> str:
    """Return a self-contained HTML block rendering the animated robot.

    Pass the result to ``st.components.v1.html``. Animations are entirely
    CSS driven, triggered by ``data-state="<STATE>"`` on the stage div.
    """
    if state not in ROBOT_STATES:
        state = "IDLE"
    robot = _robot_svg(state, battery)
    css = _ROBOT_CSS
    return (
        "<!doctype html><html><head><meta charset='utf-8'/>"
        "<link href='https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700"
        "&family=Inter:wght@400;600&display=swap' rel='stylesheet'>"
        f"<style>{css}</style></head><body>"
        f"<div class='stage' data-state='{state}'>"
        f"  <div class='robot-card'>"
        f"    <div class='card-title'>"
        f"      <span>DineBot Unit</span>"
        f"      <span class='state-badge {state}'>{state.replace('_',' ')}</span>"
        f"    </div>"
        f"    {robot}"
        f"  </div>"
        f"</div></body></html>"
    )


# ---------------------------------------------------------------------------
# CSS (kept separate to keep ``render_robot_html`` readable)
# ---------------------------------------------------------------------------
_ROBOT_CSS = """
:root {
  --bg: #0d1117; --card: #161b22; --accent: #00d4aa; --blue: #1f6feb;
  --danger: #f85149; --warn: #d29922; --ok: #3fb950; --text: #e6edf3;
  --muted: #8b949e;
}
* { box-sizing: border-box; }
html, body {
  margin: 0; padding: 0;
  background: radial-gradient(1000px 500px at 30% -10%, #16232f 0%, var(--bg) 60%, #05070a 100%);
  color: var(--text); font-family: 'Inter', sans-serif; overflow: hidden;
}
.stage { width: 100%; padding: 12px; }
.robot-card {
  background: var(--card); border: 1px solid #222c37; border-radius: 18px;
  padding: 14px;
  box-shadow: 0 18px 46px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.03);
}
.card-title {
  display: flex; justify-content: space-between; align-items: center;
  font-family: 'Orbitron', sans-serif; letter-spacing: 3px;
  color: var(--accent); font-size: 12px; text-transform: uppercase;
  margin-bottom: 10px;
}
.state-badge {
  padding: 4px 10px; border-radius: 999px;
  font-family: 'Orbitron', sans-serif; font-size: 11px; letter-spacing: 2px;
  background: rgba(0,212,170,0.12); color: var(--accent);
  border: 1px solid rgba(0,212,170,0.4);
}
.state-badge.EMERGENCY    { background: rgba(248,81,73,0.15); color: var(--danger); border-color: rgba(248,81,73,0.5); }
.state-badge.LOW_BATTERY  { background: rgba(210,153,34,0.15); color: var(--warn);   border-color: rgba(210,153,34,0.5); }
.state-badge.DELIVERING   { background: rgba(31,111,235,0.15); color: var(--blue);   border-color: rgba(31,111,235,0.5); }
.state-badge.RETURNING    { background: rgba(63,185,80,0.15);  color: var(--ok);     border-color: rgba(63,185,80,0.5); }
.robot-svg { width: 100%; height: 320px; display: block; }

.robot-body { transform-origin: 180px 220px; transform-box: fill-box; }
.wheels circle { transform-origin: center; transform-box: fill-box; }
.wheel-spoke { transform-origin: center; transform-box: fill-box; }

[data-state="IDLE"] .robot-body { animation: bob 3s ease-in-out infinite; }
[data-state="IDLE"] .eye-lid    { animation: blink 4.2s ease-in-out infinite; }
[data-state="IDLE"] .eye-glow   { animation: glow 3.5s ease-in-out infinite; }

[data-state="LOADING"] .tray     { animation: trayLift 1.4s ease-in-out infinite; transform-origin: center; transform-box: fill-box; }
[data-state="LOADING"] .door     { animation: doorFlicker 1.2s ease-in-out infinite; transform-origin: center; transform-box: fill-box; }
[data-state="LOADING"] .eye-glow { animation: glow 1.5s ease-in-out infinite; }

[data-state="DELIVERING"] .robot-body  { animation: slide 3.5s ease-in-out infinite; }
[data-state="DELIVERING"] .wheels line { animation: spin 0.5s linear infinite; }
[data-state="DELIVERING"] .antenna     { animation: wiggle 0.7s ease-in-out infinite; transform-origin: 180px 50px; transform-box: fill-box; }
[data-state="DELIVERING"] .eye-glow    { animation: glow 1.8s ease-in-out infinite; }

[data-state="WAITING"] .pupil-left  { animation: scanL 2.4s ease-in-out infinite; }
[data-state="WAITING"] .pupil-right { animation: scanR 2.4s ease-in-out infinite; }
[data-state="WAITING"] .eye-glow    { animation: glow 1.2s ease-in-out infinite; }
[data-state="WAITING"] .robot-body  { animation: bob 2.4s ease-in-out infinite; }

[data-state="RETURNING"] .robot-body   { animation: slideReverse 3.5s ease-in-out infinite; }
[data-state="RETURNING"] .wheels line  { animation: spinReverse 0.5s linear infinite; }
[data-state="RETURNING"] .eye-glow     { animation: glow 2.5s ease-in-out infinite; }

[data-state="EMERGENCY"] .robot-body     { animation: shake 0.25s linear infinite; }
[data-state="EMERGENCY"] .eye-glow       { animation: redFlash 0.7s ease-in-out infinite; }
[data-state="EMERGENCY"] .pupil          { fill: var(--danger); }
[data-state="EMERGENCY"] .antenna circle { fill: var(--danger); }

[data-state="LOW_BATTERY"] .robot-body    { animation: bob 5s ease-in-out infinite; }
[data-state="LOW_BATTERY"] .battery-fill  { animation: batteryBlink 0.9s ease-in-out infinite; }
[data-state="LOW_BATTERY"] .eye-glow      { animation: glow 4s ease-in-out infinite; }

@keyframes bob         { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-6px); } }
@keyframes blink       { 0%,90%,100% { transform: scaleY(0); } 94% { transform: scaleY(1); } }
@keyframes glow        { 0%,100% { opacity: 0.25; } 50% { opacity: 0.9; } }
@keyframes trayLift    { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
@keyframes doorFlicker { 0%,100% { opacity: 1; } 50% { opacity: 0.4; } }
@keyframes slide       { 0%,100% { transform: translateX(-14px); } 50% { transform: translateX(14px); } }
@keyframes slideReverse{ 0%,100% { transform: translateX(14px); } 50% { transform: translateX(-14px); } }
@keyframes spin        { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
@keyframes spinReverse { from { transform: rotate(0deg); } to { transform: rotate(-360deg); } }
@keyframes wiggle      { 0%,100% { transform: rotate(-4deg); } 50% { transform: rotate(4deg); } }
@keyframes scanL       { 0%,100% { transform: translateX(-5px); } 50% { transform: translateX(5px); } }
@keyframes scanR       { 0%,100% { transform: translateX(-5px); } 50% { transform: translateX(5px); } }
@keyframes shake       { 0%,100% { transform: translate(0,0); } 25% { transform: translate(3px,-2px); } 75% { transform: translate(-3px,2px); } }
@keyframes redFlash    { 0%,100% { opacity: 0.3; filter: hue-rotate(0); } 50% { opacity: 1; filter: hue-rotate(-120deg) saturate(2); } }
@keyframes batteryBlink{ 0%,100% { opacity: 0.3; } 50% { opacity: 1; } }
"""
