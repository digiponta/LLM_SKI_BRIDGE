import unittest
from adapters.llm_cha_mock import roundtrip
from adapters.llm_tmp_mock import MockTMP
from ski.message import request, response, validate_roundtrip


class BridgeV01Tests(unittest.TestCase):
    def test_found(self):
        self.assertEqual(roundtrip()["response"]["status"], "FOUND")

    def test_approved_path(self):
        self.assertEqual(roundtrip()["response"]["path"][0]["state"], "APPROVED")

    def test_pending_not_used(self):
        self.assertEqual(roundtrip(target_sd="SD-PENDING")["response"]["status"], "NOT_FOUND")

    def test_unknown(self):
        self.assertEqual(roundtrip(target_sd="MISSING")["response"]["status"], "UNKNOWN_NODE")

    def test_limit(self):
        self.assertEqual(roundtrip(max_visits=1)["response"]["status"], "LIMIT_REACHED")

    def test_depth_limit(self):
        self.assertEqual(roundtrip(max_hops=0)["response"]["status"], "DEPTH_LIMIT_REACHED")

    def test_correlation(self):
        result = roundtrip()
        self.assertEqual(result["request"]["message_id"], result["response"]["correlation_id"])

    def test_mismatched_correlation_rejected(self):
        result = roundtrip()
        result["response"]["correlation_id"] = "forged"
        self.assertFalse(validate_roundtrip(result["request"], result["response"]))

    def test_unapproved_response_rejected(self):
        req = request("A", "B")
        with self.assertRaises(ValueError):
            response(req, {"status": "FOUND", "path": [{"kind": "SUPPORTED_BY", "state": "PENDING"}]})

    def test_invalid_limit_rejected(self):
        with self.assertRaises(ValueError):
            request("A", "B", max_visits=0)


if __name__ == "__main__":
    unittest.main()
