"""Run an opt-in in-process integration against an existing local LLM_TMP checkout.

The supplied Python module is executed when imported: point only at a trusted
local checkout. This script never modifies the LLM_TMP source or result files.
"""
import argparse
import importlib.util
import json
from pathlib import Path

from adapters.llm_tmp_real import LLM_TMPAdapter
from ski.message import request, validate_roundtrip


def load_graph_class(tmp_dir):
    path = Path(tmp_dir).expanduser().resolve() / "semantic_relation_graph_v035.py"
    if not path.is_file():
        raise FileNotFoundError(f"LLM_TMP_MODULE_NOT_FOUND: {path}")
    spec = importlib.util.spec_from_file_location("llm_tmp_relation_graph_integration", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("IMPORT_SPEC_FAILED")
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.RelationGraph


def run(Graph):
    graph = Graph(["CLAIM", "MID", "EVIDENCE", "PENDING", "REJECTED", "ISOLATED"])
    graph.add_relation("CLAIM", "SUPPORTED_BY", "MID",
                       state="APPROVED", evidence_id="EV-1", provenance="bridge-integration")
    graph.add_relation("MID", "SUPPORTED_BY", "EVIDENCE",
                       state="APPROVED", evidence_id="EV-2", provenance="bridge-integration")
    graph.add_relation("CLAIM", "SUPPORTED_BY", "PENDING", state="PENDING")
    graph.add_relation("CLAIM", "SUPPORTED_BY", "REJECTED", state="REJECTED")
    cases = [
        ("approved", "CLAIM", "EVIDENCE", 5, 2000, "FOUND"),
        ("pending", "CLAIM", "PENDING", 5, 2000, "NOT_FOUND"),
        ("rejected", "CLAIM", "REJECTED", 5, 2000, "NOT_FOUND"),
        ("unknown", "CLAIM", "MISSING", 5, 2000, "UNKNOWN_NODE"),
        ("visit_budget", "CLAIM", "EVIDENCE", 5, 1, "LIMIT_REACHED"),
        ("hop_budget", "CLAIM", "EVIDENCE", 1, 2000, "NOT_FOUND"),
    ]
    adapter = LLM_TMPAdapter(graph)
    outcomes = []
    for label, source, target, hops, visits, expected in cases:
        req = request(source, target, max_hops=hops, max_visits=visits)
        resp = adapter.handle(req)
        passed = (resp["status"] == expected and validate_roundtrip(req, resp)
                  and resp["human_approved"] is False and resp["verified_fact"] is False)
        outcomes.append({"case": label, "expected": expected,
                         "actual": resp["status"], "pass": passed})
    return {"status": "PASS" if all(c["pass"] for c in outcomes) else "FAIL",
            "scope": "real LLM_TMP RelationGraph API; synthetic in-memory fixtures",
            "cases": outcomes}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm-tmp-dir", required=True)
    args = parser.parse_args()
    outcome = run(load_graph_class(args.llm_tmp_dir))
    print(json.dumps(outcome, ensure_ascii=False, indent=2))
    if outcome["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
