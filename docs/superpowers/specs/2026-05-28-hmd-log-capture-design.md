# HMD Log Capture and Gate Summary Design

## 목적

HMD physical validation 중 `/dev/pts/*` terminal 로그를 사람이 복붙하지 않아도 다음 run 이후 바로 판정할 수 있게 한다.

## 범위

MVP-safe 범위는 다음 두 가지다.

1. `scripts/run_hmd_axis_debug.sh`가 실행 전체 stdout/stderr를 `storage/logs/hmd_axis_debug/*.log`에 자동 저장한다.
2. `scripts/summarize_hmd_run_log.py`가 저장 로그, 최신 evaluation, 최신 trajectory, 최신 HMD mapping analysis를 join해 Gate A 재개 가능 여부를 요약한다.

## Non-goals

- 실제 HMD/Isaac runtime control 변경 없음.
- API endpoint 추가 없음.
- DB table 추가 없음.
- marketplace, payment, production auth 없음.

## 판정 규칙

- `AUTO_RECENTER_UNSTABLE_RIGHT_WRIST`가 로그에 있으면 Gate A collection 금지.
- `failure_reason=RAW_WRIST_JUMP`는 task 실패가 아니라 `input_quality_failure`로 분류하고 Gate A collection 금지.
- `failure_reason=TRACKING_LOSS`는 input quality failure로 분류하고 axis/gain tuning 보류.
- `H13 != PASS`이면 raw wrist valid-to-valid spike가 남아 있으므로 Gate A collection 금지.
- `right_hand_tracked_rate < 0.95` 또는 `xr_frame_valid_rate < 0.95`이면 tracking 품질 부족으로 Gate A collection 금지.

## Artifact

```text
storage/logs/hmd_axis_debug/hmd_axis_debug_<timestamp>_<mode>.log
storage/logs/hmd_axis_debug/hmd_axis_debug_<timestamp>_<mode>.log.summary.json
```

요약 schema version은 `rdf_hmd_run_log_summary_v0.1.0`이다.
