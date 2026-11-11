import copy
import json
import tempfile
import unittest
from pathlib import Path

from adapters.llm_tmp_registry_v08 import (
    PROFILE, build_relation_graph, import_snapshot, load_snapshot, validate_snapshot
)


def fixture():
    return {
        "format": PROFILE, "snapshot_id": "tmp-test-001", "source_system": "LLM_TMP",
        "nodes": ["CLAIM", "EVIDENCE", "PENDING", "REJECTED"],
        "relations": [
            {"source": "CLAIM", "kind": "SUPPORTED_BY", "target": "EVIDENCE",
             "state": "APPROVED", "evidence_id": "EV-1", "provenance": "synthetic-test"},
            {"source": "CLAIM", "kind": "SUPPORTED_BY", "target": "PENDING",
             "state": "PENDING", "evidence_id": None, "provenance": None},
            {"source": "CLAIM", "kind": "SUPPORTED_BY", "target": "REJECTED",
             "state": "REJECTED", "evidence_id": None, "provenance": None}
        ]
    }


class FakeGraph:
    def __init__(self, nodes):
        self.nodes = set(nodes)
        self.edges = []

    def add_relation(self, source, kind, target, *, state, evidence_id=None, provenance=None):
        self.edges.append((source, kind, target, state, evidence_id, provenance))


class RegistryV08Tests(unittest.TestCase):
    def test_valid_snapshot(self):
        self.assertTrue(validate_snapshot(fixture()))
        graph = build_relation_graph(FakeGraph, fixture())
        self.assertEqual(len(graph.nodes), 4)
        self.assertEqual(len(graph.edges), 3)

    def test_duplicate_nodes_rejected(self):
        payload = fixture()
        payload["nodes"].append("CLAIM")
        with self.assertRaisesRegex(ValueError, "NODES"):
            validate_snapshot(payload)

    def test_unknown_endpoints_rejected(self):
        payload = fixture()
        payload["relations"][0]["target"] = "UNKNOWN"
        with self.assertRaisesRegex(ValueError, "RELATION"):
            validate_snapshot(payload)

    def test_approved_without_evidence_rejected(self):
        for field in ("evidence_id", "provenance"):
            payload = fixture()
            payload["relations"][0][field] = None
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "UNTRACED"):
                validate_snapshot(payload)

    def test_unapproved_never_promoted(self):
        graph = build_relation_graph(FakeGraph, fixture())
        states = [edge[3] for edge in graph.edges]
        self.assertEqual(states, ["APPROVED", "PENDING", "REJECTED"])

    def test_extra_field_rejected(self):
        payload = fixture()
        payload["user_approved"] = True
        with self.assertRaisesRegex(ValueError, "SCHEMA"):
            validate_snapshot(payload)

    def test_duplicate_relation_rejected(self):
        payload = fixture()
        payload["relations"].append(copy.deepcopy(payload["relations"][0]))
        with self.assertRaisesRegex(ValueError, "DUPLICATE"):
            validate_snapshot(payload)

    def test_file_read_does_not_modify(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "snapshot.json"
            raw = json.dumps(fixture(), ensure_ascii=False).encode("utf-8")
            path.write_bytes(raw)
            graph, metadata = import_snapshot(FakeGraph, path)
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(metadata["nodes"], 4)
            self.assertFalse(metadata["approval_authenticated"])
            self.assertFalse(metadata["persistent_registry_modified"])
            self.assertEqual(len(metadata["snapshot_sha256"]), 64)
            self.assertEqual(len(graph.edges), 3)

    def test_duplicate_json_key_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "snapshot.json"
            path.write_text('{"format":"x","format":"y"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "DUPLICATE_JSON_KEY"):
                load_snapshot(path)

    def test_file_size_limit(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "snapshot.json"
            path.write_text("0123456789", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "TOO_LARGE"):
                load_snapshot(path, max_bytes=5)

    def test_wrong_system_rejected(self):
        payload = fixture()
        payload["source_system"] = "UNVERIFIED_EXTERNAL"
        with self.assertRaisesRegex(ValueError, "IDENTITY"):
            validate_snapshot(payload)

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(FileNotFoundError):
                load_snapshot(Path(root) / "missing.json")


if __name__ == "__main__":
    unittest.main()
