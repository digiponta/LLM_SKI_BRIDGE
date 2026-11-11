"""Fail-closed boundary for LLM_CHA use of SKI evidence.

APPROVED relation links establish neither factual truth nor authorization to
feed retrieved text to the LLM. All v0.5 sidecar outcomes are diagnostic only.
This module deliberately does not import chat.py, generate answers, train,
read/write a registry, or claim to invoke LLM_CHA's existing Truth Gate.
"""
from ski.dataset_v05 import validate_dataset, validate_replies, verify_ack
from ski.message import validate_roundtrip

_STATES = frozenset({
    "FOUND", "NOT_FOUND", "UNKNOWN_NODE",
    "LIMIT_REACHED", "DEPTH_LIMIT_REACHED",
})

_MESSAGES = {
    "FOUND": "承認済みEvidence関係を取得しました。事実の真偽は未検証です。",
    "NOT_FOUND": "指定範囲ではEvidence関係を確認できません。不存在の証明ではありません。",
    "UNKNOWN_NODE": "Semantic IDが未登録または不明です。確認が必要です。",
    "LIMIT_REACHED": "探索数の上限に達しました。追加探索が必要です。",
    "DEPTH_LIMIT_REACHED": "探索深度の上限に達しました。追加探索が必要です。",
}


def assess_exchange(exchange):
    """Return bounded, text-free decision suitable for diagnostics only.

    Raises ValueError on invalid data. No external-sourced sentence or relation
    attribute is allowed into an LLM prompt via this return object.
    """
    if not isinstance(exchange, dict):
        raise ValueError("INVALID_EXCHANGE")
    try:
        a = exchange["dataset_a"]
        b = exchange["dataset_b"]
        ack = exchange["ack"]
        req = exchange["evidence_request"]
        resp = exchange["evidence_response"]
        verification = exchange["verification"]
    except KeyError as exc:
        raise ValueError("MISSING_EXCHANGE_FIELD") from exc
    validate_dataset(a, source_llm="LLM_CHA", target_llm="LLM_TMP")
    validate_dataset(b, source_llm="LLM_TMP", target_llm="LLM_CHA")
    if len(a) != 1 or len(b) != 1:
        raise ValueError("INVALID_MESSAGE_COUNT")
    if not verify_ack(a, ack, "LLM_TMP"):
        raise ValueError("ACK_MISMATCH")
    validate_replies(a, b, allow_multiple=False)
    if not validate_roundtrip(req, resp):
        raise ValueError("EVIDENCE_ENVELOPE_INVALID")
    if (req["sender"] != "LLM_CHA" or req["receiver"] != "LLM_TMP"
            or a[0]["source_sd_id"] != req["source_sd"]
            or b[0]["source_sd_id"] != req["target_sd"]
            or b[0]["parent_sd_id"] != req["source_sd"]):
        raise ValueError("CROSS_PROTOCOL_MISMATCH")
    if not isinstance(verification, dict):
        raise ValueError("INVALID_VERIFICATION")
    if (verification.get("structural_exchange_valid") is not True
            or verification.get("verified_fact") is not False
            or verification.get("human_approved") is not False
            or verification.get("llm_cha_inference_invoked") is not False):
        raise ValueError("UNSAFE_VERIFICATION_CLAIM")
    assessment = b[0].get("assessments")
    if (not isinstance(assessment, dict)
            or assessment.get("verified_fact") is not False
            or assessment.get("human_approved") is not False
            or assessment.get("evidence_status") != resp.get("status")):
        raise ValueError("ASSESSMENT_MISMATCH")
    status = resp.get("status")
    if status not in _STATES:
        raise ValueError("UNKNOWN_STATUS")
    # Crucially, the decision contains no source text or edge content.
    return {
        "action": "DIAGNOSTIC_ONLY",
        "evidence_status": status,
        "display_message": _MESSAGES[status],
        "allow_model_context": False,
        "allow_answer_from_evidence": False,
        "allow_learning": False,
        "allow_truth_promotion": False,
        "truth_state": "UNVERIFIED",
        "reason": "SKI_RELATION_IS_NOT_FACT_VERIFICATION",
        "request_message_id": a[0]["message_id"],
        "response_to_message_id": b[0]["derivation"]["response_to_message_id"],
    }
