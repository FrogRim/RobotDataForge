# MVP-2 Policy Uplift Proof Execution Guide

Last updated: 2026-05-18

이 문서는 legacy `MVP-1C` policy-uplift 절차를 MVP-2 `learning-proven` proof로 옮긴 실행 가이드다.

현재 상태는 MVP-1 `learning-ready` Validated Dataset Pipeline Proof 완료다. 이 문서의 절차를 끝까지 실행해도, curated policy가 uncurated baseline보다 실제 held-out success rate에서 높지 않으면 MVP-2 `learning-proven`은 완료로 주장하지 않는다.

## Goal

같은 held-out insertion suite에서 다음을 증명한다.

```text
success_rate(policy trained on curated accepted data)
>
success_rate(policy trained on uncurated success-lifecycle data)
```

검증은 HUD 안에서 사람이 조작하는 장면이 아니라, 이미 수집된 HUD/Quest trajectory로 학습한 policy를 Isaac headless held-out scenarios에서 A/B rollout 평가하는 방식으로 한다. 이 proof는 MVP-2 전용이며 MVP-1 완료 조건이 아니다.

## Ownership Split

사용자가 직접 해야 하는 작업:

- Quest 3 / ALVR / SteamVR / Isaac live stack 실행
- proof-grade insertion trajectory 수집
- 조작 중 `P` recenter, `N/F/R` finalize 수행
- 수집 후 terminal output 또는 generated trajectory ids 확인

Codex/headless가 처리할 작업:

- diagnostics
- live export smoke
- curated/uncurated HDF5 bundle 생성
- trainer/evaluator 결과 adapter
- real policy eval ingest
- proof audit
- docs/Handoff 갱신

## Step 0. MVP-2 Ingest Preflight

목적: 현재 repo가 MVP-1 learning-ready 상태이며, policy uplift가 MVP-2 evidence로 분리되어 있는지 확인한다.

```bash
cd ~/robot-data-forge
uv run python scripts/run_mvp1c_final_hud_ingest_preflight.py \
  --refresh-headless-bundle \
  --pretty
```

통과 기준:

```text
ready_for_mvp2_policy_uplift_ingest=true
mvp2_learning_proven_claimed=false
current_stage=MVP-1
next_stage=MVP-2
missing_required_gates=[]
```

산출물:

```text
storage/mvp1c_final_hud_ingest_preflight/preflight_report.json
storage/mvp1c_final_hud_ingest_preflight/final_hud_ingest_runbook.md
```

중단 조건:

- `ready_for_mvp2_policy_uplift_ingest=false`
- MVP-1 learning-ready required gate가 빠져 있음
- headless bundle template이 invalid

## Step 0A. Forge Bounded Direct EE Target Control Smoke

목적: HMD를 쓰기 전에 현재 live teleop collection path인 `bounded_direct_ee_target` controller가 Forge PegInsert env에서 robot fingertip을 실제로 움직일 수 있는지 확인한다.

```bash
cd ~/robot-data-forge
/home/kangrim/IsaacLab/_isaac_sim/python.sh \
  scripts/check_forge_direct_action_response.py \
  --steps 20 \
  --pretty
```

통과 기준:

```text
control_mode="bounded_direct_ee_target"
passed=true
plus_x, plus_y, plus_z 또는 minus_z 중 하나 이상에서 fingertip_delta_norm > 0.001
```

이 단계가 실패하면 Quest/ALVR/SteamVR를 디버깅하지 않는다. 아직 robot controller 자체가 live handtracking 수집 UX에 맞는 bounded direct EEF target semantics로 움직인다는 증거가 없기 때문이다.

## Step 1. Fresh HUD/Quest Live Insertion Data Collection

목적: 실제 Quest/SteamVR/OpenXR/Isaac insertion trajectory를 수집한다.

권장 task:

```bash
RDF_DEBUG_ACTION_EVERY=20 \
RDF_ISAAC_TASK=Isaac-Forge-PegInsert-Direct-v0 \
RDF_TASK_TYPE=peg_in_hole \
RDF_MAX_FRAMES=900 \
RDF_WARMUP_VALID_FRAMES=10 \
RDF_ACTION_POS_GAIN=0.36 \
RDF_ACTION_ROT_GAIN=0.22 \
RDF_ACTION_SMOOTHING_ALPHA=0.40 \
RDF_TELEOP_CONTROL_MODE=auto \
RDF_DIRECT_EE_POS_GAIN=0.18 \
RDF_DIRECT_EE_ROT_GAIN=0.25 \
RDF_DIRECT_EE_MAX_STEP_M=0.06 \
RDF_DIRECT_EE_MAX_ROT_STEP_RAD=0.20 \
RDF_DIRECT_EE_SMOOTHING_ALPHA=0.95 \
RDF_DIRECT_EE_DEADZONE_M=0.0001 \
RDF_DIRECT_EE_WORKSPACE_RADIUS_M=0.35 \
RDF_DEBUG_MOTION_EVERY=20 \
RDF_VISUAL_DEBUG=1 \
RDF_VISUAL_DEBUG_EVERY=1 \
RDF_VISUAL_DEBUG_INPUT_SCALE=0.25 \
RDF_XR_ANCHOR_YAW_OFFSET_DEG=0 \
./scripts/run_live_rdf_smoke_test.sh --no-start-xr
```

`--no-start-xr`를 쓰는 경우:

- PC에서 ALVR Dashboard와 SteamVR을 이미 켜 둔다.
- Quest 3 안에서 ALVR 앱을 열고 PC 연결과 handtracking을 먼저 안정화한다.
- 스크립트가 `[RDF][READY]`를 출력하면 Quest/SteamVR 상태를 확인한 뒤 Enter를 누른다.

ALVR/SteamVR 자동 시작까지 스크립트에 맡기려면 명령 끝의 `--no-start-xr`를 제거한다. 단, Quest 3 안의 ALVR 앱 연결은 자동화되지 않으므로 항상 사용자가 직접 수행한다.

착용 후 순서:

1. ALVR Dashboard, SteamVR, Quest ALVR 연결 상태를 확인한다.
2. Isaac scene setup과 `[RDF] Terminal hotkeys active` 로그가 보일 때까지 기다린다.
   - Forge PegInsert task에서는 `[RDF] Teleop control mode: bounded_direct_ee_target`가 반드시 보여야 한다.
   - `action_debug`에는 `control=bounded_direct_ee_target`, `target_error_norm`, `command_step_norm`이 보여야 한다.
3. Isaac 창에서 Start XR 또는 Start AR를 누른다.
4. 손 tracking이 안정될 때까지 몇 초 대기한다.
5. HMD/Isaac 화면에서 RDF visual marker가 보이는지 확인한다.
   - green: 현재 robot fingertip
   - cyan: operator virtual target
   - yellow: 이번 step에서 Isaac이 적용할 rate-limited robot target
   - magenta: Forge fixed asset/hole reference
   - marker는 화면 overlay가 아니라 Isaac scene sphere여야 한다. 머리 시점에만 붙어서 움직이면 중단하고 visual debug 구현을 다시 확인한다.
6. terminal에서 `raw_xyz`, `filtered_xyz`, `step_xyz`, `eef_delta_norm`이 변하는지 확인한다.
7. 필요하면 terminal에 focus를 두고 `P` recenter를 한 번 누른다.
8. trajectory를 수행한다.
9. 수집을 끝낼 때는 Isaac을 먼저 닫지 말고 성공이면 `N`, 실패면 `F`, reset이면 `R`을 누른다.
10. `[RDF] Submitted episode ...` 로그를 확인한 뒤 Isaac을 종료한다.

수집량 기준:

- 최소: train/eval을 합쳐 usable insertion trajectory 10개 이상
- 권장: accepted train 30-50개 이상, held-out rollout policy당 50회 이상
- 초기 proof smoke: policy당 최소 10 rollout

품질 기준:

- `metadata.task_state` 존재
- non-zero frames
- `right_hand_tracked_rate`가 높음
- `workspace_alignment_v2`와 control filter metadata 존재
- Forge PegInsert live teleop에서는 `Teleop control mode: bounded_direct_ee_target`와 `control=bounded_direct_ee_target` 로그 존재
- 화면에서 cyan/yellow/magenta marker가 손 움직임에 반응하고 green marker/robot arm이 움직임
- explicit finalize 있음: `N`, `F`, 또는 `R`

시점이 30-60도 정도 돌아가 보이면 `P` recenter로 해결되지 않는다. `P`는 recording/action-filter 기준만 재설정하고 Isaac XR camera anchor는 돌리지 않는다. 이 경우 Isaac을 종료한 뒤 yaw offset을 바꿔 재실행한다.

```bash
RDF_XR_ANCHOR_YAW_OFFSET_DEG=45  ./scripts/run_live_rdf_smoke_test.sh --no-start-xr
RDF_XR_ANCHOR_YAW_OFFSET_DEG=-45 ./scripts/run_live_rdf_smoke_test.sh --no-start-xr
```

더 세밀하게 맞출 때는 `15`, `30`, `45`, `60`, `-15`, `-30`, `-45`, `-60` 순서로 좁힌다. 실행 로그에 `[RDF] XR anchor config: ... yaw_offset_deg=...`가 찍히면 해당 값이 적용된 것이다.

중단 조건:

- 손이 안 움직이거나 `raw_xyz`가 계속 0
- Forge PegInsert task인데 `Teleop control mode: bounded_direct_ee_target`가 보이지 않음
- `action_debug`에 `control=bounded_direct_ee_target`가 보이지 않음
- visual marker가 전혀 보이지 않음
- marker가 화면 중앙 조준점처럼 HMD 시점에만 붙어서 움직임
- cyan/yellow/magenta marker는 움직이는데 green marker/robot arm이 움직이지 않음
- `step_xyz`는 변하지만 `eef_delta_norm`이 계속 0
- Start XR 이후에도 trajectory frame이 0
- latest trajectory가 incomplete 0-frame뿐임
- task가 `Isaac-Forge-PegInsert-Direct-v0`가 아님

## Step 2. Post-Collection Diagnostics

목적: 새 data가 최소한 replay/export/trainer path에 들어갈 수 있는지 확인한다.

권장 순서:

1. live 수집 중 `N` 또는 `F`로 explicit finalize한다.
2. `[RDF] Submitted episode ...`를 확인한다.
3. Isaac Lab 창을 종료한다.
4. `run_live_rdf_smoke_test.sh`가 STEP 08 post API snapshot을 끝낼 때까지 기다린다.
5. 아래 진단 명령을 실행한다.

```bash
uv run python scripts/run_mvp0_offline_diagnostics.py
uv run python scripts/verify_latest_rdf_recording.py --pretty
uv run python scripts/analyze_teleop_calibration.py --latest --pretty
```

Isaac이 아직 실행 중일 때 별도 terminal에서 진단을 실행할 수는 있지만, latest episode가 `running` 또는 `incomplete`일 수 있으므로 proof 판단에는 사용하지 않는다.

0-frame incomplete episode가 latest로 잡히면, 실제 non-empty trajectory를 직접 지정한다.

```bash
uv run python scripts/verify_latest_rdf_recording.py \
  --trajectory storage/trajectories/<traj_id>.json \
  --pretty
uv run python scripts/analyze_teleop_calibration.py \
  storage/trajectories/<traj_id>.json \
  --pretty
```

통과 기준:

- `frame_count > 0`
- recording validator `passed=true`
- calibration analyzer issue count `0`
- task source가 `Isaac-Forge-PegInsert-Direct-v0` 또는 insertion task
- `metadata.task_state` 기반 live candidate가 proof audit의 MVP-1 dataset-pipeline evidence에 잡힘

중단 조건:

- trajectory has no frames
- raw/applied action unavailable
- calibration metadata unavailable
- `task_state` 없음

## Step 3. Refresh Live Export And MVP-1 Dataset Pipeline Proof

목적: 새 live trajectory가 HDF5 export와 trainer-loader dry run을 통과하는지 확인한다.

```bash
uv run python scripts/run_mvp1_live_export_smoke.py --clean --pretty
uv run python scripts/run_mvp1_proof_audit.py --pretty
```

통과 기준:

```text
trainer_loader_smoke_passed=true
current_stage=MVP-1
next_stage=MVP-2
missing_required_gates=[]
policy_uplift_required_for_mvp1=false
```

산출물:

```text
storage/mvp1_live_export/rdf_mvp1_live_export_smoke.hdf5
storage/mvp1_live_export/trainer_smoke_report.json
```

주의:

- 이 단계는 MVP-1 learning-ready evidence다.
- policy uplift를 증명하지 않는다.

## Step 3A. Recorded-Action Replay Gate

목적: accepted dataset material이 단순 evaluator success가 아니라 같은 action/replay contract에서 실제로 재생 가능한지 확인한다.

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/check_peg_insert_viability.py \
  --replay-scope raw_success \
  --pretty

uv run python scripts/apply_mvp1_replay_gate.py --pretty
```

산출물:

```text
storage/logs/peg_insert_viability_report.json
storage/mvp1_readiness/action_replay_contract.json
storage/mvp1_readiness/replay_gate_manifest.json
storage/mvp1_readiness/split_manifest_replay_verified.json
storage/mvp1_readiness/raw_replay_verified/
storage/mvp1_readiness/curated_replay_verified/
```

통과 기준:

- scripted oracle가 성공한다.
- `native_direct` recorded-action replay가 replay scope에서 통과한다.
- `accepted_replay_viability=true`
- `pool_ready_for_policy_ab=true`
- `pool_blockers=[]`

중단 조건:

- accepted trajectory가 replay contract에서 실패한다.
- replay-verified candidate pool에 train/held-out split을 만들 수 없다.
- live HMD trajectory에 recorded initial state 또는 그에 준하는 reset-state provenance가 없다.

주의:

- open-loop recorded-action replay는 같은 초기 상태에서만 의미가 있다.
- offline fixture는 `summary.action_replay_contract.initial_state.seed`로 이 조건을 표현한다.
- HMD live trajectory는 replay gate 통과 전에는 smoke/export evidence로만 쓰고, curated accepted dataset material로 승격하지 않는다.

## Step 4. Build Curated vs Uncurated Train/Eval Bundle

목적: 같은 raw/fresh dataset에서 replay-verified uncurated train view와 replay-verified curated train view를 분리한다.

```bash
uv run python scripts/run_mvp1c_headless_eval_bundle.py \
  --clean \
  --pretty
```

산출물:

```text
storage/mvp1c_headless_eval/baseline_uncurated/mvp1c_uncurated_success_lifecycle_train.hdf5
storage/mvp1c_headless_eval/candidate_curated/mvp1c_curated_accepted_train.hdf5
storage/mvp1c_headless_eval/heldout_suite_manifest.json
storage/mvp1c_headless_eval/policy_eval_input_template.json
```

통과 기준:

- baseline HDF5 inspection issues 없음
- candidate HDF5 inspection issues 없음
- `policy_eval_input_template.json`의 `evidence_tier=heldout_policy_eval`
- `real_heldout_policy_eval`은 HMD live accepted trajectory가 포함된 경우에만 사용
- `rollout_results`는 아직 빈 배열

중단 조건:

- baseline train set empty
- candidate train set empty
- held-out validation/test ids empty
- template에 smoke evidence tier가 들어감

## Step 5. Train Baseline And Candidate Policies

목적: 두 policy를 동일 조건에서 학습한다.

Baseline:

```text
train_hdf5 = storage/mvp1c_headless_eval/baseline_uncurated/mvp1c_uncurated_success_lifecycle_train.hdf5
dataset_view = uncurated_success_lifecycle
```

Candidate:

```text
train_hdf5 = storage/mvp1c_headless_eval/candidate_curated/mvp1c_curated_accepted_train.hdf5
dataset_view = curated_accepted
```

최소 요구:

- 같은 policy class
- 같은 random seed set 또는 seed 기록
- 같은 observation/action representation
- 같은 training budget
- 같은 held-out eval scenarios

권장 baseline:

- 초기 smoke: existing lightweight BC path
- proof-grade: ACT 계열 action chunking 또는 insertion에 맞춘 stronger BC trainer

중단 조건:

- baseline/candidate가 서로 다른 eval suite를 사용
- curated 쪽만 더 좋은 hyperparameter를 사용
- training failure가 한쪽에만 발생
- trainer가 rollout log를 남기지 않음

## Step 6. Headless Held-Out Policy A/B Rollout Evaluation

목적: 두 policy를 같은 held-out insertion scenario ids에서 평가한다.

최소 rollout count:

```text
min_rollouts_per_policy=10
```

주의: 이 값은 ingest script의 hard minimum이다. quick smoke는 사전 검증일 뿐이며, 최종 MVP-2 learning-proven proof는 seed/scenario 수를 늘린 held-out suite로 실행해야 한다.

권장 rollout count:

```text
rollouts_per_policy >= 50
```

rollout result CSV 형식:

```csv
rollout_id,scenario_id,seed,success,failure_reason,steps
baseline_0000,scenario_0000,7100,false,no_success_within_max_steps,150
baseline_0001,scenario_0001,7101,true,,84
```

candidate도 같은 scenario/seed set을 사용한다.

```csv
rollout_id,scenario_id,seed,success,failure_reason,steps
candidate_0000,scenario_0000,7100,true,,77
candidate_0001,scenario_0001,7101,true,,82
```

주의:

- HUD/HMD는 이 단계에 필요 없다.
- Isaac headless 평가가 기준이다.
- `success`는 terminal insertion success여야 하며, action prediction proxy가 아니다.

중단 조건:

- baseline과 candidate가 다른 scenario set에서 평가됨
- aggregate만 있고 scenario/seed 추적이 없음
- success 기준이 policy마다 다름
- rollout count가 너무 적음

## Step 7. Adapter, Real Eval Ingest, MVP-2 Proof Audit

목적: rollout 결과를 MVP-2 policy-uplift proof schema로 변환하고 audit를 통과하는지 확인한다.

adapter:

```bash
uv run python scripts/run_mvp1c_rollout_result_adapter.py \
  --template storage/mvp1c_headless_eval/policy_eval_input_template.json \
  --baseline-results <baseline_heldout_rollouts.csv-or-json> \
  --candidate-results <candidate_heldout_rollouts.csv-or-json> \
  --output storage/mvp1c_headless_eval/policy_eval_input.json \
  --policy-class <policy_class> \
  --trainer <trainer_name>
```

real eval ingest:

```bash
uv run python scripts/run_mvp1c_real_policy_eval.py \
  --input storage/mvp1c_headless_eval/policy_eval_input.json \
  --min-rollouts-per-policy 10 \
  --pretty
```

proof audit:

```bash
uv run python scripts/run_mvp1_proof_audit.py --pretty
```

MVP-2 learning-proven pass 기준:

```text
learning_results_measured=true
evidence_tier=heldout_policy_eval 또는 real_heldout_policy_eval
primary_metric=policy_success_rate
secondary_metric=rollout_success_rate
curated_vs_uncurated_uplift > 0
proof_eligible=true
proof audit current_stage=MVP-1
proof audit next_stage=MVP-2
learning_proven_policy_uplift_achieved=true
```

negative result 해석:

- 첫 A/B에서 candidate success rate가 baseline보다 낮거나 같으면 즉시 실패로 끝내지 않는다.
- negative result report를 작성하고, 정해진 범위 안에서 data/control/evaluator tuning을 1회 수행한다.
- 두 번째 반복에서도 uplift가 없으면 MVP-2 policy-uplift proof를 멈추고 root-cause/pivot decision으로 전환한다.
- 이 경우도 중요한 측정 결과이므로 숨기지 않는다.

## Final Evidence Artifacts

MVP-2 policy-uplift 시도 후 남아야 하는 파일:

```text
storage/mvp1c_headless_eval/policy_eval_input.json
storage/mvp1_readiness/policy_uplift_real_eval_report.json
storage/mvp1_readiness/curated_vs_uncurated_experiment_manifest.json
storage/mvp1_proof/proof_audit.json
```

report에서 확인할 필드:

```text
baseline_success_rate
candidate_success_rate
curated_vs_uncurated_uplift
confidence_interval_95
baseline_rollout_count
candidate_rollout_count
proof_eligible
```

## Minimal Command Checklist

```bash
cd ~/robot-data-forge

uv run python scripts/run_mvp1c_final_hud_ingest_preflight.py --refresh-headless-bundle --pretty

# User collects fresh HUD/Quest/Isaac insertion trajectories here.

uv run python scripts/run_mvp0_offline_diagnostics.py
uv run python scripts/run_mvp1_live_export_smoke.py --clean --pretty
uv run python scripts/run_mvp1c_headless_eval_bundle.py --clean --pretty

# Train/evaluate baseline and candidate policies, then provide rollout logs.

uv run python scripts/run_mvp1c_rollout_result_adapter.py \
  --template storage/mvp1c_headless_eval/policy_eval_input_template.json \
  --baseline-results <baseline_heldout_rollouts.csv-or-json> \
  --candidate-results <candidate_heldout_rollouts.csv-or-json> \
  --output storage/mvp1c_headless_eval/policy_eval_input.json \
  --policy-class <policy_class> \
  --trainer <trainer_name>

uv run python scripts/run_mvp1c_real_policy_eval.py \
  --input storage/mvp1c_headless_eval/policy_eval_input.json \
  --min-rollouts-per-policy 10 \
  --pretty

uv run python scripts/run_mvp1_proof_audit.py --pretty
```

## Do Not Claim Learning-Proven If

- rollout evidence is offline proxy or smoke-only
- `evidence_tier` is neither `heldout_policy_eval` nor `real_heldout_policy_eval`
- `real_heldout_policy_eval` is used without HMD live accepted trajectories
- `primary_metric` is not `policy_success_rate`
- `curated_vs_uncurated_uplift <= 0`
- rollout count is below the configured minimum
- held-out suite is not actually held-out
- baseline/candidate used different evaluation scenarios
- `learning_proven_policy_uplift_achieved=false`
