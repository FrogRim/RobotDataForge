# Spec: MVP-3B Source-Adapter Infrastructure Closed

Date: 2026-06-20
Status: RALPLAN APPROVED FOR IMPLEMENTATION
Branch: `codex/mvp3-heldout-closure-spine`

## Objective

MVP-3B의 목적은 MVP-3A에서 닫은 proof discipline을 Isaac task variant 바깥으로
확장하는 것이다. 이번 slice는 learning uplift를 다시 증명하는 단계가 아니라,
source-shaped robot data가 Robot Data Forge의 normalized trajectory contract와
proof package discipline으로 들어올 수 있는지 검증한다.

이번 slice의 이름은 다음 claim tier를 분리한다.

```text
MVP-3B Source-Adapter Infrastructure Closed
  UR / ROS2-DDS / Franka 스타일 recorded-log fixture source가 RDF normalized
  trajectory contract로 projection되고, self-contained proof package와 독립
  verifier로 재검증됨.

MVP-3B Learning-Proven Addendum
  이번 slice에서는 기본 목표가 아니다. 별도 fresh held-out policy evaluation이
  있을 때만 나중에 생성한다.
```

이 분리는 MVP-2와 MVP-3A에서 지킨 `learning-ready`, `proof-infrastructure`,
`learning-proven` 경계를 유지하기 위한 제품 계약이다.

## Brainstorming

### Option A: Single UR Adapter Deep Slice

```text
changed_variable=source_adapter
adapter=universal_robots_ur_industrial_arm
```

최적화:

- 범위가 작다.
- 기존 MVP-1+ UR file-backed lineage와 MVP-2 UR harness를 재사용하기 쉽다.
- 실제 구현 리스크가 낮다.

Tradeoff:

- MVP-3B가 UR 하나에 너무 붙어서 ROS2-DDS / Franka 확장성을 덜 보여준다.
- `UR support`로 오해될 위험이 커진다.

### Option B: Source-Adapter Matrix Slice

```text
changed_variable=source_adapter_matrix
adapters=[
  franka_research_arm,
  robotis_sh5_ros2_dds,
  universal_robots_ur_industrial_arm
]
```

최적화:

- MVP-3B가 source expansion임을 가장 명확하게 보여준다.
- 한 adapter의 특수 성공이 아니라 RDF contract와 package discipline의 반복성을
  보여준다.
- UR/ROS2-DDS/Franka를 모두 다루되 production support claim은 하지 않는다.

Tradeoff:

- package와 verifier contract가 조금 더 넓어진다.
- 각 adapter별 source/projection/contract hash-lock을 공통 schema로 묶어야 한다.

### Option C: Real/Public Log Import Slice

```text
changed_variable=external_log_import
source=public_or_partner_recorded_log
```

최적화:

- 외부 신뢰도와 buyer relevance가 가장 높다.

Tradeoff:

- licensing, provenance, schema variability, privacy/IP risk가 열린다.
- 지금 단계에서 external package self-containment와 non-claim boundary를 동시에
  지키기 어렵다.

### Option D: Another Isaac Robustness Slice

```text
changed_variable=fresh_isaac_range_or_task_variant
```

최적화:

- MVP-3A의 성공을 더 강하게 만든다.

Tradeoff:

- source adapter 확장이라는 MVP-3B 목적과 거리가 있다.
- MVP-3A와 포트폴리오상 차이가 약하다.

## Decision

MVP-3B는 Option B, **Source-Adapter Matrix Slice**로 진행한다.

선택 이유:

- 사용자가 리마인드한 MVP-3 방향인 UR / ROS2-DDS / Franka adapter 적용 가능성에
  가장 직접적으로 답한다.
- 단일 UR proof보다 제품 확장성을 더 잘 보여준다.
- 실제 robot support claim 없이도 adapter-shaped source evidence가 RDF trust
  package로 들어오는지 검증할 수 있다.
- MVP-3A와 다른 차원의 proof다. A는 `task_variant`, B는 `source_adapter`.

선택이 바뀌는 조건:

- 실제 partner/public robot log가 즉시 제공되고 license/provenance가 명확하면 Option C를
  별도 MVP-3B-real-log addendum으로 재검토한다.
- 구현 중 matrix contract가 불필요하게 커지면 `universal_robots_ur_industrial_arm` 단일
  adapter로 축소하되, 문서에는 MVP-3B-Single-Adapter로 명확히 이름을 바꾼다.

## Primary Claim

MVP-3B의 primary claim은 다음 문장으로 제한한다.

```text
Given generated/file-backed recorded-log fixtures shaped like Franka, ROS2-DDS,
and Universal Robots UR command-state sources, Robot Data Forge can project those
sources into normalized robot-action trajectory contracts and ship a
self-contained proof package whose source logs, projected artifacts, contracts,
claim boundaries, and package manifest are independently verifiable.
```

Equivalently, MVP-3B proves three source profiles projected through a common RDF
adapter infrastructure. It does not prove three independent robot integrations.

## Non-Claims

MVP-3B는 아래를 증명하지 않는다.

```text
- real robot success
- physical robot readiness
- live UR runtime support
- live ROS2-DDS runtime support
- Franka hardware support
- deployable policy readiness
- visual policy performance
- HMD/OpenXR collection readiness
- marketplace readiness
- production certification
- universal robot support
- policy uplift
- learning-proven value
```

특히 adapter 이름에 UR, ROS2-DDS, Franka가 포함되더라도 이번 slice는
`source-shaped recorded-log fixture compatibility`를 증명할 뿐, live hardware/runtime
support를 증명하지 않는다.

Canonical forbidden claim keys for this slice:

```text
real_robot_success
real_robot_success_claimed
physical_robot_readiness
physical_robot_readiness_claimed
deployable_policy_readiness
visual_policy_performance
hmd_openxr_collection_readiness
hmd_readiness
hmd_readiness_claimed
marketplace_readiness
marketplace_readiness_claimed
production_certification
universal_robot_support
universal_robot_support_claimed
policy_uplift
policy_uplift_claimed
learning_proven_value
live_runtime_support
live_runtime_support_claimed
live_ur_runtime_support
live_ros2_dds_runtime_support
franka_hardware_support
public_sample_import
public_sample_import_claimed
public_sample_evidence_claimed
db_migration
db_migration_claimed
production_auth
production_auth_claimed
real_robot_readiness_claimed
production_robot_support_claimed
```

The MVP-3B verifier owns this list. It must scan package config, metadata, registry
snapshots, adapter results, summaries, non-claim attestations, and package README text
recursively enough to reject any truthy claim or unsupported support wording. Existing
producer validators may enforce a smaller generic set, but they are not the authority
for this proof package.

## Scope

MVP-3B가 여는 변수는 하나다.

```text
changed_variable=source_adapter_matrix
task_family=connector_or_peg_in_hole_recorded_log_projection
source_evidence_level=generated_or_file_backed_recorded_log_fixture
policy_evaluation=not_opened
learning_proven_addendum=absent_by_default
```

Adapter matrix:

```text
required_adapters:
  - franka_research_arm
  - robotis_sh5_ros2_dds
  - universal_robots_ur_industrial_arm

optional_later_adapter:
  - universal_robots_ur_external_style
```

Spent held-out discipline:

```text
spent_no_reuse:
  - 40000-40049
  - 42000-42049

opened_in_mvp3b:
  - none
```

MVP-3B Infrastructure Closed does not require calibration or held-out policy evaluation.
If a later learning-proven addendum is attempted, it must use fresh pre-registered ranges
disjoint from `40000-40049` and `42000-42049`.

The verifier must treat the spent/opened contract as fixed, not producer-declared:

```text
required_spent_no_reuse_exact:
  - 40000-40049
  - 42000-42049

required_opened_ranges:
  calibration: none
  heldout: none
  tuning: none
  closure: none
```

## Architecture

MVP-3B builds on the existing robot embodiment adapter surface and the normalized
trajectory contract validator.

```text
source log fixture bundle
  -> RobotEmbodimentAdapterRegistry
  -> RobotEmbodimentAdapter.project_source_evidence()
  -> NormalizedTrajectoryContractValidator
  -> source-adapter matrix package builder
  -> docs/proof/mvp3b_source_adapter_matrix_proof_package/
  -> stdlib-only source-adapter package verifier
```

Producer responsibilities:

```text
- build or read source log fixture bundles for each required adapter
- project each source bundle into accepted/rejected trajectories and evaluations
- generate curation manifests and normalized trajectory contracts
- hash-lock source logs and projected artifacts
- emit adapter result summaries
- assemble a self-contained package under docs/proof/
- record non-claims as hash-locked false claims
```

Producer non-responsibilities:

```text
- no live UR/RTDE connection
- no live ROS2-DDS connection
- no real Franka hardware connection
- no policy training
- no held-out policy evaluation
- no MVP-2 or MVP-3A artifact mutation
```

Verifier responsibilities:

```text
scripts/verify_mvp3b_source_adapter_package.py
  - stdlib-only Python 3.11
  - read package_manifest.json
  - verify every data/ JSON and JSONL hash
  - verify required adapter set is exact
  - verify source log bundle completeness for each adapter
  - verify source metadata claim boundaries are false for live/hardware/support claims
  - verify projected artifact records match actual files and hashes
  - verify normalized contract required fields and action-role coverage
  - verify accepted/rejected counts and curation manifest consistency
  - verify package summary is cached only and matches recomputation
  - verify non-claims attestation has no truthy forbidden claim
  - verify canonical forbidden claims across config, metadata, summaries,
    adapter results, registry snapshot, and README text
  - verify spent_no_reuse is exactly [40000-40049, 42000-42049]
  - verify MVP-3B opens no calibration, held-out, tuning, or closure range
  - verify learning_proven_addendum remains absent unless a separate fresh-range
    addendum package is explicitly present and independently verifiable
```

The verifier should not import `app.services.robot_embodiment_adapters` or
`app.services.normalized_trajectory_contract`. Producer and auditor must remain
independent.

## Package Layout

MVP-3B package:

```text
docs/proof/mvp3b_source_adapter_matrix_proof_package/
  README.md
  package_manifest.json
  data/
    config.json
    adapter_registry_snapshot.json
    source_adapter_matrix_summary.json
    non_claims_attestation.json
    artifact_index.json
    source_logs/
      franka_research_arm/
        metadata.json
        accepted_command_state.jsonl
        rejected_command_state.jsonl
      robotis_sh5_ros2_dds/
        metadata.json
        accepted_command_state.jsonl
        rejected_command_state.jsonl
      universal_robots_ur_industrial_arm/
        metadata.json
        accepted_command_state.jsonl
        rejected_command_state.jsonl
    projections/
      <adapter_id>/
        projection_manifest.json
        curation_manifest.json
        trajectories/
          accepted.json
          rejected.json
        evaluations/
          accepted.json
          rejected.json
    contracts/
      franka_research_arm_normalized_trajectory_contract.json
      robotis_sh5_ros2_dds_normalized_trajectory_contract.json
      universal_robots_ur_industrial_arm_normalized_trajectory_contract.json
    adapter_results/
      franka_research_arm_adapter_result.json
      robotis_sh5_ros2_dds_adapter_result.json
      universal_robots_ur_industrial_arm_adapter_result.json
```

`data/source_logs/`, `data/projections/`, `data/contracts/`, and
`data/adapter_results/` are verdict-critical. They must be git-trackable and
hash-indexed.

`source_adapter_matrix_summary.json` is cached summary only. It is never the source
of truth.

## Config Contract

Example:

```json
{
  "proof_slice": "mvp3b_source_adapter_matrix",
  "claim_tier": "source_adapter_infrastructure",
  "changed_variable": "source_adapter_matrix",
  "required_adapters": [
    "franka_research_arm",
    "robotis_sh5_ros2_dds",
    "universal_robots_ur_industrial_arm"
  ],
  "source_evidence_level": "generated_or_file_backed_recorded_log_fixture",
  "spent_no_reuse": [
    [40000, 40049],
    [42000, 42049]
  ],
  "opened_ranges": {
    "calibration": [],
    "heldout": [],
    "tuning": [],
    "closure": []
  },
  "learning_proven_addendum": "absent",
  "non_claims": {
    "real_robot_success": false,
    "physical_robot_readiness": false,
    "live_ur_runtime_support": false,
    "live_ros2_dds_runtime_support": false,
    "franka_hardware_support": false,
    "deployable_policy_readiness": false,
    "visual_policy_performance": false,
    "hmd_openxr_collection_readiness": false,
    "marketplace_readiness": false,
    "production_certification": false,
    "universal_robot_support": false,
    "policy_uplift": false,
    "learning_proven_value": false
  }
}
```

## Hard-Fail Criteria

The verifier must fail if any of the following are true:

```text
1. missing or extra required adapter in the package
2. package data file exists but is not listed in artifact_index/package_manifest
3. any data file hash mismatch
4. missing source log file for any adapter
5. source metadata claims live runtime, physical robot readiness, public sample import,
   or real robot success
6. source metadata adapter_id/robot_family/runtime does not match registry snapshot
7. projection manifest source log hash does not match package source log bytes
8. projected artifact path/hash records do not match files
9. accepted/rejected counts disagree between source logs, projection manifest,
   curation manifest, adapter result, and summary
10. normalized trajectory contract missing required source fields
11. normalized trajectory contract missing required action roles:
    teleop_intent, executed_control, learning_action, retargeted_robot_action
12. frame_action_role_coverage reports missing or mismatched required roles
13. replay/action/trainer-smoke gates needed for learning eligibility are not explicit
14. non_claims_attestation contains any truthy forbidden claim
15. any canonical forbidden claim key is truthy in config, metadata, registry snapshot,
    adapter results, summary, non-claim attestation, or README text
16. `spent_no_reuse` is not exactly `[[40000, 40049], [42000, 42049]]`
17. any calibration, held-out, tuning, or closure range is opened in MVP-3B
18. learning_proven_addendum is present without separate fresh held-out evidence
19. any package uses spent held-out ranges as tuning or closure evidence
```

If trainer-smoke or export-smoke artifacts are produced to satisfy existing contract
validators, the package must label them as contract/export smoke only:

```text
learning_results_measured=false
policy_uplift=false
learning_proven_value=false
```

## Testing Strategy

RED tests before implementation:

```text
- verifier rejects missing adapter
- verifier rejects extra adapter
- verifier rejects source log hash tamper
- verifier rejects unindexed data file
- verifier rejects truthy live runtime / real robot / policy uplift claim
- verifier rejects truthy producer claim keys such as `physical_robot_readiness_claimed`,
  `real_robot_success_claimed`, `public_sample_evidence_claimed`, and
  `live_runtime_support`
- verifier rejects missing or altered exact spent_no_reuse contract
- verifier rejects any non-empty opened calibration/heldout/tuning/closure range
- verifier rejects learning_proven_addendum present without fresh-range addendum evidence
- verifier rejects contract missing action role
- verifier rejects projection manifest hash drift
- verifier rejects summary count override
```

GREEN path:

```text
- runner builds matrix package from repo-local fixtures
- verifier returns VERIFIED
- existing normalized contract validator tests continue passing
- MVP-3A verifier still returns VERIFIED
- MVP-2 verifier still returns VERIFIED
```

## Success Criteria

MVP-3B Source-Adapter Infrastructure Closed when:

```text
- package exists under docs/proof/mvp3b_source_adapter_matrix_proof_package/
- required adapters all emit passed normalized trajectory contracts
- source logs and projected artifacts are self-contained and hash-locked
- stdlib verifier recomputes package status as source_adapter_infrastructure_closed
- all non-claims are false
- no held-out policy range is opened
- docs explain that this is not live robot support
```

MVP-3B Learning-Proven Addendum remains absent unless a later fresh held-out policy
evaluation is pre-registered, executed, packaged, and verified.

## Explicit Non-Goals

```text
- no actual UR runtime
- no actual ROS2-DDS runtime
- no actual Franka hardware
- no real robot control
- no policy uplift claim
- no trainer tuning
- no held-out policy A/B
- no DB migration
- no marketplace or production auth
- no modification of frozen MVP-2/MVP-3A proof packages
```

## Next Step

Use ralplan to convert this spec into an implementation plan with:

```text
- source fixture/package builder task sequence
- independent verifier task sequence
- TDD tamper matrix
- documentation and handoff updates
- verification commands
```
