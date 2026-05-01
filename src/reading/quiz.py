# src/reading/quiz.py
"""
Reading quiz generator.

Uses src.reading.distractors for high-quality, constraint-aware distractors.
Uses JMdict SQLite.
"""
from __future__ import annotations

import json
import os
import random
from pathlib import Path

from src.reading.distractors import get_last_reading_distractor_report, get_reading_distractors


def run_reading(
    level: int,
    vocab_path: str,
    output_dir: str,
    limit: int | None = None,
) -> None:
    """
    Generate reading quiz JSON for a given JLPT level.

    Parameters
    ----------
    level      : JLPT level number (1-5)
    vocab_path : path to input vocab JSON  (list of {word, furigana, meaning})
    output_dir : directory to write reading.json
    limit      : max number of items to process (None = all)
    """
    with open(vocab_path, "r", encoding="utf-8") as f:
        data: list[dict] = json.load(f)

    items = data[:limit] if limit else data
    quiz_results: list[dict] = []
    skipped = 0
    warnings = 0

    for entry in items:
        word: str     = entry.get("word", "")
        furigana: str = entry.get("furigana", "")

        # Skip kana-only words (word == furigana → no kanji to test)
        if not word or not furigana or word == furigana:
            skipped += 1
            continue

        distractors = get_reading_distractors(word, furigana, count=3)
        report = get_last_reading_distractor_report()
        if report:
            debug_text = ", ".join(f"{row['reading']}[{row['source']}]" for row in report)
            print(f"  [DEBUG] {word}({furigana}) -> {debug_text}")

        if len(distractors) < 3:
            print(f"  [WARN] Only {len(distractors)} distractors for {word}({furigana}), skipping")
            warnings += 1
            skipped += 1
            continue

        choices = distractors[:3] + [furigana]
        random.shuffle(choices)
        correct_idx = choices.index(furigana)

        quiz_results.append(
            {
                "word": word,
                "type": "reading",
                "question": f"「{word}」の読み方は？",
                "choices": choices,
                "answer_index": correct_idx,
            }
        )

    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "reading.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(quiz_results, f, ensure_ascii=False, indent=2)

    print(
        f"[N{level}] Reading quiz: {len(quiz_results)} items generated, "
        f"{skipped} skipped ({warnings} warn) → {output_file}"
    )