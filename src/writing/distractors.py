# src/writing/distractors.py
"""
Distractor generation for the writing (漢字書き) quiz.

Two tiers:
  1. JMdict Homophones  — same full-word reading, different kanji  (best quality)
  2. Kanjidic2 Swap     — replace one kanji at a time with a same-reading alternative

Key design decisions
--------------------
- decompose_word is NOT used here. Knowing which reading each kanji contributes
  is not needed: we probe ALL ON+KUN readings from Kanjidic2 + JMdict single-char
  entries for each kanji position. JMdict single-char entries cover rendaku variants
  (e.g. 雨 → あめ AND あま) that Kanjidic2 alone may miss.

- JMdict and Kanjidic2 share the same SQLite file in jamdict-data-fix.
  One DB path is used throughout.

- The rm_group intermediate table is required for Kanjidic2 queries:
    character → rm_group → reading
    (c.ID)     (g.cid)    (r.gid = g.ID)
"""
from __future__ import annotations

import random
import re
import sqlite3
from functools import lru_cache

from jamdict import Jamdict

_KANJI_RE = re.compile(r"[一-龯]")


# ── Single DB path (JMdict + Kanjidic2 are in the same file) ──────────────────

@lru_cache(maxsize=1)
def _db_path() -> str:
    return Jamdict().jmdict.ds.path          # same file as kd2 in jamdict-data-fix


def _open_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path())
    conn.execute("PRAGMA query_only = ON")
    return conn


# ── Helpers ───────────────────────────────────────────────────────────────────

def _hira_to_kata(text: str) -> str:
    """Convert hiragana to katakana for ON-reading comparison."""
    return "".join(
        chr(ord(ch) + 0x60) if 0x3041 <= ord(ch) <= 0x3096 else ch
        for ch in text
    )


def _kanji_positions(word: str) -> list[tuple[int, str]]:
    """Return (index, char) for every kanji character in word."""
    return [(i, ch) for i, ch in enumerate(word) if _KANJI_RE.match(ch)]


# ── Tier 1: JMdict homophones ─────────────────────────────────────────────────

def _get_homophones(reading: str, word: str, count: int, conn: sqlite3.Connection) -> list[str]:
    """
    Kanji words in JMdict with exactly the same reading as *word*.
    e.g. 機会(きかい) → 機械, 器械
    """
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT k.text
            FROM Kanji k
            JOIN Kana kn ON kn.idseq = k.idseq
            WHERE kn.text  = ?
              AND k.text  != ?
              AND k.text GLOB '*[一-龯]*'
            ORDER BY RANDOM()
            LIMIT ?
            """,
            (reading, word, count),
        ).fetchall()
        return [r[0] for r in rows if r and r[0]]
    except sqlite3.OperationalError:
        return []


# ── Tier 2: Kanjidic2 kanji swap ──────────────────────────────────────────────

def _kd2_all_readings(kanji: str, conn: sqlite3.Connection) -> set[str]:
    """
    All ON and KUN readings from Kanjidic2 for a single kanji character.

    ON  → katakana (キ, カイ …)
    KUN → hiragana, may include dot notation (はな.す, うえ, め …)

    Both forms are returned as-is; _kd2_alts_for_reading handles matching.
    """
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT r.value
            FROM character c
            JOIN rm_group g ON g.cid = c.ID
            JOIN reading r  ON r.gid = g.ID
            WHERE c.literal = ?
              AND r.r_type IN ('ja_on', 'ja_kun')
            """,
            (kanji,),
        ).fetchall()
        return {r[0] for r in rows}
    except sqlite3.OperationalError:
        return set()


def _jmdict_char_readings(kanji: str, conn: sqlite3.Connection) -> set[str]:
    """
    All readings of *kanji* as a standalone single-character entry in JMdict.

    This covers rendaku variants and compound-specific readings that
    Kanjidic2 may not list directly:
      雨 → あめ (Kanjidic2) AND あま (JMdict single-char: 雨脚, 雨戸, …)
    """
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT kn.text
            FROM Kanji k
            JOIN Kana kn ON kn.idseq = k.idseq
            WHERE k.text = ?
            LIMIT 20
            """,
            (kanji,),
        ).fetchall()
        return {r[0] for r in rows if r[0]}
    except sqlite3.OperationalError:
        return set()


def _kd2_alts_for_reading(
    reading: str,
    exclude_char: str,
    conn: sqlite3.Connection,
    limit: int = 20,
) -> list[str]:
    """
    Find kanji from Kanjidic2 that share *reading*, sorted by frequency
    (most common kanji first so swaps are plausible to learners).

    Accepts hiragana or katakana; also matches dot-notation KUN entries
    (e.g. reading='うえ' matches r.value='うえ' and 'うえ.る').
    """
    kata = _hira_to_kata(reading)
    try:
        rows = conn.execute(
            """
            SELECT DISTINCT c.literal
            FROM character c
            JOIN rm_group g ON g.cid = c.ID
            JOIN reading r  ON r.gid = g.ID
            WHERE c.literal != ?
              AND r.r_type IN ('ja_on', 'ja_kun')
              AND (
                  r.value =  ?
               OR r.value =  ?
               OR r.value LIKE ?
               OR r.value LIKE ?
              )
            ORDER BY
              CASE WHEN c.freq IS NOT NULL AND c.freq != '' THEN 0 ELSE 1 END,
              CAST(c.freq AS INTEGER) ASC,
              CAST(c.grade AS INTEGER) DESC
            LIMIT ?
            """,
            (exclude_char, reading, kata, reading + ".%", kata + ".%", limit),
        ).fetchall()
        return [r[0] for r in rows if r[0]]
    except sqlite3.OperationalError:
        return []


def _get_swap_candidates(word: str, conn: sqlite3.Connection) -> list[str]:
    """
    For each kanji position in *word*, collect alternative kanji that share
    any of that position's readings (ON, KUN, JMdict variants), then build
    distractor words by substituting one kanji at a time.

    Candidates are interleaved across positions so no single kanji dominates.

    Examples
    --------
    題名(だいめい):
      題 ON:ダイ  → 代,第,台,大 → 代名,第名,台名,大名
      名 ON:メイ  → 命,明,鳴,迷 → 題命,題明,題鳴,題迷

    雨戸(あまど):
      雨 KUN:あめ/あま + JMdict → 天,尼,甘 → 天戸,尼戸
      戸 KUN:と/へ             → 都,土,度 → 雨都,雨度

    矢印(やじるし):
      矢 KUN:や               → 野,夜,八 → 野印,夜印
      印 ON:イン + KUN:しるし  → 院,員,引 → 矢院,矢員
    """
    positions = _kanji_positions(word)
    if not positions:
        return []

    alts_by_pos: dict[int, list[str]] = {}

    for pos, kanji in positions:
        # Collect all readings: Kanjidic2 ON+KUN + JMdict single-char variants
        all_readings: set[str] = _kd2_all_readings(kanji, conn)
        all_readings |= _jmdict_char_readings(kanji, conn)

        seen_chars: set[str] = {kanji}
        alts: list[str] = []
        for r in all_readings:
            for alt_char in _kd2_alts_for_reading(r, kanji, conn, limit=15):
                if alt_char not in seen_chars:
                    seen_chars.add(alt_char)
                    alts.append(alt_char)

        if alts:
            alts_by_pos[pos] = alts

    if not alts_by_pos:
        return []

    # Interleave: pick rank-0 from each position, then rank-1, etc.
    candidates: list[str] = []
    seen_words: set[str] = {word}
    max_rank = max(len(v) for v in alts_by_pos.values())

    for rank in range(max_rank):
        for pos, kanji in positions:
            if pos not in alts_by_pos or rank >= len(alts_by_pos[pos]):
                continue
            alt_char = alts_by_pos[pos][rank]
            distractor = word[:pos] + alt_char + word[pos + 1:]
            if distractor not in seen_words:
                seen_words.add(distractor)
                candidates.append(distractor)

    return candidates


# ── Public API ────────────────────────────────────────────────────────────────

def get_kanji_distractors(
    word: str,
    reading: str,
    vocab_data: list[dict],     # unused — kept for API compatibility with quiz.py
    count: int = 3,
) -> list[str]:
    """
    Return up to *count* kanji distractors for a writing quiz item.

    Tier 1 — JMdict homophones: same reading, different kanji word.
    Tier 2 — Kanjidic2 swap: probe all ON+KUN readings for each kanji position,
              find alternative single characters, substitute one at a time.

    Returns fewer than *count* if both tiers are exhausted.
    The caller (quiz.py) must skip the word in that case.
    """
    conn = _open_db()
    try:
        seen: set[str] = {word}
        candidates: list[str] = []

        # ── Tier 1: JMdict homophones ─────────────────────────────────────────
        for item in _get_homophones(reading, word, count * 4, conn):
            if item not in seen:
                seen.add(item)
                candidates.append(item)
            if len(candidates) >= count:
                break

        # ── Tier 2: Kanjidic2 swap ────────────────────────────────────────────
        if len(candidates) < count:
            for item in _get_swap_candidates(word, conn):
                if item not in seen:
                    seen.add(item)
                    candidates.append(item)
                if len(candidates) >= count:
                    break

    finally:
        conn.close()

    random.shuffle(candidates)
    return candidates[:count]