"""v0.14: structured diagnostic metadata embedded in SKI Dataset B.

This is an optional *profile extension* to SKI v0.5 Natural Language
Dataset B, not a new canonical HASKI_DOC wire format. An unauthenticated
APPROVED relation or SHA-256 digest never establishes factual truth,
sender identity, human approval, or permission to use evidence in an LLM.
"""
import hashlib
import json

from ski.dataset_v05 import validate_dataset
from ski.message import ALLOWED_STATES, validate_roundtrip

PROFILE = "ski-diagnostic-v0.14"
MAX_EDGES = 5
STATES = frozenset(ALLOWED_STATES)
STATUS_TEXT = {
    "FOUND": "承認済み関係の経路を検出。事実の真偽は未検証です。",
    "NOT_FOUND": "指定範囲内で関係を検出できませんでした。",
    "UNKNOWN_NODE": "未登録のSemantic IDを含みます。",
    "LIMIT_REACHED": "探索数上限に達しました。",
    "DEPTH_LIMIT_REACHED": "探索深度上限に達しました。",
}


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _sha(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def build_diagnostic(request, response, dataset_a, dataset_b):
    """Construct an inspectable, text-free diagnostic from real SKI envelopes.

    Only *bounded structural* fields, no path edges, raw source text or
    untrusted provenance enter the diagnostic profile.
    """
    if not validate_roundtrip(request, response):
        raise ValueError("INVALID_EVIDENCE_ENVELOPES")
    validate_dataset(dataset_a, source_llm="LLM_CHA", target_llm="LLM_TMP")
    validate_dataset(dataset_b, source_llm="LLM_TMP", target_llm="LLM_CHA")
    if len(dataset_a) != 1 or len(dataset_b) != 1:
        raise ValueError("INVALID_MESSAGE_COUNT")
    a, b = dataset_a[0], dataset_b[0]
    if (a["source_sd_id"] != request["source_sd"]
            or b["source_sd_id"] != response["target_sd"]
            or b["parent_sd_id"] != a["source_sd_id"]
            or b.get("derivation", {}).get("response_to_message_id") != a["message_id"]
            or b.get("derivation", {}).get("source_sd_id") != a["source_sd_id"]
            or response["correlation_id"] != request["message_id"]):
        raise ValueError("CROSS_PROTOCOL_CORRELATION_MISMATCH")
    status = response["status"]
    if status not in STATES:
        raise ValueError("UNSUPPORTED_DIAGNOSTIC_STATUS")
    path = response.get("path")
    hops = len(path) if status == "FOUND" else None
    if hops is not None and (hops > MAX_EDGES or hops > request["max_hops"]):
        raise ValueError("UNSAFE_PATH_LENGTH")
    diagnostic = {
        "profile": PROFILE,
        "response_to_message_id": a["message_id"],
        "evidence_request_id": request["message_id"],
        "evidence_response_id": response["message_id"],
        "source_sd": request["source_sd"],
        "target_sd": request["target_sd"],
        "diagnostic_status": status,
        "evidence_path_hops": hops,
        "truth_state": "UNVERIFIED",
        "approval_state": "UNAUTHENTICATED",
        "verified_fact": False,
        "human_approved": False,
        "allow_model_context": False,
        "allow_answer_from_evidence": False,
        "allow_learning": False,
        "allow_truth_promotion": False,
        "display_message": STATUS_TEXT[status],
    }
    # This detects accidental mutation; it does NOT prove authenticity.
    diagnostic["diagnostic_sha256"] = _sha(diagnostic)
    return diagnostic


def validate_diagnostic(exchange):
    """Verify SKI Dataset B diagnostic against all underlying envelopes.

    Legacy v0.13 messages without the field remain valid through the
    existing Truth Boundary; calling this v0.14 validator requires it.
    """
    if not isinstance(exchange, dict):
        raise ValueError("INVALID_EXCHANGE")
    try:
        a = exchange["dataset_a"]
        b = exchange["dataset_b"]
        req = exchange["evidence_request"]
        resp = exchange["evidence_response"]
        diagnostic = b[0]["diagnostic"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("MISSING_SKI_DIAGNOSTIC") from exc
    if not isinstance(diagnostic, dict):
        raise ValueError("INVALID_SKI_DIAGNOSTIC")
    # Python compares 0 == False and 1 == True, so equality with the
    # regenerated profile alone is not a strict wire type check.
    for flag in ("verified_fact", "human_approved", "allow_model_context",
                 "allow_answer_from_evidence", "allow_learning",
                 "allow_truth_promotion"):
        if type(diagnostic.get(flag)) is not bool or diagnostic[flag] is not False:
            raise ValueError("UNSAFE_DIAGNOSTIC_FLAG")
    hops = diagnostic.get("evidence_path_hops")
    if hops is not None and (type(hops) is not int or hops < 0 or hops > MAX_EDGES):
        raise ValueError("INVALID_DIAGNOSTIC_HOPS")
    expected = build_diagnostic(req, resp, a, b)
    if diagnostic != expected:
        raise ValueError("SKI_DIAGNOSTIC_MISMATCH")
    return True


def attach_diagnostic(exchange):
    """Return an independent copy of the exchange with profiled Dataset B.

    The result retains all A/B/ACK/Evidence fields and is validated
    against v0.5 and v0.7 by the caller.
    """
    import copy
    if not isinstance(exchange, dict):
        raise ValueError("INVALID_EXCHANGE")
    result = copy.deepcopy(exchange)
    result["dataset_b"][0]["diagnostic"] = build_diagnostic(
        result["evidence_request"], result["evidence_response"],
        result["dataset_a"], result["dataset_b"])
    validate_diagnostic(result)
    return result
