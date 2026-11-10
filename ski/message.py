"""Experimental SKI message envelopes; not the canonical HASKI_DOC schema."""
import uuid

ALLOWED_STATES = frozenset({"FOUND", "NOT_FOUND", "LIMIT_REACHED", "DEPTH_LIMIT_REACHED", "UNKNOWN_NODE"})


def request(source_sd, target_sd, *, sender="LLM_CHA", receiver="LLM_TMP", request_id=None,
            max_hops=5, max_visits=2000):
    if not all(isinstance(x, str) and x.strip() for x in (source_sd, target_sd, sender, receiver)):
        raise ValueError("INVALID_REQUEST")
    if type(max_hops) is not int or not 0 <= max_hops <= 5 or type(max_visits) is not int or max_visits < 1:
        raise ValueError("INVALID_LIMIT")
    return {
        "ski_version": "bridge-v0.1-experimental",
        "message_type": "EVIDENCE_REQUEST",
        "message_id": request_id or str(uuid.uuid4()),
        "sender": sender, "receiver": receiver,
        "source_sd": source_sd, "target_sd": target_sd,
        "max_hops": max_hops, "max_visits": max_visits,
    }


def response(req, search_result, *, sender="LLM_TMP", receiver="LLM_CHA"):
    if req.get("message_type") != "EVIDENCE_REQUEST" or not req.get("message_id"):
        raise ValueError("INVALID_REQUEST")
    status = search_result.get("status")
    if status not in ALLOWED_STATES:
        raise ValueError("INVALID_STATUS")
    path = search_result.get("path")
    if status == "FOUND":
        if not isinstance(path, list):
            raise ValueError("MISSING_PATH")
        if any(e.get("kind") != "SUPPORTED_BY" or e.get("state") != "APPROVED"
               for e in path):
            raise ValueError("UNAPPROVED_EVIDENCE")
    elif path is not None:
        raise ValueError("UNEXPECTED_PATH")
    return {
        "ski_version": "bridge-v0.1-experimental",
        "message_type": "EVIDENCE_RESPONSE",
        "message_id": str(uuid.uuid4()),
        "correlation_id": req["message_id"],
        "sender": sender, "receiver": receiver,
        "source_sd": req["source_sd"], "target_sd": req["target_sd"],
        "status": status, "path": path,
        "max_hops": req["max_hops"], "max_visits": req["max_visits"],
        "verified_fact": False,
        "human_approved": False,
    }


def validate_roundtrip(req, resp):
    if req.get("message_type") != "EVIDENCE_REQUEST" or resp.get("message_type") != "EVIDENCE_RESPONSE":
        return False
    if resp.get("correlation_id") != req.get("message_id"):
        return False
    if resp.get("source_sd") != req.get("source_sd") or resp.get("target_sd") != req.get("target_sd"):
        return False
    if resp.get("sender") != req.get("receiver") or resp.get("receiver") != req.get("sender"):
        return False
    if resp.get("verified_fact") is not False or resp.get("human_approved") is not False:
        return False
    if resp.get("status") not in ALLOWED_STATES:
        return False
    path = resp.get("path")
    if resp["status"] == "FOUND":
        return isinstance(path, list) and all(
            e.get("kind") == "SUPPORTED_BY" and e.get("state") == "APPROVED"
            for e in path)
    return path is None
