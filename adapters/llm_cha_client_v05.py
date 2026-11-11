"""Opt-in LLM_CHA-facing SKI sidecar, without importing/chat.py or changing models.

This is a transport/evidence handoff, NOT an LLM_CHA chat inference hook.
Calling code must decide whether/how to render evidence to the user.
"""
from ski.dataset_v05 import (
    new_message, validate_dataset, make_ack, verify_ack, validate_replies
)
from ski.message import request as evidence_request, validate_roundtrip


class CHAClient:
    def __init__(self, tmp_adapter):
        if not callable(getattr(tmp_adapter, "handle", None)):
            raise TypeError("EVIDENCE_ADAPTER_REQUIRED")
        self.tmp_adapter = tmp_adapter

    def exchange(self, text, *, source_sd, target_sd, language="ja",
                 max_hops=5, max_visits=2000):
        """Return validated SKI A/ACK/B and evidence; never a factual answer."""
        dataset_a = [new_message(
            "LLM_CHA", "LLM_TMP", source_sd, text, language=language)]
        validate_dataset(dataset_a, source_llm="LLM_CHA", target_llm="LLM_TMP")
        ack = make_ack(dataset_a, "LLM_TMP")
        if not verify_ack(dataset_a, ack, "LLM_TMP"):
            raise RuntimeError("ACK_FAILED")

        req = evidence_request(source_sd, target_sd, max_hops=max_hops,
                               max_visits=max_visits)
        resp = self.tmp_adapter.handle(req)
        if not validate_roundtrip(req, resp):
            raise RuntimeError("INVALID_EVIDENCE_ROUNDTRIP")
        status = resp["status"]
        # A status report only; never turn an APPROVED path into an asserted fact.
        report = {
            "FOUND": "承認済み関係の経路が見つかりました。事実の真偽は未検証です。",
            "NOT_FOUND": "指定した探索範囲では承認済み関係の経路を確認できませんでした。",
            "UNKNOWN_NODE": "指定されたSemantic IDを確認できませんでした。",
            "LIMIT_REACHED": "探索上限に達しました。関係の有無は未判定です。",
            "DEPTH_LIMIT_REACHED": "探索深さの上限に達しました。関係の有無は未判定です。",
        }[status]
        dataset_b = [new_message(
            "LLM_TMP", "LLM_CHA", target_sd, report, language=language,
            parent_sd_id=source_sd,
            derivation={"response_to_message_id": dataset_a[0]["message_id"],
                        "source_sd_id": source_sd},
            assessments={"verified_fact": False, "human_approved": False,
                         "evidence_status": status})]
        validate_replies(dataset_a, dataset_b, allow_multiple=False)
        # v0.14: the diagnostic is an explicit structured SKI Dataset B
        # field, not merely a local display string. It is still unverified.
        from ski.diagnostic_v014 import build_diagnostic
        dataset_b[0]["diagnostic"] = build_diagnostic(
            req, resp, dataset_a, dataset_b)
        return {
            "dataset_a": dataset_a,
            "ack": ack,
            "dataset_b": dataset_b,
            "evidence_request": req,
            "evidence_response": resp,
            "verification": {
                "structural_exchange_valid": True,
                "verified_fact": False,
                "human_approved": False,
                "llm_cha_inference_invoked": False,
            },
        }
