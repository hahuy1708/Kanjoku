import random

def generate_reading_distractors(furigana: str):
    """Tạo đáp án nhiễu dựa trên các lỗi sai phát âm thực tế của người học."""
    if not furigana: return []
    
    traps = set()
    f = furigana
    
    # 1. Long vowels: う, い
    # If has long vowels -> try removing them or changing them
    if "う" in f: traps.add(f.replace("う", "", 1))
    if "い" in f: traps.add(f.replace("い", "", 1))
    if "おう" in f: traps.add(f.replace("おう", "おお"))
    if "ゅう" in f: traps.add(f.replace("ゅう", "ゅ"))
    
    # If word doesn't end with う or い, adding them
    if not f.endswith("う") and not f.endswith("い"):
        traps.add(f + "う")
        traps.add(f + "い")

    # 2. Rendaku - Dakuon/Handakuon
    # か/が, た/だ, は/ば/ぱ
    dakuon_map = {
        "か": "が", "き": "ぎ", "く": "ぐ", "け": "げ", "こ": "ご",
        "さ": "ざ", "し": "じ", "す": "ず", "せ": "ぜ", "そ": "ぞ",
        "た": "だ", "ち": "ぢ", "つ": "づ", "て": "で", "と": "ど",
        "は": "ば", "ひ": "び", "ふ": "ぶ", "へ": "べ", "ほ": "ぼ",
        "は": "ぱ", "ひ": "ぴ", "ふ": "ぷ", "へ": "ぺ", "ほ": "ぽ"
    }
    seion_map = {v: k for k, v in dakuon_map.items()}
    
    for char in set(f):
        if char in dakuon_map: traps.add(f.replace(char, dakuon_map[char], 1))
        if char in seion_map: traps.add(f.replace(char, seion_map[char], 1))

    # 3. Sokuon: っ
    if "つ" in f: traps.add(f.replace("つ", "っ", 1))
    if "く" in f: traps.add(f.replace("く", "っ", 1))
    if "き" in f: traps.add(f.replace("き", "っ", 1))
    
    # If word has っ, try replacing it with つ or く
    if "っ" in f:
        traps.add(f.replace("っ", "つ", 1))
        traps.add(f.replace("っ", "く", 1))

    if f in traps:
        traps.remove(f)
        
    final_traps = list(traps)
    random.shuffle(final_traps)
    
    vowels = ["あ", "い", "う", "え", "お"]
    while len(final_traps) < 3:
        fallback = f[:-1] + random.choice(vowels)
        if fallback != f and fallback not in final_traps:
            final_traps.append(fallback)

    return final_traps[:3]