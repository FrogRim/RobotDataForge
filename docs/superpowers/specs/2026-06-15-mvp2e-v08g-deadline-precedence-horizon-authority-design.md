# MVP-2E v0.8g Deadline-Precedence Horizon Authority Design

## 목적

`v0_8g`는 `v0_8f` 실제 Isaac fresh calibration 실패에서 확인된
action-authority precedence 버그를 새 fresh calibration split에서 수리하는
repair slice다.

`v0_8f`는 held-out `27000-27049`를 열지 않고 fail-closed했다.

```text
baseline_success_count=15/30
candidate_success_count=17/30
candidate_minus_baseline_success_gap=0.066666666667
candidate_failures_total=13
heldout_opened=false
fresh_heldout_27000_27049_accessed=false
mvp2_closed=false
```

## 확인된 Root Cause

`v0_8f`의 설계 의도는 다음이었다.

```text
step < 56: 기존 shared authority
56 <= step < 68 and lateral > capture gate: z=0, XY recenter
step >= 68 and env_native_success=false: z=-0.16 forced progress
env_native_success=true: z force 중지, stable window 유지
```

하지만 실제 evaluator 구현은 `capture_wait_xy_authority`를
`horizon_reserved_z_deadline_step`보다 먼저 평가했다.

```python
elif step >= capture_prepare_start_step and lateral > capture_lateral_gate_m:
    after[2] = 0.0
elif step < horizon_reserved_z_deadline_step:
    after[2] = 0.0
else:
    after[2] = z_progress_action
```

따라서 deadline 이후에도 lateral이 gate보다 크면 z가 계속 차단된다. 실제
`v0_8f` failure traces에서 이 현상이 관측됐다.

```text
success traces: first_z≈68, first_depth≈92, env_native_max_consecutive=10
failure traces: first_z≈89, first_depth≈181 average, candidate_failures=13
worst case: calibration_27510 first_z=130, first_depth=None, max_depth=0
```

즉 `v0_8f` 실패의 주 원인은 새 policy/trainer 문제가 아니라, deadline reserved
progress authority가 capture-wait branch에 의해 무력화된 구현 precedence
오류다.

## Authority Boundary

`v0_8g`는 `v0_8f` artifact를 소급 수정하지 않는다.

`v0_8g`는 반드시:

```text
새 policy_slice=v0_8g 사용
새 fresh calibration range=28000-28029 사용
held-out 27000-27049는 calibration pass 전까지 봉인
env-native 10-consecutive success authority 유지
baseline/candidate 동일 shared authority 사용
retry/withdraw/search/force-control 금지
v0_8f calibration artifact를 source evidence로만 사용
```

`v0_8g`는 하지 않는다.

```text
v0_8f historical result overwrite
v0_8f calibration 27500-27529 재사용
held-out 27000-27049 선개봉
success metric 변경
policy uplift claim before held-out
real robot/HMD/visual/deployable policy claim
```

## v0.8g Runtime Rule

Priority must be:

```text
1. env_native_success == true
   -> do not force z; preserve stable hold behavior

2. step >= horizon_reserved_z_deadline_step
   -> force z_progress_action regardless of lateral capture wait
   -> keep XY authority active if lateral is still outside gate
   -> reason=forced_horizon_reserved_progress_z_deadline_precedence

3. step >= capture_prepare_start_step and lateral > capture_lateral_gate_m
   -> z=0, recompute XY recenter
   -> reason=capture_wait_xy_authority

4. step < horizon_reserved_z_deadline_step
   -> z=0
   -> reason=before_horizon_reserved_z_deadline
```

The crucial invariant:

```text
If step >= 68 and env_native_success=false, post-adapter z must be -0.16 even
when lateral_error_m > capture_lateral_gate_m.
```

## Fresh Evidence Protocol

Source evidence:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_8f_horizon_reserved_capture_authority/calibration_presignal_gate_v0_8f.json
```

Fresh calibration:

```text
28000-28029
```

Fresh held-out, still sealed until calibration passes:

```text
27000-27049
```

Burned ranges:

```text
21000-21049
24000-24049
26000-26049
26500-26529
27500-27529
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
next step = artifact-only v0.8h calibration shortfall diagnosis
```

If calibration passes:

```text
open held-out 27000-27049 once
run 50 rollouts/policy
MVP-2 closes only if candidate-baseline uplift >= 0.20 and all proof gates pass
```

## Required Outputs

```text
v0_8g_deadline_precedence_horizon_authority/
  v0_8g_deadline_precedence_horizon_authority_config.json
  v0_8g_fresh_manifest.json
  candidate_policy_artifact_v0_8g.json
  baseline_policy_artifact_v0_8g.json
  calibration_runtime_manifest_v0_8g.json
  calibration_presignal_gate_v0_8g.json
  heldout_runtime_manifest_v0_8g.json            # only if calibration passes
  heldout_closure_gate_v0_8g.json                # only if held-out runs
```

Top-level `evidence_manifest.json` must record:

```text
policy_slice=v0_8g
proof_runtime=mvp2e_v08g_deadline_precedence_horizon_authority
calibration_opened=true
heldout_opened=<actual>
fresh_calibration_28000_28029_accessed=true
fresh_heldout_27000_27049_accessed=<actual>
mvp2_closed=<actual>
policy_uplift_proven=<actual>
```

## Success Criteria

`v0_8g` implementation is ready when:

```text
Evaluator tests prove deadline precedence over capture wait.
Builder tests prove fresh calibration/held-out ranges and peer fairness.
CLI tests prove calibration before held-out using fake Isaac.
Focused and static checks pass.
Actual Isaac v0_8g proof attempt runs.
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
