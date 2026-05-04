"""
Restaurant floor map with live delivery path animation.

This module renders an 800x580 SVG top-down floor plan with:

* Docking station (bottom-center, charging-pad icon with lightning bolt).
* Kitchen pickup counter (top-center).
* Main dining area (left, tables 1-10 in a 2x5 grid).
* Private dining room (right, tables 16-20 in a 1x5 column, wall separator).
* Outdoor terrace (top-right, tables 11-15, hatched and marked restricted).
* A teal robot dot with a "DineBot" label that moves smoothly along the
  waypoint-routed delivery path via JavaScript ``setTimeout`` chaining.
* A three-segment animated dashed polyline path that follows the
  restaurant's aisle corridors instead of cutting straight through tables:
  DOCK -> KITCHEN (blue, "load"),
  KITCHEN -> TABLE (teal, "deliver"),
  TABLE -> DOCK (orange, "return").

The public entry point is :func:`render_floor_map_html`, intended for
``streamlit.components.v1.html``. Use a component height of about 640 to avoid
clipping the 580-tall SVG plus the surrounding card chrome.
"""

from __future__ import annotations

import math
from textwrap import dedent

from utils.table_parser import TERRACE_TABLES

# ---------------------------------------------------------------------------
# Hardcoded map coordinates (SVG space is 800 x 580)
# ---------------------------------------------------------------------------
DOCK_XY: tuple[int, int] = (400, 520)
KITCHEN_XY: tuple[int, int] = (400, 60)

# Corridor waypoints (aisle-following routing) ------------------------------
# These let the robot travel around tables instead of through them.
DOCK: tuple[int, int]         = (400, 520)
MAIN_AISLE_S: tuple[int, int] = (400, 460)  # main vertical aisle, south end
MAIN_AISLE_N: tuple[int, int] = (400, 140)  # main vertical aisle, north end
KITCHEN: tuple[int, int]      = (400, 60)
LEFT_AISLE: tuple[int, int]   = (200, 300)  # aisle between tables 1-4 and 5-8
RIGHT_AISLE: tuple[int, int]  = (500, 300)  # aisle between main area and private

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


# ---------------------------------------------------------------------------
# Waypoint routing
# ---------------------------------------------------------------------------
def _zone_aisle(table_number: int) -> tuple[int, int] | None:
    """Return the corridor waypoint to traverse for a given table, if any."""
    if 1 <= table_number <= 8:
        return LEFT_AISLE
    if 9 <= table_number <= 10:
        return None  # tables 9-10 sit beside the main aisle directly
    if 16 <= table_number <= 20:
        return RIGHT_AISLE
    return None


def get_load_route() -> list[tuple[int, int]]:
    """Waypoints for the loading phase: dock -> kitchen."""
    return [DOCK, MAIN_AISLE_S, MAIN_AISLE_N, KITCHEN]


def get_deliver_route(table_number: int) -> list[tuple[int, int]]:
    """Waypoints for the delivery phase: kitchen -> table N."""
    target = TABLE_COORDS.get(table_number)
    if target is None:
        return [KITCHEN]
    aisle = _zone_aisle(table_number)
    waypoints: list[tuple[int, int]] = [KITCHEN, MAIN_AISLE_N]
    if aisle is not None:
        waypoints.append(aisle)
    waypoints.append(target)
    return waypoints


def get_return_route(table_number: int) -> list[tuple[int, int]]:
    """Waypoints for the return phase: table N -> dock."""
    target = TABLE_COORDS.get(table_number)
    if target is None:
        return [DOCK]
    aisle = _zone_aisle(table_number)
    waypoints: list[tuple[int, int]] = [target]
    if aisle is not None:
        waypoints.append(aisle)
    waypoints.extend([MAIN_AISLE_S, DOCK])
    return waypoints


def get_route(table_number: int) -> list[tuple[int, int]]:
    """Return the full ordered list of waypoints for a delivery to ``table_number``.

    The list covers the whole round trip: dock -> kitchen (loading),
    kitchen -> table (delivery), and table -> dock (return), with the
    appropriate corridor aisles inserted to keep the robot off of any
    table footprint.
    """
    load = get_load_route()
    deliver = get_deliver_route(table_number)
    ret = get_return_route(table_number)
    # Drop duplicates at segment boundaries (KITCHEN, TABLE).
    return load + deliver[1:] + ret[1:]


def _polyline_points(points: list[tuple[int, int]]) -> str:
    return " ".join(f"{x},{y}" for x, y in points)


def _polyline_length(points: list[tuple[int, int]]) -> float:
    total = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        total += math.hypot(x2 - x1, y2 - y1)
    return total


# ---------------------------------------------------------------------------
# Static SVG layout
# ---------------------------------------------------------------------------
def _table_rect(
    n: int, x: int, y: int, target: int | None, completed: bool
) -> str:
    """Render a single table as a rounded rect + centred numeric label."""
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
    # Slightly larger rect (44x28) to keep the numeric label fully inside
    # without overlapping the border, even with bold Orbitron digits.
    rect = (
        f'<rect class="{cls}" x="{x - 22}" y="{y - 14}" width="44" height="28"'
        f' rx="6" ry="6" data-table-id="{n}"/>'
    )
    label = (
        f'<text class="table-label" x="{x}" y="{y}" text-anchor="middle"'
        f' dominant-baseline="central"'
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
          <text x="{kitchen_x}" y="{kitchen_y}" text-anchor="middle"
                dominant-baseline="central"
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

    if (
        target_table is None
        or target_table in TERRACE_TABLES
        or target_table not in TABLE_COORDS
    ):
        animate = False
        load_pts = get_load_route()
        deliver_pts: list[tuple[int, int]] = []
        return_pts: list[tuple[int, int]] = []
    else:
        animate = True
        load_pts = get_load_route()
        deliver_pts = get_deliver_route(target_table)
        return_pts = get_return_route(target_table)

    dock_x, dock_y = DOCK_XY

    # Emergency / low-battery override dot classes.
    dot_extra_class = ""
    if state == "EMERGENCY":
        dot_extra_class = "emergency"
    elif state == "LOW_BATTERY":
        dot_extra_class = "low-battery"

    animate_js = "true" if animate else "false"
    load_js = _polyline_points(load_pts) if load_pts else ""
    deliver_js = _polyline_points(deliver_pts) if deliver_pts else ""
    return_js = _polyline_points(return_pts) if return_pts else ""

    # JS literal arrays of [x,y] waypoints for sequential setTimeout chaining.
    def _js_array(points: list[tuple[int, int]]) -> str:
        return "[" + ",".join(f"[{x},{y}]" for x, y in points) + "]"

    load_arr = _js_array(load_pts)
    deliver_arr = _js_array(deliver_pts) if deliver_pts else "[]"
    return_arr = _js_array(return_pts) if return_pts else "[]"

    return (
        "<!DOCTYPE html>"
        "<html><head><meta charset='utf-8'/>"
        "<link href='https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700"
        "&family=Inter:wght@400;600&display=swap' rel='stylesheet'>"
        f"<style>{_FLOOR_CSS}</style></head><body>"
        f"<div class='map-stage' data-state='{state}' "
        f"style='height:100%;min-height:100%;overflow:visible;box-sizing:border-box'>"
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
        f"      <!-- Three-segment delivery polyline (aisle-following) -->"
        f"      <g id='delivery-path' class='hidden'>"
        f"        <polyline id='seg-load'    class='path-segment load'"
        f"                  points='{load_js}'"
        f"                  marker-mid='url(#arrowBlue)'/>"
        f"        <polyline id='seg-deliver' class='path-segment deliver'"
        f"                  points='{deliver_js}'"
        f"                  marker-mid='url(#arrowTeal)'/>"
        f"        <polyline id='seg-return'  class='path-segment return'"
        f"                  points='{return_js}'"
        f"                  marker-mid='url(#arrowOrange)'/>"
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
        f"  var animate    = {animate_js};"
        f"  var triggerId  = '{trigger_id}';"
        f"  var loadPts    = {load_arr};"
        f"  var deliverPts = {deliver_arr};"
        f"  var returnPts  = {return_arr};"
        f"  var marker     = document.getElementById('robot-marker');"
        f"  var phaseLbl   = document.getElementById('phase-label');"
        f"  var pathG      = document.getElementById('delivery-path');"
        f"  var segLoad    = document.getElementById('seg-load');"
        f"  var segDlv     = document.getElementById('seg-deliver');"
        f"  var segRet     = document.getElementById('seg-return');"
        f"  function dist(a, b) {{"
        f"    var dx = b[0] - a[0], dy = b[1] - a[1];"
        f"    return Math.sqrt(dx*dx + dy*dy);"
        f"  }}"
        f"  function totalLen(pts) {{"
        f"    var t = 0;"
        f"    for (var i = 1; i < pts.length; i++) t += dist(pts[i-1], pts[i]);"
        f"    return t;"
        f"  }}"
        f"  function moveAlong(pts, totalMs, startAtZero) {{"
        f"    if (!pts || pts.length < 2) return;"
        f"    var len = totalLen(pts);"
        f"    if (len <= 0) return;"
        f"    var elapsed = 0;"
        f"    if (startAtZero) {{"
        f"      marker.style.transition = 'none';"
        f"      marker.setAttribute('transform',"
        f"        'translate(' + pts[0][0] + ',' + pts[0][1] + ')');"
        f"      void marker.getBoundingClientRect();"
        f"    }}"
        f"    for (var i = 1; i < pts.length; i++) {{"
        f"      (function(target, legMs, startMs) {{"
        f"        setTimeout(function() {{"
        f"          marker.style.transition = 'transform ' + (legMs/1000) + 's linear';"
        f"          marker.setAttribute('transform',"
        f"            'translate(' + target[0] + ',' + target[1] + ')');"
        f"        }}, startMs);"
        f"      }})(pts[i], (dist(pts[i-1], pts[i]) / len) * totalMs, elapsed);"
        f"      elapsed += (dist(pts[i-1], pts[i]) / len) * totalMs;"
        f"    }}"
        f"  }}"
        f"  function setPhase(label, active) {{"
        f"    phaseLbl.textContent = label;"
        f"    [segLoad, segDlv, segRet].forEach(function(s) {{"
        f"      s.classList.remove('active', 'done', 'upcoming');"
        f"    }});"
        f"    if (active === 'load')    {{ segLoad.classList.add('active'); segDlv.classList.add('upcoming'); segRet.classList.add('upcoming'); }}"
        f"    if (active === 'deliver') {{ segLoad.classList.add('done');   segDlv.classList.add('active');   segRet.classList.add('upcoming'); }}"
        f"    if (active === 'wait')    {{ segLoad.classList.add('done');   segDlv.classList.add('done');     segRet.classList.add('upcoming'); }}"
        f"    if (active === 'return')  {{ segLoad.classList.add('done');   segDlv.classList.add('done');     segRet.classList.add('active'); }}"
        f"    if (active === 'done')    {{ segLoad.classList.add('done');   segDlv.classList.add('done');     segRet.classList.add('done'); }}"
        f"  }}"
        f"  if (!animate) {{"
        f"    phaseLbl.textContent = 'Idle at dock';"
        f"    return;"
        f"  }}"
        f"  pathG.classList.remove('hidden');"
        f"  pathG.classList.remove('fading');"
        f"  // Timeline (per spec):"
        f"  //   t=0s  LOADING    -> move dock -> kitchen along load polyline"
        f"  //   t=3s  DELIVERING -> move kitchen -> table along deliver polyline"
        f"  //   t=8s  WAITING    -> highlight target table"
        f"  //   t=11s RETURNING  -> move table -> dock along return polyline"
        f"  //   t=14s IDLE       -> reset highlights / fade out path"
        f"  setPhase('Phase 1 / 3 - Loading at kitchen', 'load');"
        f"  moveAlong(loadPts,    2800, true);"
        f"  setTimeout(function() {{"
        f"    setPhase('Phase 2 / 3 - Delivering to table', 'deliver');"
        f"    moveAlong(deliverPts, 4800, false);"
        f"  }}, 3000);"
        f"  setTimeout(function() {{"
        f"    setPhase('Waiting at table', 'wait');"
        f"  }}, 8000);"
        f"  setTimeout(function() {{"
        f"    setPhase('Phase 3 / 3 - Returning to dock', 'return');"
        f"    moveAlong(returnPts, 2800, false);"
        f"  }}, 11000);"
        f"  setTimeout(function() {{"
        f"    setPhase('Delivery complete', 'done');"
        f"  }}, 14000);"
        f"  setTimeout(function() {{ pathG.classList.add('fading'); }}, 14500);"
        f"  setTimeout(function() {{"
        f"    pathG.classList.add('hidden');"
        f"    phaseLbl.textContent = 'Idle at dock';"
        f"  }}, 16500);"
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
  margin: 0; padding: 0; height: 100%; background: var(--bg); color: var(--text);
  font-family: 'Inter', sans-serif; overflow: visible;
}
.map-stage {
  padding: 12px; height: 100%; min-height: 100%;
  box-sizing: border-box; overflow: visible;
}
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
#floor-svg { width: 100%; height: 560px; display: block; }

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
  fill: none; stroke-width: 3; stroke-linecap: round; stroke-linejoin: round;
  stroke-dasharray: 8 6; opacity: 0.4;
  transition: opacity 0.4s ease;
}
.path-segment.load    { stroke: var(--blue); }
.path-segment.deliver { stroke: var(--accent); }
.path-segment.return  { stroke: var(--orange); }
.path-segment.active  { opacity: 1; animation: marchingAnts 1s linear infinite; stroke-width: 4; }
.path-segment.done    { opacity: 0.85; stroke-dasharray: 0; }
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


__all__ = [
    "TERRACE_TABLES",
    "TABLE_COORDS",
    "DOCK_XY",
    "KITCHEN_XY",
    "DOCK",
    "MAIN_AISLE_S",
    "MAIN_AISLE_N",
    "KITCHEN",
    "LEFT_AISLE",
    "RIGHT_AISLE",
    "get_route",
    "get_load_route",
    "get_deliver_route",
    "get_return_route",
    "render_floor_map_html",
]
