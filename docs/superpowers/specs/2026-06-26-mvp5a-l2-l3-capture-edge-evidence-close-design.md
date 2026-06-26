# MVP-5A L2/L3 Capture-Edge Evidence Close Design

Date: 2026-06-26 KST

Status: Specify

Branch context: `codex/mvp5a-runtime-evidence-contract`

## Problem

PR #12 defines a useful verifier-owned runtime event consistency contract, but
review found an important boundary hole:

```text
canonical_trace.json
-> build_runtime_event_log_from_trace()
-> runtime_event_log.jsonl
```

This helper projects already-derived canonical frames into event rows. That is
valid as a verifier development fixture, but it is not capture-edge evidence.

The current helper path can stamp:

```text
capture_script_id=mvp5a_pre_isaac_sim_raw_runtime_event_capture_v0
ready_status_allowed=true
```

on helper-derived event evidence. A verifier can prove that the event rows and
canonical trace are mutually consistent, but artifact consistency alone cannot
prove the direction of derivation. The same `(events, trace)` pair can be made
by a forward capture-edge emitter or by reverse projection from canonical trace.

Therefore `file_drop_rehearsal_ready=true` must not be opened by PR #12 as-is.
PR #12 should be treated as a consistency baseline, not a ready-close package.

## Goal

Close the MVP-5A-pre rehearsal ready boundary only through a non-circular
L2/L3 evidence path:

```text
capture-edge runtime event emitter
-> raw runtime_event_log.jsonl
-> process provenance receipt
-> verifier reconstruction
-> canonical trace
-> file-drop projections
-> normalized contracts
-> HDF5 / trainer smoke
-> TrustPack verdict
```

Target final status for the future close package:

```text
file_drop_rehearsal_contract_ready=true
file_drop_rehearsal_ready=true
```

Allowed claim:

```text
RDF can close a digital-twin file-drop rehearsal package when a blessed
capture-edge emitter produces raw runtime events, process provenance binds the
declared run identity, and the independent verifier reconstructs all closing
evidence from those events.
```

Forbidden claims:

```text
external_partner_data_evaluated
real_robot_data_evaluated
real_robot_success
hardware_readiness
live_ur_rtde_support
live_franka_hardware_support
live_ros2_dds_bridge_readiness
policy_uplift
production_readiness
cryptographic proof of physical runtime origin
```

## RALPLAN-DR Summary

### Principles

```text
1. Ready status is verifier-owned, not producer/self-attested.
2. Helper-derived event evidence is fixture evidence, even when internally
   consistent.
3. PR #12 may become a consistency baseline only; it must not become a ready
   close precedent.
4. `file_drop_rehearsal_ready=true` requires capture-edge evidence plus process
   provenance; L2 consistency alone is insufficient.
5. Claim language must remain inside digital-twin file-drop rehearsal scope.
```

### Decision drivers

```text
1. Current producer path uses `build_runtime_event_log_from_trace()` and can
   stamp the blessed raw runtime capture script id.
2. Current verifier can prove event/trace consistency but cannot prove
   derivation direction from artifacts alone.
3. The checked-in MVP-5A-pre package is still contract-ready and ready=false;
   that boundary must remain intact until a non-circular L2/L3 close exists.
```

### Why Option B follows

Option B is chosen because it satisfies all three drivers: it preserves the
valuable PR #12 verifier-owned reconstruction baseline, removes the immediate
helper-forge affordance before merge, and keeps ready status closed until the
future capture-edge + process-provenance package exists.

## Brainstorming Options

### Option A — Merge PR #12 unchanged, harden later

Optimizes:

```text
Fast merge of the consistency verifier baseline.
```

Tradeoff:

```text
Main temporarily contains a helper path that can mint raw-runtime-looking
evidence with the blessed capture script id. Even if checked-in packages remain
ready=false, the dangerous production affordance exists.
```

Verdict:

```text
Rejected. The risk window is avoidable.
```

### Option B — Add immediate helper-forge hardening to PR #12, then merge

Optimizes:

```text
Keeps PR #12's consistency verifier value while preventing helper-derived event
evidence from being promoted to ready evidence on main.
```

Tradeoff:

```text
Adds a small corrective patch before the larger capture-edge close work.
```

Verdict:

```text
Chosen.
```

### Option C — Close PR #12 and rewrite the contract from scratch

Optimizes:

```text
Clean conceptual history.
```

Tradeoff:

```text
Discards a working verifier-owned reconstruction contract and 1222-test
regression evidence. The core consistency work remains useful.
```

Verdict:

```text
Rejected. Too much churn for a bounded hardening issue.
```

## Decision

Use Option B.

Execution shape:

```text
Step 0A. PR #12 immediate hardening
  - Add a forge regression test.
  - Ensure helper-derived runtime events cannot satisfy ready=true.
  - Quarantine helper production affordances so production ready path cannot
    mint blessed capture evidence from canonical trace.
  - Keep checked-in package ready=false.

Step 0B. Merge PR #12 as consistency baseline.

Step 1. New branch for L2/L3 capture-edge evidence close.
  - Build blessed capture-edge emitter.
  - Add process provenance receipt.
  - Generate close package from capture-edge events.
  - Open file_drop_rehearsal_ready=true only on that path.
```

## Evidence Model

### L0 deterministic fixture

Allowed:

```text
file_drop_rehearsal_contract_ready=true
file_drop_rehearsal_ready=false
```

### L1 runtime-shaped summary JSON

Allowed:

```text
file_drop_rehearsal_contract_ready=true
file_drop_rehearsal_ready=false
```

### L2 event-content consistency

Allowed before L3:

```text
verifier-owned reconstruction consistency
file_drop_rehearsal_ready=false unless provenance close is present
```

Important:

```text
L2 event-content consistency does not prove capture direction.
```

### L2/L3 capture-edge close

Allowed after all acceptance criteria pass:

```text
file_drop_rehearsal_ready=true
```

Reason:

```text
Forward derivation is not proven from artifacts alone. It is enforced by the
combination of a blessed capture-edge emitter identity, process provenance
binding, helper-derived evidence rejection, and verifier reconstruction.
```

### L3 process provenance ceiling

L3 binds declared process identity. It does not prove that the runtime was a
genuine physics run rather than replay or fabrication.

Required non-claim text:

```text
Process provenance binds declared process identity.
It does not prove the runtime was a genuine physics run rather than replay or
fabrication.
```

## Immediate Hardening Requirements

### H1 — Forge PoC regression

Create a regression test that builds a ready package using:

```text
canonical_trace.json
-> helper-derived runtime_event_log.jsonl
-> blessed capture_script_id
-> ready_status_allowed=true
-> file_drop_rehearsal_ready=true
```

Expected result:

```text
verifier FAIL
```

The expected issue should be explicit, for example:

```text
helper-derived runtime evidence cannot open ready status
```

### H2 — Helper quarantine

`build_runtime_event_log_from_trace()` may remain only as a development or test
fixture helper.

Production ready path must not call it to mint closing evidence.

Acceptable implementation patterns:

```text
- Rename/mark helper as fixture-only and record helper provenance in emitted
  manifest when used.
- Add `evidence_origin=canonical_trace_projection_fixture` to helper output.
- Require ready packages to use a different blessed emitter origin that helper
  cannot stamp.
- Keep helper-generated packages contract-ready only.
```

### H3 — Verifier rejection

Verifier must reject ready packages when any closing runtime evidence indicates:

```text
evidence_origin=canonical_trace_projection_fixture
producer_kind=fixture_helper
helper_source_function=build_runtime_event_log_from_trace
```

Verifier must also reject any ready package that lacks the blessed emitter
identity required by the future L2/L3 close contract.

### H4 — Producer guard

Producer must not silently stamp:

```text
capture_script_id=mvp5a_pre_isaac_sim_raw_runtime_event_capture_v0
ready_status_allowed=true
```

on helper-derived event evidence.

If helper evidence is emitted, it must declare a non-closing origin and keep:

```text
file_drop_rehearsal_ready=false
```

## L2/L3 Close Requirements

### C1 — Blessed capture-edge emitter

Add a capture-edge emitter whose output is raw runtime event rows. The emitter
must write `runtime_event_log.jsonl` directly.

Canonical trace must be derived from the event log, not used as the producer
source.

Required emitter output:

```text
data/runtime_evidence/runtime_event_log.jsonl
data/runtime_evidence/runtime_event_manifest.json
data/runtime_evidence/runtime_reconstruction_receipt.json
data/process_provenance/process_provenance_receipt.json
```

### C2 — Process provenance receipt

Receipt must bind at least:

```text
git commit
branch
command argv
working directory
script path
script sha256
config path
config sha256
input artifact hashes
runtime_event_log sha256
stdout sha256
stderr sha256
Python version
OS summary
start timestamp
end timestamp
exit code
```

Verifier must check:

```text
exit_code == 0
script hash matches package artifact
config hash matches package artifact
event log hash matches package artifact
manifest points to the same evidence as process receipt
stdout/stderr receipts exist and match declared hashes
```

### C3 — Verifier-owned reconstruction

Verifier must independently recompute:

```text
runtime event grouping
required channel coverage
timestamp / finite / duplicate / missing-channel checks
channel-specific unit/dimension/semantic checks
canonical trace reconstruction
file-drop source projection equality
normalized contract validity
HDF5 / trainer smoke consistency
buyer report and non-claim boundary
```

Cached summaries are never source of truth.

### C4 — Ready status gate

`file_drop_rehearsal_ready=true` requires all of:

```text
blessed capture-edge emitter origin
process provenance receipt verified
helper-derived evidence absent from closing path
runtime event verifier reconstruction PASS
downstream source/contract/HDF5/trainer checks PASS
non-claims all false
forbidden claim scan PASS
```

## Non-Goals

Do not implement in this slice:

```text
desktop application
real robot control
live UR/RTDE connection
live Franka hardware connection
live ROS2/DDS bridge
external partner data evaluation
policy learning or uplift
production signing infrastructure
marketplace features
```

## Acceptance Criteria

Immediate hardening acceptance:

```text
1. helper-derived ready package forge test fails verifier.
2. helper-emitted evidence is explicitly non-closing.
3. production ready path cannot mint blessed capture evidence from canonical trace.
4. checked-in MVP-5A-pre package remains contract-ready and ready=false.
5. existing MVP-5A-pre verifier regression remains green.
6. existing helper-positive ready test is replaced or inverted before PR #12
   merge; canonical-derived event rows must not assert
   file_drop_rehearsal_ready=true.
7. verifier failure includes an explicit inspectable issue string for
   helper-derived ready evidence, for example:
   `helper-derived runtime evidence cannot open ready status`.
```

L2/L3 close acceptance:

```text
1. capture-edge emitter writes runtime_event_log.jsonl directly.
2. process provenance receipt binds command/config/script/env/stdout/stderr/event hashes.
3. canonical trace is derived from runtime events for the close package.
4. verifier rejects helper-derived event evidence even if hashes are refreshed.
5. verifier opens file_drop_rehearsal_ready=true only for L2/L3-valid evidence.
6. all golden profile projections pass.
7. all defined corrupt cases fail closed.
8. HDF5/trainer smoke agrees with reconstructed evidence.
9. buyer report states the process-provenance ceiling.
10. frozen prior proof packages and verifiers remain verified.
11. `data/process_provenance/process_provenance_receipt.json` is artifact-indexed
    and hash-locked in `package_manifest.json`.
12. verifier checks process provenance receipt path, receipt sha256, event-log
    sha256, script/config hashes, stdout/stderr hashes, and manifest linkage.
```

## Required Tests

```text
test_helper_derived_ready_evidence_fails_verifier
test_helper_evidence_manifest_declares_non_closing_origin
test_producer_cannot_mark_helper_evidence_ready
test_capture_edge_event_package_verifies_ready
test_process_provenance_event_hash_tamper_fails
test_process_provenance_script_hash_tamper_fails
test_process_provenance_config_hash_tamper_fails
test_hash_refreshed_helper_event_forge_fails
test_ready_requires_l2_l3_not_l2_consistency_only
test_buyer_report_process_provenance_non_claim_present
```

## Expanded Test Plan

### Unit tests

```text
- helper runtime evidence includes non-closing provenance fields:
  evidence_origin=canonical_trace_projection_fixture
  producer_kind=fixture_helper
  helper_source_function=build_runtime_event_log_from_trace
- verifier emits a stable issue string for helper-derived ready evidence.
- runtime/event/process receipt hash mismatch helpers fail closed.
- missing origin/provenance for ready=true fails closed.
```

### Integration tests

```text
- producer package generation with helper runtime evidence stays contract-ready.
- verifier fail-closed path rejects helper-derived ready package with refreshed
  hashes and blessed-looking capture_script_id.
- package_manifest hash-locks runtime evidence and process provenance artifacts.
- checked-in MVP-5A-pre package continues to verify with
  --allow-contract-ready --deep-hdf5.
```

### E2E tests

```text
- blessed capture-edge package opens file_drop_rehearsal_ready=true only when
  process provenance, event reconstruction, source projection, contracts,
  HDF5/trainer smoke, and claim scan all pass.
- L2 consistency-only package remains file_drop_rehearsal_ready=false.
- helper-derived package remains rejected even after artifact hashes are
  refreshed.
```

### Observability tests

```text
- verifier issues name the failing boundary: helper origin, missing provenance,
  event hash drift, script/config hash drift, stdout/stderr receipt drift.
- buyer report contains the process provenance ceiling text.
- runtime/process receipts expose enough fields for a reviewer to identify the
  source of a rejection without reading code.
```

## Deliberate Pre-Mortem

### Scenario 1 — Helper-derived events still mint ready=true

Failure mode:

```text
Tests continue using canonical-derived event rows as the positive ready fixture,
or producer helper output keeps blessed capture_script_id + ready_status_allowed.
```

Mitigation:

```text
Invert the current helper-positive ready test, add the forge PoC regression, and
require helper provenance fields to be non-closing.
```

### Scenario 2 — L2 consistency is mistaken for L2/L3 provenance close

Failure mode:

```text
Verifier proves event/trace consistency and future docs call that a capture-edge
ready close without process provenance.
```

Mitigation:

```text
Keep PR #12 language as consistency baseline only. Ready=true requires process
provenance as a peer gate to reconstruction.
```

### Scenario 3 — Buyer report or manifest overclaims process provenance

Failure mode:

```text
Report text implies L3 proves a genuine Isaac physics run or real robot origin.
```

Mitigation:

```text
Add named buyer-report test for the provenance ceiling text and keep forbidden
claim scan active across package JSON/Markdown/report artifacts.
```

## Verification Commands

Minimum final verification:

```bash
uv run pytest -q apps/api/tests/test_mvp5a_pre_file_drop_profiles.py \
  apps/api/tests/test_mvp5a_pre_file_drop_package_and_verifier.py \
  apps/api/tests/test_mvp5a_pre_frozen_verifier_regressions.py

uv run pytest -q

uv run python scripts/verify_mvp5a_pre_file_drop_chaos_rehearsal_package.py \
  docs/proof/mvp5a_pre_digital_twin_file_drop_chaos_rehearsal_package/package_manifest.json \
  --allow-contract-ready --deep-hdf5

uvx ruff check <touched files>
uv run python -m compileall <touched Python files>
git diff --check
```

## Next Planning Step

Run:

```text
$ralplan --deliberate
```

against this spec before implementation.

The plan must start with the forge PoC regression and immediate hardening, then
separate the larger L2/L3 capture-edge close work.
