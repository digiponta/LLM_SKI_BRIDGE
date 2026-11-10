import copy
import unittest

from adapters.llm_tmp_real import LLM_TMPAdapter
from ski.message import request, validate_roundtrip


class GraphFixture:
    """Contract-equivalent substitute, not the live LLM_TMP implementation."""
    def __init__(self, status="FOUND", path=None, verified=False):
        self.status = status
        self.path = path
        self.verified = verified
        self.calls = []

    def evidence_path(self, source, target, *, max_hops, max_visits):
        self.calls.append((source, target, max_hops, max_visits))
        return {"status": self.status, "path": self.path, "verified_fact": self.verified}


EDGE = {"source": "CLAIM", "target": "EVIDENCE", "kind": "SUPPORTED_BY",
        "state": "APPROVED", "evidence_id": "EV-1", "provenance": "fixture"}


class RealAdapterContractTests(unittest.TestCase):
    def setUp(self):
        self.req = request("CLAIM", "EVIDENCE", max_hops=2, max_visits=10)

    def test_found_and_correlation(self):
        graph = GraphFixture(path=[EDGE])
        resp = LLM_TMPAdapter(graph).handle(self.req)
        self.assertTrue(validate_roundtrip(self.req, resp))
        self.assertEqual(resp["status"], "FOUND")
        self.assertEqual(graph.calls, [("CLAIM", "EVIDENCE", 2, 10)])
        self.assertFalse(resp["verified_fact"])

    def test_negative_states(self):
        for status in ("NOT_FOUND", "LIMIT_REACHED", "UNKNOWN_NODE"):
            with self.subTest(status=status):
                resp = LLM_TMPAdapter(GraphFixture(status=status)).handle(self.req)
                self.assertEqual(resp["status"], status)
                self.assertIsNone(resp["path"])

    def test_pending_and_rejected_blocked(self):
        for state in ("PENDING", "REJECTED"):
            with self.subTest(state=state):
                graph = GraphFixture(path=[{**EDGE, "state": state}])
                with self.assertRaises(ValueError):
                    LLM_TMPAdapter(graph).handle(self.req)

    def test_malformed_graph_output_blocked(self):
        for result in (
            {"status": "FOUND", "path": [EDGE], "verified_fact": True},
            {"status": "COMPLETE", "path": None, "verified_fact": False},
            {"status": "FOUND", "path": [], "verified_fact": False},
        ):
            with self.subTest(result=result):
                class BadGraph:
                    def evidence_path(self, *_args, **_kwargs):
                        return result
                with self.assertRaises(ValueError):
                    LLM_TMPAdapter(BadGraph()).handle(self.req)

    def test_bad_request_not_dispatched(self):
        graph = GraphFixture(path=[EDGE])
        bad = copy.deepcopy(self.req)
        bad["max_visits"] = 0
        with self.assertRaises(ValueError):
            LLM_TMPAdapter(graph).handle(bad)
        self.assertEqual(graph.calls, [])

    def test_requires_graph_api(self):
        with self.assertRaises(TypeError):
            LLM_TMPAdapter(object())


if __name__ == "__main__":
    unittest.main()
