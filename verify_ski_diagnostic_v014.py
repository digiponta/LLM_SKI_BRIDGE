"""Validate v0.14 SKI Dataset B diagnostic against the actual local LLM_TMP.

Uses synthetic native SD fixture, actual LLM_TMP SDRegistry/RelationGraph,
the SKI A/ACK/B adapters, Truth Boundary and optional live LLM_CHA runtime
module. No model inference, training or persistent writes.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

from adapters.llm_tmp_native_v09 import convert_file
from adapters.llm_tmp_registry_v08 import build_relation_graph
from adapters.llm_tmp_real import LLM_TMPAdapter
from adapters.llm_cha_client_v05 import CHAClient
from adapters.cha_truth_boundary_v07 import assess_exchange
from ski.diagnostic_v014 import PROFILE, validate_diagnostic
from ski.dataset_v05 import validate_dataset, validate_replies
from verify_llm_tmp_integration_v03 import load_graph_class


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _get_cha_runtime(cha_dir):
    root = Path(cha_dir).resolve()
    path = root / "ski_runtime_v011.py"
    if not path.is_file():
        raise FileNotFoundError("LLM_CHA_RUNTIME_MODULE_MISSING")
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location("llm_cha_runtime_v014", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify(tmp_dir, native, bridge_dir=".", cha_dir=None):
    root = Path(tmp_dir).resolve()
    source = Path(native).resolve()
    before = _digest(source)
    snapshot, report = convert_file(
        source, root, supported_by_predicates=("support-pred",))
    graph = build_relation_graph(load_graph_class(root), snapshot)
    x = CHAClient(LLM_TMPAdapter(graph)).exchange(
        "構造化診断の動作確認", source_sd="CLAIM", target_sd="EVIDENCE")
    diag = x["dataset_b"][0]["diagnostic"]
    checks = {}
    checks["ski_dataset_b_profile"] = (
        diag["profile"] == PROFILE and diag["diagnostic_status"] == "FOUND")
    checks["dataset_b_valid"] = (
        validate_dataset(x["dataset_b"]) and
        validate_replies(x["dataset_a"], x["dataset_b"]))
    checks["ski_diagnostic_correlated"] = validate_diagnostic(x)
    decision = assess_exchange(x)
    checks["truth_boundary"] = (
        decision["action"] == "DIAGNOSTIC_ONLY" and
        decision["allow_model_context"] is False and
        decision["allow_learning"] is False and
        decision["allow_answer_from_evidence"] is False and
        decision["allow_truth_promotion"] is False)
    checks["no_provenance_or_text_leak"] = (
        "provenance" not in str(diag) and "path" not in diag and
        "構造化診断の動作確認" not in str(diag))
    tampered = copy.deepcopy(x)
    tampered["dataset_b"][0]["diagnostic"]["verified_fact"] = True
    try:
        assess_exchange(tampered)
        checks["forged_fact_rejected"] = False
    except ValueError:
        checks["forged_fact_rejected"] = True
    missing = copy.deepcopy(x)
    missing["dataset_b"][0].pop("diagnostic")
    checks["legacy_backward_compatible"] = (
        assess_exchange(missing)["action"] == "DIAGNOSTIC_ONLY")
    if cha_dir is not None:
        runtime = _get_cha_runtime(cha_dir)
        r = runtime.execute_ski_query(
            {"source_sd": "CLAIM", "target_sd": "EVIDENCE",
             "question": "v0.14構造化応答の確認"},
            bridge_dir=str(Path(bridge_dir).resolve()), tmp_dir=str(root),
            native_path=str(source), predicate="support-pred")
        checks["real_cha_runtime_consumes_ski"] = (
            r["status"] == "FOUND" and r["ski_diagnostic_profile"] == PROFILE
            and r["verified_fact"] is False
            and r["human_approved"] is False
            and r["llm_inference_invoked"] is False)
    checks["source_unchanged"] = before == _digest(source)
    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "status": status,
        "scope": "real SKI Dataset B v0.14 profile; real LLM_TMP APIs; optional real LLM_CHA runtime adapter; synthetic fixture, no LLM model inference",
        "checks": {name: {"pass": passed} for name, passed in checks.items()},
        "source_sha256": before,
        "verified_fact": False,
        "approval_authenticated": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm-tmp-dir", required=True)
    parser.add_argument("--llm-cha-dir")
    parser.add_argument("--bridge-dir", default=".")
    parser.add_argument("--native", default="examples/llm_tmp_native_registry_v09.json")
    args = parser.parse_args()
    report = verify(args.llm_tmp_dir, args.native,
                    bridge_dir=args.bridge_dir, cha_dir=args.llm_cha_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
