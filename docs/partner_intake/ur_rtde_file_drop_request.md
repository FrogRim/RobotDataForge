# UR RTDE-style file-drop request

Profile id:

```text
ur_rtde_csv_v0
```

Current RDF alpha model:

```text
robot_family=universal_robots
robot_model=ur10e
dof=6
action_semantics=target_q_command
state_semantics=actual_q_state
```

## Required files

```text
metadata.json
rtde_output.csv
```

## Required metadata

```json
{
  "profile_id": "ur_rtde_csv_v0",
  "robot_family": "universal_robots",
  "robot_model": "ur10e",
  "dof": 6,
  "joint_names": [
    "shoulder_pan_joint",
    "shoulder_lift_joint",
    "elbow_joint",
    "wrist_1_joint",
    "wrist_2_joint",
    "wrist_3_joint"
  ],
  "units": {
    "joint_position": "rad",
    "tcp_position": "m",
    "tcp_rotation": "rotation_vector_rad"
  },
  "action_semantics": "target_q_command",
  "state_semantics": "actual_q_state"
}
```

## Required CSV columns

```text
timestamp
joint_names
actual_q
target_q
actual_TCP_pose
target_TCP_pose
actual_TCP_speed
robot_mode
safety_status
```

`joint_names`, `actual_q`, `target_q`, TCP pose, and TCP speed must be JSON array strings inside the CSV cell.

## Clean data expectations

```text
timestamps are finite and strictly monotonic
timestamp gaps are within the profile threshold
joint order exactly matches metadata.joint_names
actual_q and target_q are 6D radian vectors
TCP position is meters, not millimeters
TCP rotation is rotation-vector radians
robot_mode == RUNNING for clean training-eligible rows
safety_status == NORMAL for clean training-eligible rows
target_q is the command/action, actual_q is the state
```

## Expected rejection examples

```text
missing actual_q
wrong joint dimension
joint order swapped
degree/radian unit confusion
millimeter/meter TCP confusion
non-monotonic timestamp
large timestamp gap
protective stop or not-running robot mode
target/actual lag above threshold
fabricated task_success field
external claim metadata that does not match supported evidence
```
