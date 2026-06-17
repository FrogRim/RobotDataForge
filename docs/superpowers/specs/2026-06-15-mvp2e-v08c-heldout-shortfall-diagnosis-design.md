# MVP-2E v0.8c Held-Out Shortfall Diagnosis Design

## 목적

`v0_8b` actual Isaac held-out closure run은 실제 50/50 policy A/B를 수행했지만
MVP-2 Closed 조건을 만족하지 못했다. `v0_8c`의 목적은 새 controller를 바로
튜닝하거나 새 held-out을 열지 않고, `v0_8b` evidence를 artifact-only로 분류해
다음 repair slice의 입력을 고정하는 것이다.

이 slice는 closure authority가 아니다.

## v0.8b 고정 evidence

Source artifact:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_8b_scenario_aware_seat_window_authority/
    heldout_closure_gate_v0_8b.json
    v0_8b_seat_window_authority_config.json
    isaac_runtime_fresh_heldout_v0_8b/isaac_runtime_heldout_rollout_traces/
```

Source hashes:

```text
heldout_closure_gate_v0_8b_sha256=f7fb3eff1a6e9ba7a7270cafbd04904b704df41e05bcc1d7929bf45a5ea57e89
v0_8b_seat_window_authority_config_sha256=6d86e524485fbe9418bbbf9f10ae7f4b647279fedd44224097d362ab339a634c
```

Closure result:

```text
actual_rollouts_per_policy=50
baseline_success_rate=0.76
candidate_success_rate=0.88
curated_vs_uncurated_uplift=0.12
mvp2c_close_minimum_passed=false
proof_eligible=false
mvp2_closed=false
fresh_heldout_26000_26049_accessed=true
```

Fresh held-out `26000-26049` is now burned for future closure. Future closure
runs must use a new fresh held-out range.

## 실패 taxonomy

`v0_8b` candidate failures are all `ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED`,
but the per-trace dynamics split into three different classes.

### 1. `late_seat_window_shortfall`

Definition:

```text
env_native_first_success_step is not null
env_native_max_consecutive_success_steps < 10
max_insertion_depth_m >= 0.0248
```

Affected traces:

```text
candidate_0007_held_out_26007_isaac_trace.json
candidate_0047_held_out_26047_isaac_trace.json
```

Interpretation:

The policy reaches the env-native success region too late to accumulate the
required 10 consecutive control steps inside the 150-step episode.

Evidence:

```text
26007: first_success_step=144, max_consecutive=4, z_first=74
26047: first_success_step=139, max_consecutive=9, z_first=74
```

### 2. `centered_under_depth_progress`

Definition:

```text
min_lateral_error_m <= 0.0006
max_insertion_depth_m < 0.024
z_count >= 60
```

Affected traces:

```text
candidate_0008_held_out_26008_isaac_trace.json
candidate_0034_held_out_26034_isaac_trace.json
```

Interpretation:

The policy becomes centered and receives a long z descent window, but vertical
progress does not reach the env-native seating region. This is a progress
monitoring failure, not just a deadline failure.

Evidence:

```text
26008: z_count=68, max_depth=0.022784, min_lateral=0.000310
26034: z_count=68, max_depth=0.004537, min_lateral=0.000286
```

### 3. `off_center_no_capture`

Definition:

```text
max_insertion_depth_m <= 0.001
min_lateral_error_m >= 0.002
z_count >= 60
```

Affected traces:

```text
candidate_0009_held_out_26009_isaac_trace.json
candidate_0043_held_out_26043_isaac_trace.json
```

Interpretation:

The z authority opens while the peg is still outside the effective capture
region. The result is a long z command window with no insertion depth.

Evidence:

```text
26009: z_count=67, max_depth=0.000000, min_lateral=0.002451
26043: z_count=74, max_depth=0.000000, min_lateral=0.002331
```

## Derived repair direction for next slice

The next repair slice must not simply strengthen shared authority across both
policies. Shared authority can raise baseline and erase policy-uplift signal.
It must first preserve candidate/baseline action deltas after authority.

Recommended next repair class:

```text
v0_8d_capture_conditioned_progress_authority
```

Required mechanisms:

```text
1. earlier_z_deadline_step <= 68
2. pre_z_capture_conditioning after the deadline:
   - if outside capture band, z remains blocked
   - xy centering authority remains active
   - diagnostics record capture_wait reason
3. z_open progress monitor:
   - if z has been open for a configured window and depth progress is below
     expected progress, record under_depth_progress_failure
   - repair may use bounded monotonic z progress authority
4. no retry, no withdraw, no search, no force-control
5. same shared authority for baseline and candidate
6. explicit attribution-preservation gate after final authority
```

The repair must be validated on calibration/probe evidence before opening any
new held-out range.

## Fresh seed policy

The following held-out ranges are burned or diagnostic-only for closure:

```text
21000-21049
24000-24049
26000-26049
```

The next closure attempt must pre-register a new fresh held-out range. Suggested
range:

```text
27000-27049
```

The next calibration/probe range must also be fresh and disjoint from all burned
held-out ranges.

## Non-claims

This slice does not claim:

```text
mvp2_closed=true
policy_uplift_proven=true
proof_eligible=true
real_robot_success=true
deployable_real_robot_policy=true
visual_policy_performance=true
hmd_openxr_readiness=true
```

## Success criteria

`v0_8c` is complete when:

```text
1. v0_8b held-out gate and traces are parsed without Isaac runtime.
2. all six candidate failures are assigned to exactly one taxonomy class.
3. the output artifact records burned held-out ranges.
4. the output artifact recommends v0_8d_capture_conditioned_progress_authority.
5. tests prove missing or incomplete v0_8b evidence fails closed.
6. no new held-out range is opened.
```
