# MVP-2E v0.6e Repair Probe Green Design

Date: 2026-06-11

## 목적

`v0_6e`의 목적은 `v0_6d`에서 fail-closed된 repair probe를 새로
pre-register된 진단/수리 규칙으로 다시 실행해, fixed 40-run train-generation gate를
열 수 있는 최소 선행 조건을 만드는 것이다.

`v0_6e`는 MVP-2 Closed 선언이 아니다.

```text
v0_6e goal:
  repair_probe_green_light=true

v0_6e non-goal:
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

`v0_6d` runtime artifact:

```text
/tmp/rdf-mvp2e-v06d-controller-phase-fix/repair_probe_gate.json
```

핵심 결과:

```text
green_light_for_40_run_gate=false
hard_stop=true
v0_6b_native_metric_trace_validation.valid=true
phase_vocabulary_mismatch_steps=0
final_negative_z_action_steps=269
```

`v0_6c`의 `APPROACH` phase vocabulary blocker는 해결됐다. 이제 trace
`APPROACH`가 controller `ALIGN` equivalent로 매핑되어 negative z action이 실제로
나온다.

남은 문제는 두 개다.

```text
16042:
  env_native_rollout_success=true
  env_native_max_consecutive_success_steps=10
  lateral_divergence_stopped=false
  initial_lateral_error_m=0.016754
  last_10_median_lateral_error_m=0.000365

16096:
  env_native_rollout_success=false
  env_native_max_consecutive_success_steps=0
  stuck in APPROACH for 150 steps
  depth=0
  lateral progression: 23.4mm -> 2.76mm best -> 14.3mm final
```

`16042`는 env-native success를 냈는데 secondary diagnostic이 veto한
spurious fail이다. `16096`은 실제 control failure다.

## 비목표

`v0_6e`는 다음을 하지 않는다.

- env-native success authority를 바꾸지 않는다.
- `stable_steps_required=10`을 바꾸지 않는다.
- RDF secondary geometry metric을 closure authority로 승격하지 않는다.
- fixed 40-run train gate를 실행하지 않는다.
- held-out `21000-21049`를 열지 않는다.
- horizon 또는 `max_steps=150`을 늘리지 않는다.
- per-seed tuning을 하지 않는다.
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
  divergence_diagnostic = report_only
```

따라서 `16042`처럼 env-native 10-consec success를 달성한 seed는
`lateral_divergence_stopped=false`라도 pass다. 이 규칙은 `16042`를 통과시키기 위한
예외가 아니라 authority hierarchy를 바로잡는 것이다.

Secondary diagnostics:

```text
lateral_divergence_stopped
rdf_peg_in_hole_metric
insertion_depth_m
lateral_error_m
orientation_error_deg
```

위 항목들은 buyer-facing report와 debugging에는 남기지만 env-native pass를 뒤집지
못한다.

## 2. Non-seated Lateral Convergence Rule

Convergence diagnostic은 env-native를 통과하지 못한 lateral seed에만 적용한다.

폐기하는 규칙:

```text
max_lateral_error_m < 0.008
```

폐기 이유:

- `max_lateral_error_m`은 high-initial-lateral probe에서 대부분 초기 lateral distance다.
- 초기 lateral이 8mm보다 큰 seed는 강하게 수렴해도 false fail이 된다.
- 이 diagnostic이 primary env-native success를 veto하면 authority hierarchy가 뒤집힌다.

새 rule:

```text
near_band_m = capture_radius_m
min_lateral_achieved_m = min(lateral_error_m over rollout)
last_k_median_lateral_m = median(last K lateral_error_m)
regression_tol_m = max(0.0005, 0.5 * capture_radius_m)

non_seated_lateral_converged =
  last_k_median_lateral_m <= near_band_m
  AND last_k_median_lateral_m <= min_lateral_achieved_m + regression_tol_m
```

Required constants:

```text
last_k = 10
regression_tol_floor_m = 0.0005
regression_tol_capture_ratio = 0.5
```

`last_k_median_lateral_m <= near_band_m`은 peg가 capture 가능한 band 안에 머물렀는지
본다. `last_k_median_lateral_m <= min_lateral_achieved_m + regression_tol_m`은
`16096`처럼 한때 2.76mm까지 수렴했다가 14.3mm로 밀려나는 drift-back-out을 fail로
잡는다.

삭제한 조건:

```text
last_k_median_lateral_m <= initial_lateral_error_m - required_improvement
```

삭제 이유:

- small-initial seed에서는 near-band보다 큰 required improvement를 요구하는 자기모순이
  생길 수 있다.
- high-initial lateral seed에서는 near-band + no-regression 조건과 중복이다.

## 3. Capture-radius Preflight 강화

`v0_6a` Branch B는 충분하지 않았다.

문제:

```text
capture_radius_m = "approximate"
derived_insert_params.value_source = "frozen_v0_6_adapter_and_horizon_not_probe_results"
```

이 상태는 실제 geometry grounding이 아니다. `v0_6e`에서는 numeric capture radius가
필수다.

Required preflight output:

```text
capture_radius_m: numeric
capture_radius_source: empirical_runtime_probe
capture_radius_probe_geometry_isolated: true
repair_probe_allowed: true
insert_parameter_freeze_allowed: true
```

If `capture_radius_m` is not numeric:

```text
repair_probe_allowed=false
train_generation_gate_allowed=false
failure_mode=capture_radius_not_numeric
```

### Geometry-isolated Capture Probe

Capture-radius probe는 controller ability를 재면 안 된다. chamfer/lead-in의 순수
geometry capture만 측정해야 한다.

필수 절차:

```text
1. use dedicated geometry seed namespace only
2. do not use train/calibration/held-out/probe seeds
3. reset Isaac Factory PegInsert env
4. place or command peg above target with lateral offset delta
5. disable xy correction
6. disable yaw correction
7. apply straight-down bounded z push only
8. record env-native success mask
9. success(delta)=max_consecutive(env_native_success_mask) >= 10
10. capture_radius_m = conservative minimum successful offset across directions
```

Dedicated geometry seed:

```text
geometry_probe_seed = 18500
```

Forbidden seed usage:

```text
16023, 16042, 16096
19000-19159
19200-19359
20000-20029
21000-21049
```

The probe is not training material, not curation evidence, not policy evaluation
evidence, and not proof closure evidence.

Required direction set:

```text
+x, -x, +y, -y
```

Required delta sweep:

```text
0.0000
0.0001
0.0002
0.0004
0.0006
0.0008
0.0010
0.0015
0.0020
0.0030
0.0040
0.0060
0.0080
```

`capture_radius_m` must be the conservative value:

```text
capture_radius_m = min(max_successful_delta_m_by_direction)
```

## 4. Controller Repair Envelope

`16096`의 current failure는 단순히 "align이 느리다"가 아니다.

Observed failure:

```text
phase=APPROACH for 150 steps
depth=0
lateral improves to 2.76mm, then regresses to 14.3mm
env_native_consecutive=0
```

이 drift는 smooth action 또는 sign error보다, off-center 상태에서 조기 z push가 peg를 rim에
누르고 lateral로 밀어내는 rim-eject failure로 해석한다. 따라서 핵심 처방은 damping이
아니라 z-push gate를 capture radius로 강제하는 것이다.

Required controller behavior:

```text
if lateral_error_m > capture_radius_m:
  action_z = 0.0
  controller_state remains ALIGN

if lateral_error_m <= capture_radius_m and orientation gate passes:
  action_z may be negative
  controller_state may transition ALIGN -> DESCEND
```

`tol_align_m` must be derived from `capture_radius_m`.

```text
tol_align_m = capture_radius_m
```

Do not make `tol_align_m` stricter than measured capture radius in this slice.
That would recreate the prior ungrounded gate.

Controller state:

```text
ALIGN -> DESCEND -> INSERT -> HOLD
```

The controller must own this state inside a rollout. It must not infer the
controller state from trace phase on every step after the initial normalization.

Allowed:

- controller-owned persistent state
- global xy authority values
- global action clip values
- z-push gate derived from numeric capture radius
- INSERT params derived from numeric capture radius

Forbidden:

- per-seed gain tuning
- grid search against the three repair probe seeds
- horizon increase
- retry/recover
- withdraw/reinsert
- search behavior
- force-reactive controller
- changing env-native success threshold

### Overfit Guard

The repair probe seeds `16023`, `16042`, and `16096` have already been used across
several diagnostic iterations. They are valid engineering probe seeds, but they
must not become tuning targets.

Implementation must define controller params from:

```text
capture_radius_m
existing global action bounds
general stability constraints
```

Implementation must not define controller params by:

```text
trying multiple gain/clip values on 16023/16042/16096 and choosing the best
```

Fresh capability evidence is the later fixed 40-run train-generation gate, not
the three repair probe seeds.

## 5. Repair Probe Green Rule

The repair probe remains proof-authority false. It only gates whether the fixed
40-run train-generation gate may be opened.

Required seeds:

```text
16023: hold / near-stability mode
16042: lateral mode, env-native pass already observed in v0_6d
16096: severe lateral mode, current non-seated regression blocker
```

Per-seed rule:

```text
if env_native_max_consecutive_success_steps >= 10:
  seed_pass = true
  convergence_diagnostic = report_only
else if seed is a lateral seed:
  seed_pass = non_seated_lateral_converged
else:
  seed_pass = false
```

Global green rule:

```text
repair_probe_green_light =
  seed_16023_env_native_pass
  AND at_least_one_lateral_seed_env_native_pass
  AND every_non_seated_lateral_seed_converged
```

Regression guard:

```text
After any global controller param change, rerun all three repair probe seeds.
The change is invalid if it breaks the already-passing 16023 hold mode.
The change is invalid if it removes all lateral env-native passes.
```

Current `v0_6d` state under this rule:

```text
16023: pass
16042: pass
16096: fail, because non-seated and regressed from best lateral
```

Thus `v0_6e` must make `16096` either:

```text
env-native pass
```

or:

```text
non-seated but converged inside capture-radius band with no late regression
```

Full seating of the severe seed is desirable but not mandatory for repair probe
green. No-regression convergence is mandatory.

## 6. Artifacts

Required output artifacts:

```text
capture_radius_probe.json
capture_radius_preflight_result.json
repair_probe_gate.json
controller_repair_config.json
controller_repair_config_sha256
```

`repair_probe_gate.json` must include:

```text
proof_authority=false
heldout_opened=false
fixed_40_run_gate_opened=false
capture_radius_m
tol_align_m
non_seated_lateral_convergence_rule
seed_16023_result
seed_16042_result
seed_16096_result
repair_probe_green_light
hard_stop
```

## 7. Stop Conditions

Stop and report if any of the following occurs.

```text
capture_radius_m is not numeric
geometry-isolated capture probe cannot run
capture probe uses correction controller
capture probe touches train/calibration/held-out/probe seeds
controller repair requires horizon increase
controller repair requires retry/search/withdraw/force-control
controller repair requires per-seed tuning
16023 regresses from env-native pass to fail
all lateral seeds fail env-native after global controller change
held-out 21000-21049 would need to be opened
fixed 40-run train gate would need to run before repair probe green
```

## 8. Acceptance Criteria

`v0_6e` spec is satisfied when:

```text
capture_radius_m is numeric and empirically measured with xy/yaw correction disabled
tol_align_m is derived from capture_radius_m
z-push is gated by capture_radius_m
env-native pass cannot be vetoed by secondary diagnostics
non-seated lateral convergence uses near_band + no-regression
16023 remains env-native pass
at least one lateral seed remains env-native pass
every non-seated lateral seed is converged with no late regression
repair_probe_green_light=true
fixed_40_run_gate_opened=false
heldout_opened=false
```

If these criteria pass, the next slice may open the fixed 40-run train-generation
gate. It still must not open held-out A/B until the 40-run gate passes.

