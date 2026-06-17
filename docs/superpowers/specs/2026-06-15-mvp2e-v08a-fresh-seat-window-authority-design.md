# MVP-2E v0.8a Fresh Seat-Window Authority 설계

## 목적

v0.7p는 실제 Isaac held-out `21000-21049`에서 baseline 34/50, candidate 41/50을 기록했다.
candidate가 baseline보다 높았지만 `curated_vs_uncurated_uplift >= 0.20`에 필요한 44/50에 3개 부족했으므로
MVP-2는 아직 Closed가 아니다. v0.7q는 이 실패를 artifact-only로 분류했고, candidate 실패 9개 중
3개가 `NEAR_SEAT_HOLD_WINDOW_SHORT`임을 확인했다.

v0.8a의 목적은 열린 held-out 결과를 재사용하지 않고, fresh calibration/held-out split에서
seat-window 확보 authority가 실제 uplift를 만드는지 검증하는 것이다.

## Source-of-truth evidence

- `v0_7p_heldout_closure/heldout_closure_gate_v0_7p.json`
  - baseline success: 34/50
  - candidate success: 41/50
  - required candidate success for close minimum: 44/50
  - shortfall: 3
- `v0_7q_heldout_shortfall_diagnosis/heldout_shortfall_diagnosis_v0_7q.json`
  - proof authority: false
  - same held-out reuse allowed: false
  - fresh slice required: true
  - recommended downstream slice: `v0_8a_fresh_seat_window_authority_slice`
- train-generation success traces only:
  - successful expert `first_z` max: 81 step
  - successful expert `first_env_native_success` max: 138 step
  - env-native stable window required: 10 steps

## Fresh split

v0.8a must not use `21000-21049` for closure again.

Fresh ranges:

- calibration: `23000-23029`
- held_out: `24000-24049`

The ranges must be recorded in a v0.8a manifest and checked for disjointness against:

- prior held-out: `3000-3019`, `6000-6019`, `9000-9019`, `12000-12019`, `15000-15019`,
  `18000-18019`, `21000-21049`
- v0.5 train/probe: `16000-16159`, `16023`, `16042`, `16096`
- v0.6 train/calibration/held-out: `19000-19159`, `20000-20029`, `21000-21049`

## Authority change

v0.8a keeps the v0.7o policy lineage, trainer, selected adapter, feature schema, and success metric.
It adds one shared frozen runtime authority:

`seat_window_progress_authority_v0_8a`

The authority may force downward z progress only when all of the following are true:

- current step is at or after the train-derived latest successful z-open step
- the policy has not reached env-native success
- lateral is already inside the frozen z-open centering band
- insertion depth is below the env-native seating region
- action happens before held-out closure and with the same config for baseline and candidate

Parameter derivation must use train-generation success traces only. It must not use `21000-21049` thresholds.

Required derived fields:

- `train_success_trace_count`
- `train_success_first_z_step_max`
- `train_success_first_env_success_step_max`
- `seat_window_required_steps`
- `latest_z_open_step`
- `z_progress_action`
- `derivation_source_sha256`

## Gate order

1. Build v0.8a seat-window authority config from train-generation success traces.
2. Build candidate/baseline v0.8a policy artifacts from v0.7o artifacts with identical authority config.
3. Run fresh calibration `23000-23029`.
4. If calibration does not pass, stop fail-closed and do not open `24000-24049`.
5. If calibration passes, run fresh held-out `24000-24049`.
6. MVP-2 Closed only if:
   - actual rollouts per policy >= 20
   - candidate success rate > baseline success rate
   - curated_vs_uncurated_uplift >= 0.20
   - train-generation gate remains passed
   - calibration selector/fairness guards remain passed
   - held-out leakage guard passes for the fresh split

## Non-claims

v0.8a does not claim:

- real robot success
- visual policy performance
- HMD/OpenXR readiness
- universal robot support
- deployable real-world policy

It remains an Isaac evaluator-domain privileged task-state proof.

## Fail-closed rules

- If v0.7q post-heldout marker is missing or allows same held-out reuse, stop.
- If v0.8a fresh ranges overlap prior opened held-out, stop.
- If authority derivation reads `21000-21049`, stop.
- If candidate/baseline authority config differs, stop.
- If fresh calibration fails, stop before fresh held-out.
- If fresh held-out uplift is below 0.20, emit a new diagnosis slice and keep `mvp2_closed=false`.
