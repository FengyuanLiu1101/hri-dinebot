"""
Knowledge base file loading utilities.

All knowledge files live in ``knowledge_base/`` at the project root.
This module provides three entry points:

* :func:`load_knowledge_file` - load one file by name.
* :func:`load_all_knowledge` - load every knowledge file into a dict.
* :func:`get_all_documents` - return the knowledge base as a flat list of
  non-empty, non-comment lines suitable for keyword/retrieval scoring.
"""

from __future__ import annotations

from pathlib import Path

KNOWLEDGE_FILES: tuple[str, ...] = (
    "safety_rules.txt",
    "delivery_procedures.txt",
    "menu_knowledge.txt",
    "table_management.txt",
    "emergency_protocols.txt",
)

_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
_KB_DIR: Path = _PROJECT_ROOT / "knowledge_base"


def load_knowledge_file(filename: str) -> str:
    """Load a single knowledge base text file and return its content.

    Parameters
    ----------
    filename:
        Name of the file inside ``knowledge_base/`` (e.g. ``"safety_rules.txt"``).

    Returns
    -------
    str
        Full file content as UTF-8 text. Empty string if file missing.
    """
    path = _KB_DIR / filename
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except OSError as exc:
        print(f"[file_loader] Could not read {path}: {exc}")
        return ""


def load_all_knowledge() -> dict[str, str]:
    """Load every knowledge base file.

    Returns
    -------
    dict[str, str]
        Mapping from file stem (e.g. ``"safety_rules"``) to file content.
    """
    bundle: dict[str, str] = {}
    for name in KNOWLEDGE_FILES:
        stem = Path(name).stem
        bundle[stem] = load_knowledge_file(name)
    return bundle


def get_all_documents() -> list[str]:
    """Return the knowledge base as a flat list of useful lines.

    Blank lines and comment lines (``#`` or ``##``) are stripped so that
    scoring algorithms only see substantive content.
    """
    documents: list[str] = []
    for content in load_all_knowledge().values():
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("#"):
                continue
            documents.append(line)
    return documents
