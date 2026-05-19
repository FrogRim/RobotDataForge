# Design: MVP-2 Curation Diagnostic Script

Date: 2026-05-19
Topic: `run_mvp2_curation_diagnostic.py`

---

## Problem

현재 live curation gate는 `NATIVE_ACTION_SATURATION`을 hard fail 기준으로 사용한다.
Bounded direct EE mode에서 `native_isaac_action = clip(command_step / pos_threshold, -1, 1)`이므로,
saturation은 "bad teleop"이 아니라 "operator가 max-speed step을 사용했다"는 뜻일 수 있다.

결과:
- INSERT 중 움직임이 필요한 episode가 fail → transition-rich 데이터가 거부됨
- SEAT만 있는 조용한 episode가 pass → 학습에 쓸모 없는 정적 데이터만 accepted

MVP-2 policy learning을 위해서는 CONTACT + INSERT + SEAT가 모두 있는 transition-rich artifact가 필요하다.
그 전에 무엇이 왜 rejected/accepted되는지를 숫자로 파악해야 한다.

---

## Goal

curation 기준을 변경하지 않고, 다음 두 가지를 per-episode로 리포트하는 read-only 진단 스크립트:

1. **현재 data가 왜 accepted/rejected되었는가** — 기존 gate 기준 분석
2. **MVP-2용 transition-rich 기준으로는 무엇이 부족한가** — 새 A/B/C gate 판정

---

## Data Sources and Role Separation

| Source | Role |
|---|---|
| `storage/trajectories/*.json` | **Source of truth** — 모든 새 metric의 canonical source |
| `storage/evaluations/*.json` | **비교 대상** — 기존 gate 기록 읽기만 (metric derivation에 참여하지 않음) |
| SQLite / API | **없음** — 의존 없음, offline 실행 가능 |

이 분리는 의도적이다. trajectory frame에서 독립적으로 재계산한 결과와
evaluation JSON에 기록된 판단을 비교함으로써 gate logic의 일관성을 교차 검증할 수 있다.

---

## Frame-Level Field Mapping

진단 스크립트가 raw trajectory JSON에서 직접 읽는 필드:

### action_phase (fallback chain, priority order)

```
1. frame.metadata.action_phase                    → primary
2. frame.metadata.task_state.action_phase         → secondary
3. frame.action_phase                             → tertiary
4. "UNKNOWN"                                      → default
```

`phase_source_distribution`을 output에 포함: 어느 경로에서 phase를 읽었는지 통계.

### saturation check

```
frame.action.native_isaac_action   → list[float]
  per-frame: saturated = any(abs(v) >= ACTION_SAT_VALUE_THRESHOLD)
  ACTION_SAT_VALUE_THRESHOLD default: 0.999
```

### command step in meters (fallback chain, priority order)

```
1. frame.action.control_filter.teleop_control_mode.applied_ee_delta_m
2. frame.action.executed_control.applied_end_effector_action.delta_position
3. frame.action.learning_action.command
```

`frame.action.relative.delta_position`은 normalized/native action에 해당하며 meters가 아니다.
command_step_norm / jerk 계산에 사용하지 않는다. diagnostic-only 참고값으로만 기록한다.

### 기타

```
frame.metadata.xr_frame_valid   → bool, tracking validity
```

---

## Per-Episode Output

### Identity

```
episode_id
trajectory_id
frame_count
```

### Recorded Gate State (from eval JSON — 비교 대상)

```
recorded_episode_status        # success / reset / failure / incomplete
recorded_evaluator_success     # bool
recorded_failure_reason        # NATIVE_ACTION_SATURATION, RETARGETING_JUMP, etc.
recorded_live_curation_status  # passed / failed (evaluator curation decision)
recorded_training_eligible     # bool
old_live_gate_pass             # recorded_failure_reason is None
old_evaluator_pass             # recorded_evaluator_success == True
```

### Phase Coverage (from frames)

```
phase_counts: {APPROACH, CONTACT, INSERT, SEAT, ALIGN, UNKNOWN, ...}
phase_rates:  phase_counts[phase] / frame_count
phase_source_distribution: {primary: N, secondary: N, tertiary: N, default: N}
```

### Phase-Conditional Saturation (from frames — 핵심 신규 metric)

saturation = `any(abs(v) >= ACTION_SAT_VALUE_THRESHOLD)` per frame, 각 phase 내에서 집계.

```
sat_ratio_APPROACH           # APPROACH frames 중 saturated 비율
sat_ratio_CONTACT            # CONTACT frames 중 동일
sat_ratio_INSERT             # INSERT frames 중 동일
sat_ratio_SEAT               # SEAT frames 중 동일
sat_ratio_aggregate          # 전체 frames 기준 (cross-validation용)
consecutive_sat_max_INSERT   # INSERT 내 연속 saturation 최대 길이 (frames)
consecutive_sat_max_SEAT     # SEAT 내 연속 saturation 최대 길이 (frames)
```

해석 기준:
- `sat_ratio_INSERT` 높음 → 삽입 중 max-step 사용. soft warning / quality signal.
- `sat_ratio_SEAT` 높음 → 성공 후 계속 밀고 있음. hard fail 후보.

### Command Quality (from frames — 신규)

command step은 위 fallback chain에서 구한 physical meters 값을 사용.

```
command_step_norm_mean   # mean(||applied_ee_delta||) in meters/step
command_step_norm_p95    # p95(동일)
jerk_mean                # mean(||delta[t] - delta[t-1]||)
jerk_p95                 # p95(동일)
```

`jerk`는 frame 간 command 변화량. timestamp가 있으면 frame interval로 normalize 가능하나,
초기 진단에서는 index-based (constant frame rate 가정) 허용.

### Cross-Validation (from frames vs eval JSON)

```
sat_ratio_recomputed     # trajectory frames에서 재계산한 aggregate saturation ratio

gate_match               # 정의:
                         #   recomputed_sat_fail = sat_ratio_recomputed >= MAX_NATIVE_ACTION_SAT_RATIO
                         #   recorded_sat_fail   = recorded_failure_reason == "NATIVE_ACTION_SATURATION"
                         #   gate_match          = (recomputed_sat_fail == recorded_sat_fail)
                         # RETARGETING_JUMP 등 다른 이유로 fail한 episode는 별도 표시
```

`gate_match == false`이면 gate logic 불일치 또는 evaluator 버전 차이를 나타냄.

### Gate Judgment (from frames — 신규)

세 gate를 병렬로 판정하고 모두 리포트한다. 하나만 쓰지 않는다.

```
gate_A_pass   # CONTACT >= 1 AND INSERT >= 20 AND SEAT >= 8
              # = current MVP-2 collection target (현실적, APPROACH 없어도 pass)

gate_B_pass   # APPROACH >= 10 AND CONTACT >= 1 AND INSERT >= 20 AND SEAT >= 8
              # = strict generalization target (환경 reset 구조상 현재 대부분 fail)

gate_C_pass   # INSERT >= 20
              # = weak insertion-signal sanity check

phase_order_diagnostic  # APPROACH→CONTACT→INSERT→SEAT 순서 위반 여부
                        # hard fail이 아닌 별도 diagnostic으로 기록
```

---

## Gate Interpretation Matrix

| old_live_gate | A | C | 의미 |
|---|---|---|---|
| pass | pass | pass | 현재 accepted. transition coverage 확인 필요 |
| fail | pass | pass | 삽입 신호 있음. saturation/ordering gate 문제 |
| fail | fail | pass | INSERT 있으나 CONTACT/SEAT threshold 미달 |
| fail | fail | fail | policy가 배울 삽입 동작 자체 부족 |
| any | B_fail_only_APPROACH | — | APPROACH 없음 → 환경 reset 구조 문제, 데이터 아님 |

---

## APPROACH Gap Note

현재 환경 reset이 peg를 hole 근처에 배치하기 때문에,
operator가 teleoperation을 시작할 때 이미 CONTACT/INSERT phase에 있는 경우가 많다.
Gate B fail이 APPROACH 부재만으로 발생한다면, 이는 curation 문제가 아니라
**task environment reset policy 문제**임을 진단 리포트가 명시해야 한다.

---

## Output Format

### Terminal

```
per-episode colored table:
  episode_id | frames | old_live_gate | A | B | C | sat_INSERT | sat_SEAT | jerk_p95 | failure_reason

aggregate summary:
  total episodes | A_pass | B_pass | C_pass
  gate_match failures (cross-validation warnings)
  APPROACH absent in N / total episodes
  phase_source_distribution across all episodes
```

### JSON

```
storage/mvp2_curation_diagnostic/mvp2_curation_diagnostic_report.json

schema:
  schema_version: "rdf_mvp2_curation_diagnostic_v0.1.0"
  generated_at: ISO timestamp
  config:
    INSERT_MIN_FRAMES: 20
    SEAT_MIN_FRAMES: 8
    APPROACH_MIN_FRAMES: 10
    ACTION_SAT_VALUE_THRESHOLD: 0.999
    MAX_NATIVE_ACTION_SAT_RATIO: 0.05
  episodes: [per-episode records]
  summary: {counts, gate distribution, cross-validation failures, phase_source_distribution}
```

---

## CLI Interface

```bash
uv run python scripts/run_mvp2_curation_diagnostic.py [options]

--trajectories-dir            PATH   (default: storage/trajectories)
--evaluations-dir             PATH   (default: storage/evaluations)
--output-dir                  PATH   (default: storage/mvp2_curation_diagnostic)
--insert-min-frames           INT    (default: 20)
--seat-min-frames             INT    (default: 8)
--approach-min-frames         INT    (default: 10)
--action-sat-value-threshold  FLOAT  (default: 0.999)  per-frame saturation check
--max-native-action-sat-ratio FLOAT  (default: 0.05)   ratio gate for cross-validation
--pretty                             (pretty-print JSON)
--episode-ids                 ID...  (optional: filter to specific episodes)
```

---

## Implementation Constraints

- input artifacts are read-only; script only writes to the output directory
- no SQLite / no API dependency
- trajectory JSON과 evaluation JSON은 `episode_id`로 join
- evaluation JSON이 없는 trajectory는 `recorded_*` 필드를 null로 처리하고 진단에서 제외하지 않음
- action_phase는 fallback chain을 순서대로 시도하고, 모두 없으면 `UNKNOWN`으로 처리
- `native_isaac_action`이 없는 frame은 saturation 계산에서 skip
- command step fallback chain을 모두 시도하고 모두 없는 frame은 command_step_norm / jerk 계산에서 skip

---

## Non-Goals

- curation 기준 변경 없음
- threshold 결정 없음 — 숫자를 보고 다음 세션에서 결정
- policy training 없음
- LeRobot / HDF5 export 변경 없음
- 새 gate를 live curation에 적용하지 않음

---

## Success Criteria

```
uv run python scripts/run_mvp2_curation_diagnostic.py --pretty

→ per-episode table이 terminal에 출력됨
→ storage/mvp2_curation_diagnostic/mvp2_curation_diagnostic_report.json 생성됨
→ gate_A, gate_B, gate_C per-episode 판정이 포함됨
→ phase-conditional saturation (INSERT / SEAT / CONTACT) 포함됨
→ phase_source_distribution이 aggregate summary에 포함됨
→ cross-validation gate_match 포함됨
→ APPROACH absent 카운트가 aggregate summary에 포함됨
→ curation/control 코드 변경 없음
```
