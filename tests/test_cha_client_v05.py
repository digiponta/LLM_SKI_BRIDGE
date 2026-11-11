import unittest

from adapters.llm_cha_client_v05 import CHAClient
from adapters.llm_tmp_real import LLM_TMPAdapter
from ski.dataset_v05 import verify_ack, validate_replies


class FixtureGraph:
    def __init__(self, state="APPROVED"):
        self.state = state
        self.calls = 0

    def evidence_path(self, source, target, *, max_hops, max_visits):
        self.calls += 1
        if target == "MISSING":
            return {"status": "UNKNOWN_NODE", "path": None, "verified_fact": False}
        if max_visits == 1:
            return {"status": "LIMIT_REACHED", "path": None, "verified_fact": False}
        if self.state != "APPROVED" or max_hops < 1:
            return {"status": "NOT_FOUND", "path": None, "verified_fact": False}
        return {"status": "FOUND", "verified_fact": False, "path": [
            {"source": source, "target": target, "kind": "SUPPORTED_BY",
             "state": "APPROVED", "evidence_id": "fixture"}]}


class CHAClientTests(unittest.TestCase):
    def client(self, state="APPROVED"):
        return CHAClient(LLM_TMPAdapter(FixtureGraph(state)))

    def test_approved_status_not_truth(self):
        result = self.client().exchange("成分は？", source_sd="A", target_sd="B")
        self.assertEqual(result["evidence_response"]["status"], "FOUND")
        self.assertFalse(result["verification"]["verified_fact"])
        self.assertFalse(result["verification"]["llm_cha_inference_invoked"])
        self.assertTrue(verify_ack(result["dataset_a"], result["ack"], "LLM_TMP"))
        self.assertTrue(validate_replies(result["dataset_a"], result["dataset_b"]))

    def test_pending_never_found(self):
        result = self.client("PENDING").exchange("成分は？", source_sd="A", target_sd="B")
        self.assertEqual(result["evidence_response"]["status"], "NOT_FOUND")

    def test_unknown(self):
        result = self.client().exchange("質問", source_sd="A", target_sd="MISSING")
        self.assertEqual(result["evidence_response"]["status"], "UNKNOWN_NODE")

    def test_visit_budget(self):
        result = self.client().exchange("質問", source_sd="A", target_sd="B", max_visits=1)
        self.assertEqual(result["evidence_response"]["status"], "LIMIT_REACHED")

    def test_invalid_limit_no_dispatch(self):
        with self.assertRaises(ValueError):
            self.client().exchange("質問", source_sd="A", target_sd="B", max_visits=0)

    def test_no_model_answer_promotion(self):
        result = self.client().exchange("事実を教えて", source_sd="A", target_sd="B")
        self.assertFalse(result["dataset_b"][0]["assessments"]["human_approved"])
        self.assertFalse(result["dataset_b"][0]["assessments"]["verified_fact"])

    def test_invalid_adapter(self):
        with self.assertRaises(TypeError):
            CHAClient(object())


if __name__ == "__main__":
    unittest.main()
