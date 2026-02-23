# src/quiz_reading.py
import json
import random
from pathlib import Path
from distractors import generate_reading_distractors

def process_reading_quiz(input_file: str, output_file: str, limit: int = None):
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

if __name__ == "__main__":
    INPUT_PATH = "data/vocab_json/n2.json"

    # OUTPUT_PATH = "data/test/output_reading.json"
    OUTPUT_PATH = "data/output/n2/reading.json"

    
    print("Creating reading quiz...")
    process_reading_quiz(INPUT_PATH, OUTPUT_PATH, limit=10) 
    print(f"Completed! File saved to: {OUTPUT_PATH}")