# Spec: MVP-3C Isaac Sim Embodiment Source Closed

Date: 2026-06-22
Status: RALPLAN CONSENSUS APPROVED
Branch: `codex/mvp3c-isaac-sim-embodiment-source`

## Objective

MVP-3C의 목적은 MVP-3A/B에서 닫은 proof discipline을 generated/file-backed
fixture 밖으로 한 단계 올리는 것이다. 이번 slice는 실제 UR/Franka 하드웨어를
사용하지 않는다. 대신 Linux Isaac Sim runtime 안에서 UR + Franka embodiment source를
실행 또는 로드하고, 그 runtime-backed command/state source evidence가 Robot Data
Forge의 normalized trajectory contract와 self-contained proof package discipline을
통과하는지 검증한다.

이번 slice의 이름은 다음 claim tier를 분리한다.

```text
MVP-3C Isaac Sim Embodiment Source Closed
  Franka + Universal Robots UR Isaac Sim runtime-backed embodiment source logs are
  recorded, projected through RDF adapter infrastructure, packaged as self-contained
  evidence, and independently verified.

MVP-3C Learning-Proven Addendum
  이번 slice의 기본 목표가 아니다. 별도 fresh held-out policy evaluation이 있을 때만
  나중에 생성한다.
```

이 분리는 MVP-2, MVP-3A, MVP-3B에서 지킨 `proof-infrastructure`와
`learning-proven` 경계를 유지하기 위한 제품 계약이다.

## Current MVP-3 Position

MVP-3의 전체 닫힘 기준은 다음 세 slice로 정의한다.

```text
MVP-3A: task_variant expansion
  새 target / fixture pose variant에서 proof package discipline과 actual Isaac
  learning-proven addendum이 반복됨.

MVP-3B: source_adapter_matrix expansion
  UR / ROS2-DDS / Franka-style generated/file-backed recorded-log fixture source가
  RDF adapter/package/verifier discipline을 통과함.

MVP-3C: isaac_sim_embodiment_source expansion
  UR + Franka Isaac Sim runtime-backed source evidence가 RDF adapter/package/verifier
  discipline을 통과함.
```

MVP-3C가 닫히면 MVP-3는 다음 문장으로 요약할 수 있다.

```text
Robot Data Forge proof discipline generalized across a new task variant,
source-adapter fixture profiles, and Isaac Sim runtime-backed embodiment sources.
```

## Brainstorming

### Option A: Franka Only

```text
changed_variable=isaac_sim_embodiment_source
embodiments=[franka_panda_isaac_sim]
```

최적화:

- 성공 확률이 높다.
- 기존 Isaac/Franka 경로와 가장 잘 맞는다.
- MVP-3C preflight로 좋다.

Tradeoff:

- MVP-3B의 multi-adapter story와 연결이 약하다.
- MVP-3C가 "generated fixture 밖으로 나갔다"는 의미는 생기지만, cross-embodiment
  확장성은 약하게 보인다.

### Option B: UR + Franka

```text
changed_variable=isaac_sim_embodiment_source_pair
embodiments=[
  franka_panda_isaac_sim,
  universal_robots_ur10e_isaac_sim
]
```

최적화:

- 실제 기기가 없어도 두 embodiment source가 Isaac Sim runtime-backed evidence로 닫힌다.
- MVP-3B의 Franka/UR source-profile projection이 runtime-backed source로 한 단계
  강화된다.
- MVP-3의 초기 구상인 task/source/embodiment expansion과 가장 잘 맞는다.

Tradeoff:

- UR asset import, articulation, controller, action/state extraction setup에서 막힐 수 있다.
- Franka와 UR의 command/state schema를 공통 package contract로 묶어야 한다.

### Option C: UR + Franka + ROS2-DDS Bridge

```text
changed_variable=isaac_sim_embodiment_source_and_ros2_bridge
embodiments=[franka_panda_isaac_sim, universal_robots_ur10e_isaac_sim]
transport=ros2_dds_bridge
```

최적화:

- 가장 강한 integration story다.

Tradeoff:

- ROS 2 bridge/live runtime support claim과 혼동될 위험이 크다.
- Docker/host DDS, domain id, middleware, bridge extension, message schema risk가 동시에 열린다.
- MVP-3C의 proof objective보다 integration surface가 커진다.

### Option D: Generated Fixture Robustness Addendum

```text
changed_variable=source_adapter_fixture_robustness
```

최적화:

- 빠르고 안정적이다.

Tradeoff:

- MVP-3B와 너무 비슷하다.
- "runtime-backed source evidence" gap을 닫지 못한다.

## Decision

MVP-3C는 Option B, **UR + Franka Isaac Sim Embodiment Source Pair**로 진행한다.

선택 이유:

- 사용자는 실제 UR/Franka 기기를 갖고 있지 않다. Isaac Sim runtime-backed source는
  실제 하드웨어 없이도 source/embodiment expansion을 검증할 수 있는 가장 정직한 중간
  단계다.
- MVP-3B에서 이미 UR/Franka-style fixture projection은 닫혔다. MVP-3C는 같은 이름의
  source profile을 generated fixture가 아니라 Isaac Sim runtime-backed evidence로
  끌어올린다.
- ROS2-DDS bridge까지 이번 slice에 넣으면 live bridge support claim과 범위가 흐려진다.
  ROS2-DDS는 MVP-3D 또는 별도 bridge-readiness slice로 남긴다.

선택이 바뀌는 조건:

- UR asset/controller setup이 preflight에서 fail-closed되면 scope 이름을
  `MVP-3C-Franka Isaac Sim Embodiment Source Closed`로 낮추고, UR은
  `UR preflight failed with evidence`로 남긴다.
- Franka와 UR이 모두 preflight에서 실패하면 MVP-3C는 닫지 않는다. 실패 원인을
  `MVP-3C Preflight Fail-Closed` artifact로 남기고 implementation을 중단한다.
- ROS2 bridge가 이미 안정적으로 설정되어 있고 proof surface를 키우지 않아도 되면
  후속 addendum으로만 검토한다. MVP-3C 본체에는 넣지 않는다.

## Primary Claim

MVP-3C의 primary claim은 다음 문장으로 제한한다.

```text
Given Linux Isaac Sim runtime-backed Franka and Universal Robots UR embodiment
source logs, Robot Data Forge can project those command/state streams into
normalized robot-action trajectory contracts and ship a self-contained proof
package whose source logs, runtime metadata, projected artifacts, contracts,
claim boundaries, and package manifest are independently verifiable.
```

Equivalently, MVP-3C proves Isaac Sim runtime-backed embodiment source ingestion for
two simulated robot embodiments. It does not prove physical hardware integration.

## Non-Claims

MVP-3C는 아래를 증명하지 않는다.

```text
- real robot success
- physical robot readiness
- live UR hardware support
- live Franka hardware support
- live ROS2-DDS runtime support
- deployable policy readiness
- visual policy performance
- HMD/OpenXR collection readiness
- marketplace readiness
- production certification
- universal robot support
- policy uplift
- learning-proven value
- public sample compatibility
```

특히 `UR`, `Franka`, `Isaac Sim`, `ROS2`라는 이름이 package에 등장하더라도 이번 slice는
`Isaac Sim runtime-backed source evidence`만 증명한다. Real robot, live bridge,
deployment, policy learning value는 열지 않는다.

Canonical forbidden claim keys for this slice:

```text
real_robot_success
real_robot_success_claimed
physical_robot_readiness
physical_robot_readiness_claimed
deployable_policy_readiness
deployable_policy_readiness_claimed
visual_policy_performance
visual_policy_performance_claimed
hmd_openxr_collection_readiness
hmd_openxr_collection_readiness_claimed
hmd_readiness
hmd_readiness_claimed
marketplace_readiness
marketplace_readiness_claimed
production_certification
production_certification_claimed
universal_robot_support
universal_robot_support_claimed
policy_uplift
policy_uplift_claimed
learning_proven_value
learning_proven_value_claimed
live_runtime_support
live_runtime_support_claimed
live_ur_runtime_support
live_ur_runtime_support_claimed
live_ur_hardware_support
live_ur_hardware_support_claimed
live_franka_hardware_support
live_franka_hardware_support_claimed
live_ros2_dds_runtime_support
live_ros2_dds_runtime_support_claimed
franka_hardware_support
franka_hardware_support_claimed
ur_hardware_support
ur_hardware_support_claimed
ros2_bridge_support
ros2_bridge_support_claimed
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

The MVP-3C verifier owns this list for the MVP-3C package. It must recursively scan
config, runtime metadata, source logs, adapter results, summaries, non-claim
attestations, and package README text enough to reject truthy claim drift.

## Scope

MVP-3C가 여는 변수는 하나다.

```text
changed_variable=isaac_sim_embodiment_source_pair
task_family=connector_or_peg_in_hole_source_capture
runtime=isaac_sim
platform=linux
embodiments=[
  franka_panda_isaac_sim,
  universal_robots_ur10e_isaac_sim
]
source_kind=isaac_sim_runtime_backed_command_state_log
```

MVP-3C가 열지 않는 변수:

```text
opened_calibration_range=[]
opened_heldout_range=[]
opened_tuning_range=[]
opened_closure_range=[]
policy_training=false
policy_eval=false
learning_proven_addendum=absent
ros2_live_bridge=false
real_robot_hardware=false
marketplace=false
production_auth=false
```

Spent/no-reuse discipline:

```text
spent_no_reuse=[
  [40000, 40049],
  [42000, 42049]
]
```

MVP-3C는 policy held-out proof를 열지 않으므로 fresh held-out range를 쓰지 않는다.
나중에 MVP-3C Learning-Proven Addendum을 만들려면 fresh pre-registered
calibration/held-out range를 별도 spec에서 새로 잡아야 한다.

## Evidence Levels

MVP-3C는 evidence level을 명시적으로 구분한다.

```text
Level 0: generated fixture
  MVP-3B 수준. Isaac Sim runtime metadata가 없다.

Level 1: Isaac Sim asset preflight
  robot asset/articulation/controller/action-state extraction 가능성을 확인한다.
  proof package closed는 아니다.

Level 2: Isaac Sim runtime-backed source log
  Isaac Sim process에서 command/state source log와 runtime metadata를 기록한다.
  MVP-3C package source evidence가 될 수 있다.

Level 3: Isaac Sim task/evaluator-backed rollout
  task success/evaluation까지 포함한다. MVP-3C 본체의 필수 조건은 아니다.

Level 4: learning-proven policy eval
  fresh held-out policy A/B. MVP-3C 본체 범위 밖이다.
```

MVP-3C Closed의 최소 evidence level은 Level 2다.

## Architecture

MVP-3C는 MVP-3B package discipline을 runtime-backed source로 확장한다.

```text
Isaac Sim source capture
  -> per-embodiment runtime metadata
  -> command/state source logs
  -> RDF IsaacSimEmbodimentSourceAdapter
  -> normalized trajectory contract
  -> self-contained package under docs/proof/
  -> stdlib-only independent verifier
```

Producer 책임:

```text
- Isaac Sim preflight를 실행한다.
- Franka와 UR asset/runtime metadata를 기록한다.
- command/state source log를 생성한다.
- source log를 RDF adapter로 projection한다.
- normalized trajectory contract를 만든다.
- package data/ 아래에 verdict-critical JSON/JSONL evidence를 복사한다.
- package manifest와 artifact index를 생성한다.
- non-claim attestation을 hash-lock한다.
```

Producer 비책임:

```text
- 실제 UR/Franka 하드웨어를 제어하지 않는다.
- ROS2-DDS live bridge support를 주장하지 않는다.
- policy training/eval을 실행하지 않는다.
- MVP-2, MVP-3A, MVP-3B proof package를 수정하지 않는다.
- held-out range를 열지 않는다.
```

Verifier 책임:

```text
scripts/verify_mvp3c_isaac_sim_embodiment_source_package.py
  - package_manifest.json을 읽는다.
  - data/ artifact hash를 재계산한다.
  - required embodiment set이 정확한지 확인한다.
  - source log와 runtime metadata 존재를 확인한다.
  - per-embodiment preflight required fields를 verifier-owned constant로 확인한다.
  - 각 source row의 runtime_capture_id가 hash-bound runtime metadata와 연결되는지 확인한다.
  - source log row count와 accepted/rejected counts를 재계산한다.
  - runtime metadata가 Isaac Sim source임을 검증한다.
  - projection manifest와 source log hash binding을 확인한다.
  - normalized trajectory contract의 source fields, action roles, frame/action role
    coverage를 검증한다.
  - non-claim attestation과 forbidden claim recursive scan을 수행한다.
  - spent_no_reuse가 [[40000,40049],[42000,42049]]와 정확히 일치하는지 확인한다.
  - opened calibration/held-out/tuning/closure range가 비어 있는지 확인한다.
  - source summary cache가 source-of-truth artifact 재계산과 일치하는지 확인한다.
```

Verifier 비책임:

```text
- Isaac Sim을 실행하지 않는다.
- producer adapter code를 import하지 않는다.
- physical hardware integration을 검증하지 않는다.
- policy uplift를 검증하지 않는다.
```

## Package Layout

MVP-3C package는 MVP-2, MVP-3A, MVP-3B package와 분리한다.

```text
docs/proof/mvp3c_isaac_sim_embodiment_source_proof_package/
  README.md
  package_manifest.json
  data/
    config.json
    artifact_index.json
    non_claims_attestation.json
    isaac_sim_runtime_summary.json
    embodiment_source_summary.json
    runtime_metadata/
      franka_panda_isaac_sim_runtime_metadata.json
      universal_robots_ur10e_isaac_sim_runtime_metadata.json
    source_logs/
      franka_panda_isaac_sim/
        metadata.json
        accepted_command_state.jsonl
        rejected_command_state.jsonl
      universal_robots_ur10e_isaac_sim/
        metadata.json
        accepted_command_state.jsonl
        rejected_command_state.jsonl
    projections/
      franka_panda_isaac_sim/
        projection_manifest.json
        curation_manifest.json
        trajectories/
        evaluations/
      universal_robots_ur10e_isaac_sim/
        projection_manifest.json
        curation_manifest.json
        trajectories/
        evaluations/
    contracts/
      franka_panda_isaac_sim_normalized_trajectory_contract.json
      universal_robots_ur10e_isaac_sim_normalized_trajectory_contract.json
    adapter_results/
      franka_panda_isaac_sim_adapter_result.json
      universal_robots_ur10e_isaac_sim_adapter_result.json
    preflight/
      franka_panda_isaac_sim_preflight.json
      universal_robots_ur10e_isaac_sim_preflight.json
```

`embodiment_source_summary.json` is cached summary only. It is never the source of
truth for verifier verdicts.

## Isaac Sim Preflight Contract

Preflight는 MVP-3C implementation에서 가장 먼저 닫아야 한다.

Franka preflight must report:

```text
embodiment_id=franka_panda_isaac_sim
runtime_capture_id=<non-empty stable id>
asset_loaded=true
articulation_detected=true
joint_state_readable=true
action_command_writable=true
source_log_rows_emitted>=2
runtime_metadata_recorded=true
```

UR preflight must report:

```text
embodiment_id=universal_robots_ur10e_isaac_sim
runtime_capture_id=<non-empty stable id>
asset_loaded=true
articulation_detected=true
joint_state_readable=true
action_command_writable=true
source_log_rows_emitted>=2
runtime_metadata_recorded=true
```

If UR preflight fails:

```text
target_status=fail_closed
allowed_fallback=MVP-3C-Franka Isaac Sim Embodiment Source Closed
required_artifact=UR preflight failed with evidence
not_allowed=silent downgrade while still claiming UR+Franka MVP-3C Closed
```

If Franka preflight fails:

```text
target_status=fail_closed
allowed_fallback=none for MVP-3C Closed
required_artifact=MVP-3C preflight fail-closed report
```

## Success Criteria

MVP-3C UR + Franka Closed requires all of:

```text
- Franka Isaac Sim preflight passes.
- UR Isaac Sim preflight passes.
- Source rows bind to per-embodiment runtime_capture_id values.
- Each runtime_capture_id resolves to a hash-bound data/runtime_metadata artifact.
- Franka source log is recorded from Isaac Sim runtime metadata.
- UR source log is recorded from Isaac Sim runtime metadata.
- Both source logs are projected through RDF adapter infrastructure.
- Both normalized trajectory contracts pass validation.
- Self-contained package exists under docs/proof/mvp3c_isaac_sim_embodiment_source_proof_package/.
- Stdlib-only verifier recomputes package status as isaac_sim_embodiment_source_closed.
- Verifier rejects hash-refreshed semantic tamper for forbidden claims, counts, runtime metadata,
  source/projection binding, contract roles, opened ranges, and spent range drift.
- MVP-2, MVP-3A, and MVP-3B verifiers remain VERIFIED.
- full pytest and ruff pass.
```

Package status values:

```text
isaac_sim_embodiment_source_closed
franka_only_isaac_sim_embodiment_source_closed
preflight_failed_closed
```

Only `isaac_sim_embodiment_source_closed` closes the original MVP-3C target.
`franka_only_isaac_sim_embodiment_source_closed` is a renamed fallback, not the original
UR + Franka close.

## Testing Strategy

Verifier-first TDD:

```text
1. RED tests for scripts/verify_mvp3c_isaac_sim_embodiment_source_package.py.
2. GREEN verifier implementation using synthetic self-contained fixtures only for
   verifier mechanics and negative closure tests.
3. RED tests for preflight runner and package builder.
4. GREEN producer implementation.
5. Isaac Sim preflight execution.
6. Package generation from real Isaac Sim runtime-backed source logs.
7. Real generated package tamper matrix.
8. Full regression and frozen proof verification.
```

Synthetic/self-contained fixtures are not closure evidence. They must not verify as
`isaac_sim_embodiment_source_closed`, even if their hashes are refreshed and their
metadata is plausible. Original MVP-3C closure is allowed only for the runtime package
created from G005 Isaac Sim runtime evidence and then defended by the G006 tamper
matrix.

Minimum tamper matrix:

```text
- plausible synthetic package tries to assert isaac_sim_embodiment_source_closed
- preflight boolean changed from true to false
- source row runtime_capture_id changed
- source row embodiment_id changed
- runtime metadata file removed
- source-row/runtime-metadata mismatch
- source log byte tamper
- runtime metadata runtime changed away from Isaac Sim
- source log row count override
- accepted/rejected count override
- projection source hash mismatch
- contract source field drift
- required action role removed
- non-claim truthy field
- README positive forbidden claim text
- spent_no_reuse changed
- opened held-out/tuning/closure range
- summary cache override
- manifest data-file removal
```

## Implementation Workflow Recommendation

MVP-3C는 `ultragoal`로 구현한다.

이유:

```text
- preflight, verifier, producer, Isaac runtime execution, package generation, tamper tests,
  documentation, final review가 순차 의존성을 가진다.
- UR 실패 시 scope rename 또는 fail-closed artifact가 필요한 branching workflow다.
- final quality gate가 code-reviewer + architect 독립 검수까지 요구된다.
```

Recommended top-level flow:

```text
1. Brainstorming/spec approval
2. ralplan --deliberate for implementation plan
3. ultragoal create-goals from approved plan
4. ultragoal execute sequential tasks
5. Use subagent-driven-development inside independent tasks only
6. Use sh-goal only for small bounded diagnostics or recovery loops
7. Final ultragoal quality gate
8. PR, CI, merge, tag
```

`sh-goal` is not the top-level recommendation for MVP-3C because MVP-3C is not a
single small active slice. It is better used as a local diagnostic loop when Isaac Sim
preflight or package verification hits a bounded blocker.

## External References

Primary implementation should use repo-local evidence and installed Isaac environment.
Official Isaac references that justify feasibility:

```text
Isaac Sim ROS 2 installation / bridge setup:
https://docs.isaacsim.omniverse.nvidia.com/6.0.0/installation/install_ros.html

Isaac Sim URDF importer:
https://docs.isaacsim.omniverse.nvidia.com/6.0.0/importer_exporter/ext_isaacsim_asset_importer_urdf.html

Isaac Sim manipulator import / UR10e + Robotiq tutorial:
https://docs.isaacsim.omniverse.nvidia.com/6.0.0/robot_setup_tutorials/tutorial_import_assemble_manipulator.html

Isaac Sim robot USD assets, including Franka and Universal Robots families:
https://docs.isaacsim.omniverse.nvidia.com/4.5.0/assets/usd_assets_robots.html
```

These references do not create a live hardware support claim.

## Explicit Non-Goals

```text
- no real robot control
- no ROS2-DDS live bridge support claim
- no deployment readiness claim
- no visual policy claim
- no HMD/OpenXR collection readiness claim
- no policy uplift or learning-proven claim
- no public sample import claim
- no marketplace or production auth work
- no DB migration
- no fresh held-out policy evaluation
```

## Stop Rules

Stop implementation and write a fail-closed artifact if:

```text
- Isaac Sim is unavailable or cannot launch in the target Linux environment.
- Franka asset/articulation/action-state extraction fails.
- UR asset/articulation/action-state extraction fails and the user has not approved the
  explicit Franka-only fallback rename.
- Source log rows cannot be generated from runtime-backed metadata.
- Verifier needs producer service imports to pass.
- Package source evidence would be storage-local instead of git-tracked/self-contained.
- Any forbidden claim must be weakened to make the package pass.
- MVP-2/MVP-3A/MVP-3B frozen verifiers regress.
```

## Expected Final Tag

If UR + Franka MVP-3C closes:

```text
mvp3c-v0.1-isaac-sim-ur-franka-embodiment-source
```

If only Franka closes after explicit fallback rename:

```text
mvp3c-v0.1-franka-isaac-sim-embodiment-source
```

Do not tag a fallback as the original UR + Franka scope.
