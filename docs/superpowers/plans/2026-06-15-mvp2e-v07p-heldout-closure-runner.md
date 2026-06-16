# MVP-2E v0.7p Held-out Closure Runner 구현 계획

## 목표

v0.7o calibration pass 이후에만 pre-registered held-out `21000-21049`를 실제 Isaac runtime으로 열고,
기존 MVP-2C learning validator와 closure gate를 통해 `mvp2_closed`를 산출한다.

## 작업 순서

1. RED tests
   - v0.7o calibration gate가 없거나 실패하면 v0.7p held-out runner가 fail-closed하는지 검증한다.
   - fake Isaac backend로 v0.7o held-out runner가 baseline/candidate v0.7o artifacts를 사용하고,
     protected held-out seed range를 실제로 열며, positive uplift에서 `mvp2_closed=true`를 산출하는지 검증한다.

2. 구현
   - `V07P_*` 상수와 `--heldout-closure-only` CLI 모드를 추가한다.
   - `load_required_v07o_calibration_pass(...)`를 추가한다.
   - `validate_v07o_policy_peer_fairness(...)`를 추가한다.
   - `run_v07p_heldout_closure_runtime(...)`를 추가해 다음을 수행한다.
     - root manifest/curation/train view/selector/train-generation gate 검증
     - v0.7o policy artifacts 로드
     - Isaac held-out backend 실행
     - external rollout JSON 생성
     - learning validator 실행
     - `derive_mvp2c_closure(...)`로 close 판정
     - v0.7p gate와 root evidence manifest 기록

3. 실제 실행
   - focused tests 통과 후 실제 Isaac command 실행:
     `/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py --scenario-profile v0_6 --policy-slice v0_7o --heldout-closure-only --isaac-task Isaac-Factory-PegInsert-Direct-v0 --device cuda:0 --pretty`

4. 결과 분기
   - `mvp2_closed=true`: worklog/todo/Handoff 갱신 후 MVP-2 Closed로 보고한다.
   - `mvp2_closed=false`: held-out traces를 분류하고 다음 valid slice spec을 즉시 작성한다.

## 검증

- `uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v07p or heldout_closure" -q`
- `uv run python -m compileall -q scripts apps/api/tests`
- `uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
- `git diff --check`
