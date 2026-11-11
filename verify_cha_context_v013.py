"""Three-repository v0.13 multi-turn Semantic context integration smoke.

Loads actual LLM_CHA context module, actual local LLM_TMP context resolver,
SDRegistry, RelationGraph, and SKI Bridge. Uses a synthetic native fixture.
This script never executes chat.py model inference or writes snapshot data.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def get_context_module(cha_dir):
    root = Path(cha_dir).resolve()
    path = root / "ski_context_route_v013.py"
    needed = ("ski_runtime_v011.py", "ski_auto_route_v012.py")
    if not path.is_file() or not all((root / name).is_file() for name in needed):
        raise FileNotFoundError("LLM_CHA_CONTEXT_MODULE_MISSING")
    # Resolve lazy sibling imports just as actual python chat.py does.
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    spec = importlib.util.spec_from_file_location("llm_cha_context_v013", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(module, env, turns, expectation):
    state = module.empty_context()
    diagnostic = None
    for utterance in turns:
        state, diagnostic = module.context_route(utterance, state, environ=env)
    actual = "PASS_THROUGH" if diagnostic is None else diagnostic["status"]
    passed = actual == expectation
    if diagnostic is not None:
        passed = (passed and diagnostic["kind"] == "SKI_CONTEXT_DIAGNOSTIC"
                  and diagnostic["verified_fact"] is False
                  and diagnostic["allow_model_context"] is False)
    return {"expected": expectation, "actual": actual, "pass": passed}


def verify(cha_dir, tmp_dir, bridge_dir, native):
    source = Path(native).resolve()
    before = digest(source)
    # Build language fixtures from the actual native Registry labels.
    # This prevents silent test drift when display_names changes.
    from adapters.llm_tmp_native_v09 import read_native
    snapshot, snapshot_sha = read_native(source)
    if snapshot_sha != before:
        raise ValueError("SNAPSHOT_CHANGED_DURING_VERIFICATION")
    display_names = snapshot.get("display_names", {})
    source_label = display_names.get("CLAIM")
    other_label = display_names.get("OTHER")
    if not all(isinstance(x, str) and x.strip() and x != sid
               for sid, x in (("CLAIM", source_label), ("OTHER", other_label))):
        raise ValueError("REQUIRED_TEST_DISPLAY_NAMES_MISSING")
    if source_label == other_label:
        raise ValueError("TEST_DISPLAY_NAMES_NOT_UNIQUE")
    module = get_context_module(cha_dir)
    env = {
        "LLM_CHA_SKI_ENABLED": "1",
        "LLM_CHA_SKI_AUTO_ENABLED": "1",
        "LLM_CHA_SKI_CONTEXT_ENABLED": "1",
        "LLM_CHA_SKI_BRIDGE_DIR": str(Path(bridge_dir).resolve()),
        "LLM_CHA_SKI_TMP_DIR": str(Path(tmp_dir).resolve()),
        "LLM_CHA_SKI_NATIVE": str(source),
        "LLM_CHA_SKI_PREDICATE": "support-pred",
    }
    examples = (
        ("explicit_then_followup",
         ("主張について教えて", "その根拠は？"), "FOUND"),
        ("short_followup",
         ("主張について教えて", "根拠は？"), "FOUND"),
        ("intervening_turn",
         ("主張について", "そうですね", "その根拠は？"), "FOUND"),
        ("no_context",
         ("その根拠は？",), "PASS_THROUGH"),
        ("expired",
         ("主張について", "はい", "そう", "なるほど", "その根拠は？"),
         "PASS_THROUGH"),
        ("unmapped_topic",
         (f"{source_label}について", f"{other_label}の話です", "その根拠は？"),
         "PASS_THROUGH"),
        ("two_topics",
         (f"{source_label}について", f"{source_label}と{other_label}について", "その根拠は？"),
         "PASS_THROUGH"),
        ("normal_chat",
         ("主張について", "こんにちは"), "PASS_THROUGH"),
        ("explicit_unrelated_question",
         ("主張について", "化学組成は？"), "PASS_THROUGH"),
    )
    results = {
        name: check(module, env, utterances, expected)
        for name, utterances, expected in examples
    }
    disabled = dict(env, LLM_CHA_SKI_CONTEXT_ENABLED="0")
    results["disabled"] = check(
        module, disabled, ("主張について", "その根拠は？"), "PASS_THROUGH")
    no_predicate = dict(env, LLM_CHA_SKI_PREDICATE="")
    results["no_predicate"] = check(
        module, no_predicate, ("主張について", "その根拠は？"),
        "PASS_THROUGH")
    results["reset"] = check(
        module, env, ("主張について", "/reset", "その根拠は？"),
        "PASS_THROUGH")
    # Test the actual v0.33 resolver ambiguity veto, without inventing
    # model-derived evidence or importing its context as factual truth.
    native_data = module._load_tmp_resolver(tmp_dir)
    tmp_result = native_data("スファレライトとダイヤモンドの硬度は？")
    results["real_tmp_ambiguity_veto"] = {
        "expected": "MULTIPLE_TOPICS",
        "actual": tmp_result.get("reason"),
        "pass": tmp_result.get("status") == "ABSTAIN"
                and tmp_result.get("reason") == "MULTIPLE_TOPICS",
    }
    after = digest(source)
    results["source_unchanged"] = {
        "expected": "UNCHANGED",
        "actual": "UNCHANGED" if after == before else "CHANGED",
        "pass": after == before,
    }
    return {
        "status": "PASS" if all(result["pass"] for result in results.values()) else "FAIL",
        "scope": "actual LLM_CHA v0.13 context module, actual LLM_TMP v0.33 resolver and Graph APIs, SKI Bridge; synthetic snapshot; no chat.py model inference",
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
