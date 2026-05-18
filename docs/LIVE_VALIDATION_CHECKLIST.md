# Live Validation Checklist

이 문서는 Quest 3 / ALVR / SteamVR/OpenXR / Isaac Lab / Robot Data Forge live validation을 반복 실행하기 위한 체크리스트다.

목표:

```text
실제 장비에서 RDF recorder가 success/failure/reset/incomplete episode를 저장하고,
trajectory/evaluation/HDF5 export/inspector까지 이어지는지 검증한다.
```

---

## 1. Environment Checklist

Repository root:

```bash
cd ~/robot-data-forge
```

의존성:

```bash
uv sync --group dev
```

기본 regression:

```bash
uv run pytest -q apps/api/tests
uv run python -m compileall -q apps/api/app apps/api/tests scripts
```

필수 파일:

```bash
test -x ~/run_isaac_handtracking.sh
test -f ~/IsaacLab/scripts/environments/teleoperation/teleop_se3_agent.py
test -x ~/.local/share/ALVR-Launcher/installations/v20.14.1/alvr_streamer_linux/bin/alvr_dashboard
test -x ~/.steam/debian-installation/steamapps/common/SteamVR/bin/vrmonitor.sh
test -f ~/.steam/debian-installation/steamapps/common/SteamVR/steamxr_linux64.json
```

Isaac wrapper 확인:

```bash
bash -n ~/run_isaac_handtracking.sh
```

---

## 2. Quest / ALVR / SteamVR / OpenXR Checklist

확인 항목:

```text
Quest 3 and PC are on the same network.
Quest 3 handtracking is enabled.
ALVR Quest app can find the PC streamer.
ALVR Dashboard is trusted/connected.
SteamVR sees headset and hands/controllers.
SteamVR OpenXR runtime JSON exists.
```

One-shot script는 ALVR Dashboard와 SteamVR을 자동 시작한다.

```bash
cd ~/robot-data-forge
./scripts/run_live_rdf_smoke_test.sh
```

XR stack을 수동으로 먼저 준비한 경우:

```bash
cd ~/robot-data-forge
./scripts/run_live_rdf_smoke_test.sh --no-start-xr
```

---

## 3. Isaac Launch Checklist

One-shot 기본 실행:

```bash
cd ~/robot-data-forge
./scripts/run_live_rdf_smoke_test.sh
```

짧은 실험:

```bash
cd ~/robot-data-forge
uv run python scripts/check_rdf_runtime_env.py
RDF_MAX_FRAMES=300 ./scripts/run_live_rdf_smoke_test.sh
```

초반 handtracking false frame이 많을 때:

```bash
cd ~/robot-data-forge
RDF_WARMUP_VALID_FRAMES=30 ./scripts/run_live_rdf_smoke_test.sh
```

조작이 너무 민감하거나 방향이 어색할 때:

```bash
cd ~/robot-data-forge
RDF_ACTION_POS_GAIN=0.30 RDF_ACTION_ROT_GAIN=0.20 ./scripts/run_live_rdf_smoke_test.sh
RDF_ACTION_POS_AXIS_MAP=x,-z,y ./scripts/run_live_rdf_smoke_test.sh
```

수동 API + Isaac 실행:

```bash
cd ~/robot-data-forge
./scripts/run_local_api_sqlite.sh
```

다른 terminal:

```bash
RDF_RECORD=1 RDF_MAX_FRAMES=300 ~/run_isaac_handtracking.sh
```

기대 로그:

```text
[RDF] Recording episode episode_...
[RDF] Waiting for ... consecutive valid handtracking frames...
[RDF] Terminal hotkeys active: P=recenter, N=success, F=failure, R=reset
[RDF] Recording frames started after dropping ... warm-up frames
[RDF] Submitted episode episode_...: status=...
```

---

## 4. P / N / F / R Lifecycle Command Checklist

Isaac 실행 중 다음 command를 각각 테스트한다.

| Command | 기대 동작 | 검증 포인트 |
|---|---|---|
| `P` | calibration/recenter metadata 갱신 | `summary.calibration_events` 증가 |
| `N` | current episode를 `success`로 finalize 후 새 episode 시작 | latest episode `status=success` |
| `F` | current episode를 `failure`로 finalize 후 새 episode 시작 | latest episode `status=failure` |
| `R` | current episode를 `reset`으로 finalize 후 env reset/start | latest episode `status=reset`, `reset_count` 증가 |
| Isaac close | 명시적 finalize 없이 종료 | latest episode `status=incomplete` |

`RDF_RECORD=1` 실행에서는 P/N/F/R이 terminal hotkey로도 동작한다. Isaac viewport keyboard focus가 불확실하면 실행한 terminal에 focus를 둔 뒤 소문자 `p`, `n`, `f`, `r`을 눌러도 된다.

정상 입력 로그:

```text
[RDF] Calibration/recenter requested
[RDF] Episode finalize requested: status=success reason=operator_success
```

위 로그가 없으면 command가 아직 Python process에 들어가지 않은 것이다.

`P`는 다음 두 가지를 함께 수행한다.

```text
1. recorder calibration metadata 갱신
2. RDF action filter recenter
   - smoothing state reset
   - recenter 직후 1 frame position/rotation movement suppress
```

각 command 후 확인:

```bash
curl -sS http://localhost:8000/api/episodes
curl -sS http://localhost:8000/api/admin/kpis
```

필수 lifecycle 상태:

```text
success
failure
reset
incomplete
```

---

## 5. Trajectory Field Checklist

latest trajectory를 확인한다.

```bash
curl -sS http://localhost:8000/api/episodes
```

`trajectory_id`를 얻은 뒤:

```bash
curl -sS http://localhost:8000/api/trajectories/$TRAJECTORY_ID
```

필수 top-level field:

```text
schema_version
source.input_device
source.runtime
source.simulator
source.robot
source.task_name
frames
summary
```

필수 frame field:

```text
frames[].t
frames[].step
frames[].end_effector_position
frames[].object_position
frames[].action
frames[].metadata
```

필수 RDF XR field:

```text
frames[].metadata.raw_xr
frames[].metadata.aligned_xr
frames[].metadata.retargeted
frames[].action.retargeted_robot_action
```

UX calibration / action filter 확인 field:

```text
frames[].action.raw
frames[].action.applied
frames[].action.control_filter
frames[].metadata.retargeted.raw_robot_action
frames[].metadata.retargeted.control_filter
frames[].metadata.aligned_xr.rotation_offset_quat
frames[].metadata.aligned_xr.position_gain
summary.control_filter
```

최신 recording을 한 번에 확인:

```bash
cd ~/robot-data-forge
uv run python scripts/verify_latest_rdf_recording.py --pretty
uv run python scripts/analyze_teleop_calibration.py --latest --pretty
```

Quest 착용 전 또는 live run 직후의 offline diagnostics bundle:

```bash
cd ~/robot-data-forge
uv run python scripts/run_mvp0_offline_diagnostics.py --allow-legacy
```

새 recorder patch 이후 recording만 strict하게 확인할 때:

```bash
uv run python scripts/run_mvp0_offline_diagnostics.py
```

patch 전 recording을 비교할 때는 다음처럼 legacy warning 모드로 본다.

```bash
uv run python scripts/verify_latest_rdf_recording.py --allow-legacy --pretty
```

필수 lifecycle summary:

```text
summary.episode_status
summary.episode_started_at
summary.episode_finalized_at
summary.episode_finalize_reason
summary.warmup_dropped_frames
summary.calibration_events
```

---

## 6. Evaluator Checklist

latest `evaluation_id`를 확인한다.

```bash
curl -sS http://localhost:8000/api/evaluations/$EVALUATION_ID
```

필수 field:

```text
id
trajectory_id
episode_id
task_id
evaluated_at
success
score
quality_score
failure_reason
metrics
```

Quality metric:

```text
metrics.tracking_loss_after_warmup
metrics.post_warmup_frame_count
metrics.retargeting_jump_max
metrics.retargeting_jump_mean
metrics.frame_interval_mean_ms
metrics.frame_interval_jitter_ms
```

Latency metric은 현재 runtime이 `input_latency_ms`를 제공할 때만 의미가 있다.

```text
metrics.average_input_latency_ms
metrics.max_input_latency_ms
```

실패 해석:

```text
TRACKING_LOSS:
  warm-up 이후에도 handtracking invalid frame이 많다.

RETARGETING_JUMP:
  retargeted action이 frame-to-frame으로 크게 튄다.

INPUT_LATENCY:
  input_latency_ms가 threshold를 넘는다.

FRAME_JITTER:
  timestamp 간격이 불안정하다.
```

---

## 7. HDF5 Export Checklist

Success-only export:

```bash
cd ~/robot-data-forge
uv run python scripts/export_rdf_to_hdf5.py \
  --storage-root storage \
  --output storage/exports/rdf_success_dataset.hdf5
```

Debug export:

```bash
cd ~/robot-data-forge
uv run python scripts/export_rdf_to_hdf5.py \
  --storage-root storage \
  --output storage/exports/rdf_debug_dataset.hdf5 \
  --include-failure \
  --include-reset \
  --include-incomplete
```

기대:

```text
success-only export succeeds only after at least one success lifecycle episode exists.
failure/reset/incomplete are excluded by default.
debug export includes explicitly requested non-success statuses.
```

---

## 8. Inspector Checklist

Success dataset 검사:

```bash
cd ~/robot-data-forge
uv run python scripts/inspect_rdf_hdf5.py storage/exports/rdf_success_dataset.hdf5 --pretty
```

Debug dataset 검사:

```bash
cd ~/robot-data-forge
uv run python scripts/inspect_rdf_hdf5.py storage/exports/rdf_debug_dataset.hdf5 --pretty
```

확인 항목:

```text
episode_count > 0
episode_statuses includes expected statuses
timestamp_monotonic == true
lifecycle_metadata_available == true
evaluation_metrics_available == true
retargeting_action_jump_max is not extreme
issues == []
```

`warnings`는 optional field 누락이나 NaN padding을 포함할 수 있다. `issues`는 training export 전에 원인을 확인해야 한다.

---

## 9. Failure Diagnosis Table

| 증상 | 가능 원인 | 확인 명령 | 조치 |
|---|---|---|---|
| `/health`는 200, `/api/episodes`는 500 | DB 미연결 | `curl -sS http://localhost:8000/api/episodes` | `./scripts/run_local_api_sqlite.sh`로 재시작 |
| SteamVR이 뜨지 않음 | ALVR/SteamVR path 또는 startup race | `pgrep -a vrserver` | `--no-start-xr`로 수동 시작 |
| Quest가 PC를 못 찾음 | 네트워크/방화벽/ALVR trust 문제 | ALVR Dashboard connection 상태 | 같은 Wi-Fi, trust, firewall 확인 |
| Isaac Start XR 후 종료 | SteamVR startup race 또는 Quest disconnect | `storage/logs/live_smoke_*.log` | ALVR/SteamVR 먼저 안정화 후 `--no-start-xr` |
| 새 episode 증가 없음 | recorder disabled 또는 API POST 실패 | Isaac terminal `[RDF]` 로그 | `RDF_RECORD=1`, `RDF_API_BASE` 확인 |
| P/N/F/R을 눌러도 반응 없음 | terminal/Isaac focus 또는 terminal hotkey 비활성 | `[RDF] Terminal hotkeys active` 로그 | terminal focus 후 소문자 입력, 최신 teleop script 확인 |
| episode가 계속 `running` | finalize command가 들어가지 않았거나 Isaac이 clean shutdown 전 종료 | `/api/episodes` latest status | 다음 run에서 terminal hotkey 로그 확인, 필요 시 stale episode를 incomplete로 수동 정리 |
| trajectory frames 없음 | Isaac을 너무 빨리 닫음 또는 frame extraction 실패 | latest trajectory JSON | 손 tracking 후 10초 이상 조작 |
| `TRACKING_LOSS` | 손이 HMD camera 시야 밖 | evaluation metrics | 손 위치 조정, `RDF_WARMUP_VALID_FRAMES=30` |
| raw/aligned metadata 없음 | 오래된 recorder path | trajectory frame metadata | wrapper와 recorder compile/test |
| success-only HDF5 export 실패 | success lifecycle episode 없음 | `/api/episodes?status=success` | Isaac 실행 중 `N`으로 success finalize |
| inspector `timestamp_monotonic=false` | frame timestamp 역전 | inspector output | trajectory export 전 recorder timestamp 원인 분석 |
| 조작 시점이 맞지 않음 | XR anchor / robot workspace mismatch | calibration events, operator note | P calibration, 필요 시 control-side recenter PR |

---

## 10. Run Result Recording

각 live validation 후 `docs/DATA_COLLECTION_LOG.md`에 기록한다.

필수 기록:

```text
date/time
operator
ALVR/SteamVR state
run command
episode ids
lifecycle statuses
tracking_loss_after_warmup
retargeting_jump_max
HDF5 export result
inspector issues/warnings
operator UX notes
next action
```
