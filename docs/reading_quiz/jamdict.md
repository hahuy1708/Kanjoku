# Jamdict

This document provides instructions for using the Jamdict library and its data for generating reading and context quizzes, along with insights on how to effectively utilize it in the quiz generation process.

---

## 1. Install jamdict and data

```bash
python -m pip install --upgrade pip
pip install wheel setuptools==65.5.0
pip install jamdict
pip install jamdict_data_fix
```

Reason for using jamdict-data-fix:

- Original jamdict-data has issues when building.
- jamdict-data-fix is better compatible in Windows venv.


## 3. Implementation notes (concise)

This section explains how the reading distractor generator works.

- Purpose: produce high-quality, exam-style distractor readings for kanji
  words.

- Key rules:
  - Exact mora-length match: distractors must have the same mora count as
    the correct reading.
  - Okurigana: if the word has trailing hiragana, distractors must keep the
    same okurigana suffix (checks commonly cap to last 2 morae).
  - Forbidden readings: exclude all valid readings of the whole word and
    of each kanji component.
  - JMdict existence: final distractors must exist in JMdict's `Kana` table.
  - Mora-swap priority: generate single-mora substitutions first; use DB
    candidates as fallback.
  - Phonetic ranking: rank candidates by `phonetic_similarity` to prefer
    more confusable choices.

- Main functions: `get_reading_distractors()`, `_get_forbidden_readings()`,
  `_mora_swap_candidates()`, `_db_candidates()`, and utilities in
  `src/reading/utils.py`.

- Troubleshooting:
  - Words written entirely in kana (`word == furigana`) are skipped.
  - If there are too few distractors, check JMdict data installation or
    adjust the code if you want to relax constraints.

- Run example:

```bash
python main.py --level 2 --mode reading --limit 200
```

Output: `data/output/n{level}/reading.json`.
