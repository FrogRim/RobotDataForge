# MimicGen

## Overview

- problem: collecting many high-quality human demonstrations is expensive.
- why it matters: MimicGen shows a practical pipeline for generating many demonstrations from a small number of human demos, with failed/generated stats and training compatibility.

## System Architecture

- components:
  - source human demonstration dataset.
  - environment interface.
  - subtask annotation/preparation.
  - data generation config.
  - generated HDF5 datasets.
  - robomimic-compatible training.
- data flow:
  - collect source demos.
  - prepare source dataset with extra datagen info.
  - generate config.
  - run `generate_dataset.py`.
  - inspect successful and failed generated demos.
  - train policy.

## Data Pipeline (MOST IMPORTANT)

- input (VR signal):
  - RDF’s Quest/Isaac trajectories are source human demonstrations.
- processing (mapping -> robot action):
  - segment demonstration into object-centric subtasks.
  - transform/stitch segments under new initial states/objects.
- output (dataset):
  - `demo.hdf5` successful generated demos.
  - `demo_failed.hdf5` failed demos.
  - `important_stats.json`.
  - playback videos.

## Dataset Structure

- state:
  - object pose.
  - robot pose.
  - environment metadata.
- action:
  - robot action per timestep.
- observation:
  - simulator observation dict.
- timestamp:
  - timestep index.

## Logging Strategy

- frequency:
  - simulator step.
- storage format:
  - robomimic HDF5.
  - stats JSON.
  - logs and videos.

## Implementation Details

- Each task needs an environment interface that can:
  - retrieve object poses.
  - translate between actions and target end-effector poses.
  - provide subtask termination heuristics.
- Failed generated demos are kept separately for debugging.
- Playback videos are generated for inspection.

## Direct Implementation Mapping (MOST IMPORTANT)

- where this fits in my codebase:
  - `apps/api/app/services/curator.py`
  - `apps/api/app/services/evaluator.py`
  - `apps/api/app/services/exporter.py`
  - new `scripts/generate_synthetic_from_rdf.py`
- what module/function to modify:
  - `ForgeCurate`: add `source_demo_eligible` output.
  - `Evaluation.metrics`: add `subtask_boundaries` later.
  - exporter: include failed trajectories in debug export for generation analysis.

## Minimal Integration Plan

1. Add `subtask_labels` and `subtask_boundaries` optional fields in trajectory summary.
2. For stack cube MVP-0, define simple subtasks:
   - approach cube.
   - grasp/close.
   - move to target.
   - release/stabilize.
3. Add offline script to derive heuristic boundaries from gripper/action/object motion.
4. Use this as preparation layer before Isaac Lab Mimic, not as a separate simulator rewrite.

## Expected Impact

- RDF can turn 100 clean demos into a larger synthetic dataset later.
- Failure analysis becomes systematic because generated failures are stored and counted.

## What to Adopt

- environment interface concept.
- subtask boundary annotation.
- separate successful and failed generated dataset outputs.
- `important_stats.json` equivalent for RDF generation runs.

## What to Avoid

- simulator migration to robosuite.
- generating data before evaluator agreement is trustworthy.

## Reference

- https://mimicgen.github.io/
- https://mimicgen.github.io/docs/tutorials/getting_started.html
