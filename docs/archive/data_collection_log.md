# Data Collection Log

이 문서는 live Quest/OpenXR/Isaac collection session을 반복 기록하기 위한 템플릿이다.

새 session을 실행할 때마다 아래 템플릿을 복사해 가장 위에 추가한다.

---

## Template

```text
Session ID:
Date / Time:
Operator:
Machine:
Quest device:
ALVR version:
SteamVR version:
Isaac Sim version:
Isaac Lab path:
Robot Data Forge commit / state:

Purpose:
  [ ] MVP-0 live smoke
  [ ] lifecycle command validation
  [ ] success trajectory collection
  [ ] failure/reset/incomplete debug
  [ ] HDF5 export validation
  [ ] UX/control alignment validation

Command:

Environment variables:
  RDF_MAX_FRAMES:
  RDF_WARMUP_VALID_FRAMES:
  RDF_DISABLE_AUTO_CALIBRATE:
  RDF_ACTION_FILTER:
  RDF_ACTION_POS_GAIN:
  RDF_ACTION_ROT_GAIN:
  RDF_ACTION_POS_DEADZONE:
  RDF_ACTION_ROT_DEADZONE:
  RDF_ACTION_SMOOTHING_ALPHA:
  RDF_ACTION_POS_AXIS_MAP:
  RDF_ACTION_ROT_AXIS_MAP:
  RDF_CONTRIBUTOR_ID:
  API_BASE:

Preflight:
  [ ] uv sync completed
  [ ] backend tests passed
  [ ] compileall passed
  [ ] ALVR Dashboard launches
  [ ] SteamVR vrserver running
  [ ] Quest ALVR connected
  [ ] Isaac task starts
  [ ] handtracking visible

Lifecycle commands tested:
  [ ] P calibration/recenter
  [ ] N success finalize
  [ ] F failure finalize
  [ ] R reset finalize
  [ ] incomplete by shutdown

Generated artifacts:
  Task ID:
  Collection Session ID:
  Episode IDs:
  Trajectory IDs:
  Evaluation IDs:
  HDF5 export path:
  Inspector report path:
  Live smoke logs:

Episode summary:
  recorded episodes:
  success episodes:
  failure episodes:
  reset episodes:
  incomplete episodes:
  frame count range:
  average episode duration:

Quality metrics:
  tracking_loss_after_warmup:
  retargeting_jump_max:
  retargeting_jump_mean:
  average_input_latency_ms:
  max_input_latency_ms:
  frame_interval_jitter_ms:
  session_crash_rate:
  replayable_trajectory_rate:

Export result:
  [ ] success-only HDF5 export succeeded
  [ ] debug HDF5 export succeeded
  [ ] inspector issues empty
  [ ] inspector warnings reviewed

Operator UX notes:
  Viewpoint/control alignment:
  Hand tracking stability:
  Latency feel:
  Task difficulty:
  Any nausea/discomfort:
  Calibration/recenter usefulness:

Failure notes:
  Failure reason:
  Logs checked:
  Suspected root cause:
  Next fix:

Decision:
  [ ] proceed
  [ ] repeat run
  [ ] fix required before more collection
  [ ] no-go / pivot candidate

Next action:
```

---

## Session Entries

## 2026-05-03 Live Function Smoke

```text
Session ID:
  live_smoke_2026_05_03_terminal_hotkeys

Date / Time:
  2026-05-03 23:21 KST

Operator:
  kangrim

Machine:
  kangrim-ubuntu, RTX 4060 Ti, Ubuntu 24.04.4, NVIDIA 570.211.01

Purpose:
  [x] MVP-0 live smoke
  [x] lifecycle command validation
  [x] failure/reset/incomplete debug
  [x] UX/control alignment validation
  [ ] success trajectory collection
  [ ] HDF5 export validation

Command:
  RDF_RECORD=1 RDF_MAX_FRAMES=300 ~/run_isaac_handtracking.sh

Observed lifecycle commands:
  [x] P calibration/recenter
  [x] N success finalize
  [x] F failure finalize
  [x] R reset finalize
  [x] incomplete by shutdown

Generated episodes:
  success: 3
  failure: 2
  reset: 1
  incomplete: 1
  stale running/recording from older runs: 4

Key artifacts:
  latest incomplete episode: episode_d7eb3558ed5b
  latest trajectory: traj_d5d416fc578c
  latest evaluation: eval_4d60c7f58857
  export manifest: storage/exports/dataset_83b16c595bb2.json
  dataset card: storage/dataset_cards/dataset_83b16c595bb2.json

Quality metrics:
  task_success_rate: 0.0
  accepted_trajectory_rate: 0.0
  average_data_usability_score: 0.776
  replayable_trajectory_rate: 0.615
  sync_error_ms_mean: unavailable
  sync_error_ms_p95: unavailable
  action_segments: present, but phase UNKNOWN

Interpretation:
  기능 smoke 기준으로는 pipeline이 동작했다.
  사용자가 실제 task success를 목표로 한 run이 아니었으므로 task_success_rate=0.0은 MVP 기능 실패로 보지 않는다.
  다만 accepted dataset은 비어 있었고, 이는 실제 success trajectory가 없었기 때문이다.

Found issues:
  1. live recorder가 reset/restart마다 새 task를 생성해 task 단위 dataset export가 누적되지 않았다.
  2. incomplete episode가 frames를 가진 경우 usable=true로 표시될 수 있었다.
  3. sync_error_ms가 아직 recorder frame metadata에 없다.
  4. action_phase metadata가 없어 segment가 UNKNOWN으로만 생성된다.

Fixes applied after this session:
  1. live recorder는 같은 process 안에서 collection task를 재사용한다.
  2. POST /api/tasks는 같은 name/task_type이면 기존 task를 반환한다.
  3. evaluator는 trajectory.summary.target_position을 task config보다 우선 사용한다.
  4. incomplete episode는 INCOMPLETE_EPISODE rejection reason으로 not usable 처리한다.
  5. only_success export도 rejected episode reason metadata를 보존한다.

Decision:
  [x] proceed after fixes
  [ ] repeat run before next major PR

Next action:
  같은 명령으로 한 번 더 smoke run을 실행하고, 이번에는 여러 episode가 동일 task_id로 누적되는지 확인한다.
```

다음 real validation도 위 템플릿을 복사해 이 섹션 위에 추가한다.
