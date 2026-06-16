# MVP-2E v0.7n Z-Open XY Center-Maintenance Implementation Plan

## 목표

`v0_7m` 실제 Isaac calibration 실패에서 확인된 z-open 중 XY sign mismatch 방치를
좁게 수리하고, calibration pre-signal을 다시 실행할 수 있게 한다.

## 단계

1. RED tests
   - evaluator runtime에서 `v0_7n` policy slice와 XY config를 수용하는지 검증한다.
   - z-open + low-depth + sign mismatch에서 final XY authority가 state-feedback
     centering으로 덮어쓰고 z는 보존하는지 검증한다.
   - training script가 failed-closed `v0_7m` calibration gate를 parent로 요구하고
     `v0_7n` artifacts/gate/manifest를 생성하는지 검증한다.
   - CLI `--offline-relabel-only --policy-slice v0_7n` 및
     `--calibration-presignal-only --policy-slice v0_7n`을 검증한다.

2. Runtime implementation
   - `V07N_POLICY_SLICE_ID`를 evaluator runtime path에 추가한다.
   - v0.7n final XY authority config validator를 추가한다.
   - `_apply_v07g_final_post_adapter_xy_authority`에 z-open low-depth centering
     override를 추가한다.

3. Artifact implementation
   - `load_required_v07n_parent_calibration_failure`
   - `build_v07n_final_xy_authority_config`
   - `build_v07n_policy_artifact_payload`
   - `derive_v07n_z_open_xy_centering_gate`
   - `build_v07n_z_open_xy_center_maintenance_slice`
   - `run_v07n_calibration_presignal_runtime`

4. Verification
   - focused pytest
   - offline v0.7n artifact generation
   - actual Isaac calibration pre-signal
   - compileall / ruff / diff check as budget allows

## Stop Conditions

- parent v0.7m calibration gate가 failed-closed가 아니면 v0.7n 생성 금지.
- protected held-out 접근이 감지되면 즉시 fail-closed.
- success metric 또는 held-out boundary를 바꿔야 한다면 stop.
