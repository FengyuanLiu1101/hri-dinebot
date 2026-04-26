"""Helpers for parsing and validating restaurant table mentions."""

from __future__ import annotations

import re

TABLE_MENTION_RE = re.compile(r"\btable\s*#?\s*(\d+)\b", re.IGNORECASE)

VALID_TABLES: set[int] = set(range(1, 21))
TERRACE_TABLES: set[int] = set(range(11, 16))
SERVABLE_TABLES: set[int] = VALID_TABLES - TERRACE_TABLES


def mentioned_table_number(text: str) -> int | None:
    """Return the first explicitly mentioned table number, if any."""
    if not text:
        return None
    match = TABLE_MENTION_RE.search(text)
    if not match:
        return None
    return int(match.group(1))


def target_table_from_text(text: str) -> int | None:
    """Return a valid table number from text, or ``None`` if absent/invalid."""
    table_number = mentioned_table_number(text)
    return table_number if table_number in VALID_TABLES else None


def is_terrace_table(table_number: int | None) -> bool:
    """Return ``True`` when ``table_number`` is in the restricted terrace zone."""
    return table_number in TERRACE_TABLES


def is_servable_table(table_number: int | None) -> bool:
    """Return ``True`` when DineBot may deliver to ``table_number``."""
    return table_number in SERVABLE_TABLES
