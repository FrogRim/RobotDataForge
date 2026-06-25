# Spec: MVP-5A-pre Digital Twin File-Drop Chaos Rehearsal

Date: 2026-06-25
Status: IMPLEMENTED V0 CONTRACT-READY; READY CLOSED IN V0; FUTURE VERIFIER-OWNED RAW RUNTIME CONTRACT REQUIRED
Branch: `codex/mvp5a-pre-file-drop-chaos-rehearsal`

## Objective

이번 milestone의 목적은 실제 외부 partner file-drop을 받기 전에 RDF ingest,
adapter, verifier, TrustPack, buyer report가 현실적인 recorded-log 오류를
fail-closed로 잡는지 리허설하는 것이다.

핵심 claim:

```text
RDF can rehearse external recorded-log ingestion using deterministic/generated
digital-twin file-drop profiles, separate good logs from corrupted logs,
preserve structured rejection reasons, and package the result with a
self-contained verifier.
```

한국어로:

```text
RDF는 실제 외부 로그를 받기 전에 deterministic/generated digital-twin 로그로
UR/Franka/ROS2-style/generic file-drop을 리허설하고, 정상/손상 로그를
pass/fail로 분리하며, 실패 이유를 구조화하고, TrustPack/verifier로
재계산 가능하게 만들 수 있다.
```

이 milestone은 새 external partner data evaluation proof가 아니다.
실제 외부 file-drop 직전의 chaos rehearsal이다.

## Current Repo Facts

이미 존재하는 기반:

```text
MVP-3C:
  docs/proof/mvp3c_isaac_sim_embodiment_source_proof_package/
  scripts/run_mvp3c_isaac_sim_embodiment_source.py
  scripts/capture_mvp3c_isaac_sim_embodiment_source.py
  scripts/verify_mvp3c_isaac_sim_embodiment_source_package.py

External ingest v0:
  docs/proof/external_robot_data_ingest_eval_v0_proof_package/
  apps/api/app/services/external_robot_data_ingest.py
  scripts/run_external_robot_data_ingest_eval_v0.py
  scripts/verify_external_robot_data_ingest_package.py

TrustPack v0:
  docs/proof/rdf_public_dataset_trustpack_v0_lerobot_matrix_package/
  apps/api/app/services/rdf_public_dataset_trustpack.py
  scripts/run_rdf_public_dataset_trustpack_generator.py
```

현재 `external_robot_data_ingest`는 `external_ingest_contract_ready`와
`external_data_evaluated`를 분리한다. 기존 verifier는 semantic parity가
없는 `external_data_evaluated` package를 의도적으로 fail-closed한다.

이번 작업은 그 fail-closed branch를 실제 partner data로 바로 여는 것이
아니라, digital-twin rehearsal log를 대상으로 별도 status를 닫는다.

## External Format Grounding

UR RTDE는 controller와 외부 application을 TCP/IP로 동기화하는 인터페이스다.
공식 문서는 RTDE output field에 `timestamp`, `target_q`, `actual_q`,
`actual_TCP_pose`, `target_TCP_pose`, `actual_TCP_speed`, `robot_mode`,
`safety_status` 계열 field가 있음을 설명한다. 또한 controller resource가
부족하면 output package를 skip하고 가장 최근 data만 보낼 수 있다고
문서화한다.

MCAP은 timestamped multi-channel pre-serialized log data를 저장하는
open-source container이며, pub/sub 또는 robotics application에 적합하다고
문서화되어 있다. v0에서는 binary MCAP parser를 제품 claim으로 열지 않고,
MCAP/ROS2에서 실제로 터지는 multi-channel timestamp/schema/frame 문제를
`ros2_channel_bundle_jsonl_v0`로 먼저 리허설한다.

Franka 계열은 `q`, `q_d`, `O_T_EE`, `O_T_EE_d`, `robot_mode` 같은
state field가 널리 쓰인다. v0는 live Franka FCI support가 아니라
Franka-style recorded state/action JSONL의 schema/semantic validation만
다룬다.

References:

```text
UR RTDE Guide:
https://docs.universal-robots.com/tutorials/communication-protocol-tutorials/rtde-guide.html

MCAP:
https://mcap.dev/

libfranka RobotState:
https://frankarobotics.github.io/libfranka/0.15.0/structfranka_1_1RobotState.html
```

## Brainstorming Options

### Option A — Minimal generic JSONL rehearsal

구성:

```text
generic_command_state_jsonl_v0 하나만 생성
몇 개의 corrupt row만 테스트
기존 external ingest path 재사용
```

장점:

```text
구현이 빠르다.
기존 external ingest v0와 가장 가깝다.
```

거절 이유:

```text
실제 file-drop에서 자주 터지는 profile-specific 오류를 거의 못 잡는다.
UR timestamp skip, Franka matrix/joint semantics, ROS2 topic/frame drift가 빠진다.
```

### Option B — Digital-twin multi-profile chaos rehearsal

구성:

```text
deterministic/generated digital-twin canonical trace
→ UR RTDE-like CSV
→ Franka-state JSONL
→ ROS2 channel-bundle JSONL
→ generic command-state JSONL
→ golden + corrupt matrix
→ verifier-backed rehearsal TrustPack
```

장점:

```text
실제 partner file-drop에서 터질 schema/timestamp/unit/frame/action-state 오류를
넓게 다룬다.
canonical truth와 projected file-drop을 분리해 self-attestation을 줄인다.
bad log까지 evidence로 포함해 fail-closed behavior를 검증한다.
```

트레이드오프:

```text
구현 파일과 테스트가 많다.
mutation taxonomy와 verifier가 커진다.
Isaac Sim runtime evidence가 없으면 full ready claim을 닫지 못한다.
```

선택:

```text
Option B를 선택한다.
```

### Option C — Live hardware / native ROS2-MCAP rehearsal

구성:

```text
실제 UR RTDE client, Franka FCI log, ROS2 bag/MCAP binary parser까지 직접 다룬다.
```

장점:

```text
실제 deployment와 가장 가깝다.
```

거절 이유:

```text
실제 robot control 또는 live runtime support로 오독될 위험이 크다.
hardware/runtime dependency가 들어와 proof boundary가 흐린다.
partner file-drop 전에 먼저 깨야 할 offline schema/semantic 문제와 섞인다.
```

## Decision

MVP-5A-pre는 **Digital Twin File-Drop Chaos Rehearsal**로 간다.

정확한 milestone claim:

```text
file_drop_rehearsal_contract_ready=true
file_drop_rehearsal_ready=false
```

이 v0 status는 아래가 모두 만족될 때 가능하다.

```text
1. canonical trace source가 deterministic digital-twin fixture임을 정직하게
   표시한다.
2. 4개 required file-drop profile이 canonical trace에서 deterministic projection된다.
3. 각 profile golden case가 RDF ingest/export/trainer-smoke path를 통과한다.
4. 정의된 corruption matrix가 100% fail-closed된다.
5. 모든 failure가 structured rejection reason으로 남는다.
6. verifier가 summary가 아니라 included evidence에서 pass/fail을 재계산한다.
```

`file_drop_rehearsal_ready=true`는 v0에서 의도적으로 닫지 않는다. Runtime-shaped
JSON은 구조적으로 검사할 수 있지만, offline verifier가 raw Isaac process origin을
독립적으로 증명할 수 없으므로 ready evidence가 아니다.

```text
runtime_capture_structurally_valid=true 가능
runtime_capture_sufficient=false
blocked_reason=runtime_capture_unverified_source_process
```

향후 ready claim은 별도 raw runtime evidence contract와 verifier-owned replay/hash
binding이 생긴 뒤에만 열 수 있다. Deterministic fixture나 self-declared
`runtime_capture.json`만으로는 full rehearsal ready를 닫지 않는다.

## Claim Boundary

Allowed claim:

```text
RDF rehearsed external recorded-log ingestion using deterministic/generated
digital-twin file-drop profiles and verified that defined good logs pass while
defined corrupted logs fail closed with structured rejection reasons.
```

Forbidden claims:

```text
external_partner_data_evaluated
external_partner_data
real_robot_success
physical_robot_readiness
hardware_integration
hardware_readiness
live_ur_rtde_support
live_franka_hardware_support
live_ros2_dds_bridge_readiness
native_mcap_parser_support
generic_file_drop_support
generic_robot_log_parser
policy_uplift
learning_proven_value
visual_policy_performance
deployable_policy_readiness
marketplace_readiness
production_certification
sim_to_real_proven
general_robot_intelligence
```

Package metadata must use explicit truth values:

```json
{
  "external_partner_data_evaluated": false,
  "generated_by_rdf_sim": true,
  "external_partner_data": false,
  "real_robot_success": false,
  "live_ur_rtde_support": false,
  "live_franka_hardware_support": false,
  "live_ros2_dds_bridge_readiness": false
}
```

## Core Architecture

### Layer 1 — Canonical Digital Twin Trace

The canonical trace is the source of projection truth.

Required artifact:

```text
data/canonical_trace/canonical_trace.json
data/canonical_trace/runtime_capture_hash_receipt.json
data/canonical_trace/runtime_capture_preflight.json
```

`data/canonical_trace/runtime_capture.json` is optional in v0. If supplied, it
is treated as self-declared runtime-shaped evidence unless a future
verifier-owned raw runtime evidence contract exists. Therefore it may improve
diagnostics, but it must not mint `file_drop_rehearsal_ready`.

Required properties:

```text
source_kind=deterministic_fixture_digital_twin_trace for contract-ready packages
runtime-shaped capture may be structurally checked but remains non-closing in v0
runtime_capture_sufficient=false for all v0 packages
runtime_provenance.capture_script_id=mvp5a_pre_isaac_sim_canonical_trace_capture_v0
generated_by_rdf_sim=true
external_partner_data=false
frame_count >= 12
monotonic timestamps
joint state present
end-effector pose present when available
commanded target and actual state separated
reset/safety/status metadata present
```

The canonical trace must include at least:

```text
time index
timestamp_seconds
robot profile id
joint_names
commanded_joint_position
actual_joint_position
commanded_tcp_pose
actual_tcp_pose
robot_mode
safety_status
task_phase
source_runtime_metadata
```

#### Runtime Capture Sufficiency Preflight

Implementation must run a read-only runtime-capture preflight when a capture is
supplied. In v0 this preflight is deliberately diagnostic-only: it can report
whether a runtime-shaped payload is structurally valid, but it must keep
`runtime_capture_sufficient=false` because raw runtime origin is not independently
verified by the package verifier.

The current MVP-3C package is only a candidate source. It must not be assumed
sufficient. If no capture is supplied, the correct output is:

```text
file_drop_rehearsal_contract_ready=true
file_drop_rehearsal_ready=false
blocked_reason=runtime_capture_not_supplied
fresh_runtime_capture_required=true
```

If a capture is supplied and structurally valid, the correct output is still:

```text
file_drop_rehearsal_contract_ready=true
file_drop_rehearsal_ready=false
runtime_capture_structurally_valid=true
runtime_capture_sufficient=false
blocked_reason=runtime_capture_unverified_source_process
fresh_runtime_capture_required=true
```

Missing runtime-backed facts must not be synthesized from deterministic
fixtures, and self-declared runtime provenance must not be upgraded into a ready
claim.

### Layer 2 — Required File-Drop Profiles

v0 requires 4 profile contracts.

```text
ur_rtde_csv_v0
franka_state_jsonl_v0
ros2_channel_bundle_jsonl_v0
generic_command_state_jsonl_v0
```

#### `ur_rtde_csv_v0`

Required source files:

```text
metadata.json
rtde_output.csv
```

Required fields:

```text
timestamp
joint_names
target_q
actual_q
target_TCP_pose
actual_TCP_pose
actual_TCP_speed
robot_mode
safety_status
```

Semantic checks:

```text
timestamp monotonic
timestamp gap / dropped RTDE output sample detection
vector length 6 for q/TCP fields
joint units rad
TCP translation unit m
TCP rotation representation rotation_vector_rad
target_q != actual_q allowed but lag bounded
robot_mode must be running for accepted rows
safety_status must not be protective stop for accepted rows
```

#### `franka_state_jsonl_v0`

Required source files:

```text
metadata.json
franka_state.jsonl
franka_command.jsonl
```

Required fields:

```text
timestamp
q
q_d
O_T_EE
O_T_EE_d
robot_mode
```

Semantic checks:

```text
q/q_d length 7
O_T_EE/O_T_EE_d length 16
matrix values finite
rigid transform plausibility
stable representation order
commanded and actual joint state separated
robot_mode accepted value for accepted rows
```

#### `ros2_channel_bundle_jsonl_v0`

This is a ROS2/MCAP rehearsal surrogate, not a native MCAP parser claim.

Required source files:

```text
metadata.json
topic_manifest.json
topics/joint_states.jsonl
topics/tf.jsonl
topics/tf_static.jsonl
topics/command.jsonl
```

Required channels:

```text
/joint_states
/tf
/tf_static
/command
```

Semantic checks:

```text
topic manifest matches files
timestamp monotonic within each topic
time skew between command and joint_states bounded
cross-topic timestamp alignment
tf_static present
frame tree has stable root
frame tree acyclic
base frame does not change mid-episode
joint name order stable
command topic semantics declared
```

#### `generic_command_state_jsonl_v0`

Required source files:

```text
metadata.json
command_state.jsonl
```

This profile is the bridge to the existing external ingest v0 path.

Semantic checks:

```text
command stream present
state stream present
action_semantics present
state_semantics present
accepted rows pass command/state contract
future-state-as-action rejected
state-only log claiming command rejected
reset boundary rejected
fabricated task_success rejected
rejected cases preserve rejection reason in the corruption matrix
```

### Layer 3 — Golden + Corrupt Matrix

Every profile must have:

```text
1 golden case
at least 12 corrupt cases
```

v0 total minimum:

```text
profiles >= 4
golden_cases >= 4
corrupt_cases >= 50
```

All defined corrupt cases must fail closed.

### Layer 4 — Ingest / Normalization / Curation

Flow:

```text
file_drop_directory
→ profile resolver
→ source file hash manifest
→ profile-specific parser
→ semantic normalizer
→ normalized trajectory contract
→ evaluator / consistency checks
→ curation manifest
→ HDF5 export for accepted golden logs
→ trainer smoke
→ buyer report
→ TrustPack verifier
```

Bad logs are not thrown away.

```text
bad log raw source is retained
bad log has evaluator result
bad log has structured rejection reason
bad log has export_eligible=false
bad log has trainer_smoke_eligible=false
```

### Layer 5 — Rehearsal TrustPack

Output package:

```text
docs/proof/mvp5a_pre_digital_twin_file_drop_chaos_rehearsal_package/
  README.md
  package_manifest.json
  buyer_report.html
  data/
    config.json
    non_claims_attestation.json
    canonical_trace/
      canonical_trace.json
      runtime_capture.json                 # present only when runtime capture is supplied
      runtime_capture_preflight.json
      runtime_capture_hash_receipt.json
    profile_registry.json
    source_drops/
      golden/
        ur_rtde_csv_v0/
        franka_state_jsonl_v0/
        ros2_channel_bundle_jsonl_v0/
        generic_command_state_jsonl_v0/
      corrupt/
        <profile_id>/<mutation_id>/
    ingest_results/
      golden_results.json
      corruption_matrix_results.json
      rejection_reason_coverage.json
    normalized_contracts/
      <profile_id>_normalized_contract.json
    export/
      <profile_id>/dataset.hdf5
      <profile_id>/split_manifest.json
      <profile_id>/hdf5_inspection_report.json
      <profile_id>/semantic_preservation_receipt.json
      <profile_id>/trainer_smoke_report.json
    reports/
      buyer_report.html
    artifact_index.json
```

## Corruption Matrix

The matrix must cover at least these categories.

### Schema / shape

```text
missing_required_file
missing_metadata
missing_required_field
wrong_json_type
wrong_vector_length
malformed_jsonl
malformed_csv_row
header_field_mismatch
unknown_robot_model
wrong_profile_declared
duplicate_field_semantics
path_traversal_filename
```

### Timestamp / ordering

```text
timestamp_non_monotonic
timestamp_duplicate
timestamp_gap_large
timestamp_negative
timestamp_mixed_seconds_milliseconds
timestamp_string_timezone
topic_clock_skew_high
```

### Units / representation

```text
joint_degrees_instead_of_radians
tcp_millimeters_instead_of_meters
tcp_rotation_quaternion_instead_of_rotation_vector
franka_transform_length_wrong
quaternion_not_normalized
velocity_unit_cm_per_s
non_finite_numeric_value
```

### Frame / transform

```text
frame_id_missing
base_frame_changed_mid_episode
tf_static_missing
tf_parent_cycle
left_right_handed_axis_swap
tcp_offset_changed_mid_episode
projection_frame_mismatch
```

### Action-state semantics

```text
target_actual_swapped
state_only_log_claims_command
command_state_lag_high
future_state_used_as_action
gripper_stream_missing_when_declared
reset_boundary_inside_episode
safety_status_protective_stop
robot_mode_not_running
fabricated_task_success_field
task_phase_inconsistent_with_motion
```

### Provenance / claim boundary

```text
external_partner_data_true
real_robot_success_true
generated_by_rdf_sim_false
source_kind_external_partner
license_placeholder
source_owner_placeholder
source_hash_mismatch
spent_seed_leak
```

### Export / summary tamper

```text
cached_summary_pass_but_evidence_fail
trainer_smoke_false_but_summary_true
hdf5_semantic_drift
non_claim_true
buyer_report_overclaim_text
artifact_index_hash_mismatch
```

## Required Rejection Reason Taxonomy

Every failed case must map to at least one structured reason:

```text
schema_missing_required_artifact
schema_missing_required_field
schema_type_mismatch
timestamp_not_monotonic
timestamp_gap_or_drift
unit_mismatch
vector_dimension_mismatch
frame_tree_invalid
frame_semantic_drift
action_state_semantic_mismatch
safety_or_robot_mode_invalid
provenance_boundary_violation
claim_boundary_violation
hash_integrity_failure
export_semantic_drift
unsupported_profile
```

Defined mutation coverage must be 100%.

```text
silent_pass_rate=0
unclassified_failure_rate=0
```

## Verifier Contract

New verifier:

```text
scripts/verify_mvp5a_pre_file_drop_chaos_rehearsal_package.py
```

Verifier properties:

```text
stdlib-only
producer import = 0
Isaac import = 0
no network
no HDF5 dependency in default mode
```

Verifier recomputes:

```text
artifact hashes
runtime_capture hash binding
canonical trace frame count and timestamp monotonicity
profile registry exactness
golden source file hashes
corrupt source file hashes
profile-specific parser-visible invariants
golden pass count
corrupt fail count
rejection reason coverage
non-claims false
forbidden claim text scan for README and HTML
spent seed no-reuse range
summary-vs-evidence consistency
semantic-preservation receipts for accepted golden exports
```

Optional deep modes:

```text
--deep-hdf5
  inspect exported HDF5 payloads for accepted golden logs.
```

Default verifier must be enough to recompute `file_drop_rehearsal_contract_ready`
from included small evidence without trusting `buyer_report.html`,
`config.json`, or `package_manifest.json` as source of truth. In v0 any
`file_drop_rehearsal_ready=true` package must fail closed until a separate
verifier-owned raw runtime evidence contract exists.
Because MVP-5A-pre packages include HDF5 exports, a final
`VERDICT: VERIFIED` package run must use `--deep-hdf5`; default mode without it
must fail closed with `hdf5 payload verification requires --deep-hdf5` rather
than claiming full HDF5 semantic verification from sidecar hashes alone.

## Acceptance Criteria

Required:

```text
1. New branch is used; frozen packages remain untouched.
2. Package includes 4 required profiles.
3. Canonical trace is hash-bound to deterministic fixture provenance for v0
   contract-ready status; runtime-shaped capture JSON is structurally checked
   but cannot mint ready status, and any ready-status tamper fails.
4. Golden case for every profile passes.
5. At least 50 corrupt cases exist.
6. Every defined corrupt case fails closed.
7. Every corrupt failure has structured rejection reason.
8. Accepted golden logs produce normalized contract, HDF5 export, and trainer smoke report.
9. Rejected/corrupt logs have export_eligible=false and trainer_smoke_eligible=false.
10. Verifier recomputes from included evidence, not cached summaries.
11. Buyer report includes clear non-claims and provenance boundary.
12. Forbidden claim scanner covers JSON, JSONL, Markdown, text, and HTML.
13. Package sets generated_by_rdf_sim=true and external_partner_data=false.
14. No generated fixture is promoted to external partner data.
15. Prior MVP-2/MVP-3/MVP-4 proof verifiers still pass.
```

Quantitative gates:

```text
golden_profile_pass_rate = 100%
corrupt_matrix_silent_pass_rate = 0%
structured_rejection_reason_coverage = 100%
defined_tamper_detection = 100%
accepted_golden_hdf5_trainer_smoke_pass_rate = 100%
```

## Test Plan

New tests should include:

```text
test_profile_registry_has_required_profiles
test_runtime_shaped_capture_stays_contract_ready_without_verifier_owned_runtime_evidence
test_canonical_trace_timestamp_monotonic
test_ur_rtde_csv_golden_passes
test_franka_state_jsonl_golden_passes
test_ros2_channel_bundle_golden_passes
test_generic_command_state_golden_passes
test_each_defined_mutation_fails_closed
test_corrupt_cases_have_structured_rejection_reasons
test_corrupt_cases_not_export_or_trainer_eligible
test_summary_tamper_fails_verifier
test_source_hash_tamper_fails_verifier
test_buyer_report_overclaim_text_fails_verifier
test_non_claim_true_fails_verifier
test_spent_seed_reuse_fails_verifier
test_verifier_import_guard_stdlib_only
```

Regression verification:

```text
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

Standard code checks:

```text
uv run pytest -q apps/api/tests/test_mvp5a_pre_file_drop_rehearsal.py
uv run pytest -q
uv run ruff check <touched files>
python -m compileall <touched scripts/services/tests>
git diff --check
```

## Stop Conditions

Stop and report instead of closing `file_drop_rehearsal_ready` if:

```text
The package only has runtime-shaped/self-declared JSON instead of verifier-owned
raw runtime evidence.
The package only contains deterministic fixtures.
Any required profile lacks a golden pass.
Any defined corruption silently passes.
Any corrupt failure lacks a structured rejection reason.
Verifier trusts cached summary instead of included evidence.
HDF5 export requires erasing profile-specific semantics.
Implementation would claim external_partner_data_evaluated.
Implementation would claim live UR/RTDE, live Franka, or live ROS2 bridge support.
Implementation would require real robot control.
Implementation would mutate frozen MVP-2/MVP-3/MVP-4 packages.
```

If raw runtime evidence is unavailable, the allowed output is:

```text
file_drop_rehearsal_contract_ready=true
file_drop_rehearsal_ready=false
blocked_reason=runtime_capture_not_supplied
```

## Non-Goals

```text
No real external partner file-drop evaluation.
No live robot control.
No live RTDE client.
No live Franka FCI client.
No live ROS2/DDS bridge.
No binary MCAP parser claim.
No policy training or policy uplift.
No visual-policy or camera-conditioned learning readiness.
No production certification or marketplace readiness.
No generic robot log parser.
```

## Implementation Notes for Later Ralplan

Expected task decomposition:

```text
T1 profile contracts + corruption taxonomy tests
T2 canonical trace capture/binding contract
T3 projection writers for 4 profiles
T4 profile parsers + semantic validators
T5 mutation generator + expected rejection mapping
T6 ingest/export/trainer integration for golden profiles
T7 TrustPack package builder
T8 stdlib verifier + tamper tests
T9 buyer report + partner file-drop readiness kit
T10 regression verification + docs/handoff updates
```

Dependency order:

```text
T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8 → T9 → T10
```

Parallelizable after T3:

```text
profile parser tests per profile
mutation definitions per category
buyer report copy
partner intake docs
```

## Final Claim Boundary

When this milestone is complete, the strongest allowed statement is:

```text
RDF has rehearsed external recorded-log file-drop ingestion using
deterministic/generated digital-twin UR/Franka/ROS2-style/generic profiles, including
golden and corrupted logs. The rehearsal package proves that defined good logs
pass and defined bad logs fail closed with structured rejection reasons under a
self-contained verifier.
```

It still does not prove:

```text
actual external partner data evaluation
real robot readiness
live UR/RTDE support
live Franka support
live ROS2/DDS support
policy uplift
production use
```
