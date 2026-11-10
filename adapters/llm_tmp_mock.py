"""Pure mock: does not import or execute the real LLM_TMP."""
from collections import deque


class MockTMP:
    def __init__(self):
        self.nodes = {"SD-CLAIM", "SD-EVIDENCE", "SD-PENDING", "SD-OTHER"}
        self.edges = {
            "SD-CLAIM": [
                {"source": "SD-CLAIM", "target": "SD-EVIDENCE", "kind": "SUPPORTED_BY",
                 "state": "APPROVED", "evidence_id": "EV-1", "provenance": "synthetic"},
                {"source": "SD-CLAIM", "target": "SD-PENDING", "kind": "SUPPORTED_BY",
                 "state": "PENDING", "evidence_id": "EV-2", "provenance": "synthetic"}
            ]
        }

    def search(self, source, target, max_hops=5, max_visits=2000):
        if source not in self.nodes or target not in self.nodes:
            return {"status": "UNKNOWN_NODE", "path": None}
        if source == target:
            return {"status": "FOUND", "path": []}
        queue = deque([(source, [])])
        seen = {source}
        depth_truncated = False
        while queue:
            node, path = queue.popleft()
            for edge in self.edges.get(node, ()):
                if edge["state"] != "APPROVED" or edge["kind"] != "SUPPORTED_BY":
                    continue
                if edge["target"] in seen:
                    continue
                if len(path) >= max_hops:
                    depth_truncated = True
                    continue
                if len(seen) >= max_visits:
                    return {"status": "LIMIT_REACHED", "path": None}
                new_path = path + [edge]
                seen.add(edge["target"])
                if edge["target"] == target:
                    return {"status": "FOUND", "path": new_path}
                queue.append((edge["target"], new_path))
        return {"status": "DEPTH_LIMIT_REACHED" if depth_truncated else "NOT_FOUND", "path": None}
