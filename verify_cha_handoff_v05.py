"""Run LLM_CHA-facing SKI sidecar against trusted LLM_TMP source on disk.

Does not invoke LLM_CHA inference or mutate either repository.
"""
import argparse
import json

from adapters.llm_cha_client_v05 import CHAClient
from adapters.llm_tmp_real import LLM_TMPAdapter
from verify_llm_tmp_integration_v03 import load_graph_class


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm-tmp-dir", required=True)
    parser.add_argument("--text", default="この命題の根拠を確認してください")
    args = parser.parse_args()
    Graph = load_graph_class(args.llm_tmp_dir)
    graph = Graph(["CHA-CLAIM", "TMP-EVIDENCE", "TMP-PENDING"])
    graph.add_relation(
        "CHA-CLAIM", "SUPPORTED_BY", "TMP-EVIDENCE",
        state="APPROVED", evidence_id="EV-DEMO", provenance="synthetic-v05")
    graph.add_relation(
        "CHA-CLAIM", "SUPPORTED_BY", "TMP-PENDING",
        state="PENDING", evidence_id="EV-PENDING", provenance="synthetic-v05")
    client = CHAClient(LLM_TMPAdapter(graph))
    results = {}
    for label, target in (("approved", "TMP-EVIDENCE"),
                          ("pending", "TMP-PENDING"),
                          ("unknown", "NOT-REGISTERED")):
        exchange = client.exchange(args.text, source_sd="CHA-CLAIM", target_sd=target)
        results[label] = {
            "evidence_status": exchange["evidence_response"]["status"],
            "ack_valid": exchange["verification"]["structural_exchange_valid"],
            "response_to_message_id": exchange["dataset_b"][0]["derivation"]["response_to_message_id"],
            "request_message_id": exchange["dataset_a"][0]["message_id"],
            "verified_fact": exchange["verification"]["verified_fact"],
            "llm_cha_inference_invoked": exchange["verification"]["llm_cha_inference_invoked"],
        }
    print(json.dumps({
        "status": "PASS" if (
            results["approved"]["evidence_status"] == "FOUND"
            and results["pending"]["evidence_status"] == "NOT_FOUND"
            and results["unknown"]["evidence_status"] == "UNKNOWN_NODE"
            and all(x["request_message_id"] == x["response_to_message_id"]
                    and not x["verified_fact"] for x in results.values())
        ) else "FAIL",
        "scope": "real LLM_TMP RelationGraph API, synthetic in-memory graph; LLM_CHA sidecar only",
        "cases": results,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
