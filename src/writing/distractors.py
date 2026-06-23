# src/writing/distractors.py
"""
Distractor generation for the writing (漢字書き) quiz.

Strategy (three priority levels, matching JLPT exam style):
  1. Homophones (同音異義語) — same furigana reading, different kanji.
     These are the best distractors because JLPT exams use them exclusively.
  2. Near-homophones — same mora count, different reading/kanji.
     Used when there are not enough true homophones.
  3. JLPT vocab fallback — random kanji words from the same vocab list.

JMdict SQLite path is resolved once at module level via Jamdict.
A new connection is opened per call to stay thread-safe.
"""
from __future__ import annotations

import random
import re
import sqlite3
from functools import lru_cache

from jamdict import Jamdict

# ── Module-level DB path (resolved once) ─────────────────────────────────────
@lru_cache(maxsize=1)
def _get_db_path() -> str:
    return Jamdict().jmdict.ds.path


def _open_conn() -> sqlite3.Connection:
    """Open a fresh read-only connection to the JMdict SQLite database."""
    conn = sqlite3.connect(_get_db_path())
    conn.execute("PRAGMA query_only = ON")
    return conn


# ── Kanji character range helper ──────────────────────────────────────────────
_KANJI_RE = re.compile(r"[一-龯]")


def _has_kanji(text: str) -> bool:
    return bool(_KANJI_RE.search(text))


# ── Strategy 1: homophones ────────────────────────────────────────────────────

def get_homophones(reading: str, exclude_word: str, count: int) -> list[str]:
    """
    Query JMdict for kanji words that share *exactly* the same reading as the
    answer word but have different kanji representation.

    Parameters
    ----------
    reading      : exact hiragana reading of the answer (e.g. "きかい")
    exclude_word : the correct kanji word to exclude   (e.g. "機会")
    count        : max number of results to return

    Returns
    -------
    List of distractor kanji strings (may be shorter than *count*).
    """
    sql = """
        SELECT DISTINCT k.text
        FROM Kanji k
        JOIN Kana kn ON kn.idseq = k.idseq
        WHERE kn.text = ?
          AND k.text != ?
          AND k.text GLOB '*[一-龯]*'
        ORDER BY RANDOM()
        LIMIT ?
    """
    try:
        conn = _open_conn()
        try:
            rows = conn.execute(sql, (reading, exclude_word, count)).fetchall()
            return [row[0] for row in rows if row and row[0]]
        finally:
            conn.close()
    except sqlite3.OperationalError:
        return []


# ── Strategy 2: near-homophones ───────────────────────────────────────────────

def get_near_homophones(reading: str, exclude_word: str, count: int) -> list[str]:
    """
    Query JMdict for kanji words whose reading has the *same mora length* as
    *reading* but is itself different — a softer fallback when homophones are
    scarce.

    Parameters
    ----------
    reading      : hiragana reading of the answer
    exclude_word : the correct kanji word to exclude
    count        : max number of results

    Returns
    -------
    List of distractor kanji strings.
    """
    sql = """
        SELECT DISTINCT k.text
        FROM Kanji k
        JOIN Kana kn ON kn.idseq = k.idseq
        WHERE length(kn.text) = ?
          AND kn.text != ?
          AND k.text != ?
          AND k.text GLOB '*[一-龯]*'
        ORDER BY RANDOM()
        LIMIT ?
    """
    try:
        conn = _open_conn()
        try:
            rows = conn.execute(
                sql, (len(reading), reading, exclude_word, count)
            ).fetchall()
            return [row[0] for row in rows if row and row[0]]
        finally:
            conn.close()
    except sqlite3.OperationalError:
        return []


# ── Strategy 3: vocab fallback ────────────────────────────────────────────────

def get_vocab_fallback(
    exclude_word: str,
    vocab_data: list[dict],
    count: int,
) -> list[str]:
    """
    Last-resort pool: pick kanji words from the current JLPT vocab list.

    Filters:
    - Must differ from *exclude_word*
    - Must not be a pure-kana word (word != furigana)
    - Must contain at least one kanji character

    Parameters
    ----------
    exclude_word : the correct answer word to exclude
    vocab_data   : full vocab list for the current JLPT level
    count        : max number of results

    Returns
    -------
    Shuffled list of up to *count* candidate words.
    """
    pool: list[str] = []
    for entry in vocab_data:
        word = entry.get("word", "")
        furigana = entry.get("furigana", "")
        if not word:
            continue
        if word == exclude_word:
            continue
        if word == furigana:  # pure kana — no kanji to write
            continue
        if not _has_kanji(word):
            continue
        pool.append(word)

    random.shuffle(pool)
    return pool[:count]


# ── Combined distractor engine ────────────────────────────────────────────────

def get_kanji_distractors(
    word: str,
    reading: str,
    vocab_data: list[dict],
    count: int = 3,
) -> list[str]:
    """
    Generate *count* unique kanji distractors for a writing quiz item using
    the three-tier priority strategy described in the module docstring.

    Parameters
    ----------
    word       : the correct kanji answer (e.g. "機会")
    reading    : the hiragana reading     (e.g. "きかい")
    vocab_data : full JLPT vocab list (used for fallback)
    count      : number of distractors required (default 3)

    Returns
    -------
    Shuffled list of *count* distractor strings, or fewer if the combined
    strategies cannot produce enough candidates.
    """
    seen: set[str] = {word}
    candidates: list[str] = []

    # ── Tier 1: homophones ────────────────────────────────────────────────────
    for item in get_homophones(reading, word, count * 3):
        if item not in seen:
            seen.add(item)
            candidates.append(item)

    # ── Tier 2: near-homophones ───────────────────────────────────────────────
    if len(candidates) < count:
        needed = (count - len(candidates)) * 3
        for item in get_near_homophones(reading, word, needed):
            if item not in seen:
                seen.add(item)
                candidates.append(item)

    # ── Tier 3: vocab fallback ────────────────────────────────────────────────
    if len(candidates) < count:
        needed = (count - len(candidates)) * 3
        for item in get_vocab_fallback(word, vocab_data, needed):
            if item not in seen:
                seen.add(item)
                candidates.append(item)

    random.shuffle(candidates)
    return candidates[:count]
