# Writing Quiz

- Writing quiz is a type of quiz where the user is given a sentence with a word in hiragana with underlines. The user must choose the correct kanji for the word from a list of options. The options include the correct kanji and three distractors.

- Example:
```
問題：この【きかい】はめったにない。
　　  1. 気会　2. 機会　3. 機械　4. 器械
正解：**2**
```

## Quiz Architecture

```
vocab JSON  →  word(kanji) + furigana(hiragana)
                     │
              Tatoeba DB
              sentences_for_word(word)   →  real sentence containing kanji
                     │
              replace word → 【furigana】  →  display sentence with hiragana reading
                     │
              JMdict + Kanjidic2 distractor engine
              ┌─────────────────────────────────────────┐
              │ 1. JMdict Homophones (同音異義語)        │
              │    same furigana but different kanji    │
              │ 2. Kanjidic2 Kanji Swap                 │
              │    phonetically identical (swap kanji)  │
              └─────────────────────────────────────────┘
                     │
              shuffle → 4 choices + answer_index

```

- **JMdict Homophones**: Same furigana but different kanji. Best option for whole-word homophones (e.g., `機会` -> `機械`).
- **Kanjidic2 Kanji Swap**: Decompose word using `decompose_word`, find alternative kanji with same pronunciation from Kanjidic2 (e.g. `題名` -> `代名`, `題明`), and swap them. Extremely effective for compounds with rare whole-word homophones.

## Output format

```json
[
  {
    "word": "機会",
    "type": "writing",
    "sentence": "この【きかい】はめったにない。",
    "questions": "下線のひらがなを漢字にすると？",
    "choices": ["気会", "機会", "機械", "器械"],
    "answer_index": 1
  },
  {
    "word": "習慣",
    "type": "writing",
    "sentence": "彼は毎日運動する【しゅうかん】がある。",
    "questions": "下線のひらがなを漢字にすると？",
    "choices": ["習慣", "経験", "目的", "記憶"],
    "answer_index": 0
  }
]
```

## Implementation

### Structure

```
src/writing/
├── __init__.py
├── quiz.py           # Main function to run the quiz
├── distractors.py    # All logic for generating distractors (2 strategies)
└── sentences.py      # Contains make_hiragana_sentence() and string processing helpers
```

### Dependencies

```python
from jamdict import Jamdict
from src import constants
from src.context.tatoeba_db import TatoebaDB
```

JMdict SQLite path: `Jamdict().jmdict.ds.path` — assign to module-level `_DB_PATH`.  
Open connection per call via `sqlite3.connect(_DB_PATH)` to avoid thread issues.

---

### `run_writing(level, limit=None)`

**Input:** `constants.vocab_path(level)` → load vocab JSON  
**Output:** `constants.output_dir_for(level)/writing.json`

Loop over each `entry` in vocab:

- `word`     = `entry["word"]`
- `furigana` = `entry["furigana"]`

**Skip conditions** (increment `skipped`):
- `word` or `furigana` is empty
- `word == furigana` — pure kana, nothing to guess
- no kanji in `word` (`re.search(r'[一-龯]', word)` is None)

**Sentence:**

1. Call `TatoebaDB().sentences_for_word(word, min_chars=8, max_chars=50, limit=15)`
2. Shuffle candidates, iterate → call `make_hiragana_sentence(text, word, furigana)` until non-None result
3. If no Tatoeba sentence found → `sentence = f"【{furigana}】"` (word-only fallback), increment `no_sentence`

**Distractors:**

1. Call `get_kanji_distractors(word, furigana, vocab_data, count=3)`
2. If `len < 3` → skip entry (log warn)

**Build choices:**

```python
choices = distractors[:3] + [word]
random.shuffle(choices)
answer_index = choices.index(word)
```

**Append to results:**

```python
{
    "word": word,
    "type": "writing",
    "sentence": sentence,
    "question": "下線のひらがなを漢字にすると？",
    "choices": choices,
    "answer_index": answer_index,
}
```

Write results to output file, print summary: total items / skipped / no\_sentence count.

---

### Integration: `main.py`

1. Import `from src import quiz_writing`
2. Add `"writing"` to `--mode` choices, including `"local"` group
3. Call `quiz_writing.run_writing(level, limit)` when mode in `("all", "local", "writing")`

#### Run example:
```
python main.py --level 2 --mode writing --limit 20
```