# src/quiz_reading.py
import json
import random
import os
import sqlite3
from pathlib import Path

from jamdict import Jamdict

from src import constants

_jam = Jamdict()
_DB_PATH = _jam.jmdict.ds.path


def _get_db():
    """Open a fresh SQLite connection per call to avoid thread issues."""
    return sqlite3.connect(_DB_PATH)


def _extract_kanji_chars(text: str) -> list[str]:
    return [ch for ch in text if "\u4e00" <= ch <= "\u9fff"]


def _extend_unique(target: list[str], values: list[str], blocked: str):
    for value in values:
        if value and value != blocked and value not in target:
            target.append(value)


def get_reading_distractors(word: str, furigana: str, count: int = 3) -> list[str]:
    """
    Build stronger distractors from JMdict.

    Priority:
      1. Same kanji spelling, different reading.
      2. Words sharing at least one kanji character.
      3. Generic hiragana fallback by near length.
    """
    if not word or not furigana:
        return []

    conn = _get_db()
    cur = conn.cursor()
    results = []

    try:
        target_len = len(furigana)

        # 1) Same exact kanji spelling, but alternative kana reading.
        cur.execute(
            """
            SELECT DISTINCT ka.text
            FROM Kanji kj
            JOIN Kana ka ON ka.idseq = kj.idseq
            WHERE kj.text = ?
              AND ka.text != ?
                            AND ka.text NOT GLOB '*[^ぁ-ん]*'
                            AND ABS(LENGTH(ka.text) - LENGTH(?)) <= 1
            ORDER BY RANDOM()
            LIMIT ?
            """,
                        (word, furigana, furigana, count * 4),
        )
        _extend_unique(results, [r[0] for r in cur.fetchall()], furigana)

        # 2) Share at least one kanji with target word.
        for kanji_char in _extract_kanji_chars(word):
            if len(results) >= count:
                break
            cur.execute(
                """
                SELECT DISTINCT ka.text
                FROM Kanji kj
                JOIN Kana ka ON ka.idseq = kj.idseq
                WHERE kj.text LIKE ?
                  AND kj.text != ?
                  AND ka.text != ?
                                    AND ka.text NOT GLOB '*[^ぁ-ん]*'
                  AND ABS(LENGTH(ka.text) - LENGTH(?)) <= 1
                ORDER BY RANDOM()
                LIMIT ?
                """,
                (f"%{kanji_char}%", word, furigana, furigana, count * 3),
            )
            _extend_unique(results, [r[0] for r in cur.fetchall()], furigana)

        # 3) Fallback: near-length kana words with same first kana.
        if len(results) < count:
            cur.execute(
                """
                SELECT DISTINCT text
                FROM Kana
                WHERE text != ?
                                    AND text NOT GLOB '*[^ぁ-ん]*'
                  AND LENGTH(text) BETWEEN ? AND ?
                  AND SUBSTR(text, 1, 1) = SUBSTR(?, 1, 1)
                ORDER BY RANDOM()
                LIMIT ?
                """,
                (furigana, max(1, target_len - 1), target_len + 1, furigana, count * 5),
            )
            _extend_unique(results, [r[0] for r in cur.fetchall()], furigana)

        # 4) Final fallback: near-length kana words.
        if len(results) < count:
            cur.execute(
                """
                SELECT DISTINCT text
                FROM Kana
                WHERE text != ?
                                    AND text NOT GLOB '*[^ぁ-ん]*'
                  AND LENGTH(text) BETWEEN ? AND ?
                ORDER BY RANDOM()
                LIMIT ?
                """,
                (furigana, max(1, target_len - 1), target_len + 1, count * 8),
            )
            _extend_unique(results, [r[0] for r in cur.fetchall()], furigana)

    finally:
        conn.close()

    random.shuffle(results)
    return results[:count]


def run_reading(level: int, limit: int = None):
    input_file = constants.vocab_path(level)
    output_dir = constants.output_dir_for(level)
    output_file = os.path.join(output_dir, "reading.json")

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    quiz_results = []
    limit_items = data[:limit] if limit else data
    skipped = 0

    for entry in limit_items:
        word = entry.get("word")
        furigana = entry.get("furigana")

        if not word or not furigana or word == furigana:
            skipped += 1
            continue

        distractors = get_reading_distractors(word, furigana, count=3)

        if len(distractors) < 3:
            print(f"  [WARN] Not enough distractors for {word} ({furigana}), skipping")
            skipped += 1
            continue

        choices = distractors + [furigana]
        random.shuffle(choices)
        correct_idx = choices.index(furigana)

        quiz_item = {
            "word": word,
            "type": "reading",
            "question": f"「{word}」の読み方は？",
            "choices": choices,
            "answer_index": correct_idx
        }
        quiz_results.append(quiz_item)

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(quiz_results, f, ensure_ascii=False, indent=2)

    print(f"Reading quiz done: {len(quiz_results)} items, {skipped} skipped -> {output_file}")
