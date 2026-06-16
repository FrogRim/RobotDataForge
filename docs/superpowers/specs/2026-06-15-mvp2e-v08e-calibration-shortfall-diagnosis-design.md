# MVP-2E v0.8e Calibration Shortfall Diagnosis Design

## 목적

`v0_8e`는 `v0_8d` 실제 Isaac fresh calibration 실패를 artifact-only로
분류하는 diagnosis slice다.

`v0_8d`는 candidate가 baseline보다 좋아졌지만 calibration gate를 통과하지
못했다.

```text
baseline_success_count=17/30
candidate_success_count=21/30
candidate_minus_baseline_success_gap=0.133333333333
candidate_failures_total=9
candidate_failures_maximum=3
fresh_heldout_27000_27049_accessed=false
mvp2_closed=false
```

따라서 다음 단계는 수리 추측이 아니라, 실패 9개의 구조를 분류하고 다음
repair slice가 어떤 실패를 줄여야 하는지 고정하는 것이다.

## Source Evidence

Source gate:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_8d_capture_conditioned_progress_authority/calibration_presignal_gate_v0_8d.json
```

Source traces:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_8d_capture_conditioned_progress_authority/
  isaac_runtime_fresh_calibration_v0_8d/isaac_runtime_heldout_rollout_traces/
```

The path label `heldout_rollout_traces` is legacy naming only. The seed range is
calibration `26500-26529`, not held-out.

## Authority Boundary

`v0_8e` has no closure authority.

It must not:

```text
open fresh held-out 27000-27049
change success metric
change calibration thresholds
rerun Isaac
modify action authority
claim policy uplift
claim MVP-2 Closed
```

It may:

```text
read v0_8d calibration gate
read v0_8d calibration trace JSON
classify candidate failures
write diagnosis JSON
recommend a downstream repair slice
```

## Failure Taxonomy

Classify only candidate failures from `v0_8d` calibration.

### `late_z_open_depth_shortfall`

The policy eventually centers enough to descend, but z opens too late to reach
the seat window inside the 150-step horizon.

Signals:

```text
env_native_first_success_step is null
max_insertion_depth_m < 0.024
min_lateral_error_m <= 0.0006
z_open_step >= 84 OR first_depth_positive_step >= 119
z_open_row_count > 0
```

### `late_seat_window_shortfall`

The policy reaches the env-native seat region, but too late to accumulate
10 consecutive success steps.

Signals:

```text
env_native_first_success_step is not null
env_native_max_consecutive_success_steps < 10
max_insertion_depth_m >= 0.024
```

### `off_center_no_capture`

The policy opens z and pushes for many steps, but remains outside the capture
region and never gets meaningful insertion depth.

Signals:

```text
max_insertion_depth_m <= 0.001
min_lateral_error_m >= 0.002
z_open_row_count >= 50
```

### `unclassified`

Any failed candidate trace that does not match the above classes. The diagnosis
must fail closed if this count is non-zero.

## Required Diagnosis Outputs

```text
v0_8e_calibration_shortfall_diagnosis/v0_8e_calibration_shortfall_diagnosis.json
v0_8e_calibration_shortfall_diagnosis/candidate_failure_taxonomy_v0_8e.json
evidence_manifest.json
```

The top-level diagnosis must include:

```text
source_policy_slice=v0_8d
policy_slice=v0_8e
runtime_backend=offline_artifact_diagnosis
proof_authority=false
mvp2_closed=false
policy_uplift_proven=false
calibration_opened=true
heldout_opened=false
fresh_heldout_27000_27049_accessed=false
candidate_failures_total=9
candidate_failures_to_recover_for_calibration_gate=6
failure_taxonomy
recommended_downstream_slice
recommended_downstream_constraints
```

## Downstream Recommendation

If `late_z_open_depth_shortfall` plus `late_seat_window_shortfall` explain the
shortfall and `unclassified=0`, recommend:

```text
v0_8f_horizon_reserved_capture_authority
```

The recommended downstream slice must:

```text
use a fresh calibration range, not 26500-26529
keep held-out 27000-27049 sealed until calibration passes
preserve env-native 10-consecutive success authority
preserve shared baseline/candidate action authority
preserve attribution-delta reporting
avoid retry/withdraw/search/force-control
target earlier z-open and enough horizon reserve for 10-step hold
avoid making the shared authority so strong that baseline/candidate gap collapses
```

## Success Criteria

`v0_8e` succeeds when:

```text
v0_8d failed calibration gate is required
all 60 v0_8d calibration traces are present
candidate failures are classified with unclassified=0
fresh held-out 27000-27049 is reported sealed
diagnosis JSON and taxonomy JSON are hash-stable
evidence_manifest records diagnostic-only authority
focused tests pass
```

## Non-Claims

Do not claim:

```text
MVP-2 Closed
policy uplift proven
held-out A/B passed
real robot success
deployable policy
visual policy performance
HMD/OpenXR readiness
```
