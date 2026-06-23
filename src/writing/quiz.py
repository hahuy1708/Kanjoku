# src/writing/quiz.py
"""
Writing quiz (漢字書き) generator — fully local, no LLM required.

Flow per word:
  1. Skip kana-only entries (word == furigana) or entries without kanji.
  2. Fetch natural sentences from Tatoeba DB that contain the kanji word.
  3. Replace the kanji word with 【furigana】 to form the display sentence.
     If no Tatoeba sentence is found, fall back to a word-only sentence.
  4. Generate 3 distractors using the three-tier JMdict engine.
  5. Shuffle the four choices and record the correct answer index.
"""
from __future__ import annotations

import json
import os
import random
import re

from src import constants
from src.context.tatoeba_db import TatoebaDB
from src.writing.sentences import make_hiragana_sentence
from src.writing.distractors import get_kanji_distractors

# Regex to detect at least one CJK Unified Ideograph
_KANJI_RE = re.compile(r"[一-龯]")


def run_writing(level: int, limit: int | None = None) -> None:
    """
    Generate a writing quiz JSON file for a given JLPT level.

    Parameters
    ----------
    level : JLPT level number (1-5)
    limit : max number of vocab entries to process (None = all)

    Output
    ------
    ``data/output/n{level}/writing.json``
    """
    vocab_path = constants.vocab_path(level)
    output_dir = constants.output_dir_for(level)

    # ── Load vocab ────────────────────────────────────────────────────────────
    with open(vocab_path, "r", encoding="utf-8") as f:
        vocab_data: list[dict] = json.load(f)

    items = vocab_data[:limit] if limit else vocab_data

    # ── Tatoeba DB ────────────────────────────────────────────────────────────
    db = TatoebaDB(constants.TATOEBA_DB)

    quiz_results: list[dict] = []
    skipped = 0
    no_sentence = 0

    for entry in items:
        word: str     = entry.get("word", "")
        furigana: str = entry.get("furigana", "")

        # ── Skip conditions ───────────────────────────────────────────────────
        if not word or not furigana:
            skipped += 1
            continue
        if word == furigana:  # pure kana — nothing to write in kanji
            skipped += 1
            continue
        if not _KANJI_RE.search(word):  # no kanji character at all
            skipped += 1
            continue

        # ── Build display sentence ────────────────────────────────────────────
        candidates = db.sentences_for_word(word, min_chars=8, max_chars=50, limit=15)
        random.shuffle(candidates)

        sentence: str | None = None
        for text in candidates:
            result = make_hiragana_sentence(text, word, furigana)
            if result is not None:
                sentence = result
                break

        if sentence is None:
            # Fallback: word-only "sentence"
            sentence = f"【{furigana}】"
            no_sentence += 1

        # ── Generate distractors ──────────────────────────────────────────────
        distractors = get_kanji_distractors(word, furigana, vocab_data, count=3)

        if len(distractors) < 3:
            print(f"  [WARN] Only {len(distractors)} distractors for {word}({furigana}), skipping")
            skipped += 1
            continue

        # ── Build choices ─────────────────────────────────────────────────────
        choices = distractors[:3] + [word]
        random.shuffle(choices)
        answer_index = choices.index(word)

        quiz_results.append(
            {
                "word": word,
                "type": "writing",
                "sentence": sentence,
                "question": "下線のひらがなを漢字にすると？",
                "choices": choices,
                "answer_index": answer_index,
            }
        )

    # ── Write output ──────────────────────────────────────────────────────────
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "writing.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(quiz_results, f, ensure_ascii=False, indent=2)

    total = len(items)
    success = len(quiz_results)
    print(
        f"[N{level}] Writing quiz: {success}/{total} generated "
        f"(skipped={skipped}, no_sentence={no_sentence})"
        f" -> {output_file}"
    )
