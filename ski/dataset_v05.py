"""SKI v0.5 NL dataset *subset* adapter, separate from experimental Evidence envelopes.

HASKI_DOC v0.5 specifies bare nonempty message arrays for Dataset A/B.
The v0.5 DIALOGUE/LEARNING addendum proposes dataset_type as *separate*
metadata; this adapter does not invent a new canonical wire format.
"""
import hashlib
import json
import uuid

FORMAT = "ski-natural-language-v0.5"
TYPES = frozenset(("DIALOGUE", "LEARNING"))
FORBIDDEN = frozenset(("embedding", "embeddings", "vector", "vectors", "tensor", "weights"))

def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())

def _digest_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def _canonical(dataset):
    return json.dumps(dataset, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def _no_vectors(value):
    if isinstance(value, dict):
        return not any(k in FORBIDDEN or not _no_vectors(v) for k, v in value.items())
    if isinstance(value, list):
        return all(_no_vectors(item) for item in value)
    return True

def new_message(source_llm, target_llm, source_sd_id, text, *,
                language="ja", message_id=None, parent_sd_id=None,
                derivation=None, **metadata):
    msg = {
        "format": FORMAT,
        "message_id": message_id or str(uuid.uuid4()),
        "source_llm": source_llm, "target_llm": target_llm,
        "source_sd_id": source_sd_id,
        "parent_sd_id": parent_sd_id, "language": language,
        "text": text, "text_sha256": _digest_text(text) if isinstance(text, str) else None,
        "derivation": derivation,
    }
    if set(metadata) & set(msg):
        raise ValueError("RESERVED_FIELD")
    msg.update(metadata)
    if not valid_message(msg):
        raise ValueError("INVALID_SKI_MESSAGE")
    return msg

def valid_message(msg):
    if not isinstance(msg, dict) or not _no_vectors(msg):
        return False
    if msg.get("format") != FORMAT:
        return False
    if not all(_nonempty(msg.get(k)) for k in (
        "message_id", "source_llm", "target_llm", "source_sd_id",
        "language", "text")):
        return False
    if msg["source_llm"] == msg["target_llm"]:
        return False
    if msg.get("text_sha256") != _digest_text(msg["text"]):
        return False
    parent = msg.get("parent_sd_id")
    derivation = msg.get("derivation")
    if parent is not None and not _nonempty(parent):
        return False
    if derivation is not None and not isinstance(derivation, dict):
        return False
    if isinstance(derivation, dict):
        for key in ("response_to_message_id", "source_sd_id"):
            if key in derivation and not _nonempty(derivation[key]):
                return False
    return True

def validate_dataset(messages, *, source_llm=None, target_llm=None, max_messages=1000):
    if type(max_messages) is not int or max_messages < 1:
        raise ValueError("INVALID_LIMIT")
    if not isinstance(messages, list) or not 1 <= len(messages) <= max_messages:
        raise ValueError("INVALID_DATASET")
    ids = set()
    for msg in messages:
        if not valid_message(msg):
            raise ValueError("INVALID_SKI_MESSAGE")
        if msg["message_id"] in ids:
            raise ValueError("DUPLICATE_MESSAGE_ID")
        ids.add(msg["message_id"])
        if ((source_llm is not None and msg["source_llm"] != source_llm)
                or (target_llm is not None and msg["target_llm"] != target_llm)):
            raise ValueError("WRONG_DIRECTION")
    return True

def dataset_digest(messages):
    validate_dataset(messages)
    return hashlib.sha256(_canonical(messages)).hexdigest()

def make_ack(messages, receiver_llm):
    validate_dataset(messages, target_llm=receiver_llm)
    return {
        "protocol": FORMAT,
        "receiver_llm": receiver_llm,
        "message_ids": [m["message_id"] for m in messages],
        "dataset_sha256": dataset_digest(messages),
    }

def verify_ack(messages, ack, receiver_llm):
    try:
        validate_dataset(messages, target_llm=receiver_llm)
    except ValueError:
        return False
    return (isinstance(ack, dict)
            and ack.get("protocol") == FORMAT
            and ack.get("receiver_llm") == receiver_llm
            and type(ack.get("message_ids")) is list
            and ack["message_ids"] == [m["message_id"] for m in messages]
            and ack.get("dataset_sha256") == dataset_digest(messages))

def validate_replies(sent, replies, *, allow_multiple=True):
    validate_dataset(sent)
    validate_dataset(replies)
    requests = {m["message_id"]: m for m in sent}
    counts = {}
    for reply in replies:
        ref = reply.get("derivation")
        if not isinstance(ref, dict):
            raise ValueError("MISSING_DERIVATION")
        request_id = ref.get("response_to_message_id")
        original = requests.get(request_id)
        if original is None:
            raise ValueError("UNKNOWN_CORRELATION")
        if (reply["source_llm"] != original["target_llm"]
                or reply["target_llm"] != original["source_llm"]
                or ref.get("source_sd_id") != original["source_sd_id"]
                or reply.get("parent_sd_id") != original["source_sd_id"]):
            raise ValueError("INVALID_LINEAGE")
        counts[request_id] = counts.get(request_id, 0) + 1
        if not allow_multiple and counts[request_id] > 1:
            raise ValueError("MULTIPLE_REPLIES")
    return True

def validate_metadata(meta, messages):
    """Dataset type is out-of-band, not embedded into the v0.5 message array."""
    validate_dataset(messages)
    if not isinstance(meta, dict) or meta.get("dataset_type") not in TYPES:
        raise ValueError("INVALID_DATASET_TYPE")
    if not _nonempty(meta.get("dataset_id")):
        raise ValueError("INVALID_DATASET_ID")
    if not _nonempty(meta.get("source_llm")) or not _nonempty(meta.get("target_llm")):
        raise ValueError("INVALID_PARTICIPANTS")
    validate_dataset(messages, source_llm=meta["source_llm"], target_llm=meta["target_llm"])
    if meta["dataset_type"] == "DIALOGUE":
        turns = meta.get("turns")
        if not isinstance(turns, list) or not turns:
            raise ValueError("INVALID_TURNS")
        ids = set()
        for turn in turns:
            if not isinstance(turn, dict) or not all(_nonempty(turn.get(k)) for k in (
                    "utterance_id", "speaker", "language", "text")):
                raise ValueError("INVALID_TURN")
            if turn["utterance_id"] in ids:
                raise ValueError("DUPLICATE_UTTERANCE_ID")
            ids.add(turn["utterance_id"])
            reply_to = turn.get("in_reply_to")
            if reply_to is not None and (reply_to not in ids or reply_to == turn["utterance_id"]):
                raise ValueError("INVALID_TURN_REFERENCE")
    else:
        examples = meta.get("examples")
        if not isinstance(examples, list) or not examples:
            raise ValueError("INVALID_EXAMPLES")
        ids = set()
        for example in examples:
            if not isinstance(example, dict) or not _nonempty(example.get("example_id")):
                raise ValueError("INVALID_EXAMPLE")
            if example["example_id"] in ids:
                raise ValueError("DUPLICATE_EXAMPLE_ID")
            ids.add(example["example_id"])
            for k in ("question", "answer"):
                v = example.get(k)
                if not isinstance(v, dict) or not _nonempty(v.get("language")) or not _nonempty(v.get("text")):
                    raise ValueError("INCOMPLETE_QA")
            # Received data MUST NOT be promoted to approved learning.
            if example.get("approval", "PENDING") not in ("PENDING", "REVIEW_REQUIRED", "REJECTED"):
                raise ValueError("UNSAFE_LEARNING_APPROVAL")
    if not _no_vectors(meta):
        raise ValueError("VECTOR_PAYLOAD_FORBIDDEN")
    return True
