"""LLM_CHA v0.11 real runtime-hook smoke using local checked-out repositories.

Loads actual local ski_runtime_v011.py (not the large chat.py) and the real
LLM_TMP SDRegistry/RelationGraph APIs. Synthetic fixture. Never runs model,
trains, mutates registry or sends evidence to LLM context.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


def load_cha_hook(cha_dir):
    path = Path(cha_dir).resolve() / "ski_runtime_v011.py"
    if not path.is_file():
        raise FileNotFoundError("LLM_CHA_SKI_HOOK_NOT_FOUND")
    spec = importlib.util.spec_from_file_location("llm_cha_ski_runtime_v011", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(cha_dir, tmp_dir, bridge_dir, native_path):
    path = Path(native_path).resolve()
    before = digest(path)
    runtime = load_cha_hook(cha_dir)
    base = {
        "LLM_CHA_SKI_ENABLED": "1",
        "LLM_CHA_SKI_BRIDGE_DIR": str(Path(bridge_dir).resolve()),
        "LLM_CHA_SKI_TMP_DIR": str(Path(tmp_dir).resolve()),
        "LLM_CHA_SKI_NATIVE": str(path),
    }
    outcomes = {}
    for name, predicate, target, expected in (
        ("default_deny", "", "EVIDENCE", "NOT_FOUND"),
        ("explicit_allowlist", "support-pred", "EVIDENCE", "FOUND"),
        ("unknown_sd", "support-pred", "MISSING-SD-ID", "UNKNOWN_NODE"),
    ):
        env = dict(base, LLM_CHA_SKI_PREDICATE=predicate)
        result = runtime.handle_ski_input(
            "/ski CLAIM " + target + " | Semantic関係の状態を確認",
            environ=env)
        outcomes[name] = {
            "status": result["status"],
            "expected": expected,
            "pass": result["status"] == expected
                    and result.get("verified_fact") is False
                    and result.get("human_approved") is False
                    and result.get("llm_inference_invoked") is False
                    and result.get("request_message_id") ==
                        result.get("response_to_message_id"),
        }
    disabled = runtime.handle_ski_input(
        "/ski CLAIM EVIDENCE | 質問", environ={})
    normal = runtime.handle_ski_input(
        "スファレライトの成分は？", environ=base)
    outcomes["disabled"] = {
        "status": disabled["status"], "expected": "DISABLED",
        "pass": disabled["status"] == "DISABLED",
    }
    outcomes["normal_chat"] = {
        "status": "UNCHANGED" if normal is None else "INTERCEPTED",
        "expected": "UNCHANGED", "pass": normal is None,
    }
    after = digest(path)
    outcomes["file_unchanged"] = {
        "status": "UNCHANGED" if before == after else "MODIFIED",
        "expected": "UNCHANGED", "pass": before == after,
    }
    passed = all(v["pass"] for v in outcomes.values())
    return {
        "status": "PASS" if passed else "FAIL",
        "scope": "real local LLM_CHA SKI hook + real SKI Bridge + real LLM_TMP APIs; synthetic native SD snapshot; no chat.py model inference",
        "checks": outcomes,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm-cha-dir", required=True)
    parser.add_argument("--llm-tmp-dir", required=True)
    parser.add_argument("--bridge-dir", default=".")
    parser.add_argument("--native", default="examples/llm_tmp_native_registry_v09.json")
    args = parser.parse_args()
    output = verify(args.llm_cha_dir, args.llm_tmp_dir, args.bridge_dir,
                    args.native)
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if output["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
