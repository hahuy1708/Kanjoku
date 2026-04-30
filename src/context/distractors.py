# src/context/distractors.py
"""
Distractor generation for context (穴埋め) quiz.

Strategy
========
The blank hides a word; the 3 wrong choices must be:
  - The same part-of-speech as the correct word  →  plausible substitutes
  - Exist in JMdict  →  real words
  - NOT valid in the blank  →  contextually wrong

We query JMdict by POS to get same-category words, then rank by
character-length similarity to the correct word (closer length = harder).
"""
from __future__ import annotations

import random
import sqlite3
from functools import lru_cache

from jamdict import Jamdict

_jam = Jamdict()
_DB_PATH: str = _jam.jmdict.ds.path

# Map broad POS keywords (from JMdict verbose tags) -> short group label
_POS_KEYWORD_MAP: dict[str, str] = {
    "noun":       "noun",
    "verb":       "verb",
    "adjective":  "adjective",
    "adverb":     "adverb",
    "expression": "expression",
}


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("PRAGMA query_only = ON")
    return conn


@lru_cache(maxsize=4096)
def _get_word_pos(word: str) -> str | None:
    """Return the broad POS group for *word*, or None if unknown."""
    result = _jam.lookup(word)
    if not result.entries:
        return None
    senses = result.entries[0].senses
    if not senses or not senses[0].pos:
        return None
    raw = senses[0].pos[0].lower()
    for keyword, group in _POS_KEYWORD_MAP.items():
        if keyword in raw:
            return group
    return None


def get_context_distractors(
    word: str,
    sentence: str,
    all_vocab: list[dict],
    count: int = 3,
) -> list[str]:
    """
    Return *count* distractor words for a context quiz item.

    Parameters
    ----------
    word       : correct answer word (kanji/mixed)
    sentence   : the sentence containing the blank (used to exclude obvious fits)
    all_vocab  : full vocab list for the current JLPT level — used as candidate pool
    count      : number of distractors needed
    """
    correct_len = len(word)
    chosen: list[str] = []
    seen: set[str] = {word}

    # ── Pool 1: same-level vocab (same POS preferred) ─────────────────────────
    pos = _get_word_pos(word)
    same_pos: list[str] = []
    diff_pos: list[str] = []

    for entry in all_vocab:
        candidate = entry.get("word", "")
        if not candidate or candidate in seen:
            continue
        # Skip if the candidate also fits in the blank (too easy to eliminate)
        if candidate in sentence:
            continue
        if _get_word_pos(candidate) == pos:
            same_pos.append(candidate)
        else:
            diff_pos.append(candidate)

    # Sort: prefer candidates of similar character length (harder to eliminate)
    def length_closeness(w: str) -> int:
        return abs(len(w) - correct_len)

    same_pos.sort(key=length_closeness)
    diff_pos.sort(key=length_closeness)

    # Take from same_pos first, then diff_pos as fallback.
    # We keep the pool ordered by length closeness (harder), but add randomness
    # by shuffling within a top-k window.
    def take_from_pool(pool: list[str], top_k: int = 60) -> None:
        if not pool:
            return

        head = pool[:top_k]
        tail = pool[top_k:]
        random.shuffle(head)

        for cand in head + tail:
            if cand in seen:
                continue
            chosen.append(cand)
            seen.add(cand)
            if len(chosen) >= count:
                return

    take_from_pool(same_pos)
    if len(chosen) < count:
        take_from_pool(diff_pos)

    return chosen[:count]