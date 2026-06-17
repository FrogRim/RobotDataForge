# MVP-2E v0.8f Horizon-Reserved Capture Authority Design

## 목적

`v0_8f`는 `v0_8d` 실제 Isaac calibration 실패와 `v0_8e` artifact-only
진단을 근거로, held-out `27000-27049`를 열기 전에 fresh calibration에서
candidate failure를 3개 이하로 낮출 수 있는지 검증하는 repair slice다.

`v0_8d` 결과:

```text
baseline_success_count=17/30
candidate_success_count=21/30
candidate_baseline_success_gap=0.133333333333
candidate_failures_total=9
candidate_failures_maximum=3
fresh_heldout_27000_27049_accessed=false
```

`v0_8e` 진단:

```text
late_z_open_depth_shortfall=5
late_seat_window_shortfall=3
off_center_no_capture=1
unclassified=0
candidate_failures_to_recover_for_calibration_gate=6
recommended_downstream_slice=v0_8f_horizon_reserved_capture_authority
```

## 핵심 가설

`v0_8d`의 지배 실패는 policy class나 success metric 문제가 아니라 두 개의
runtime authority gap이다.

1. `capture_conditioning_wait` 구간에서 XY state-feedback sign flip이 막혀
   centering이 늦어진다. 그 결과 z-open이 94-121 step까지 밀리고 150-step
   horizon 안에서 충분한 depth와 10-step env-native hold를 만들지 못한다.
2. `seat_region_depth_m=0.024`에 도달하면 env-native success가 아직 false여도
   progress authority가 멈춘다. 그 결과 first success가 140-147 step에 발생하거나
   10 consecutive window를 채우지 못한다.

따라서 `v0_8f`는 다음 두 수리만 허용한다.

```text
capture-wait XY state-feedback override:
  - z는 계속 0으로 막는다.
  - XY만 state-feedback으로 재계산한다.
  - capture wait 구간에서는 sign flip을 허용한다.

horizon-reserved seat completion:
  - env-native success가 false이면 depth>=0.024여도 z progress를 유지한다.
  - env-native success가 true이면 stable hold로 넘어가 10-step window를 쌓는다.
```

## Authority Boundary

`v0_8f`는 proof authority가 아니다. Fresh calibration gate를 통과한 뒤에만
held-out `27000-27049`를 열 수 있다.

금지:

```text
success metric 변경
env-native 10-consecutive window 완화
retry / withdraw / search / force_control
candidate-only authority
held-out 27000-27049를 calibration 통과 전 접근
calibration 26500-26529 재사용
v0_8d/v0_8e 결과를 closure claim으로 소급 적용
```

허용:

```text
v0_8e diagnosis를 source evidence로 사용
v0_8d parent policy artifacts를 복사해 v0_8f policy artifact 생성
shared baseline/candidate horizon-reserved capture authority 추가
fresh calibration 27500-27529 실행
calibration pass 시에만 held-out 27000-27049 실행
```

## Seed Firewall

Burned / opened ranges:

```text
heldout burned: 21000-21049, 24000-24049, 26000-26049
calibration burned: 26500-26529
```

`v0_8f` fresh ranges:

```text
fresh_calibration=27500-27529
fresh_heldout=27000-27049
```

`27000-27049`는 아직 sealed 상태다. `v0_8f` calibration이 fail-closed이면
held-out은 계속 unopened로 남아야 한다.

## Config

`v0_8f_horizon_reserved_capture_authority_config.json` 필수 필드:

```text
schema_version=rdf_mvp2e_v08f_horizon_reserved_capture_authority_config_v0.1.0
horizon_reserved_capture_authority_id=horizon_reserved_capture_authority_v0_8f
policy_slice=v0_8f
parent_policy_slice=v0_8d
source_policy_slice=v0_8e
source_v08e_calibration_shortfall_diagnosis_sha256
parent_v08d_capture_conditioned_progress_authority_config_sha256
capture_prepare_start_step=56
horizon_reserved_z_deadline_step=68
capture_lateral_gate_m=0.0035
capture_wait_xy_authority_enabled=true
capture_wait_xy_authority_gain=4.0
capture_wait_xy_clip_abs=0.05
capture_wait_sign_flip_allowed=true
seat_completion_until_env_native_success=true
seat_region_depth_m=0.024
z_progress_action=-0.16
fresh_calibration_seed_range=[27500,27529]
fresh_heldout_seed_range=[27000,27049]
burned_heldout_seed_ranges=[[21000,21049],[24000,24049],[26000,26049]]
burned_calibration_seed_ranges=[[26500,26529]]
candidate_specific=false
baseline_specific=false
forbidden_mechanisms=["retry","withdraw","search","force_control"]
fresh_heldout_27000_27049_accessed=false
```

## Runtime Rules

Per step, after the selected action adapter and before the final returned action:

1. If `env_native_success=true`, do not force z progress.
2. If `step >= capture_prepare_start_step` and `lateral_error_m > capture_lateral_gate_m`:
   - set `action[2]=0.0`
   - recompute `action[0:2] = -relative_xy * capture_wait_xy_authority_gain`
   - clip XY to `capture_wait_xy_clip_abs`
   - record `horizon_reserved_reason=capture_wait_xy_authority`
3. Else if `step < horizon_reserved_z_deadline_step`:
   - set `action[2]=0.0`
   - record `horizon_reserved_reason=before_horizon_reserved_z_deadline`
4. Else:
   - set `action[2]=z_progress_action`
   - record `horizon_reserved_reason=forced_horizon_reserved_progress_z`
5. If `insertion_depth_m >= seat_region_depth_m` and `env_native_success=false`, rule 4 still
   applies. The previous `already_in_seat_region` stop condition is removed for this slice.

The authority must never mutate rotation or gripper. XY mutation is allowed only for rule 2.

## Calibration Gate

Fresh calibration passes only if:

```text
runtime_backend=isaac_runtime
baseline_rollouts=30
candidate_rollouts=30
candidate_success_rate > baseline_success_rate
candidate_baseline_success_gap >= 0.10
candidate_failures_total <= 3
attribution_preservation_gate_passed=true
heldout_opened=false
fresh_heldout_27000_27049_accessed=false
```

If calibration fails, write the gate and stop before held-out.

If calibration passes, run held-out `27000-27049` once and evaluate MVP-2 closure with the
existing learning validator. The held-out result is final for this slice and must not be
tuned after inspection.

## Required Outputs

```text
v0_8f_horizon_reserved_capture_authority/
  v0_8f_horizon_reserved_capture_authority_config.json
  candidate_policy_artifact_v0_8f.json
  baseline_policy_artifact_v0_8f.json
  v0_8f_fresh_manifest.json
  calibration_runtime_manifest_v0_8f.json
  calibration_presignal_gate_v0_8f.json
  heldout_runtime_manifest_v0_8f.json       # only if calibration passes
  heldout_closure_gate_v0_8f.json           # only if held-out runs
```

Compatibility outputs:

```text
calibration_presignal_gate.json
heldout_closure_gate.json                   # only if held-out runs
evidence_manifest.json
```

## Non-Claims

Until held-out closure passes:

```text
mvp2_closed=false
policy_uplift_proven=false
real_robot_success=false
deployable_real_robot_policy=false
visual_policy_performance=false
hmd_openxr_readiness=false
```
