# src/prompts.py
SYSTEM_PROMPT = """You are a Japanese JLPT question writer.
You must output ONLY valid JSON. No markdown, no code fences, no commentary.
Use natural Japanese, JLPT-appropriate difficulty.
"""


CONTEXT_QUIZ_PROMPT = """Create a JLPT-style Context (fill-in-the-blank) multiple-choice question.

Target word:
- word: {word}
- reading (furigana, hiragana): {furigana}
- meaning (English): {meaning}
- level: N{level}

Requirements:
- Output JSON with this exact schema:
	{{
		"sentence": "... ____ ...",
		"hint": "short JP hint (optional, can be empty string)",
		"explanation": "short JP explanation (optional, can be empty string)"
	}}
- The sentence must be Japanese and include exactly one blank: "____".
- The correct answer to fill the blank must be exactly the target "word" (not a synonym).
- Do NOT include answer options; the program will provide choices.
- Avoid proper nouns and overly specific facts.
"""


USAGE_QUIZ_PROMPT = """Create a JLPT-style Usage question.

Target word:
- word: {word}
- reading (furigana, hiragana): {furigana}
- meaning (English): {meaning}
- level: N{level}

Requirements:
- Output JSON with this exact schema:
	{{
		"sentences": ["A", "B", "C", "D"],
		"answer_index": 0,
		"explanation": "short JP explanation (optional, can be empty string)"
	}}
- Provide exactly 4 Japanese sentences.
- Exactly ONE sentence uses the target word correctly in context.
- The other 3 sentences must be plausible but wrong (collocation/meaning/register/grammar).
- All 4 sentences must contain the target word exactly once.
- answer_index is 0..3 corresponding to the correct sentence.
"""