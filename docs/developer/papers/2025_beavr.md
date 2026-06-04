# BEAVR

## Overview

- problem: RDF는 VR teleoperation, data recording, policy learning을 하나의 MVP pipeline으로 닫아야 한다.
- why it matters: BEAVR은 Meta Quest 3 기반 VR teleoperation, synchronized multi-modal demonstration recording, LeRobot schema, policy learning compatibility를 한 시스템으로 묶는다.

## System Architecture

- components:
  - Meta Quest 3 VR headset/controllers.
  - robot/network API.
  - low-latency visual feedback.
  - synchronized cameras.
  - LeRobot dataset writer.
  - ACT, Diffusion Policy, SmolVLA evaluation.
- data flow:
  - VR input이 robot control API로 전달된다.
  - camera/state/action streams가 synchronized recording으로 저장된다.
  - demonstrations가 LeRobot schema로 저장된다.
  - policies are trained/evaluated on the recorded data.

## Data Pipeline (MOST IMPORTANT)

- input (VR signal):
  - Quest 3 hand/controller pose.
  - gesture/control command.
- processing (mapping -> robot action):
  - real-time control API.
  - asynchronous think-act loop로 inference/control coupling 완화.
- output (dataset):
  - synchronized multi-modal LeRobot demonstrations.
  - policy training/evaluation result.

## Dataset Structure

- state:
  - robot proprioception.
  - gripper/hand state.
  - task metadata.
- action:
  - robot command.
  - high-frequency action stream.
- observation:
  - front/overhead RGB streams at 480x640 30 FPS.
- timestamp:
  - synchronized streams.
  - latency/jitter/frequency benchmark를 별도 기록.

## Logging Strategy

- frequency:
  - camera 30 FPS.
  - robot/action loop는 별도 frequency.
- storage format:
  - LeRobot schema 직접 저장.
  - performance metrics: latency, jitter, frequency.

## Implementation Details

- BEAVR은 data recording과 policy learning을 같은 system boundary 안에 둔다.
- task success, average time, policy success rate를 operator와 policy 모두에 대해 비교한다.
- RDF MVP-1의 `curated_vs_uncurated_uplift`에 가까운 evaluation framing을 제공한다.

## Direct Implementation Mapping (MOST IMPORTANT)

- where this fits in my codebase:
  - `apps/api/app/schemas/admin.py`
  - `apps/api/app/routers/admin.py`
  - `apps/api/app/models/learning_experiment.py`
  - `apps/web/app/admin`
  - `docs/ROADMAP.md`
- what module/function to modify:
  - Admin KPI에 `teleop_latency_ms`, `jitter_ms`, `recording_fps`, `policy_eval_success_rate` 추가.
  - `LearningExperiment`에 `policy_type` 값으로 `act`, `diffusion_policy`, `smolvla` 허용.
  - dataset export 후 policy evaluation report를 dashboard에 표시.

## Minimal Integration Plan

1. RDF API에 별도 migration 없이 `LearningExperiment.metrics` JSON에 latency/jitter/frequency 값을 저장한다.
2. `/api/admin/kpis`에서 latest learning experiment summary를 반환한다.
3. frontend `/admin`에 `teleop quality` group을 추가한다.
4. `docs/ROADMAP.md`에 MVP-1 baseline policy를 ACT first로 명시한다.

## Expected Impact

- 투자자/고객 관점에서 “데이터가 policy 성능을 올리는가”를 직접 보여줄 수 있다.
- VR UX 개선이 KPI로 연결된다.

## What to Adopt

- Quest 3 + synchronized multi-modal recording.
- LeRobot schema alignment.
- policy result dashboard.
- latency/jitter/frequency metrics.

## What to Avoid

- bimanual/dexterous full scope를 지금 도입하지 않는다.
- multi-embodiment abstraction을 MVP-0에 넣지 않는다.

## Reference

- https://arclab-mit.github.io/beavr-landing/
- https://github.com/ARCLab-MIT/BEAVR-Bot
