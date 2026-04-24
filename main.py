"""
DineBot CLI entry point.

Usage:
    python main.py --agent a        # run Agent A (offline, rule-based)
    python main.py --agent b        # run Agent B (RAG + MAS)

The Streamlit UI is launched separately:
    streamlit run ui/app.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dinebot",
        description="DineBot - Restaurant food delivery HRI agent",
    )
    parser.add_argument(
        "--agent",
        choices=["a", "b"],
        help="Which agent to run: 'a' (rule-based) or 'b' (RAG + MAS).",
    )
    return parser


def _print_usage() -> None:
    print(
        "\nDineBot CLI\n"
        "-----------\n"
        "  python main.py --agent a       Run Agent A (offline, rule-based)\n"
        "  python main.py --agent b       Run Agent B (RAG + MAS, uses OpenAI)\n"
        "  streamlit run ui/app.py        Launch the animated web UI\n"
    )


def main() -> int:
    args = _build_parser().parse_args()

    if args.agent is None:
        _print_usage()
        return 0

    if args.agent == "a":
        from agent_a.simple_agent import SimpleAgent

        SimpleAgent().run()
        return 0

    if args.agent == "b":
        from agent_b.mas.orchestrator import Orchestrator

        Orchestrator().run()
        return 0

    _print_usage()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
