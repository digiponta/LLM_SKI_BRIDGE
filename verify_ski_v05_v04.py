"""Smoke verification for the SKI v0.5 data exchange subset; no real LLM inference."""
import json

from ski.dataset_v05 import (
    new_message, validate_dataset, make_ack, verify_ack,
    validate_replies, validate_metadata,
)


def run():
    a = new_message("LLM_CHA", "LLM_TMP", "CHA-SD-01", "化学組成を知りたい",
                    message_id="CHA-MSG-01")
    messages_a = [a]
    ack = make_ack(messages_a, "LLM_TMP")
    b = new_message(
        "LLM_TMP", "LLM_CHA", "TMP-SD-01", "質問対象の確認が必要です。",
        message_id="TMP-MSG-01", parent_sd_id="CHA-SD-01",
        derivation={"response_to_message_id": a["message_id"],
                    "source_sd_id": a["source_sd_id"]},
        provenance={"source": "synthetic-v04-smoke"},
        assessments={"truth": "UNVERIFIED"})
    dialogue = {
        "dataset_id": "demo-dialogue-01", "dataset_type": "DIALOGUE",
        "source_llm": "LLM_CHA", "target_llm": "LLM_TMP",
        "turns": [{"utterance_id": "u01", "speaker": "USER",
                   "language": "ja", "text": "化学組成を知りたい"}],
    }
    checks = {
        "dataset_a": validate_dataset(messages_a),
        "ack": verify_ack(messages_a, ack, "LLM_TMP"),
        "dataset_b": validate_dataset([b]),
        "roundtrip": validate_replies(messages_a, [b]),
        "dialogue_metadata": validate_metadata(dialogue, messages_a),
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL",
            "scope": "synthetic SKI v0.5 subset; no model invocation",
            "checks": checks, "ack": ack,
            "reply_correlation": b["derivation"]["response_to_message_id"]}


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["status"] != "PASS":
        raise SystemExit(1)
