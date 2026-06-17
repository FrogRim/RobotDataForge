# MVP-2E v0.7i Calibration Failure Diagnosis Implementation Plan

## 목표

`v0_7h` actual Isaac calibration failure를 artifact-only로 분해하고, 다음 repair slice가 `v0_7j_off_center_xy_authority_repair`인지 증거로 판정한다.

## 변경 파일

- `scripts/run_mvp2c_isaac_training_calibration.py`
- `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
- `docs/developer/worklog.md`
- `tasks/todo.md`
- `Handoff.md`

## Task 1: RED tests

- [ ] synthetic trace로 `OFF_CENTER_XY_AUTHORITY_GAP_DEPTH_ZERO` 분류 테스트 추가
- [ ] synthetic near-miss trace로 `UNDER_INSERTION_LATE_SEAT_WINDOW` 분류 테스트 추가
- [ ] `build_v07i_calibration_failure_diagnosis`가 held-out 접근 없이 diagnosis artifact를 쓰고 downstream slice를 추천하는지 테스트
- [ ] CLI `--calibration-failure-diagnosis-only` 테스트 추가

## Task 2: Diagnosis implementation

- [ ] `V07I_*` constants 추가
- [ ] `classify_v07i_calibration_trace` 구현
- [ ] `build_v07i_calibration_failure_diagnosis` 구현
- [ ] `calibration_failure_diagnosis_v0_7i.json` 및 `calibration_trace_classification_v0_7i.json` 작성

## Task 3: CLI wiring

- [ ] `--calibration-failure-diagnosis-only` 추가
- [ ] `--scenario-profile v0_6 --policy-slice v0_7g`만 허용
- [ ] 다른 runtime modes와 조합 금지
- [ ] evidence manifest 기록

## Task 4: Verification

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  -k "v07i or calibration_failure_diagnosis" -q

uv run python -m py_compile scripts/run_mvp2c_isaac_training_calibration.py

uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7g \
  --calibration-failure-diagnosis-only \
  --pretty
```

## Branch rule

- `diagnosis_confident=true`이면 바로 `v0_7j_off_center_xy_authority_repair` spec/plan/implementation으로 이동한다.
- `diagnosis_confident=false`이면 missing evidence를 보강하는 artifact-only harness를 먼저 추가한다.
