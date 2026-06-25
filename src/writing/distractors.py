# src/writing/distractors.py
"""
Distractor generation for the writing (漢字書き) quiz.

Two tiers only:
  1. JMdict Homophones  — same full-word reading, different kanji  (best quality)
  2. Kanjidic2 Swap     — swap one kanji character with a homophonous character

If fewer than 3 distractors are found after both tiers, the word is skipped
by the caller (quiz.py). No near-homophones, no vocab fallback.
"""
from __future__ import annotations

import random
import re
import sqlite3
from functools import lru_cache

from jamdict import Jamdict
from src.reading.kanji_reading import decompose_word, KanjiSegment

_KANJI_RE = re.compile(r"[一-龯]")


# ── DB connections ────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _jmdict_path() -> str:
    return Jamdict().jmdict.ds.path


@lru_cache(maxsize=1)
def _kd2_path() -> str:
    return Jamdict().kd2.ds.path


def _jmdict_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_jmdict_path())
    conn.execute("PRAGMA query_only = ON")
    return conn


def _kd2_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_kd2_path())
    conn.execute("PRAGMA query_only = ON")
    return conn


def _hira_to_kata(text: str) -> str:
    return "".join(
        chr(ord(ch) + 0x60) if 0x3041 <= ord(ch) <= 0x3096 else ch
        for ch in text
    )


# ── Tier 1: JMdict homophones ─────────────────────────────────────────────────

def _get_homophones(reading: str, exclude_word: str, count: int) -> list[str]:
    """
    Kanji words in JMdict that share exactly the same reading as the answer word.
    Example: 機会(きかい) → 機械, 器械
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
        conn = _jmdict_conn()
        try:
            rows = conn.execute(sql, (reading, exclude_word, count)).fetchall()
            return [r[0] for r in rows if r and r[0]]
        finally:
            conn.close()
    except sqlite3.OperationalError:
        return []


# ── Tier 2: Kanjidic2 kanji swap ──────────────────────────────────────────────

def _jmdict_readings_for_char(kanji_char: str) -> list[str]:
    """
    Get all single-character readings from JMdict for a given kanji.
    This handles rendaku and other phonetic variants that Kanjidic2 may not
    list directly — e.g. 雨 has 'あめ' in Kanjidic2 but appears as 'あま'
    in compounds like 雨戸(あまど). JMdict single-char entries cover both.
    """
    try:
        conn = _jmdict_conn()
        try:
            sql = """
                SELECT DISTINCT kn.text FROM Kanji k
                JOIN Kana kn ON kn.idseq = k.idseq
                WHERE k.text = ?
                LIMIT 20
            """
            rows = conn.execute(sql, (kanji_char,)).fetchall()
            return [r[0] for r in rows if r[0]]
        finally:
            conn.close()
    except sqlite3.OperationalError:
        return []


def _kd2_alts_for_reading(reading: str, exclude_char: str) -> list[str]:
    """
    Find alternative kanji characters from Kanjidic2 that share the given reading.
    Sorted by frequency (most common first) so swaps are plausible.
    Accepts both hiragana and katakana, and kunyomi with okurigana (e.g. い.く).
    """
    kata = _hira_to_kata(reading)
    sql = """
        SELECT DISTINCT c.literal
        FROM character c
        JOIN reading r ON r.gid = c.ID
        WHERE c.literal != ?
          AND r.r_type IN ('ja_on', 'ja_kun')
          AND (
            r.value = ?
            OR r.value = ?
            OR r.value LIKE ?
            OR r.value LIKE ?
          )
        ORDER BY
          CASE WHEN c.freq IS NOT NULL AND c.freq != '' THEN 0 ELSE 1 END,
          CAST(c.freq AS INTEGER) ASC,
          CAST(c.grade AS INTEGER) DESC,
          c.ID ASC
    """
    try:
        conn = _kd2_conn()
        try:
            rows = conn.execute(
                sql,
                (exclude_char, reading, kata, reading + ".%", kata + ".%"),
            ).fetchall()
            return [r[0] for r in rows if r[0]]
        finally:
            conn.close()
    except sqlite3.OperationalError:
        return []


def _get_swap_candidates(word: str, furigana: str) -> list[str]:
    """
    Decompose word into kanji segments, then for each kanji character try
    all its readings (decompose_word reading + JMdict readings, to cover
    rendaku variants) and collect alternative kanji from Kanjidic2.

    Candidates are interleaved across positions so a single problematic
    character doesn't dominate the output.

    Example: 題名(だいめい) → 代名, 題明, 台名 …
    """
    segments = decompose_word(word, furigana)
    if not segments:
        return []

    # For each kanji position, collect alternative characters
    alts_by_pos: dict[int, list[str]] = {}
    for idx, seg in enumerate(segments):
        if not isinstance(seg, KanjiSegment):
            continue

        # All readings to probe: the one from decompose + JMdict single-char
        readings_to_try: set[str] = {seg.reading}
        readings_to_try.update(_jmdict_readings_for_char(seg.kanji))

        seen_chars: set[str] = {seg.kanji}
        alts: list[str] = []
        for r in readings_to_try:
            for ch in _kd2_alts_for_reading(r, seg.kanji):
                if ch not in seen_chars:
                    seen_chars.add(ch)
                    alts.append(ch)

        if alts:
            alts_by_pos[idx] = alts

    if not alts_by_pos:
        return []

    # Interleave: rank 0 from pos 0, rank 0 from pos 1, rank 1 from pos 0 …
    candidates: list[str] = []
    seen_words: set[str] = {word}
    max_rank = max(len(v) for v in alts_by_pos.values())

    for rank in range(max_rank):
        for idx in sorted(alts_by_pos.keys()):
            alts = alts_by_pos[idx]
            if rank >= len(alts):
                continue
            new_parts = [
                alts[rank] if j == idx
                else (seg.kanji if isinstance(seg, KanjiSegment) else seg.text)
                for j, seg in enumerate(segments)
            ]
            new_word = "".join(new_parts)
            if new_word not in seen_words:
                seen_words.add(new_word)
                candidates.append(new_word)

    return candidates


# ── Public API ────────────────────────────────────────────────────────────────

def get_kanji_distractors(
    word: str,
    reading: str,
    vocab_data: list[dict],  # unused, kept for API compatibility with quiz.py
    count: int = 3,
) -> list[str]:
    """
    Return up to *count* kanji distractors for a writing quiz item.

    Tier 1 — JMdict homophones (same reading, different kanji word).
              Highest quality: tests exactly what JLPT writing questions test.
    Tier 2 — Kanjidic2 swap (replace one kanji character with a homophone).
              Used only when tier 1 is insufficient.

    Returns fewer than *count* items if both tiers are exhausted.
    The caller must skip the word in that case.
    """
    seen: set[str] = {word}
    candidates: list[str] = []

    # Tier 1: JMdict homophones
    for item in _get_homophones(reading, word, count * 4):
        if item not in seen:
            seen.add(item)
            candidates.append(item)
        if len(candidates) >= count:
            break

    # Tier 2: Kanjidic2 swap — only if tier 1 didn't give enough
    if len(candidates) < count:
        for item in _get_swap_candidates(word, reading):
            if item not in seen:
                seen.add(item)
                candidates.append(item)
            if len(candidates) >= count:
                break

    random.shuffle(candidates)
    return candidates[:count]