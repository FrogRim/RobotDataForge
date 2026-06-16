# MVP-2E v0.7m Z-Window Progress Authority Repair Implementation Plan

## 목표

`v0_7l` confident diagnosis를 parent로 삼아 shared z-window progress authority를
수리하고, calibration pre-signal 재실행 준비까지 닫는다.

## 단계

1. RED tests
   - evaluator runtime이 `v0_7m` policy slice에서 새 hysteresis config를
     수용하는지 검증한다.
   - z-open 중 `z_window_realign_lateral_m` 초과 시 hard-sticky가 아니라
     `ALIGN`으로 되돌아가는지 검증한다.
   - training script가 `v0_7l` parent diagnosis를 요구하고 `v0_7m` policy
     artifact/gate/manifest를 쓰는지 검증한다.
   - CLI `--offline-relabel-only --policy-slice v0_7m` 및
     `--calibration-presignal-only --policy-slice v0_7m`을 검증한다.

2. Runtime implementation
   - `V07M_POLICY_SLICE_ID`를 evaluator runtime path에 추가한다.
   - `_validated_v07e_hysteresis_authority_config`가 v0.7m config schema를
     허용하도록 확장한다.
   - `_advance_v07e_hysteresis_state`에 non-sticky
     `z_window_realign_lateral_m` soft realign rule을 추가한다.

3. Artifact implementation
   - `build_v07m_hysteresis_authority_config`
   - `build_v07m_policy_artifact_payload`
   - `derive_v07m_z_window_progress_authority_gate`
   - `build_v07m_z_window_progress_authority_repair_slice`
   - `run_v07m_calibration_presignal_runtime`

4. Verification
   - focused pytest
   - offline v0.7m artifact generation
   - actual Isaac calibration pre-signal if offline gates pass
   - compileall / ruff / diff check

## Stop Conditions

- `v0_7l` diagnosis가 confident가 아니면 v0.7m 생성 금지.
- protected held-out 접근이 감지되면 즉시 fail-closed.
- success metric 또는 held-out boundary를 바꿔야 한다면 stop.
