# MVP-2E v0.6 Env-native Train-generation Recovery Design

Date: 2026-06-11

## 목적

MVP-2E `v0_6`의 목적은 MVP-2D `v0_5`에서 fail-closed된 actual Isaac
train-generation gate를 새 success authority와 새 seed profile로 다시 정의하고,
held-out A/B를 열기 전에 train-generation material이 충분히 강한지 검증하는 것이다.

`v0_6`은 MVP-2 Closed 선언 자체가 아니다. `v0_6`의 첫 milestone은 아래 gate다.

```text
fixed pre-registered stratified train seed set 40 attempts
-> env-native consecutive success traces >= 20
-> only then calibration freeze and held-out A/B may proceed
```

MVP-2 Closed는 여전히 positive held-out policy uplift다.

```text
candidate_success_rate > baseline_success_rate
curated_vs_uncurated_uplift >= 0.20
```

## 배경

`v0_5` implementation slice는 완료됐지만 actual Isaac train-generation gate에서
멈췄다.

```text
/tmp/rdf-mvp2d-v05-train-gate/train_generation_runtime_gate.json
passed=false
generated_rollout_count=40
generated_success_count=5
required_success_count=20
actual_train_generation_evidence=false
```

Stop rule에 따라 `v0_5` held-out `18000-18019`는 실행하지 않았다.

이후 진단에서 중요한 사실이 드러났다.

- `v0_5`의 `5/40`은 frozen MVP-2C geometry metric
  `lateral_error_m_max=0.006` 기준 결과다.
- 기존 RDF peg-in-hole evaluator는 `peg_tip_distance_to_target_max=0.015`,
  `peg_axis_alignment_error_max_rad=0.25`, `insertion_depth_min=0.025`
  계열의 buyer-facing geometry metric을 가진다.
- Isaac Factory env-native success는 `_get_curr_successes()`에서
  env/task가 직접 정의한 keypoint success를 계산한다.

따라서 `v0_6`은 `v0_5` metric을 patch하지 않는다. `v0_6`은 새
pre-registered profile로 열고, env-native success를 primary closure authority로
freeze한다.

## 비목표

`v0_6`은 다음을 하지 않는다.

- `v0_5` 결과를 소급 pass시키지 않는다.
- `v0_5` held-out `18000-18019`를 열지 않는다.
- `0.015` RDF metric을 보고 `v0_5`를 다시 해석해 closure claim으로 쓰지 않는다.
- success metric, stable window, seed selection, probe pass rule을 실행 결과를 본 뒤
  바꾸지 않는다.
- force-reactive controller, retry/recover, withdraw/reinsert, search pattern을
  구현하지 않는다.
- policy/trainer/dataset view/selected action adapter를 이 slice에서 바꾸지 않는다.
- real robot success, physical robot readiness, HMD readiness, deployable visual
  policy performance를 주장하지 않는다.

## Primary Success Authority

`v0_6`부터 train-generation gate, calibration result, held-out policy A/B closure는
env-native success를 primary authority로 사용한다.

Peg insertion의 env-native success 호출은 Isaac Lab Factory/Forge env의 reward
path와 동일하게 둔다.

```text
env._get_curr_successes(
  success_threshold=env.cfg_task.success_threshold,
  check_rot=false
)
```

고정 근거:

```text
task=peg_insert
success_threshold=0.04
fixed_asset.height=0.025
height_threshold=0.025 * 0.04 = 0.001 m
xy_dist_threshold=0.0025 m
check_rot=false
```

이 기준은 NVIDIA Isaac Lab Factory task가 제공하는 exogenous task success
function이다. RDF가 `v0_5` 결과를 보고 threshold를 고르는 구조를 피하기 위해,
`v0_6` closure authority는 이 env-native function으로 freeze한다.

### Stability Window

Per-step env-native success first-hit만으로 rollout success를 인정하지 않는다.

`v0_6` rollout success:

```text
max_consecutive(env_native_success_mask) >= 10 control steps
```

`stable_steps_required=10`은 MVP-2C에서 상속한 값이다. 이 값은 `v0_5`
env-native recomputation 전에 이미 존재한 값이므로 새롭게 결과를 보고 고른
값이 아니다.

Required trace fields:

```text
env_native_success_mask_per_step
env_native_first_success_step
env_native_max_consecutive_success_steps
env_native_rollout_success
```

### Secondary Diagnostics

RDF `peg_in_hole` geometry metric은 buyer-facing continuity와 debugging을 위해
기록하지만 closure authority가 아니다.

Diagnostic-only fields:

```text
rdf_peg_in_hole_metric
rdf_first_success_step
rdf_max_consecutive_success_steps
lateral_error_m
insertion_depth_m
orientation_error_deg
seated_at_horizon
```

## Profile Identity

`v0_6`은 fresh profile이다.

```text
scenario_profile=v0_6
manifest_version=rdf_mvp2e_scenario_manifest_v0.6.0
```

`v0_5`는 historical fail-closed slice로 보존한다.

```text
v0_5 metric=connector_insertion_geometry_stability_v0
v0_5 result=5/40 under frozen v0_5 train-generation gate
v0_5 closure=false
```

`v0_5` trace를 env-native으로 재계산할 수 있더라도 그 결과는 engineering
diagnostic only다. Closure는 오직 fresh `v0_6` proof path에서만 가능하다.

## Seed Ranges

`v0_6`은 probe seed와 proof gate seed를 분리한다.

### Repair Probe Seeds

Probe는 repair validation only다. Proof authority가 없다.

```text
16023 near-stability / hold mechanism
16042 moderate lateral divergence mechanism
16096 severe lateral divergence mechanism
```

Probe seeds는 `v0_5` failed train-side traces에서 온다. 이들은 `v0_6`
train/calibration/held-out에 포함하지 않는다.

### Fresh v0_6 Ranges

```text
train_success range: 19000-19159
train_failure/noisy range: 19200-19359
calibration range: 20000-20029
held_out range: 21000-21049
```

`held_out=21000-21049`는 50 seeds를 한 번에 봉인한다. Engineering close
minimum은 20 rollouts per policy일 수 있지만, stronger public evidence target을
나중에 보기 위해 held-out range를 사후 확장하지 않는다.

Excluded ranges include:

```text
3000-3019
6000-6019
9000-9019
12000-12019
15000-15019
16000-16159
18000-18019
16023
16042
16096
```

Manifest build는 모든 train/calibration/held-out/probe/excluded seed set의
disjointness를 programmatically 검증해야 한다. 겹치면 `ValueError`로 실패한다.

## Fixed Stratified 40 Train Gate Set

Train-generation gate는 `19000-19159`에서 build-time config difficulty로 40 seeds를
deterministic하게 선택한다.

선정은 Isaac rollout 결과, success/failure 결과, RNG를 사용하지 않는다.

Difficulty cell:

```text
offset_class = abs((seed % 9) - 4)          # 0..4
orient_class = abs(((seed // 5) % 11) - 5)  # 0..5
difficulty_cell = (offset_class, orient_class)
```

Selection rule:

```text
1. enumerate every seed in 19000-19159
2. group by difficulty_cell
3. allocate 40 seeds across the grid as evenly as possible
4. guarantee representative extreme cells
5. tie-break inside each cell by lowest seed id
```

Manifest fields:

```text
v0_6_train_gate_seed_selection.source_range
v0_6_train_gate_seed_selection.difficulty_cell_formula
v0_6_train_gate_seed_selection.allocation_rule
v0_6_train_gate_seed_selection.tie_break_rule
v0_6_train_gate_seed_selection.selected_40_seed_ids
v0_6_train_gate_seed_selection.selection_config_sha256
v0_6_train_gate_seed_selection.selected_seed_list_sha256
```

Limitations:

- This is config coverage, not a proven physical difficulty oracle.
- Initial offset/orientation are weak difficulty proxies.
- The `v0_6` initial-condition distribution remains narrow. Wider distributions
  require a future pre-registered slice.

## Repair Probe Rule

Probe purpose is to decide whether the repair is ready for the fresh 40-run gate.
It does not prove closure.

Green light:

```text
A. seed 16023 env-native consecutive success >= 10
B. seed 16042 or 16096 env-native consecutive success >= 10
C. seed 16042 and 16096 both satisfy lateral_divergence_stopped
```

Hard stop:

```text
seed 16023 fails env-native consecutive success >= 10
OR both lateral seeds still diverge
OR trace lacks required lateral/error diagnostics
```

Severe seed `16096` full seat is diagnostic, not mandatory. However, divergence
must stop on both lateral seeds before opening the 40-run gate.

### Lateral Divergence Diagnostic

`lateral_divergence_stopped`:

```text
max_lateral_error_m < 0.008
AND median(last_10_lateral_error_m) <= initial_lateral_error_m + 0.002
```

Definitions:

```text
lateral_error_m = sqrt(relative_x_m^2 + relative_y_m^2)
last_K = 10 control steps
divergence_cap_m = 0.008
final_drift_margin_m = 0.002
```

Rationale:

```text
expected initial config lateral <= about 0.0022 m
observed v0_5 lateral failure floor >= about 0.011 m
diagnostic gap=[0.0022, 0.011]
chosen cap=0.008
```

This diagnostic cap is not a success metric. It is a pre-registered repair
go/no-go signal that prevents running the full 40-seed gate when the dominant
lateral divergence mechanism is still present.

## Chamfer Preflight Gate

Before freezing INSERT parameters, run a mandatory static geometry preflight.

Primary inspection target:

```text
factory_hole_8mm.usd
factory_peg_8mm.usd
```

Known config values:

```text
peg diameter=0.007986 m
hole diameter=0.008100 m
radial clearance=(0.008100 - 0.007986) / 2 = 0.000057 m
```

Preflight scope:

```text
blocks INSERT parameter freeze only
does not block ALIGN / DESCEND / HOLD implementation
```

Three branches:

```text
Branch A:
  chamfer/lead-in present and measurable
  capture_radius_m=measured_or_estimated
  INSERT push/correction params derived from geometry
  proceed to repair probe

Branch B:
  chamfer/lead-in present but capture radius approximate
  capture_radius_m=approximate
  conservative bounded push + modest correction gain allowed
  proceed to repair probe
  if probe shows align-then-jam, escalate to blocker

Branch C:
  chamfer absent OR geometry uninspectable
  STOP
  do not freeze INSERT params
  do not run repair probe
  do not run 40-run gate
```

Manifest fields:

```text
chamfer_preflight.chamfer_present
chamfer_preflight.capture_radius_m
chamfer_preflight.inspection_method
chamfer_preflight.source_asset_paths
chamfer_preflight.source_asset_sha256
chamfer_preflight.derived_insert_params
chamfer_preflight.derivation_rationale
chamfer_preflight.preflight_branch
```

Static USD/mesh inspection is the first choice. Empirical Isaac capture probing is
fallback only.

## Controller Repair Envelope

`v0_6` uses complete minimal state-based repair. It is not a new contact-rich
search controller.

Allowed:

```text
live target re-read every step
active phase state: ALIGN / DESCEND / INSERT / HOLD
condition-gated phase transitions
z descent gated by lateral/orientation alignment
continued lateral/yaw correction through DESCEND and INSERT
bounded monotonic downward push in INSERT
env-native success hold for 10 consecutive steps
instrumentation and trace diagnostics
```

Disallowed:

```text
force-reactive control
retry/recover
withdraw and reinsert
search pattern
per-seed tuning
selected action adapter change
policy/trainer change
dataset view change
held-out access
success metric relaxation
```

Phase behavior:

```text
ALIGN:
  hold z above rim
  servo xy/yaw
  exit when alignment gate is satisfied

DESCEND:
  continue xy/yaw correction
  lower z only while alignment gate remains satisfied
  if lateral drifts out of gate, pause z and re-align in place

INSERT:
  monotonic bounded downward push
  continue xy/yaw correction
  no search, no withdraw, no retry
  exit when env-native success begins

HOLD:
  maintain pose
  success when env-native mask is true for 10 consecutive control steps
```

This remains BC-friendly because it is a single-pass monotonic state-action
trajectory, not a multimodal retry/search policy.

## Close Gates

Train-generation gate:

```text
scenario_profile=v0_6
train_gate_seed_count=40
generated_success_count >= 20
success_authority=env_native_consecutive_success_v0
stable_steps_required=10
training_trajectory_source=isaac_runtime_scripted_expert_rollout
train_generation_runtime_gate.passed=true
```

MVP-2 Closed still additionally requires:

```text
actual_rollouts_per_policy >= 20
candidate_success_rate > baseline_success_rate
curated_vs_uncurated_uplift >= 0.20
learning_validator.proof_eligible=true
learning_validator.evidence_tier=external_heldout_policy_eval
mvp2_closed=true
```

Stronger public evidence target remains separate:

```text
actual_rollouts_per_policy >= 50 per policy preferred
confidence interval reported
stronger_public_evidence_target_passed=true
```

## Stop Rules

Stop and report if:

- chamfer preflight returns Branch C.
- env-native success cannot be measured per step.
- trace cannot record env-native success mask and lateral diagnostics.
- repair probe hard-stops.
- train-generation gate produces fewer than 20 successes out of fixed 40 seeds.
- implementation would need force control, retry/search, held-out tuning, success
  metric relaxation, policy/trainer changes, dataset view changes, or selected
  action adapter changes.
- any implementation path requires opening held-out `21000-21049` before
  train-generation gate and calibration freeze.

## Next Implementation Handoff

The next implementation plan should create `v0_6` without modifying `v0_5`
history.

Implementation should proceed in this order:

1. Add `v0_6` manifest/schema tests.
2. Add env-native success authority fields and stable-window reporting.
3. Add seed disjointness and config-difficulty 40-subset selection.
4. Add repair probe pack and go/no-go diagnostics.
5. Add chamfer preflight artifact.
6. Add complete minimal state-based repair envelope.
7. Run repair probe only.
8. If green, run fresh fixed 40 train-generation gate.
9. Do not run held-out until the train-generation gate passes and calibration is
   frozen.
