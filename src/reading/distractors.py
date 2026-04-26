# src/reading/distractors.py
"""
High-quality reading distractor generation for JLPT-style quiz.

Design goals
============
1. **Exact mora-length match** — distractor must have the same number of morae
   as the correct reading.  No exceptions.

2. **Okurigana constraint** — if the target word has okurigana (trailing
   hiragana, e.g. 詰*まる*, 軟*らかい*), every distractor reading must end
   with the same okurigana suffix.  This prevents answers like つまり for
   詰まる(つまる).

3. **Forbidden-reading filter** — all valid readings of the target word AND of
   every individual kanji it contains are excluded.  This prevents はつ from
   appearing as a distractor for 発つ(たつ).

4. **JMdict-existence check** — every distractor must be an actual reading that
   exists in JMdict.  No fabricated strings.

5. **Mora-swap priority** — the best distractors differ from the correct reading
   by exactly one mora (JLPT exam style).  We generate swap-variants first,
   then fall back to DB queries.

6. **Phonetic ranking** — among valid candidates we rank by phonetic_similarity
   so the most confusable options are chosen (harder quiz).
"""
from __future__ import annotations

import random
import sqlite3
from functools import lru_cache

from jamdict import Jamdict

from src.reading.utils import (
    extract_kanji_chars,
    get_mora_substitutes,
    get_okurigana,
    has_sokuon,
    has_yoon,
    is_pure_hiragana,
    mora_length,
    phonetic_similarity,
    split_morae,
)

# ── Shared DB connection (read-only, thread-local is fine for scripts) ────────
_jam = Jamdict()
_DB_PATH: str = _jam.jmdict.ds.path


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


# ── Forbidden readings ────────────────────────────────────────────────────────
@lru_cache(maxsize=2048)
def _get_forbidden_readings(word: str) -> frozenset[str]:
    """
    All valid readings of *word* AND of every kanji component.
    Cached so repeated calls for the same word are free.
    """
    forbidden: set[str] = set()

    # Readings of the whole word
    result = _jam.lookup(word)
    for entry in result.entries:
        for kf in entry.kana_forms:
            forbidden.add(kf.text)

    # Readings of individual kanji (catches partial-readings like はつ for 発)
    for ch in extract_kanji_chars(word):
        result2 = _jam.lookup(ch)
        for entry in result2.entries:
            for kf in entry.kana_forms:
                forbidden.add(kf.text)

    return frozenset(forbidden)


# ── Existence check ───────────────────────────────────────────────────────────
def _exists_in_jmdict(conn: sqlite3.Connection, reading: str) -> bool:
    cur = conn.execute("SELECT 1 FROM Kana WHERE text = ? LIMIT 1", (reading,))
    return cur.fetchone() is not None


# ── Mora-swap candidates ──────────────────────────────────────────────────────
def _mora_swap_candidates(furigana: str, okurigana: str) -> list[str]:
    """
    Generate all single-mora-swap variants of *furigana* that:
    - remain pure hiragana
    - have the same mora length
    - end with *okurigana* (if non-empty, capped at 2 morae)

    For long okurigana (>2 morae), we allow swapping within the okurigana
    too so the candidate pool isn't empty.
    """
    morae = split_morae(furigana)
    oku_morae = split_morae(okurigana) if okurigana else []

    # For long okurigana (>2), only fix the last 2 morae; swap freely elsewhere
    fixed_tail = min(len(oku_morae), 2)
    free_positions = range(len(morae) - fixed_tail)

    candidates: list[str] = []
    for i in free_positions:
        for sub in get_mora_substitutes(morae[i]):
            new_morae = morae[:i] + [sub] + morae[i + 1:]
            candidate = "".join(new_morae)
            if is_pure_hiragana(candidate):
                candidates.append(candidate)
    return candidates


# ── DB-based fallback pool ────────────────────────────────────────────────────
def _db_candidates(
    conn: sqlite3.Connection,
    furigana: str,
    okurigana: str,
    target_mora_len: int,
    limit: int = 200,
) -> list[str]:
    """
    Query JMdict for pure-hiragana readings that satisfy hard constraints:
    - same mora length as furigana
    - ends with okurigana suffix (capped at 2 morae to avoid over-constraining)
    - same sokuon presence
    - same yoon presence
    """
    conditions = [
        "text != ?",
        "text NOT GLOB '*[^ぁ-ん]*'",    # pure hiragana only
        "text NOT GLOB '*ー*'",          # no katakana prolonged mark
    ]
    params: list = [furigana]

    if okurigana:
        # Cap okurigana suffix to last 2 morae to avoid over-constraining
        # e.g. 'らかい' -> 'かい', 'まる' -> 'まる', 'む' -> 'む'
        from src.reading.utils import split_morae as _split
        oku_morae = _split(okurigana)
        suffix = "".join(oku_morae[-2:]) if len(oku_morae) > 2 else okurigana
        conditions.append("text LIKE ?")
        params.append("%" + suffix)

    if has_sokuon(furigana):
        conditions.append("INSTR(text, 'っ') > 0")
    else:
        conditions.append("INSTR(text, 'っ') = 0")

    if has_yoon(furigana):
        conditions.append(
            "(INSTR(text,'ゃ')>0 OR INSTR(text,'ゅ')>0 OR INSTR(text,'ょ')>0)"
        )

    sql = f"""
        SELECT DISTINCT text FROM Kana
        WHERE {' AND '.join(conditions)}
        ORDER BY RANDOM()
        LIMIT {limit}
    """
    cur = conn.execute(sql, params)
    raw = [r[0] for r in cur.fetchall()]

    # Filter to exact mora-length (SQL LENGTH() counts chars, not morae)
    return [r for r in raw if mora_length(r) == target_mora_len]


# ── Main public function ──────────────────────────────────────────────────────
def get_reading_distractors(
    word: str,
    furigana: str,
    count: int = 3,
) -> list[str]:
    """
    Return *count* high-quality distractor readings for a JLPT reading quiz.

    Parameters
    ----------
    word     : kanji/mixed spelling, e.g. '詰まる'
    furigana : correct hiragana reading, e.g. 'つまる'
    count    : number of distractors needed (default 3)
    """
    if not word or not furigana:
        return []

    okurigana     = get_okurigana(word)
    target_mlen   = mora_length(furigana)
    forbidden     = _get_forbidden_readings(word)

    conn = _get_conn()
    try:
        # ── Step 1: mora-swap candidates (highest quality) ──────────────────
        swap_candidates = _mora_swap_candidates(furigana, okurigana)
        # Validate: must exist in JMdict AND not forbidden
        valid_swaps: list[str] = []
        for cand in swap_candidates:
            if cand not in forbidden and _exists_in_jmdict(conn, cand):
                valid_swaps.append(cand)

        # ── Step 2: DB fallback pool ─────────────────────────────────────────
        db_pool = _db_candidates(conn, furigana, okurigana, target_mlen)
        valid_db: list[str] = [c for c in db_pool if c not in forbidden]

    finally:
        conn.close()

    # ── Step 3: Rank by phonetic similarity (most confusable first) ──────────
    def rank(candidates: list[str]) -> list[str]:
        scored = [(phonetic_similarity(furigana, c), c) for c in candidates]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored]

    ranked_swaps = rank(valid_swaps)
    ranked_db    = rank(valid_db)

    # ── Step 4: Fill quota — swaps first, then DB, then random shuffle ───────
    chosen: list[str] = []
    seen: set[str] = {furigana}

    for pool in (ranked_swaps, ranked_db):
        for cand in pool:
            if cand not in seen:
                chosen.append(cand)
                seen.add(cand)
            if len(chosen) >= count:
                break
        if len(chosen) >= count:
            break

    # Shuffle so answer position isn't predictable from distractor quality
    random.shuffle(chosen)
    return chosen[:count]