# src/pipeline.py
from src.llm_client import call_ai_for_json
from src.prompts import SYSTEM_PROMPT, CONTEXT_QUIZ_PROMPT, USAGE_QUIZ_PROMPT
from src.distractors import get_semantic_distractors
import json
import random

def shuffle_quiz(correct_answer, distractors):
    options = list(dict.fromkeys(distractors + [correct_answer]))
    
    while len(options) < 4:
        options.append("---") 
        
    random.shuffle(options)
    correct_index = options.index(correct_answer)
    return options, correct_index

def test_llm_quiz():
    all_vocab = [
        {"word": "題名", "furigana": "だいめい", "meaning": "title", "level": 2},
        {"word": "でたらめ", "furigana": "でたらめ", "meaning": "nonsense/random", "level": 2},
        {"word": "いきなり", "furigana": "いきなり", "meaning": "suddenly", "level": 2},
        {"word": "心得る", "furigana": "こころえる", "meaning": "to understand", "level": 2}
    ]
    
    target = all_vocab[0]
    print(f"Call AI api for: {target['word']}...")

    # --- QUIZ CONTEXT ---
    context_prompt = CONTEXT_QUIZ_PROMPT.format(
        word=target['word'], furigana=target['furigana'], meaning=target['meaning'], level=target['level']
    )
    context_data = call_ai_for_json(SYSTEM_PROMPT, context_prompt)
    
    if context_data:
        distractors = get_semantic_distractors(target['word'], target['level'], all_vocab)
        choices, correct_idx = shuffle_quiz(target['word'], distractors)
        
        context_quiz = {
            "type": "context",
            "prompt": "（____）に入る語は？",
            "sentence": context_data.get("sentence"),
            "choices": choices,
            "answer_index": correct_idx,
            "explanation": context_data.get("explanation")
        }
        print("\n=== RESULT CONTEXT ===")
        print(json.dumps(context_quiz, ensure_ascii=False, indent=2))


    # --- QUIZ USAGE ---
    usage_prompt = USAGE_QUIZ_PROMPT.format(
        word=target['word'], furigana=target['furigana'], meaning=target['meaning'], level=target['level']
    )
    usage_data = call_ai_for_json(SYSTEM_PROMPT, usage_prompt)
    
    if usage_data:
        usage_quiz = {
            "type": "usage",
            "prompt": f"「{target['word']}の使い方は？。",
            "choices": usage_data.get("sentences"),
            "answer_index": usage_data.get("answer_index"),
            "explanation": usage_data.get("explanation")
        }
        print("\n=== RESULT USAGE ===")
        print(json.dumps(usage_quiz, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    test_llm_quiz()