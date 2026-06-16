# MVP-2E v0.8h Early-Centered Z Open / Safe Entry Authority Design

## 목적

`v0_8h`는 `v0_8g` 실제 Isaac fresh calibration 실패에서 확인된
off-center z-open 문제를 새 fresh calibration split에서 수리하는 repair
slice다.

`v0_8g`는 held-out `27000-27049`를 열지 않고 fail-closed했다.

```text
baseline_success_count=17/30
candidate_success_count=20/30
candidate_minus_baseline_success_gap=0.10
candidate_failures_total=10
failure_reason=candidate_failures_above_maximum
heldout_opened=false
fresh_heldout_27000_27049_accessed=false
mvp2_closed=false
```

## 확인된 Root Cause

`v0_8g`는 `v0_8f`의 z-window 부족을 고치기 위해 deadline 이후 z progress를
항상 강제했다. 이 precedence는 z-window를 복구했지만, lateral이 아직 unsafe한
seed에서도 step 68부터 z를 열었다.

`v0_8g` candidate failure traces의 공통 신호:

```text
first_z_step=68
longest_z_window≈80
failed seeds=10/30
many failures open z at lateral≈0.004-0.009m
several failures have depth≈0 or shallow depth
28027 reaches env-native only too late for 10-consecutive window
```

따라서 남은 결함은 더 이상 "z가 너무 짧다"가 아니다.

```text
1. centered seed도 step 68까지 z를 막아 hole 입구 도달 시간이 늦어진다.
2. off-center seed도 step 68 이후에는 lateral과 무관하게 z를 열어 rim-side
   miss 또는 shallow depth를 만든다.
```

## Authority Boundary

`v0_8h`는 `v0_8g` artifact를 소급 수정하지 않는다.

`v0_8h`는 반드시:

```text
새 policy_slice=v0_8h 사용
새 fresh calibration range=28500-28529 사용
held-out 27000-27049는 calibration pass 전까지 봉인
env-native 10-consecutive success authority 유지
baseline/candidate 동일 shared authority 사용
retry/withdraw/search/force-control 금지
v0_8g calibration artifact를 source evidence로만 사용
```

`v0_8h`는 하지 않는다.

```text
v0_8g historical result overwrite
v0_8g calibration 28000-28029 재사용
held-out 27000-27049 선개봉
success metric 변경
policy uplift claim before held-out
real robot/HMD/visual/deployable policy claim
```

## v0.8h Runtime Rule

`v0_8h`의 핵심은 `deadline force`가 아니라 `safe entry`다. z progress는
centered 상태에서는 더 일찍 열고, unsafe lateral 상태에서는 deadline 이후에도
막는다.

Pre-registered constants:

```text
capture_prepare_start_step=56
reference_deadline_step=68
safe_entry_lateral_gate_m=0.005
depth_progress_continuation_lateral_gate_m=0.006
seat_region_depth_m=0.024
z_progress_action=-0.16
```

Priority:

```text
1. env_native_success == true
   -> do not force z; preserve stable hold behavior

2. depth > 0 and lateral <= depth_progress_continuation_lateral_gate_m
   -> keep z_progress_action until env-native success or seat region
   -> reason=depth_progress_continuation_z

3. step >= capture_prepare_start_step and lateral <= safe_entry_lateral_gate_m
   -> open z_progress_action before the old deadline if already centered
   -> reason=early_centered_safe_entry_z

4. step >= capture_prepare_start_step and lateral > safe_entry_lateral_gate_m
   -> z=0, recompute XY recenter, even after reference_deadline_step
   -> reason=unsafe_lateral_z_block

5. step < capture_prepare_start_step
   -> z=0
   -> reason=before_capture_prepare_start
```

The crucial invariants:

```text
If step >= 56 and lateral <= 0.005 and env_native_success=false, post-adapter z
must be -0.16.

If step >= 68 and lateral > 0.005 and depth == 0 and env_native_success=false,
post-adapter z must remain 0.0.

If depth > 0 and lateral <= 0.006 and env_native_success=false, z progress may
continue so the authority does not reintroduce short z-window chatter.
```

## Threshold Rationale

`safe_entry_lateral_gate_m=0.005`는 held-out 결과가 아니라 `v0_8g` calibration
failure diagnostics에서 도출한 engineering repair threshold다.

관측 근거:

```text
v0_8g candidate successes mostly opened z at lateral <= 0.004318m.
v0_8g candidate failures mostly opened z at lateral > 0.004m.
several failed seeds were already <= 0.005 before step 68, but v0_8g still
delayed them until the deadline and/or opened after lateral drift.
```

`0.005`는 proof metric이 아니다. 이 값은 action-authority repair의 shared
runtime constant이며, calibration/held-out success authority는 계속
env-native 10-consecutive다.

`depth_progress_continuation_lateral_gate_m=0.006`은 depth가 이미 양수인 구간에서
short z-window chatter를 막기 위한 continuation guard다. 이는 success authority를
완화하지 않으며, unsafe lateral에서 z를 무조건 여는 v0.8g deadline precedence를
복구하지 않는다.

## Fresh Evidence Protocol

Source evidence:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_8g_deadline_precedence_horizon_authority/calibration_presignal_gate_v0_8g.json
```

Fresh calibration:

```text
28500-28529
```

Fresh held-out, still sealed until calibration passes:

```text
27000-27049
```

Burned ranges:

```text
held-out:
  21000-21049
  24000-24049
  26000-26049

calibration:
  26500-26529
  27500-27529
  28000-28029
```

## Calibration Gate

Same gate semantics as prior slices:

```text
actual_rollouts_per_policy >= 30 for calibration
candidate_success_rate > baseline_success_rate
candidate_baseline_success_gap >= 0.10
candidate_failures_total <= 3
attribution_preservation_gate_passed=true
```

If calibration fails:

```text
heldout_opened=false
fresh_heldout_27000_27049_accessed=false
mvp2_closed=false
next step = preserve evidence and diagnose the new shortfall
```

If calibration passes:

```text
open held-out 27000-27049 once
run 50 rollouts/policy
MVP-2 closes only if candidate-baseline uplift >= 0.20 and all proof gates pass
```

## Required Outputs

```text
v0_8h_early_centered_z_open_safe_entry/
  v0_8h_early_centered_z_open_safe_entry_config.json
  v0_8h_fresh_manifest.json
  candidate_policy_artifact_v0_8h.json
  baseline_policy_artifact_v0_8h.json
  calibration_runtime_manifest_v0_8h.json
  calibration_presignal_gate_v0_8h.json
  heldout_runtime_manifest_v0_8h.json            # only if calibration passes
  heldout_closure_gate_v0_8h.json                # only if held-out runs
```

Top-level `evidence_manifest.json` must record:

```text
policy_slice=v0_8h
proof_runtime=mvp2e_v08h_early_centered_z_open_safe_entry
calibration_opened=true
heldout_opened=<actual>
fresh_calibration_28500_28529_accessed=true
fresh_heldout_27000_27049_accessed=<actual>
mvp2_closed=<actual>
policy_uplift_proven=<actual>
```

## Success Criteria

`v0_8h` implementation is ready when:

```text
Evaluator tests prove early centered z opens before the old deadline.
Evaluator tests prove unsafe lateral blocks z even after the old deadline.
Evaluator tests prove depth-progress continuation avoids z-window chatter.
Builder tests prove fresh calibration/held-out ranges and peer fairness.
CLI tests prove calibration before held-out using fake Isaac.
Focused and static checks pass.
Actual Isaac v0_8h proof attempt runs.
Held-out remains sealed if calibration fails.
```

## Non-Claims

Do not claim:

```text
MVP-2 Closed before held-out A/B pass
policy uplift from calibration only
real robot success
physical robot readiness
HMD/OpenXR readiness
visual policy performance
deployable policy
```
