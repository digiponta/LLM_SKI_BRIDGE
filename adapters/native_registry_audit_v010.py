"""v0.10: conservative, read-only audit of native Intent SD v0.3 snapshots.

Native SDRegistry validates node topology, not reviewer authenticity. Report
structural counts and allowlist disposition without leaking source text.
The audit never approves relations, writes to disk, or invokes an LLM.
"""
from collections import Counter

from adapters.llm_tmp_native_v09 import read_native, load_registry_class


NODE_TYPES = frozenset(("TOPIC", "CONCEPT", "ENTITY", "PREDICATE", "RELATION"))
STATES = frozenset(("APPROVED", "PENDING", "REJECTED"))


def audit_native(data, Registry, *, supported_by_predicates=()):
    if not isinstance(data, dict):
        raise ValueError("INVALID_NATIVE_ROOT")
    # Exactly the native frozen snapshot plus its UI-only display_names.
    registry_data = {k: v for k, v in data.items() if k != "display_names"}
    registry = Registry(registry_data)
    if not isinstance(registry_data.get("nodes"), list):
        raise ValueError("INVALID_NATIVE_NODES")
    nodes = registry_data["nodes"]
    indexed = {node["sd_id"]: node for node in nodes}
    if len(indexed) != len(nodes):
        raise ValueError("DUPLICATE_SD_ID")
    allowed = tuple(supported_by_predicates)
    if any(not isinstance(p, str) or not p.strip() for p in allowed) or len(set(allowed)) != len(allowed):
        raise ValueError("INVALID_PREDICATE_ALLOWLIST")
    for predicate in allowed:
        if predicate not in indexed or indexed[predicate]["node_type"] != "PREDICATE":
            raise ValueError("ALLOWLIST_PREDICATE_NOT_FOUND")

    types = Counter(node["node_type"] for node in nodes)
    if any(t not in NODE_TYPES for t in types):
        raise ValueError("UNKNOWN_NODE_TYPE")

    by_state = Counter()
    by_predicate = {}
    eligible = 0
    excluded = Counter()
    nonempty_evidence = 0
    evidence_ref_counts = Counter()
    relation_count = 0
    for node in nodes:
        if node["node_type"] != "RELATION":
            continue
        relation_count += 1
        state = node["validation_state"]
        if state not in STATES:
            raise ValueError("INVALID_RELATION_STATE")
        by_state[state] += 1
        predicate = node["predicate_ref"]
        if predicate not in by_predicate:
            by_predicate[predicate] = {"total": 0, "states": Counter(),
                                       "mapped_to_supported_by": predicate in allowed}
        by_predicate[predicate]["total"] += 1
        by_predicate[predicate]["states"][state] += 1
        evidence_id = node.get("evidence_id")
        if isinstance(evidence_id, str) and evidence_id.strip():
            nonempty_evidence += 1
            evidence_ref_counts[evidence_id] += 1
        if predicate not in allowed:
            excluded["predicate_not_allowlisted"] += 1
        elif state != "APPROVED":
            excluded["not_approved"] += 1
        elif not isinstance(evidence_id, str) or not evidence_id.strip():
            excluded["missing_evidence_id"] += 1
        else:
            eligible += 1

    # Identifiers are intentionally excluded; do not expose sensitive labels.
    predicates = [
        {"predicate_sd_id": key, "relations": entry["total"],
         "states": {state: entry["states"][state] for state in sorted(STATES)},
         "mapped_to_supported_by": entry["mapped_to_supported_by"]}
        for key, entry in sorted(by_predicate.items())
    ]
    return {
        "status": "AUDITED",
        "native_schema": "intent_sd_context_v03.SDRegistry",
        "namespace": registry.namespace,
        "snapshot_id": registry_data.get("snapshot_id"),
        "counts": {
            "nodes_total": len(nodes),
            "node_types": {kind: types[kind] for kind in sorted(NODE_TYPES)},
            "relations_total": relation_count,
            "relation_states": {state: by_state[state] for state in sorted(STATES)},
            "relations_with_evidence_id": nonempty_evidence,
            "reused_evidence_ids": sum(n > 1 for n in evidence_ref_counts.values()),
            "eligible_for_explicit_mapping": eligible,
            "excluded": dict(sorted(excluded.items())),
        },
        "predicates": predicates,
        "mapping": {
            "supported_by_predicates": list(allowed),
            "default_deny": len(allowed) == 0,
            "semantic_mapping_reviewed": False,
        },
        "trust": {
            "approval_authenticated": False,
            "evidence_authenticity_verified": False,
            "verified_fact": False,
            "allow_model_context": False,
            "allow_learning": False,
        },
        "source_modified": False,
        "caution": "Structural analysis only; APPROVED flags and Evidence IDs do not prove factual truth or reviewer authority.",
    }


def audit_file(native_path, tmp_dir, *, supported_by_predicates=()):
    data, digest = read_native(native_path)
    report = audit_native(data, load_registry_class(tmp_dir),
                          supported_by_predicates=supported_by_predicates)
    report["source_sha256"] = digest
    return report
