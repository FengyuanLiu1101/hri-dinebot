"""
Agent B entry point: boots the Multi-Agent System orchestrator.

Invoked from ``main.py --agent b`` or directly via
``python -m agent_b.rag_agent``.
"""

from __future__ import annotations

from agent_b.mas.orchestrator import Orchestrator


def main() -> None:
    Orchestrator().run()


if __name__ == "__main__":
    main()
