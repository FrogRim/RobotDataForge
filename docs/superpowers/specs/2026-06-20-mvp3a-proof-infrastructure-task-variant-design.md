# Spec: MVP-3A Proof-Infrastructure Closed - Target / Fixture Pose Variant

Date: 2026-06-20
Status: DRAFT FOR USER REVIEW
Branch: `codex/mvp3-heldout-closure-spine`

## Objective

MVP-3의 전체 방향은 Robot Data Forge proof discipline을 새 task, source,
embodiment, adapter로 확장하는 것이다. 단, 첫 slice인 MVP-3A는 adapter 확장이
아니다. MVP-3A는 같은 Isaac source와 같은 connector-insertion evaluator family 안에서
새 task variant를 열어, MVP-2에서 만든 proof spine / package / verifier discipline이
반복 가능한지 검증한다.

이번 slice의 이름은 다음 두 claim tier를 분리한다.

```text
MVP-3A Proof-Infrastructure Closed
  새 target / fixture pose task variant에서 proof spine, package, verifier,
  fresh held-out discipline이 actual Isaac evidence 위에서 반복됨.

MVP-3A Learning-Proven Addendum
  같은 새 variant에서 curated candidate가 uncurated baseline보다 fresh held-out에서
  유의미하게 높은 success rate를 냄.
```

이 분리는 MVP-2에서 지킨 `learning-ready`와 `learning-proven` 경계를 MVP-3에서도
유지하기 위한 제품 계약이다. Infrastructure proof가 닫혀도 uplift가 없으면
learning-proven claim은 생성하지 않는다.

## Primary Claim

MVP-3A의 primary claim은 다음 문장으로 제한한다.

```text
Given a new target / fixture pose variant in the current Isaac connector-insertion
evaluator family, Robot Data Forge can repeat the proof package discipline:
fresh seed ranges, no-reuse guard, closure derivation, manifest/package generation,
and independent verification.
```

Learning-proven addendum은 별도 조건을 통과할 때만 붙는다.

```text
In the same new variant, the curated candidate policy outperformed the uncurated
baseline on the fresh held-out range.
```

## Non-Claims

MVP-3A는 아래를 증명하지 않는다.

```text
- real robot success
- physical robot readiness
- deployable policy readiness
- visual policy performance
- HMD/OpenXR collection readiness
- universal robot support
- UR adapter support
- ROS2-DDS adapter support
- Franka hardware support
- marketplace readiness
- production certification
```

UR, ROS2-DDS, Franka, generated trajectory source는 MVP-3 전체 로드맵의 후속
source/embodiment expansion 후보로 남긴다. MVP-3A에서는 source variable을 열지 않는다.

## Scope

MVP-3A가 여는 변수는 하나다.

```text
changed_variable=task_variant
task_variant=target_fixture_pose_variant
source=isaac_runtime
evaluator_family=connector_insertion
policy_comparator=curated_candidate_vs_uncurated_baseline
```

Fresh seed ranges:

```text
calibration=41000-41029
heldout=42000-42049
rollouts_per_policy=50
spent_after_closure_attempt=42000-42049
already_spent_no_reuse=40000-40049
```

`40000-40049`는 MVP-2 closure에 사용된 spent held-out range이므로 MVP-3A tuning,
calibration, held-out, threshold selection에 재사용하지 않는다. `42000-42049`는
MVP-3A closure attempt 이후 결과와 무관하게 spent/audit-only/no-reuse로 남긴다.

## Architecture

MVP-3A는 frozen MVP-2 archive를 분해하지 않는다. 새 얇은 coordinator runner와 새
generic verifier를 만든다.

```text
actual Isaac run artifacts
  -> config JSON + evidence artifact paths
  -> scripts/run_mvp3a_proof_infrastructure.py
  -> app.services.proof spine
  -> self-contained rollout recompute bundle under docs/proof/mvp3a_target_fixture_pose_variant_proof_package/data/
  -> docs/proof/mvp3a_target_fixture_pose_variant_proof_package/
  -> scripts/verify_proof_package.py
```

Runner의 책임:

```text
- config JSON을 읽는다.
- actual Isaac evidence artifact path를 해시로 묶는다.
- closure 판정에 필요한 작은 rollout JSON을 package `data/rollouts/`로 복사한다.
- C-lite mask evidence가 있으면 package `data/masks/`로 복사한다.
- seed discipline과 spent/no-reuse rule을 검증한다.
- app.services.proof closure spine을 호출한다.
- MVP-3A package manifest와 data/ bundle을 만든다.
- learning-proven addendum 생성 조건을 판정한다.
```

Runner의 비책임:

```text
- Isaac rollout을 직접 실행하지 않는다.
- trainer를 직접 튜닝하지 않는다.
- threshold를 held-out 결과에 맞춰 변경하지 않는다.
- MVP-2 archive script를 import하거나 수정하지 않는다.
```

Verifier의 책임:

```text
scripts/verify_proof_package.py
  - package_manifest.json을 읽는다.
  - data/ artifact hash를 재계산한다.
  - data/rollouts/ JSON에서 rollout count, success count, success rate, uplift,
    confidence interval, learning result를 직접 재계산한다.
  - closure_verdict.json은 expected/cached summary로만 취급하고 source of truth로
    사용하지 않는다.
  - data/gates/ JSON에서 runtime, calibration selection, train trace, post-heldout
    guard source fields를 읽어 non-learning closure gates를 재계산한다.
  - seed range disjointness와 spent/no-reuse를 재검증한다.
  - closure verdict와 package claim consistency를 재계산한다.
  - rollout record에 success, env_native_rollout_success,
    env_native_max_consecutive_success_steps, scenario_id가 있으면 Level B label
    consistency를 검증한다.
  - data/masks/가 있으면 per-step env_native_success_mask에서 max consecutive
    success steps와 rollout success를 재유도한다.
  - non-claim attestation이 모두 false인지 검증한다.
  - learning-proven addendum이 present일 때 uplift 조건을 재검증한다.
  - learning_result=non_closing일 때 learning-proven claim이 없는지 검증한다.
```

Frozen MVP-2 verifier는 변경하지 않는다.

```text
do_not_modify=scripts/verify_mvp2_package.py
do_not_modify=docs/proof/mvp2_learning_proven_evidence_package/
```

## Package Layout

MVP-3A package는 MVP-2 package와 분리한다.

```text
docs/proof/mvp3a_target_fixture_pose_variant_proof_package/
  README.md
  package_manifest.json
  data/
    config.json
    task_variant_attestation.json
    seed_discipline_report.json
    closure_verdict.json
    learning_result_summary.json
    non_claims_attestation.json
    artifact_index.json
    gates/
      runtime_gate.json
      train_generation_runtime_gate.json
      calibration_selection_report.json
      train_trace_summary.json
      post_heldout_guard.json
    rollouts/
      calibration_baseline_rollouts.json
      calibration_candidate_rollouts.json
      heldout_baseline_rollouts.json
      heldout_candidate_rollouts.json
    masks/
      heldout_baseline_success_masks.json
      heldout_candidate_success_masks.json
  addenda/
    learning_proven/
      package_manifest.json
      learning_proven_report.json
```

`addenda/learning_proven/`은 positive uplift 조건을 통과한 경우에만 생성한다. Uplift가
없거나 음수이면 addendum directory를 만들지 않고, package는 infrastructure evidence로
남긴다.

`data/rollouts/`는 필수다. 외부 감사자는 이 네 파일만으로 calibration/held-out count,
success count, success rate, held-out uplift, confidence interval, addendum condition,
non-closing condition을 재계산할 수 있어야 한다. `closure_verdict.json`,
`learning_result_summary.json`, `artifact_index.json`, `package_manifest.json`은 검증 대상
요약과 hash index일 뿐 verdict-critical source of truth가 아니다.

`data/gates/`도 필수다. Runtime, calibration selection, train trace count,
post-heldout guard는 `closure_verdict.json` 안의 boolean을 믿지 않고 `data/gates/`의
작은 self-contained JSON에서 재계산한다.

`data/masks/`는 C-lite evidence layer다. Full trace 100개를 git에 넣지 않고도 감사자가
다음 사슬을 재계산하게 한다.

```text
per-step env_native_success_mask
  -> env_native_max_consecutive_success_steps
  -> success == (max_consecutive >= stable_steps_required)
  -> success count
  -> success rate
  -> uplift
```

Mask bundle이 없으면 verifier는 Level B까지만 수행한다. Mask bundle이 있으면 C-lite
검증까지 수행한다. Full trace tarball은 이 spec의 필수 산출물이 아니다.

단, `evidence_kind=actual_isaac`인 패키지는 mask bundle이 선택 사항이 아니다.
Actual-Isaac tier는 `data/masks/`를 반드시 포함해야 하며 verifier는 각 held-out rollout의
`(seed, scenario_id)`와 mask record를 1:1로 대조한다. 총 success count만 맞는 것은 충분하지
않다. 각 mask에서 재유도한 `max_consecutive`와 `success`가 해당 rollout row의
`env_native_max_consecutive_success_steps`, `success`와 일치해야 한다.

Actual-Isaac tier는 policy provenance binding도 필수다.

```text
data/policies/
  baseline_policy_artifact.json
  candidate_policy_artifact.json
```

Verifier는 각 policy artifact의 canonical payload hash
(`policy_artifact_sha256` 자기 필드 제외)를 재계산하고, calibration/held-out rollout row의
`policy_artifact_sha256`가 role별 policy artifact hash와 일치하는지 확인한다. 따라서
`evidence_kind: actual_isaac` 한 줄만 바꿔서는 `proof_infrastructure_closed`를 mint할 수 없다.

## Config Contract

Runner input은 JSON config 하나와 실제 evidence artifact path들이다.

```json
{
  "proof_slice": "mvp3a_target_fixture_pose_variant",
  "evidence_kind": "actual_isaac",
  "claim_tier": "proof_infrastructure",
  "task_variant": {
    "family": "connector_insertion",
    "variant": "target_fixture_pose_variant",
    "changed_variable": "task_variant",
    "source_variable_opened": false
  },
  "runtime_expectations": {
    "backend": "isaac_runtime",
    "proof_runtime": "dedicated_isaac_connector_insertion_evaluator",
    "training_source": "isaac_runtime"
  },
  "seed_ranges": {
    "train": [43000, 43049],
    "calibration": [41000, 41029],
    "heldout": [42000, 42049],
    "spent_no_reuse": [[40000, 40049]]
  },
  "thresholds": {
    "uplift_min": 0.2,
    "min_calibration_rollouts_per_policy": 30,
    "min_heldout_rollouts_per_policy": 50,
    "stable_steps_required": 10
  },
  "audit_ci": {
    "method": "bootstrap_success_rate_difference",
    "iterations": 10000,
    "seed": 20260620
  },
  "evidence_paths": {
    "baseline_calibration_rollouts": "storage/proof_evidence/mvp3a_target_fixture_pose_variant/baseline_calibration_rollouts.json",
    "candidate_calibration_rollouts": "storage/proof_evidence/mvp3a_target_fixture_pose_variant/candidate_calibration_rollouts.json",
    "baseline_heldout_rollouts": "storage/proof_evidence/mvp3a_target_fixture_pose_variant/baseline_heldout_rollouts.json",
    "candidate_heldout_rollouts": "storage/proof_evidence/mvp3a_target_fixture_pose_variant/candidate_heldout_rollouts.json",
    "baseline_policy_artifact": "storage/proof_evidence/mvp3a_target_fixture_pose_variant/baseline_policy_artifact.json",
    "candidate_policy_artifact": "storage/proof_evidence/mvp3a_target_fixture_pose_variant/candidate_policy_artifact.json",
    "heldout_baseline_success_masks": "storage/proof_evidence/mvp3a_target_fixture_pose_variant/heldout_baseline_success_masks.json",
    "heldout_candidate_success_masks": "storage/proof_evidence/mvp3a_target_fixture_pose_variant/heldout_candidate_success_masks.json"
  },
  "package_policy": {
    "output_dir": "docs/proof/mvp3a_target_fixture_pose_variant_proof_package",
    "freeze_mvp2_assets": true,
    "copy_rollout_json_into_package": true,
    "copy_c_lite_masks_into_package_when_present": true
  }
}
```

Config에 `source_variable_opened=true`가 들어오면 MVP-3A runner와 verifier는 모두
fail-closed 한다.
Source/adapter expansion은 MVP-3B 이후의 별도 spec에서 다룬다.

Mask evidence paths는 synthetic fixture에서는 선택 입력이다. 제공되면 runner가 `data/masks/`로
복사하고 verifier가 C-lite를 수행한다. 제공되지 않으면 verifier는 `data/rollouts/` 기반
Level B까지 수행한다. Actual-Isaac evidence에서는 mask paths와 policy artifact paths가 필수다.

## Status Rules

Package status는 infrastructure와 learning을 분리한다.

```text
package_status:
  proof_infrastructure_closed
  proof_infrastructure_failed

learning_result:
  positive_uplift
  non_closing
  unavailable

learning_proven_addendum:
  present
  absent
```

`proof_infrastructure_closed` 조건:

```text
- actual Isaac evidence artifacts are present and hash-locked
- actual Isaac packages include mandatory policy artifact binding and C-lite per-rollout mask binding
- self-contained rollout JSON exists under data/rollouts/ and verifies
- self-contained gate JSON exists under data/gates/ and verifies
- task_variant_attestation identifies the target / fixture pose variant
- train, calibration, and held-out seed ranges match the pre-registered MVP-3A contract
- MVP-2 spent range 40000-40049 is listed and not reused
- held-out range is disjoint from train, calibration, burned, and spent ranges
- calibration rollout count >= thresholds.min_calibration_rollouts_per_policy
- held-out rollout count >= thresholds.min_heldout_rollouts_per_policy
- package manifest, data bundle, and non-claim attestation verify
- generic verifier exits 0
```

`learning_proven_addendum=present` 조건:

```text
- package_status=proof_infrastructure_closed
- candidate held-out success rate > baseline held-out success rate
- uplift >= thresholds.uplift_min
- reported uplift equals candidate_success_rate - baseline_success_rate
- confidence interval is recomputed from data/rollouts/ using audit_ci.method,
  audit_ci.iterations, and audit_ci.seed
- addendum manifest and report verify
```

Uplift가 없으면 다음 값을 기록한다.

```text
package_status=proof_infrastructure_closed
learning_result=non_closing
learning_proven_addendum=absent
```

이 결과는 실패가 아니라 bounded negative/neutral evidence다. 이 경우에도
`42000-42049`는 spent/no-reuse로 남기며, 해당 결과를 보고 threshold, metric, held-out
range를 다시 조정하지 않는다.

## Implementation Boundaries

Always:

```text
- 새 브랜치 또는 현재 feature branch에서 review 가능한 작은 diff로 진행한다.
- app.services.proof spine을 사용한다.
- MVP-3A package는 MVP-2 package와 별도 directory에 둔다.
- verifier producer independence를 유지한다.
- docs/developer/worklog.md와 Handoff.md를 갱신한다.
```

Never:

```text
- scripts/run_mvp2c_isaac_training_calibration.py 수정
- scripts/run_mvp2b_isaac_proof_evaluator.py 수정
- scripts/verify_mvp2_package.py 수정
- docs/proof/mvp2_learning_proven_evidence_package/ 수정
- held-out 40000-40049 재사용
- held-out 42000-42049 결과를 보고 threshold 또는 metric 재튜닝
- simulator evidence를 real robot claim으로 승격
```

## Testing Strategy

Tests are written before implementation changes.

```text
runner tests:
  - config with source_variable_opened=true fails closed
  - config with spent overlap against 40000-40049 fails closed
  - config missing seed_ranges.train fails closed
  - actual_isaac config without policy artifacts and C-lite masks fails closed
  - config with calibration 41000-41029 and heldout 42000-42049 passes preflight
  - runner copies four verdict-critical rollout JSON files into data/rollouts/
  - runner copies five verdict-critical gate JSON files into data/gates/
  - runner copies actual_isaac policy artifacts into data/policies/
  - non-positive uplift creates no learning-proven addendum
  - positive uplift creates learning-proven addendum with consistent rates

verifier tests:
  - valid synthetic MVP-3A package verifies
  - verifier recomputes rollout counts, success counts, rates, uplift, and confidence interval
    from data/rollouts/
  - closure_verdict tamper fails when cached summary contradicts recomputed rollout evidence
  - gate JSON tamper fails when runtime, train trace, selection, or post-heldout guard
    no longer supports the cached closure summary
  - artifact byte tamper fails
  - manifest claim tamper fails
  - evidence_kind:actual_isaac without provenance binding fails
  - source_variable_opened=true fails in verifier, not only runner
  - missing seed_ranges.train fails cleanly without traceback
  - seed range reuse tamper fails
  - non-claim true tamper fails
  - addendum present with uplift mismatch fails
  - learning_proven_report.json tamper fails when learning_proven_addendum=present
  - non_closing package with learning-proven claim fails
  - Level B fails when success != (env_native_max_consecutive_success_steps >= stable_steps_required)
  - C-lite fails when env_native_success_mask recomputes a different max consecutive count
  - C-lite fails when total success count matches but per-rollout mask binding drifts

regression tests:
  - scripts/verify_mvp2_package.py still verifies MVP-2 package
  - git diff shows no frozen MVP-2 package or archive script changes
```

Synthetic package tests only validate runner and verifier behavior. They cannot set
`package_status=proof_infrastructure_closed` for MVP-3A. Actual Isaac evidence artifacts and
self-contained rollout JSON under `data/rollouts/` are required before
`proof_infrastructure_closed` is claimed.

Synthetic verifier fixtures must set:

```text
evidence_kind=synthetic_test_fixture
package_status=synthetic_verifier_fixture
learning_proven_addendum=absent
```

Actual MVP-3A evidence packages must set:

```text
evidence_kind=actual_isaac
package_status=proof_infrastructure_closed
```

Full validation before claiming completion:

```bash
uv run pytest apps/api/tests/test_proof_spine_*.py -q
uv run pytest apps/api/tests/test_verify_mvp2_package.py -q
uv run pytest apps/api/tests/test_mvp3a_proof_infrastructure.py -q
uv run pytest apps/api/tests/test_verify_proof_package.py -q
python3 scripts/verify_mvp2_package.py docs/proof/mvp2_learning_proven_evidence_package/package_manifest.json
uvx ruff check scripts apps/api
git diff --check
```

Actual Isaac rollout execution is outside this spec's code-writing loop. MVP-3A
`Proof-Infrastructure Closed` cannot be claimed until actual Isaac evidence artifacts are
present and the package verifies against them.

## SH Usage Point

`sh` starts after this design spec is reviewed and an implementation plan exists. The first
`sh` objective is narrow:

```text
objective:
  Build the MVP-3A proof-infrastructure runner and generic verifier without
  modifying frozen MVP-2 assets.

success_criteria:
  - synthetic package tests prove status/addendum behavior
  - verifier rejects tamper cases
  - MVP-2 verifier still passes
  - frozen MVP-2 files have zero diff
  - worklog and handoff updated
```

Do not use `sh` for fresh Isaac rollout execution until the runner/verifier contract is
implemented and reviewed. Fresh Isaac execution is a separate evidence collection slice.

## Roadmap Position

MVP-3A is the control slice.

```text
MVP-3A: same Isaac source, new target / fixture pose task variant
MVP-3B: first source/adapter expansion candidate
MVP-3C: second source/embodiment expansion candidate
```

UR, ROS2-DDS, Franka, generated trajectory adapters, and real/public log import belong to
MVP-3B or a named follow-on source expansion slice. MVP-3A earns the right to open those
variables by proving the package discipline repeats cleanly on one new task variant first.
