"""Read-only adapter to LLM_TMP v0.35 RelationGraph.evidence_path.

Pass an actual RelationGraph instance to this adapter. No data is imported,
modified, promoted or approved by the bridge.
"""
from ski.message import validate_request, response, validate_roundtrip


class LLM_TMPAdapter:
    def __init__(self, graph):
        if not callable(getattr(graph, "evidence_path", None)):
            raise TypeError("EVIDENCE_PATH_REQUIRED")
        self.graph = graph

    def search(self, req):
        if not validate_request(req):
            raise ValueError("INVALID_REQUEST")
        result = self.graph.evidence_path(
            req["source_sd"], req["target_sd"],
            max_hops=req["max_hops"], max_visits=req["max_visits"])
        if not isinstance(result, dict) or result.get("verified_fact") is not False:
            raise ValueError("INVALID_GRAPH_RESULT")
        status = result.get("status")
        # LLM_TMP v0.35 returns NOT_FOUND when hop budget is exhausted.
        # Do not turn that into a claim of exhaustive absence.
        if status not in ("FOUND", "NOT_FOUND", "LIMIT_REACHED", "UNKNOWN_NODE"):
            raise ValueError("UNSUPPORTED_GRAPH_STATUS")
        return {"status": status, "path": result.get("path")}

    def handle(self, req):
        result = self.search(req)
        resp = response(req, result, sender=req["receiver"], receiver=req["sender"])
        if not validate_roundtrip(req, resp):
            raise RuntimeError("INVALID_ROUNDTRIP")
        return resp
