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
              JMdict distractor engine
              ┌─────────────────────────────────────────┐
              │ 1. homophones (同音異義語) ← best option │
              │    same furigana but different kanji    │
              │ 2. same length reading, different kanji │
              │ 3. Fallback: JLPT vocab list            │
              └─────────────────────────────────────────┘
                     │
              shuffle → 4 choices + answer_index

```

- homophones (同音異義語) query JMdict -> same furigana but different kanji. This is the best option for distractors and JLPT exam also use this method
-  If there are not enough homophones, the engine will look for other words with the same length reading but different kanji. 
-  If there are still not enough distractors, it will fall back to using a JLPT vocab list to find additional options.

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
├── distractors.py    # All logic for generating distractors (3 priority strategies)
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

### Function: `make_hiragana_sentence(sentence, word, furigana) → str | None`

1. Check `word in sentence` → return `None` if not found
2. `sentence.replace(word, f"【{furigana}】", 1)` — replace first occurrence only
3. Return the replaced string

---

### Function: `get_homophones(reading, exclude_word, count) → list[str]`

Query JMdict for kanji words sharing the same reading:

```sql
SELECT DISTINCT k.text
FROM Kanji k
JOIN Kana kn ON kn.idseq = k.idseq
WHERE kn.text = ?              -- same reading
  AND k.text != ?              -- not the answer word
  AND k.text GLOB '*[一-龯]*'  -- must contain kanji
ORDER BY RANDOM()
LIMIT ?
```

Wrap in `try/except sqlite3.OperationalError` in case table `Kanji` does not exist → return `[]`.

---

### Function: `get_near_homophones(reading, exclude_word, count) → list[str]`

Fallback when homophones are insufficient. Same query but match reading **length** instead of exact reading:

```sql
SELECT DISTINCT k.text
FROM Kanji k
JOIN Kana kn ON kn.idseq = k.idseq
WHERE length(kn.text) = ?      -- same mora count
  AND kn.text != ?             -- different reading
  AND k.text != ?              -- not the answer word
  AND k.text GLOB '*[一-龯]*'
ORDER BY RANDOM()
LIMIT ?
```

---

### Function: `get_vocab_fallback(exclude_word, vocab_data, count) → list[str]`

Last resort. Filter `vocab_data` list for entries where:
- `entry["word"] != exclude_word`
- `entry["word"] != entry["furigana"]` — has kanji (not pure kana)
- `re.search(r'[一-龯]', entry["word"])` — contains kanji character

Shuffle and return first `count` items.

---

### Function: `get_kanji_distractors(word, reading, vocab_data, count=3) → list[str]`

Combine all three strategies in priority order:

1. Call `get_homophones(reading, word, count * 3)`
2. If `len < count` → extend with `get_near_homophones(reading, word, count * 3)`, deduplicating
3. If still `len < count` → extend with `get_vocab_fallback(word, vocab_data, count * 3)`, deduplicating

Shuffle the combined list, return first `count` items.

---

### Function: `run_writing(level, limit=None)`

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