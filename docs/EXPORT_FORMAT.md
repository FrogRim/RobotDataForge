# Offline Dataset Export Format

이 문서는 live recorder가 만든 Robot Data Forge JSON/state-first trajectory를 offline training dataset으로 변환하는 규칙을 정리한다.

핵심 원칙:

```text
live recording:
  JSON/state-first trajectory만 저장

offline export:
  기존 JSON trajectory를 읽어 HDF5 training dataset 생성
```

즉, Isaac loop 안에서 HDF5, Parquet, LeRobot writer를 직접 실행하지 않는다.

---

## Export Command

기본 명령은 lifecycle `success` episode만 export한다.

```bash
cd ~/robot-data-forge
uv run python scripts/export_rdf_to_hdf5.py \
  --storage-root storage \
  --output storage/exports/rdf_success_dataset.hdf5
```

failure/reset/incomplete episode를 debug 또는 negative-example 분석용으로 포함하려면 명시적으로 flag를 켠다.

```bash
uv run python scripts/export_rdf_to_hdf5.py \
  --storage-root storage \
  --output storage/exports/rdf_debug_dataset.hdf5 \
  --include-failure \
  --include-reset \
  --include-incomplete
```

직접 directory를 지정할 수도 있다.

```bash
uv run python scripts/export_rdf_to_hdf5.py \
  --trajectories-dir storage/trajectories \
  --evaluations-dir storage/evaluations \
  --output storage/exports/rdf_dataset.hdf5
```

---

## Episode Filtering

기본 include status:

```text
success
```

추가 flag:

| Flag | 포함되는 lifecycle status | 목적 |
|---|---|---|
| `--include-failure` | `failure` | 실패 trajectory 분석, negative example 후보 |
| `--include-reset` | `reset` | operator reset 패턴 분석 |
| `--include-incomplete` | `incomplete` | Isaac shutdown/runtime issue 분석 |

`running` trajectory는 training export 대상으로 보지 않는다. 기존 trajectory에 lifecycle metadata가 없으면 다음 순서로 legacy inference를 수행한다.

```text
1. summary.episode_status
2. summary.episode_finalize_reason 또는 summary.complete_reason
3. evaluation.success
4. fallback: incomplete
```

이 inference는 backward compatibility 목적이다. 신규 recording은 `summary.episode_status`를 저장해야 한다.

---

## HDF5 Structure

Top-level group:

```text
/episodes
/observations
/states
/actions
/timestamps
/metadata
/evaluation
```

Episode별 subgroup:

```text
/episodes/<episode_id>
/observations/<episode_id>
/states/<episode_id>
/actions/<episode_id>
/timestamps/<episode_id>
/metadata/<episode_id>
/evaluation/<episode_id>
```

Dataset-level metadata:

```text
/metadata/dataset_json
```

---

## Field Mapping

| HDF5 path | RDF source |
|---|---|
| `/episodes/episode_ids` | sorted exported episode ids |
| `/episodes/trajectory_ids` | sorted exported trajectory ids |
| `/observations/<episode_id>/end_effector_position` | `frame.end_effector_position` |
| `/observations/<episode_id>/end_effector_quaternion` | `frame.end_effector_quaternion` |
| `/observations/<episode_id>/object_position` | `frame.object_position` |
| `/observations/<episode_id>/object_quaternion` | `frame.object_quaternion` |
| `/observations/<episode_id>/raw_xr_right_wrist_pose` | `frame.metadata.raw_xr.right_wrist_pose` |
| `/observations/<episode_id>/aligned_xr_right_wrist_pose` | `frame.metadata.aligned_xr.right_wrist_pose` |
| `/observations/<episode_id>/metadata_json` | full `frame.metadata` per frame |
| `/states/<episode_id>/robot_end_effector_position` | `frame.end_effector_position` |
| `/states/<episode_id>/object_position` | `frame.object_position` |
| `/states/<episode_id>/cube_states_json` | `frame.metadata.cube_states` |
| `/actions/<episode_id>/raw_action` | `frame.action.raw` or compatible legacy action dict |
| `/actions/<episode_id>/teleop_intent` | `frame.action.teleop_intent.command` or fallback `frame.action.raw` |
| `/actions/<episode_id>/executed_control` | `frame.action.executed_control.command` or fallback `frame.action.retargeted_robot_action.command` |
| `/actions/<episode_id>/learning_action` | `frame.action.learning_action.command` or fallback `frame.action.retargeted_robot_action.command` |
| `/actions/<episode_id>/retargeted_robot_action` | `frame.action.retargeted_robot_action.command` or `frame.metadata.retargeted.robot_action` |
| `/actions/<episode_id>/action_json` | full `frame.action` per frame |
| `/timestamps/<episode_id>/t` | `frame.t` |
| `/timestamps/<episode_id>/step` | `frame.step` |
| `/metadata/<episode_id>/source_json` | `trajectory.source` |
| `/metadata/<episode_id>/summary_json` | `trajectory.summary` |
| `/metadata/<episode_id>/lifecycle_json` | normalized lifecycle metadata |
| `/evaluation/<episode_id>/evaluation_json` | matched evaluation JSON if available |
| `/evaluation/<episode_id>/metrics_json` | `evaluation.metrics` if available |

Numeric arrays use fixed 2D matrices. Missing optional vectors become empty-width arrays or `NaN` padding when widths vary. Full JSON fields are preserved for debugging and future migration.

For trajectories recorded with the teleop action filter, `/actions/<episode_id>/teleop_intent` stores the operator/XR retargeter intent, `/actions/<episode_id>/executed_control` stores the command applied to the Isaac robot controller, and `/actions/<episode_id>/learning_action` stores the candidate action used by downstream training exports after validation and curation. The legacy `/actions/<episode_id>/retargeted_robot_action` remains as a compatibility alias for the applied command. The original OpenXR retargeter command remains available in JSON fields such as `frame.action.raw` and `/actions/<episode_id>/action_json`.

---

## Validation Rules

Exporter는 다음 조건을 검증한다.

```text
trajectory.schema_version exists
trajectory.source has input_device/runtime/simulator/robot/task_name
trajectory.frames is a list
each frame has numeric t and step
success episode has at least one frame
episode_id and trajectory_id are safe HDF5 group names
```

실패하면 export를 중단하고 clear error를 출력한다.

---

## Evaluation Matching

Evaluation JSON은 다음 key로 trajectory에 연결한다.

```text
1. evaluation.trajectory_id
2. evaluation.episode_id
```

신규 evaluation JSON은 아래 metadata를 포함한다.

```json
{
  "id": "eval_001",
  "trajectory_id": "traj_001",
  "episode_id": "episode_001",
  "task_id": "task_001",
  "evaluated_at": "2026-05-01T00:00:00Z"
}
```

초기 legacy recording 중 일부는 evaluation JSON에 link field가 없다. trajectory가 정확히 1개이고 evaluation도 1개인 경우에만 단일 파일 fallback으로 연결한다. 여러 trajectory가 있으면 unlinked evaluation은 특정 episode에 붙이지 않는다.

HDF5에는 pairing 결과를 남긴다.

```text
/episodes/<episode_id>.attrs["evaluation_pairing_source"]
/evaluation/<episode_id>.attrs["evaluation_pairing_source"]
```

가능한 값:

```text
trajectory_id
episode_id
single_unlinked_legacy
missing
```

Evaluation metrics는 optional이다. Metrics가 없어도 export는 실패하지 않고 `dataset_json.warnings`에 warning을 남긴다.

---

## Sanity Checker

HDF5 export 후 구조와 품질 metadata를 빠르게 확인한다.

```bash
uv run python scripts/inspect_rdf_hdf5.py storage/exports/rdf_success_dataset.hdf5 --pretty
```

보고 항목:

```text
number of exported episodes
episode statuses
available observation/state/action fields
action dimensions
timestamp count
timestamp monotonicity
missing fields
NaN / Inf values
evaluation metric availability
lifecycle metadata availability
retargeting action jump max
average frame interval
frame interval jitter
tracking loss metric availability
```

`issues`가 비어 있지 않으면 training export로 사용하기 전에 원인을 확인한다. `warnings`는 optional metadata 누락이나 NaN/Inf reporting처럼 export 자체를 막지는 않는 문제다.

---

## LeRobot Compatibility Status

이번 PR에서는 LeRobot directory export를 구현하지 않는다.

확인한 최신 LeRobot Dataset v3 expectation:

```text
meta/info.json
meta/stats.json
meta/tasks 또는 tasks.parquet
meta/episodes/... parquet
data/... parquet
videos/... mp4 optional
dataset.finalize() 필요
```

Robot Data Forge의 현재 state-only JSON trajectory를 바로 LeRobot v3로 쓰려면 feature schema, Parquet writer, stats generation, task metadata, episode offsets, finalize flow를 모두 맞춰야 한다. 이 작업은 추측 구현 위험이 있으므로 HDF5 baseline 이후 별도 PR로 진행한다.

참고:

- https://huggingface.co/docs/lerobot/lerobot-dataset-v3
- https://huggingface.co/docs/lerobot/porting_datasets_v3

---

## LeRobot Mapping Follow-up

초기 mapping 후보:

| LeRobot key | RDF source |
|---|---|
| `observation.state` | concatenated `end_effector_position`, `object_position`, optional gripper state |
| `action` | `retargeted_robot_action` |
| `timestamp` | `frame.t` |
| `episode_index` | exported episode ordinal |
| `frame_index` | `frame.step` |
| `task_index` | task metadata table |
| `next.done` 또는 terminal marker | lifecycle final frame |
| custom metadata | lifecycle/evaluation/runtime JSON |

Follow-up에서는 LeRobot package version을 고정하고, official writer API로 dataset 생성과 `finalize()`까지 검증해야 한다.

---

## API Export Readiness Contract

`POST /api/datasets/export`의 format 처리:

| format | 현재 동작 | 용도 |
|---|---|---|
| `json` | 실제 JSON dataset export | MVP live API export |
| `hdf5` | JSON placeholder manifest | offline HDF5 export와 연결될 future API slot |
| `lerobot_v3` | JSON placeholder manifest + LeRobot metadata row | LeRobot-compatible schema readiness |

Placeholder manifest는 실제 HDF5 또는 LeRobot dataset이 아니다.

```json
{
  "export_format": "lerobot_v3",
  "export_status": "placeholder",
  "episodes": [],
  "placeholder": {
    "requested_format": "lerobot_v3",
    "actual_file_type": "json_manifest",
    "reason": "Live API export is metadata-ready only. Use offline HDF5 exporter for training datasets."
  }
}
```

지원하지 않는 format 예:

```bash
curl -sS -X POST http://localhost:8000/api/datasets/export \
  -H 'Content-Type: application/json' \
  -d '{"task_id":"task_001","name":"bad","export_format":"parquet"}'
```

예상 응답:

```json
{"detail":"Unsupported export_format: parquet"}
```

## Dataset Card Metadata

Dataset export는 별도 dataset card JSON을 생성한다.

```text
storage/dataset_cards/<dataset_id>.json
```

포함 항목:

```text
dataset_name
task_description
task_type
robot
simulator
input_device
runtime
num_episodes
num_accepted
num_rejected
success_criteria
evaluator_version
curation_rules
train/validation/test split
limitations
```
