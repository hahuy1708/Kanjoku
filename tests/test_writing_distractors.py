import unittest

from src.reading.kanji_reading import KanjiSegment, decompose_word


class DecomposeWordTests(unittest.TestCase):
    def test_decompose_word_supports_long_kunyomi_for_multi_kanji_words(self) -> None:
        segments = decompose_word("目上", "めうえ")
        self.assertTrue(segments)
        readings = [seg.reading for seg in segments if isinstance(seg, KanjiSegment)]
        self.assertEqual(readings, ["め", "うえ"])

    def test_decompose_word_supports_compound_readings_like_amado(self) -> None:
        segments = decompose_word("雨戸", "あまど")
        self.assertTrue(segments)
        readings = [seg.reading for seg in segments if isinstance(seg, KanjiSegment)]
        self.assertEqual(readings, ["あめ", "と"])

    def test_decompose_word_supports_compound_readings_like_yajirushi(self) -> None:
        segments = decompose_word("矢印", "やじるし")
        self.assertTrue(segments)
        readings = [seg.reading for seg in segments if isinstance(seg, KanjiSegment)]
        self.assertEqual(readings, ["や", "しるし"])


if __name__ == "__main__":
    unittest.main()
