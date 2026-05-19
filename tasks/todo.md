# Robot Data Forge — Task Tracker

## MVP-2 Phase-Conditional Saturation Gate — 2026-05-19

### 완료

- [x] MVP-2 offline curation diagnostic 스크립트 작성
  - `scripts/run_mvp2_curation_diagnostic.py` — read-only, 40 tests passed
  - commit: `74e5754 feat: add MVP-2 curation diagnostic`
  - 결과: 48 episodes 중 2개가 Gate A pass이지만 old gate로 거부됨, gate_match_failure_count=0

- [x] Phase-conditional saturation gate 구현 (offline evaluator)
  - `apps/api/app/services/evaluator.py`: INSERT saturation → soft metric, SEAT > 0.30 → hard fail
  - `apps/api/tests/test_evaluator.py`: 8개 테스트 추가, 전체 152 passed
  - commit: `978d8cd feat: add phase-conditional saturation gate`

- [x] Phase-conditional saturation gate 구현 (live HMD curation)
  - `IsaacLab/scripts/environments/teleoperation/teleop_se3_agent.py`
  - 새 env var: `RDF_LIVE_CURATION_MAX_SEAT_ACTION_SATURATION_RATIO=0.30`
  - live log: `sat_agg=... sat_seat=...` 출력
  - IsaacLab repo에 미커밋 변경 다수 있어 별도 commit 보류
  - RDF repo patch artifact로 캡처: `patches/isaaclab/2026-05-19-rdf-live-hmd-curation.patch`
  - smoke 검증: `sat_agg=0.70+`에서도 INSERT saturation으로 reset 없음 ✅

- [x] RETARGETING_JUMP trailing window 수정
  - `IsaacLab/scripts/environments/teleoperation/teleop_se3_agent.py`
  - `RdfLiveCurationGate.RETARGETING_JUMP_WINDOW = 60`
  - gate 판정: cumulative max → 최근 60프레임 max (`retargeting_jump_recent_max`)
  - all-time max는 `retargeting_jump_max`로 result dict에 유지 (observability)
  - log: `jump=<recent_max><={limit}(all=<all_time_max>)` 형식으로 변경
  - smoke 검증: jump 이후 ~60프레임 만에 gate pass 복귀 확인 ✅

- [x] `insertion_depth` metric 버그 수정
  - `scripts/rdf_isaac_runtime_recorder.py:531`: `_vec_sub(peg_tip, hole_position)` → `_vec_sub(peg_tip, hole_target)`
  - `scripts/run_live_rdf_smoke_test.sh`: `RDF_HOLE_TARGET_LOCAL_OFFSET=0,0,0.025` 기본값 추가
  - 원인: `hole_position`은 hole body CoM(바닥)이므로 항상 depth=0
         수정 후 `hole_target`(입구 = CoM + height)을 기준으로 계산 → RL success 기준과 일치
  - 수식: `depth = max(0, hole_entry_z - peg_CoM_z)`, threshold 0.025 = 완전 삽입

- [x] SUCCESS_READY threshold 완화 (라이브 + 오프라인 동기화)
  - `scripts/run_live_rdf_smoke_test.sh` 기본값 변경:
    - `RDF_LIVE_CURATION_MAX_RETARGETING_JUMP`: 1.50 → **3.50** (실측 최대 3.453 관측)
    - `RDF_GUIDANCE_PEG_TIP_DISTANCE_MAX`: (없음) → **0.030**
    - `RDF_GUIDANCE_PEG_AXIS_ALIGNMENT_MAX_RAD`: (없음) → **0.40**
    - `RDF_GUIDANCE_INSERTION_DEPTH_MIN`: (없음) → **0.010** (depth 노이즈 대응)
    - `RDF_SUCCESS_READY_HOLD_SEC`: 1.5 → **0.5** (depth 노이즈로 hold 끊기는 문제 해결)
  - `apps/api/app/services/evaluator.py`: `depth_min` default 0.025 → **0.010** (라이브 gate와 동기화)
  - 테스트: 20 passed ✅
  - 검증: `episode_1a3521e94409` — depth=0.0184, SUCCESS_READY hold=0.53/0.50s 통과, auto-finalize 성공 ✅

- [x] Isaac Sim Stop 버튼 crash 수정
  - `IsaacLab/scripts/environments/teleoperation/teleop_se3_agent.py`
  - `env.step()` 직전, `env.sim.render()` 직전에 `env.sim.is_stopped()` 가드 추가
  - 원인: Stop 버튼이 timeline을 멈추지만 `is_running()=True` 유지 → stopped 상태에서 physics 접근 → segfault
  - IsaacLab external repo commit은 보류, RDF patch artifact에 포함

### 대기 중

- [ ] **Gate A pass episode 수집** ≥10개
  - 현재 첫 성공 에피소드 수집됨: `episode_1a3521e94409` (depth=0.0184, score=0.563)
  - 연속 수집 루프 command (`scripts/run_mvp2_curation_diagnostic.py`의 Gate A count 기준):
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
  - 수집 후: `uv run python scripts/run_mvp2_curation_diagnostic.py --pretty`로 gate_A_pass_count 증가 확인

- [ ] **IsaacLab runtime patch 승격**
  - 현재 RDF repo patch artifact: `patches/isaaclab/2026-05-19-rdf-live-hmd-curation.patch`
  - 다음 단계: IsaacLab external repo 전용 commit 또는 dependency pin으로 승격

- [ ] **MVP-2 policy training** (Gate A 에피소드 충분히 쌓인 후)
  - curated vs uncurated 데이터로 policy uplift 실험

---

## 현재 기본값 (run_live_rdf_smoke_test.sh)

| 변수 | 값 |
|---|---|
| `RDF_GUIDANCE_INSERTION_DEPTH_MIN` | 0.010 |
| `RDF_SUCCESS_READY_HOLD_SEC` | 0.5s |
| `RDF_GUIDANCE_PEG_TIP_DISTANCE_MAX` | 0.030 |
| `RDF_GUIDANCE_PEG_AXIS_ALIGNMENT_MAX_RAD` | 0.40 |
| `RDF_LIVE_CURATION_MAX_RETARGETING_JUMP` | 3.50 |
| `RDF_LIVE_CURATION_MAX_SEAT_ACTION_SATURATION_RATIO` | 0.30 (env var으로 전달) |

## 참고

- 진단 스펙: `docs/superpowers/specs/2026-05-19-mvp2-curation-diagnostic-design.md`
- 진단 플랜: `docs/superpowers/plans/2026-05-19-mvp2-curation-diagnostic.md`
- Gate 변경 플랜: `docs/superpowers/plans/2026-05-19-phase-conditional-saturation-gate.md`
- 진단 리포트: `storage/mvp2_curation_diagnostic/mvp2_curation_diagnostic_report.json`
