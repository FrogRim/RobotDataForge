# MVP-1 Task Spec Draft

이 문서는 MVP-1에서 사용할 customer/investor proof task의 초안이다.

MVP-1의 목적은 단순히 trajectory를 저장하는 것이 아니라, XR/HMD teleoperation raw trajectory를 검증 가능하고 큐레이션된 learning-ready dataset artifact로 승격하는 pipeline을 보이는 것이다. Curated dataset이 downstream policy 성능을 올린다는 learning-proven 주장은 MVP-2에서 별도로 검증한다.

---

## 1. Preferred Task

우선순위:

```text
Primary:
  peg-in-hole

Alternative:
  connector insertion
```

선호 이유:

```text
assembly/insertion 계열 task는 산업용 manipulation customer pain과 연결하기 쉽다.
단순 pick-and-place보다 데이터 가치가 높다.
success/failure criteria를 geometric/contact 조건으로 정의할 수 있다.
Quest handtracking teleoperation의 정밀 조작 문제를 드러낸다.
```

MVP-0와의 차이:

```text
MVP-0:
  Isaac-Stack-Cube-Franka-IK-Rel-v0
  engineering smoke test

MVP-1:
  peg-in-hole or connector insertion
  customer/investor value proof
```

---

## 2. Task Definition: Peg-in-Hole

목표:

```text
Operator uses Quest 3 handtracking teleoperation to guide a robot end-effector
that grasps or controls a peg and inserts it into a matching hole.
```

초기 단순화:

```text
single peg
single fixed hole
rigid objects
single-arm Franka
state-first observations
no camera requirement for first implementation
```

후속 확장:

```text
randomized peg initial pose
randomized hole pose within small workspace
friction/contact variation
visual observation
connector-shaped geometry
```

---

## 3. Alternative Task: Connector Insertion

목표:

```text
Operator inserts a connector-like object into a port-like receptacle.
```

장점:

```text
industrial relevance is stronger than generic peg-in-hole.
customer can understand cable/connector/assembly analogy quickly.
```

위험:

```text
geometry/contact modeling is harder.
success criteria may need orientation and contact sequence checks.
operator UX may be more sensitive to calibration and latency.
```

결론:

```text
Use peg-in-hole first unless a design partner provides a specific connector task.
```

---

## 4. Success Criteria

Peg-in-hole success는 최소 아래 조건을 만족해야 한다.

```text
peg_tip_distance_to_hole_bottom < threshold
peg_axis_alignment_error < threshold
insertion_depth > threshold
final_state_stable_for_n_steps >= threshold
object_not_dropped == true
excessive_collision == false
timeout == false
```

초기 threshold 후보:

```json
{
  "peg_tip_distance_to_target_max": 0.015,
  "peg_axis_alignment_error_max_rad": 0.25,
  "insertion_depth_min": 0.025,
  "min_stable_steps": 10,
  "max_completion_time_sec": 45,
  "max_tracking_loss_after_warmup": 0.2,
  "max_retargeting_jump": 0.25,
  "max_frame_interval_jitter_ms": 50
}
```

주의:

```text
Threshold는 실제 Isaac task geometry와 unit scale을 확인한 뒤 조정해야 한다.
위 값은 implementation starting point일 뿐 final criteria가 아니다.
```

---

## 4.1 BEHAVIOR-style Task Spec

MVP-1 task spec은 최종 success flag만 정의하지 않는다. BEHAVIOR식으로 goal, progress, efficiency를 분리해서 기록한다.

Task goal:

```text
Insert the peg into the fixed hole with sufficient lateral centering,
axis alignment, insertion depth, and final stability.
```

Progress signals:

```text
phase = APPROACH | ALIGN | CONTACT | INSERT | SEAT | RELEASE
lateral_distance_to_hole_axis
axis_alignment_error_rad
insertion_depth
contact_state
stable_final_steps
```

Efficiency signals:

```text
completion_time_sec
path_length_end_effector
action_saturation_ratio
retargeting_jump_max
tracking_loss_rate_after_warmup
unnecessary_contact_or_collision_count
```

Training eligibility는 goal success만으로 결정하지 않는다. Goal/progress/efficiency와 replay/action contract, data quality, transition coverage가 함께 curation manifest에 기록되어야 한다.

---

## 5. Failure Criteria

명확한 failure reason 후보:

```text
TIMEOUT
TARGET_MISSED
ALIGNMENT_ERROR
INSUFFICIENT_INSERTION_DEPTH
UNSTABLE_FINAL_STATE
OBJECT_DROPPED
EXCESSIVE_COLLISION
BAD_CONTACT_SEQUENCE
GRIPPER_FAILURE
TRACKING_LOSS
RETARGETING_JUMP
INPUT_LATENCY
FRAME_JITTER
SIM_RUNTIME_ERROR
```

기존 taxonomy와 겹치는 항목은 그대로 사용하고, task-specific 항목만 추가한다.

추가 후보:

```text
ALIGNMENT_ERROR
INSUFFICIENT_INSERTION_DEPTH
```

---

## 6. Required Observations

State-first MVP-1 최소 observation:

```text
robot_end_effector_position
robot_end_effector_quaternion
gripper_state
peg_position
peg_quaternion
hole_position
hole_quaternion
peg_tip_position
peg_axis_vector
insertion_depth
contact_count
timestamp
raw_xr_right_wrist_pose
aligned_xr_right_wrist_pose
tracking_valid
```

Optional later observation:

```text
camera_rgb_reference_path
camera_depth_reference_path
wrist_camera_reference_path
contact_force
force_torque_proxy
```

중요:

```text
Do not store image frames directly inside trajectory JSON.
If images are added later, store external references or export them in a separate dataset layout.
```

---

## 7. Required Actions

현재 RDF action schema와 호환되는 최소 action:

```text
retargeted_robot_action
relative.delta_position
relative.delta_rotation
relative.gripper
teleoperation_active
pinch_or_gripper
```

MVP-1에서 추가로 유용한 action metadata:

```text
action_space_type = delta_ee_pose_plus_gripper
control_mode = relative
position_gain
rotation_gain
precision_mode_enabled
calibration_id
```

주의:

```text
Action schema는 기존 trajectory reader를 깨지 않도록 optional nested field로 확장한다.
```

---

## 8. Evaluator Metrics

Task outcome metric:

```text
peg_tip_distance_to_target
axis_alignment_error_rad
insertion_depth
stable_final_steps
completion_time_sec
collision_count
contact_sequence_valid
object_drop_detected
```

Runtime quality metric:

```text
tracking_loss_after_warmup
retargeting_jump_max
average_input_latency_ms
max_input_latency_ms
frame_interval_jitter_ms
calibration_event_count
calibration_valid
```

MVP-2 learning value metric:

```text
curated_vs_uncurated_success_rate
policy_success_rate
baseline_success_rate
success_rate_uplift
average_completion_time
collision_count_mean
failure_mode_distribution
```

주의:

```text
위 learning value metric은 MVP-2 proof에 속한다.
MVP-1 task spec은 이 metric을 기록/연결할 수 있는 dataset artifact를 만드는 것이 목표다.
```

---

## 9. Dataset Schema Implications

기존 schema에 그대로 맞는 항목:

```text
source
frames[].t
frames[].step
frames[].end_effector_position
frames[].end_effector_quaternion
frames[].action.retargeted_robot_action
frames[].metadata.raw_xr
frames[].metadata.aligned_xr
summary.episode_status
evaluation.metrics
```

추가가 필요한 task-specific state:

```text
frames[].metadata.task_state.peg_position
frames[].metadata.task_state.peg_quaternion
frames[].metadata.task_state.hole_position
frames[].metadata.task_state.hole_quaternion
frames[].metadata.task_state.peg_tip_position
frames[].metadata.task_state.insertion_depth
frames[].metadata.task_state.axis_alignment_error_rad
frames[].metadata.task_state.contact_count
```

HDF5 exporter follow-up:

```text
/states/<episode_id>/task_state_json
/observations/<episode_id>/peg_position
/observations/<episode_id>/hole_position
/observations/<episode_id>/peg_tip_position
/evaluation/<episode_id>/metrics_json
```

Schema 원칙:

```text
Keep live JSON/state-first.
Add task-specific fields under metadata.task_state.
Do not redesign base trajectory format for MVP-1.
```

---

## 10. Implementation Risks

| Risk | 설명 | 대응 |
|---|---|---|
| task geometry setup | peg/hole assets and contact properties may take time | start with simple primitive peg/hole |
| success threshold ambiguity | insertion depth/alignment threshold may be wrong | log raw metrics first, tune after 20 runs |
| handtracking precision | Quest handtracking may be too noisy for insertion | add precision mode/recenter before large collection |
| contact instability | simulation contact may bounce or penetrate | tune PhysX/contact material conservatively |
| evaluator false positives | shallow insertion may be marked success | require depth + alignment + stable steps |
| dataset value unproven | curated data may not improve policy | keep MVP-1 experiment small and explicit |

---

## 11. Minimal Integration Plan

Step 1: Spec freeze

```text
Choose peg-in-hole unless a customer/design partner provides connector insertion details.
Freeze task geometry and success criteria.
```

Step 2: Isaac task setup

```text
Create or adapt Isaac Lab task with peg and hole state access.
Expose peg/hole pose in scene.
```

Step 3: Recorder task state extension

```text
Add optional metadata.task_state fields.
Do not change existing base frame schema.
```

Step 4: Evaluator task-specific metrics

```text
Add distance/alignment/depth/stability metrics.
Keep XR runtime quality gates unchanged.
```

Step 5: Small collection

```text
Collect 20 attempts.
Tune thresholds.
Check evaluator agreement manually.
```

Step 6: MVP-1 experiment

```text
Collect curated and uncurated trajectory sets.
Run minimal imitation learning baseline only after dataset quality is stable.
```

---

## 12. Open Questions

질문:

```text
1. MVP-1에서 peg-in-hole을 먼저 할지 connector insertion으로 바로 갈지?
2. Customer-facing task는 어느 산업 도메인으로 설명할지?
3. Initial policy baseline은 ACT, Diffusion Policy, 또는 simpler BC 중 무엇으로 할지?
4. Visual observation 없이 state-only로 첫 uplift 실험을 할지?
5. Precision mode/control-side recenter가 MVP-1 전 필수인지?
```

현재 권장 답:

```text
Start with peg-in-hole.
Keep state-only first.
Use HDF5 baseline export.
Delay LeRobot and behavior cloning until real MVP-0 dataset passes validation.
```
