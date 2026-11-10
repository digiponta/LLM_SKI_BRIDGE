# LLM_SKI_BRIDGE

Experimental **in-process** SKI evidence bridge between `LLM_CHA` (conversation) and `LLM_TMP` (semantic evidence). The adapters currently run **synthetic mocks**, not the actual LLM_CHA or LLM_TMP runtime. The bridge-v0.1-experimental message format is **not** the canonical SKI v0.5 / HASKI_DOC schema.

## Architecture

```text
LLM_CHA mock             SKI envelope                   LLM_TMP mock
 source/target SD --> EVIDENCE_REQUEST (id, budgets) --> graph query
 result           <-- EVIDENCE_RESPONSE (correlation, APPROVED path)
                              |
                      validation gate
```

## Windows validation

```powershell
cd C:\Users\inoma\git\misc\LLM_SKI_BRIDGE
python -m unittest discover -s tests -v
python -c "from adapters.llm_cha_mock import roundtrip; import json; print(json.dumps(roundtrip(), ensure_ascii=False, indent=2))"
```

No third-party Python packages are required.

## Experimental message contract

| Field | Request | Response |
| --- | --- | --- |
| `ski_version` | `bridge-v0.1-experimental` | same |
| `message_type` | `EVIDENCE_REQUEST` | `EVIDENCE_RESPONSE` |
| `message_id` | nonempty identifier | distinct nonempty identifier |
| `correlation_id` | — | matches request `message_id` |
| `sender / receiver` | `LLM_CHA / LLM_TMP` by default | reversed |
| `source_sd / target_sd` | required strings | same as request |
| `max_hops` | integer 0–5 | same as request |
| `max_visits` | positive integer | same as request |
| `status` | — | `FOUND`, `NOT_FOUND`, `UNKNOWN_NODE`, `LIMIT_REACHED`, `DEPTH_LIMIT_REACHED` |
| `path` | — | contiguous APPROVED SUPPORTED_BY edges if FOUND, otherwise null |
| `verified_fact / human_approved` | — | always false |

A zero-edge FOUND path is allowed only when source and target are identical. Nonempty FOUND paths must be contiguous from source to target, have no repeated nodes and stay within `max_hops`. Non-FOUND states must have `path=null`.

**FOUND only means structural evidence was retrieved. It does not confirm factual truth or human approval.** This bridge must not promote pending evidence automatically.

## Follow-on integration plan

1. Map experimental envelopes to the canonical SKI v0.5/HASKI_DOC format, preserving source semantic references, request/response matching, and origin identity without assuming shared embedding-vector coordinates.
2. Replace `MockTMP.search` with a read-only adapter to LLM_TMP Relation Graph / Evidence Topology, keeping approval provenance intact.
3. Integrate an LLM_CHA client with timeout, retry and idempotency/replay protection, and process-level tests.
4. Benchmark real evidence requests, unknown-node cases, search budgets, tampering and evidence-state mismatches. Preserve the mock regression suite.

Out of scope at this stage: real network transport, real model inference, weight training, cryptographic authentication, automatic approval, semantic-vector transfer, and factual verification.
