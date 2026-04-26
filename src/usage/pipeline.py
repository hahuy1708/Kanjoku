import json
import os
import re
from time import sleep

from src import constants
from src.usage.llm_client import call_ai_for_json
from src.usage.prompts import BATCH_USER_PROMPT, SYSTEM_PROMPT


def load_input(level):
    input_path = constants.vocab_path(level)

    if not os.path.exists(input_path):
        print(f"Input file not found: {input_path}")
        return []

    with open(input_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            return data
        except json.JSONDecodeError:
            print(f"Error decoding JSON from: {input_path}")
            return []


def save_quiz_to_file(quiz_data, quiz_type, level):
    output_dir = constants.output_dir_for(level)

    os.makedirs(output_dir, exist_ok=True)

    file_path = os.path.join(output_dir, f"{quiz_type}.json")

    existing_data = []

    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try:
                existing_data = json.load(f)
            except json.JSONDecodeError:
                existing_data = []

    existing_data.append(quiz_data)

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(existing_data, f, ensure_ascii=False, indent=2)

    print(f"Saved to: {file_path}")


def _load_processed_words(level):
    out_dir = os.path.join("data", "output", f"n{level}")
    processed = set()

    for quiz_type in ("usage",):
        file_path = os.path.join(out_dir, f"{quiz_type}.json")
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                try:
                    items = json.load(f)
                    for it in items:
                        if isinstance(it, dict) and it.get("word"):
                            processed.add(it.get("word"))
                except json.JSONDecodeError:
                    continue

    return processed


def _validate_usage_sentences(sentences, word):
    if not sentences or len(sentences) != 4:
        return False, f"Expected 4 sentences, got {len(sentences) if sentences else 0}"

    for i, s in enumerate(sentences):
        if "____" in s or "（　）" in s or "＿＿＿＿" in s or re.search(r"_{2,}", s):
            return False, f"Sentence {i} contains a blank: {s}"

    return True, ""


def run(level, limit, batch_size=4):
    all_vocab = load_input(level)

    if not all_vocab:
        print("No vocabulary loaded. Aborting.")
        return

    processed = _load_processed_words(level)

    worklist = [w for w in all_vocab if w.get("word") not in processed]

    if limit:
        worklist = worklist[:limit]

    total = len(worklist)
    if total == 0:
        print("Nothing to process — all words already processed.")
        return

    print(f"Processing {total} words in batches of {batch_size} (level N{level})")

    for batch_start in range(0, total, batch_size):
        batch = worklist[batch_start : batch_start + batch_size]
        idx_range = f"{batch_start+1}-{batch_start+len(batch)}"
        print(f"Processing batch {idx_range} ({len(batch)} words)")

        items = []
        for t in batch:
            items.append(
                {
                    "word": t.get("word"),
                    "furigana": t.get("furigana", ""),
                    "meaning": t.get("meaning", ""),
                    "level": level,
                }
            )

        user_prompt = BATCH_USER_PROMPT.format(items=json.dumps(items, ensure_ascii=False, indent=2))

        try:
            response = call_ai_for_json(SYSTEM_PROMPT, user_prompt)

            if not response:
                print("No response or failed to parse JSON from AI for this batch.")
                continue

            for item in response:
                word = item.get("word")
                if not word:
                    print("Skipping malformed item without 'word'")
                    continue

                usage = item.get("usage") or {}
                sentences = usage.get("sentences") or []
                is_valid, reason = _validate_usage_sentences(sentences, word)
                if not is_valid:
                    print(f"Invalid usage sentences for word '{word}': {reason}")
                    continue

                usage_item = {
                    "word": word,
                    "type": "usage",
                    "choices": usage.get("sentences"),
                    "answer_index": usage.get("answer_index"),
                }
                save_quiz_to_file(usage_item, "usage", level)

            sleep(20)

        except Exception as e:
            print(f"Error processing batch {idx_range}: {e}")
            continue
