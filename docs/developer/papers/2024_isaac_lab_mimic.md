# Isaac Lab Mimic

## Overview

- problem: RDF needs to scale from a small number of human demonstrations to more usable synthetic/validated trajectories without asking the operator to collect everything manually.
- why it matters: Isaac Lab Mimic is native to Isaac Lab and provides `DataGenerator`, `DatagenInfo`, source demonstration selection, waypoint trajectories, and generated demonstrations.

## System Architecture

- components:
  - Isaac Lab environment.
  - source demonstration dataset.
  - `DataGenerator`.
  - `DatagenInfoPool`.
  - object/robot nearest-neighbor selection strategies.
  - generated trajectory exporter.
- data flow:
  - load source dataset.
  - parse demonstration into datagen info.
  - select source subtask segments.
  - transform/interpolate waypoints for new scene.
  - execute and check success.
  - export generated demo.

## Data Pipeline (MOST IMPORTANT)

- input (VR signal):
  - RDF human teleop trajectories become source demos.
- processing (mapping -> robot action):
  - convert RDF frames into object-centric subtask segments.
  - generate new trajectories under scene/task variation.
- output (dataset):
  - generated actions.
  - observations.
  - initial state.
  - success flag.
  - source demo indices/labels.

## Dataset Structure

- state:
  - env initial state.
  - simulator states over time.
  - object poses.
  - end-effector pose.
- action:
  - actions executed at each timestep.
  - waypoint trajectory.
- observation:
  - observation dictionary per timestep.
- timestamp:
  - timestep index.
  - RDF should keep original `t` for source demo but generated data can use sim step.

## Logging Strategy

- frequency:
  - simulator timestep.
- storage format:
  - HDF5 source/generated dataset path.
  - generated metadata includes source demo index and success.

## Implementation Details

- `DatagenInfo` centralizes object poses and robot pose data needed for data generation.
- `NearestNeighborObjectStrategy` selects source demos by object pose.
- generation can select a different source demo per subtask.
- `transform_first_robot_pose` and interpolation options influence quality.

## Direct Implementation Mapping (MOST IMPORTANT)

- where this fits in my codebase:
  - `scripts/rdf_isaac_runtime_recorder.py`
  - `apps/api/app/services/exporter.py`
  - `apps/api/app/services/curator.py`
  - `apps/api/app/models/dataset.py`
- what module/function to modify:
  - recorder: ensure object pose and EE pose are always present for source demos.
  - curator: select source demos with high quality and low tracking loss.
  - new script `scripts/prepare_rdf_for_isaaclab_mimic.py`.

## Minimal Integration Plan

1. Do not integrate full Mimic generation immediately.
2. Add source-demo eligibility check:
   - success true.
   - tracking loss low.
   - object pose present.
   - EE pose present.
3. Export eligible RDF trajectories to an intermediate HDF5/JSON format with `datagen_info`.
4. Later implement Isaac Lab Mimic env interface for `Isaac-Stack-Cube-Franka-IK-Rel-v0`.

## Expected Impact

- Human demo count needed for MVP-1 can drop.
- RDF can become a validated source-demo supplier for automated data generation.

## What to Adopt

- object-centric `DatagenInfo`.
- source demo selection strategy.
- success-checked generated demos.

## What to Avoid

- starting Mimic before RDF source demos are clean.
- generating data from failed/tracking-loss trajectories.

## Reference

- https://isaac-sim.github.io/IsaacLab/v2.0.0/source/api/lab_mimic/isaaclab_mimic.datagen.html
- https://huggingface.co/datasets/nvidia/PhysicalAI-Robotics-mindmap-GR1-Drill-in-Box
