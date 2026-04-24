"""
Restaurant floor map with live delivery path animation.

This module renders an 800x580 SVG top-down floor plan with:

* Docking station (bottom-center, charging-pad icon with lightning bolt).
* Kitchen pickup counter (top-center).
* Main dining area (left, tables 1-10 in a 2x5 grid).
* Private dining room (right, tables 16-20 in a 1x5 column, wall separator).
* Outdoor terrace (top-right, tables 11-15, hatched and marked restricted).
* A teal robot dot with a "DineBot" label that moves smoothly along the
  delivery path via JavaScript ``setTimeout`` sequencing.
* A three-segment animated dashed path
  DOCK -> KITCHEN (blue) -> TARGET TABLE (teal) -> DOCK (orange) that
  highlights the active phase, shades upcoming segments, and fades the
  full path out two seconds after arrival at the dock.

The public entry point is :func:`render_floor_map_html`, intended for
``streamlit.components.v1.html``.
"""

from __future__ import annotations

from textwrap import dedent

# ---------------------------------------------------------------------------
# Hardcoded map coordinates (SVG space is 800 x 580)
# ---------------------------------------------------------------------------
DOCK_XY: tuple[int, int] = (400, 520)
KITCHEN_XY: tuple[int, int] = (400, 60)

TABLE_COORDS: dict[int, tuple[int, int]] = {
    1:  (80, 180),  2:  (160, 180),
    3:  (80, 260),  4:  (160, 260),
    5:  (80, 340),  6:  (160, 340),
    7:  (80, 420),  8:  (160, 420),
    9:  (240, 180), 10: (240, 260),
    # Terrace (restricted)
    11: (520, 60),  12: (560, 60),  13: (600, 60),  14: (640, 60),  15: (680, 60),
    # Private dining room
    16: (580, 160), 17: (580, 230), 18: (580, 300), 19: (580, 370), 20: (580, 440),
}
TERRACE_TABLES: set[int] = {11, 12, 13, 14, 15}

_SVG_W = 800
_SVG_H = 580


def _table_rect(
    n: int, x: int, y: int, target: int | None, completed: bool
) -> str:
    """Render a single table as a rounded rect + numeric label."""
    is_terrace = n in TERRACE_TABLES
    is_target = target == n
    is_complete = completed and is_target

    classes = ["table"]
    if is_terrace:
        classes.append("table-restricted")
    elif is_complete:
        classes.append("table-complete")
    elif is_target:
        classes.append("table-target")

    cls = " ".join(classes)
    rect = (
        f'<rect class="{cls}" x="{x - 20}" y="{y - 16}" width="40" height="32"'
        f' rx="6" ry="6" data-table-id="{n}"/>'
    )
    label = (
        f'<text class="table-label" x="{x}" y="{y + 4}" text-anchor="middle"'
        f' font-family="Orbitron, sans-serif" font-size="13" font-weight="700">'
        f"{n}</text>"
    )
    extra = ""
    if is_terrace:
        # Red X overlay on restricted tables.
        extra = (
            f'<line x1="{x - 10}" y1="{y - 10}" x2="{x + 10}" y2="{y + 10}"'
            f' stroke="#f85149" stroke-width="2"/>'
            f'<line x1="{x - 10}" y1="{y + 10}" x2="{x + 10}" y2="{y - 10}"'
            f' stroke="#f85149" stroke-width="2"/>'
        )
    return f'<g class="table-group">{rect}{label}{extra}</g>'


def _static_layout_svg(
    target_table: int | None, delivery_completed: bool
) -> str:
    """Build the non-animated part of the map (zones, tables, dock, etc.)."""
    tables_svg = "\n".join(
        _table_rect(n, x, y, target_table, delivery_completed)
        for n, (x, y) in TABLE_COORDS.items()
    )

    dock_x, dock_y = DOCK_XY
    kitchen_x, kitchen_y = KITCHEN_XY

    return dedent(
        f"""
        <!-- Zone backgrounds -->
        <rect class="zone-main"    x="20"  y="120" width="280" height="420" rx="16"/>
        <rect class="zone-private" x="500" y="120" width="280" height="420" rx="16"/>
        <rect class="zone-terrace" x="500" y="20"  width="280" height="80"  rx="10"
              fill="url(#terraceHatch)"/>

        <!-- Wall separating main dining from private room -->
        <line class="wall" x1="380" y1="120" x2="380" y2="540"/>

        <!-- Zone labels -->
        <text class="zone-label main"    x="40"  y="148">MAIN DINING</text>
        <text class="zone-label private" x="520" y="148">PRIVATE DINING</text>
        <text class="zone-label terrace" x="520" y="48">TERRACE (NO ROBOT)</text>

        <!-- Kitchen counter (top center) -->
        <g class="kitchen">
          <rect x="{kitchen_x - 120}" y="{kitchen_y - 22}" width="240" height="44"
                rx="6" fill="#161b22" stroke="#00d4aa" stroke-width="2"/>
          <text x="{kitchen_x}" y="{kitchen_y + 6}" text-anchor="middle"
                font-family="Orbitron, sans-serif" font-size="13" fill="#00d4aa"
                letter-spacing="2">KITCHEN (PICKUP COUNTER)</text>
        </g>

        <!-- Docking station (bottom center) with lightning bolt -->
        <g class="dock">
          <circle cx="{dock_x}" cy="{dock_y}" r="42" class="dock-glow"/>
          <rect x="{dock_x - 30}" y="{dock_y - 22}" width="60" height="44" rx="8"
                fill="#0d1117" stroke="#00d4aa" stroke-width="2"/>
          <polygon points="{dock_x - 6},{dock_y - 14} {dock_x + 4},{dock_y - 2}
                           {dock_x - 2},{dock_y - 2} {dock_x + 6},{dock_y + 14}
                           {dock_x - 4},{dock_y + 2} {dock_x + 2},{dock_y + 2}"
                   fill="#00d4aa"/>
          <text x="{dock_x}" y="{dock_y + 36}" text-anchor="middle"
                font-family="Orbitron, sans-serif" font-size="11" fill="#00d4aa"
                letter-spacing="3">DOCK</text>
        </g>

        <!-- Tables -->
        {tables_svg}
        """
    ).strip()


def render_floor_map_html(
    robot_state: str,
    target_table: int | None,
    delivery_completed: bool = False,
    trigger_id: str | int = 0,
) -> str:
    """Render the full floor map HTML block.

    Parameters
    ----------
    robot_state:
        Current robot state (drives dot color / aura).
    target_table:
        Table to animate toward. ``None`` keeps the robot docked.
    delivery_completed:
        If ``True``, show the gold "completed" flash on the target table.
    trigger_id:
        Monotonically increasing value. Changing it forces the iframe to
        restart the delivery animation even if the target table is the same.
    """
    state = robot_state or "IDLE"
    layout = _static_layout_svg(target_table, delivery_completed)

    if target_table is None or target_table in TERRACE_TABLES:
        table_x, table_y = (0, 0)
        animate = False
    else:
        table_x, table_y = TABLE_COORDS[target_table]
        animate = True

    dock_x, dock_y = DOCK_XY
    kitchen_x, kitchen_y = KITCHEN_XY

    # Emergency / low-battery override dot classes.
    dot_extra_class = ""
    if state == "EMERGENCY":
        dot_extra_class = "emergency"
    elif state == "LOW_BATTERY":
        dot_extra_class = "low-battery"

    animate_js = "true" if animate else "false"

    return (
        "<!doctype html><html><head><meta charset='utf-8'/>"
        "<link href='https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700"
        "&family=Inter:wght@400;600&display=swap' rel='stylesheet'>"
        f"<style>{_FLOOR_CSS}</style></head><body>"
        f"<div class='map-stage' data-state='{state}'>"
        f"  <div class='map-card'>"
        f"    <div class='map-title'>"
        f"      <span>Restaurant Floor Map</span>"
        f"      <span id='phase-label' class='phase-label'>Idle</span>"
        f"    </div>"
        f"    <svg id='floor-svg' viewBox='0 0 {_SVG_W} {_SVG_H}'"
        f"         preserveAspectRatio='xMidYMid meet'>"
        f"      <defs>"
        f"        <pattern id='terraceHatch' width='10' height='10'"
        f"                 patternUnits='userSpaceOnUse' patternTransform='rotate(45)'>"
        f"          <rect width='10' height='10' fill='#1a1410'/>"
        f"          <line x1='0' y1='0' x2='0' y2='10' stroke='#f85149'"
        f"                stroke-width='2' stroke-opacity='0.55'/>"
        f"        </pattern>"
        f"        <marker id='arrowBlue' viewBox='0 0 10 10' refX='8' refY='5'"
        f"                markerWidth='6' markerHeight='6' orient='auto-start-reverse'>"
        f"          <path d='M0,0 L10,5 L0,10 z' fill='#1f6feb'/>"
        f"        </marker>"
        f"        <marker id='arrowTeal' viewBox='0 0 10 10' refX='8' refY='5'"
        f"                markerWidth='6' markerHeight='6' orient='auto-start-reverse'>"
        f"          <path d='M0,0 L10,5 L0,10 z' fill='#00d4aa'/>"
        f"        </marker>"
        f"        <marker id='arrowOrange' viewBox='0 0 10 10' refX='8' refY='5'"
        f"                markerWidth='6' markerHeight='6' orient='auto-start-reverse'>"
        f"          <path d='M0,0 L10,5 L0,10 z' fill='#e3a008'/>"
        f"        </marker>"
        f"      </defs>"
        f"      {layout}"
        f"      <!-- Three-segment delivery path -->"
        f"      <g id='delivery-path' class='hidden'>"
        f"        <path id='seg-load'    class='path-segment load'    "
        f"              d='M {dock_x} {dock_y} L {kitchen_x} {kitchen_y}'"
        f"              marker-mid='url(#arrowBlue)'/>"
        f"        <path id='seg-deliver' class='path-segment deliver' "
        f"              d='M {kitchen_x} {kitchen_y} L {table_x} {table_y}'"
        f"              marker-mid='url(#arrowTeal)'/>"
        f"        <path id='seg-return'  class='path-segment return'  "
        f"              d='M {table_x} {table_y} L {dock_x} {dock_y}'"
        f"              marker-mid='url(#arrowOrange)'/>"
        f"      </g>"
        f"      <!-- Robot dot -->"
        f"      <g id='robot-marker' class='robot-marker {dot_extra_class}'"
        f"         transform='translate({dock_x},{dock_y})'>"
        f"        <circle r='18' class='robot-aura'/>"
        f"        <circle r='10' class='robot-dot'/>"
        f"        <text y='28' class='robot-label' text-anchor='middle'>DineBot</text>"
        f"      </g>"
        f"    </svg>"
        f"  </div>"
        f"</div>"
        f"<script>"
        f"(function() {{"
        f"  const animate = {animate_js};"
        f"  const triggerId = '{trigger_id}';"
        f"  const dock     = [{dock_x}, {dock_y}];"
        f"  const kitchen  = [{kitchen_x}, {kitchen_y}];"
        f"  const table    = [{table_x}, {table_y}];"
        f"  const marker   = document.getElementById('robot-marker');"
        f"  const phaseLbl = document.getElementById('phase-label');"
        f"  const pathG    = document.getElementById('delivery-path');"
        f"  const segLoad  = document.getElementById('seg-load');"
        f"  const segDlv   = document.getElementById('seg-deliver');"
        f"  const segRet   = document.getElementById('seg-return');"
        f"  function move(to, ms) {{"
        f"    marker.style.transition = 'transform ' + (ms/1000) + 's ease-in-out';"
        f"    marker.setAttribute('transform', 'translate(' + to[0] + ',' + to[1] + ')');"
        f"  }}"
        f"  function setPhase(label, active) {{"
        f"    phaseLbl.textContent = label;"
        f"    [segLoad, segDlv, segRet].forEach(function(s) {{"
        f"      s.classList.remove('active', 'done', 'upcoming');"
        f"    }});"
        f"    if (active === 'load')    {{ segLoad.classList.add('active'); segDlv.classList.add('upcoming'); segRet.classList.add('upcoming'); }}"
        f"    if (active === 'deliver') {{ segLoad.classList.add('done');   segDlv.classList.add('active');   segRet.classList.add('upcoming'); }}"
        f"    if (active === 'return')  {{ segLoad.classList.add('done');   segDlv.classList.add('done');     segRet.classList.add('active'); }}"
        f"    if (active === 'done')    {{ segLoad.classList.add('done');   segDlv.classList.add('done');     segRet.classList.add('done'); }}"
        f"  }}"
        f"  if (!animate) {{"
        f"    phaseLbl.textContent = 'Idle at dock';"
        f"    return;"
        f"  }}"
        f"  pathG.classList.remove('hidden');"
        f"  pathG.classList.remove('fading');"
        f"  marker.setAttribute('transform', 'translate(' + dock[0] + ',' + dock[1] + ')');"
        f"  setPhase('Phase 1 / 3 - Loading at kitchen', 'load');"
        f"  setTimeout(function() {{ move(kitchen, 2000); }}, 50);"
        f"  setTimeout(function() {{ setPhase('Phase 2 / 3 - Delivering to table', 'deliver'); move(table, 3000); }}, 2100);"
        f"  setTimeout(function() {{ setPhase('Phase 3 / 3 - Returning to dock',  'return');  move(dock,  2000); }}, 5200);"
        f"  setTimeout(function() {{ setPhase('Delivery complete', 'done'); }}, 7300);"
        f"  setTimeout(function() {{ pathG.classList.add('fading'); }}, 8000);"
        f"  setTimeout(function() {{ pathG.classList.add('hidden'); phaseLbl.textContent = 'Idle at dock'; }}, 10000);"
        f"  void triggerId;"
        f"}})();"
        f"</script>"
        f"</body></html>"
    )


# ---------------------------------------------------------------------------
# CSS (kept out-of-line for readability)
# ---------------------------------------------------------------------------
_FLOOR_CSS = """
:root {
  --bg: #0d1117; --card: #161b22; --accent: #00d4aa; --blue: #1f6feb;
  --danger: #f85149; --warn: #d29922; --ok: #3fb950; --text: #e6edf3;
  --muted: #8b949e; --orange: #e3a008;
}
* { box-sizing: border-box; }
html, body {
  margin: 0; padding: 0; background: var(--bg); color: var(--text);
  font-family: 'Inter', sans-serif; overflow: hidden;
}
.map-stage { padding: 12px; }
.map-card {
  background: var(--card); border: 1px solid #222c37; border-radius: 18px;
  padding: 14px;
  box-shadow: 0 18px 46px rgba(0,0,0,0.45);
}
.map-title {
  display: flex; justify-content: space-between; align-items: center;
  font-family: 'Orbitron', sans-serif; letter-spacing: 3px;
  color: var(--accent); font-size: 12px; text-transform: uppercase;
  margin-bottom: 10px;
}
.phase-label {
  padding: 4px 10px; border-radius: 999px;
  background: rgba(0,212,170,0.12); color: var(--accent);
  border: 1px solid rgba(0,212,170,0.4);
  font-size: 11px; letter-spacing: 2px;
  transition: all 0.4s ease;
}
#floor-svg { width: 100%; height: 580px; display: block; }

.zone-main    { fill: #0f1620; stroke: rgba(31,111,235,0.35); stroke-width: 1.5; }
.zone-private { fill: #0f1620; stroke: rgba(63,185,80,0.35);  stroke-width: 1.5; }
.zone-terrace { stroke: rgba(248,81,73,0.55); stroke-width: 2; stroke-dasharray: 6 4; }
.wall         { stroke: #222c37; stroke-width: 4; stroke-dasharray: 10 6; }
.zone-label {
  font-family: 'Orbitron', sans-serif; font-size: 11px; letter-spacing: 3px;
  opacity: 0.8;
}
.zone-label.main    { fill: #1f6feb; }
.zone-label.private { fill: #3fb950; }
.zone-label.terrace { fill: #f85149; }

.table { fill: #e6edf3; stroke: #0d1117; stroke-width: 1.5; }
.table-label { fill: #0d1117; pointer-events: none; }
.table-group:hover .table { stroke: #00d4aa; stroke-width: 2; }
.table-restricted { fill: #1a1410; stroke: #f85149; stroke-dasharray: 4 3; }
.table-restricted + .table-label,
.table-group .table-restricted ~ .table-label { fill: #f85149; }
.table-target {
  fill: #00d4aa;
  animation: targetPulse 1.4s ease-in-out infinite;
  filter: drop-shadow(0 0 6px rgba(0,212,170,0.7));
}
.table-complete {
  fill: #e3a008;
  animation: completeFlash 2s ease-in-out 1 forwards;
  filter: drop-shadow(0 0 8px rgba(227,160,8,0.8));
}

.dock-glow {
  fill: rgba(0,212,170,0.18);
  animation: dockPulse 2.6s ease-in-out infinite;
}

.robot-marker { transition: transform 1.5s ease-in-out; pointer-events: none; }
.robot-dot   { fill: var(--accent); stroke: #0d1117; stroke-width: 3; filter: drop-shadow(0 0 6px rgba(0,212,170,0.8)); }
.robot-aura  { fill: none; stroke: var(--accent); stroke-width: 2; opacity: 0.6;
               animation: auraPulse 1.6s ease-out infinite; }
.robot-label { fill: var(--accent); font-family: 'Orbitron', sans-serif;
               font-size: 10px; letter-spacing: 2px; }
.robot-marker.emergency   .robot-dot   { fill: var(--danger); }
.robot-marker.emergency   .robot-aura  { stroke: var(--danger); }
.robot-marker.low-battery .robot-dot   { fill: var(--warn); }
.robot-marker.low-battery .robot-aura  { stroke: var(--warn); }

#delivery-path.hidden { display: none; }
#delivery-path.fading { opacity: 0; transition: opacity 2s ease-out; }
.path-segment {
  fill: none; stroke-width: 3; stroke-linecap: round;
  stroke-dasharray: 8 6; opacity: 0.4;
  transition: opacity 0.4s ease, stroke-dashoffset 0.6s linear;
}
.path-segment.load    { stroke: var(--blue); }
.path-segment.deliver { stroke: var(--accent); }
.path-segment.return  { stroke: var(--orange); }
.path-segment.active  { opacity: 1; animation: marchingAnts 1s linear infinite; stroke-width: 4; }
.path-segment.done    { opacity: 1; stroke-dasharray: 0; }
.path-segment.upcoming{ opacity: 0.35; }

@keyframes marchingAnts { from { stroke-dashoffset: 0; } to { stroke-dashoffset: -28; } }
@keyframes targetPulse  { 0%,100% { filter: drop-shadow(0 0 3px rgba(0,212,170,0.4)); }
                           50%     { filter: drop-shadow(0 0 14px rgba(0,212,170,1)); } }
@keyframes completeFlash{ 0% { fill: #e3a008; }
                           60% { fill: #e3a008; }
                           100% { fill: #e6edf3; filter: none; } }
@keyframes auraPulse    { 0% { r: 12; opacity: 0.8; } 100% { r: 30; opacity: 0; } }
@keyframes dockPulse    { 0%,100% { r: 38; opacity: 0.3; } 50% { r: 48; opacity: 0.7; } }

[data-state="EMERGENCY"]   .robot-aura { animation: auraPulse 0.7s ease-out infinite; }
[data-state="LOW_BATTERY"] .robot-aura { animation: auraPulse 2.4s ease-out infinite; }
"""
