# scripts/check.py
"""Debug decompose_word matching."""
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.reading.kanji_reading import _normalize_for_match, _candidate_readings_for_kanji
from src.reading.utils import kata_to_hira

# Test normalization
print("=== Normalization tests ===")
pairs = [
    ("めうえ", "め + うえ"),
    ("やじるし", "や + しるし"),
    ("あまど", "あめ + と"),
]
for reading, desc in pairs:
    print(f"  {reading} -> normalized: {_normalize_for_match(reading)} ({desc})")

# Check: does normalization of the full reading match normalization of parts?
print("\n=== Match simulation for 目上(めうえ) ===")
full = _normalize_for_match("めうえ")
print(f"  full normalized: '{full}'")
# 目 = め
for r in _candidate_readings_for_kanji("目"):
    nr = _normalize_for_match(r)
    if full.startswith(nr):
        remaining = full[len(nr):]
        print(f"  目 reading '{r}' -> normalized '{nr}' -> matches! remaining='{remaining}'")
        for r2 in _candidate_readings_for_kanji("上"):
            nr2 = _normalize_for_match(r2)
            if remaining == nr2:
                print(f"    上 reading '{r2}' -> normalized '{nr2}' -> FULL MATCH!")
            elif remaining.startswith(nr2):
                print(f"    上 reading '{r2}' -> normalized '{nr2}' -> partial match")

print("\n=== Match simulation for 矢印(やじるし) ===")
full = _normalize_for_match("やじるし")
print(f"  full normalized: '{full}'")
for r in _candidate_readings_for_kanji("矢"):
    nr = _normalize_for_match(r)
    if full.startswith(nr):
        remaining = full[len(nr):]
        print(f"  矢 reading '{r}' -> normalized '{nr}' -> matches! remaining='{remaining}'")
        for r2 in _candidate_readings_for_kanji("印"):
            nr2 = _normalize_for_match(r2)
            if remaining == nr2:
                print(f"    印 reading '{r2}' -> normalized '{nr2}' -> FULL MATCH!")
            elif remaining.startswith(nr2):
                print(f"    印 reading '{r2}' -> normalized '{nr2}' -> partial match")

print("\n=== Match simulation for 雨戸(あまど) ===")
full = _normalize_for_match("あまど")
print(f"  full normalized: '{full}'")
for r in _candidate_readings_for_kanji("雨"):
    nr = _normalize_for_match(r)
    print(f"  雨 reading '{r}' -> normalized '{nr}' -> starts? {full.startswith(nr)}")