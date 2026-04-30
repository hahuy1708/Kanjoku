# src/context/quiz.py
"""
Context quiz (穴埋め) generator — fully local, no LLM required.

Flow per word:
  1. Look up natural sentences from Tatoeba DB.
  2. Pick the best sentence (clean, word appears once, blank not at pos 0).
  3. Generate 3 distractors from the same JLPT vocab list (same POS preferred).
  4. Shuffle choices and record the correct index.
"""
from __future__ import annotations

import json
import os
import random
from pathlib import Path

from src.context.tatoeba_db import TatoebaDB
from src.context.sentences import make_blank, pick_sentence
from src.context.distractors import get_context_distractors


def run_context(
    level: int,
    vocab_path: str,
    output_dir: str,
    tatoeba_db_path: str,
    limit: int | None = None,
) -> None:
    """
    Generate context quiz JSON for a JLPT level.

    Parameters
    ----------
    level            : JLPT level (1-5)
    vocab_path       : input vocab JSON (list of {word, furigana, meaning})
    output_dir       : directory to write context.json
    tatoeba_db_path  : path to tatoeba.db (built by scripts/build_tatoeba_db.py)
    limit            : max words to process (None = all)
    """
    db = TatoebaDB(tatoeba_db_path)

    with open(vocab_path, "r", encoding="utf-8") as f:
        all_vocab: list[dict] = json.load(f)

    items = all_vocab[:limit] if limit else all_vocab
    quiz_results: list[dict] = []
    skipped_no_sentence = 0
    skipped_no_distractor = 0

    for entry in items:
        word: str     = entry.get("word", "")
        furigana: str = entry.get("furigana", "")
        meaning: str  = entry.get("meaning", "")

        # Context quiz only needs the surface form (word). Furigana may be empty
        # for kana words in vocab lists.
        if not word:
            continue

        # ── Step 1: find a usable sentence ───────────────────────────────────
        candidates = db.sentences_for_word(word, min_chars=12, max_chars=55)
        sentence   = pick_sentence(candidates, word)

        if sentence is None:
            skipped_no_sentence += 1
            continue

        blanked = make_blank(sentence, word)

        # ── Step 2: generate distractors ─────────────────────────────────────
        distractors = get_context_distractors(
            word=word,
            sentence=sentence,
            all_vocab=all_vocab,
            count=3,
        )

        if len(distractors) < 3:
            skipped_no_distractor += 1
            continue

        # ── Step 3: build quiz item ───────────────────────────────────────────
        choices = distractors[:3] + [word]
        random.shuffle(choices)
        correct_idx = choices.index(word)

        quiz_results.append(
            {
                "word": word,
                "type": "context",
                "sentence": blanked,
                "choices": choices,
                "answer_index": correct_idx,
            }
        )

    # ── Write output ──────────────────────────────────────────────────────────
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "context.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(quiz_results, f, ensure_ascii=False, indent=2)

    total   = len(items)
    success = len(quiz_results)
    print(
        f"[N{level}] Context quiz: {success}/{total} generated "
        f"(no_sentence={skipped_no_sentence}, no_distractor={skipped_no_distractor})"
        f" → {output_file}"
    )