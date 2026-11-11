"""Read-only conversion of LLM_TMP Intent SD v0.3 native frozen registry.

Never infer a SUPPORTED_BY relation from a topic/continuity predicate.
Only caller-supplied, explicitly allowlisted predicate SD IDs can be mapped,
and mapped labels remain UNAUTHENTICATED and UNVERIFIED.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
from adapters.llm_tmp_registry_v08 import PROFILE, MAX_BYTES, validate_snapshot

def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result

def read_native(path):
    src = Path(path)
    with src.open("rb") as f:
        raw = f.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("NATIVE_TOO_LARGE")
    try:
        data = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("INVALID_NATIVE_JSON") from exc
    return data, hashlib.sha256(raw).hexdigest()

def load_registry_class(tmp_dir):
    """Load only trusted local LLM_TMP source; imports execute local Python."""
    path = Path(tmp_dir).resolve() / "intent_sd_context_v03.py"
    if not path.is_file():
        raise FileNotFoundError("LLM_TMP_SD_REGISTRY_MODULE_NOT_FOUND")
    spec = importlib.util.spec_from_file_location("llm_tmp_intent_sd_v03_import", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("IMPORT_FAILED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SDRegistry

def convert_native(data, Registry, *, supported_by_predicates=()):
    if not isinstance(data, dict):
        raise ValueError("INVALID_NATIVE_ROOT")
    # The optional display_names belong to the annotation UI, not SDRegistry.
    registry_input = {k: v for k, v in data.items() if k != "display_names"}
    registry = Registry(registry_input)
    namespace = registry.namespace
    snapshot_id = registry_input.get("snapshot_id")
    if not isinstance(snapshot_id, str) or not snapshot_id.strip():
        raise ValueError("NATIVE_SNAPSHOT_ID_REQUIRED")
    allowed = tuple(supported_by_predicates)
    if any(not isinstance(p, str) or not p.strip() for p in allowed) or len(set(allowed)) != len(allowed):
        raise ValueError("INVALID_PREDICATE_ALLOWLIST")
    nodes = registry_input["nodes"]
    indexed = {n["sd_id"]: n for n in nodes}
    for p in allowed:
        if p not in indexed or indexed[p]["node_type"] != "PREDICATE":
            raise ValueError("ALLOWLIST_PREDICATE_NOT_FOUND")
    topics = sorted(n["sd_id"] for n in nodes if n["node_type"] in ("TOPIC", "ENTITY", "CONCEPT"))
    relations = []
    skipped = {"not_allowlisted": 0, "not_approved": 0}
    for n in nodes:
        if n["node_type"] != "RELATION":
            continue
        if n["predicate_ref"] not in allowed:
            skipped["not_allowlisted"] += 1
            continue
        if n["validation_state"] != "APPROVED":
            skipped["not_approved"] += 1
            continue
        # Intent SD v0.3 does not carry authenticated provenance.
        # The value below is a *local reference*, not proof of approval.
        relations.append({
            "source": n["source_ref"], "kind": "SUPPORTED_BY",
            "target": n["target_ref"], "state": "APPROVED",
            "evidence_id": n["evidence_id"],
            "provenance": "unverified-native-intent-sd:" + namespace + ":" + n["sd_id"],
        })
    out = {"format": PROFILE,
           "snapshot_id": "intent-sd-v03:" + namespace + ":" + snapshot_id,
           "source_system": "LLM_TMP", "nodes": topics, "relations": relations}
    validate_snapshot(out)
    return out, {
        "native_schema": "intent_sd_context_v03.SDRegistry",
        "namespace": namespace, "native_snapshot_id": snapshot_id,
        "source_predicates_allowlisted": list(allowed),
        "relations_exported": len(relations), "skipped": skipped,
        "approval_authenticated": False, "verified_fact": False,
        "source_modified": False,
        "note": "Explicit policy mapping; native topic relations are NOT automatically evidence.",
    }

def convert_file(path, tmp_dir, *, supported_by_predicates=()):
    data, digest = read_native(path)
    converted, report = convert_native(
        data, load_registry_class(tmp_dir),
        supported_by_predicates=supported_by_predicates)
    report["native_file_sha256"] = digest
    return converted, report
