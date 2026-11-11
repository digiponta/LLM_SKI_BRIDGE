import copy
import json
import tempfile
import unittest
from pathlib import Path

from adapters.native_registry_audit_v010 import audit_native


def snapshot():
    return {
        "namespace": "demo", "snapshot_id": "unit-v010",
        "display_names": {"CLAIM": "主張"},
        "nodes": [
            {"sd_id": "CLAIM", "node_type": "TOPIC"},
            {"sd_id": "EV", "node_type": "CONCEPT"},
            {"sd_id": "X", "node_type": "ENTITY"},
            {"sd_id": "supp", "node_type": "PREDICATE", "continuity_allowed": False},
            {"sd_id": "topic", "node_type": "PREDICATE", "continuity_allowed": True},
            {"sd_id": "R1", "node_type": "RELATION", "predicate_ref": "supp",
             "source_ref": "CLAIM", "target_ref": "EV",
             "validation_state": "APPROVED", "evidence_id": "E-1"},
            {"sd_id": "R2", "node_type": "RELATION", "predicate_ref": "supp",
             "source_ref": "CLAIM", "target_ref": "X",
             "validation_state": "PENDING", "evidence_id": "E-2"},
            {"sd_id": "R3", "node_type": "RELATION", "predicate_ref": "topic",
             "source_ref": "CLAIM", "target_ref": "X",
             "validation_state": "REJECTED", "evidence_id": "E-1"},
        ]
    }


class ContractRegistry:
    def __init__(self, data):
        if set(data) - {"namespace", "snapshot_id", "nodes"}:
            raise ValueError("INVALID_SCHEMA_FIELDS")
        self.namespace = data["namespace"]
        nodes = data["nodes"]
        ids = {x["sd_id"]: x for x in nodes}
        if len(ids) != len(nodes):
            raise ValueError("DUPLICATE_SD_ID")
        for x in nodes:
            if x["node_type"] == "RELATION":
                for k in ("source_ref", "target_ref", "predicate_ref"):
                    if x[k] not in ids:
                        raise ValueError("DANGLING_RELATION_REF")
                if x["validation_state"] not in ("APPROVED", "PENDING", "REJECTED"):
                    raise ValueError("INVALID_RELATION_STATE")


class AuditTests(unittest.TestCase):
    def test_default_deny(self):
        report = audit_native(snapshot(), ContractRegistry)
        self.assertEqual(report["counts"]["eligible_for_explicit_mapping"], 0)
        self.assertTrue(report["mapping"]["default_deny"])
        self.assertFalse(report["trust"]["verified_fact"])

    def test_explicit_predicate(self):
        report = audit_native(snapshot(), ContractRegistry,
                              supported_by_predicates=("supp",))
        self.assertEqual(report["counts"]["eligible_for_explicit_mapping"], 1)
        self.assertEqual(report["counts"]["excluded"]["not_approved"], 1)
        self.assertEqual(report["counts"]["excluded"]["predicate_not_allowlisted"], 1)

    def test_type_counts(self):
        report = audit_native(snapshot(), ContractRegistry)
        self.assertEqual(report["counts"]["nodes_total"], 8)
        self.assertEqual(report["counts"]["relations_total"], 3)
        self.assertEqual(report["counts"]["node_types"]["RELATION"], 3)

    def test_state_counts(self):
        report = audit_native(snapshot(), ContractRegistry)
        self.assertEqual(report["counts"]["relation_states"],
                         {"APPROVED": 1, "PENDING": 1, "REJECTED": 1})

    def test_shared_evidence_is_not_authenticated(self):
        report = audit_native(snapshot(), ContractRegistry,
                              supported_by_predicates=("supp",))
        self.assertEqual(report["counts"]["reused_evidence_ids"], 1)
        self.assertFalse(report["trust"]["approval_authenticated"])
        self.assertFalse(report["trust"]["allow_model_context"])

    def test_no_input_mutation(self):
        raw = snapshot()
        original = copy.deepcopy(raw)
        audit_native(raw, ContractRegistry, supported_by_predicates=("supp",))
        self.assertEqual(raw, original)

    def test_unlisted_predicate_rejected(self):
        with self.assertRaisesRegex(ValueError, "ALLOWLIST_PREDICATE_NOT_FOUND"):
            audit_native(snapshot(), ContractRegistry,
                         supported_by_predicates=("unknown",))

    def test_non_predicate_rejected(self):
        with self.assertRaisesRegex(ValueError, "ALLOWLIST_PREDICATE_NOT_FOUND"):
            audit_native(snapshot(), ContractRegistry,
                         supported_by_predicates=("CLAIM",))

    def test_duplicate_predicate_rejected(self):
        with self.assertRaisesRegex(ValueError, "INVALID_PREDICATE_ALLOWLIST"):
            audit_native(snapshot(), ContractRegistry,
                         supported_by_predicates=("supp", "supp"))

    def test_invalid_native_rejected(self):
        raw = snapshot()
        raw["nodes"][-1]["source_ref"] = "MISSING"
        with self.assertRaisesRegex(ValueError, "DANGLING"):
            audit_native(raw, ContractRegistry)

    def test_no_source_text_output(self):
        raw = snapshot()
        raw["display_names"]["CLAIM"] = "SECRET-DISPLAY-TEXT"
        report = audit_native(raw, ContractRegistry)
        self.assertNotIn("SECRET-DISPLAY-TEXT", json.dumps(report))

    def test_approval_not_upgraded(self):
        report = audit_native(snapshot(), ContractRegistry,
                              supported_by_predicates=("supp",))
        self.assertFalse(report["trust"]["allow_learning"])
        self.assertFalse(report["trust"]["evidence_authenticity_verified"])
        self.assertFalse(report["mapping"]["semantic_mapping_reviewed"])


if __name__ == "__main__":
    unittest.main()
