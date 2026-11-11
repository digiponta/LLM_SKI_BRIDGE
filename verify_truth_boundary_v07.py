"""Validate SKI evidence-to-Truth-Gate boundary against trusted LLM_TMP code.

Uses a synthetic in-memory graph and never writes into LLM_CHA or LLM_TMP.
"""
import argparse
import json

from adapters.cha_truth_boundary_v07 import assess_exchange
from adapters.llm_cha_client_v05 import CHAClient
from adapters.llm_tmp_real import LLM_TMPAdapter
from verify_llm_tmp_integration_v03 import load_graph_class


def run(graph_class):
    graph = graph_class(("CLAIM", "EVIDENCE", "PENDING"))
    graph.add_relation("CLAIM", "SUPPORTED_BY", "EVIDENCE",
                       state="APPROVED", provenance="synthetic-v07")
    graph.add_relation("CLAIM", "SUPPORTED_BY", "PENDING",
                       state="PENDING", provenance="synthetic-v07")
    client = CHAClient(LLM_TMPAdapter(graph))
    outcomes = {}
    for name, target, expected in (
        ("approved", "EVIDENCE", "FOUND"),
        ("pending", "PENDING", "NOT_FOUND"),
        ("unknown", "MISSING", "UNKNOWN_NODE"),
    ):
        decision = assess_exchange(
            client.exchange("根拠の状態を確認", source_sd="CLAIM", target_sd=target))
        passed = (decision["evidence_status"] == expected
                  and decision["action"] == "DIAGNOSTIC_ONLY"
                  and not decision["allow_model_context"]
                  and not decision["allow_answer_from_evidence"]
                  and not decision["allow_learning"]
                  and not decision["allow_truth_promotion"])
        outcomes[name] = {"status": decision["evidence_status"], "pass": passed}
    return {"status": "PASS" if all(o["pass"] for o in outcomes.values()) else "FAIL",
            "scope": "real LLM_TMP graph class; synthetic graph; no LLM_CHA inference",
            "cases": outcomes}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm-tmp-dir", required=True)
    args = parser.parse_args()
    report = run(load_graph_class(args.llm_tmp_dir))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
