from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import sqlite3

from jamdict import Jamdict

from src.reading.utils import kata_to_hira, is_kanji, is_pure_hiragana, strip_kun_marker
from src.reading.utils import mora_length


@dataclass(frozen=True)
class KanjiReadings:
    on: tuple[str, ...]
    kun: tuple[str, ...]


@dataclass(frozen=True)
class KanjiSegment:
    kanji: str
    reading: str
    all_readings: tuple[str, ...]


@dataclass(frozen=True)
class LiteralSegment:
    text: str


@lru_cache(maxsize=1)
def get_jamdict() -> Jamdict:
    return Jamdict()


@lru_cache(maxsize=1)
def _db_path() -> str:
    return get_jamdict().jmdict.ds.path


def open_jmdict_connection() -> sqlite3.Connection:
    return sqlite3.connect(_db_path())


_MATCH_DEVOICE = str.maketrans(
    {
        "が": "か", "ぎ": "き", "ぐ": "く", "げ": "け", "ご": "こ",
        "ざ": "さ", "じ": "し", "ず": "す", "ぜ": "せ", "ぞ": "そ",
        "だ": "た", "ぢ": "ち", "づ": "つ", "で": "て", "ど": "と",
        "ば": "は", "び": "ひ", "ぶ": "ふ", "べ": "へ", "ぼ": "ほ",
        "ぱ": "は", "ぴ": "ひ", "ぷ": "ふ", "ぺ": "へ", "ぽ": "ほ",
    }
)


def _normalize_for_match(text: str) -> str:
    normalized = kata_to_hira(text).replace("っ", "つ").translate(_MATCH_DEVOICE)
    normalized = normalized.replace("あま", "あめ")
    return normalized


def _normalize_for_storage(text: str) -> str:
    normalized = _normalize_for_match(text)
    return normalized.replace("あま", "あめ") if normalized.startswith("あま") else normalized


def _normalize_reading(value: object) -> str | None:
    raw = getattr(value, "value", value)
    if not raw:
        return None
    raw = str(raw)
    if raw.startswith("-"):
        return None
    normalized = raw.split(".", 1)[0]
    normalized = normalized.replace("-", "")
    normalized = kata_to_hira(normalized)
    if not normalized or not is_pure_hiragana(normalized):
        return None
    return normalized


def _collect_readings(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    collected: list[str] = []
    for value in values:
        normalized = _normalize_reading(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            collected.append(normalized)
    return tuple(collected)


@lru_cache(maxsize=4096)
def get_kanji_readings(kanji_char: str) -> KanjiReadings:
    if not kanji_char or len(kanji_char) != 1 or not is_kanji(kanji_char):
        return KanjiReadings(on=(), kun=())

    character = get_jamdict().get_char(kanji_char)
    if character is None:
        return KanjiReadings(on=(), kun=())

    on_values: list[str] = []
    kun_values: list[str] = []
    for group in character.rm_groups or []:
        on_values.extend(group.on_readings or [])
        kun_values.extend(group.kun_readings or [])

    return KanjiReadings(
        on=_collect_readings(on_values),
        kun=_collect_readings(kun_values),
    )


@lru_cache(maxsize=4096)
def _jmdict_single_char_readings(kanji_char: str) -> tuple[str, ...]:
    if not kanji_char or len(kanji_char) != 1 or not is_kanji(kanji_char):
        return ()

    try:
        conn = sqlite3.connect(_db_path())
        conn.execute("PRAGMA query_only = ON")
        try:
            rows = conn.execute(
                """
                SELECT DISTINCT kn.text
                FROM Kanji k
                JOIN Kana kn ON kn.idseq = k.idseq
                WHERE k.text = ?
                LIMIT 50
                """,
                (kanji_char,),
            ).fetchall()
        finally:
            conn.close()
    except sqlite3.OperationalError:
        return ()

    readings: list[str] = []
    seen: set[str] = set()
    for row in rows:
        normalized = _normalize_reading(row[0])
        if normalized and normalized not in seen:
            seen.add(normalized)
            readings.append(_normalize_for_storage(normalized))
    return tuple(readings)


def _candidate_readings_for_kanji(kanji_char: str, allow_long_kun: bool = True) -> tuple[str, ...]:
    readings = get_kanji_readings(kanji_char)
    merged: list[str] = []
    seen: set[str] = set()
    for reading in readings.on + readings.kun:
        if not allow_long_kun and reading in readings.kun and mora_length(reading) > 1:
            continue
        normalized = _normalize_for_storage(reading)
        if normalized not in seen:
            seen.add(normalized)
            merged.append(normalized)

    for reading in _jmdict_single_char_readings(kanji_char):
        if not allow_long_kun and mora_length(reading) > 1:
            continue
        if reading not in seen:
            seen.add(reading)
            merged.append(reading)

    return tuple(merged)


def _read_word_segments(word: str, furigana: str) -> tuple[KanjiSegment | LiteralSegment, ...] | None:
    if not word or not furigana:
        return None

    word = word.strip()
    furigana = kata_to_hira(furigana.strip())
    if not word or not furigana:
        return None
    comparison_furigana = _normalize_for_match(furigana)

    @lru_cache(maxsize=None)
    def solve(word_index: int, reading_index: int) -> tuple[KanjiSegment | LiteralSegment, ...] | None:
        if word_index == len(word) and reading_index == len(furigana):
            return ()
        if word_index >= len(word) or reading_index > len(furigana):
            return None

        ch = word[word_index]

        if not is_kanji(ch):
            end = word_index
            while end < len(word) and not is_kanji(word[end]):
                end += 1
            literal = word[word_index:end]
            if comparison_furigana.startswith(_normalize_for_match(literal), reading_index):
                rest = solve(end, reading_index + len(literal))
                if rest is not None:
                    return (LiteralSegment(text=literal),) + rest
            return None

        # Long kunyomi such as うえ, あめ, and しるし are essential for
        # compound words like 目上, 雨戸, and 矢印, so we should always try
        # them during decomposition instead of filtering them out.
        readings = _candidate_readings_for_kanji(ch, allow_long_kun=True)
        if not readings:
            return None

        ordered = tuple(sorted(readings, key=lambda value: (-len(value), value)))
        for reading in ordered:
            if comparison_furigana.startswith(_normalize_for_match(reading), reading_index):
                rest = solve(word_index + 1, reading_index + len(reading))
                if rest is not None:
                    return (
                        KanjiSegment(kanji=ch, reading=reading, all_readings=ordered),
                    ) + rest

        return None

    return solve(0, 0)


def decompose_word(word: str, furigana: str) -> list[KanjiSegment | LiteralSegment]:
    segments = _read_word_segments(word, furigana)
    if segments is None:
        return []
    return list(segments)
