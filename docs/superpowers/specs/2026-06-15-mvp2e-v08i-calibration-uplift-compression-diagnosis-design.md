# MVP-2E v0.8i Calibration Uplift Compression Diagnosis Design

## 목적

`v0_8i`는 `v0_8h` 실제 Isaac fresh calibration 실패를 artifact-only로
분류하는 diagnosis slice다.

`v0_8h`는 held-out `27000-27049`를 열지 않고 fail-closed했다.

```text
baseline_success_count=23/30
candidate_success_count=25/30
candidate_minus_baseline_success_gap=0.066666666666
candidate_failures_total=5
heldout_opened=false
fresh_heldout_27000_27049_accessed=false
mvp2_closed=false
```

`v0_8h`의 핵심 변화는 off-center z-open을 막고 centered seed의 z-open을
앞당기는 것이었다. 실제 결과는 candidate success를 25/30까지 올렸지만,
shared authority가 baseline도 23/30까지 올려 uplift gap이 압축되었다.

따라서 다음 단계는 수리 추측이 아니라 아래 두 현상을 분리해 기록하는 것이다.

```text
1. candidate hard failure 5개가 어떤 실패 모드인지
2. baseline이 shared authority로 너무 많이 성공해 uplift gap이 왜 낮아졌는지
```

## Source Evidence

Source gate:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_8h_early_centered_z_open_safe_entry/calibration_presignal_gate_v0_8h.json
```

Source traces:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_8h_early_centered_z_open_safe_entry/
  isaac_runtime_fresh_calibration_v0_8h/isaac_runtime_heldout_rollout_traces/
```

The path label `heldout_rollout_traces` is legacy naming only. The seed range is
fresh calibration `28500-28529`, not held-out.

## Authority Boundary

`v0_8i` has no closure authority.

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
read v0_8h calibration gate
read v0_8h calibration trace JSON
classify candidate failures
compute paired baseline/candidate outcome counts
write diagnosis JSON
recommend a downstream repair slice
```

## Failure Taxonomy

Classify only candidate failures from `v0_8h` calibration.

### `late_seat_window_shortfall`

The policy reaches the env-native seat region, but too late to accumulate 10
consecutive success steps.

Signals:

```text
env_native_first_success_step is not null
env_native_max_consecutive_success_steps < 10
max_insertion_depth_m >= 0.024
```

### `under_depth_late_entry`

The policy centers and descends, but depth remains below the env-native seat
window because z opens too late or progresses too slowly.

Signals:

```text
env_native_first_success_step is null
max_insertion_depth_m < 0.024
min_lateral_error_m <= 0.0015
z_open_row_count > 0
first_depth_positive_step >= 110 OR z_open_step >= 80
```

### `centered_no_depth_contact_miss`

The policy opens z for many steps while laterally near the target, but never
gets meaningful insertion depth.

Signals:

```text
env_native_first_success_step is null
max_insertion_depth_m <= 0.001
min_lateral_error_m <= 0.003
z_open_row_count >= 50
```

### `unclassified`

Any failed candidate trace that does not match the above classes. The diagnosis
must fail closed if this count is non-zero.

## Paired Outcome Diagnosis

The diagnosis must compute paired baseline/candidate outcomes:

```text
B1_C1: both succeed
B0_C1: candidate-only success
B1_C0: baseline-only success
B0_C0: both fail
```

For v0.8h actual evidence the expected shape is:

```text
B1_C1 is high
B0_C1 is small
B1_C0 is zero
B0_C0 is candidate hard-failure residue
```

This must be reported as `baseline_success_compression=true` when:

```text
baseline_success_count >= 20
candidate_only_success_count <= 3
candidate_baseline_success_gap < 0.10
```

## Required Diagnosis Outputs

```text
v0_8i_calibration_uplift_compression_diagnosis/
  v0_8i_calibration_uplift_compression_diagnosis.json
  candidate_failure_taxonomy_v0_8i.json
evidence_manifest.json
```

The top-level diagnosis must include:

```text
source_policy_slice=v0_8h
policy_slice=v0_8i
runtime_backend=offline_artifact_diagnosis
proof_authority=false
mvp2_closed=false
policy_uplift_proven=false
calibration_opened=true
heldout_opened=false
fresh_heldout_27000_27049_accessed=false
candidate_failures_total=5
candidate_failures_to_recover_for_calibration_gate=2
paired_outcome_counts
baseline_success_compression
failure_taxonomy
recommended_downstream_slice
recommended_downstream_constraints
```

## Downstream Recommendation

If candidate failures are fully classified and baseline success compression is
true, recommend:

```text
v0_8j_attribution_preserving_candidate_margin_repair
```

The recommended downstream slice must:

```text
use a fresh calibration range, not 28500-28529
keep held-out 27000-27049 sealed until calibration passes
preserve env-native 10-consecutive success authority
preserve same shared safety/action authority for baseline and candidate
avoid further strengthening shared authority that benefits baseline and candidate equally
increase candidate-specific learned residual margin on hard seeds
preserve attribution-delta reporting
avoid retry/withdraw/search/force-control
```

## Success Criteria

`v0_8i` succeeds when:

```text
v0_8h failed calibration gate is required
all 60 v0_8h calibration traces are present
candidate failures are classified with unclassified=0
paired outcome counts match the v0_8h gate
baseline success compression is reported
fresh held-out 27000-27049 is reported sealed
diagnosis JSON and taxonomy JSON are hash-stable
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
