# LeRobot Dataset v3

## Overview

- problem: RDF JSON export is sufficient for debugging, but not ideal for large-scale imitation learning.
- why it matters: LeRobot Dataset v3 is a standardized robot learning dataset format with tabular state/action data, MP4 visual streams, and metadata for episode indexing.

## System Architecture

- components:
  - `LeRobotDataset`.
  - Parquet low-dimensional data shards.
  - MP4 visual data shards.
  - metadata for schema, FPS, normalization stats, episode offsets.
  - Hub streaming support.
- data flow:
  - recorder builds dataset frames.
  - frames are written to larger shard files.
  - metadata reconstructs episode-level views.
  - dataset loads into PyTorch training.

## Data Pipeline (MOST IMPORTANT)

- input (VR signal):
  - LeRobot itself is input-agnostic. RDF input is Quest/OpenXR.
- processing (mapping -> robot action):
  - RDF maps Quest handtracking to Isaac action first.
  - exporter maps RDF trajectory frames to LeRobot features.
- output (dataset):
  - `observation.state`
  - `action`
  - `timestamp`
  - optional `observation.images.*`
  - metadata and episode boundaries.

## Dataset Structure

- state:
  - RDF candidate: end-effector pose, object pose, gripper state, tracking flags.
- action:
  - raw Isaac action.
  - relative action.
  - gripper command.
- observation:
  - state-only MVP-0.
  - camera MP4 for MVP-1.
- timestamp:
  - explicit timestamp column.
  - FPS in `meta/info.json`.

## Logging Strategy

- frequency:
  - fixed dataset FPS for training.
  - keep original raw timestamps in metadata if source FPS varies.
- storage format:
  - Parquet for low-dimensional signals.
  - MP4 for images.
  - JSON/Parquet metadata.

## Implementation Details

- v3 decouples storage files from episode API.
- Many episodes can be stored in larger Parquet/MP4 files.
- `finalize()` is required to write metadata/footer and make dataset valid.
- transforms are training-time, not recording-time, which preserves raw data.

## Direct Implementation Mapping (MOST IMPORTANT)

- where this fits in my codebase:
  - `apps/api/app/services/exporter.py`
  - `apps/api/app/routers/datasets.py`
  - `packages/shared/dataset_schema.json`
  - new `scripts/export_rdf_to_lerobot.py`
- what module/function to modify:
  - do not change live recorder first.
  - implement offline converter from accepted RDF trajectories.
  - add dataset export metadata: `fps`, `features`, `num_frames`, `episode_offsets`.

## Minimal Integration Plan

1. Keep `/api/datasets/export` JSON unchanged.
2. Add CLI converter:
   - input: `storage/exports/{dataset_id}.json`
   - output: `storage/exports/{dataset_id}_lerobot/`
3. Map RDF frames to `observation.state` and `action`.
4. Write `meta/info.json`, `meta/episodes`, data shard.
5. Add tests using two short RDF trajectories.

## Expected Impact

- RDF becomes compatible with modern imitation learning tooling.
- MVP-1 learning uplift experiment can use off-the-shelf LeRobot loaders.

## What to Adopt

- metadata-driven episode offsets.
- split low-dimensional and visual data.
- dataset stats and schema metadata.

## What to Avoid

- storing large camera frames inside RDF JSON.
- running heavy Parquet/MP4 encoding in the Isaac teleop loop.

## Reference

- https://github.com/huggingface/lerobot/blob/main/docs/source/lerobot-dataset-v3.mdx
- https://docs.nvidia.com/learning/physical-ai/sim-to-real-so-101/latest/04-lerobot.html
