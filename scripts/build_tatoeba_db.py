#!/usr/bin/env python3
# scripts/build_tatoeba_db.py
"""
One-time script: import Tatoeba CSV exports into a local SQLite database.

Download these 2 files from https://downloads.tatoeba.org/exports/
  - per_language/jpn_sentences.tsv   (~50MB)  — Japanese sentences
  - jpn_indices.csv                  (~17MB)  — word index per sentence

Usage:
    python scripts/build_tatoeba_db.py \\
        --sentences data/tatoeba/jpn_sentences.tsv \\
        --indices   data/tatoeba/jpn_indices.csv \\
        --output    data/tatoeba/tatoeba.db

Runtime: ~2-4 minutes for ~230k sentences.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import time
from pathlib import Path


# ── Schema ────────────────────────────────────────────────────────────────────
SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous  = NORMAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sentences (
    id      INTEGER PRIMARY KEY,
    text    TEXT    NOT NULL,
    length  INTEGER GENERATED ALWAYS AS (length(text)) VIRTUAL
);

-- One row per (sentence, word) pair from jpn_indices
CREATE TABLE IF NOT EXISTS word_index (
    sentence_id INTEGER NOT NULL,
    word        TEXT    NOT NULL,
    reading     TEXT,
    FOREIGN KEY (sentence_id) REFERENCES sentences(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_word        ON word_index(word);
CREATE INDEX IF NOT EXISTS idx_sent_word   ON word_index(sentence_id, word);
"""

# ── Tatoeba index entry parser ────────────────────────────────────────────────
# Entry format: word[reading](checked) or word[reading] or bare word
_INDEX_RE = re.compile(r"^([^\[\(]+)(?:\[([^\]]*)\])?")


def parse_index_entry(raw: str) -> tuple[str, str | None]:
    """
    Parse one token from the jpn_indices 'indices' column.
    Returns (word, reading_or_None).
    """
    m = _INDEX_RE.match(raw.strip())
    if not m:
        return raw.strip(), None
    word    = m.group(1).strip()
    reading = m.group(2).strip() if m.group(2) else None
    return word, reading or None


# ── Import helpers ────────────────────────────────────────────────────────────
def import_sentences(conn: sqlite3.Connection, sentences_path: Path) -> int:
    """Import jpn_sentences.tsv into `sentences` table."""
    cur   = conn.cursor()
    count = 0
    print(f"Importing sentences from {sentences_path} ...")

    with open(sentences_path, encoding="utf-8") as f:
        batch: list[tuple] = []
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            sid, lang, text = parts[0], parts[1], "\t".join(parts[2:])
            if lang != "jpn":
                continue
            try:
                batch.append((int(sid), text))
            except ValueError:
                continue

            if len(batch) >= 10_000:
                cur.executemany("INSERT OR IGNORE INTO sentences(id, text) VALUES (?,?)", batch)
                count += len(batch)
                batch.clear()
                print(f"  {count:,} sentences...", end="\r")

        if batch:
            cur.executemany("INSERT OR IGNORE INTO sentences(id, text) VALUES (?,?)", batch)
            count += len(batch)

    conn.commit()
    print(f"  {count:,} sentences imported.          ")
    return count


def import_indices(conn: sqlite3.Connection, indices_path: Path) -> int:
    """Import jpn_indices.csv into `word_index` table."""
    cur   = conn.cursor()
    count = 0
    skipped = 0
    print(f"Importing word index from {indices_path} ...")

    # Some index rows may reference sentence IDs that are not present in the
    # per_language export (or the snapshot differs). To keep the DB consistent
    # and avoid FK failures, pre-load valid sentence IDs and skip unknown ones.
    valid_sentence_ids = {r[0] for r in cur.execute("SELECT id FROM sentences")}

    with open(indices_path, encoding="utf-8") as f:
        batch: list[tuple] = []
        for line in f:
            parts = line.rstrip("\n").split("\t")
            # columns: sentence_id, meaning_id, [index_entries...]
            if len(parts) < 3:
                continue
            try:
                sentence_id = int(parts[0])
            except ValueError:
                continue

            if sentence_id not in valid_sentence_ids:
                skipped += 1
                continue

            # The "indices" column is a whitespace-separated list of tokens.
            # Example: "は 二十歳(はたち){２０歳} になる[01]{になりました}"
            for column in parts[2:]:
                column = column.strip()
                if not column:
                    continue
                for raw in column.split():
                    raw = raw.strip()
                    if not raw:
                        continue
                    word, reading = parse_index_entry(raw)
                    if not word:
                        continue
                    batch.append((sentence_id, word, reading))
                    count += 1

            if len(batch) >= 50_000:
                cur.executemany(
                    "INSERT INTO word_index(sentence_id, word, reading) VALUES (?,?,?)",
                    batch,
                )
                batch.clear()
                print(f"  {count:,} word entries...", end="\r")

        if batch:
            cur.executemany(
                "INSERT INTO word_index(sentence_id, word, reading) VALUES (?,?,?)",
                batch,
            )

    conn.commit()
    if skipped:
        print(f"  {count:,} word index entries imported (skipped {skipped:,} sentence rows).")
    else:
        print(f"  {count:,} word index entries imported.   ")
    return count


# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Build Tatoeba SQLite DB")
    parser.add_argument("--sentences", required=True, help="Path to jpn_sentences.tsv")
    parser.add_argument("--indices",   required=True, help="Path to jpn_indices.csv")
    parser.add_argument("--output",    required=True, help="Output path for tatoeba.db")
    args = parser.parse_args()

    sentences_path = Path(args.sentences)
    indices_path   = Path(args.indices)
    output_path    = Path(args.output)

    for p in (sentences_path, indices_path):
        if not p.exists():
            print(f"ERROR: File not found: {p}", file=sys.stderr)
            sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Building Tatoeba DB -> {output_path}")
    t0 = time.time()

    conn = sqlite3.connect(output_path)
    conn.executescript(SCHEMA)

    import_sentences(conn, sentences_path)
    import_indices(conn, indices_path)

    # Verify
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM sentences")
    n_sent = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM word_index")
    n_idx = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT word) FROM word_index")
    n_words = cur.fetchone()[0]

    conn.close()

    elapsed = time.time() - t0
    db_mb   = output_path.stat().st_size / 1_048_576

    print()
    print("=== Done ===")
    print(f"  Sentences : {n_sent:,}")
    print(f"  Word index: {n_idx:,} entries / {n_words:,} unique words")
    print(f"  DB size   : {db_mb:.1f} MB")
    print(f"  Time      : {elapsed:.1f}s")


if __name__ == "__main__":
    main()