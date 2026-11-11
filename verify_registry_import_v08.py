"""Verify v0.8 snapshot import with real LLM_TMP Graph and SKI truth boundary.

Only reads user-specified snapshot. Does not modify original LLM_TMP registry,
authenticate approval provenance, or run any LLM.
"""
import argparse
import json

from adapters.cha_truth_boundary_v07 import assess_exchange
from adapters.llm_cha_client_v05 import CHAClient
from adapters.llm_tmp_real import LLM_TMPAdapter
from adapters.llm_tmp_registry_v08 import import_snapshot
from verify_llm_tmp_integration_v03 import load_graph_class


def run(graph_class, snapshot_path, *, source_sd="CLAIM",
        approved_target="EVIDENCE", pending_target="PENDING",
        rejected_target="REJECTED"):
    graph, meta = import_snapshot(graph_class, snapshot_path)
    client = CHAClient(LLM_TMPAdapter(graph))
    results = {}
    for name, target, expected in (
        ("approved", approved_target, "FOUND"),
        ("pending", pending_target, "NOT_FOUND"),
        ("rejected", rejected_target, "NOT_FOUND"),
        ("unknown", "SKI-NONEXISTENT-REGISTRY-ID-v08", "UNKNOWN_NODE"),
    ):
        if name == "unknown" and target in graph.nodes:
            raise ValueError("RESERVED_UNKNOWN_ID_COLLISION")
        exchange = client.exchange(
            "Evidence関係の状態を確認", source_sd=source_sd, target_sd=target)
        decision = assess_exchange(exchange)
        passed = (decision["evidence_status"] == expected
                  and decision["action"] == "DIAGNOSTIC_ONLY"
                  and decision["allow_model_context"] is False
                  and decision["allow_learning"] is False
                  and decision["allow_truth_promotion"] is False)
        results[name] = {"expected": expected,
                         "actual": decision["evidence_status"], "pass": passed}
    return {
        "status": "PASS" if all(v["pass"] for v in results.values()) else "FAIL",
        "scope": "real LLM_TMP Graph API; explicit JSON snapshot; no LLM inference",
        "snapshot": meta, "cases": results,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--llm-tmp-dir", required=True)
    p.add_argument("--snapshot", required=True)
    p.add_argument("--source-sd", default="CLAIM")
    p.add_argument("--approved-target", default="EVIDENCE")
    p.add_argument("--pending-target", default="PENDING")
    p.add_argument("--rejected-target", default="REJECTED")
    args = p.parse_args()
    report = run(
        load_graph_class(args.llm_tmp_dir), args.snapshot,
        source_sd=args.source_sd, approved_target=args.approved_target,
        pending_target=args.pending_target, rejected_target=args.rejected_target)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
