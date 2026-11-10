import unittest
from ski.message import request, response, validate_request, validate_roundtrip

class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.req = request("A", "C", max_hops=3)
        self.path = [
            {"source": "A", "target": "B", "kind": "SUPPORTED_BY", "state": "APPROVED"},
            {"source": "B", "target": "C", "kind": "SUPPORTED_BY", "state": "APPROVED"},
        ]
        self.resp = response(self.req, {"status": "FOUND", "path": self.path})

    def test_valid_chain(self):
        self.assertTrue(validate_roundtrip(self.req, self.resp))

    def test_invalid_request(self):
        for change in ({"message_id": " "}, {"max_hops": True},
                       {"max_visits": 0}, {"sender": "LLM_TMP"}):
            with self.subTest(change=change):
                self.assertFalse(validate_request({**self.req, **change}))

    def test_invalid_path(self):
        for path in ([], self.path[:1], self.path + self.path[:1],
                     [{**self.path[0], "state": "PENDING"}, self.path[1]],
                     [{**self.path[0], "target": "C"}, self.path[1]],
                     ["invalid"],
                     [{**self.path[0], "target": "A"}, self.path[1]]):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    response(self.req, {"status": "FOUND", "path": path})

    def test_response_tampering(self):
        changes = ({"ski_version": "other"}, {"message_id": " "},
                   {"message_id": self.req["message_id"]},
                   {"max_visits": 999}, {"max_hops": 0},
                   {"human_approved": True}, {"verified_fact": True},
                   {"sender": "LLM_CHA"}, {"status": "NOT_FOUND"},
                   {"correlation_id": "other"})
        for change in changes:
            with self.subTest(change=change):
                self.assertFalse(validate_roundtrip(self.req, {**self.resp, **change}))

    def test_same_node_zero_hop(self):
        req = request("A", "A", max_hops=0)
        resp = response(req, {"status": "FOUND", "path": []})
        self.assertTrue(validate_roundtrip(req, resp))

    def test_different_node_zero_hop(self):
        req = request("A", "B", max_hops=0)
        with self.assertRaises(ValueError):
            response(req, {"status": "FOUND", "path": []})

    def test_nonfound_must_not_have_path(self):
        with self.assertRaises(ValueError):
            response(self.req, {"status": "NOT_FOUND", "path": []})

if __name__ == "__main__":
    unittest.main()
