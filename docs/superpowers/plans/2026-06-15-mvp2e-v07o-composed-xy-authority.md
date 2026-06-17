# MVP-2E v0.7o Composed XY Authority Implementation Plan

## 목표

`v0_7n`에서 parent piecewise XY authority가 꺼진 회귀를 새 slice로 수리한다.
`v0_7o`는 parent `v0_7m`/`v0_7j` ALIGN XY behavior를 유지하면서,
z-open low-depth 구간에만 sign-flip center-maintenance override를 추가한다.

## 단계

1. RED tests
   - evaluator runtime에서 `v0_7o` policy slice와 composed XY config를 수용하는지
     검증한다.
   - off-center/non-z-open saturated action은 parent piecewise reason으로 처리되는지
     검증한다.
   - z-open low-depth sign mismatch는 `z_open_center_maintenance_state_feedback`으로
     처리되고 z는 보존되는지 검증한다.
   - training script가 failed-closed `v0_7n` calibration gate를 parent로 요구하고
     `v0_7o` artifacts/gate/manifest를 생성하는지 검증한다.

2. Runtime implementation
   - `V07O_POLICY_SLICE_ID`를 evaluator runtime path에 추가한다.
   - v0.7o final XY authority config validator를 추가한다.
   - `_apply_v07g_final_post_adapter_xy_authority`에
     `composed_piecewise_plus_z_open_center_maintenance` strategy를 추가한다.
   - non-z-open은 parent piecewise path를 그대로 사용하고, z-open low-depth만
     sign-flip override를 허용한다.

3. Artifact implementation
   - `load_required_v07o_parent_calibration_failure`
   - `build_v07o_final_xy_authority_config`
   - `build_v07o_policy_artifact_payload`
   - `derive_v07o_composed_xy_authority_gate`
   - `build_v07o_composed_xy_authority_slice`
   - `run_v07o_calibration_presignal_runtime`

4. Verification
   - focused pytest
   - offline v0.7o artifact generation
   - actual Isaac calibration pre-signal
   - 실패하면 v0.7o trace classifier/spec으로 자동 이동

## Stop Conditions

- parent v0.7n calibration gate가 failed-closed가 아니면 v0.7o 생성 금지.
- protected held-out 접근이 감지되면 즉시 fail-closed.
- success metric 또는 held-out boundary를 바꿔야 한다면 stop.
