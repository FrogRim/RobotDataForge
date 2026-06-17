# MVP-2E v0.7l Calibration Z-Window Failure Diagnosis Implementation Plan

## 목표

`v0_7k` calibration pre-signal 실패를 artifact-only로 진단하고, 다음 repair
slice를 `v0_7m_z_window_progress_authority_repair`로 제한한다.

## 구현 단계

1. RED tests
   - `classify_v07l_calibration_trace`가 z-window no-progress / lateral escape /
     seat-window failure를 분류하는지 검증한다.
   - `build_v07l_calibration_failure_diagnosis`가 `v0_7k` parent gate와 trace를
     읽고 confident diagnosis를 생성하는지 검증한다.
   - CLI `--calibration-failure-diagnosis-only --policy-slice v0_7k`가
     non-closure evidence manifest를 쓰는지 검증한다.

2. Code
   - `V07L_*` constants를 추가한다.
   - `classify_v07l_calibration_trace`와 trace path resolver를 추가한다.
   - `build_v07l_calibration_failure_diagnosis`를 추가한다.
   - 기존 `--calibration-failure-diagnosis-only` CLI에서 `v0_7g`는 기존
     v0.7i 경로, `v0_7k`는 새 v0.7l 경로로 분기한다.

3. Artifact run
   - 실제 repo artifact에서 v0.7l diagnosis를 생성한다.
   - calibration은 이미 열린 `20000-20029`만 사용하고 held-out은 열지 않는다.

4. Verification
   - focused pytest
   - v0.7l artifact-only CLI
   - compileall
   - targeted ruff
   - `git diff --check`

## Stop Condition

- Parent `v0_7k` gate가 없거나 Isaac runtime failure가 아니면 stop.
- Protected held-out `21000-21049`가 trace/gate에서 감지되면 stop.
- 진단이 confident가 아니면 repair 구현으로 넘어가지 않고 더 작은 진단 step을
  자동으로 선택한다.

## 다음 자동 분기

v0.7l이 confident이면 바로 `v0_7m_z_window_progress_authority_repair` spec과
구현으로 넘어간다. confident가 아니면 trace schema/authority mismatch 진단을
다음 valid step으로 잡는다.
