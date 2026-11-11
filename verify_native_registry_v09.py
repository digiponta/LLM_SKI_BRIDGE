"""Verify native LLM_TMP Intent SD v0.3 snapshot -> explicit SKI relation profile.

No persistent files are written; mapping is opt-in and never truth-certified.
"""
import argparse
import json
from adapters.llm_tmp_native_v09 import convert_file
from adapters.llm_tmp_registry_v08 import build_relation_graph
from adapters.llm_tmp_real import LLM_TMPAdapter
from adapters.llm_cha_client_v05 import CHAClient
from adapters.cha_truth_boundary_v07 import assess_exchange
from verify_llm_tmp_integration_v03 import load_graph_class

def run(tmp_dir, native_path, predicate, source, target):
    converted, report = convert_file(
        native_path, tmp_dir,
        supported_by_predicates=() if predicate is None else (predicate,))
    graph = build_relation_graph(load_graph_class(tmp_dir), converted)
    exchange = CHAClient(LLM_TMPAdapter(graph)).exchange(
        "指定した関係の状態を確認", source_sd=source, target_sd=target)
    decision = assess_exchange(exchange)
    expected = "FOUND" if predicate is not None else "NOT_FOUND"
    passed = (decision["evidence_status"] == expected
              and decision["action"] == "DIAGNOSTIC_ONLY"
              and not decision["allow_model_context"]
              and not decision["allow_truth_promotion"])
    return {
        "status": "PASS" if passed else "FAIL",
        "scope": "real LLM_TMP SDRegistry and RelationGraph APIs; synthetic fixture; no inference",
        "expected": expected, "actual": decision["evidence_status"],
        "native": report,
        "conversion": {"nodes": len(converted["nodes"]),
                       "relations": len(converted["relations"])},
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--llm-tmp-dir", required=True)
    p.add_argument("--native", required=True)
    p.add_argument("--supported-by-predicate")
    p.add_argument("--source", default="CLAIM")
    p.add_argument("--target", default="EVIDENCE")
    args = p.parse_args()
    result = run(args.llm_tmp_dir, args.native,
                 args.supported_by_predicate, args.source, args.target)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result["status"] != "PASS":
        raise SystemExit(1)

if __name__ == "__main__":
    main()
