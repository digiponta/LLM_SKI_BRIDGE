"""v0.14 structured SKI Dataset B diagnostic: strict, backward compatible."""
import copy
import unittest

from adapters.llm_cha_client_v05 import CHAClient
from adapters.llm_tmp_real import LLM_TMPAdapter
from adapters.cha_truth_boundary_v07 import assess_exchange
from ski.diagnostic_v014 import (
    PROFILE, attach_diagnostic, build_diagnostic, validate_diagnostic,
)
from ski.dataset_v05 import dataset_digest, validate_dataset, validate_replies


class Graph:
    def __init__(self, status="FOUND"):
        self.status = status

    def evidence_path(self, source, target, *, max_hops, max_visits):
        if self.status != "FOUND":
            return {"status": self.status, "path": None, "verified_fact": False}
        return {"status": "FOUND", "verified_fact": False,
                "path": [{"source": source, "target": target,
                          "kind": "SUPPORTED_BY", "state": "APPROVED",
                          "evidence_id": "EV-SYN-1",
                          "provenance": "UNTRUSTED_SOURCE_SENTENCE"}]}


def exchange(status="FOUND"):
    return CHAClient(LLM_TMPAdapter(Graph(status))).exchange(
        "この質問は学習せず診断だけ", source_sd="CLAIM", target_sd="EVIDENCE")


class DiagnosticV014Tests(unittest.TestCase):
    def test_profile_is_inside_ski_b(self):
        e = exchange()
        d = e["dataset_b"][0]["diagnostic"]
        self.assertEqual(d["profile"], PROFILE)
        self.assertEqual(d["diagnostic_status"], "FOUND")
        self.assertTrue(validate_diagnostic(e))
        self.assertEqual(assess_exchange(e)["evidence_status"], "FOUND")

    def test_dataset_and_reply_compat(self):
        e = exchange()
        self.assertTrue(validate_dataset(e["dataset_b"]))
        self.assertTrue(validate_replies(e["dataset_a"], e["dataset_b"]))
        self.assertEqual(len(dataset_digest(e["dataset_b"])), 64)

    def test_actual_ski_correlation_ids(self):
        e = exchange()
        d = e["dataset_b"][0]["diagnostic"]
        self.assertEqual(d["response_to_message_id"],
                         e["dataset_a"][0]["message_id"])
        self.assertEqual(d["evidence_request_id"],
                         e["evidence_request"]["message_id"])
        self.assertEqual(d["evidence_response_id"],
                         e["evidence_response"]["message_id"])

    def test_not_factual_or_learning_authority(self):
        d = exchange()["dataset_b"][0]["diagnostic"]
        self.assertEqual(d["truth_state"], "UNVERIFIED")
        self.assertEqual(d["approval_state"], "UNAUTHENTICATED")
        for key in ("verified_fact", "human_approved", "allow_model_context",
                    "allow_learning", "allow_answer_from_evidence",
                    "allow_truth_promotion"):
            self.assertIs(d[key], False)

    def test_no_raw_text_or_provenance_leak(self):
        d = exchange()["dataset_b"][0]["diagnostic"]
        self.assertNotIn("UNTRUSTED_SOURCE_SENTENCE", str(d))
        self.assertNotIn("この質問は学習せず診断だけ", str(d))
        self.assertNotIn("provenance", str(d))
        self.assertNotIn("path", list(d))  # only evidence_path_hops present

    def test_all_statuses(self):
        for status in ("FOUND", "NOT_FOUND", "UNKNOWN_NODE", "LIMIT_REACHED"):
            with self.subTest(status=status):
                e = exchange(status)
                d = e["dataset_b"][0]["diagnostic"]
                self.assertEqual(d["diagnostic_status"], status)
                self.assertTrue(validate_diagnostic(e))
                self.assertIsNone(d["evidence_path_hops"]) if status != "FOUND" else self.assertEqual(d["evidence_path_hops"], 1)

    def test_forged_truth_rejected(self):
        e = exchange()
        e["dataset_b"][0]["diagnostic"]["verified_fact"] = True
        with self.assertRaises(ValueError):
            assess_exchange(e)

    def test_forged_approval_rejected(self):
        e = exchange()
        e["dataset_b"][0]["diagnostic"]["approval_state"] = "APPROVED"
        with self.assertRaises(ValueError):
            validate_diagnostic(e)

    def test_forged_model_context_rejected(self):
        e = exchange()
        e["dataset_b"][0]["diagnostic"]["allow_model_context"] = True
        with self.assertRaises(ValueError):
            assess_exchange(e)

    def test_cross_response_id_rejected(self):
        e = exchange()
        e["dataset_b"][0]["diagnostic"]["evidence_response_id"] = "forged"
        with self.assertRaises(ValueError):
            validate_diagnostic(e)

    def test_status_mismatch_rejected(self):
        e = exchange()
        e["dataset_b"][0]["diagnostic"]["diagnostic_status"] = "NOT_FOUND"
        with self.assertRaises(ValueError):
            assess_exchange(e)

    def test_checksum_rewrite_is_not_authentication(self):
        e = exchange()
        e["dataset_b"][0]["diagnostic"]["approval_state"] = "APPROVED"
        # The profile recalculates the expected safety fields, so even
        # a forged hash cannot upgrade its trust boundary.
        from ski.diagnostic_v014 import _sha
        d = e["dataset_b"][0]["diagnostic"]
        d.pop("diagnostic_sha256")
        d["diagnostic_sha256"] = _sha(d)
        with self.assertRaises(ValueError):
            validate_diagnostic(e)

    def test_integer_zero_cannot_impersonate_false(self):
        e = exchange()
        e["dataset_b"][0]["diagnostic"]["allow_learning"] = 0
        with self.assertRaisesRegex(ValueError, "UNSAFE_DIAGNOSTIC_FLAG"):
            validate_diagnostic(e)

    def test_boolean_true_cannot_impersonate_one_hop(self):
        e = exchange()
        e["dataset_b"][0]["diagnostic"]["evidence_path_hops"] = True
        with self.assertRaisesRegex(ValueError, "INVALID_DIAGNOSTIC_HOPS"):
            validate_diagnostic(e)

    def test_legacy_dataset_b_without_extension_allowed(self):
        e = exchange()
        del e["dataset_b"][0]["diagnostic"]
        self.assertEqual(assess_exchange(e)["action"], "DIAGNOSTIC_ONLY")
        with self.assertRaisesRegex(ValueError, "MISSING_SKI_DIAGNOSTIC"):
            validate_diagnostic(e)

    def test_attach_preserves_original(self):
        e = exchange()
        del e["dataset_b"][0]["diagnostic"]
        original = copy.deepcopy(e)
        extended = attach_diagnostic(e)
        self.assertEqual(e, original)
        self.assertTrue(validate_diagnostic(extended))

    def test_tampered_ack_still_rejected(self):
        e = exchange()
        e["ack"]["dataset_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            assess_exchange(e)


if __name__ == "__main__":
    unittest.main()
