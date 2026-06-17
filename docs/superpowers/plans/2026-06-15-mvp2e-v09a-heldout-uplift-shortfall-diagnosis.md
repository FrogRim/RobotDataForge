# MVP-2E v0.9a Held-out Uplift Shortfall Diagnosis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` and `superpowers:executing-plans`. Implement task-by-task and verify each task before moving on.

## 목표

`v0_9` actual Isaac held-out 결과가 `baseline=0.88`, `candidate=0.94`,
`uplift=0.06`으로 MVP-2 close minimum `>=0.20`을 통과하지 못했다. v0.9a는
이 실패를 artifact-only로 진단하고, opened held-out `27000-27049`를 더 이상
closure에 쓸 수 없다는 산술적 blocker를 고정한다.

## Task 1: RED tests

Files:

- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

Steps:

- [ ] fake v0.9 failed held-out evidence helper를 추가한다.
- [ ] missing source gate가 `missing_v0_9_heldout_closure_gate`로 실패하는 test를 추가한다.
- [ ] paired outcome과 opened held-out impossible-close 산술을 검증하는 test를 추가한다.
- [ ] `--heldout-uplift-shortfall-diagnosis-only` CLI가 artifact-only로 report를 생성하는 test를 추가한다.
- [ ] RED 실행:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v09a" -q
```

Expected: `V09A_*`, builder, CLI flag가 없어 실패한다.

## Task 2: v0.9a diagnosis builder

Files:

- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

Steps:

- [ ] constants 추가:
  - `V09A_POLICY_SLICE_ID = "v0_9a"`
  - `V09A_SLICE_ID = "mvp2e_v09a_heldout_uplift_shortfall_diagnosis"`
  - `V09A_CHILD_OUTPUT_DIRNAME = "v0_9a_heldout_uplift_shortfall_diagnosis"`
  - `V09A_DIAGNOSIS_SCHEMA_VERSION`
  - `V09A_RECOMMENDED_DOWNSTREAM_SLICE = "v0_10_fresh_comparator_stress_slice"`
- [ ] `_load_required_failed_v09_heldout_closure_gate(output_dir)` 구현:
  - `heldout_closure_gate_v0_9.json` 존재 확인
  - `policy_slice == "v0_9"`
  - `heldout_opened is True`
  - `fresh_heldout_27000_27049_accessed is True`
  - `actual_rollouts_per_policy >= 50`
  - `mvp2_closed is False`
  - `policy_uplift_proven is False`
  - `curated_vs_uncurated_uplift < 0.20`
- [ ] rollout JSON loader 구현:
  - `baseline_external_rollouts`
  - `candidate_external_rollouts`
  - `rollout_results`를 `scenario_id` 기준으로 pair
- [ ] trace summary helper 구현:
  - trace path가 있으면 depth/lateral/z/env-native window 요약
  - 없으면 `trace_summary_available=false`
- [ ] `build_v09a_heldout_uplift_shortfall_diagnosis(output_dir)` 구현:
  - paired counts
  - baseline/candidate/common failure seeds
  - max possible uplift = `1.0 - baseline_success_rate`
  - `opened_heldout_can_no_longer_close_minimum`
  - failure mix shortfall flags
  - downstream recommendation
  - report sha256
- [ ] report를 `v0_9a_heldout_uplift_shortfall_diagnosis_report.json`에 기록한다.

## Task 3: CLI wiring

Files:

- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

Steps:

- [ ] `--policy-slice v0_9a` 허용
- [ ] `--heldout-uplift-shortfall-diagnosis-only` flag 추가
- [ ] `_command_from_args`에 flag 추가
- [ ] main guard에 mode 추가
- [ ] branch 추가:
  - requires `--scenario-profile v0_6 --policy-slice v0_9a`
  - rejects `--clean`
  - rejects Isaac/fake/runtime modes와 incompatible modes
  - writes top-level `evidence_manifest.json`
  - returns 0

## Task 4: Verification

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v09a" -q
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08k or v08l or v09 or v09a" -q
uv run python -m compileall -q scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
```

Then run actual artifact-only diagnosis:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_9a \
  --heldout-uplift-shortfall-diagnosis-only \
  --output-dir storage/proof_evidence/mvp2c_isaac_training_calibration \
  --pretty
```

## Task 5: Documentation

Files:

- Modify: `docs/developer/worklog.md`
- Modify: `Handoff.md`
- Modify: `tasks/todo.md`

Steps:

- [ ] v0.9 actual held-out result를 기록한다.
- [ ] v0.9a diagnosis result를 기록한다.
- [ ] MVP-2가 아직 closed가 아님을 명시한다.
- [ ] 다음 valid step을 `v0_10_fresh_comparator_stress_slice` spec으로 적는다.

## Stop condition

이 plan은 v0.9a diagnosis artifact 생성까지다. MVP-2 Closed가 아니면 바로 다음
valid step인 v0.10 fresh comparator stress slice spec/plan으로 이어간다.
