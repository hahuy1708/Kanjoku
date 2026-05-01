# src/reading/utils.py
from __future__ import annotations

_HIRAGANA_START = 0x3041
_HIRAGANA_END   = 0x3096
_KANJI_START    = 0x4E00
_KANJI_END      = 0x9FFF
_KATAKANA_START = 0x30A1
_KATAKANA_END   = 0x30F6

def is_hiragana(ch: str) -> bool:
    return _HIRAGANA_START <= ord(ch) <= _HIRAGANA_END

def is_kanji(ch: str) -> bool:
    return _KANJI_START <= ord(ch) <= _KANJI_END

def is_katakana(ch: str) -> bool:
    return _KATAKANA_START <= ord(ch) <= _KATAKANA_END

def is_pure_hiragana(text: str) -> bool:
    return bool(text) and all(is_hiragana(ch) for ch in text)


def kata_to_hira(text: str) -> str:
    return "".join(chr(ord(ch) - 0x60) if is_katakana(ch) else ch for ch in text)


def strip_kun_marker(kun: str) -> str | None:
    if not kun:
        return None
    if kun.startswith("-"):
        return None
    normalized = kata_to_hira(kun.split(".", 1)[0])
    return normalized or None


_SMALL_KANA = set("ぁぃぅぇぉゃゅょ")

def split_morae(text: str) -> list[str]:
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


def get_okurigana(word: str) -> str:
    result = []
    for ch in reversed(word):
        if is_hiragana(ch):
            result.append(ch)
        else:
            break
    return "".join(reversed(result))

def extract_kanji_chars(word: str) -> list[str]:
    return [ch for ch in word if is_kanji(ch)]


def has_sokuon(reading: str) -> bool:
    return "っ" in reading

def has_yoon(reading: str) -> bool:
    return any(ch in reading for ch in ("ゃ", "ゅ", "ょ"))

def has_long_vowel_marker(reading: str) -> bool:
    return "ー" in reading


_VOICED_TO_UNVOICED = {
    "が": "か", "ぎ": "き", "ぐ": "く", "げ": "け", "ご": "こ",
    "ざ": "さ", "じ": "し", "ず": "す", "ぜ": "せ", "ぞ": "そ",
    "だ": "た", "ぢ": "ち", "づ": "つ", "で": "て", "ど": "と",
    "ば": "は", "び": "ひ", "ぶ": "ふ", "べ": "へ", "ぼ": "ほ",
    "ぱ": "は", "ぴ": "ひ", "ぷ": "ふ", "ぺ": "へ", "ぽ": "ほ",
}
_UNVOICED_TO_VOICED = {
    "か": "が", "き": "ぎ", "く": "ぐ", "け": "げ", "こ": "ご",
    "さ": "ざ", "し": "じ", "す": "ず", "せ": "ぜ", "そ": "ぞ",
    "た": "だ", "ち": "ぢ", "つ": "づ", "て": "で", "と": "ど",
    "は": "ば", "ひ": "び", "ふ": "ぶ", "へ": "べ", "ほ": "ぼ",
}


def _replace_initial_mora(mora: str, mapping: dict[str, str]) -> str | None:
    if not mora:
        return None
    head = mora[0]
    if head not in mapping:
        return None
    return mapping[head] + mora[1:]


def apply_rendaku(mora: str) -> str | None:
    return _replace_initial_mora(mora, _UNVOICED_TO_VOICED)


def remove_rendaku(mora: str) -> str | None:
    return _replace_initial_mora(mora, _VOICED_TO_UNVOICED)


def toggle_chouon(reading: str) -> list[str]:
    variants: set[str] = set()
    if not reading:
        return []

    if reading.endswith(("う", "い")) and len(reading) > 1:
        variants.add(reading[:-1])

    morae = split_morae(reading)
    if not morae:
        return []

    last = morae[-1]
    if last in {"しょ", "じょ", "ちょ", "きょ", "ぎょ", "ひょ", "ぴょ", "みょ", "りょ", "にょ"}:
        variants.add(reading + "う")
    elif last in {"せ", "ぜ", "て", "で", "け", "げ", "へ", "べ", "ぺ"}:
        variants.add(reading + "い")
    elif last in {"こ", "ご", "そ", "ぞ", "と", "ど", "ほ", "ぼ", "ぽ", "お", "ろ", "も", "の"}:
        variants.add(reading + "う")

    return [variant for variant in variants if variant != reading]


def toggle_sokuon(reading: str) -> list[str]:
    variants: set[str] = set()
    if not reading:
        return []

    if "っ" in reading:
        index = reading.index("っ")
        variants.add(reading[:index] + reading[index + 1:])
        if index + 1 < len(reading):
            variants.add(reading[:index] + "つ" + reading[index + 1:])
        return [variant for variant in variants if variant != reading]

    morae = split_morae(reading)
    for index, mora in enumerate(morae):
        if mora and mora[0] in {"か", "き", "く", "け", "こ", "さ", "し", "す", "せ", "そ", "た", "ち", "つ", "て", "と", "ぱ", "ぴ", "ぷ", "ぺ", "ぽ", "は", "ひ", "ふ", "へ", "ほ"}:
            variants.add("".join(morae[:index] + ["っ" + mora] + morae[index + 1:]))

    return [variant for variant in variants if variant != reading]


def kanji_distractor_score(correct: str, candidate: str, source: str) -> float:
    if not correct or not candidate or candidate == correct:
        return 0.0

    source_bonus = {
        "permutation": 0.9,
        "trap": 0.8,
        "db_fallback": 0.5,
    }.get(source, 0.4)

    correct_morae = split_morae(correct)
    candidate_morae = split_morae(candidate)
    if not correct_morae or not candidate_morae:
        return source_bonus

    shared = sum(1 for left, right in zip(correct_morae, candidate_morae) if left == right)
    shared_ratio = shared / max(len(correct_morae), len(candidate_morae))

    edge_bonus = 0.0
    if correct_morae[0] == candidate_morae[0]:
        edge_bonus += 0.08
    if correct_morae[-1] == candidate_morae[-1]:
        edge_bonus += 0.08

    length_bonus = 0.06 if len(correct_morae) == len(candidate_morae) else max(0.0, 0.06 - (0.02 * abs(len(correct_morae) - len(candidate_morae))))
    return round(source_bonus + (0.2 * shared_ratio) + edge_bonus + length_bonus, 6)