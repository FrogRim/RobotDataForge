# Open-TeleVision

## Overview

- problem: RDF의 current UX issue는 “내 손이 robot target으로 어디에 매핑되는지 보기 어렵다”는 visual feedback 문제다.
- why it matters: Open-TeleVision은 immersive active visual feedback과 teleoperation data pipeline을 함께 다룬다. 특히 image/action replay와 ACT training path가 RDF MVP-1과 연결된다.

## System Architecture

- components:
  - WebXR/Vuer browser-based immersive interface.
  - VisionPro/Quest streaming path.
  - robot/simulation hand teleoperation.
  - dataset post-processing.
  - replay and ACT training scripts.
- data flow:
  - visual stream is sent to headset/browser.
  - operator hand motion controls robot hands.
  - data are recorded.
  - `post_process.py` prepares dataset.
  - `replay_demo.py` checks image/action sequences.
  - ACT training consumes processed data.

## Data Pipeline (MOST IMPORTANT)

- input (VR signal):
  - hand pose from XR browser/session.
  - visual feedback stream.
- processing (mapping -> robot action):
  - hand pose to robot hand action.
  - active view makes fine manipulation easier.
- output (dataset):
  - recordings.
  - post-processed image/action sequences.
  - replayable episodes.

## Dataset Structure

- state:
  - robot hand state.
  - task state.
- action:
  - robot hand action sequence.
- observation:
  - image sequences.
- timestamp:
  - sequence index for image/action alignment.

## Logging Strategy

- frequency:
  - streaming loop and action sequence recording.
- storage format:
  - dataset under `data/recordings`.
  - post-processed training data.

## Implementation Details

- Open-TeleVision has a concrete verification step: `scripts/replay_demo.py` to inspect image/action sequences.
- ACT training command uses dataset task id and chunk size.
- Quest local/network streaming requires HTTPS/tunnel handling.

## Direct Implementation Mapping (MOST IMPORTANT)

- where this fits in my codebase:
  - `apps/web/app/episodes/[episodeId]`
  - `apps/web/lib/trajectory.ts`
  - `scripts/rdf_isaac_runtime_recorder.py`
  - `docs/FRONTEND_PLAN.md`
- what module/function to modify:
  - frontend replay: add `action timeline + end-effector target overlay`.
  - recorder: add `target_end_effector_position` separate from measured EE pose.
  - exporter: add `replay_verified` flag before dataset export.

## Minimal Integration Plan

1. Add `target_end_effector_position` to frame metadata/action payload.
2. Add replay page visualization of action path vs object path.
3. Add `/api/episodes/{id}/mark-replay-verified` or use HumanReview notes for now.
4. Do not export accepted dataset unless replay is possible and evaluation passed.

## Expected Impact

- operator can debug bad teleop sessions visually.
- MVP investor demo gets a clear replay story.
- raw trajectory collection becomes auditable.

## What to Adopt

- replay verification before training.
- image/action sequence thinking.
- active visual feedback and ghost/overlay UI.

## What to Avoid

- ngrok/WebXR networking complexity in MVP.
- building a separate browser XR app while Isaac OpenXR path is already working.

## Reference

- https://github.com/OpenTeleVision/TeleVision
- https://arxiv.org/abs/2407.01512
