# HMD axis/yaw live debug protocol

Date: 2026-05-26
Scope: isolate H8, the operator/HMD perceived direction mismatch. As of 2026-05-27, H8 is also the camera-conditioning branch: prove or disprove whether the dataset preserves the HMD/operator camera geometry needed to explain view-dependent direction. Gate A collection remains frozen; this is a short diagnostic run, not dataset collection.

## Current live observation

The `RDF_ACTION_POS_YAW_OFFSET_DEG=90` run is rejected. The operator observed:

- hand up/down moved the robot sideways;
- hand sideways moved the robot up/down.

That means the +90 yaw hypothesis is not the next path. A later operator report narrowed the active symptom to `hand-right -> robot-down`; the current next diagnostic is the short `right-down-fix` wrapper below, not another yaw-offset run.

## Cyan box removal

The cyan/blue box above the task is the recenter start-box visual (`RDF_RECENTER_BOX_VISUAL=1`). It is only a visual aid for the robot-space recenter gate. The recenter gate still works without rendering the box, so the next commands set:

```bash
RDF_RECENTER_BOX_VISUAL=0
```



## 2026-05-26 follow-up: robot cannot reach start box / no useful setup motion

If the robot cannot be moved into the start box, stop the axis test. This is no longer a direction-mapping test; it is a pre-recenter motion/control test. Use `free-motion` first, which bypasses the robot start-box gate and recenters on the first valid hand frames:

```bash
cd ~/robot-data-forge
./scripts/run_hmd_axis_debug.sh free-motion
```

`free-motion` forces:

```text
RDF_RECENTER_MODE=first_valid_hand
RDF_BLOCK_TELEOP_UNTIL_RECENTER=0
RDF_RECENTER_SETUP_CONTROL=0
RDF_RECENTER_BOX_VISUAL=0
RDF_ACTION_POS_AXIS_MAP=x,z,y
```

Pass/fail for this branch:

- PASS: robot visibly moves with the hand at all. Then return to a direction test (`right-down-fix` or another one-variable axis map).
- FAIL: robot still does not move. Then the issue is below the start-box gate: hand tracking, teleop activation, action filter output, bounded direct-EE target, or Isaac env stepping. Use terminal `action_debug`/`motion_debug` logs from the generated run; the HMD operator still does not need to read terminal text.

## 2026-05-26 follow-up: reported right -> down, but latest files did not capture the intended test

After the operator reported that the changed run still maps hand-right to robot-down, the newest local files were checked with `--include-empty-latest`. Both newest trajectories were zero-frame aborts, and they did **not** contain the intended PegInsert identity-map evidence:

```text
traj_168904165832: frames=0, task=Isaac-Stack-Cube-Franka-IK-Rel-v0, position_axis_map=x,z,y
traj_eadf37bfbad4: frames=0, task=Isaac-Stack-Cube-Franka-IK-Rel-v0, position_axis_map=x,z,y
```

Therefore do not infer axis truth from those files. They only prove the long env command/run mode drifted back to the wrapper defaults and ended before any post-recenter recording frames were saved.

To prevent another env-copy drift, use the short wrapper below. It forces PegInsert, hides the cyan recenter box, lowers warmup to 3 valid frames, and runs post-run verification automatically.

### Next one-variable hypothesis: `right-down-fix`

Observation to test: operator moves hand right, robot moves down. If the current source axis feeding robot Z is the operator-right axis, the smallest signed-axis hypothesis is to move source Z into robot X and move source X into robot Z:

```text
RDF_ACTION_POS_AXIS_MAP=-z,y,x
RDF_ACTION_POS_YAW_OFFSET_DEG=0
```

Run:

```bash
cd ~/robot-data-forge
./scripts/run_hmd_axis_debug.sh right-down-fix
```

If this makes right/left mirrored but no longer vertical, test only the sign flip:

```bash
cd ~/robot-data-forge
./scripts/run_hmd_axis_debug.sh right-down-fix-flipped
```

Critical operator rule: do **not** read terminal text while wearing the HMD. Judge direction only after the in-HMD guidance panel shows `RECENTER: OK` and `RECORDING: ON`. Pre-recenter/setup motion is intentionally allowed to get into the start box and is not saved as trajectory evidence.

## Earlier fallback: identity axis-map baseline, no yaw, no box

```bash
cd ~/robot-data-forge
RDF_ISAAC_TASK=Isaac-Forge-PegInsert-Direct-v0 \
RDF_TASK_TYPE=peg_in_hole \
RDF_MAX_FRAMES=180 \
RDF_WARMUP_VALID_FRAMES=10 \
RDF_ACTION_POS_AXIS_MAP=x,y,z \
RDF_ACTION_POS_YAW_OFFSET_DEG=0 \
RDF_ACTION_POS_GAIN=0.40 \
RDF_ACTION_ROT_GAIN=0.35 \
RDF_TELEOP_CONTROL_MODE=bounded_direct_ee_target \
RDF_DIRECT_EE_POS_GAIN=0.18 \
RDF_DIRECT_EE_ROT_GAIN=0.25 \
RDF_DIRECT_EE_MAX_STEP_M=0.04 \
RDF_DIRECT_EE_MAX_ROT_STEP_RAD=0.12 \
RDF_DIRECT_EE_SMOOTHING_ALPHA=0.50 \
RDF_DIRECT_EE_DEADZONE_M=0.003 \
RDF_DIRECT_EE_WORKSPACE_RADIUS_M=0.35 \
RDF_RECENTER_MODE=robot_start_box \
RDF_RECENTER_BOX_CENTER_SOURCE=hole_target_approach \
RDF_RECENTER_BOX_APPROACH_OFFSET=0,0,0.08 \
RDF_RECENTER_BOX_RANDOM_OFFSET=0,0,0 \
RDF_RECENTER_BOX_HALF_EXTENTS=0.07,0.07,0.07 \
RDF_RECENTER_BOX_VISUAL=0 \
RDF_BLOCK_TELEOP_UNTIL_RECENTER=1 \
RDF_RECENTER_SETUP_CONTROL=1 \
RDF_VISUAL_DEBUG=1 \
RDF_DEBUG_ACTION_EVERY=10 \
RDF_DEBUG_MOTION_EVERY=10 \
RDF_AUTO_SUCCESS_FINALIZE=0 \
RDF_EXIT_AFTER_FINALIZE=0 \
./scripts/run_live_rdf_smoke_test.sh --no-start-xr
```

## If an identity fallback fixes vertical but horizontal is rotated

Do not go back to `+90` immediately. Record exactly which directions are wrong, then test one variable at a time:

- if only forward/back is inverted: try `RDF_ACTION_POS_AXIS_MAP=x,-y,z`;
- if only left/right is inverted: try `RDF_ACTION_POS_AXIS_MAP=-x,y,z`;
- if X/Y are swapped again: stop and analyze the latest trajectory before another live run.

## Operator motion script

After robot-start-box recenter is ready, do short isolated motions with pauses:

1. right hand right, pause;
2. right hand left, pause;
3. right hand forward from operator/HMD view, pause;
4. right hand backward from operator/HMD view, pause;
5. right hand up, pause;
6. right hand down, pause.

Use small motions first. Stop the run after these six checks; task completion is not required.

## Success criteria

The active wrapper run is a candidate pass only if all of these hold:

- HMD perception: right/left/forward/back/up/down match the operator viewpoint.
- Camera-conditioning evidence is not discarded: the run records or explicitly marks missing HMD/operator camera pose, XR anchor/yaw provenance, world/robot/task/camera transform chain, and visibility/projection readiness.
- Analyzer or `--include-empty-latest` verification confirms the intended `position_axis_map` for the selected wrapper mode and `position_yaw_offset_deg=0`.
- H7 stays PASS: command-to-next-EEF sign agreement shows the robot follows the command.
- H6 is not dominant: workspace clamp/saturation is not masking direction.
- Tracking remains stable enough for subjective judgment.

## Failure criteria

Mark the run failed if any of these occur:

- Up/down still moves sideways, or sideways still moves up/down.
- Direction seems viewpoint-dependent but trajectory metadata cannot reconstruct camera/operator view geometry.
- Metadata does not store the selected wrapper mode axis map and `position_yaw_offset_deg=0`.
- H7 drops to WARN/FAIL.
- H6 saturation/clamp dominates, making direction uninterpretable.
- Tracking instability invalidates the subjective run.

## Analysis command after each run

```bash
cd ~/robot-data-forge
uv run python scripts/verify_latest_rdf_recording.py --include-empty-latest --pretty
uv run python scripts/analyze_hmd_motion_mapping.py \
  --latest \
  --pretty \
  --output storage/hmd_motion_mapping/latest_mapping_report.json
```

## Evidence to record after each run

- Trajectory ID and episode ID.
- `config.position_axis_map` and `config.position_yaw_offset_deg` from the analyzer report.
- H1/H6/H7/H8/H9 statuses.
- Operator subjective result: which of right/left/forward/back/up/down matched or failed.
- Camera-conditioning status: `camera_conditioning_ready`, missing camera geometry reasons, and whether raw action labels were kept separate from camera/operator-view derived labels.
- If failed, the next one-variable axis-map change to try and why.

## Update scope

Update only diagnostic tracking artifacts unless code changes are required:

- `/home/kangrim/tasks/todo.md`: mark this iteration status and summarize evidence.
- `Handoff.md`: durable current state, active hypothesis, latest trajectory, next command.
- `docs/WORKLOG.md`: dated execution/evidence log.
- `storage/hmd_motion_mapping/latest_mapping_report.json`: generated analyzer output.

Do not update Gate A collection status until a mapping is proven and operator-confirmed.
