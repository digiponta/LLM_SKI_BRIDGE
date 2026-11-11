"""Cross-repository v0.12 auto-SKI verification with real LLM_TMP APIs.

No model inference, training or persistent writes. The test fixture is
synthetic and should not be mistaken for the user's real Registry.
"""
import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


def get_cha_router(cha_dir):
    root = Path(cha_dir).resolve()
    path = root / "ski_auto_route_v012.py"
    if not path.is_file() or not (root / "ski_runtime_v011.py").is_file():
        raise FileNotFoundError("LLM_CHA_AUTO_ROUTE_NOT_FOUND")
    # When dynamically importing from the BRIDGE checkout, spec_from_file_location
    # does not put the companion LLM_CHA directory on sys.path. Unlike
    # 'python chat.py', the lazy 'from ski_runtime_v011 import ...' otherwise
    # raises ModuleNotFoundError and auto_route returns its fail-closed ERROR.
    # Only use the explicitly supplied, trusted local checkout directory.
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location("llm_cha_auto_v012", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify(cha_dir, tmp_dir, bridge_dir, native):
    original_hash = sha(native)
    module = get_cha_router(cha_dir)
    env = {
        "LLM_CHA_SKI_ENABLED": "1",
        "LLM_CHA_SKI_AUTO_ENABLED": "1",
        "LLM_CHA_SKI_BRIDGE_DIR": str(Path(bridge_dir).resolve()),
        "LLM_CHA_SKI_TMP_DIR": str(Path(tmp_dir).resolve()),
        "LLM_CHA_SKI_NATIVE": str(Path(native).resolve()),
        "LLM_CHA_SKI_PREDICATE": "support-pred",
    }
    cases = [
        ("exact_japanese", "主張の根拠を確認してください", "FOUND"),
        ("exact_question", "主張の根拠は何ですか？", "FOUND"),
        ("unresolved_reference", "それの根拠は？", "PASS_THROUGH"),
        ("ordinary_chat", "主張について雑談しましょう", "PASS_THROUGH"),
        ("other_topic", "その他の根拠は？", "PASS_THROUGH"),
        ("command", "/status", "PASS_THROUGH"),
    ]
    results = {}
    for name, utterance, expected in cases:
        result = module.auto_route(utterance, environ=env)
        actual = "PASS_THROUGH" if result is None else result["status"]
        passed = actual == expected
        if result is not None:
            passed = (passed and result["kind"] == "SKI_AUTO_DIAGNOSTIC"
                      and result["verified_fact"] is False
                      and result["allow_model_context"] is False)
        results[name] = {"expected": expected, "actual": actual, "pass": passed}
    disabled = dict(env, LLM_CHA_SKI_AUTO_ENABLED="0")
    result = module.auto_route("主張の根拠は？", environ=disabled)
    results["disabled"] = {"expected": "PASS_THROUGH",
                           "actual": "PASS_THROUGH" if result is None else result["status"],
                           "pass": result is None}
    unchanged = original_hash == sha(native)
    results["input_unchanged"] = {
        "expected": "UNCHANGED",
        "actual": "UNCHANGED" if unchanged else "CHANGED", "pass": unchanged}
    return {
        "status": "PASS" if all(v["pass"] for v in results.values()) else "FAIL",
        "scope": "real LLM_CHA auto router + actual local SKI Bridge + real LLM_TMP APIs; synthetic snapshot; no chat.py model inference",
        "checks": results,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--llm-cha-dir", required=True)
    p.add_argument("--llm-tmp-dir", required=True)
    p.add_argument("--bridge-dir", default=".")
    p.add_argument("--native", default="examples/llm_tmp_native_registry_v09.json")
    args = p.parse_args()
    result = verify(args.llm_cha_dir, args.llm_tmp_dir,
                    args.bridge_dir, args.native)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
