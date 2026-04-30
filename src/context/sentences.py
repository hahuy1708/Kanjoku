# src/context/sentence.py
"""
Utilities for turning a raw Tatoeba sentence into a fill-in-the-blank quiz item.
"""
from __future__ import annotations

import re


# Characters that should not appear in a usable quiz sentence
_NOISE_PATTERNS = [
    re.compile(r"https?://"),           # URLs
    re.compile(r"[A-Za-z]{4,}"),       # long Latin strings (loanword exceptions OK)
    re.compile(r"\d{4,}"),             # long numbers
    re.compile(r"[「」『』（）【】〔〕].*[「」『』（）【】〔〕]"),  # nested brackets
]


def _is_clean(text: str) -> bool:
    """Return False for sentences that would make bad quiz items."""
    for pat in _NOISE_PATTERNS:
        if pat.search(text):
            return False
    return True


def _word_appears_once(text: str, word: str) -> bool:
    """The target word must appear exactly once to avoid ambiguous blanking."""
    return text.count(word) == 1


def _blank_position_ok(text: str, word: str) -> bool:
    """
    Prefer the blank NOT to be at position 0 (makes the sentence trivially easy
    because the particle after the blank still gives the answer away too easily).
    Sentences where the word starts at char 0 are allowed but deprioritised.
    """
    return text.index(word) > 0


def make_blank(text: str, word: str) -> str:
    """Replace the first occurrence of *word* in *text* with ____."""
    return text.replace(word, "____", 1)


def pick_sentence(candidates: list[str], word: str) -> str | None:
    """
    From a list of candidate sentences, pick the best one for a quiz item.

    Priority:
      1. Clean, word appears exactly once, blank NOT at position 0.
      2. Clean, word appears exactly once (blank may be at position 0).
    Returns None if no suitable sentence found.
    """
    tier1: list[str] = []
    tier2: list[str] = []

    for text in candidates:
        if not _is_clean(text):
            continue
        if not _word_appears_once(text, word):
            continue
        if _blank_position_ok(text, word):
            tier1.append(text)
        else:
            tier2.append(text)

    for tier in (tier1, tier2):
        if tier:
            import random
            return random.choice(tier)

    return None