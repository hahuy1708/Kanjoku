# src/reading/utils.py
"""
Utility functions for Japanese reading analysis.
No external deps beyond stdlib + jamdict.
"""
from __future__ import annotations

# ── Hiragana ranges ──────────────────────────────────────────────────────────
_HIRAGANA_START = 0x3041
_HIRAGANA_END   = 0x3096
_KANJI_START    = 0x4E00
_KANJI_END      = 0x9FFF

def is_hiragana(ch: str) -> bool:
    return _HIRAGANA_START <= ord(ch) <= _HIRAGANA_END

def is_kanji(ch: str) -> bool:
    return _KANJI_START <= ord(ch) <= _KANJI_END

def is_pure_hiragana(text: str) -> bool:
    return bool(text) and all(is_hiragana(ch) for ch in text)


# ── Mora-level helpers ───────────────────────────────────────────────────────
# Small kana that attach to the previous character (not independent morae)
# Note: sokuon 'っ' is an independent mora and must NOT be merged here.
_SMALL_KANA = set("ぁぃぅぇぉゃゅょ")

def split_morae(text: str) -> list[str]:
    """
    Split hiragana string into morae (音節).
    'しゅくしょう' -> ['しゅ', 'く', 'しょ', 'う']
    """
    morae: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if i + 1 < len(text) and text[i + 1] in _SMALL_KANA:
            morae.append(ch + text[i + 1])
            i += 2
        else:
            morae.append(ch)
            i += 1
    return morae

def mora_length(text: str) -> int:
    return len(split_morae(text))


# ── Okurigana extraction ─────────────────────────────────────────────────────
def get_okurigana(word: str) -> str:
    """
    Return trailing hiragana suffix of a word (okurigana).
    '詰まる' -> 'まる'
    '軟らかい' -> 'らかい'
    '基準'   -> ''
    """
    result = []
    for ch in reversed(word):
        if is_hiragana(ch):
            result.append(ch)
        else:
            break
    return "".join(reversed(result))

def extract_kanji_chars(word: str) -> list[str]:
    return [ch for ch in word if is_kanji(ch)]


# ── Phonetic feature flags ───────────────────────────────────────────────────
def has_sokuon(reading: str) -> bool:
    return "っ" in reading

def has_yoon(reading: str) -> bool:
    return any(ch in reading for ch in ("ゃ", "ゅ", "ょ"))

def has_long_vowel_marker(reading: str) -> bool:
    """ー (katakana prolonged sound mark) sometimes appears in loanword furigana."""
    return "ー" in reading


# ── Mora substitution table ──────────────────────────────────────────────────
# Groups of perceptually similar morae — used for "swap-one-mora" generation.
# Each group contains sounds that learners commonly confuse.
_MORA_CONFUSION_GROUPS: list[list[str]] = [
    # ka-row
    ["か", "が", "か"],
    ["き", "ぎ", "き"],
    ["く", "ぐ", "く"],
    ["け", "げ", "け"],
    ["こ", "ご", "こ"],
    # sa-row
    ["さ", "ざ", "さ"],
    ["し", "じ", "し"],
    ["す", "ず", "す"],
    ["せ", "ぜ", "せ"],
    ["そ", "ぞ", "そ"],
    # ta-row
    ["た", "だ", "た"],
    ["ち", "じ", "ぢ"],
    ["つ", "づ", "ず"],
    ["て", "で", "て"],
    ["と", "ど", "と"],
    # na-row (confusable with ma/ra in listening)
    ["な", "に", "ぬ", "ね", "の"],
    # ha-row
    ["は", "ば", "ぱ"],
    ["ひ", "び", "ぴ"],
    ["ふ", "ぶ", "ぷ"],
    ["へ", "べ", "ぺ"],
    ["ほ", "ぼ", "ぽ"],
    # ma-row
    ["ま", "も", "む", "め", "み"],
    # ra-row (confusable with na/da)
    ["ら", "だ", "な"],
    ["り", "に", "ぢ"],
    ["る", "ぬ", "づ"],
    ["れ", "ね", "で"],
    ["ろ", "の", "ど"],
    # ya-row / yoon bases
    ["や", "ゃ"],
    ["ゆ", "ゅ"],
    ["よ", "ょ"],
    # long-vowel endings
    ["ん", "う", "い"],
    # short vowels
    ["あ", "お"],
    ["い", "え"],
    ["う", "お"],
]

# Build char -> set-of-substitutes map
_MORA_SUB_MAP: dict[str, list[str]] = {}
for _group in _MORA_CONFUSION_GROUPS:
    for _m in _group:
        existing = _MORA_SUB_MAP.setdefault(_m, [])
        for _other in _group:
            if _other != _m and _other not in existing:
                existing.append(_other)

def get_mora_substitutes(mora: str) -> list[str]:
    """Return list of morae that could be confused with *mora*."""
    return _MORA_SUB_MAP.get(mora, [])


# ── Similarity scoring ───────────────────────────────────────────────────────
def phonetic_similarity(a: str, b: str) -> float:
    """
    Return a [0, 1] score of how phonetically similar two readings are.
    Higher = more confusable = better distractor.
    """
    if a == b:
        return 1.0

    ma = split_morae(a)
    mb = split_morae(b)

    # Must be same mora-length (hard constraint enforced elsewhere, but score 0 if not)
    if len(ma) != len(mb):
        return 0.0

    n = len(ma)
    matches = sum(1 for x, y in zip(ma, mb) if x == y)

    # Edge matches weighted more (first/last mora most salient in listening)
    edge_bonus = 0.0
    if ma[0] == mb[0]:
        edge_bonus += 0.15
    if ma[-1] == mb[-1]:
        edge_bonus += 0.10

    base = matches / n
    return min(1.0, base + edge_bonus)