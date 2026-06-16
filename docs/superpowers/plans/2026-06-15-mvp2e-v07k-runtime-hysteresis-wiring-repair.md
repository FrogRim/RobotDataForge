# MVP-2E v0.7k Runtime Hysteresis Wiring Repair Implementation Plan

## 목표

`v0_7j` calibration failure의 직접 원인인 runtime hysteresis wiring 누락을 `v0_7k` child slice로 수리하고 actual Isaac calibration pre-signal을 재실행한다.

## 변경 파일

- `scripts/run_mvp2b_isaac_proof_evaluator.py`
- `scripts/run_mvp2c_isaac_training_calibration.py`
- `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
- `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
- `docs/developer/worklog.md`
- `tasks/todo.md`
- `Handoff.md`

## Task 1: Evaluator wiring

- [ ] `v0_7k` constants 추가
- [ ] `v0_7j`/`v0_7k`를 stateful hysteresis prediction 경로에 포함
- [ ] `v0_7j`/`v0_7k`를 residual base-servo / authority filter 경로에 포함
- [ ] runtime rollout hysteresis state 대상에 `v0_7k` 포함

## Task 2: Training/calibration builder

- [ ] `v0_7k` constants 추가
- [ ] parent `v0_7j` failed calibration gate loader 구현
- [ ] `build_v07k_runtime_hysteresis_wiring_repair_slice` 구현
- [ ] `--offline-relabel-only --policy-slice v0_7k` 지원

## Task 3: Calibration pre-signal

- [ ] `--calibration-presignal-only --policy-slice v0_7k` 지원
- [ ] `v0_7k_runtime_hysteresis_wiring_repair` child dir에 artifacts 작성
- [ ] actual Isaac calibration 30x2 실행

## Task 4: Verification

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -k "v07j or v07k or v0_7j or v0_7k" -q
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v07j or v07k or v0_7j or v0_7k" -q
uv run python -m py_compile scripts/run_mvp2b_isaac_proof_evaluator.py scripts/run_mvp2c_isaac_training_calibration.py
uv run python scripts/run_mvp2c_isaac_training_calibration.py --scenario-profile v0_6 --policy-slice v0_7k --offline-relabel-only --pretty
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py --scenario-profile v0_6 --policy-slice v0_7k --calibration-presignal-only --isaac-task Isaac-Factory-PegInsert-Direct-v0 --device cuda:0 --pretty
```

## Branch rule

- calibration pass: `v0_7l_heldout_ab`로 이동
- calibration fail: `v0_7l_calibration_failure_diagnosis`로 이동
