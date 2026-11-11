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


## v0.4 — SKI v0.5 dataset subset

Source specification: HASKI_DOC branch `v0.5`,
`docs/SKI_v0.5_Semantic_Dataset_Roundtrip_Interchange_ja.md`, plus
`docs/SKI_v0.5_Dialogue_and_Learning_Datasets_ja.md`.

`ski/dataset_v05.py` adds a **separate** natural-language SKI message-array
API without changing existing experimental `ski/message.py` evidence envelopes.

- `new_message(...)`: `ski-natural-language-v0.5` messages with UTF-8 SHA-256.
- `validate_dataset(messages)`: bounded nonempty array, unique message IDs and direction.
- `make_ack(messages, receiver_llm)`/`verify_ack(...)`: separate delivery receipt
  with canonical JSON dataset hash; **not** an interpretation/approval receipt.
- `validate_replies(dataset_a, dataset_b)`: B→A direction, parent SD,
  response_to_message_id and source SD correlation. Multiple replies opt-in.
- `validate_metadata(metadata, messages)`: DIALOGUE turn references or
  LEARNING question/answer pairs; out-of-band `dataset_type` (not inserted
  into a v0.5 message), with incoming learning approval never promoted.
- Embeddings and model vectors are not transmitted.

### Windows regression

```powershell
cd C:\Users\inoma\git\misc\LLM_SKI_BRIDGE
git fetch origin
git switch feature/ski-v05-datasets-v0.4
git pull --ff-only
python -m unittest discover -s tests -v
python verify_llm_tmp_integration_v03.py --llm-tmp-dir C:\Users\inoma\git\misc\LLM_TMP
```

**Scope boundaries:** This is a conservative **subset** of the SKI v0.5
proposal, not complete normative conformance. It does not implement actual
LLM_CHA runtime hooks, authenticated network delivery, persistent replicas,
replay-resistant sender authentication, full lifecycle/retraction,
semantic quality verification or training. Out-of-order dialogue references
are not handled in this subset. Source SHA-256 prevents accidental corruption,
not maliciously recomputed hashes. The user's local validation is required
before reporting test success.


## v0.5 — LLM_CHA-facing SKI sidecar (opt-in, no model inference)

`adapters/llm_cha_client_v05.py` provides `CHAClient.exchange(text, source_sd=..., target_sd=...)`.
It converts the input to SKI v0.5 Dataset A, generates and verifies an independent
ACK, calls `LLM_TMPAdapter.handle()` through the existing experimental evidence
envelope, validates the correlated Dataset B, and returns **structured data**.
No model-generated answer, human approval, registration, or learning is performed.

This is deliberately **not** yet a change to LLM_CHA's `chat.py` or
`chat_gui.py`; LLM_CHA v0.14.0 has a substantial existing runtime and should
not be patched or have truth gates bypassed without a dedicated integration
test. Existing LLM_CHA logic can consume the returned structured result at a
subsequent stage. Evidence status strings are descriptions of *retrieval*,
not proof of factual truth.

Run on Windows from this repository:

```powershell
git fetch origin
git switch feature/llm-cha-client-v0.5
git pull --ff-only
python -m unittest discover -s tests -v
python verify_cha_handoff_v05.py --llm-tmp-dir C:\Users\inoma\git\misc\LLM_TMP
python verify_llm_tmp_integration_v03.py --llm-tmp-dir C:\Users\inoma\git\misc\LLM_TMP
python verify_ski_v05_v04.py
```

The handoff demonstration invokes the **real local LLM_TMP RelationGraph class**
but uses **synthetic ephemeral graph data**; it never invokes a trained LLM,
loads existing semantic memory, or changes model/data files.

**Upcoming v0.6:** integrate with a reviewed LLM_CHA runtime extension point,
map actual local SD IDs, add provenance/authentication and replay protection,
and measure end-to-end semantic quality independently of transport validity.


## v0.6 — opt-in console with actual LLM_CHA/chat.py process

`run_cha_ski_console_v06.py` launches the existing `LLM_CHA/chat.py`
as a child process (Python unbuffered; its stdout remains visible). Ordinary
user text is forwarded unchanged to that real process. A separate explicit
`/ski SOURCE_SD TARGET_SD | question` command sends a read-only SKI
evidence lookup to the real LLM_TMP RelationGraph class, using the
`CHAClient` v0.5 sidecar. **/ski does not invoke the LLM or inject evidence
into its context.** It prints a separate machine-readable diagnostic and
never asserts the query result is factual truth.

The real LLM_CHA model can run for ordinary chat *if the user has all local
dependencies and model checkpoints installed*. The SKI graph may optionally
come from a user-provided, trusted, local JSON file with `nodes` and
`relations`. Such a file is loaded only into an ephemeral in-memory graph.
No existing Semantic Registry is connected automatically; no files in
LLM_CHA or LLM_TMP are rewritten.

### Windows steps

```powershell
cd C:\Users\inoma\git\misc\LLM_SKI_BRIDGE
git fetch origin
git switch feature/llm-cha-console-v0.6
git pull --ff-only
python -m unittest discover -s tests -v

# Only SKI diagnostics, without launching the LLM:
python run_cha_ski_console_v06.py `
  --llm-cha-dir C:\Users\inoma\git\misc\LLM_CHA `
  --llm-tmp-dir C:\Users\inoma\git\misc\LLM_TMP `
  --graph-file examples/ski_graph_v06.json `
  --no-chat

# To additionally launch the actual LLM_CHA/chat.py, remove --no-chat.
```

At the `CHA/SKI>` prompt:

```text
/ski CHA-CLAIM TMP-EVIDENCE | 根拠を確認してください
/ski CHA-CLAIM TMP-PENDING | 根拠を確認してください
/ski CHA-CLAIM MISSING | 根拠を確認してください
量子力学とは
/status
/exit
```

Expected synthetic statuses are FOUND, NOT_FOUND and UNKNOWN_NODE
respectively. `量子力学とは` and `/status` are sent to the actual chat
process when started; `/exit` closes the console and child process.

The demo JSON contains **synthetic, unauthenticated** approvals. The result
remains `verified_fact: false`, even for FOUND. Do not expose this CLI
on a network or treat arbitrary external JSON as verified evidence.

### v0.6 boundaries

- Actual `LLM_CHA/chat.py` is launched for ordinary user input, but is
  not modified; the existing truth/unknown gates remain in control.
- The explicit `/ski` query is a separate diagnostic, not automatic
  chat-context resolution, semantic alignment or answer generation.
- There is no model-generated response based on SKI evidence yet.
- There is no source authentication, real persistent Replica Registry,
  production network transport, or proof of semantic equivalence.
- A future opt-in GUI or verified runtime-hook integration requires
  dedicated testing and a review of the existing LLM_CHA truth policies.


## v0.7 — SKI evidence / LLM_CHA truth-boundary isolation

`adapters/cha_truth_boundary_v07.py` adds a fail-closed,
**read-only protocol boundary** to check the full v0.5 `CHAClient.exchange()`
result before any consumer considers using it.

The boundary verifies:
- Dataset A/B message directions, nonempty arrays, and SHA-256 digests;
- ACK receipt hash and IDs, answer correlation and local-SD lineage;
- experimental evidence-envelope pairing and approved contiguous path;
- cross-protocol source/target SD IDs;
- that verification and response assessments explicitly remain unverified.

Every valid evidence outcome—including FOUND—returns:
`action=DIAGNOSTIC_ONLY`, `truth_state=UNVERIFIED`, and
`allow_model_context=false`, `allow_answer_from_evidence=false`,
`allow_learning=false`, `allow_truth_promotion=false`.
The decision never exposes user-provided text or untrusted edge descriptions.

**This boundary is not the existing internal LLM_CHA Truth Gate** and does not
patch `chat.py` or `chat_gui.py`. It prevents unauthorized promotion; it
does not yet implement the separate verified-input policy needed for prompt
injection/answer generation. Arbitrary `APPROVED` attributes supplied through
local graph JSON remain unauthenticated and do not confer authority.

### Windows v0.7 validation

```powershell
cd C:\Users\inoma\git\misc\LLM_SKI_BRIDGE
git fetch origin
git switch feature/evidence-truth-boundary-v0.7
git pull --ff-only
python -m unittest discover -s tests -v
python verify_truth_boundary_v07.py `
  --llm-tmp-dir C:\Users\inoma\git\misc\LLM_TMP
python verify_cha_handoff_v05.py `
  --llm-tmp-dir C:\Users\inoma\git\misc\LLM_TMP
```

The target suite contains 62 test methods (previous 50 plus 12 v0.7 cases);
this is an expected count, **not a claim of execution**.

Next: map LLM_CHA's actual truth classifications and the stored Registry
to an explicitly reviewed, provenance-aware policy, under independent tests.
Do not auto-feed a FOUND path or unreviewed external source to model context.


## v0.8 — strict read-only LLM_TMP RelationGraph snapshot importer

The public LLM_TMP branch `feature/intent-sd-v0.3.2-proxy-approval` exposes
`semantic_relation_graph_v035.py` as an in-memory graph, while
`benchmark_sd_registry_v034.py` uses a **synthetic benchmark-only**
adjacency index. A stable persistent RelationGraph registry reader is not
established in that code. Therefore this version **does not silently assume
that an arbitrary LLM_TMP registry JSON is compatible**.

`adapters/llm_tmp_registry_v08.py` defines a strict, explicitly versioned
bridge **snapshot interchange profile**, `ski-relation-snapshot-v0.8`.
The JSON has exactly: `format`, `snapshot_id`,
`source_system=LLM_TMP`, `nodes[]` (local SD IDs), and
`relations[]` (directed edge records). Relation fields are exactly
`source`, `kind`, `target`, `state`, `evidence_id`, `provenance`.
An APPROVED edge requires traceable nonempty `evidence_id` and
`provenance`. This is **not authentication or proof of truth**.
PENDING and REJECTED edges remain non-usable for approved evidence paths.

The loader rejects duplicate JSON object keys, duplicate SD IDs, unknown
endpoints, duplicate edges, unrecognized relation kinds/states, malformed
or ambiguous metadata, and oversized files. The input file is only opened
for reading and its raw SHA-256 is returned. The parsed graph is newly
constructed in memory; no registry, model or training state is modified.

### Windows validation

```powershell
cd C:\Users\inoma\git\misc\LLM_SKI_BRIDGE
git fetch origin
git switch feature/registry-import-v0.8
git pull --ff-only
python -m unittest discover -s tests -v
python verify_registry_import_v08.py `
  --llm-tmp-dir C:\Users\inoma\git\misc\LLM_TMP `
  --snapshot examples/llm_tmp_snapshot_v08.json
```

Expected tests: 74 methods (previous 62 plus 12 new ones). The integration
program checks APPROVED / PENDING / REJECTED / UNKNOWN through the real
LLM_TMP graph class, the SKI v0.5 handoff and the v0.7 fail-closed boundary.
The example contains deliberately synthetic, unauthenticated evidence.

**Important:** To work with an actual saved LLM_TMP registry in a future
version, first document its real schema and create an explicit, audited,
read-only exporter to this profile. Never reinterpret an unrelated
`linked_sd_registry_dev.json` or a synthetic benchmark report as an
approved relation registry. The v0.8 loader does not prove that imported
APPROVED markers were issued by a trusted reviewer; the returned metadata
contains `approval_authenticated=false` and `verified_fact=false`.


## v0.9 — native LLM_TMP Intent SD v0.3 snapshot conversion

Inspected actual LLM_TMP code on
`feature/intent-sd-v0.3.2-proxy-approval`:
`intent_sd_context_v03.py` defines `SDRegistry`, a frozen read-only
JSON format with `namespace`, `snapshot_id`, `nodes[]` and optional
GUI `display_names`. A RELATION SD node includes `predicate_ref`,
`source_ref`, `target_ref`, `validation_state`, and `evidence_id`.
This is a **context/topic relation graph**, not automatically a factual
Evidence Graph. `linked_sd_annotation_v031.py` also consumes this format.

`adapters/llm_tmp_native_v09.py` reads a native snapshot without
modifying it, validates it using the **real trusted local SDRegistry
implementation**, then converts it to the strictly validated v0.8
snapshot profile.

**Safety boundary:** By default **zero relations are exported**.
A caller may explicitly allowlist a predicate SD ID that is intended
to mean `SUPPORTED_BY`. Only relations with that exact predicate
and `validation_state=APPROVED` are exported; PENDING/REJECTED and
all other predicates are excluded. The converter makes no assertion
that the allowed predicate really encodes evidence semantics: this
requires separately reviewed mapping. It does not authenticate
the approval, the evidence ID, or provenance.

### Windows verification (synthetic native fixture)

```powershell
cd C:\Users\inoma\git\misc\LLM_SKI_BRIDGE
git fetch origin
git switch feature/native-sd-registry-v0.9
git pull --ff-only
python -m unittest discover -s tests -v

# Default-deny: no relation mapping -> NOT_FOUND
python verify_native_registry_v09.py `
  --llm-tmp-dir C:\Users\inoma\git\misc\LLM_TMP `
  --native examples/llm_tmp_native_registry_v09.json

# Explicit synthetic demonstration: mapping -> FOUND
python verify_native_registry_v09.py `
  --llm-tmp-dir C:\Users\inoma\git\misc\LLM_TMP `
  --native examples/llm_tmp_native_registry_v09.json `
  --supported-by-predicate support-pred
```

Expected suite: 86 tests (74 existing + 12 new). The two integration
runs should return NOT_FOUND and FOUND respectively, with
`approval_authenticated=false` and `verified_fact=false`.
These are expected outcomes, not claims of executed tests.

For real local files, use the actual `SDRegistry` frozen JSON format;
do not use a benchmark report or the v0.8 synthetic relation
snapshot as native input. An explicitly approved predicate mapping
is still a hypothesis to evaluate, not proof of factual truth.


## v0.10 — read-only audit of native LLM_TMP SD Registry

`adapters/native_registry_audit_v010.py` inspects native frozen
`intent_sd_context_v03.SDRegistry` JSON supplied explicitly as a local
file. Its companion `audit_native_registry_v010.py` prints a JSON report
**to stdout only**; neither input nor any Registry/LLM state is changed.

The audit records node counts by SD kind; relations grouped by
`validation_state` and predicate SD ID; Evidence ID coverage and
repeat usage; exact mapping-eligible counts; and exclusions for
unallowlisted predicates and unapproved states. No source expressions,
display names, conversation transcripts, or Evidence text are exported.

Mapping remains **default deny**: `--supported-by-predicate` must explicitly
identify each existing predicate SD ID to treat as `SUPPORTED_BY`.
The validator uses LLM_TMP's real local `SDRegistry` class for topology
validation. The audit then invokes the v0.9 conversion separately and
compares both source SHA-256 and eligible/exported relation counts.

### Windows verification

```powershell
cd C:\Users\inoma\git\misc\LLM_SKI_BRIDGE
git fetch origin
git switch feature/native-registry-audit-v0.10
git pull --ff-only
python -m unittest discover -s tests -v

# Audit a synthetic native registry, without allowing evidence mapping
python audit_native_registry_v010.py `
  --llm-tmp-dir C:\Users\inoma\git\misc\LLM_TMP `
  --native examples/llm_tmp_native_registry_v09.json

# Audit explicit synthetic SUPPORT mapping
python audit_native_registry_v010.py `
  --llm-tmp-dir C:\Users\inoma\git\misc\LLM_TMP `
  --native examples/llm_tmp_native_registry_v09.json `
  --supported-by-predicate support-pred
```

Expected regression suite: **98 tests** (previous 86 + 12 new), subject
to actual Windows execution. The demo has 3 topic/concept/entity SD
nodes, 2 predicate SD nodes and 2 relation SD nodes (7 total). The
default audit reports **zero** eligible mappings; the explicitly mapped
audit reports **one** eligible mapping. The files are still synthetic.

To examine an **actual local frozen Intent SD registry**, replace
`--native` with its existing absolute JSON path. Avoid assuming a
benchmark results JSON or annotations packet is a compatible SDRegistry
snapshot. If the requested file is not in that known schema, the tool
rejects it rather than guessing its meaning.

**Security boundary:** `APPROVED` on a relation means the stored
label says approved, not that its authority or factual truth was verified.
`semantic_mapping_reviewed=false`, `approval_authenticated=false`,
`verified_fact=false`, and `allow_model_context=false` remain in
the report; no truth promotion or model learning occurs. The
`--llm-tmp-dir` argument must refer to a trusted local Python checkout
because the interface intentionally loads its module for validation.


## v0.11 — direct in-process integration into LLM_CHA's real chat.py

Companion branch in `digiponta/LLM_CHA`:
`feature/ski-runtime-integration-v0.11`.
Unlike the v0.6 detached console, this branch **adds an actual
`/ski` dispatch hook to the LLM_CHA v0.14.0 `chat.py` input loop**.
The hook consumes explicit SKI commands before any model, learning
or semantic routes. Normal dialogue is not intercepted.

The hook calls the v0.9 native registry converter, v0.5 CHAClient
and v0.7 fail-closed Truth Boundary in this repository, plus
LLM_TMP's actual trusted local SDRegistry/RelationGraph modules.
The result is a separate evidence diagnostic, **not a model answer**
and not proof of factual truth.

To validate the **actual three-repository handoff**, check out the
corresponding LLM_CHA branch and execute:

```powershell
cd C:\Users\inoma\git\misc\LLM_SKI_BRIDGE
git fetch origin
git switch feature/cha-runtime-contract-v0.11
git pull --ff-only
python -m unittest discover -s tests -v
python verify_cha_runtime_hook_v011.py `
  --llm-cha-dir C:\Users\inoma\git\misc\LLM_CHA `
  --llm-tmp-dir C:\Users\inoma\git\misc\LLM_TMP
```

The verifier dynamically loads the actual LLM_CHA hook (without
loading the trained `chat.py` model) and exercises:
default-deny `NOT_FOUND`, explicit synthetic predicate mapping
`FOUND`, missing Semantic ID `UNKNOWN_NODE`, disabled mode,
normal-chat pass-through, and input file immutability. It uses the
synthetic native sample already present in `examples/`, not the
user's production Registry.

See `LLM_CHA/SKI_RUNTIME_V011.md` on the companion branch for
PowerShell environment variables and the commands that exercise
the actual running `chat.py`.

**Verification status:** code committed; the user's local Windows
regression and model-startup tests for v0.11 are not yet observed.


## v0.12 — opt-in natural-language routing from the real LLM_CHA chat loop

Companion LLM_CHA branch:
`feature/ski-auto-router-v0.12`.
The chat.py loop now also calls `ski_auto_route_v012.py` for normal
Japanese user inputs when both `LLM_CHA_SKI_ENABLED=1` and
`LLM_CHA_SKI_AUTO_ENABLED=1`.

The router recognizes a narrow, literal form: a single native
`display_names` value followed by a Japanese evidence-request ending.
It requires exactly one approved relation target after explicit
`LLM_CHA_SKI_PREDICATE` mapping, then uses the existing v0.11
real SKI diagnostic path. Ambiguous, unrelated or disabled inputs
pass through to ordinary chat without an SKI result.

It is *not* semantic intent inference by the LLM and does not feed
evidence into model prompts, verify factual truth, or learn.
See `LLM_CHA/SKI_AUTO_ROUTE_V012.md` for setup.

To validate with the real local LLM_TMP SDRegistry/RelationGraph
implementations (using only the **synthetic** native fixture):

```powershell
cd C:\Users\inoma\git\misc\LLM_SKI_BRIDGE
git fetch origin
git switch feature/cha-auto-router-v0.12
git pull --ff-only
python -m unittest discover -s tests -v
python verify_cha_auto_route_v012.py `
  --llm-cha-dir C:\Users\inoma\git\misc\LLM_CHA `
  --llm-tmp-dir C:\Users\inoma\git\misc\LLM_TMP
```

Expected: 98 existing Bridge tests and eight new runtime verification
scenarios; these expectations are not yet Windows execution evidence.


### v0.12 integration verifier import-path fix

After the first v0.12 Windows evaluation the Bridge suite passed (98/98)
and the **actual** LLM_CHA `python chat.py` automatic query returned FOUND.
However `verify_cha_auto_route_v012.py` reported ERROR on matching
phrases because it dynamically loaded `ski_auto_route_v012.py` from
another directory without registering the companion LLM_CHA path.
The auto-router's lazy `import ski_runtime_v011` therefore failed in
that verifier process. This is a **harness import-path issue**, not
evidence that `chat.py` failed in the observed live run.

The verifier now registers its explicitly supplied, trusted local
`--llm-cha-dir` before loading the hook. Added 2 unit regressions in
`tests/test_cha_auto_import_v012.py`.

Re-check in Windows:

```powershell
cd C:\Users\inoma\git\misc\LLM_SKI_BRIDGE
git switch feature/cha-auto-router-v0.12
git pull --ff-only
python -m unittest discover -s tests -v
python verify_cha_auto_route_v012.py `
  --llm-cha-dir C:\Users\inoma\git\misc\LLM_CHA `
  --llm-tmp-dir C:\Users\inoma\git\misc\LLM_TMP
```

Expected Bridge test count after fix: **100**. Run the cross-repository
verifier again to confirm eight checked cases; those test results have
not yet been observed after this fix.


## v0.13 — real LLM_CHA multi-turn Semantic Context → SKI diagnostic

Companion `LLM_CHA` branch:
`feature/ski-context-v0.13`. The actual LLM_CHA `chat.py` now
maintains a separate session-local source SD pointer for *bounded*
context references such as `その根拠は？`. It stores no third-party
evidence in the prompt and never trains or promotes truth from SKI.

The source SD is selected only from an **explicit and unique** native
Registry display name having exactly one approved, explicitly mapped
`SUPPORTED_BY` target. The valid reference window is at most two
subsequent user turns; ambiguous competing topics and the `/reset`
command erase it. The real local LLM_TMP `context_intent_resolver_v033.py`
is used for a limited **multi-topic/attribute ambiguity veto**,
not to infer a generalized factual Evidence relation.

### Windows verification

```powershell
cd C:\Users\inoma\git\misc\LLM_CHA
git fetch origin
git switch feature/ski-context-v0.13
git pull --ff-only
python -m unittest -v test_ski_runtime_v011.py test_ski_auto_route_v012.py test_ski_context_route_v013.py

cd C:\Users\inoma\git\misc\LLM_SKI_BRIDGE
git fetch origin
git switch feature/cha-context-v0.13
git pull --ff-only
python -m unittest discover -s tests -v
python verify_cha_context_v013.py `
  --llm-cha-dir C:\Users\inoma\git\misc\LLM_CHA `
  --llm-tmp-dir C:\Users\inoma\git\misc\LLM_TMP
```

Expected: LLM_CHA **46 focused tests**; SKI Bridge **102 tests**
(previous 100 plus 2 new); integration **14 scenarios**. These are
expected counts, not execution results.

The sample is synthetic. The actual v0.33 Context Intent Resolver has
a limited hardcoded topic/attribute vocabulary and is only a secondary
fail-closed check; v0.13 does not implement universal pronoun resolution,
model-grounded answers, real-source provenance authentication, or
cross-host SKI transport.

### Windows follow-up: synthetic display-name fixture mismatch

The real sample `examples/llm_tmp_native_registry_v09.json` contains:
`display_names.CLAIM="主張"`, `display_names.OTHER="別話題"`.
The v0.13 integration verifier previously used `その他` for OTHER,
so its `unmapped_topic` and `two_topics` checks never named the actual
SECOND SD node. The corrected verifier reads display names from the
native JSON file and requires nonempty, distinct labels. It uses those
literal labels in the two test scenarios. Three new regression tests
check successful label extraction and malformed/duplicate labels.

After the change, the expected Bridge unit count is **105** (102+3);
the v0.13 cross-repo verifier still checks **14** scenarios.
LLM_CHA separately fixed its `printer()` callback usage in all three
diagnostic functions; the focused LLM_CHA test count stays **49**.
Windows verification of this combined patch is pending.
