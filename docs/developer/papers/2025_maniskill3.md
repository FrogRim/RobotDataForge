# ManiSkill 3 Dataset Tools

## Overview

- problem: RDF must support replay, conversion, reproducibility, and training-ready dataset exports.
- why it matters: ManiSkill 3 demonstrates a clean split between compressed raw trajectory, metadata JSON, replay/conversion tools, and LeRobot conversion.

## System Architecture

- components:
  - trajectory HDF5 file.
  - matching JSON metadata file.
  - replay tool.
  - observation/control-mode conversion.
  - LeRobot converter.
- data flow:
  - raw demonstration stores initial states/actions/seeds.
  - replay reconstructs trajectory.
  - conversion adds target observation mode/control mode.
  - converted dataset is used for imitation learning.

## Data Pipeline (MOST IMPORTANT)

- input (VR signal):
  - not VR-specific.
  - RDF provides teleop demonstrations as raw trajectories.
- processing (mapping -> robot action):
  - raw trajectories can be replayed into different observation/control modes.
  - control mode conversion makes learning easier.
- output (dataset):
  - HDF5 trajectory.
  - JSON metadata.
  - converted LeRobot dataset.

## Dataset Structure

- state:
  - `env_states` with actors/articulations.
  - reset kwargs and initial states.
- action:
  - `actions [T, A]`.
- observation:
  - optional `obs [T+1, D]`.
  - can be generated during replay.
- timestamp:
  - timestep index and elapsed steps.

## Logging Strategy

- frequency:
  - simulator step.
- storage format:
  - `trajectory.{obs_mode}.{control_mode}.{sim_backend}.h5`.
  - paired `.json` with env info and episode metadata.

## Implementation Details

- ManiSkill stores enough information to reproduce a trajectory without storing every large observation.
- Replay can save videos, save converted trajectories, and switch observation/control modes.
- It has a converter to LeRobot format.

## Direct Implementation Mapping (MOST IMPORTANT)

- where this fits in my codebase:
  - `apps/api/app/services/storage.py`
  - `apps/api/app/services/exporter.py`
  - `scripts/rdf_isaac_runtime_recorder.py`
  - `apps/web/lib/trajectory.ts`
- what module/function to modify:
  - recorder: store `reset_state` and `env_seed` if accessible.
  - exporter: separate raw trajectory storage from generated observation export.
  - add `scripts/replay_rdf_trajectory.py` for deterministic replay checks.

## Minimal Integration Plan

1. Add trajectory summary keys:
   - `env_seed`
   - `reset_state_available`
   - `control_mode`
   - `obs_mode`
2. Add a paired metadata JSON for export:
   - `env_info`
   - `episodes`
   - `source_type`
   - `source_desc`
3. Build replay-first workflow before camera-heavy storage.

## Expected Impact

- RDF datasets become reproducible and convertible.
- Storage stays lightweight until visual observations are needed.

## What to Adopt

- paired metadata file.
- raw compressed trajectory first, replay-to-observation later.
- explicit control mode and observation mode.

## What to Avoid

- describing ManiSkill 3 as Isaac Sim native. AGENTS.md explicitly forbids that.
- moving RDF primary simulator away from Isaac Lab.

## Reference

- https://maniskill.readthedocs.io/en/v3.0.0b20/user_guide/datasets/demos.html
- https://maniskill.readthedocs.io/en/latest/user_guide/datasets/replay.html
