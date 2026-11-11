"""Strict, read-only import of an explicit LLM_TMP relation *snapshot*.

This is a BRIDGE-specific JSON interchange profile, NOT the undocumented
native persistent LLM_TMP registry format. All imported approvals are
UNAUTHENTICATED relation labels, not truth or human-review attestations.
"""
import hashlib
import json
from pathlib import Path

PROFILE = "ski-relation-snapshot-v0.8"
KINDS = frozenset(("ABOUT", "REFERS_TO", "DEPENDS_ON", "NEGATES",
                   "SUPPORTED_BY", "CONTRADICTS", "BEFORE", "AFTER", "CAUSES"))
STATES = frozenset(("PENDING", "APPROVED", "REJECTED"))
MAX_BYTES = 8 * 1024 * 1024
MAX_NODES = 10000
MAX_RELATIONS = 50000


def _unique_object(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            raise ValueError("DUPLICATE_JSON_KEY")
        output[key] = value
    return output


def _id(value):
    return isinstance(value, str) and 0 < len(value) <= 256 and bool(value.strip())


def _note(value):
    return isinstance(value, str) and 0 < len(value) <= 2048 and bool(value.strip())


def validate_snapshot(payload):
    if not isinstance(payload, dict) or set(payload) != {
            "format", "snapshot_id", "source_system", "nodes", "relations"}:
        raise ValueError("INVALID_SNAPSHOT_SCHEMA")
    if (payload["format"] != PROFILE or payload["source_system"] != "LLM_TMP"
            or not _id(payload["snapshot_id"])):
        raise ValueError("INVALID_SNAPSHOT_IDENTITY")
    nodes = payload["nodes"]
    relations = payload["relations"]
    if (not isinstance(nodes, list) or not 1 <= len(nodes) <= MAX_NODES
            or any(not _id(node) for node in nodes)
            or len(set(nodes)) != len(nodes)):
        raise ValueError("INVALID_SNAPSHOT_NODES")
    if not isinstance(relations, list) or len(relations) > MAX_RELATIONS:
        raise ValueError("INVALID_SNAPSHOT_RELATIONS")
    known = set(nodes)
    seen = set()
    for edge in relations:
        if not isinstance(edge, dict) or set(edge) != {
                "source", "kind", "target", "state", "evidence_id", "provenance"}:
            raise ValueError("INVALID_RELATION_SCHEMA")
        if (not _id(edge["source"]) or not _id(edge["target"])
                or edge["source"] not in known or edge["target"] not in known
                or edge["kind"] not in KINDS or edge["state"] not in STATES):
            raise ValueError("INVALID_RELATION")
        for key in ("evidence_id", "provenance"):
            if edge[key] is not None and not _note(edge[key]):
                raise ValueError("INVALID_EVIDENCE_METADATA")
        # An APPROVED label without any traceability is not imported.
        # Traceability here still does NOT authenticate its provenance.
        if edge["state"] == "APPROVED" and not (
                _id(edge["evidence_id"]) and _note(edge["provenance"])):
            raise ValueError("UNTRACED_APPROVED_RELATION")
        key = (edge["source"], edge["kind"], edge["target"],
               edge["state"], edge["evidence_id"], edge["provenance"])
        if key in seen:
            raise ValueError("DUPLICATE_RELATION")
        seen.add(key)
    return True


def load_snapshot(path, *, max_bytes=MAX_BYTES):
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_BYTES:
        raise ValueError("INVALID_BYTE_LIMIT")
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError("SNAPSHOT_FILE_NOT_FOUND")
    with source.open("rb") as handle:
        raw = handle.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError("SNAPSHOT_TOO_LARGE")
    try:
        payload = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_unique_object,
                             parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE_JSON")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("INVALID_SNAPSHOT_JSON") from exc
    validate_snapshot(payload)
    return payload, hashlib.sha256(raw).hexdigest()


def build_relation_graph(Graph, payload):
    validate_snapshot(payload)
    graph = Graph(payload["nodes"])
    if not callable(getattr(graph, "add_relation", None)):
        raise TypeError("RELATION_GRAPH_REQUIRED")
    for edge in payload["relations"]:
        graph.add_relation(
            edge["source"], edge["kind"], edge["target"],
            state=edge["state"], evidence_id=edge["evidence_id"],
            provenance=edge["provenance"])
    return graph


def import_snapshot(Graph, path):
    payload, file_sha256 = load_snapshot(path)
    graph = build_relation_graph(Graph, payload)
    return graph, {
        "format": PROFILE,
        "snapshot_id": payload["snapshot_id"],
        "snapshot_sha256": file_sha256,
        "nodes": len(payload["nodes"]),
        "relations": len(payload["relations"]),
        "approval_authenticated": False,
        "verified_fact": False,
        "persistent_registry_modified": False,
    }
