# MVP-2 Rebase UR Policy A/B Harness Design

## Goal

MVP-2를 legacy `MVP-1C` / HUD-first policy-uplift 흐름에서 새
MVP-1/MVP-1+ data trust layer 구조로 재정렬한다.

첫 MVP-2 slice는 Universal Robots UR industrial-arm file-backed recorded log를
proof source로 사용해 offline policy A/B harness를 준비하고, 외부
trainer/evaluator rollout 결과를 받을 수 있는 ingest contract까지 검증한다.

이 slice는 learning-proven policy uplift를 측정하거나 주장하지 않는다.

## Background

현재 ForgeXR / Robot Data Forge는 HMD-first 제품이 아니라 robot data trust
layer다.

MVP-1은 다음 learning-ready proof path를 닫았다.

```text
raw robot-action trajectory
-> normalized trajectory contract
-> replay/action gate
-> data-quality gate
-> curation gate
-> HDF5 export
-> trainer smoke
-> buyer-facing trust artifacts
```

MVP-1+는 여러 robot embodiment source가 같은 normalized trajectory contract를
emit하고 같은 data trust layer를 통과할 수 있음을 보였다.

```text
JSONL + metadata command-state logs
-> RobotEmbodimentAdapterRegistry
-> RobotEmbodimentAdapter
-> RobotEmbodimentContractBuilder
-> NormalizedTrajectoryContractValidator
-> curation evidence
-> HDF5 export
-> trainer smoke
-> buyer summary
```

따라서 MVP-2의 primary input도 legacy HMD/HUD collection path가 아니라
adapter-emitted contract lineage에서 시작해야 한다.

## Problem

기존 MVP-2 실행 문서는 많은 부분이 legacy `MVP-1C` 흐름을 MVP-2로 해석한
상태다.

문제는 다음과 같다.

- `mvp1c_*` script name과 artifact path가 남아 있어 MVP-2 primary entrypoint가
  불명확하다.
- 일부 preflight는 `fresh HUD data ingest`, Quest/OpenXR/HMD quality field,
  HMD live trajectory를 전제로 한다.
- 새 MVP-1+에서 만든 `AdapterRegistry -> ContractBuilder -> Validator` lineage가
  policy A/B harness의 입력 기준으로 명시되어 있지 않다.
- policy A/B harness readiness와 실제 policy uplift measurement가 섞여 보일 수
  있다.

MVP-2 Rebase first slice는 이 혼선을 제거하고, UR recorded/log-backed data trust
lineage에서 policy A/B 준비물과 ingest contract를 만드는 구조로 재정의한다.

## User-Approved Decisions

- First proof source: `universal_robots_ur_industrial_arm` file-backed recorded
  log.
- First slice scope: Rebase spec + offline policy A/B harness.
- Legacy handling: 새 `mvp2_*` primary entrypoint를 만들고, 기존 `mvp1c_*`는
  compatibility path로 보존한다.
- Harness target: policy A/B ingest proof.
- Rollout ingest validation: schema-only ingest fixture.
- Final report wiring: 독립 `mvp2_policy_ab_harness_report.json`을 primary artifact로
  만들고, `run_mvp1_proof_audit.py`에는 MVP-2 harness readiness 요약만 연결한다.

## Scope

이 slice는 다음을 포함한다.

- UR file-backed recorded log lineage를 MVP-2 policy A/B harness input으로 사용.
- adapter-emitted normalized trajectory contract 검증 결과를 harness report에 기록.
- curated / uncurated train dataset view를 생성할 수 있는 artifact boundary 정의.
- baseline uncurated train HDF5와 candidate curated train HDF5 export boundary 정의.
- held-out suite manifest와 policy eval input template 생성 boundary 정의.
- 외부 trainer/evaluator rollout CSV/JSON을 받을 수 있는 ingest contract 검증.
- schema-only rollout fixture를 사용해 ingest shape를 테스트하되 policy result로
  해석하지 않음.
- proof audit에는 MVP-1 pass와 분리된 MVP-2 harness readiness summary만 추가.

## Non-Goals

이 slice는 다음을 구현하거나 주장하지 않는다.

- policy uplift 측정
- curated-vs-uncurated improvement claim
- learning-proven proof 완료
- real robot success
- physical robot readiness
- live UR/RTDE runtime
- live ROS2/DDS runtime
- HMD / Quest / OpenXR readiness
- HMD Gate A collection readiness
- VLA fine-tuning
- World Model training
- marketplace
- production auth
- DB migration

## Claim Boundary

MVP-2 Rebase first slice의 claim boundary는 다음 값으로 고정한다.

```json
{
  "learning_results_measured": false,
  "curated_vs_uncurated_uplift": null,
  "learning_proven": false,
  "proof_eligible": false,
  "policy_uplift_claimed": false,
  "real_robot_success_claimed": false,
  "physical_robot_readiness_claimed": false,
  "hmd_readiness_claimed": false
}
```

schema-only rollout fixture는 policy result evidence가 아니다. 이 fixture는
외부 trainer/evaluator output shape를 RDF가 받을 수 있는지 검증하는 ingest
contract fixture다.

## Architecture

Primary flow:

```text
UR file-backed recorded log
-> RobotEmbodimentAdapterRegistry
-> RobotEmbodimentAdapter
-> ContractBuilder
-> NormalizedTrajectoryContractValidator
-> curated / uncurated dataset views
-> baseline_uncurated_train.hdf5
-> candidate_curated_train.hdf5
-> mvp2_heldout_suite_manifest.json
-> mvp2_policy_eval_input_template.json
-> schema-only rollout ingest fixture
-> mvp2_policy_ab_harness_report.json
-> run_mvp1_proof_audit.py MVP-2 summary
```

The MVP-2 harness must treat adapter lineage as a first-class input. At minimum,
the report must preserve:

- `adapter_id`
- `adapter_version`
- `builder_id`
- `robot_embodiment`
- `source_evidence_type`
- source file hash lineage when present
- normalized trajectory contract path
- validator backend
- curation manifest path
- HDF5 export paths
- buyer-facing limitations

## Primary Artifacts

The first slice should produce or define these primary artifacts.

```text
storage/mvp2_policy_ab_harness/
  mvp2_policy_ab_harness_report.json
  mvp2_policy_eval_input_template.json
  mvp2_heldout_suite_manifest.json
  baseline_uncurated/
    baseline_uncurated_train.hdf5
    hdf5_inspection.json
  candidate_curated/
    candidate_curated_train.hdf5
    hdf5_inspection.json
  rollout_ingest_contract_fixture/
    baseline_rollouts.schema_fixture.json
    candidate_rollouts.schema_fixture.json
    ingest_contract_report.json
```

Exact file names may be adjusted during implementation if existing repo naming
patterns require it, but public artifact names must use `mvp2_*` wording and must
not expose `mvp1c_*` as the primary path.

## Policy A/B Semantics

MVP-2 learning-proven proof remains:

```text
success_rate(policy trained on curated accepted data)
>
success_rate(policy trained on uncurated success-lifecycle data)
```

This first slice does not run that comparison. It only proves the harness can
prepare and ingest the required evidence shape.

State meanings:

| State | Meaning |
|---|---|
| `harness_ready=true` | Dataset views, HDF5 exports, held-out suite template, and policy eval template exist. |
| `rollout_ingest_contract_ready=true` | External rollout result CSV/JSON shape can be parsed and validated. |
| `learning_results_measured=false` | No real policy evaluation result has been ingested. |
| `proof_eligible=false` | The schema fixture is not proof-grade held-out policy evidence. |
| `learning_proven=false` | No positive curated-vs-uncurated uplift claim exists. |

## Legacy Compatibility

Existing `mvp1c_*` scripts remain available for compatibility and regression
tests. They should not be deleted in this slice.

The rebase should introduce new MVP-2 primary surfaces, for example:

```text
scripts/run_mvp2_ur_policy_ab_harness.py
scripts/run_mvp2_rollout_ingest_contract.py
```

Implementation may reuse stable logic from:

```text
scripts/run_mvp1c_headless_eval_bundle.py
scripts/run_mvp1c_rollout_result_adapter.py
scripts/run_mvp1c_real_policy_eval.py
scripts/run_mvp1_proof_audit.py
```

but the new public report wording must be MVP-2 / UR contract lineage based.

## Proof Audit Integration

`run_mvp1_proof_audit.py` should continue to preserve the existing MVP-1 meaning:

- MVP-1 pass means learning-ready dataset pipeline proof.
- Policy uplift is not required for MVP-1.
- Negative policy evidence does not invalidate MVP-1.

For this slice, proof audit may add a small MVP-2 harness summary section:

```json
{
  "mvp2_policy_ab_harness": {
    "harness_ready": true,
    "rollout_ingest_contract_ready": true,
    "learning_results_measured": false,
    "curated_vs_uncurated_uplift": null,
    "learning_proven": false,
    "proof_eligible": false,
    "primary_report_path": "storage/mvp2_policy_ab_harness/mvp2_policy_ab_harness_report.json"
  }
}
```

The audit must not promote MVP-2 to learning-proven from schema-only fixture
evidence.

## Error Handling

The harness should fail closed when:

- UR adapter profile cannot be resolved.
- Contract emission does not pass `NormalizedTrajectoryContractValidator`.
- Source lineage is missing where the UR file-backed fixture promises lineage.
- curated or uncurated dataset view is empty.
- HDF5 export or inspection fails.
- held-out suite manifest is missing or not held out.
- policy eval input template is missing required fields.
- schema-only rollout fixture is interpreted as proof-grade held-out evidence.
- any report claims policy uplift before real held-out evaluation is ingested.

## Testing Strategy

Focused tests should cover:

- UR adapter-emitted contract lineage appears in the MVP-2 harness report.
- The harness uses `universal_robots_ur_industrial_arm` as the first proof source.
- `mvp2_policy_eval_input_template.json` is created with baseline and candidate
  dataset identities.
- baseline uncurated and candidate curated HDF5 exports exist and pass inspection.
- held-out suite manifest exists and declares `held_out=true`.
- schema-only rollout fixture validates ingest shape but keeps `proof_eligible=false`.
- `learning_results_measured=false`, `curated_vs_uncurated_uplift=null`, and
  `learning_proven=false` are preserved.
- proof audit continues to pass MVP-1 and only adds MVP-2 harness readiness summary.
- HMD/Quest/OpenXR does not become primary proof path evidence.
- legacy `mvp1c_*` compatibility tests continue to pass.

Minimum verification commands for the implementation plan should include:

```bash
uv run pytest apps/api/tests/test_mvp1plus_embodiment_proof_script.py -q
uv run pytest apps/api/tests/test_mvp1_proof_audit_script.py apps/api/tests/test_mvp1c_real_policy_eval_script.py -q
uv run pytest apps/api/tests/test_mvp1c_headless_eval_bundle_script.py apps/api/tests/test_mvp1c_rollout_result_adapter_script.py -q
uv run python scripts/run_mvp1plus_embodiment_proof.py --clean --pretty
uv run python scripts/run_data_trust_layer_proof.py --clean --pretty
uv run python -m compileall -q scripts apps/api/app apps/api/tests
uvx ruff check scripts apps/api/app apps/api/tests
git diff --check
```

The implementation plan should add new focused MVP-2 harness tests before
implementation.

## Stop Conditions

Stop and report instead of continuing if:

- Existing MVP-1 proof output compatibility would break.
- Existing `mvp1c_*` compatibility must be deleted or broken.
- `run_mvp1_proof_audit.py` would need to treat policy uplift as an MVP-1 gate.
- The validator must be weakened to make the UR source pass.
- Live UR/RTDE runtime becomes necessary.
- Live ROS2/DDS runtime becomes necessary.
- HMD/OpenXR must become primary path evidence.
- A DB migration becomes necessary.
- The schema-only fixture would be mistaken for real policy evidence.
- A positive policy uplift claim would be made without real held-out evaluation.

## Acceptance Criteria

The first MVP-2 Rebase slice is complete when:

- A new MVP-2 primary spec and implementation plan are based on UR
  file-backed recorded-log lineage.
- The planned primary script/artifacts use `mvp2_*` naming.
- Legacy `mvp1c_*` scripts remain compatibility surfaces.
- MVP-2 harness report preserves adapter-emitted contract lineage.
- The harness prepares curated/uncurated train dataset views and HDF5 export
  boundaries.
- The harness prepares held-out suite and policy eval input template boundaries.
- Schema-only rollout ingest fixture verifies input shape without proof eligibility.
- Proof audit can summarize MVP-2 harness readiness while keeping MVP-1 meaning
  unchanged.
- The claim boundary remains learning-ready-to-harness-ready, not learning-proven.

## Next Slice After This Rebase

After this first slice, MVP-2 can proceed to real policy evaluation only when
real held-out rollout results are available from an external trainer/evaluator
or a separately approved offline evaluator flow.

The next slice should decide:

- trainer/policy class
- held-out scenario construction
- rollout count
- positive uplift threshold and confidence reporting
- negative result report format

Those decisions are intentionally outside this first Rebase slice.
