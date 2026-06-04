# VisionProTeleop

## Overview

- problem: RDF는 hand/head tracking, visual feedback, session recording, calibration metadata를 하나의 reproducible dataset pipeline으로 묶어야 한다.
- why it matters: VisionProTeleop은 Python client가 hand/head tracking을 받고, video/simulation을 다시 headset으로 stream하며, recordings에 tracking/video/calibration metadata를 포함하는 구조를 제공한다.

## System Architecture

- components:
  - VisionOS Tracking Streamer app.
  - Python `avp_stream` library.
  - WebRTC video/audio/simulation streaming.
  - Tracking Manager app for recordings/calibration.
  - Isaac Lab/MuJoCo AR simulation mode.
- data flow:
  - headset streams hand/head tracking to Python.
  - Python renders robot camera/simulation stream back.
  - session can be recorded with tracking JSON, video, timestamps, calibration metadata.

## Data Pipeline (MOST IMPORTANT)

- input (VR signal):
  - head pose.
  - right/left wrist.
  - finger skeleton.
- processing (mapping -> robot action):
  - choose tracking origin: headset native frame or simulation world frame.
  - simulation mode can set `origin="sim"` so hand tracking is already in sim coordinates.
- output (dataset):
  - video file.
  - tracking JSON with hand/head poses.
  - metadata with timestamps, calibration, session details.

## Dataset Structure

- state:
  - head pose.
  - wrist/finger poses.
  - simulation/robot state.
- action:
  - retargeted robot command from hand pose.
- observation:
  - video/audio/simulation stream.
- timestamp:
  - tracking/video/session timestamps.
  - RDF should add equivalent fields even before video recording exists.

## Logging Strategy

- frequency:
  - depends on WebRTC/tracking stream.
  - stream and control loops are separated.
- storage format:
  - video encoded H.264/H.265.
  - tracking JSON.
  - metadata JSON.

## Implementation Details

- VisionProTeleop explicitly exposes `set_origin("avp")` and `set_origin("sim")`.
- It includes camera calibration workflow and synchronized egocentric recording.
- It supports overlays through frame callbacks before streaming back to headset.

## Direct Implementation Mapping (MOST IMPORTANT)

- where this fits in my codebase:
  - `scripts/rdf_isaac_runtime_recorder.py`
  - `apps/api/app/schemas/common.py`
  - `apps/web/app/episodes/[episodeId]`
  - `docs/DEBUGGING_GUIDE.md`
- what module/function to modify:
  - `_xr_metadata()`: add `tracking_origin`, `head_pose`, `right_fingers`, `left_fingers`.
  - `TrajectoryFrame.metadata`: store `origin_frame = "steamvr_openxr"` or later `"sim"`.
  - frontend replay: show calibration/tracking origin summary.

## Minimal Integration Plan

1. Add `tracking_origin` and `coordinate_frame` metadata to every RDF trajectory.
2. Add `head_pose` extraction if Isaac OpenXR cache exposes head tracking target.
3. Add ghost visual/replay overlay later using same data.
4. Add `calibration_metadata` summary even if visual recording is not implemented.

## Expected Impact

- coordinate-frame ambiguity becomes explicit.
- future AVP or other XR device integration will not require schema rewrite.
- current Quest/SteamVR path can still use the same metadata keys.

## What to Adopt

- explicit `origin` concept.
- separate tracking JSON / video / metadata storage idea.
- calibration metadata as first-class dataset field.

## What to Avoid

- switching hardware to Vision Pro for MVP.
- cloud sync or personal cloud recording. AGENTS.md forbids marketplace/payment-like scope and current storage is local filesystem.

## Reference

- https://github.com/Improbable-AI/VisionProTeleop
