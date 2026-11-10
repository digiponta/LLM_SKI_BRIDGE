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


## v0.3 — LLM_TMP real RelationGraph adapter (experimental)

`adapters/llm_tmp_real.py` accepts an actual `RelationGraph` instance from LLM_TMP's
`semantic_relation_graph_v035.py`. It calls `evidence_path` read-only and
converts the returned approved path into a validated SKI response. There is
no network transport, persistent registry access, or live model inference.

The canonical implementation was inspected on LLM_TMP branch
`feature/intent-sd-v0.3.2-proxy-approval`. The LLM_TMP checkout on disk must
contain `semantic_relation_graph_v035.py`.

### Run on Windows

```powershell
cd C:\Users\inoma\git\misc\LLM_SKI_BRIDGE
git fetch origin
git switch feature/llm-tmp-adapter-v0.3
git pull --ff-only
python -m unittest discover -s tests -v
python verify_llm_tmp_integration_v03.py --llm-tmp-dir C:\Users\inoma\git\misc\LLM_TMP
```

The opt-in integration script imports Python code from the explicitly supplied
local directory, so use only a trusted checkout. It constructs ephemeral,
synthetic in-memory relation nodes; it does not load or alter saved LLM_TMP
registries. The six scenarios cover approved paths, PENDING, REJECTED,
unknown nodes, visit budget and hop budget. There is no numerical pass claim
until the script runs in the user's environment.

**Important limit semantics:** LLM_TMP v0.35 returns `NOT_FOUND` when
`max_hops` truncates a search. This is not proof that no longer path exists.
`LIMIT_REACHED` preserves the visit-budget condition. The bridge deliberately
does not invent `DEPTH_LIMIT_REACHED` for the real backend.

Evidence links marked `APPROVED` remain `verified_fact=false` and
`human_approved=false` in the bridge response. A true claim needs separate
external verification. Next: canonical SKI schema mapping, provenance
attestation, live registry loading, and LLM_CHA runtime integration.
