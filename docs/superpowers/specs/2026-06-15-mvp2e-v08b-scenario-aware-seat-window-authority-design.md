# MVP-2E v0.8b Scenario-Aware Seat-Window Authority 설계

## 목적

v0.8a는 fresh calibration `23000-23029`를 통과했지만 fresh held-out `24000-24049`에서
MVP-2 close minimum을 통과하지 못했다.

```text
baseline: 38/50 = 0.76
candidate: 45/50 = 0.90
curated_vs_uncurated_uplift: +0.14
required uplift: >= +0.20
mvp2_closed: false
```

v0.8b의 목적은 열린 held-out `24000-24049`를 다시 closure에 쓰지 않고, 그 결과를 진단 증거로만 사용하여
fresh calibration/held-out split에서 seat-window authority의 구조적 결함을 수리하는 것이다.

## v0.8a 진단 증거

근거 artifact:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_8a_fresh_seat_window_authority/
    calibration_presignal_gate_v0_8a.json
    heldout_closure_gate_v0_8a.json
    isaac_runtime_fresh_heldout_v0_8a/isaac_runtime_heldout_rollout_traces/
```

candidate 실패 5개는 모두 `ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED`이다.

```text
candidate_0002 held_out_24002: first_success=None, max_consecutive=0, max_depth=0.022869
candidate_0011 held_out_24011: first_success=None, max_consecutive=0, max_depth=0.000000
candidate_0015 held_out_24015: first_success=139, max_consecutive=9
candidate_0031 held_out_24031: first_success=140, max_consecutive=8
candidate_0033 held_out_24033: first_success=139, max_consecutive=9
```

하위 원인:

1. `latest_z_open_step=81` 고정 deadline은 일부 scenario에서 너무 늦다.
   - 3개 실패는 env-native success 영역에 진입했지만 horizon 전에 10-step window를 확보하지 못했다.
   - 1개 실패는 depth `0.022869`까지 내려갔지만 seat region에 도달하지 못했다.
2. v0.8a `seat_window_progress_authority_v0_8a`는 final XY authority 이후에 z만 강제한다.
   - 따라서 z가 강제로 열려도 `z_open_low_depth`용 XY center-maintenance가 재평가되지 않는다.
   - `candidate_0011`은 step 81에 z가 열렸지만 lateral이 `0.001388 -> 0.009319`로 밀려 z gate가 다시 닫혔다.
3. 실패는 success metric 변경 문제가 아니다.
   - env-native closure authority와 10-step stable window는 유지한다.

## Fresh split

v0.8b는 closure에 `21000-21049` 또는 `24000-24049`를 재사용하지 않는다.

Fresh ranges:

- calibration: `25000-25029`
- held_out: `26000-26049`

다음 range는 burned 또는 non-closure diagnostic으로만 취급한다.

- `21000-21049`: v0.7p opened held-out
- `24000-24049`: v0.8a opened held-out

## Authority 변경

v0.8b는 v0.8a의 child slice다. trainer, policy class, selected adapter, feature schema,
env-native success authority는 변경하지 않는다.

새 authority id:

```text
scenario_aware_seat_window_authority_v0_8b
```

필수 변경:

1. Seat-window z forcing을 final XY authority와 결합한다.
   - v0.8a처럼 XY 이후에 z만 바꾸는 방식 금지.
   - z forcing이 필요한 step에서는 XY authority가 `z_open_low_depth` 상태를 볼 수 있어야 한다.
   - 구현은 다음 둘 중 하나여야 한다.
     - z forcing을 final XY authority 전에 prospective action에 반영한다.
     - 또는 z forcing 후 동일 final XY authority를 한 번 재평가한다.
2. z-open deadline은 fixed max만 쓰지 않고 scenario-aware budget으로 유도한다.
   - 입력은 train-generation success traces와 current runtime state only.
   - opened held-out result로 threshold를 fit하지 않는다.
   - 최소 required fields:
     - `latest_z_open_step_train_max`
     - `seat_window_required_steps`
     - `terminal_guard_steps`
     - `descent_latency_steps_p95`
     - `scenario_aware_deadline_formula`
     - `z_open_centering_lateral_m`
     - `z_progress_action`
3. v0.8a diagnostic held-out는 config에 기록하되 proof authority가 아니다.
   - `source_diagnostic_heldout_24000_24049_accessed=true`
   - `heldout_24000_24049_used_for_parameter_derivation=false`
4. Candidate와 baseline은 동일 authority config를 사용한다.

## Gate order

1. v0.8a held-out closure gate를 읽어 v0.8b가 필요한지 확인한다.
2. train-generation success traces only로 v0.8b authority config를 만든다.
3. v0.8b candidate/baseline policy artifacts를 peer-fair하게 생성한다.
4. offline authority regression gate를 먼저 실행한다.
   - z forcing step에서 XY authority가 `z_open_low_depth`를 인식해야 한다.
   - v0.8a ordering regression을 재현하는 test가 실패해야 하고 v0.8b는 통과해야 한다.
5. fresh calibration `25000-25029`를 실행한다.
6. calibration이 통과하면 fresh held-out `26000-26049`를 실행한다.
7. MVP-2 Closed는 fresh held-out 결과로만 판단한다.

## Close criteria

MVP-2 Closed 조건은 변경하지 않는다.

- actual rollouts per policy >= 20
- candidate success rate > baseline success rate
- curated_vs_uncurated_uplift >= 0.20
- train-generation gate remains passed
- calibration/fairness/leakage guards pass
- env-native success + 10 consecutive window remains primary closure authority

## Fail-closed rules

- `24000-24049`가 closure seed로 다시 열리면 fail.
- `21000-21049`가 closure seed로 다시 열리면 fail.
- v0.8b authority config가 candidate/baseline 사이에서 다르면 fail.
- z forcing이 final XY authority 후에만 적용되어 XY가 z-open 상태를 모르면 fail.
- fresh calibration 실패 시 held-out `26000-26049`를 열지 않는다.
- held-out uplift가 `+0.20` 미만이면 `mvp2_closed=false`로 기록하고 다음 진단 slice로 넘어간다.

## Non-claims

v0.8b는 다음을 주장하지 않는다.

- real robot success
- deployable real-world policy
- visual policy performance
- HMD/OpenXR readiness
- universal robot support

이 slice는 Isaac evaluator-domain privileged task-state learning proof이다.
