# API 명세

구현된 API route는 `apps/api/app/main.py`에서 노출되며, FastAPI OpenAPI 문서는 `/openapi.json`에서 확인할 수 있다.

## Health

```http
GET /health
```

## Task API

```http
POST /api/tasks
GET /api/tasks
GET /api/tasks/{task_id}
```

예시:

```bash
curl -sS -X POST http://localhost:8000/api/tasks \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "Peg-in-Hole",
    "description": "Move the peg into the target hole.",
    "task_type": "peg_in_hole",
    "environment_config": {
      "target_position": [0.75, 0.5],
      "success_tolerance": 0.03
    },
    "success_criteria": {
      "distance_to_target_max": 0.03,
      "min_stable_steps": 2,
      "max_completion_time_sec": 30
    }
  }'
```

## Collection Session API

```http
POST /api/collection-sessions/start
POST /api/collection-sessions/{session_id}/complete
GET /api/collection-sessions/{session_id}
```

Session runtime metadata는 명세 #26을 따른다.

Live IsaacLab recorder는 frame metadata와 session runtime metrics에 reset-boundary evidence를 저장할 수 있다.

```json
{
  "frames": [
    {
      "metadata": {
        "sim_step_boundary": {
          "schema_version": "rdf_sim_step_boundary_v0.1.0",
          "source": "isaac_env_step_return",
          "env_step_return_available": true,
          "terminated": {"available": true, "any": true, "true_count": 1, "count": 1},
          "truncated": {"available": true, "any": false, "true_count": 0, "count": 1},
          "done": {"available": true, "any": true, "true_count": 1, "count": 1},
          "reset_boundary": true,
          "reset_boundary_reason": "terminated",
          "info_keys": ["final_observation"]
        }
      }
    }
  ],
  "summary": {
    "sim_reset_boundary_frame_count": 1,
    "sim_reset_boundary_frames": [172]
  }
}
```

`sim_step_boundary`는 `env.step()` 반환값의 boundary signal만 기록한다. Raw trajectory는 그대로 보존하고, split/reject 판단은 evaluator/curator gate가 담당한다.

Raw-wrist direct control mode에서는 trajectory artifact에 valid-to-valid spike debounce/reacquire metadata가 포함될 수 있다.
API endpoint shape는 바뀌지 않지만, frame action payload의 `raw_wrist_direct`에는 다음 key가 추가된다.

```json
{
  "action": {
    "raw_wrist_direct": {
      "gate_state": "held",
      "gate_reason": "raw_wrist_spike_reacquire_pending",
      "valid_to_valid_jump_m": 0.28,
      "raw_wrist_reacquire_valid_count": 1,
      "raw_wrist_reacquire_required_frames": 3,
      "raw_wrist_reacquire_stable_m": 0.03
    }
  }
}
```

## Episode API

```http
POST /api/episodes/start
POST /api/episodes/{episode_id}/complete
POST /api/episodes/{episode_id}/finalize
GET /api/episodes/{episode_id}
GET /api/episodes
```

`start` 응답의 `status`는 신규 lifecycle 기준으로 `running`이다. 기존 `recording` status는 legacy row를 읽기 위해서만 유지한다.

Episode lifecycle status:

```text
running
success
failure
reset
incomplete
```

`complete`는 backward-compatible alias이고, 신규 runtime recorder는 `finalize`를 사용한다. 요청에는 `trajectory.schema_version`과 전체 source block이 필요하다.

```json
{
  "source": {
    "input_device": "quest3_handtracking",
    "runtime": "steamvr_openxr",
    "simulator": "isaac_lab",
    "robot": "franka",
    "task_name": "Isaac-Stack-Cube-Franka-IK-Rel-v0"
  }
}
```

Finalize request의 optional lifecycle field:

```json
{
  "episode_status": "success",
  "episode_finalize_reason": "operator_success",
  "episode_failure_reason": null,
  "episode_failure_note": null,
  "reset_count": 0
}
```

규칙:

- `episode_status`가 있으면 evaluator 결과와 별개로 `Episode.status`에 저장한다.
- `episode_status`가 없으면 legacy request로 보고 evaluator result 또는 `summary.complete_reason`에서 `success`, `failure`, `reset`, `incomplete`를 추론한다.
- `success` status는 operator lifecycle 상태이고, response의 `success`는 evaluator success다. 두 값은 의도적으로 분리되어 있다.
- Isaac shutdown 또는 runtime error로 finalize되면 `incomplete`로 저장한다.
- Reset episode는 `reset`으로 저장되어 `success`/`failure`와 구분된다.

## Evaluation API

```http
POST /api/evaluations
GET /api/evaluations/{evaluation_id}
```

`Evaluation.metrics`에는 task outcome metric과 XR/runtime quality metric이 함께 저장될 수 있다. Runtime quality gate는 request/response schema를 바꾸지 않고 `metrics` JSON에 아래 optional key를 추가한다.

```text
tracking_loss_after_warmup
retargeting_jump_max
raw_wrist_valid_to_valid_jump
scene_state_discontinuity
average_input_latency_ms
max_input_latency_ms
frame_interval_jitter_ms
```

MVP-1 evaluation semantics는 top-level `success`와 별도로 아래 구조를 `metrics`에 포함할 수 있다. Top-level `success`는 backward compatibility를 위해 기존 validated evaluator success 의미를 유지한다.

```json
{
  "failure_category": "DATA_QUALITY_FAILURE",
  "task_outcome": {
    "operator_success": true,
    "auto_success_ready": false,
    "success_label_source": "operator",
    "evaluator_task_success": "unknown",
    "task_success_confidence": null,
    "task_failure_reason": null
  },
  "data_quality": {
    "replay_verified": false,
    "action_contract_valid": true,
    "retargeting_jump": "fail",
    "raw_wrist_valid_to_valid_jump": "pass",
    "sync_quality": "pass",
    "control_quality": "fail",
    "quality_failure_reasons": ["RETARGETING_JUMP"]
  },
  "curation": {
    "raw_saved": true,
    "human_success_pool": true,
    "task_success_candidate_pool": true,
    "training_eligible": false,
    "curated_accepted": false,
    "proof_eligible": false,
    "rejection_reasons": ["REPLAY_NOT_VERIFIED", "RETARGETING_JUMP"]
  }
}
```

`evaluator_task_success`는 `true` / `false` / `"unknown"` tri-state다. `RETARGETING_JUMP`는 task failure가 아니라 `DATA_QUALITY_FAILURE`로 분류한다.
`RAW_WRIST_JUMP`도 `DATA_QUALITY_FAILURE`다. `raw_wrist_direct_ee_target` mode에서 valid-to-valid right-wrist jump가 `max_raw_wrist_valid_to_valid_jump_m` 기본값 `0.10m`를 넘으면 task 성공 여부와 분리해 `training_eligible=false`로 둔다.
`SCENE_STATE_DISCONTINUITY`도 `DATA_QUALITY_FAILURE`다. Peg-in-hole evaluator에서 static task target(`hole_position`, `hole_target_position`)이 한 trajectory 안에서 순간 이동하면 controller target 누적 문제가 아니라 hidden reset/teleport 또는 recorder boundary 누락으로 보고 `training_eligible=false`가 된다.

HMD task guidance가 `SUCCESS_READY` hold를 만족해 자동 finalize한 episode는 `episode_finalize_reason=auto_success_ready`, `success_label_source=task_state_auto`, `auto_success_ready=true`를 summary에 저장할 수 있다. 이 label은 human success가 아니므로 `human_success_pool=false`가 될 수 있지만, `task_success_candidate_pool=true`로 남는다. 자동 success도 replay/action/data-quality gate를 우회하지 않는다.

아래 failure reason이 추가로 반환될 수 있다.

```text
RETARGETING_JUMP
RAW_WRIST_JUMP
SCENE_STATE_DISCONTINUITY
INPUT_LATENCY
FRAME_JITTER
ALIGNMENT_ERROR
INSUFFICIENT_INSERTION_DEPTH
```

`task_type=peg_in_hole` 계열 task에서 trajectory frame에 `metadata.task_state`가 있으면 evaluator는 MVP-1 insertion metric을 사용한다.

지원되는 최소 `task_state`:

```json
{
  "peg_tip_distance_to_target": 0.008,
  "axis_alignment_error_rad": 0.08,
  "insertion_depth": 0.032,
  "contact_sequence_valid": true,
  "object_drop_detected": false
}
```

이 경우 evaluation `metrics`에는 `peg_tip_distance_to_target`, `axis_alignment_error_rad`, `insertion_depth`, `stable_final_steps`, `contact_sequence_valid`가 포함된다.

## Dataset API

```http
POST /api/datasets/export
GET /api/datasets
GET /api/datasets/{dataset_id}/download
GET /api/datasets/{dataset_id}/card
```

MVP live API에서는 `json` export만 실제 dataset 파일로 구현되어 있다. `hdf5`, `lerobot_v3`는 export readiness 확인용 placeholder manifest를 생성한다. 실제 training용 HDF5는 offline exporter를 사용한다.

Export 안전성 및 필터링 규칙:

- `name`은 dataset 표시 이름으로만 사용한다.
- Export 파일명은 서버가 생성한 `dataset_id`를 사용한다.
- `storage/exports/{dataset_id}.json`만 허용되는 export 위치다.
- `only_success=true`는 `ForgeCurate`를 적용하고 accepted successful trajectory만 export한다.
- `only_success=false`는 error analysis를 위해 성공 episode와 실패 episode를 모두 export한다.
- `num_episodes`, `num_success`, `num_failed`는 실제 export된 episode set을 기준으로 계산한다.
- `hdf5`, `lerobot_v3` 요청은 `status=placeholder`와 JSON manifest를 반환한다.
- 지원하지 않는 format은 `422 Unsupported export_format`으로 거부한다.
- Dataset card는 `metadata_json.dataset_card`와 `/api/datasets/{dataset_id}/card`에서 조회한다.

## Quality Metadata API

```http
GET /api/episodes/{episode_id}/sync-metrics
GET /api/episodes/{episode_id}/usability
GET /api/trajectories/{trajectory_id}/segments
```

이 endpoint들은 recorder 원본을 바꾸지 않고 episode finalize 후 계산된 파생 품질 metadata를 반환한다.

```text
sync-metrics:
  timestamp monotonicity, frame interval, handtracking loss, latency, optional sync_error_ms

usability:
  usable/not usable, data_usability_score, rejection reasons, component scores

segments:
  phase, start_frame, end_frame, confidence, source
```

지원 phase:

```text
APPROACH
ALIGN
CONTACT
INSERT
SEAT
STABILIZE
RELEASE
RECOVER
UNKNOWN
```

## Human Review API

```http
POST /api/human-reviews
```

## Learning Experiment API

```http
POST /api/learning-experiments
```

## Admin KPI API

```http
GET /api/admin/kpis
```

명세 #24의 KPI group을 반환한다.

```text
collection
xr_runtime
evaluation
learning
curation
data_usability
```

Live validation 중 과거 stale row를 제외하려면 query filter를 사용한다.

```http
GET /api/admin/kpis?task_id=task_001
GET /api/admin/kpis?started_after=2026-05-03T14:48:00Z
GET /api/admin/kpis?task_id=task_001&started_after=2026-05-03T14:48:00Z
```

`GET /api/episodes`도 동일하게 `task_id`, `status`, `collection_session_id`, `started_after` filter를 지원한다.

## Local Recorder 제출 흐름

Local recorder 경계는 다음 명령으로 확인한다.

```bash
uv run python scripts/record_isaac_episode.py --api-base http://localhost:8000 --mock-submit
```

`--mock-submit`은 fallback/debug 전용이다. Primary adapter는 계속 `IsaacLabAdapter`다.

실제 Isaac Lab teleoperation process 안에서 frame을 수집하려면 backend API를 먼저 실행한 뒤 recorder를 켜서 Isaac handtracking launcher를 실행한다.

```bash
cd ~/robot-data-forge
./scripts/run_local_api_sqlite.sh
```

다른 terminal에서:

```bash
RDF_RECORD=1 ~/run_isaac_handtracking.sh
```

선택 환경 변수:

```bash
RDF_API_BASE=http://localhost:8000
RDF_CONTRIBUTOR_ID=user_001
RDF_MAX_FRAMES=0
RDF_WARMUP_VALID_FRAMES=10
RDF_DISABLE_AUTO_CALIBRATE=0
RDF_ACTION_FILTER=1
RDF_ACTION_POS_GAIN=0.45
RDF_ACTION_ROT_GAIN=0.35
RDF_ACTION_POS_AXIS_MAP=x,z,y
```

`RDF_RECORD=1`은 `teleop_se3_agent.py`에 `--rdf_record`를 전달한다. 이 hook은 Isaac loop 안에서 `ee_frame`, `cube_1`, `cube_2`, `cube_3`, teleop action, OpenXR device cache metadata를 frame 단위로 수집하고 `/api/episodes/{episode_id}/complete`로 제출한다.

Recorder가 제출하는 trajectory frame은 기존 field를 유지하면서 `action.teleop_intent`, `action.executed_control`, `action.learning_action`, `action.retargeted_robot_action`, `action.control_filter`, `metadata.teleop_pipeline`, `metadata.raw_xr`, `metadata.aligned_xr`, `metadata.retargeted`, `metadata.calibration`을 optional field로 포함할 수 있다. `RDF_ACTION_FILTER=1`이면 `action.teleop_intent.command`에는 원본 OpenXR retargeted operator intent, `action.executed_control.command`에는 실제 Isaac controller에 적용된 command, `action.learning_action.command`에는 export/training 후보 action이 저장된다. `learning_action`은 evaluator/curator를 통과하기 전까지 learning-ready라는 뜻이 아니다. 기존 `action.raw`, `action.applied`, `retargeted_robot_action.command`는 호환을 위해 유지된다. API contract는 additive하게 확장된다.

## 테스트 명령

Repository root에서 `uv`를 사용한다.

```bash
uv sync --group dev
uv run pytest -q apps/api/tests
uv run python -m compileall -q apps/api/app apps/api/tests scripts
uv run python - <<'PY'
from app.main import app
schema = app.openapi()
print(schema["info"]["title"])
print(len(schema["paths"]))
PY
```
