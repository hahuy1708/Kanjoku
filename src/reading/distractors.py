from __future__ import annotations

from functools import lru_cache
import random
import sqlite3

from src.reading.kanji_reading import (
    KanjiSegment,
    LiteralSegment,
    decompose_word,
    get_jamdict,
    open_jmdict_connection,
)
from src.reading.utils import (
    apply_rendaku,
    extract_kanji_chars,
    is_pure_hiragana,
    kanji_distractor_score,
    remove_rendaku,
    split_morae,
    toggle_chouon,
    toggle_sokuon,
)


_LAST_DISTRACTOR_REPORT: list[dict[str, str | float]] = []


def get_last_reading_distractor_report() -> list[dict[str, str | float]]:
    return list(_LAST_DISTRACTOR_REPORT)


def _set_last_reading_distractor_report(rows: list[dict[str, str | float]]) -> None:
    global _LAST_DISTRACTOR_REPORT
    _LAST_DISTRACTOR_REPORT = rows


def _compose_segments(
    segments: tuple[KanjiSegment | LiteralSegment, ...],
    replacements: dict[int, str] | None = None,
) -> str:
    replacements = replacements or {}
    parts: list[str] = []
    for index, segment in enumerate(segments):
        if isinstance(segment, KanjiSegment):
            parts.append(replacements.get(index, segment.reading))
        else:
            parts.append(segment.text)
    return "".join(parts)


def _shared_kanji(word: str) -> list[str]:
    ordered: list[str] = []
    for ch in extract_kanji_chars(word):
        if ch not in ordered:
            ordered.append(ch)
    return ordered


@lru_cache(maxsize=2048)
def _whole_word_readings(word: str) -> frozenset[str]:
    readings: set[str] = set()
    result = get_jamdict().lookup(word)
    for entry in result.entries:
        for kana_form in entry.kana_forms:
            if kana_form.text:
                readings.add(kana_form.text)
    return frozenset(readings)


def _forbidden_readings(word: str) -> frozenset[str]:
    return _whole_word_readings(word)


def _segment_trap_variants(
    segments: tuple[KanjiSegment | LiteralSegment, ...],
    correct: str,
) -> list[tuple[str, str]]:
    variants: list[tuple[str, str]] = []

    for index, segment in enumerate(segments):
        if not isinstance(segment, KanjiSegment):
            continue

        reading = segment.reading
        morae = split_morae(reading)

        for candidate in toggle_chouon(reading):
            variants.append((_compose_segments(segments, {index: candidate}), "trap"))

        for candidate in toggle_sokuon(reading):
            variants.append((_compose_segments(segments, {index: candidate}), "trap"))

        if morae:
            suffix = "".join(morae[1:])
            voiced = apply_rendaku(morae[0])
            devoiced = remove_rendaku(morae[0])
            if voiced:
                variants.append((_compose_segments(segments, {index: voiced + suffix}), "trap"))
            if devoiced:
                variants.append((_compose_segments(segments, {index: devoiced + suffix}), "trap"))

        if len(morae) > 1 and morae[-1] in {"う", "い"}:
            variants.append((_compose_segments(segments, {index: "".join(morae[:-1])}), "trap"))

        if index > 0 and morae:
            suffix = "".join(morae[1:])
            voiced = apply_rendaku(morae[0])
            devoiced = remove_rendaku(morae[0])
            if voiced:
                variants.append((_compose_segments(segments, {index: voiced + suffix}), "trap"))
            if devoiced:
                variants.append((_compose_segments(segments, {index: devoiced + suffix}), "trap"))

    filtered: list[tuple[str, str]] = []
    seen: set[str] = set()
    for candidate, source in variants:
        if candidate == correct or candidate in seen:
            continue
        if not is_pure_hiragana(candidate):
            continue
        seen.add(candidate)
        filtered.append((candidate, source))
    return filtered


def _kanji_permutation_candidates(
    segments: tuple[KanjiSegment | LiteralSegment, ...],
    correct: str,
) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []

    for index, segment in enumerate(segments):
        if not isinstance(segment, KanjiSegment):
            continue

        for reading in segment.all_readings:
            if reading == segment.reading:
                continue
            candidate = _compose_segments(segments, {index: reading})
            if candidate != correct and is_pure_hiragana(candidate):
                candidates.append((candidate, "permutation"))

    deduped: list[tuple[str, str]] = []
    seen: set[str] = set()
    for candidate, source in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        deduped.append((candidate, source))
    return deduped


def _smart_db_fallback(
    conn: sqlite3.Connection,
    word: str,
    furigana: str,
    limit: int,
) -> list[tuple[str, str]]:
    kanji_chars = _shared_kanji(word)
    if not kanji_chars:
        return []

    clauses = []
    params: list[str] = []
    for ch in kanji_chars:
        clauses.append("INSTR(k.text, ?) > 0")
        params.append(ch)

    params.append(furigana)
    sql = f"""
        SELECT DISTINCT ka.text
        FROM Kanji k
        JOIN Kana ka ON k.idseq = ka.idseq
        WHERE ({' OR '.join(clauses)})
          AND ka.text != ?
          AND ka.text NOT GLOB '*[^ぁ-ん]*'
        LIMIT {limit}
    """

    rows = conn.execute(sql, params).fetchall()
    candidates = [row[0] for row in rows if row and row[0]]

    scored: list[tuple[float, str, str]] = []
    for candidate in candidates:
        scored.append((kanji_distractor_score(furigana, candidate, "db_fallback"), candidate, "db_fallback"))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [(candidate, source) for _, candidate, source in scored]


def get_reading_distractors(word: str, furigana: str, count: int = 3) -> list[str]:
    if not word or not furigana:
        _set_last_reading_distractor_report([])
        return []

    furigana = furigana.strip()
    if not furigana:
        _set_last_reading_distractor_report([])
        return []

    segments = tuple(decompose_word(word, furigana))
    forbidden = _forbidden_readings(word)

    candidates: list[tuple[str, str]] = []
    if segments:
        candidates.extend(_kanji_permutation_candidates(segments, furigana))
        candidates.extend(_segment_trap_variants(segments, furigana))

    conn = open_jmdict_connection()
    try:
        if len(candidates) < count:
            candidates.extend(_smart_db_fallback(conn, word, furigana, limit=max(60, count * 12)))
    finally:
        conn.close()

    seen: set[str] = {furigana}
    ranked: list[tuple[float, str, str]] = []
    for candidate, source in candidates:
        if candidate in seen or candidate in forbidden:
            continue
        if not is_pure_hiragana(candidate):
            continue
        seen.add(candidate)
        ranked.append((kanji_distractor_score(furigana, candidate, source), candidate, source))

    ranked.sort(key=lambda item: item[0], reverse=True)

    if len(ranked) < count:
        seeds = [furigana]
        if segments:
            seeds.append(_compose_segments(segments))
        for seed in seeds:
            for variant in toggle_chouon(seed) + toggle_sokuon(seed):
                if variant in seen or variant in forbidden or not is_pure_hiragana(variant):
                    continue
                seen.add(variant)
                ranked.append((kanji_distractor_score(furigana, variant, "trap"), variant, "trap"))
                if len(ranked) >= count * 3:
                    break
            if len(ranked) >= count * 3:
                break
        ranked.sort(key=lambda item: item[0], reverse=True)

    final = ranked[:count]
    _set_last_reading_distractor_report(
        [
            {"reading": candidate, "source": source, "score": score}
            for score, candidate, source in final
        ]
    )

    distractors = [candidate for _, candidate, _ in final]
    random.shuffle(distractors)
    return distractors[:count]
