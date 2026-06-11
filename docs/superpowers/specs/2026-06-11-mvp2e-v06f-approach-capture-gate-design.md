# MVP-2E v0.6f Approach Capture Gate Design

Date: 2026-06-11

## 목적

`v0_6f`의 목적은 `v0_6e` repair probe fail-closed 결과를 소급 수정하지 않고,
다음 repair probe를 위한 z-descent gate semantics를 다시 pre-register하는 것이다.

`v0_6f`는 MVP-2 Closed 선언이 아니다.

```text
v0_6f goal:
  repair_probe_green_light=true

v0_6f non-goal:
  fixed 40-run train-generation gate 실행
  held-out 21000-21049 개봉
  curated > uncurated held-out policy uplift claim
```

MVP-2 Closed는 여전히 다음 조건을 필요로 한다.

```text
candidate_success_rate > baseline_success_rate
curated_vs_uncurated_uplift >= 0.20
actual held-out rollouts per policy >= 20
```

## 현재 증거

`v0_6e` runtime artifact:

```text
/tmp/rdf-mvp2e-v06e-repair-probe-green/capture_radius_preflight_result.json
/tmp/rdf-mvp2e-v06e-repair-probe-green/repair_probe_gate.json
```

핵심 결과:

```text
capture_radius_m=0.0001
preflight_branch=B
green_light_for_40_run_gate=false
hard_stop=true
fixed_40_run_gate_opened=false
heldout_opened=false
```

Seed-level result:

```text
16023:
  env_native_rollout_success=false
  env_native_max_consecutive_success_steps=0
  min_lateral_error_m=0.000135
  max_insertion_depth_m=0

16042:
  env_native_rollout_success=false
  env_native_max_consecutive_success_steps=0
  min_lateral_error_m=0.000875
  max_insertion_depth_m=0

16096:
  env_native_rollout_success=false
  env_native_max_consecutive_success_steps=0
  min_lateral_error_m=0.000632
  max_insertion_depth_m=0
```

해석:

- `capture_radius_m=0.0001`은 geometry-isolated straight-down capture의 보수적
  lower bound다.
- `v0_6e`는 이 값을 그대로 `z_push_gate`로 사용했다.
- 그 결과 세 repair probe seed 모두 lateral을 줄였지만 effective descent를 시작하지 못했고,
  `max_insertion_depth_m=0`으로 종료했다.
- 따라서 `v0_6e`의 실패 원인은 env-native authority가 아니라 z-descent gate semantics가
  지나치게 좁은 lower bound에 직접 묶인 것이다.

## 비목표

`v0_6f`는 다음을 하지 않는다.

- env-native success authority를 바꾸지 않는다.
- `stable_steps_required=10`을 바꾸지 않는다.
- `capture_radius_m=0.0001`을 삭제하거나 소급 무효화하지 않는다.
- RDF secondary geometry metric을 closure authority로 승격하지 않는다.
- fixed 40-run train gate를 실행하지 않는다.
- held-out `21000-21049`를 열지 않는다.
- horizon 또는 `max_steps=150`을 늘리지 않는다.
- per-seed tuning, grid search, seed replacement를 하지 않는다.
- force-control, retry, withdraw, reinsert, search pattern을 도입하지 않는다.
- HMD readiness, real robot readiness, visual policy performance를 주장하지 않는다.

## 1. Authority Layer

Primary closure authority는 계속 Isaac env-native consecutive success다.

```text
seed_env_native_pass =
  env_native_max_consecutive_success_steps >= 10
```

이 값이 true인 seed는 pass다. Secondary diagnostic은 pass seed를 veto할 수 없다.

```text
if seed_env_native_pass:
  seed_pass = true
  secondary_diagnostics = report_only
```

Secondary diagnostics:

```text
lateral_converged_to_approach_gate
rdf_peg_in_hole_metric
insertion_depth_m
lateral_error_m
orientation_error_deg
```

위 항목들은 buyer-facing report와 debugging에는 남기지만 env-native pass를 뒤집지
못한다.

## 2. Capture Radius의 의미 재정의

`v0_6e`의 `capture_radius_m=0.0001`은 보존한다. 단, 의미를 다음처럼 고정한다.

```text
straight_down_capture_radius_m:
  geometry-isolated, no xy/yaw correction, straight-down bounded push에서
  env-native 10-consecutive seating이 관측된 보수적 lower bound
```

이 값은 다음에 사용한다.

```text
used_for:
  geometry evidence
  preflight integrity
  approach gate derivation input
  report-only diagnostics
```

이 값은 다음에 직접 사용하지 않는다.

```text
not_directly_used_for:
  controller-assisted z descent gate
  task success authority
  held-out policy success authority
```

이 결정의 이유:

- straight-down probe는 xy/yaw correction을 의도적으로 끄고 순수 geometry capture만 측정한다.
- 실제 controller-assisted descent는 xy/yaw correction을 유지하며 내려간다.
- 따라서 straight-down lower bound를 controller-assisted z gate에 그대로 쓰면,
  valid approach 상태에서도 descent가 봉쇄될 수 있다.
- `v0_6e` 세 seed의 `max_insertion_depth_m=0`이 이 failure mode를 실제로 보여준다.

## 3. v0.6f Approach Capture Gate

`v0_6f`는 straight-down capture radius와 별도로 controller-assisted approach gate를
pre-register한다.

```text
straight_down_capture_radius_m = numeric capture_radius_m from v0_6e preflight
approach_lateral_gate_m = max(0.0010, 10.0 * straight_down_capture_radius_m)
```

`v0_6e` evidence에서는:

```text
straight_down_capture_radius_m = 0.0001
approach_lateral_gate_m = 0.0010
```

정당화:

- `0.0010m`은 controller-assisted descent를 허용하기 위한 approach gate이지 success
  threshold가 아니다.
- `0.0010m`은 straight-down lower bound의 10배지만, 이전 폐기된 absolute diagnostic cap
  `0.008m`보다 훨씬 엄격하다.
- `0.0010m`은 env-native 10-consecutive success를 대체하지 않는다.
- `0.0010m`은 fixed 40-run gate와 held-out을 보기 전에 고정한다.

Required config fields:

```text
schema_version = rdf_mvp2e_v06f_controller_repair_config_v0.1.0
straight_down_capture_radius_m = <numeric>
approach_lateral_gate_m = max(0.0010, 10.0 * straight_down_capture_radius_m)
approach_lateral_gate_source = pre_registered_controller_assisted_approach_gate_v0_6f
z_push_gate = lateral_error_m <= approach_lateral_gate_m
success_authority = env_native_10_consecutive
proof_authority = false
```

Forbidden config fields:

```text
per_seed_gate_m
heldout_tuned_gate_m
success_threshold_override
horizon_increase
retry_enabled
search_enabled
withdraw_enabled
force_control_enabled
```

## 4. Controller Envelope

`v0_6f` controller envelope는 `v0_6e`와 같은 단조 1-pass 구조를 유지한다.

```text
ALIGN -> DESCEND -> INSERT -> HOLD
```

허용:

```text
live target re-read
phase-normalized controller state
xy/yaw correction 유지
z descent only when lateral_error_m <= approach_lateral_gate_m
bounded downward push
env-native hold window N=10
```

금지:

```text
horizon increase
retry
withdraw
reinsert
search pattern
force-control
per-seed gain/grid tuning
held-out feedback
```

중요한 차이:

```text
v0_6e z gate:
  lateral_error_m <= straight_down_capture_radius_m

v0_6f z gate:
  lateral_error_m <= approach_lateral_gate_m
```

`straight_down_capture_radius_m`은 계속 기록되지만, controller-assisted descent를 직접
봉쇄하지 않는다.

## 5. Non-seated Lateral Convergence Rule

Convergence diagnostic은 env-native를 통과하지 못한 lateral seed에만 적용한다.

```text
near_band_m = approach_lateral_gate_m
min_lateral_achieved_m = min(lateral_error_m over rollout)
last_k_median_lateral_m = median(last K lateral_error_m)
regression_tol_m = max(0.0005, 0.5 * approach_lateral_gate_m)

non_seated_lateral_converged =
  last_k_median_lateral_m <= near_band_m
  AND last_k_median_lateral_m <= min_lateral_achieved_m + regression_tol_m
```

Required constants:

```text
last_k = 10
approach_gate_floor_m = 0.0010
approach_gate_capture_multiplier = 10.0
regression_tol_floor_m = 0.0005
regression_tol_approach_ratio = 0.5
```

이 rule은 proof authority가 아니다. 목적은 repair probe가 green이 아닐 때 지배 failure가
`approach gate에 수렴하지 못함`인지, `seat/HOLD 실패`인지, `runtime/action blocker`인지
분리하는 것이다.

## 6. Repair Probe Green Rule

`v0_6f` green rule:

```text
green_light_for_40_run_gate =
  16023 env-native pass
  AND at least one of 16042/16096 env-native pass
  AND every non-seated lateral seed converged to approach gate with no regression
  AND fixed_40_run_gate_opened=false
  AND heldout_opened=false
```

Hard stop:

```text
16023 env-native fail
OR both lateral seeds env-native fail
OR any non-seated lateral seed fails approach convergence/no-regression
OR max_insertion_depth_m remains 0 for all three seeds
```

`max_insertion_depth_m=0 for all three seeds`는 `v0_6e`에서 관측된 z-descent blockade의
재발 신호다. 이 경우 fixed 40-run gate를 열지 않는다.

## 7. Anti-overfit Guard

`16023`, `16042`, `16096`은 repair validation probe다. 이 세 seed에서 여러 번
iterate한 사실 때문에 다음 guard를 둔다.

```text
probe_seeds_are_not_training_gate=true
probe_seeds_excluded_from_v0_6_train_gate=true
fixed_40_run_gate_seed_range=19000-19159
heldout_seed_range=21000-21049
```

금지:

```text
approach_lateral_gate_m을 seed별로 바꾸기
16023/16042/16096 결과를 보고 approach gate를 다시 고르기
probe seed를 fixed 40-run gate에 재사용하기
probe success를 MVP-2 Closed evidence로 쓰기
```

허용:

```text
v0_6f repair probe 결과를 다음 engineering diagnosis evidence로 보존하기
green이면 이후 별도 fixed 40-run train gate로 넘어가기
red이면 held-out을 열지 않고 다음 controller diagnosis로 멈추기
```

## 8. Runtime Artifact Requirements

`v0_6f` runtime은 다음 artifact를 남긴다.

```text
controller_repair_config.json
repair_probe_gate.json
isaac_runtime_repair_probe/probe_summary.json
isaac_runtime_repair_probe/*trace*.json
```

`controller_repair_config.json` required fields:

```text
schema_version
straight_down_capture_radius_m
approach_lateral_gate_m
approach_lateral_gate_source
z_push_gate
success_authority
proof_authority
non_claims
config_sha256
```

`repair_probe_gate.json` required fields:

```text
schema_version
probe_seeds
success_authority
straight_down_capture_radius_m
approach_lateral_gate_m
green_light_for_40_run_gate
hard_stop
fixed_40_run_gate_opened
heldout_opened
seed_results
repair_probe_gate_sha256
```

Required non-claims:

```text
mvp2_closed=false
learning_proven=false
heldout_opened=false
real_robot_success=false
physical_robot_readiness=false
visual_policy_performance=false
universal_robot_support=false
```

## Stop Conditions

Stop and report if any condition is hit.

```text
capture_radius_m is not numeric
approach_lateral_gate_m cannot be computed before repair probe
repair probe requires held-out 21000-21049
repair probe requires fixed 40-run train gate
controller repair requires horizon increase
controller repair requires retry/search/withdraw/force-control
controller repair requires per-seed grid search over 16023/16042/16096
16023 loses env-native pass
all lateral seeds fail env-native
all probe seeds remain max_insertion_depth_m=0
```

## Verification Minimum

Required local verification before runtime:

```text
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q
uv run python -m compileall -q scripts apps/api/app apps/api/tests
uvx ruff check scripts/run_mvp2b_isaac_proof_evaluator.py scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
git diff --check
```

Required runtime verification:

```text
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2e-v06f-approach-capture-gate \
  --scenario-profile v0_6 \
  --capture-radius-probe-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty

uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2e-v06f-approach-capture-gate \
  --scenario-profile v0_6 \
  --train-generation-probe-only \
  --repair-probe-only \
  --repair-probe-controller-version v0_6f \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

The second command must not schedule fixed 40-run gate or held-out evaluation.

