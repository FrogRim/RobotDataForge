# MVP-2E v0.7j Off-Center XY Authority Repair Implementation Plan

## 목표

`v0_7i` diagnosis에 따라 `v0_7g` final XY authority를 `v0_7j` piecewise off-center authority로 확장하고, actual Isaac calibration pre-signal을 다시 실행한다.

## 변경 파일

- `scripts/run_mvp2b_isaac_proof_evaluator.py`
- `scripts/run_mvp2c_isaac_training_calibration.py`
- `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
- `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
- `docs/developer/worklog.md`
- `tasks/todo.md`
- `Handoff.md`

## Task 1: Evaluator authority support

- [ ] `v0_7j` constants 추가
- [ ] `v0_7j` policy artifact validation 추가
- [ ] `_apply_v07g_final_post_adapter_xy_authority`가 `xy_authority_strategy=piecewise_off_center_state_feedback_clip`을 지원하도록 확장
- [ ] runtime hysteresis state 대상에 `v0_7j` 포함

## Task 2: Training/calibration builder

- [ ] `v0_7j` constants 추가
- [ ] `build_v07j_off_center_xy_authority_repair_slice` 구현
- [ ] offline gate 구현
- [ ] `--offline-relabel-only --policy-slice v0_7j` 지원

## Task 3: Calibration pre-signal

- [ ] `--calibration-presignal-only --policy-slice v0_7j` 지원
- [ ] `v0_7j_calibration_presignal` child dir에 artifacts 작성
- [ ] actual Isaac calibration 30x2 실행

## Task 4: Verification

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -k "v07j or v0_7j" -q
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v07j or v0_7j" -q
uv run python -m py_compile scripts/run_mvp2b_isaac_proof_evaluator.py scripts/run_mvp2c_isaac_training_calibration.py
uv run python scripts/run_mvp2c_isaac_training_calibration.py --scenario-profile v0_6 --policy-slice v0_7j --offline-relabel-only --pretty
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py --scenario-profile v0_6 --policy-slice v0_7j --calibration-presignal-only --isaac-task Isaac-Factory-PegInsert-Direct-v0 --device cuda:0 --pretty
```

## Branch rule

- calibration pass: `v0_7k_heldout_ab`로 이동
- calibration fail: `v0_7k_calibration_failure_diagnosis`로 이동
