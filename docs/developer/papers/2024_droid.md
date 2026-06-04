# DROID

## Overview

- problem: RDF MVP-1 must prove that curated demonstrations produce useful policy data, not only that episodes can be recorded.
- why it matters: DROID is a large-scale teleoperated manipulation dataset collected with a consistent hardware stack and Oculus Quest 2 controllers, and it emphasizes camera calibration, scene diversity, and dataset quality.

## System Architecture

- components:
  - Franka Panda 7DoF robot.
  - two external Zed 2 stereo cameras.
  - wrist-mounted Zed Mini stereo camera.
  - Oculus Quest 2 headset/controllers for teleoperation.
  - portable height-adjustable desk.
  - code/docs for reproducing hardware setup and collection.
- data flow:
  - operator teleoperates robot with Quest controllers.
  - multi-camera observations and robot state/action are recorded.
  - dataset is analyzed for scenes, tasks, camera viewpoints, interaction points.
  - policies are trained/evaluated on collected data.

## Data Pipeline (MOST IMPORTANT)

- input (VR signal):
  - Quest controller command for teleoperation.
- processing (mapping -> robot action):
  - teleop command controls Franka.
  - data is collected across diverse scenes/tasks with consistent hardware.
- output (dataset):
  - trajectories.
  - camera images.
  - robot states/actions.
  - camera calibration metadata.
  - language annotations.

## Dataset Structure

- state:
  - robot state.
  - scene/task metadata.
  - camera calibration.
- action:
  - teleop robot action.
- observation:
  - external stereo cameras.
  - wrist-mounted camera.
- timestamp:
  - synchronized demonstrations.
  - RDF should explicitly track sync and calibration quality.

## Logging Strategy

- frequency:
  - multi-camera + robot data streams.
- storage format:
  - dataset-level metadata and episode-level trajectories.
  - DROID later released improved camera calibrations for many episodes, showing calibration is not one-time setup but dataset maintenance.

## Implementation Details

- DROID standardizes hardware across institutions to make distributed data collection tractable.
- It analyzes 3D interaction points relative to robot base, camera viewpoints, and scene/task diversity.
- It treats calibration metadata as dataset quality infrastructure.

## Direct Implementation Mapping (MOST IMPORTANT)

- where this fits in my codebase:
  - `apps/api/app/models/collection_session.py`
  - `apps/api/app/schemas/collection_session.py`
  - `apps/api/app/routers/admin.py`
  - `apps/api/app/services/evaluator.py`
- what module/function to modify:
  - CollectionSession runtime metadata: add `workspace_id`, `camera_calibration_version`, `xr_calibration_version`, `scene_id`.
  - Admin KPI: add `scene_count`, `task_count`, `workspace_coverage`.
  - Evaluation metrics: add `first_gripper_close_position` or `first_contact_position` for workspace coverage.

## Minimal Integration Plan

1. Add session metadata keys without DB migration by storing them inside existing JSON runtime metrics.
2. In recorder, detect first gripper close frame and store `first_gripper_close_position`.
3. Add admin KPI function to aggregate interaction positions from trajectory summaries.
4. Use this in MVP-0 to avoid collecting 100 nearly identical trajectories.

## Expected Impact

- RDF collection becomes measurable for diversity, not just count.
- MVP-1 design partner discussion can show task/workspace coverage.

## What to Adopt

- dataset diversity metrics.
- camera/XR calibration version metadata.
- interaction point distribution.

## What to Avoid

- copying DROID’s real-world hardware scope now.
- adding real robot control before MVP-0/MVP-1 simulation proof is stable.

## Reference

- https://droid-dataset.github.io/
- https://github.com/droid-dataset/droid
