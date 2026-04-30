# Tatoeba

This document provides instructions for downloading and preparing the Tatoeba dataset for use in the context quiz project and some insights of its usage.

---

## 1. Download

Source: **https://downloads.tatoeba.org/exports/**

Download 2 files:

1. `jpn_sentences.tsv`: All of the sentences in Japanese.
- `per_language/` → `jpn_sentences.tsv.bz2` 
2. `jpn_indices.csv`: Index of vocabulary in each sentence 

> **Note:** you might need to download the `.bz2` file if you cant find the `.tsv` file, then extract it.

Put 2 file to folder `data/tatoeba/`:

```
data/tatoeba/
├── jpn_sentences.tsv
└── jpn_indices.csv
```

## 2. Build tatoeba.db

```bash
python scripts/build_tatoeba_db.py \
    --sentences data/tatoeba/jpn_sentences.tsv \
    --indices   data/tatoeba/jpn_indices.csv \
    --output    data/tatoeba/tatoeba.db
```

Output will be something like this:

```
Building Tatoeba DB -> data/tatoeba/tatoeba.db
Importing sentences from data/tatoeba/jpn_sentences.tsv ...
  230,000 sentences imported.
Importing word index from data/tatoeba/jpn_indices.csv ...
  1,200,000 word index entries imported.

=== Done ===
  Sentences : 230,000
  Word index: 1,200,000 entries / 85,000 unique words
  DB size   : ~120 MB
  Time      : ~3 min
```

> **Only need to run once.** After that, `tatoeba.db` can be used indefinitely — no need to keep the 2 CSV files if you want to save storage space.


## 3. Output format

```json
[
  {
    "word": "音楽",
    "type": "context",
    "sentence": "彼女は____を聞きながら勉強する。",
    "choices": ["映画", "音楽", "運動", "料理"],
    "answer_index": 1
  },
  {
    "word": "習慣",
    "type": "context",
    "sentence": "彼は毎日運動する____がある。",
    "choices": ["習慣", "経験", "目的", "記憶"],
    "answer_index": 0
  }
]
```


## 4. Implementation notes (concise)

This section summarizes how the code uses the Tatoeba data.

- DB build: run `scripts/build_tatoeba_db.py` to create `data/tatoeba/tatoeba.db`.
  The script creates two tables: `sentences(id, text, length)` and
  `word_index(sentence_id, word, reading)`, with indexes on `word` and
  `(sentence_id, word)`. The index parser extracts tokens like
  `word[reading]` or `word[reading](checked)`.

- API: `src/context/tatoeba_db.py` provides `TatoebaDB.sentences_for_word(word, min_chars=12, max_chars=60, limit=20)`
  which returns randomized sentences containing the word. `has_sentences_for_word(word)` checks existence.

- Sentence selection: `src/context/sentences.py` filters candidates to remove
  noisy sentences (URLs, long Latin words, long numbers, nested brackets),
  requires the target to appear exactly once, and prefers sentences where
  the word is not at position 0. The blank is produced with
  `make_blank(text, word)` (replaces the first occurrence with `____`).

- Distractors: `src/context/distractors.py` builds candidates from the JLPT
  vocab list and uses JMdict (via `jamdict`) to get a broad POS. It
  excludes words present in the sentence, prefers same-POS words, ranks by
  character-length closeness, shuffles the top window (top_k=60), and
  selects the first three valid choices.

- Running: use the top-level CLI:

```bash
python main.py --level 2 --mode context --limit 200
```

  Input vocab: `data/vocab_json/n{level}.json` • DB path: `data/tatoeba/tatoeba.db`
  Output: `data/output/n{level}/context.json`.

Note: building the DB is a one-time step. If `tatoeba.db` is missing, run
the build script. To change thresholds, edit `src/context/quiz.py` or
`src/context/tatoeba_db.py`.
