# Demo Script

이 문서는 Robot Data Forge MVP-0 demo rehearsal용 script다.

Demo 목적:

```text
Quest 3 handtracking으로 Isaac Lab teleoperation을 수행하고,
Robot Data Forge가 trajectory lifecycle, evaluation, HDF5 export까지 닫는 것을 보여준다.
```

Demo에서 보여주는 것은 robot autonomy가 아니다.

```text
This is a robot data generation pipeline demo, not a real robot control demo.
```

---

## 1. Demo Narrative

짧은 설명:

```text
Robot Data Forge turns human XR teleoperation into validated robot learning data.
The operator controls an Isaac Lab manipulation task with Quest 3 handtracking.
The system records raw XR pose, calibrated XR pose, retargeted robot action,
robot/object state, episode lifecycle, runtime quality metrics, and evaluator output.
After collection, successful episodes are exported offline into HDF5 for training.
```

한국어 설명:

```text
Robot Data Forge는 Quest 3 기반 사람 조작 데이터를 Isaac Lab에서 수집하고,
성공/실패/리셋/미완료 lifecycle과 품질 지표를 붙여 imitation learning용 dataset으로 변환하는 파이프라인이다.
```

핵심 메시지:

```text
1. VR teleoperation data is captured as structured robot learning data.
2. Raw input, calibrated input, and retargeted action are all preserved.
3. Episode lifecycle is explicit and does not depend on closing Isaac.
4. Evaluator quality gates detect tracking/runtime problems.
5. HDF5 export is offline and training-ready baseline format.
```

---

## 2. Pre-Demo Setup

Repository:

```bash
cd ~/robot-data-forge
uv sync --group dev
```

Regression:

```bash
uv run pytest -q apps/api/tests
uv run python -m compileall -q apps/api/app apps/api/tests scripts
```

XR/Isaac script check:

```bash
bash -n ~/run_isaac_handtracking.sh
bash -n scripts/run_live_rdf_smoke_test.sh
```

Optional API-only rehearsal:

```bash
./scripts/run_live_rdf_smoke_test.sh --skip-isaac
```

---

## 3. Live Demo Commands

Start one-shot live smoke:

```bash
cd ~/robot-data-forge
RDF_MAX_FRAMES=300 RDF_WARMUP_VALID_FRAMES=10 ./scripts/run_live_rdf_smoke_test.sh
```

If ALVR/SteamVR is already prepared manually:

```bash
cd ~/robot-data-forge
RDF_MAX_FRAMES=300 RDF_WARMUP_VALID_FRAMES=10 ./scripts/run_live_rdf_smoke_test.sh --no-start-xr
```

During Isaac session:

```text
P = calibration/recenter metadata
N = success finalize and start next episode
F = failure finalize and start next episode
R = reset finalize and start next episode
```

Recommended demo sequence:

```text
1. Start live smoke script.
2. Connect Quest 3 ALVR.
3. Confirm SteamVR headset/hand tracking.
4. Start Isaac scene.
5. Move hands for 3-5 seconds after warm-up.
6. Press P to record calibration metadata.
7. Perform one short manipulation attempt.
8. Press N for a clean success episode if successful.
9. Optionally press F/R in a separate short run to show lifecycle distinction.
10. Close Isaac.
11. Let script print API snapshot and KPI summary.
```

---

## 4. Expected Outputs

Console output should include:

```text
[RDF][STEP 01] Preflight
[RDF][STEP 02] API 선택
[RDF][STEP 03] 실행 전 API snapshot
[RDF][STEP ..] XR stack 시작
[RDF][READY] Quest 3에서 ALVR 앱을 열고...
[RDF] Recording episode episode_...
[RDF] Recording frames started after dropping ... warm-up frames
[RDF] Calibration updated calib_...
[RDF] Submitted episode episode_...: status=...
[RDF][KPI] recorded_episodes=...
[RDF][KPI] hand_tracking_loss_rate=...
```

Artifacts:

```text
storage/trajectories/*.json
storage/evaluations/*.json
storage/logs/live_smoke_*_episodes_*.json
storage/logs/live_smoke_*_kpis_*.json
```

API checks:

```bash
curl -sS http://localhost:8000/api/episodes
curl -sS http://localhost:8000/api/admin/kpis
```

---

## 5. What To Show

### 5.1 Live Teleoperation

Show:

```text
Quest hand movement drives Isaac camera/input.
Operator can mark lifecycle with N/F/R.
P calibration event can be triggered.
```

Do not claim:

```text
autonomous robot control
real robot deployment
production-grade VR UX
```

### 5.2 Trajectory JSON

Open latest trajectory:

```bash
ls -t storage/trajectories/*.json | head -1
```

Show fields:

```text
source
frames[0].metadata.raw_xr
frames[0].metadata.aligned_xr
frames[0].metadata.retargeted
frames[0].action.retargeted_robot_action
summary.episode_status
summary.calibration_events
```

### 5.3 Evaluation JSON

Open latest evaluation:

```bash
ls -t storage/evaluations/*.json | head -1
```

Show fields:

```text
trajectory_id
episode_id
success
quality_score
failure_reason
metrics.tracking_loss_after_warmup
metrics.retargeting_jump_max
metrics.frame_interval_jitter_ms
```

### 5.4 HDF5 Export

Success-only export:

```bash
uv run python scripts/export_rdf_to_hdf5.py \
  --storage-root storage \
  --output storage/exports/rdf_success_dataset.hdf5
```

If no success episode exists yet, explain:

```text
Default export intentionally refuses non-success data.
Use N during live collection to create success lifecycle episodes.
```

Debug export:

```bash
uv run python scripts/export_rdf_to_hdf5.py \
  --storage-root storage \
  --output storage/exports/rdf_debug_dataset.hdf5 \
  --include-failure \
  --include-reset \
  --include-incomplete
```

Inspect:

```bash
uv run python scripts/inspect_rdf_hdf5.py storage/exports/rdf_debug_dataset.hdf5 --pretty
```

Show:

```text
episode_count
episode_statuses
action_dimensions
timestamp_monotonic
evaluation_metrics_available
lifecycle_metadata_available
issues
```

---

## 6. Known Limitations

현재 demo에서 솔직히 말해야 할 제한:

```text
MVP-0 task is Franka stack cube smoke test, not final customer wedge.
Calibration is currently metadata alignment; it may not fully fix control feel.
Input latency may be unavailable if OpenXR runtime does not expose it.
Real success-only export requires at least one N-finalized success episode.
Frontend replay visualization is not the main demo path yet.
LeRobot Dataset v3 export is intentionally not implemented yet.
No real robot control is included.
No behavior cloning training is included.
```

---

## 7. Fallback Demo Path

If Quest/SteamVR fails:

```bash
cd ~/robot-data-forge
./scripts/run_live_rdf_smoke_test.sh --skip-isaac
uv run pytest -q apps/api/tests
```

Then show existing JSON/HDF5 tooling:

```bash
uv run python scripts/export_rdf_to_hdf5.py \
  --storage-root storage \
  --output storage/exports/rdf_debug_dataset.hdf5 \
  --include-failure \
  --include-reset \
  --include-incomplete

uv run python scripts/inspect_rdf_hdf5.py storage/exports/rdf_debug_dataset.hdf5 --pretty
```

Positioning:

```text
Fallback proves backend/export pipeline, not live XR capture.
Do not count fallback as MVP-0 completion.
```

---

## 8. Demo Completion Criteria

Demo is considered successful when:

```text
1. Isaac handtracking starts through Quest/OpenXR.
2. At least one episode is finalized with explicit lifecycle status.
3. Trajectory JSON contains raw/aligned/retargeted fields.
4. Evaluation JSON is created and linked by trajectory_id/episode_id.
5. HDF5 export succeeds for the available lifecycle set.
6. Inspector runs without blocking issues for the exported file.
```
