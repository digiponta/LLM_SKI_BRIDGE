import copy
import unittest

from ski.dataset_v05 import (
    new_message, valid_message, validate_dataset, dataset_digest,
    make_ack, verify_ack, validate_replies, validate_metadata,
)


class SKIV05Tests(unittest.TestCase):
    def setUp(self):
        self.a = new_message("LLM_CHA", "LLM_TMP", "CHA-01",
                             "スファレライトの成分は？", message_id="req-01")
        self.b = new_message(
            "LLM_TMP", "LLM_CHA", "TMP-01", "未検証です。",
            message_id="reply-01", parent_sd_id="CHA-01",
            derivation={"response_to_message_id": "req-01",
                        "source_sd_id": "CHA-01"})

    def test_message_and_digest(self):
        self.assertTrue(valid_message(self.a))
        self.assertEqual(len(dataset_digest([self.a])), 64)

    def test_tamper_rejected(self):
        altered = {**self.a, "text": "変更した"}
        self.assertFalse(valid_message(altered))
        with self.assertRaises(ValueError):
            validate_dataset([altered])

    def test_duplicate_rejected(self):
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            validate_dataset([self.a, copy.deepcopy(self.a)])

    def test_wrong_direction(self):
        with self.assertRaisesRegex(ValueError, "DIRECTION"):
            validate_dataset([self.a], target_llm="LLM_CHA")

    def test_ack_separate_from_reply(self):
        ack = make_ack([self.a], "LLM_TMP")
        self.assertTrue(verify_ack([self.a], ack, "LLM_TMP"))
        self.assertNotIn("text", ack)
        self.assertNotIn("human_approved", ack)
        self.assertFalse(verify_ack([self.a], {**ack, "dataset_sha256": "0" * 64}, "LLM_TMP"))

    def test_replies_correlation(self):
        self.assertTrue(validate_replies([self.a], [self.b]))
        with self.assertRaisesRegex(ValueError, "CORRELATION"):
            validate_replies([self.a], [{**self.b, "derivation": {
                "response_to_message_id": "not-found", "source_sd_id": "CHA-01"}}])

    def test_lineage_rejected(self):
        with self.assertRaisesRegex(ValueError, "LINEAGE"):
            validate_replies([self.a], [{**self.b, "parent_sd_id": "WRONG"}])

    def test_multiple_response_profile(self):
        alt = new_message("LLM_TMP", "LLM_CHA", "TMP-02",
                          "追加資料が必要です。", message_id="reply-02",
                          parent_sd_id="CHA-01",
                          derivation={"response_to_message_id": "req-01",
                                      "source_sd_id": "CHA-01"})
        self.assertTrue(validate_replies([self.a], [self.b, alt]))
        with self.assertRaisesRegex(ValueError, "MULTIPLE"):
            validate_replies([self.a], [self.b, alt], allow_multiple=False)

    def test_vectors_forbidden(self):
        with self.assertRaisesRegex(ValueError, "INVALID_SKI"):
            new_message("A", "B", "id", "hello", embedding=[0.1, 0.2])

    def test_dialogue_metadata(self):
        metadata = {
            "dataset_id": "dlg-1", "dataset_type": "DIALOGUE",
            "source_llm": "LLM_CHA", "target_llm": "LLM_TMP",
            "turns": [
                {"utterance_id": "u1", "speaker": "USER",
                 "language": "ja", "text": "こんにちは"},
                {"utterance_id": "u2", "speaker": "ASSISTANT",
                 "language": "ja", "text": "こんにちは", "in_reply_to": "u1"},
            ],
        }
        self.assertTrue(validate_metadata(metadata, [self.a]))
        bad = copy.deepcopy(metadata)
        bad["turns"][1]["in_reply_to"] = "unknown"
        with self.assertRaisesRegex(ValueError, "TURN_REFERENCE"):
            validate_metadata(bad, [self.a])

    def test_learning_pending_only(self):
        metadata = {
            "dataset_id": "learn-1", "dataset_type": "LEARNING",
            "source_llm": "LLM_CHA", "target_llm": "LLM_TMP",
            "examples": [{
                "example_id": "qa-1",
                "question": {"language": "ja", "text": "成分は？"},
                "answer": {"language": "ja", "text": "不明"},
                "approval": "PENDING", "assessment": "UNVERIFIED",
            }],
        }
        self.assertTrue(validate_metadata(metadata, [self.a]))
        metadata["examples"][0]["approval"] = "APPROVED"
        with self.assertRaisesRegex(ValueError, "UNSAFE"):
            validate_metadata(metadata, [self.a])

    def test_learning_requires_qa(self):
        metadata = {
            "dataset_id": "learn-2", "dataset_type": "LEARNING",
            "source_llm": "LLM_CHA", "target_llm": "LLM_TMP",
            "examples": [{"example_id": "qa-1",
                          "question": {"language": "ja", "text": "?"}}],
        }
        with self.assertRaisesRegex(ValueError, "INCOMPLETE_QA"):
            validate_metadata(metadata, [self.a])

if __name__ == "__main__":
    unittest.main()
