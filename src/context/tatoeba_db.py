# src/context/tatoeba_db.py
"""
Read-only interface to the local Tatoeba SQLite database.

Responsibilities:
- Find natural sentences that contain a target word.
- Expose a clean API so the quiz generator never touches SQL directly.
"""
from __future__ import annotations

import random
import re
import sqlite3
from functools import lru_cache
from pathlib import Path


class TatoebaDB:
    """Thin wrapper around tatoeba.db for quiz-related lookups."""

    def __init__(self, db_path: str | Path) -> None:
        self._path = str(db_path)
        self._verify()

    # ── Internal ─────────────────────────────────────────────────────────────
    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.execute("PRAGMA query_only = ON")
        return conn

    def _verify(self) -> None:
        if not Path(self._path).exists():
            raise FileNotFoundError(
                f"tatoeba.db not found at: {self._path}\n"
                "Run:  python scripts/build_tatoeba_db.py --help"
            )

    # ── Public API ────────────────────────────────────────────────────────────
    def sentence_count(self) -> int:
        with self._conn() as conn:
            return conn.execute("SELECT COUNT(*) FROM sentences").fetchone()[0]

    def sentences_for_word(
        self,
        word: str,
        min_chars: int = 12,
        max_chars: int = 60,
        limit: int = 20,
    ) -> list[str]:
        """
        Return up to *limit* Japanese sentences that contain *word*,
        filtered by character length.
        """
        with self._conn() as conn:
            cur = conn.execute(
                """
                SELECT s.text
                FROM sentences s
                JOIN word_index wi ON wi.sentence_id = s.id
                WHERE wi.word = ?
                  AND length(s.text) BETWEEN ? AND ?
                ORDER BY RANDOM()
                LIMIT ?
                """,
                (word, min_chars, max_chars, limit),
            )
            return [r[0] for r in cur.fetchall()]

    def has_sentences_for_word(self, word: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                "SELECT 1 FROM word_index WHERE word = ? LIMIT 1", (word,)
            )
            return cur.fetchone() is not None