# src/quiz_reading.py
import json
import random
import os
from pathlib import Path
from src.distractors import generate_reading_distractors
from src import constants

def run_reading(level: int, limit: int = None):
    input_file = constants.vocab_path(level)
    output_dir = constants.output_dir_for(level)
    output_file = os.path.join(output_dir, "reading.json")

    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    quiz_results = []
    limit_items = data[:limit] if limit else data

    for entry in limit_items:
        word = entry.get("word")
        furigana = entry.get("furigana")

        if not word or not furigana or word == furigana:
            continue

        distractors = generate_reading_distractors(furigana)
        choices = distractors + [furigana]
        random.shuffle(choices)
        correct_idx = choices.index(furigana)

        quiz_item = {
            "word": word,
            "type": "reading",
            "question": f"「{word}」？",
            "choices": choices,
            "answer_index": correct_idx
        }
        quiz_results.append(quiz_item)

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(quiz_results, f, ensure_ascii=False, indent=2)

    print(f"Completed. File saved to: {output_file}")
