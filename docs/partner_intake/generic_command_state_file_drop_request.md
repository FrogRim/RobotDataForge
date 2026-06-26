# Generic command-state JSONL file-drop request

Profile id:

```text
generic_command_state_jsonl_v0
```

Current RDF alpha model:

```text
robot_family=generic_manipulator
robot_model=generic_6dof_command_state
dof=6
action_semantics=explicit_command_vector
state_semantics=explicit_state_vector
```

## Required files

```text
metadata.json
command_state.jsonl
```

## Required metadata

```json
{
  "profile_id": "generic_command_state_jsonl_v0",
  "robot_family": "generic_manipulator",
  "robot_model": "generic_6dof_command_state",
  "dof": 6,
  "joint_names": ["joint_1", "joint_2", "joint_3", "joint_4", "joint_5", "joint_6"],
  "units": {
    "joint_position": "rad"
  },
  "action_semantics": "explicit_command_vector",
  "state_semantics": "explicit_state_vector"
}
```

## Required JSONL fields

```text
timestamp
state_timestamp
command_timestamp
state
command
```

`state` and `command` must be 6D finite numeric vectors.

## Clean data expectations

```text
timestamps are finite and strictly monotonic
command_timestamp is not after state_timestamp
command/state lag is within threshold
state is observation/state
command is action/target
state-only logs are not action logs unless a future explicit state-only profile is created
```

## Expected rejection examples

```text
missing command_state.jsonl
missing state
missing command
wrong state dimension
wrong action dimension
NaN or Inf in state/action/timestamp
future state used as action
wrong action semantics
large timestamp gap
reset boundary inside one continuous trajectory
fabricated task_success field
placeholder source owner
```
