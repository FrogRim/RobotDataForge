# MVP-2E v0.7q Held-out Shortfall Diagnosis 구현 계획

## 목표

v0.7p 실제 Isaac held-out 실패를 artifact-only로 분류하고, 같은 held-out split 재사용을 금지하는 marker와
fresh split downstream 추천을 생성한다.

## 작업 순서

1. RED tests
   - v0.7p gate가 없으면 v0.7q diagnosis가 fail-closed하는지 검증한다.
   - fake v0.7p held-out traces로 paired outcome, close shortfall, candidate failure class,
     downstream recommendation을 검증한다.
   - v0.7q CLI가 `post_heldout_tuning_marker.json`을 기록하고 `mvp2_closed=false`를 유지하는지 검증한다.

2. 구현
   - `V07Q_*` 상수를 추가한다.
   - `build_v07q_heldout_shortfall_diagnosis(...)`를 추가한다.
   - candidate failure classifier를 추가한다.
   - `--heldout-shortfall-diagnosis-only` CLI 모드를 추가한다.
   - 루트 evidence manifest와 post-heldout marker를 기록한다.

3. 검증
   - `uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v07q or heldout_shortfall" -q`
   - `uv run python -m compileall -q scripts apps/api/tests`
   - `uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
   - `git diff --check`

4. 결과 분기
   - 추천이 `v0_8a_fresh_seat_window_authority_slice`이면 해당 fresh split spec으로 즉시 진행한다.
   - 추천이 다른 값이면 해당 추천에 맞춰 fresh split spec을 작성한다.

## 중단 조건

- v0.7p held-out trace가 100개 미만이면 중단하고 evidence incompleteness를 보고한다.
- gate success count와 trace-derived count가 불일치하면 중단한다.
- 같은 `21000-21049` split을 closure로 재사용해야만 한다면 중단한다.
