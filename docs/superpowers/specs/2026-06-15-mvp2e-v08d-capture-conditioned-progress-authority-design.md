# MVP-2E v0.8d Capture-Conditioned Progress Authority Design

## 목적

`v0_8d`는 `v0_8c` shortfall diagnosis에서 분리된 세 실패 모드를 대상으로
하는 다음 repair slice다.

이 slice의 목표는 실제 Isaac closure를 바로 재시도하는 것이 아니라, 먼저
fresh calibration에서 다음 조건을 검증하는 것이다.

```text
1. v0_8b late-seat failures를 줄일 만큼 z가 더 일찍 열린다.
2. off-center no-capture 상황에서 z push가 무작정 지속되지 않는다.
3. centered under-depth 상황에서 depth progress 부족이 계측된다.
4. shared authority가 candidate/baseline 차이를 지우지 않는다.
```

## Source Evidence

Source diagnosis:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_8c_heldout_shortfall_diagnosis/v0_8c_shortfall_diagnosis.json
```

Source result:

```text
baseline_success_rate=0.76
candidate_success_rate=0.88
curated_vs_uncurated_uplift=0.12
mvp2_closed=false
```

Failure taxonomy:

```text
late_seat_window_shortfall: 26007, 26047
centered_under_depth_progress: 26008, 26034
off_center_no_capture: 26009, 26043
unclassified: none
```

Burned held-out ranges:

```text
21000-21049
24000-24049
26000-26049
```

## v0.8d Authority Envelope

Allowed:

```text
earlier z deadline
pre-z capture conditioning
post-z-open depth progress monitor
bounded monotonic z progress authority
shared candidate/baseline authority
action-level attribution preservation gate
```

Forbidden:

```text
retry
withdraw
search
force control
held-out-specific tuning
candidate-only action adapter
baseline suppression
success metric changes
```

## Pre-Registered Parameters

### Earlier z deadline

`v0_8b` showed max observed z-to-first-success latency of 70 control steps.
The env-native hold window requires 10 consecutive success steps inside a
150-step episode. The last viable first-success step is 138, so the latest
deadline that covers the observed max latency is:

```text
early_z_deadline_step=68
```

This uses burned `v0_8b` diagnostics only to define a future fresh slice. It is
not applied retroactively to `v0_8b`.

### Capture conditioning

`v0_8b` no-capture failures opened z with lateral around 4-5 mm and produced
zero insertion depth. Therefore `v0_8d` introduces a capture preparation window.

```text
capture_prepare_start_step=56
capture_lateral_gate_m=0.0035
```

Rule:

```text
if step >= capture_prepare_start_step
and depth < seat_region_depth_m
and lateral > capture_lateral_gate_m:
  z must be blocked
  xy capture-centering authority remains active
  diagnostics.reason = "capture_conditioning_wait"
```

### Z-open progress monitor

Once z opens, the controller must record whether insertion depth progresses.

```text
depth_progress_window_steps=12
minimum_depth_progress_m=0.001
under_depth_progress_threshold_m=0.024
```

Rule:

```text
if z has been open for depth_progress_window_steps
and depth_delta_since_z_open < minimum_depth_progress_m:
  z remains monotonic but is marked under_depth_progress_watch
  diagnostics must record the watch condition
```

The monitor is diagnostic and bounded. It must not change success authority and
must not introduce withdraw/search behavior.

## Fresh Split Policy

Fresh calibration:

```text
26500-26529
```

Future held-out candidate range:

```text
27000-27049
```

`27000-27049` must remain sealed until calibration/pre-signal gates pass.

## Required Artifacts

```text
v0_8d_capture_conditioned_progress_authority_config.json
candidate_policy_artifact_v0_8d.json
baseline_policy_artifact_v0_8d.json
v0_8d_fresh_manifest.json
calibration_presignal_gate_v0_8d.json
```

Held-out closure artifact is allowed only after calibration passes:

```text
heldout_closure_gate_v0_8d.json
```

## Calibration Gate

Calibration must fail closed unless:

```text
actual_rollouts_per_policy >= 30
candidate_success_rate > baseline_success_rate
candidate_minus_baseline_success_rate >= 0.10
candidate_failures_total <= 3
attribution_preservation_gate_passed=true
fresh_heldout_27000_27049_accessed=false
```

This is not MVP-2 closure. It only authorizes opening the fresh held-out range.

## Attribution Preservation

The same v0.8d authority must be used for baseline and candidate. Because shared
authority can erase uplift, the calibration artifact must report:

```text
candidate_baseline_post_authority_action_delta_l2_mean
candidate_baseline_post_authority_action_delta_nonzero_fraction
candidate_baseline_success_gap
```

Gate:

```text
candidate_baseline_post_authority_action_delta_l2_mean > 1e-6
candidate_baseline_post_authority_action_delta_nonzero_fraction >= 0.10
```

## Non-Claims

Do not claim:

```text
mvp2_closed=true
policy_uplift_proven=true
proof_eligible=true
real_robot_success=true
deployable_real_robot_policy=true
visual_policy_performance=true
hmd_openxr_readiness=true
```

## Success Criteria

`v0_8d` implementation is successful when:

```text
1. v0_8d policy artifacts and manifest are created from v0_8c diagnosis.
2. burned held-out ranges are recorded and rejected for closure reuse.
3. fresh calibration 26500-26529 can run before any held-out 27000-27049 access.
4. v0_8d authority diagnostics expose capture conditioning and depth progress watch.
5. attribution preservation is tested.
6. focused tests and static verification pass.
```
