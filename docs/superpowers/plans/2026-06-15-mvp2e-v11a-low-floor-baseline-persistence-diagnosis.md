# MVP-2E v0.11a Low-Floor Baseline Persistence Diagnosis Plan

## 목표

`v0_11` actual Isaac calibration failure를 artifact-only로 진단하고, 다음
downstream slice를 결정한다. 새 Isaac runtime은 실행하지 않는다.

## 작업 순서

1. RED tests 추가
   - `v0_11` calibration artifact가 없으면 실패
   - paired outcome counts와 recovery/degradation seed가 계산됨
   - baseline floor persistence가 분류됨
   - CLI `--low-floor-baseline-diagnosis-only`가 held-out 미개봉 상태를 보존함

2. 진단 구현
   - constants: `v0_11a`, child output dir, schema version
   - `build_v11a_low_floor_baseline_persistence_diagnosis`
   - paired outcome table, policy delta report 작성
   - evidence manifest 갱신

3. 검증
   - focused pytest `-k "v11a"`
   - `compileall`
   - `ruff check`
   - 실제 artifact-only diagnosis command 실행

4. 루프 분기
   - 권고가 `v0_12_baseline_floor_suppression_comparator`이면 즉시 v0.12 spec/plan으로 진행
   - held-out은 열지 않는다

## 성공 기준

- v0.11a report가 `LOW_FLOOR_BASELINE_RUNTIME_FLOOR_PERSISTENCE`를 재현한다.
- `baseline=21/30`, `candidate=25/30`, `gap=0.133333333333`,
  `paired_outcome_counts={B1_C1:20,B1_C0:1,B0_C1:5,B0_C0:4}`를 기록한다.
- `mvp2_closed=false`, `policy_uplift_proven=false`,
  `fresh_heldout_34000_34049_accessed=false`.
