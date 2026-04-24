"""
Session logger for DineBot.

Every process run creates a single timestamped log file inside ``logs/``
(``logs/session_YYYYMMDD_HHMMSS.log``) with a consistent format usable by
both Agent A (rule-based) and Agent B (RAG + MAS).
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Callable

_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
_LOG_DIR: Path = _PROJECT_ROOT / "logs"

# ---------------------------------------------------------------------------
# Live trace listener hooks
# ---------------------------------------------------------------------------
# Any subscriber (e.g. the Streamlit UI) can register a callback that will be
# invoked for every MAS trace event. This powers the right-panel live trace.
_TRACE_LISTENERS: list[Callable[[str, str], None]] = []


def register_trace_listener(listener: Callable[[str, str], None]) -> None:
    """Attach a ``(step_name, content) -> None`` callback to the trace stream."""
    if listener not in _TRACE_LISTENERS:
        _TRACE_LISTENERS.append(listener)


def unregister_trace_listener(listener: Callable[[str, str], None]) -> None:
    """Detach a previously registered listener."""
    if listener in _TRACE_LISTENERS:
        _TRACE_LISTENERS.remove(listener)


def clear_trace_listeners() -> None:
    """Remove every registered listener. Useful between queries."""
    _TRACE_LISTENERS.clear()


def _configure_logger() -> logging.Logger:
    """Initialize a module-level logger writing to ``logs/session_*.log``."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = _LOG_DIR / f"session_{timestamp}.log"

    logger = logging.getLogger("dinebot")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    # Avoid attaching duplicate handlers when imported multiple times.
    if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(file_handler)

    return logger


_logger: logging.Logger = _configure_logger()


def _truncate(text: str, limit: int = 1000) -> str:
    text = str(text).replace("\n", " ").strip()
    return text if len(text) <= limit else text[:limit] + "...<truncated>"


def log_query(agent_name: str, query: str) -> None:
    """Record an incoming user query."""
    _logger.info("[%s][QUERY] %s", agent_name, _truncate(query))


def log_response(agent_name: str, response: str) -> None:
    """Record an outgoing agent response."""
    _logger.info("[%s][RESPONSE] %s", agent_name, _truncate(response))


def log_mas_trace(step_name: str, content: str) -> None:
    """Record a single MAS pipeline step (retriever / generator / critic)."""
    _logger.debug("[MAS][%s] %s", step_name, _truncate(str(content), limit=2000))
    # Broadcast to any live UI listeners. Listener errors must never break the
    # pipeline, so we swallow exceptions individually.
    for listener in list(_TRACE_LISTENERS):
        try:
            listener(step_name, str(content))
        except Exception:  # noqa: BLE001
            pass


def log_error(agent_name: str, error: str | Exception) -> None:
    """Record a recoverable error from an agent."""
    _logger.error("[%s][ERROR] %s", agent_name, _truncate(str(error)))
