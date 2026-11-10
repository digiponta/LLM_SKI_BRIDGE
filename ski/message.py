"""Experimental SKI evidence exchange (not the canonical HASKI_DOC schema)."""
import uuid

VERSION = "bridge-v0.1-experimental"
ALLOWED_STATES = frozenset({"FOUND", "NOT_FOUND", "LIMIT_REACHED", "DEPTH_LIMIT_REACHED", "UNKNOWN_NODE"})

def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())

def _limits(max_hops, max_visits):
    return (type(max_hops) is int and 0 <= max_hops <= 5
            and type(max_visits) is int and max_visits >= 1)

def _valid_path(path, source, target, max_hops):
    if not isinstance(path, list) or len(path) > max_hops:
        return False
    if not path:
        return source == target
    if source == target:
        return False
    current = source
    seen = {source}
    for edge in path:
        if not isinstance(edge, dict):
            return False
        nxt = edge.get("target")
        if (edge.get("source") != current or not _nonempty(nxt)
                or edge.get("kind") != "SUPPORTED_BY"
                or edge.get("state") != "APPROVED" or nxt in seen):
            return False
        current = nxt
        seen.add(nxt)
    return current == target

def validate_request(req):
    return (isinstance(req, dict) and req.get("ski_version") == VERSION
            and req.get("message_type") == "EVIDENCE_REQUEST"
            and all(_nonempty(req.get(key)) for key in (
                "message_id", "sender", "receiver", "source_sd", "target_sd"))
            and req["sender"] != req["receiver"]
            and _limits(req.get("max_hops"), req.get("max_visits")))

def request(source_sd, target_sd, *, sender="LLM_CHA", receiver="LLM_TMP",
            request_id=None, max_hops=5, max_visits=2000):
    req = {
        "ski_version": VERSION,
        "message_type": "EVIDENCE_REQUEST",
        "message_id": str(uuid.uuid4()) if request_id is None else request_id,
        "sender": sender, "receiver": receiver,
        "source_sd": source_sd, "target_sd": target_sd,
        "max_hops": max_hops, "max_visits": max_visits,
    }
    if not validate_request(req):
        raise ValueError("INVALID_REQUEST")
    return req

def validate_response(req, resp):
    if not validate_request(req) or not isinstance(resp, dict):
        return False
    if (resp.get("ski_version") != VERSION
            or resp.get("message_type") != "EVIDENCE_RESPONSE"
            or not _nonempty(resp.get("message_id"))
            or resp.get("message_id") == req["message_id"]
            or resp.get("correlation_id") != req["message_id"]
            or resp.get("source_sd") != req["source_sd"]
            or resp.get("target_sd") != req["target_sd"]
            or resp.get("sender") != req["receiver"]
            or resp.get("receiver") != req["sender"]
            or resp.get("max_hops") != req["max_hops"]
            or resp.get("max_visits") != req["max_visits"]
            or resp.get("verified_fact") is not False
            or resp.get("human_approved") is not False
            or resp.get("status") not in ALLOWED_STATES):
        return False
    if resp["status"] == "FOUND":
        return _valid_path(resp.get("path"), req["source_sd"],
                           req["target_sd"], req["max_hops"])
    return resp.get("path") is None

def response(req, search_result, *, sender="LLM_TMP", receiver="LLM_CHA"):
    if not validate_request(req) or not isinstance(search_result, dict):
        raise ValueError("INVALID_REQUEST")
    status = search_result.get("status")
    if status not in ALLOWED_STATES:
        raise ValueError("INVALID_STATUS")
    path = search_result.get("path")
    if status == "FOUND" and not _valid_path(
            path, req["source_sd"], req["target_sd"], req["max_hops"]):
        raise ValueError("INVALID_EVIDENCE_PATH")
    if status != "FOUND" and path is not None:
        raise ValueError("UNEXPECTED_PATH")
    resp = {
        "ski_version": VERSION,
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
    if not validate_response(req, resp):
        raise ValueError("INVALID_RESPONSE")
    return resp

def validate_roundtrip(req, resp):
    """Validate envelope, correlation, limits, provenance state and contiguous path."""
    return validate_response(req, resp)
