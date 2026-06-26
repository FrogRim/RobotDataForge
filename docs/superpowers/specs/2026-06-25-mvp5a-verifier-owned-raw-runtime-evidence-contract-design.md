# MVP-5A-pre Verifier-Owned Raw Runtime Evidence Contract Design

Date: 2026-06-25 KST

Status: Specify

Branch: `codex/mvp5a-runtime-evidence-contract`

## Problem

MVP-5A-pre is currently closed only at:

```text
file_drop_rehearsal_contract_ready=true
file_drop_rehearsal_ready=false
```

This is intentional. The existing package proves that RDF can run a deterministic
digital-twin file-drop chaos rehearsal with four profiles, golden pass cases,
52 corrupt fail-closed cases, HDF5/trainer-smoke evidence, buyer report claim
scan, and verifier recomputation.

But `file_drop_rehearsal_ready=true` is blocked because current evidence is
still fixture or runtime-shaped JSON. A JSON object that already contains
`mvp5a_canonical_trace.frames` can be made to look like runtime output while
actually being hand-written or copied from the fixture. If verifier accepts that
as sufficient, it reintroduces the self-attestation trap.

The next slice must define a contract where the verifier owns the derivation:

```text
raw runtime events
-> verifier reconstruction
-> canonical trace
-> projected file-drop logs
-> normalized contracts
-> HDF5/trainer smoke
-> TrustPack verdict
```

The verifier must not trust `runtime_capture.json`, `canonical_trace.json`,
`config.json`, `package_manifest.json`, or buyer reports as source of truth for
ready status.

## Goal

Define the minimum raw runtime evidence contract that can unlock
`file_drop_rehearsal_ready=true` without accepting runtime-shaped JSON theater.

Target claim after implementation:

```text
RDF can mark a digital-twin file-drop chaos rehearsal ready only when the
verifier reconstructs the canonical rehearsal trace from included raw runtime
event evidence and all downstream projections/verifier checks agree.
```

The contract remains simulation/digital-twin rehearsal evidence. It does not
prove external partner data evaluation, hardware readiness, live RTDE support,
live Franka support, live ROS2 bridge readiness, policy uplift, or real robot
success.

## Evidence Levels

### L0 — Deterministic fixture

Current contract-ready package:

```text
build_fixture_canonical_trace()
-> canonical_trace.json
-> generated file-drop profiles
```

Allowed status:

```text
file_drop_rehearsal_contract_ready=true
file_drop_rehearsal_ready=false
```

Reason:

```text
Useful for parser/verifier/chaos-matrix testing, but not runtime evidence.
```

### L1 — Runtime-shaped summary JSON

Current blocked form:

```text
runtime_capture.json
  mvp5a_canonical_trace.frames[]
  runtime_provenance
```

Allowed status:

```text
file_drop_rehearsal_contract_ready=true
file_drop_rehearsal_ready=false
```

Reason:

```text
The payload already contains the derived canonical trace. A verifier can check
shape and hashes, but it cannot tell whether the canonical trace was produced by
a runtime process or manually copied.
```

### L2 — Verifier-owned raw runtime event log

This slice defines L2. The package includes raw channel events, not a
pre-derived canonical trace as the closing source of truth:

```text
data/runtime_evidence/runtime_event_log.jsonl
data/runtime_evidence/runtime_event_manifest.json
data/runtime_evidence/runtime_reconstruction_receipt.json
```

Allowed status after implementation and passing verifier:

```text
file_drop_rehearsal_contract_ready=true
file_drop_rehearsal_ready=true
```

Reason:

```text
The verifier groups raw events by frame/channel, validates required channels,
timestamps, units, dimensions, finite values, modes, and action-state lag, then
reconstructs the canonical trace itself. `canonical_trace.json` becomes a cached
derived artifact, not the source of truth.
```

Residual limitation:

```text
An offline verifier still cannot cryptographically prove that the event log came
from a real Isaac Sim process rather than a fabricated file. It can prove that
the package's ready claim is supported by included raw event evidence under a
deterministic reconstruction contract.
```

### L3 — Process-level provenance

Future stronger evidence:

```text
Isaac/Omniverse run receipt
capture script version + argv + environment hash
stdout/stderr digest
render/video receipt
container/session digest
optional signed attestation
```

Out of scope for this slice. L3 can later raise trust in runtime origin, but L2
is the minimum required to avoid accepting pre-derived runtime-shaped JSON.

## Chosen Design

Use L2 raw runtime events as the ready-status source of truth.

Rejected alternatives:

```text
1. Make runtime_capture.json stricter.
   Rejected because it still contains the derived canonical trace and remains
   self-attested.

2. Require live Isaac Sim execution inside verifier.
   Rejected because verifier must stay lightweight/offline by default and should
   not require heavy runtime.

3. Jump directly to L3 signed process provenance.
   Rejected for this slice because it is valuable but larger than the immediate
   ready-status blocker.
```

## Package Layout

Additive package layout:

```text
docs/proof/mvp5a_pre_digital_twin_file_drop_chaos_rehearsal_package/
  data/
    runtime_evidence/
      runtime_event_log.jsonl
      runtime_event_manifest.json
      runtime_reconstruction_receipt.json
    canonical_trace/
      canonical_trace.json
      runtime_capture_preflight.json
      runtime_capture_hash_receipt.json
```

Existing `canonical_trace/canonical_trace.json` remains present for downstream
compatibility and package readability. It is not authoritative for
`file_drop_rehearsal_ready=true`.

`package_manifest.json` must hash-lock all new runtime evidence artifacts.

## Runtime Event Log Contract

File:

```text
data/runtime_evidence/runtime_event_log.jsonl
```

Each line is one JSON object.

Required top-level fields:

```json
{
  "schema_version": "rdf_mvp5a_pre_raw_runtime_event_v0.1.0",
  "capture_id": "mvp5a_pre_isaac_sim_capture_...",
  "event_index": 0,
  "frame_index": 0,
  "timestamp": 0.0,
  "channel": "ur_joint_state",
  "source_backend": "isaac_sim",
  "source_process_kind": "isaac_sim_process",
  "units": {},
  "payload": {}
}
```

Global invariants:

```text
event_index is contiguous starting at 0
timestamp is finite and monotonic non-decreasing by event_index
frame_index is integer and contiguous starting at 0
each frame has exactly one required event for each required channel
no duplicate (frame_index, channel)
no missing required channel
no unknown closing channel
no NaN/Inf in any numeric payload
no external_partner_data=true
generated_by_rdf_sim=true remains explicit at package/config level
```

## Required Channels

The verifier owns the required channel set:

```text
phase_marker
ur_joint_state
ur_tcp_state
franka_joint_state
franka_eef_state
generic_command_state
```

### `phase_marker`

Payload:

```json
{
  "phase": "approach"
}
```

Allowed phases are verifier-owned constants:

```text
approach
align
insert
insert_rehearsal
settle
retract
```

The phase becomes canonical frame `phase`.

### `ur_joint_state`

Payload:

```json
{
  "actual_q": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
  "target_q": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
  "robot_mode": "RUNNING",
  "safety_status": "NORMAL",
  "joint_names": [
    "shoulder_pan_joint",
    "shoulder_lift_joint",
    "elbow_joint",
    "wrist_1_joint",
    "wrist_2_joint",
    "wrist_3_joint"
  ]
}
```

Units:

```json
{
  "joint_position": "rad"
}
```

Canonical output:

```text
frame.ur.actual_q
frame.ur.target_q
frame.ur.robot_mode
frame.ur.safety_status
```

Hard-fail:

```text
wrong dimension
missing joint_names
unknown or reordered joint names
degrees passed as radians
robot_mode != RUNNING
safety_status != NORMAL
```

### `ur_tcp_state`

Payload:

```json
{
  "actual_TCP_pose": [0.45, 0.0, 0.28, 0.0, 3.14159, 0.0],
  "target_TCP_pose": [0.45, 0.0, 0.27, 0.0, 3.14159, 0.0],
  "actual_TCP_speed": [0.0, 0.0, -0.02, 0.0, 0.0, 0.0]
}
```

Units:

```json
{
  "tcp_position": "m",
  "tcp_rotation": "rotation_vector_rad",
  "tcp_speed": "m_per_s"
}
```

Hard-fail:

```text
millimeters passed as meters
Euler/quaternion/rotation-vector mismatch
wrong vector length
NaN/Inf
```

### `franka_joint_state`

Payload:

```json
{
  "q": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
  "q_d": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
  "robot_mode": "move",
  "joint_names": [
    "panda_joint1",
    "panda_joint2",
    "panda_joint3",
    "panda_joint4",
    "panda_joint5",
    "panda_joint6",
    "panda_joint7"
  ]
}
```

Units:

```json
{
  "joint_position": "rad"
}
```

Canonical output:

```text
frame.franka.q
frame.franka.q_d
frame.franka.robot_mode
```

### `franka_eef_state`

Payload:

```json
{
  "O_T_EE": [1.0, 0.0, 0.0, 0.45, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.28, 0.0, 0.0, 0.0, 1.0],
  "O_T_EE_d": [1.0, 0.0, 0.0, 0.451, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.28, 0.0, 0.0, 0.0, 1.0]
}
```

Units:

```json
{
  "pose_matrix": "homogeneous_transform_row_major_m"
}
```

Hard-fail:

```text
wrong matrix length
missing homogeneous matrix final row semantics
millimeters passed as meters
NaN/Inf
```

### `generic_command_state`

Payload:

```json
{
  "state": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
  "command": [0.01, 0.0, 0.0, 0.0, 0.0, 0.0],
  "state_timestamp": 0.0,
  "command_timestamp": 0.0,
  "action_semantics": "commanded_target_state",
  "state_semantics": "actual_robot_state"
}
```

Hard-fail:

```text
missing command
missing state
action/state semantics omitted
state-only log treated as action log
abs(command_timestamp - state_timestamp) > MAX_ACTION_STATE_LAG
```

## Runtime Event Manifest

File:

```text
data/runtime_evidence/runtime_event_manifest.json
```

Required fields:

```json
{
  "schema_version": "rdf_mvp5a_pre_runtime_event_manifest_v0.1.0",
  "evidence_level": "L2_verifier_owned_raw_runtime_events",
  "runtime_event_log_path": "data/runtime_evidence/runtime_event_log.jsonl",
  "runtime_event_log_sha256": "...",
  "capture_id": "...",
  "capture_script_id": "mvp5a_pre_isaac_sim_raw_runtime_event_capture_v0",
  "source_backend": "isaac_sim",
  "source_process_kind": "isaac_sim_process",
  "frame_count": 12,
  "event_count": 72,
  "required_channels": [
    "phase_marker",
    "ur_joint_state",
    "ur_tcp_state",
    "franka_joint_state",
    "franka_eef_state",
    "generic_command_state"
  ],
  "generated_by_rdf_sim": true,
  "external_partner_data": false,
  "non_claims": {
    "external_partner_data_evaluated": false,
    "external_partner_data": false,
    "real_robot_success": false,
    "physical_robot_readiness": false,
    "hardware_integration": false,
    "hardware_readiness": false,
    "live_ur_rtde_support": false,
    "live_franka_hardware_support": false,
    "live_ros2_dds_bridge_readiness": false,
    "native_mcap_parser_support": false,
    "generic_file_drop_support": false,
    "generic_robot_log_parser": false,
    "policy_uplift": false,
    "learning_proven_value": false,
    "visual_policy_performance": false,
    "deployable_policy_readiness": false,
    "production_certification": false,
    "marketplace_readiness": false,
    "sim_to_real_proven": false,
    "general_robot_intelligence": false
  }
}
```

The manifest is an index, not source of truth. The verifier recomputes
`runtime_event_log_sha256`, `frame_count`, `event_count`, channels, non-claims,
and canonical trace digest from the JSONL.

## Runtime Reconstruction Receipt

File:

```text
data/runtime_evidence/runtime_reconstruction_receipt.json
```

Required fields:

```json
{
  "schema_version": "rdf_mvp5a_pre_runtime_reconstruction_receipt_v0.1.0",
  "reconstruction_algorithm": "rdf_mvp5a_pre_runtime_events_to_canonical_trace_v0.1.0",
  "runtime_event_log_sha256": "...",
  "reconstructed_canonical_trace_sha256": "...",
  "included_canonical_trace_sha256": "...",
  "matches_included_canonical_trace": true,
  "runtime_capture_sufficient": true,
  "ready_status_allowed": true
}
```

The receipt is a cached summary. The verifier recomputes every field above.

## Verifier Algorithm

Default verifier with ready package:

```text
1. Load package_manifest.json.
2. Verify package path safety and artifact hashes.
3. Load config, canonical trace, runtime evidence manifest, runtime event JSONL,
   runtime reconstruction receipt.
4. If status=file_drop_rehearsal_ready:
   a. require runtime evidence artifacts to exist and be hash-locked.
   b. reject if only runtime_capture.json exists.
   c. parse runtime_event_log.jsonl.
   d. validate global event invariants.
   e. group events by frame_index.
   f. validate required channels per frame.
   g. validate per-channel units, dimensions, finite values, semantics, modes.
   h. reconstruct canonical frames.
   i. hash reconstructed canonical trace using stable JSON.
   j. compare reconstructed trace to included canonical_trace.json.
   k. compare reconstructed trace to generated profile source logs.
   l. require deep HDF5 verification for final VERIFIED status.
5. Recompute golden/corrupt profile outcomes from included evidence.
6. Scan non-claims and forbidden claims across JSON/JSONL/MD/TXT/HTML.
7. Emit VERIFIED only if all checks pass.
```

Important:

```text
runtime_capture_preflight.runtime_capture_sufficient=true is not enough.
runtime_event_log -> reconstructed canonical trace is the only ready source.
```

## Ready Status Criteria

`file_drop_rehearsal_ready=true` is allowed only when all are true:

```text
1. status/config/manifest agree on file_drop_rehearsal_ready.
2. runtime_event_manifest exists and is hash-locked.
3. runtime_event_log exists and is hash-locked.
4. runtime_reconstruction_receipt exists and is hash-locked.
5. verifier reconstructs canonical trace from runtime_event_log.
6. reconstructed canonical trace hash equals included canonical_trace hash.
7. downstream profile source logs match projections from reconstructed canonical trace.
8. golden profiles pass.
9. corrupt matrix fail-closed count remains complete.
10. accepted HDF5 exports pass --deep-hdf5 semantic verification.
11. trainer smoke reports match exported data.
12. non-claims remain false.
13. forbidden external/hardware/live/runtime production claims are absent.
```

If any item fails:

```text
VERDICT: FAILED
```

## Tamper Matrix

New tests must include at least:

```text
missing runtime_event_log -> fail
runtime_event_log hash mismatch -> fail
manifest hash refreshed after semantic event drift -> fail
missing required channel -> fail
duplicate frame/channel event -> fail
event_index gap -> fail
frame_index gap -> fail
non-monotonic timestamp -> fail
large timestamp gap -> fail
NaN/Inf payload -> fail
UR joint order swapped -> fail
UR degrees-as-radians -> fail
UR tcp mm-as-m -> fail
UR robot_mode not running -> fail
UR safety protective_stop -> fail
Franka wrong DOF -> fail
Franka EEF matrix wrong length -> fail
generic command/state lag too high -> fail
generic state-only promoted to action -> fail
phase unknown -> fail
canonical_trace edited after event log -> fail
source log edited after event log -> fail
HDF5 drift after event log -> fail with --deep-hdf5
buyer_report overclaim -> fail
runtime_capture.json present but no event log -> fail for ready
```

## Implementation Boundaries

Allowed:

```text
Add new runtime evidence schema constants.
Add builder support to emit L2 event evidence from a capture path or contract
test fixture, clearly labelled.
Add verifier reconstruction path.
Add tests and tamper fixtures in temporary directories.
Regenerate the MVP-5A-pre package only after ready criteria can be recomputed
from included L2 evidence.
```

Forbidden:

```text
Do not mark deterministic fixture-only evidence as ready.
Do not let runtime_capture.json alone mint ready.
Do not weaken the existing chaos-matrix verifier checks.
Do not weaken HDF5 --deep-hdf5 requirement.
Do not mark external_partner_data=true.
Do not claim real robot, hardware, live UR, live Franka, live ROS2, policy
uplift, production readiness, or external partner data evaluation.
Do not mutate frozen MVP-2/MVP-3/MVP-4 packages.
```

## Open Review Question

The contract can be implemented in two valid ways:

```text
A. Contract-first: implement verifier support and synthetic L2 contract tests,
   but keep the shipped MVP-5A-pre package contract-ready until an actual capture
   script emits L2 runtime events.

B. Package-close: also add a capture/export path that emits L2 event evidence
   from the current digital-twin generation path, regenerate the package, and set
   file_drop_rehearsal_ready=true.
```

Objective recommendation:

```text
Choose A first unless there is real capture-produced L2 evidence. If B uses the
same deterministic fixture generator to emit event rows, it risks becoming
"runtime-shaped JSON v2." B is acceptable only if the producer path is explicitly
a capture/event export path and the package claims only digital-twin rehearsal
readiness, not process-origin proof.
```

## Acceptance Criteria For This Slice

Spec/plan acceptance:

```text
1. L0/L1/L2/L3 evidence boundaries are documented.
2. Runtime event JSONL schema is documented.
3. Required channels and per-channel semantic checks are documented.
4. Verifier reconstruction algorithm is documented.
5. Ready status criteria are documented.
6. Tamper matrix is documented.
7. Claim boundary explicitly states offline verifier cannot cryptographically
   prove genuine Isaac process origin.
```

Implementation acceptance:

```text
1. Verifier fails ready packages without L2 runtime event evidence.
2. Verifier reconstructs canonical trace from L2 event evidence.
3. Verifier detects all defined runtime-event tamper cases.
4. Runtime-shaped capture JSON remains non-closing.
5. Existing contract-ready package still verifies with --allow-contract-ready.
6. Prior MVP verifiers still pass.
```

## Verification Commands

Focused:

```bash
uv run pytest -q apps/api/tests/test_mvp5a_pre_file_drop_package_and_verifier.py
uv run pytest -q apps/api/tests/test_mvp5a_pre_file_drop_profiles.py
python3 scripts/verify_mvp5a_pre_file_drop_chaos_rehearsal_package.py \
  docs/proof/mvp5a_pre_digital_twin_file_drop_chaos_rehearsal_package/package_manifest.json \
  --allow-contract-ready --deep-hdf5
```

Regression:

```bash
python3 scripts/verify_mvp2_package.py \
  docs/proof/mvp2_learning_proven_evidence_package/package_manifest.json
python3 scripts/verify_proof_package.py \
  docs/proof/mvp3a_target_fixture_pose_variant_proof_package/package_manifest.json
python3 scripts/verify_mvp3b_source_adapter_package.py \
  docs/proof/mvp3b_source_adapter_matrix_proof_package/package_manifest.json
python3 scripts/verify_mvp3c_isaac_sim_embodiment_source_package.py \
  docs/proof/mvp3c_isaac_sim_embodiment_source_proof_package/package_manifest.json
python3 scripts/verify_external_robot_data_ingest_package.py \
  docs/proof/external_robot_data_ingest_eval_v0_proof_package/package_manifest.json
python3 scripts/verify_lerobot_public_dataset_matrix_package.py \
  docs/proof/rdf_public_dataset_trustpack_v0_lerobot_matrix_package/package_manifest.json
```

Standard:

```bash
python -m compileall <touched scripts/services/tests>
uv run ruff check <touched files>
git diff --check
```
