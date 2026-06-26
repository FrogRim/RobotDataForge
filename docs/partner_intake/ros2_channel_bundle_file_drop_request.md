# ROS2 channel-bundle file-drop request

Profile id:

```text
ros2_channel_bundle_jsonl_v0
```

Current RDF alpha model:

```text
robot_family=ros2_simulated_manipulator
robot_model=ur10e_channel_bundle
dof=6
action_semantics=command_topic_target_joint_state
state_semantics=joint_states_topic_actual_state
```

This is a JSONL channel-bundle rehearsal profile. It is not a live ROS2/DDS bridge claim and is not an MCAP binary parser.

## Required files

```text
metadata.json
topic_manifest.json
topics/joint_states.jsonl
topics/tf.jsonl
topics/tf_static.jsonl
topics/command.jsonl
```

## Required topics

`topic_manifest.json` must list exactly:

```text
/joint_states
/tf
/tf_static
/command
```

## Required message fields

`topics/joint_states.jsonl`:

```text
timestamp
name
position
```

`topics/tf.jsonl`:

```text
timestamp
parent_frame_id
child_frame_id
translation
```

`topics/tf_static.jsonl`:

```text
parent_frame_id
child_frame_id
```

`topics/command.jsonl`:

```text
timestamp
target_position
frame_id
```

## Clean data expectations

```text
joint_states.name matches expected joint_names exactly
joint_states.position is 6D radians
tf timestamps align with joint state timestamps
command timestamps align with joint state timestamps
tf_static exists
required frame ids include world, base_link, tool0
base frame does not drift inside one trajectory
command target is action, joint_states.position is state
```

## Expected rejection examples

```text
missing /joint_states
missing /tf
missing /tf_static
missing /command
missing frame_id
wrong joint names
wrong dimensions
topic timestamp mismatch
base frame drift
command/state lag above threshold
fabricated task_success field
```
