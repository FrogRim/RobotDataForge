# Raw-wrist Direct Control Research and Design Sketch

Date: 2026-05-27
Status: research-backed design sketch; no implementation approval implied

## Why this direction

The latest physical Quest/OpenXR run shows that the robot can follow issued direct-EE commands, but the command source does not line up cleanly with the operator's real wrist motion:

- latest trajectory: `storage/trajectories/traj_4108cd8c3b9c.json`
- evaluation failure: `TRACKING_LOSS`
- H9: `right_hand_tracked_rate=0.55`, `xr_frame_valid_rate=0.55`
- H13: `18` valid-to-valid raw wrist jumps larger than 10 cm; max valid-to-valid jump `0.3797 m`
- H11/H12 are no longer the main blocker: deadzone-exit target jumps and fake-anchor acceptance are fixed in the latest analysis.
- current bounded direct-EE controller still takes its motion input from the retargeted OpenXR action stream (`teleop_interface.advance()` -> filter -> bounded target controller), while raw/aligned wrist displacement is mainly stored as metadata.

Therefore, the next architectural branch should make the calibrated raw wrist pose the canonical translation-control source, then keep retargeted OpenXR actions as comparison/fallback data.

## Literature takeaways

### 1. Commodity XR hand/wrist tracking is a viable teleoperation input

- **Holo-Dex** uses headset hand pose estimation to teleoperate a dexterous robot and collect demonstrations. It emphasizes commodity VR, low-latency feedback, real-time hand pose streaming, and recording action information for imitation learning.
- **OPEN TEACH** extends the same idea to Meta Quest 3 and multiple robot morphologies. For robot arms, it explicitly uses the wrist keypoint plus hand landmarks to create a palm coordinate frame; the wrist position maps to robot end-effector position, and hand frame changes map to end-effector orientation.
- **Open-TeleVision** also starts arm control from human wrist poses, converts them into the robot coordinate frame, smooths target poses, and uses IK to command robot arms.

Implication for RDF: raw wrist pose should not be treated as a debug side-channel only. It is a valid first-class control primitive for end-effector translation if we add quality gates, calibration, smoothing, and workspace limits.

### 2. Calibration and frame contracts are not optional

- Quest/VR systems avoid relying on startup pose by defining an explicit reference frame or by initializing from operator/head/wrist pose.
- Open-TeleVision converts wrist poses into the robot frame and treats position and orientation differently for stability.
- Existing RDF notes on Quest2ROS and VisionProTeleop already point to the same conclusion: store raw pose, aligned pose, tracking origin, calibration transform, and timestamps.

Implication for RDF: the design should not tune `RDF_ACTION_POS_AXIS_MAP` endlessly. It should define a canonical transform:

```text
raw OpenXR/SteamVR wrist pose
  -> validity/jump gate
  -> RDF workspace calibration transform
  -> calibrated wrist pose / wrist offset
  -> bounded EE target in Isaac/world/task frame
```

### 3. Raw action provenance matters for learning-ready datasets

- UMI highlights carefully designed policy interfaces, inference-time latency matching, and relative-trajectory action representations.
- DROID demonstrates that large-scale useful robot datasets are not just episode counts; they need consistent hardware/session metadata, calibration, and quality management.
- RoboTurk shows that 6-DoF teleoperation interfaces can produce large imitation datasets, but the action stream must be consistent enough to be learnable.

Implication for RDF: we should log enough to distinguish operator intent, transformed wrist target, robot command, applied end-effector motion, and curation gates. This is more valuable long-term than only storing one final retargeted action vector.

## Recommended architecture

### Name

`raw_wrist_direct_ee_target`

This should be a new explicit mode, not a silent behavior change to current `bounded_direct_ee_target`.

### Data/control pipeline

```text
OpenXR hand cache
  raw_right_wrist_pose [x,y,z,qw,qx,qy,qz]
        |
        v
Tracking quality gate
  - valid pose check
  - anchor-fallback rejection
  - valid-to-valid jump / velocity rejection
  - warmup after loss/jump
  - hold/rebase current EEF target on loss/resume
        |
        v
Calibration layer
  - recenter_id / calibration_id
  - raw wrist origin pose at recenter
  - current EEF origin pose at recenter
  - task/workspace transform
  - optional HMD/head pose conditioning
        |
        v
Raw-wrist target builder
  wrist_offset_raw = raw_wrist_pos - raw_wrist_origin
  wrist_offset_robot = R_calibration * axis_map(wrist_offset_raw)
  desired_ee_target = ee_origin + position_gain * wrist_offset_robot
        |
        v
Bounded target servo
  - deadzone
  - smoothing
  - max step
  - workspace radius clamp
  - robot/task safety clamp
        |
        v
Isaac Forge action
  normalized delta command + explicit metadata
```

### Position vs orientation

Phase the rollout instead of solving all 6 DoF at once:

1. **Phase 1: raw wrist translation only**
   - wrist position controls EE target translation.
   - rotation is held at current/task orientation or remains from current stable retargeter path.
   - gripper/pinch can remain from current retargeter.

2. **Phase 2: palm-frame orientation diagnostic**
   - derive palm frame from wrist + index/pinky/knuckle landmarks as in OPEN TEACH.
   - record orientation target but do not drive it until translation is stable.

3. **Phase 3: relative wrist orientation control**
   - apply relative orientation from recenter pose with rotation gain and max angular step.
   - promote only if replay and operator-feel evidence beat current retargeted orientation.

### Quality gates

Raw-wrist direct control will only improve the system if bad XR samples cannot drive or label accepted data.

Minimum gates:

- `pose_valid`: wrist pose is finite, nonzero, non-anchor, and has a valid quaternion.
- `tracking_loss_gate`: invalid frames hold robot target and mark frames rejected for training.
- `jump_gate`: valid-to-valid wrist displacement above threshold triggers hold/rebase, not robot motion.
- `velocity_gate`: per-second wrist velocity above plausible human threshold triggers hold/rebase.
- `warmup_gate`: after loss/jump, require `RDF_AUTO_RECENTER_VALID_FRAMES` consecutive valid frames.
- `latency/jitter_metric`: store `xr_sample_time`, sim step time, and observed interval jitter when available.

Initial conservative thresholds for diagnostics:

```text
valid_to_valid_jump_warn_m = 0.10
valid_to_valid_jump_reject_m = 0.15
max_control_step_m = existing RDF_DIRECT_EE_MAX_STEP_M, currently 0.04
warmup_valid_frames = existing RDF_AUTO_RECENTER_VALID_FRAMES, currently 3
```

The exact reject threshold should become configurable and evidence-driven after the first HMD-free and physical A/B tests.

### Dataset/action contract

Every saved frame in this mode should make the action provenance explicit:

```text
metadata.raw_xr.right_wrist_pose
metadata.aligned_xr.right_wrist_pose
metadata.raw_wrist_direct_control = {
  mode,
  calibration_id,
  input_source,
  raw_wrist_origin_pose,
  ee_origin_pose,
  wrist_offset_raw,
  wrist_offset_robot,
  desired_ee_target_pose,
  applied_ee_delta_m,
  gate_state,
  gate_reason,
  jump_m,
  velocity_mps,
  retargeter_action_for_comparison
}
action.teleop_intent        # operator-space intent/action
 action.raw_wrist_direct     # calibrated wrist-derived target/action
 action.retargeted_robot_action  # current retargeter output, if available
 action.applied_action       # normalized Isaac action actually applied
 action.learning_action      # stable exported action, dimension-consistent
```

Important: fix the current `learning_action has inconsistent dimensions: [3, 7]` warning before treating any run as training-ready.

## How this differs from the current path

Current path:

```text
OpenXR retargeter action -> RDF action filter -> bounded direct-EE target servo
raw/aligned wrist stored mostly for metadata/debug
```

Proposed path:

```text
raw right wrist pose -> RDF calibration/gate -> bounded direct-EE target servo
retargeter action stored for comparison/fallback
```

This makes RDF's action label more interpretable: the training action can be traced from physical wrist displacement to desired EE target to applied robot command.

## Alternatives considered

### A. Keep tuning retargeter/axis map only

Pros:

- smallest code change.
- stays close to Isaac Lab's default OpenXR retargeter path.

Cons:

- latest evidence already shows axis-map tuning is not discriminating enough.
- operator intent remains hidden behind retargeter internals.
- hard to prove why a saved action corresponds to a hand motion.

Use only as fallback/comparison.

### B. Raw-wrist direct translation + current retargeter rotation/gripper

Pros:

- best balance for RDF MVP-1.
- fixes the specific mismatch: translation source becomes raw calibrated wrist motion.
- keeps pinch/gripper and orientation from known path until translation is proven.
- produces clean provenance for learning-ready action labels.

Cons:

- needs jump gate and calibration tests before physical use.
- may initially feel less expressive than full retargeting.

Recommended first implementation target.

### C. Full raw hand skeleton retargeting now

Pros:

- closest to Holo-Dex / OPEN TEACH dexterous hand-control ambition.
- long-term extensible to multi-finger hands.

Cons:

- too broad for current Franka peg-insert MVP.
- orientation/finger retargeting can obscure the translation bug we need to isolate.

Defer until raw wrist translation is stable.

## Validation plan

### Offline/unit validation

- Add synthetic calibration tests:
  - raw wrist +10 cm in calibrated X -> desired EE target +expected robot axis.
  - raw wrist returns to origin -> target returns to EE origin without drift.
  - recenter changes origin and suppresses first sample.
- Add jump-gate tests:
  - valid-to-valid 30 cm raw jump does not move target.
  - after `N` stable frames, control resumes from current EEF pose.
- Add dimension contract tests:
  - `learning_action` has one declared dimension for the chosen export mode.

### HMD-free Isaac validation

Use synthetic raw wrist trajectories in `check_forge_direct_action_response.py` or a sibling smoke script:

- right-only / left-only / up-only / down-only command sequence.
- confirm sign agreement between synthetic wrist offset and desired target.
- confirm command-to-EEF agreement at lag 1-3 frames.
- confirm H11/H12/H13 pass.

### Physical Quest validation

Run A/B with the same operator script:

```bash
./scripts/run_hmd_axis_debug.sh free-motion
```

Compare:

1. current `bounded_direct_ee_target`
2. new `raw_wrist_direct_ee_target`

Acceptance gates before data collection resumes:

```text
H11 deadzone_exit_target_jump_count = 0
H12 anchor_like_valid_frame_count = 0
H13 valid_to_valid_raw_wrist_jump_gt_10cm_count = 0 in accepted frames
right_hand_tracked_rate >= 0.90 for accepted windows, or invalid windows are explicitly gated out
command_to_ee_sign_agreement_lag_adjusted >= 0.75
raw_wrist_offset_to_desired_target_sign_agreement >= 0.85
learning_action_dimensionality consistent
operator reports right/left/up/down match in HMD
```

Task success is not the first gate. First prove control fidelity; then return to peg insertion success.

## Implementation sketch

Suggested small, reversible sequence:

1. **Document + tests first**
   - add analyzer/test cases for raw-wrist direct-control metadata shape.
   - add synthetic calibration and jump-gate tests.

2. **HMD-free controller path**
   - extend the direct-EE smoke controller with `input_source=raw_wrist_pose`.
   - drive target from synthetic raw wrist pose, not retargeted action.

3. **Live opt-in mode**
   - add `RDF_TELEOP_CONTROL_MODE=raw_wrist_direct_ee_target` or `RDF_DIRECT_EE_INPUT_SOURCE=raw_right_wrist`.
   - keep existing `bounded_direct_ee_target` unchanged for comparison.

4. **Recorder/export contract**
   - write `raw_wrist_direct_control` metadata per frame.
   - ensure HDF5/export includes the stable chosen learning action.

5. **Physical A/B run**
   - one free-motion run per mode.
   - compare H9/H13, raw wrist target mapping, command-to-EEF response, operator feel.

## Stop conditions

Stop and re-plan if any of these happen:

- raw wrist stream remains below 90% valid after gates even outside occlusion-heavy periods.
- valid-to-valid jumps persist after jump gate because OpenXR reports no confidence/quality signal to distinguish them.
- raw-wrist direct target improves metrics but feels worse to operator, suggesting missing camera/HMD frame conditioning.
- learning export cannot represent one stable action contract without inconsistent dimensions.

## References

- Holo-Dex: https://arxiv.org/abs/2210.06463
- OPEN TEACH: https://arxiv.org/abs/2403.07870
- Open-TeleVision: https://arxiv.org/abs/2407.01512
- Universal Manipulation Interface: https://arxiv.org/abs/2402.10329
- DROID: https://arxiv.org/abs/2403.12945
- RoboTurk: https://arxiv.org/abs/1811.02790
- DexPilot: https://research.nvidia.com/publication/2020-05_dexpilot-vision-based-teleoperation-dexterous-robotic-hand-arm-system
- Existing RDF notes: `../../developer/papers/2024_open_teach.md`, `../../developer/papers/2024_open_television.md`, `../../developer/papers/2024_umi.md`, `../../developer/papers/2024_droid.md`, `../../developer/papers/2024_quest2ros.md`, `../../developer/papers/2024_visionproteleop.md`, `../../developer/papers/2026_isaac_lab_openxr_device.md`

## Implementation status — 2026-05-27

The first opt-in implementation slice is now available as `raw_wrist_direct_ee_target`.

- Default behavior remains `bounded_direct_ee_target`.
- HMD test entrypoint: `./scripts/run_hmd_axis_debug.sh raw-wrist-direct`.
- HMD-free smoke artifact: `storage/hmd_motion_mapping/forge_direct_action_response_20260527_raw_wrist_direct.json` with `passed=true`.
- Recorder contract: frames include `action.raw_wrist_direct` plus raw/retargeted/executed control fields.
- Next required evidence is a physical Quest/OpenXR A/B run, not further axis-map guessing.
