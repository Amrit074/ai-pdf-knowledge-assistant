import unittest

from app.utils.text import clean_text, split_text


class TextUtilsTest(unittest.TestCase):
    def test_clean_text_removes_nulls_and_extra_spacing(self):
        self.assertEqual(clean_text("  Hello\x00   PDF\n\n\nWorld  "), "Hello PDF\n\nWorld")

    def test_split_text_returns_overlapping_chunks(self):
        text = "Alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu."

        chunks = split_text(text, chunk_size=28, overlap=8)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunk for chunk in chunks))
        self.assertTrue(all(len(chunk) <= 28 for chunk in chunks))

    def test_split_text_handles_invalid_overlap(self):
        chunks = split_text("One two three four five six seven eight.", chunk_size=20, overlap=20)

        self.assertGreaterEqual(len(chunks), 1)


if __name__ == "__main__":
    unittest.main()
