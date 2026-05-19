# 로드맵

1. MVP-0: Quest/OpenXR/Isaac Lab 수집 루프를 닫는다.
2. MVP-1: peg-in-hole에서 learning-ready artifact를 증명한다 (curated dataset + evaluator pipeline).
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
    RDF_TELEOP_CONTROL_MODE=bounded_direct_ee_target \
    RDF_AUTO_SUCCESS_FINALIZE=1 \
    RDF_AUTO_FINALIZE_REQUIRE_LIVE_CURATION=1 \
    RDF_LIVE_CURATION_MAX_SEAT_ACTION_SATURATION_RATIO=0.30 \
    RDF_LIVE_CURATION_ON_FAIL=reset \
    RDF_EXIT_AFTER_FINALIZE=1 \
    ./scripts/run_live_rdf_smoke_test.sh --no-start-xr
```

연속 수집 루프 (Gate A pass 10개 목표):
```bash
RDF_ISAAC_TASK=Isaac-Forge-PegInsert-Direct-v0 \
    RDF_TASK_TYPE=peg_in_hole \
    RDF_MAX_FRAMES=600 \
    RDF_WARMUP_VALID_FRAMES=10 \
    RDF_TELEOP_CONTROL_MODE=bounded_direct_ee_target \
    RDF_AUTO_SUCCESS_FINALIZE=1 \
    RDF_AUTO_FINALIZE_REQUIRE_LIVE_CURATION=1 \
    RDF_LIVE_CURATION_MAX_SEAT_ACTION_SATURATION_RATIO=0.30 \
    RDF_LIVE_CURATION_ON_FAIL=reset \
    RDF_EXIT_AFTER_FINALIZE=1 \
    GATE_A_TARGET=10 \
    ./scripts/run_collection_loop.sh
```
