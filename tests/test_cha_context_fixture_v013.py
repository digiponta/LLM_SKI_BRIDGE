"""Regress native display name mismatch in multi-turn test scenarios."""
import unittest
from verify_cha_context_v013 import fixture_labels


class NativeContextFixtureTests(unittest.TestCase):
    def test_distinct_real_fixture_labels(self):
        # Native synthetic fixture v0.9 uses OTHER="別話題",
        # not the older mocked test label "その他".
        source, other = fixture_labels({
            "display_names": {"CLAIM": "主張", "OTHER": "別話題"}
        })
        self.assertEqual(source, "主張")
        self.assertEqual(other, "別話題")
        utterance = f"{source}と{other}について"
        self.assertIn("主張", utterance)
        self.assertIn("別話題", utterance)

    def test_missing_display_label_rejected(self):
        with self.assertRaisesRegex(ValueError, "DISPLAY_NAMES_MISSING"):
            fixture_labels({"display_names": {"CLAIM": "主張"}})

    def test_duplicate_display_label_rejected(self):
        with self.assertRaisesRegex(ValueError, "DISPLAY_NAMES_NOT_UNIQUE"):
            fixture_labels({"display_names": {"CLAIM": "主張", "OTHER": "主張"}})


if __name__ == "__main__":
    unittest.main()
