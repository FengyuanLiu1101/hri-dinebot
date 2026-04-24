"""
Light-weight text processing helpers used by Agent A and the intent router.

These helpers intentionally avoid heavy NLP libraries. They are sufficient
for the offline, rule-based retrieval path and for keyword-based intent
classification shared by both agents.
"""

from __future__ import annotations

import string
from collections import Counter
from typing import Iterable

_PUNCT_TABLE = str.maketrans({c: " " for c in string.punctuation})


def tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, and split on whitespace."""
    if not text:
        return []
    cleaned = text.lower().translate(_PUNCT_TABLE)
    return [tok for tok in cleaned.split() if tok]


def tf_score(query_tokens: Iterable[str], doc_tokens: Iterable[str]) -> float:
    """Simple term-frequency overlap score.

    For each query token, add the number of times it appears in the document.
    Returns a float so higher is better.
    """
    q_counts = Counter(query_tokens)
    d_counts = Counter(doc_tokens)
    if not q_counts or not d_counts:
        return 0.0
    score = 0.0
    for token, q_freq in q_counts.items():
        if token in d_counts:
            score += float(q_freq * d_counts[token])
    return score


def clean_text(text: str) -> str:
    """Strip blank lines, comment lines, and surrounding whitespace.

    Useful for turning raw knowledge base files into normalized prompt context.
    """
    if not text:
        return ""
    kept: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        kept.append(line)
    return "\n".join(kept)


def classify_intent(query: str, keyword_categories: dict[str, list[str]]) -> str:
    """Return the intent category with the most keyword matches.

    Parameters
    ----------
    query:
        Raw user query.
    keyword_categories:
        Mapping from category name to list of keywords (see
        ``config.agent_config.KEYWORD_CATEGORIES``).

    Returns
    -------
    str
        The winning category name or ``"general"`` if no keyword matches.
    """
    if not query:
        return "general"
    lowered = query.lower()
    best_category = "general"
    best_hits = 0
    for category, keywords in keyword_categories.items():
        hits = sum(1 for kw in keywords if kw.lower() in lowered)
        if hits > best_hits:
            best_hits = hits
            best_category = category
    return best_category
