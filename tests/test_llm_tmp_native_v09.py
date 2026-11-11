import copy
import json
import tempfile
import unittest
from pathlib import Path

from adapters.llm_tmp_native_v09 import convert_native, read_native

def registry(state="APPROVED"):
    return {
        "namespace": "local", "snapshot_id": "sample-01",
        "display_names": {"CLAIM": "主張", "EVIDENCE": "根拠"},
        "nodes": [
            {"sd_id": "CLAIM", "node_type": "TOPIC"},
            {"sd_id": "EVIDENCE", "node_type": "CONCEPT"},
            {"sd_id": "PENDING", "node_type": "ENTITY"},
            {"sd_id": "support-pred", "node_type": "PREDICATE",
             "continuity_allowed": True},
            {"sd_id": "about-pred", "node_type": "PREDICATE",
             "continuity_allowed": True},
            {"sd_id": "r1", "node_type": "RELATION",
             "predicate_ref": "support-pred", "source_ref": "CLAIM",
             "target_ref": "EVIDENCE", "validation_state": state,
             "evidence_id": "EV-1"},
            {"sd_id": "r2", "node_type": "RELATION",
             "predicate_ref": "about-pred", "source_ref": "CLAIM",
             "target_ref": "PENDING", "validation_state": "APPROVED",
             "evidence_id": "EV-2"},
        ],
    }

class MockRegistry:
    """Subset contract used by unit tests; real API tested separately."""
    def __init__(self, snapshot):
        if not isinstance(snapshot, dict) or not isinstance(snapshot.get("nodes"), list):
            raise ValueError("INVALID_NATIVE")
        self.namespace = snapshot["namespace"]
        ids = {n["sd_id"]: n for n in snapshot["nodes"]}
        if len(ids) != len(snapshot["nodes"]):
            raise ValueError("DUPLICATE_SD_ID")
        for n in snapshot["nodes"]:
            if n["node_type"] == "RELATION":
                for k in ("predicate_ref", "source_ref", "target_ref"):
                    if n[k] not in ids:
                        raise ValueError("DANGLING_RELATION_REF")
                if ids[n["predicate_ref"]]["node_type"] != "PREDICATE":
                    raise ValueError("INVALID_PREDICATE")

class NativeV09Tests(unittest.TestCase):
    def test_default_denies_all_edges(self):
        out, report = convert_native(registry(), MockRegistry)
        self.assertEqual(len(out["relations"]), 0)
        self.assertEqual(report["skipped"]["not_allowlisted"], 2)

    def test_explicit_mapping_only(self):
        out, report = convert_native(
            registry(), MockRegistry, supported_by_predicates=("support-pred",))
        self.assertEqual(len(out["relations"]), 1)
        self.assertEqual(out["relations"][0]["kind"], "SUPPORTED_BY")
        self.assertEqual(out["relations"][0]["evidence_id"], "EV-1")
        self.assertFalse(report["approval_authenticated"])

    def test_pending_not_exported(self):
        out, report = convert_native(
            registry("PENDING"), MockRegistry, supported_by_predicates=("support-pred",))
        self.assertEqual(out["relations"], [])
        self.assertEqual(report["skipped"]["not_approved"], 1)

    def test_rejected_not_exported(self):
        out, _ = convert_native(
            registry("REJECTED"), MockRegistry, supported_by_predicates=("support-pred",))
        self.assertEqual(out["relations"], [])

    def test_not_mutated(self):
        original = registry()
        old = copy.deepcopy(original)
        convert_native(original, MockRegistry, supported_by_predicates=("support-pred",))
        self.assertEqual(original, old)

    def test_bad_allowlist(self):
        with self.assertRaisesRegex(ValueError, "NOT_FOUND"):
            convert_native(registry(), MockRegistry, supported_by_predicates=("missing",))

    def test_relation_not_predicate(self):
        with self.assertRaisesRegex(ValueError, "NOT_FOUND"):
            convert_native(registry(), MockRegistry, supported_by_predicates=("CLAIM",))

    def test_duplicate_allowlist(self):
        with self.assertRaisesRegex(ValueError, "INVALID_PREDICATE_ALLOWLIST"):
            convert_native(registry(), MockRegistry,
                           supported_by_predicates=("support-pred", "support-pred"))

    def test_missing_snapshot_id(self):
        data = registry()
        del data["snapshot_id"]
        with self.assertRaisesRegex(ValueError, "ID_REQUIRED"):
            convert_native(data, MockRegistry)

    def test_dangling_relation(self):
        data = registry()
        data["nodes"][-1]["target_ref"] = "MISSING"
        with self.assertRaisesRegex(ValueError, "DANGLING"):
            convert_native(data, MockRegistry, supported_by_predicates=("about-pred",))

    def test_native_file_digest(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "registry.json"
            raw = json.dumps(registry(), ensure_ascii=False).encode("utf-8")
            path.write_bytes(raw)
            data, digest = read_native(path)
            self.assertEqual(data, registry())
            self.assertEqual(len(digest), 64)
            self.assertEqual(path.read_bytes(), raw)

    def test_duplicate_key_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "registry.json"
            path.write_text('{"nodes":[],"nodes":[]}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "DUPLICATE"):
                read_native(path)

if __name__ == "__main__":
    unittest.main()
