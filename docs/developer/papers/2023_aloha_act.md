# ALOHA / ACT

## Overview

- problem: RDF must eventually export data that imitation learning baselines can consume and compare.
- why it matters: ALOHA/ACT provides a practical dataset format and training target for bimanual manipulation. Even though RDF is single-arm Franka in MVP-0, the data structure is directly useful.

## System Architecture

- components:
  - leader-follower teleoperation system.
  - recording script `record_episodes.py`.
  - replay script `replay_episodes.py`.
  - HDF5 episode files.
  - ACT policy training.
- data flow:
  - operator controls leader arms.
  - follower robot state/action/images are recorded.
  - each episode is saved as HDF5.
  - ACT trains on observations and action chunks.

## Data Pipeline (MOST IMPORTANT)

- input (VR signal):
  - ALOHA itself is leader-arm teleop, not VR.
  - RDF input remains Quest/OpenXR.
- processing (mapping -> robot action):
  - RDF should convert handtracking actions into stable robot action sequences.
  - ACT prefers temporally coherent action chunks.
- output (dataset):
  - HDF5 with images, `qpos`, `qvel`, `action`.

## Dataset Structure

- state:
  - `/observations/qpos`
  - `/observations/qvel`
- action:
  - `/action`
  - optional `base_action` for mobile variant.
- observation:
  - `/observations/images/{camera_name}`
- timestamp:
  - implicit fixed frequency by row index.
  - RDF should also store explicit timestamps before conversion.

## Logging Strategy

- frequency:
  - control/data frequency around 50Hz in ACT-style setups.
- storage format:
  - one `episode_{idx}.hdf5` per episode.
  - auto-record script can collect many episodes sequentially.

## Implementation Details

- ALOHA docs provide explicit dataset hierarchy:
  - images.
  - qpos.
  - qvel.
  - action.
- It also provides replay tooling to validate recorded episodes.
- ACT uses action chunks to reduce effective horizon and stabilize behavior cloning on precise tasks.

## Direct Implementation Mapping (MOST IMPORTANT)

- where this fits in my codebase:
  - `apps/api/app/services/exporter.py`
  - new `scripts/export_rdf_to_hdf5.py`
  - `apps/api/app/models/learning_experiment.py`
- what module/function to modify:
  - exporter: produce ACT-like HDF5 for MVP-1 baseline.
  - recorder: add robot joint state if accessible from Isaac env.
  - LearningExperiment: store `chunk_size`, `control_frequency`, `policy_class`.

## Minimal Integration Plan

1. Add `scripts/export_rdf_to_act_hdf5.py`.
2. For MVP-0 state-only export:
   - `/observations/qpos`: use Franka joint state if accessible, else EE/object compact state with explicit caveat.
   - `/action`: raw Isaac action.
3. For MVP-1:
   - add camera observations.
   - train simple ACT/BC baseline.
4. Add replay check before training.

## Expected Impact

- Provides a concrete baseline format for learning experiments.
- Helps define what RDF must record beyond current EE/object pose.

## What to Adopt

- HDF5 episode layout for baseline experiments.
- replay before training.
- action chunking as first serious IL baseline.

## What to Avoid

- pretending current MVP-0 JSON is already ACT-ready.
- adding bimanual/mobile scope now.

## Reference

- https://tonyzhaozh.github.io/aloha/
- https://docs.trossenrobotics.com/aloha_docs/2.0/operation/data_collection.html
