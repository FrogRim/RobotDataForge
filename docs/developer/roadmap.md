# 로드맵

1. MVP-0: Quest/OpenXR/Isaac Lab 수집 루프를 닫는다.
2. MVP-1: peg-in-hole에서 learning-ready artifact를 증명한다 (curated dataset + evaluator pipeline). 신규 ForgeXR artifact는 camera-conditioning-ready 여부도 별도 gate로 기록한다.
3. MVP-2: curated gate를 정교화하고 policy training uplift를 증명한다.
4. Post-MVP: contact-rich, deformable, tool-use, long-horizon task로 확장한다.

---

## MVP-0 — 완료

- monorepo structure, Isaac handtracking wrapper, IsaacLabAdapter/MockSimAdapter
- evaluator, exporter, FastAPI skeleton, DB models
- Task/Episode/Trajectory API, local recorder submit flow
- Next.js frontend (task/session list, replay, admin dashboard, dataset export)
- real Isaac runtime frame hook boundary
- Quest/OpenXR/Isaac 실기기 연결 + `RDF_RECORD=1` 제출 검증 완료

## MVP-1 — 완료

- peg-in-hole (Isaac-Forge-PegInsert-Direct-v0) live HMD 수집 루프 완성
- insertion task_state 추출 (APPROACH/CONTACT/INSERT/SEAT phase)
- `insertion_depth` metric 구현 및 버그 수정 (hole entry 기준 계산)
- live curation gate: tracking loss, retargeting jump, action saturation
- SUCCESS_READY guidance + HMD panel (hold timer, auto-finalize)
- offline evaluator pipeline (score, quality_score, failure_reason)
- 71개 에피소드 수집, learning-ready artifact 확보
- 2026-05-27 기준 추가 결정: `camera-conditioning-ready`는 MVP-1 artifact의 새 metadata/readiness gate다. 기존 raw/replay/action/evaluator evidence를 무효화하지 않지만, camera-conditioned visual downstream claim 전에는 HMD/camera geometry, transform chain, visibility, projection smoke를 구현/검증해야 한다.

## MVP-1.5 — Camera Conditioning Gate — 신규

**목표:** ForgeXR dataset을 action-contract-valid, replay-verified, task-validated뿐 아니라 camera-conditioning-ready로 만들 수 있게 한다.

### 필요한 산출물

- `summary.camera_conditioning` 및 frame-level `metadata.camera_conditioning` 저장
  - HMD/operator view frame
  - camera intrinsics/extrinsics 또는 XR runtime projection provenance
  - `T_world_camera`, `T_world_robot_base`, `T_world_end_effector`, `T_world_task_target`
  - `T_camera_end_effector`, `T_camera_task_target`
- Derived action views
  - `robot_world_action`
  - `robot_base_action`
  - `eef_relative_action`
  - `camera_relative_action`
  - `operator_view_relative_action`
- Readiness gate
  - intrinsics present
  - extrinsics present
  - time aligned
  - task objects visible
  - projection smoke passed
- Export/manifest
  - camera-conditioning failure reasons in curation manifest
  - HDF5/export fields for visual downstream loaders
  - trainer/loader smoke that can read camera conditioning metadata

### 완료 조건

- Raw trajectory는 camera-ready 여부와 무관하게 저장된다.
- `camera_conditioning_ready=false`인 trajectory는 camera-conditioned proof/training claim에서 제외된다.
- `camera_conditioning_ready=true`인 trajectory는 robot/action replay evidence와 camera/view transform evidence를 동시에 가진다.

## MVP-2 — 진행 중

**목표:** phase-conditional curation gate로 transition-rich episode를 선별하고 policy uplift를 증명한다.

### 완료

- offline curation diagnostic (`scripts/run_mvp2_curation_diagnostic.py`)
  - Gate A/B/C 병렬 판정, phase-conditional saturation 분석
- phase-conditional saturation gate 구현
  - INSERT saturation → soft metric (hard fail 제거)
  - SEAT saturation > 0.30 → hard fail
  - RDF offline evaluator는 commit됨
  - live HMD gate는 `/patches/isaaclab/2026-05-19-rdf-live-hmd-curation.patch`로 versioned artifact 캡처
- RETARGETING_JUMP trailing 60-frame window 수정
  - 단발 jump 이후 ~60프레임 만에 gate 복귀 가능
- robot-space start-box recenter UX 구현
  - operator 첫 손 위치가 아니라 `/World/RDFRecenterStartBox` 기준으로 recenter
  - start box center는 `hole_target_approach` + episode/reset당 1회 random offset
  - recenter 전 setup-only control 허용, recording/warmup은 recenter 후 시작
  - 세부 계약: [`docs/experiments/hmd/hmd_recenter_start_box.md`](../experiments/hmd/hmd_recenter_start_box.md)
- SUCCESS_READY threshold 완화 (노이즈 대응)
  - `depth_min` 0.025 → 0.010 (live + offline 동기화)
  - `hold_sec` 1.5 → 0.5
  - `dist_max` 0.015 → 0.030, `jump_max` 1.5 → 3.5
- Isaac Sim Stop 버튼 crash 수정 (`env.sim.is_stopped()` 가드, IsaacLab patch artifact에 포함)
- **첫 Gate A pass episode 수집 완료** (`episode_1a3521e94409`, depth=0.018)

### 대기 중

- Gate A pass episode ≥10개 수집
- IsaacLab runtime patch를 external repo 전용 commit 또는 dependency pin으로 승격
- curated vs uncurated policy training 실험 (uplift 증명)

---

## 현재 수집 command

단발 실행:
```bash
RDF_ISAAC_TASK=Isaac-Forge-PegInsert-Direct-v0 \
    RDF_TASK_TYPE=peg_in_hole \
    RDF_MAX_FRAMES=600 \
    RDF_WARMUP_VALID_FRAMES=10 \
    RDF_ACTION_POS_AXIS_MAP=x,z,y \
    RDF_TELEOP_CONTROL_MODE=bounded_direct_ee_target \
    RDF_AUTO_SUCCESS_FINALIZE=1 \
    RDF_AUTO_FINALIZE_REQUIRE_LIVE_CURATION=1 \
    RDF_LIVE_CURATION_MAX_SEAT_ACTION_SATURATION_RATIO=0.30 \
    RDF_LIVE_CURATION_ON_FAIL=reset \
    RDF_RECENTER_MODE=robot_start_box \
    RDF_RECENTER_BOX_CENTER_SOURCE=hole_target_approach \
    RDF_RECENTER_BOX_APPROACH_OFFSET=0,0,0.08 \
    RDF_RECENTER_BOX_RANDOM_OFFSET=0.02,0.02,0.01 \
    RDF_RECENTER_BOX_VISUAL=0 \
    RDF_BLOCK_TELEOP_UNTIL_RECENTER=1 \
    RDF_RECENTER_SETUP_CONTROL=1 \
    RDF_EXIT_AFTER_FINALIZE=1 \
    ./scripts/run_live_rdf_smoke_test.sh --no-start-xr
```

연속 수집 루프 (Gate A pass 10개 목표):
```bash
RDF_ISAAC_TASK=Isaac-Forge-PegInsert-Direct-v0 \
    RDF_TASK_TYPE=peg_in_hole \
    RDF_MAX_FRAMES=600 \
    RDF_WARMUP_VALID_FRAMES=10 \
    RDF_ACTION_POS_AXIS_MAP=x,z,y \
    RDF_TELEOP_CONTROL_MODE=bounded_direct_ee_target \
    RDF_AUTO_SUCCESS_FINALIZE=1 \
    RDF_AUTO_FINALIZE_REQUIRE_LIVE_CURATION=1 \
    RDF_LIVE_CURATION_MAX_SEAT_ACTION_SATURATION_RATIO=0.30 \
    RDF_LIVE_CURATION_ON_FAIL=reset \
    RDF_RECENTER_MODE=robot_start_box \
    RDF_RECENTER_BOX_CENTER_SOURCE=hole_target_approach \
    RDF_RECENTER_BOX_APPROACH_OFFSET=0,0,0.08 \
    RDF_RECENTER_BOX_RANDOM_OFFSET=0.02,0.02,0.01 \
    RDF_RECENTER_BOX_VISUAL=0 \
    RDF_BLOCK_TELEOP_UNTIL_RECENTER=1 \
    RDF_RECENTER_SETUP_CONTROL=1 \
    RDF_EXIT_AFTER_FINALIZE=1 \
    GATE_A_TARGET=10 \
    ./scripts/run_collection_loop.sh
```

## 2026-05-28 Gate 0 추가 결정

현재 Gate A physical collection은 `handtracking loss` / `RAW_WRIST_JUMP` / `AUTO_RECENTER_UNSTABLE_RIGHT_WRIST` 문제가 사라질 때까지 재개하지 않는다.

새 선행 gate:

```text
Gate 0 XR Input Stream Viability
→ Gate A physical collection
→ curation/export/trainer smoke
```

Gate 0 완료 조건:

- `./scripts/run_hmd_axis_debug.sh gate0-static`
- `./scripts/run_hmd_axis_debug.sh gate0-slow-motion`
- `./scripts/run_hmd_axis_debug.sh gate0-recenter`
- `./scripts/run_hmd_axis_debug.sh gate0-reacquire`
- 각 run의 `.gate0.json`에서 `gate0_pass=true`
- H13 `PASS`
- `RAW_WRIST_JUMP`, `TRACKING_LOSS`, `AUTO_RECENTER_UNSTABLE_RIGHT_WRIST` 없음

위 조건 전에는 이 문서의 기존 “Gate A pass episode ≥10개 수집” command를 실행하지 않는다. 기존 command는 Gate 0 통과 후 재개할 대기 command다.

## 2026-05-31 Gate 0 Phase 1: Input-Agnostic Foundation

ForgeXR Phase 1은 Quest handtracking 전용 로직을 바로 모든 입력 소스로 확장하지 않고, 먼저 source-agnostic input sample boundary를 도입한다.

이번 Phase 1 포함 범위:

- `WristPoseSample` / `InputSourceAdapter` contract
- 현재 Quest/OpenXR handtracking trajectory metadata를 normalize하는 `QuestOpenXrHandtrackingAdapter`
- Gate 0 report의 input source identity
- `scripts/run_collection_loop.sh`의 script-limited Gate A hard block

이번 Phase 1 제외 범위:

- episode event bus / event spine 구현
- MediaPipe, controller, Vision Pro, Pico, phone pose, smart glasses 등 추가 adapter 구현
- DB migration
- IsaacLab live control loop 대규모 refactor
- policy A/B, VLA, WFM, real robot validation, full RL, connector insertion proof
- wrist-mounted hardware, marker, glove, mocap 등 추가 wearable/hardware

Event dispatch/spdlog-style fan-out은 장기 방향으로 유지하되, Phase 1에서는 구현하지 않는다. 향후 event sink는 side effect 전용이어야 하며, curation acceptance, proof decision, training eligibility authority가 되면 안 된다.
