# Franka-style file-drop request

Profile id:

```text
franka_state_jsonl_v0
```

Current RDF alpha model:

```text
robot_family=franka
robot_model=panda
dof=7
action_semantics=q_d_command
state_semantics=q_actual_state
```

## Required files

```text
metadata.json
franka_state.jsonl
franka_command.jsonl
```

## Required metadata

```json
{
  "profile_id": "franka_state_jsonl_v0",
  "robot_family": "franka",
  "robot_model": "panda",
  "dof": 7,
  "joint_names": [
    "panda_joint1",
    "panda_joint2",
    "panda_joint3",
    "panda_joint4",
    "panda_joint5",
    "panda_joint6",
    "panda_joint7"
  ],
  "units": {
    "joint_position": "rad"
  },
  "action_semantics": "q_d_command",
  "state_semantics": "q_actual_state"
}
```

## Required JSONL fields

`franka_state.jsonl` rows:

```text
timestamp
q
O_T_EE
robot_mode
```

`franka_command.jsonl` rows:

```text
timestamp
q_d
O_T_EE_d
```

`q` and `q_d` must be 7D vectors. `O_T_EE` and `O_T_EE_d` must be 16-number transforms.

## Clean data expectations

```text
timestamps are finite and strictly monotonic
state and command rows are aligned by row count and timestamp
q is actual state
q_d is commanded target/action
O_T_EE is a plausible rigid transform
O_T_EE_d is present when command semantics require it
robot_mode == move for clean training-eligible rows
```

## Expected rejection examples

```text
missing state or command file
wrong DOF
non-finite q or q_d
timestamp drift between state and command
missing or malformed O_T_EE
non-rigid transform
robot mode not in clean motion state
missing action semantics
fabricated task_success field
```
