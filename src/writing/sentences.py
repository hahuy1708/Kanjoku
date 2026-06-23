# src/writing/sentences.py
"""
Sentence helpers for the writing quiz.

Responsibilities:
- make_hiragana_sentence: replace the kanji word in a sentence with 【furigana】.
"""
from __future__ import annotations


def make_hiragana_sentence(sentence: str, word: str, furigana: str) -> str | None:
    """
    Replace the first occurrence of *word* inside *sentence* with 【furigana】.

    Parameters
    ----------
    sentence : the raw Tatoeba sentence
    word     : the kanji word to replace  (e.g. "機会")
    furigana : the hiragana reading       (e.g. "きかい")

    Returns
    -------
    The modified sentence string, or None if *word* is not found in *sentence*.
    """
    if word not in sentence:
        return None
    return sentence.replace(word, f"【{furigana}】", 1)
