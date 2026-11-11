import json
import tempfile
import unittest
from pathlib import Path

from adapters.llm_cha_console_v06 import parse_input, run_command, build_graph


class FakeGraph:
    def __init__(self, nodes):
        self.nodes = set(nodes)
        self.edges = []
    def add_relation(self, source, kind, target, *, state, evidence_id=None, provenance=None):
        if source not in self.nodes or target not in self.nodes:
            raise ValueError("UNKNOWN_NODE")
        self.edges.append((source, kind, target, state))


class FakeClient:
    def exchange(self, question, *, source_sd, target_sd):
        req_id = "M-1"
        return {
            "dataset_a": [{"message_id": req_id}],
            "dataset_b": [{"derivation": {"response_to_message_id": req_id}}],
            "evidence_response": {
                "status": "FOUND",
                "path": [{"source": source_sd, "target": target_sd,
                          "kind": "SUPPORTED_BY", "state": "APPROVED"}],
            },
        }


class CHAConsoleV06Tests(unittest.TestCase):
    def test_ski_command(self):
        command = parse_input("/ski SD-A SD-B | これは何ですか")
        self.assertEqual(command["kind"], "SKI")
        self.assertEqual(command["question"], "これは何ですか")

    def test_chat_pass_through(self):
        sent = []
        result = run_command("スファレライトの成分は？", FakeClient(), sent.append)
        self.assertEqual(result["kind"], "FORWARDED_TO_CHAT")
        self.assertEqual(sent, ["スファレライトの成分は？"])

    def test_chat_slash_pass_through(self):
        self.assertEqual(parse_input("/status")["kind"], "CHAT")

    def test_ski_is_not_forwarded(self):
        sent = []
        outcome = run_command("/ski A B | 根拠確認", FakeClient(), sent.append)
        self.assertEqual(sent, [])
        self.assertEqual(outcome["kind"], "SKI_DIAGNOSTIC")
        self.assertFalse(outcome["verified_fact"])
        self.assertEqual(outcome["request_id"], outcome["response_to_message_id"])

    def test_invalid_lines(self):
        for line in ("", "/ski", "/ski A", "/ski A B |   ",
                     "one\ntwo", "bad\x00text", "x" * 4001):
            with self.subTest(line=line[:20]):
                with self.assertRaises(ValueError):
                    parse_input(line)

    def test_exit(self):
        self.assertEqual(run_command("/exit", FakeClient(), lambda _: None),
                         {"kind": "EXIT"})

    def test_graph_file(self):
        fixture = {"nodes": ["A", "B"], "relations": [
            {"source": "A", "kind": "SUPPORTED_BY", "target": "B",
             "state": "APPROVED", "evidence_id": "EV-1"}]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "graph.json"
            path.write_text(json.dumps(fixture), encoding="utf-8")
            graph = build_graph(FakeGraph, path)
            self.assertEqual(graph.edges, [("A", "SUPPORTED_BY", "B", "APPROVED")])

    def test_invalid_graph(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "graph.json"
            for doc in (
                    {"nodes": ["A", "A"], "relations": []},
                    {"nodes": ["A"], "relations": [{"source": "A"}]},
                    {"nodes": [], "relations": []},
                    {"nodes": ["A"], "relations": [], "unexpected": True}):
                with self.subTest(doc=doc):
                    path.write_text(json.dumps(doc), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        build_graph(FakeGraph, path)


if __name__ == "__main__":
    unittest.main()
