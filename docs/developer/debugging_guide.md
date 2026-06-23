# 디버깅 가이드

Robot Data Forge를 혼자 디버깅할 때는 아래 순서로 확인한다.

---

## 2026-05-18 Proof Framing

MVP-1은 이제 `learning-ready` Validated Dataset Pipeline Proof다. `run_mvp1_proof_audit.py`가 raw XR trajectory, task state/outcome, data quality, operator/evaluator separation, replay/action gate, curation manifest, HDF5 export, trainer loader smoke, dataset card를 확인하면 MVP-1은 통과한다.

Curated-vs-uncurated policy uplift는 MVP-2 `learning-proven` proof다. 이 문서의 오래된 `MVP-1C` 문구는 legacy policy-uplift 절차로 해석하고, MVP-1 blocker로 해석하지 않는다.

---

## 1. 환경 확인

Repository root로 이동한다.

```bash
cd ~/robot-data-forge
```

의존성을 설치한다.

```bash
uv sync --group dev
```

Backend test를 실행한다.

```bash
uv run pytest -q apps/api/tests
```

Compile check를 실행한다.

```bash
uv run python -m compileall -q apps/api/app apps/api/tests scripts
```

## External Robot Data Ingest / Evaluation v0 확인

현재 canonical external ingest package는 실제 external source row가 없어서
`external_ingest_contract_ready` 상태다. `external_data_evaluated`를 claim하려면
외부에서 제공되거나 공개 source에 refetch-bind된 `metadata.json`,
`accepted_command_state.jsonl`, `rejected_command_state.jsonl`을
`docs/proof/.../data/source/`에 포함할 수 있어야 한다.

현재 package 검증:

```bash
cd ~/robot-data-forge
python3 scripts/verify_external_robot_data_ingest_package.py \
  docs/proof/external_robot_data_ingest_eval_v0_proof_package/package_manifest.json
```

예상 결과:

```text
VERDICT: VERIFIED
status=external_ingest_contract_ready
external_source_included=false
```

새 external JSONL drop을 임시로 검사할 때:

```bash
uv run python scripts/run_external_robot_data_ingest_eval_v0.py \
  --external-source-dir /path/to/external_drop \
  --output-dir /tmp/rdf_external_ingest_eval_v0 \
  --package-status external_data_evaluated \
  --clean \
  --pretty
```

주의:

```text
- /path/to/external_drop이 repo fixture, docs/proof, storage, .omx 아래면 external_data_evaluated는 fail한다.
- raw metadata는 adapter-only field를 갖출 필요가 없다. staging metadata는 RDF가 결정적으로 파생한다.
- external_source_included=false package는 external robot data를 평가했다는 claim이 아니다.
- 현재 verifier는 semantic parity artifact 검증이 추가되기 전까지 external_data_evaluated package를 fail-closed한다.
- verifier는 package 내부 row/hash 일관성을 재계산하지만, self-asserted metadata의 물리적 origin을 암호학적으로 증명하지 않는다.
```

---

## 2. Backend API 스모크 테스트

현재 머신에 Docker/PostgreSQL이 없으면 SQLite local API mode를 사용한다. Quest/OpenXR/Isaac live smoke test는 이 모드로 충분하다.

```bash
cd ~/robot-data-forge
./scripts/run_local_api_sqlite.sh
```

다른 terminal에서 확인:

```bash
curl -sS http://localhost:8000/health
curl -sS http://localhost:8000/api/episodes
curl -sS http://localhost:8000/api/admin/kpis
```

`/health`만 200이고 `/api/episodes`, `/api/admin/kpis`가 `Internal Server Error`면 DB가 떠 있지 않은 상태일 가능성이 높다. 이 경우 현재 API 서버를 `Ctrl+C`로 종료하고 `./scripts/run_local_api_sqlite.sh`로 다시 시작한다.

PostgreSQL을 사용할 수 있는 환경에서는 아래 경로를 사용한다.

PostgreSQL을 시작한다.

```bash
RDF_POSTGRES_PASSWORD=local-dev-only docker compose up -d postgres
```

Migration을 실행한다.

```bash
cd ~/robot-data-forge/apps/api
PYTHONPATH=. uv run --project ../.. alembic upgrade head
```

API 서버를 시작한다.

```bash
cd ~/robot-data-forge
uv run uvicorn app.main:app --app-dir apps/api --reload
```

Health endpoint를 확인한다.

```bash
curl -sS http://localhost:8000/health
```

예상 결과:

```json
{"status":"ok"}
```

---

## 3. One-shot Live Smoke Test

터미널 여러 개를 오가며 API, Isaac 실행, curl 확인을 따로 수행하면 실수가 생기기 쉽다. 실제 Quest/OpenXR/Isaac recorder 제출 검증은 아래 스크립트를 우선 사용한다.

```bash
cd ~/robot-data-forge
./scripts/run_live_rdf_smoke_test.sh
```

스크립트가 수행하는 단계:

```text
1. uv/curl/python3, Isaac runner, SteamVR OpenXR runtime path 확인
2. 기존 API가 정상인지 확인
3. 기존 8000번 API가 없거나 DB endpoint가 실패하면 다른 포트에 local SQLite API 자동 시작
4. 실행 전 `/api/episodes`, `/api/admin/kpis` snapshot 저장
5. ALVR Dashboard 자동 시작
6. SteamVR `vrmonitor.sh` 자동 시작 및 `vrserver` 확인
7. Quest 3에서 ALVR 앱 연결 확인 후 Isaac handtracking recorder 실행
8. Isaac 종료 후 `/api/episodes`, `/api/admin/kpis` 재확인
9. 새 episode 증가 여부 확인
10. latest trajectory/evaluation을 불러와 frame, source metadata, score 확인
```

실행 중 메시지는 다음 형식으로 출력된다.

```text
[RDF][STEP 01] Preflight
[RDF][STEP 02] API 선택
[RDF][STEP 03] 실행 전 API snapshot
...
```

중요한 사용 방식:

```text
ALVR Dashboard와 SteamVR은 스크립트가 자동 시작한다.
Quest 3 안에서 ALVR 앱을 열고 PC에 연결하는 동작은 사람이 해야 한다.
스크립트가 `[RDF][READY]`를 출력하면 Quest 화면에서 SteamVR/handtracking이 정상인지 확인한 뒤 Enter를 누른다.
Isaac이 열리면 손을 몇 초 움직이고 Isaac 창을 닫는다.
Isaac이 닫히면 스크립트가 자동으로 API 제출 결과를 확인한다.
```

옵션:

```bash
# Isaac 실행 없이 API/script 경계만 확인
./scripts/run_live_rdf_smoke_test.sh --skip-isaac

# 스크립트가 시작한 local API를 종료하지 않고 유지
./scripts/run_live_rdf_smoke_test.sh --keep-api

# 준비 확인 Enter prompt 생략
./scripts/run_live_rdf_smoke_test.sh --no-prompt

# ALVR/SteamVR 자동 시작 생략
./scripts/run_live_rdf_smoke_test.sh --no-start-xr
```

환경 변수:

```bash
RDF_MAX_FRAMES=300 ./scripts/run_live_rdf_smoke_test.sh
RDF_WARMUP_VALID_FRAMES=10 ./scripts/run_live_rdf_smoke_test.sh
RDF_DISABLE_AUTO_CALIBRATE=0 ./scripts/run_live_rdf_smoke_test.sh
RDF_ACTION_FILTER=1 ./scripts/run_live_rdf_smoke_test.sh
RDF_ACTION_POS_GAIN=0.40 ./scripts/run_live_rdf_smoke_test.sh
RDF_ACTION_ROT_GAIN=0.35 ./scripts/run_live_rdf_smoke_test.sh
RDF_ACTION_POS_AXIS_MAP=x,z,y ./scripts/run_live_rdf_smoke_test.sh
RDF_CONTRIBUTOR_ID=user_001 ./scripts/run_live_rdf_smoke_test.sh
API_BASE=http://127.0.0.1:8001 ./scripts/run_live_rdf_smoke_test.sh
```

`RDF_WARMUP_VALID_FRAMES`는 recorder가 trajectory frame 저장을 시작하기 전에 요구하는 연속 valid handtracking frame 수다. 기본값은 `10`이다. Quest 3 연결 직후 초반 handtracking false frame이 많이 저장되면 `30`까지 올려서 다시 테스트한다.

`RDF_DISABLE_AUTO_CALIBRATE=1`을 지정하면 자동 calibration을 만들지 않는다. 기본값은 `0`이다. 현재 HMD primary flow에서는 첫 valid hand frame만으로 recenter하지 않고, `RDF_RECENTER_MODE=robot_start_box`에서 robot이 visible start box 안에 들어간 뒤 `workspace_alignment_v2` calibration metadata를 저장한다. 기존 reader 호환을 위해 `translation_offset`도 계속 저장한다.

`RDF_ACTION_FILTER=1`은 Isaac에 적용하기 전 teleop action을 완만하게 보정한다. 기본값은 다음과 같다.

```text
RDF_ACTION_POS_GAIN=0.40
RDF_ACTION_ROT_GAIN=0.35
RDF_ACTION_POS_DEADZONE=0.0015
RDF_ACTION_ROT_DEADZONE=0.01
RDF_ACTION_SMOOTHING_ALPHA=0.45
RDF_ACTION_POS_AXIS_MAP=x,z,y
RDF_ACTION_ROT_AXIS_MAP=x,y,z
RDF_DEBUG_ACTION_EVERY=0
RDF_DEBUG_MOTION_EVERY=0
RDF_TELEOP_CONTROL_MODE=auto
RDF_OPERATOR_FOLLOW_PRESET=safe
RDF_OPERATOR_FOLLOW_WORKSPACE_GAIN=-1
RDF_OPERATOR_FOLLOW_MAX_STEP_M=-1
RDF_OPERATOR_FOLLOW_SMOOTHING_ALPHA=-1
RDF_OPERATOR_FOLLOW_DEADZONE_M=-1
RDF_OPERATOR_FOLLOW_WORKSPACE_RADIUS_M=-1
```

Quest/OpenXR handtracking은 Y-up이고 Isaac robot workspace는 Z-up이다. 그래서 live 기본값은 `RDF_ACTION_POS_AXIS_MAP=x,z,y`다. 이 값이면 손을 아래로 내릴 때 robot `z`도 내려간다. 좌우나 전후 방향이 맞지 않으면 axis map을 바꿔서 짧게 테스트한다.

```bash
RDF_ACTION_POS_AXIS_MAP=x,-z,y RDF_RECORD=1 RDF_MAX_FRAMES=300 ~/run_isaac_handtracking.sh
RDF_ACTION_POS_AXIS_MAP=x,z,-y RDF_RECORD=1 RDF_MAX_FRAMES=300 ~/run_isaac_handtracking.sh
```

작은 조작이 너무 튀면 gain을 낮춘다.

```bash
RDF_ACTION_POS_GAIN=0.30 RDF_ACTION_ROT_GAIN=0.20 RDF_RECORD=1 RDF_MAX_FRAMES=300 ~/run_isaac_handtracking.sh
```

손을 움직여도 로봇이 안 움직이는지, 아니면 손 입력은 들어오는데 적용만 작게 되는지 가르려면 live action debug를 켠다.

```bash
RDF_DEBUG_ACTION_EVERY=20 RDF_RECORD=1 RDF_MAX_FRAMES=300 ~/run_isaac_handtracking.sh
```

터미널에 다음 형식의 로그가 주기적으로 찍힌다.

```text
[RDF] action_debug loop=120 active=True raw_norm=... applied_norm=... raw_xyz=[...] filtered_xyz=[...] step_xyz=[...] adapter=...
[RDF] motion_debug loop=120 eef_before=[...] eef_after=[...] eef_delta_norm=... env_action_xyz=[...]
```

- `raw_xyz`가 계속 `[0,0,0]`이면 OpenXR hand pose가 teleop action으로 변환되지 않는 상태다.
- `raw_xyz`는 움직이는데 `filtered_xyz`가 너무 작으면 `RDF_ACTION_*` filter/gain/deadzone 문제다.
- `filtered_xyz`는 움직이는데 `step_xyz`가 이상하면 Forge action adapter 문제다.
- `step_xyz`는 움직이는데 `eef_delta_norm`이 거의 0이면 Isaac task controller/action dimension/clip 문제다.

Isaac/HMD 화면에는 기본적으로 RDF visual debug marker가 USD scene sphere로 표시된다.

```text
green   = 현재 robot fingertip 위치
cyan    = handtracking delta가 요청한 즉시 target
yellow  = Isaac이 이번 step에서 적용할 clipped robot target
magenta = Forge fixed asset/hole 기준 asset-relative target
```

판정 기준:

- cyan/yellow/magenta marker가 손 움직임에 따라 움직이지 않으면 input/filter/adapter 문제다.
- marker는 움직이는데 green marker와 robot arm이 움직이지 않으면 Isaac controller/action application 문제다.
- marker와 robot은 움직이는데 HMD에서 방향이 틀어져 보이면 XR anchor yaw 문제다.

`RDF_VISUAL_DEBUG_INPUT_SCALE`은 cyan marker만 크게 보이도록 하는 표시 전용 scale이다. control action이나 저장 데이터는 바꾸지 않는다. 손 입력 marker가 너무 작아 green에 묻히면 `0.5` 또는 `1.0`으로 키워서 다시 본다.

`Isaac-Forge-PegInsert-Direct-v0`는 일반 ManagerBased IK task와 action 의미가 다르다. Forge native action은 current pose delta가 아니라 fixed asset/hole 기준 normalized target으로 해석된다. 이는 policy benchmark에는 맞지만 HMD live teleop 수집 UX에는 부적합하다.

따라서 live handtracking에서는 기본적으로 `RDF_TELEOP_CONTROL_MODE=auto`를 사용한다. Forge PegInsert에서는 이 값이 `bounded_direct_ee_target`으로 해석되어, Forge scene/task_state는 유지하되 controller는 손 움직임을 bounded desired EEF target으로 바꾸는 direct target servo로 동작한다. `operator_follow`는 fallback/debug/legacy mode다.

```text
handtracking delta
-> RDF action filter
-> bounded_direct_ee_target desired EEF target
-> workspace/max-step/smoothing-limited fingertip target command
-> robot arm visible motion
```

중요한 로그:

```text
[RDF] Teleop control mode: bounded_direct_ee_target
[RDF] Bounded direct EE config: position_gain=... max_step_m=...
[RDF] action_debug ... control=bounded_direct_ee_target target_error_norm=... command_step_norm=...
```

이 로그가 없고 `adapter=forge_asset_relative_delta_adapter`만 보이면 아직 native Forge path라서 사람이 보기에는 로봇팔이 손을 따라오지 않는 것이 정상에 가깝다. `operator_follow`와 `cartesian_delta`는 fallback/debug path이고, MVP-1 live collection의 기본 통과 기준은 `bounded_direct_ee_target`이다.

### HMD six-direction motion mapping debug

손 움직임과 robot EEF 움직임이 맞지 않는다고 느껴지면 Gate A 수집을 멈추고 짧은 six-direction debug run을 먼저 실행한다. 목표는 성공 삽입이 아니라 raw input -> filtered input -> desired target -> applied command -> actual EEF movement를 축별로 증명하는 것이다.

실행 중 operator 동작:

```text
1. recenter start box 안으로 robot을 넣고 RECENTER OK까지 기다린다.
2. 손을 1초 멈춘다.
3. 오른쪽, 왼쪽, 앞으로, 뒤로, 위로, 아래로를 각각 1-2초씩 천천히 움직인다.
4. 마지막에 손을 다시 1초 멈춘다.
```

Debug command:

```bash
cd ~/robot-data-forge
RDF_ISAAC_TASK=Isaac-Forge-PegInsert-Direct-v0 \
RDF_TASK_TYPE=peg_in_hole \
RDF_MAX_FRAMES=240 \
RDF_WARMUP_VALID_FRAMES=10 \
RDF_ACTION_POS_AXIS_MAP=x,y,z \
RDF_ACTION_POS_YAW_OFFSET_DEG=0 \
RDF_ACTION_POS_GAIN=0.40 \
RDF_ACTION_ROT_GAIN=0.35 \
RDF_TELEOP_CONTROL_MODE=bounded_direct_ee_target \
RDF_DIRECT_EE_POS_GAIN=0.18 \
RDF_DIRECT_EE_ROT_GAIN=0.25 \
RDF_DIRECT_EE_MAX_STEP_M=0.04 \
RDF_DIRECT_EE_MAX_ROT_STEP_RAD=0.12 \
RDF_DIRECT_EE_SMOOTHING_ALPHA=0.50 \
RDF_DIRECT_EE_DEADZONE_M=0.003 \
RDF_DIRECT_EE_WORKSPACE_RADIUS_M=0.35 \
RDF_RECENTER_MODE=robot_start_box \
RDF_RECENTER_BOX_CENTER_SOURCE=hole_target_approach \
RDF_RECENTER_BOX_APPROACH_OFFSET=0,0,0.08 \
RDF_RECENTER_BOX_RANDOM_OFFSET=0,0,0 \
RDF_RECENTER_BOX_HALF_EXTENTS=0.07,0.07,0.07 \
RDF_RECENTER_BOX_VISUAL=0 \
RDF_BLOCK_TELEOP_UNTIL_RECENTER=1 \
RDF_RECENTER_SETUP_CONTROL=1 \
RDF_VISUAL_DEBUG=1 \
RDF_VISUAL_DEBUG_EVERY=1 \
RDF_VISUAL_DEBUG_SIZE=30 \
RDF_VISUAL_DEBUG_INPUT_SCALE=0.35 \
RDF_DEBUG_ACTION_EVERY=10 \
RDF_DEBUG_MOTION_EVERY=10 \
RDF_TASK_GUIDANCE=1 \
RDF_TERMINAL_HOTKEYS=0 \
RDF_AUTO_SUCCESS_FINALIZE=0 \
RDF_EXIT_AFTER_FINALIZE=0 \
./scripts/run_live_rdf_smoke_test.sh --no-start-xr
```

Run 직후 per-axis mapping report를 저장한다.

```bash
uv run python scripts/analyze_hmd_motion_mapping.py \
  --latest \
  --pretty \
  --output storage/hmd_motion_mapping/latest_mapping_report.json
```

판정 기준:

```text
H1 PASS: raw wrist/input delta가 six directions에서 기대 축과 부호를 가진다.
H2 PASS: trajectory config의 position_axis_map이 실행 command와 같다.
H4 PASS: 손을 멈춘 구간에서 command_nonzero_ratio가 0에 가깝다.
H6 PASS: workspace_clamped_ratio가 debug run에서 0에 가깝다.
H7 PASS: command_to_next_eef_delta sign agreement가 축별로 높다.
H8 PASS: HMD/operator camera frame, robot/world frame, task frame이 기록되어 perceived direction mismatch를 camera geometry로 설명할 수 있다.
H5 UNKNOWN/WARN: intentional motion sample 수가 부족하거나 deadzone보다 작은 손 움직임만 기록됐다.
H11 PASS: deadzone boundary에서 desired target이 hand movement보다 훨씬 크게 점프하지 않는다.
H12 PASS: raw right-wrist pose가 configured XR anchor position으로 collapse되는 fallback frame이 없다.
H13 PASS: valid로 표시된 연속 wrist pose 사이에 10cm 이상 spike가 반복되지 않는다.
H14 PASS: stable control segment 안에서 `desired_ee_target - hand_delta_m` residual이 cm 단위로 누적 drift하지 않는다.
H15 PASS: 하나의 recorded trajectory 안에서 EEF/object/peg/hole target이 동시에 큰 폭으로 순간 이동하지 않는다.
```

`H11 WARN`이면 deadzone 내부에서는 drift가 멈춰도 deadzone을 벗어나는 첫 nonzero sample에서
오래된 anchor 기준 `target=anchor+hand_delta`가 복원되고 있을 가능성이 높다. 이 경우
bounded direct-EE controller는 deadzone branch에서 `target=current_eef`, `previous_step=0`뿐 아니라
`anchor=current_eef`로 rebase되어야 한다.

`H12 WARN`이면 OpenXR/Isaac handtracking stream이 실제 hand pose 대신 configured XR anchor pose
(`RDF_XR_ANCHOR_POS`, 기본 `-0.1,-0.5,-1.05`)를 right wrist로 내보낸 frame이 기록된 것이다. 이 pose는
손 위치가 아니라 XR stage anchor fallback이므로 handtracking valid로 취급하면 안 된다. Runtime recorder와
live controller는 해당 frame을 invalid tracking으로 표시하고, robot control은 fake target을 따라가지 말고
held/frozen 상태를 유지해야 한다.

`H13 WARN`이면 OpenXR stream이 `right_hand_tracked=true`, `xr_frame_valid=true`인 상태에서도 raw wrist pose가
10cm 이상 순간 이동한 것이다. 이 경우 axis map/gain을 바꾸기 전에 raw-wrist gate의
`raw_wrist_gate_state`, `raw_wrist_gate_reason`, `raw_wrist_jump_m` 로그를 먼저 확인한다.
신규 raw-wrist debounce/reacquire 정책이 적용된 run에서는 단일 spike가 `raw_wrist_spike_reacquire_pending`
으로 held 처리되고, stable 후보가 `raw_wrist_reacquire_required_frames`만큼 유지될 때만
`raw_wrist_spike_reacquired`로 rebase된다. 따라서 다음 실증 run에서 H13을 볼 때는
`raw_wrist_jump_rebase` 반복 여부보다 `raw_wrist_spike_reacquire_pending`,
`raw_wrist_spike_reacquired`, `raw_wrist_reacquire_valid_count` 분포를 우선 확인한다.

`H14 WARN`이면 사용자의 "처음엔 맞다가 점점 position 계산이 누적 drift한다" 가설을 지지한다.
이 지표는 stable segment에서 `desired_ee_target_xyz - hand_delta_m`이 거의 상수로 유지되는지 본다.
정상 raw-wrist/direct-EE controller는 `target = anchor + current_absolute_hand_offset`이어야 하며,
`target += current_hand_offset`처럼 누적하면 H14 residual이 커진다.

`H15 WARN`이면 controller target 계산이 아니라 simulator/task-state boundary를 먼저 의심한다.
특히 같은 frame에서 EEF, held object/peg, hole 또는 hole target이 같이 점프하면 hidden env reset,
task-state teleport, 또는 recorder가 reset boundary를 episode 안에 섞어 저장했을 가능성이 높다.
이 frame은 학습 trajectory boundary로 분리하거나 reset evidence를 별도로 기록해야 한다.
신규 recorder metadata가 있는 run에서는 해당 frame의 `metadata.sim_step_boundary.reset_boundary`,
`terminated`, `truncated`, `done`, `reset_boundary_reason`, `info_keys`를 먼저 확인한다.
`sim_step_boundary.reset_boundary=true`이면 IsaacLab auto-reset/done boundary 가능성이 높고,
`false`인데 static task target이 순간 이동했다면 recorder가 아직 잡지 못한 task-state teleport 또는
다른 reset path를 의심한다.

2026-05-26 live observation: `RDF_ACTION_POS_YAW_OFFSET_DEG=90` caused an axis swap in HMD -- hand up/down moved sideways and hand sideways moved up/down. Do not continue the yaw-offset branch until a new trajectory proves otherwise. The next diagnostic uses identity position mapping and no yaw offset:

```bash
RDF_ACTION_POS_AXIS_MAP=x,y,z \
RDF_ACTION_POS_YAW_OFFSET_DEG=0 \
RDF_RECENTER_BOX_VISUAL=0 \
./scripts/run_live_rdf_smoke_test.sh --no-start-xr
```

If identity mapping fixes vertical but leaves only one horizontal sign wrong, change one axis sign at a time (`x,-y,z` for forward/back inversion, `-x,y,z` for left/right inversion) and analyze the trajectory before further tuning.

시점이 몸 정면과 30-60도 정도 어긋나면 Isaac OpenXR anchor yaw를 조정한다. `robot_start_box` recenter와 fallback `P` recenter는 recorder/action-filter 기준을 다시 잡는 기능이며 XR camera anchor 자체를 돌리지 않는다. 이 branch는 단순 UX 문제가 아니라 `camera-conditioning-ready` gate의 증거 수집 branch이기도 하다. 방향이 시점 때문에 달라 보이면 axis map을 감으로 바꾸기 전에 HMD/operator camera pose와 world/robot/task transform provenance가 trajectory에 남는지 확인한다.

```bash
RDF_XR_ANCHOR_YAW_OFFSET_DEG=45 RDF_RECORD=1 RDF_MAX_FRAMES=300 ~/run_isaac_handtracking.sh
RDF_XR_ANCHOR_YAW_OFFSET_DEG=-45 RDF_RECORD=1 RDF_MAX_FRAMES=300 ~/run_isaac_handtracking.sh
```

세밀하게 맞출 때는 `15`, `30`, `45`, `60`, `-15`, `-30`, `-45`, `-60` 순서로 시도한다. 실행 로그의 `[RDF] XR anchor config: ... yaw_offset_deg=...`로 적용 여부를 확인한다.

HMD 없이 Forge direct action/controller 자체가 살아 있는지 먼저 보려면 다음을 실행한다.

```bash
cd ~/robot-data-forge
/home/kangrim/IsaacLab/_isaac_sim/python.sh \
  scripts/check_forge_direct_action_response.py \
  --steps 20 \
  --pretty
```

`control_mode=bounded_direct_ee_target`, `passed=true`면 현재 live teleop collection path가 robot fingertip을 움직일 수 있다. 이 경우 live 문제는 Start XR/Start AR 이후 `Teleop control mode: bounded_direct_ee_target`, `raw_xyz`, `filtered_xyz`, `step_xyz`, `target_error_norm`, `command_step_norm`, `motion_debug` 로그를 기준으로 좁힌다.

HMD에서 반응이 여전히 둔하면 direct EE target gain/max step을 조금 올린다.

```bash
RDF_TELEOP_CONTROL_MODE=bounded_direct_ee_target \
RDF_DIRECT_EE_POS_GAIN=0.24 \
RDF_DIRECT_EE_MAX_STEP_M=0.08 \
RDF_DIRECT_EE_SMOOTHING_ALPHA=0.98 \
RDF_ACTION_POS_GAIN=0.55 \
RDF_ACTION_SMOOTHING_ALPHA=0.65 \
./scripts/run_live_rdf_smoke_test.sh --no-start-xr
```

legacy native Forge action path를 비교해야 할 때만 다음처럼 명시한다.

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh \
  scripts/check_forge_direct_action_response.py \
  --control-mode asset_relative \
  --steps 20 \
  --pretty
```

실기기 착용 전 실행환경을 먼저 점검한다.

```bash
cd ~/robot-data-forge
uv run python scripts/check_rdf_runtime_env.py
```

XR process가 이미 떠 있어야 하는 상황까지 강하게 확인하려면 다음을 사용한다.

```bash
uv run python scripts/check_rdf_runtime_env.py --require-running-xr
```

live run 직후 최신 recording이 새 calibration/action field를 갖는지 확인한다.

```bash
uv run python scripts/verify_latest_rdf_recording.py --pretty
```

기본 latest 진단은 종료 직전에 생긴 0-frame incomplete trajectory를 건너뛰고 최신 non-empty trajectory를 우선 선택한다. 정말 가장 최신 파일이 0-frame인지 확인해야 할 때만 아래 flag를 쓴다.

```bash
uv run python scripts/verify_latest_rdf_recording.py --include-empty-latest --pretty
uv run python scripts/analyze_teleop_calibration.py --latest --include-empty-latest --pretty
```

기존 recording 또는 patch 전 recording을 확인할 때는 새 field 누락을 warning으로 낮춘다.

```bash
uv run python scripts/verify_latest_rdf_recording.py --allow-legacy --pretty
```

조작 UX 판단용 action 통계를 확인한다.

```bash
uv run python scripts/analyze_teleop_calibration.py --latest --pretty
```

Quest 착용 전 또는 live run 직후에는 세 진단을 한 번에 실행할 수 있다.

```bash
uv run python scripts/run_mvp0_offline_diagnostics.py --allow-legacy
```

새 recorder patch 이후 recording만 엄격하게 확인할 때는 `--allow-legacy`를 빼고 실행한다.

```bash
uv run python scripts/run_mvp0_offline_diagnostics.py
```

확인할 값:

```text
raw_action_jump.max
applied_action_jump.max
raw_applied_delta.max
position_suppression_ratio
operator_recenter_event_count
control_filter_frame_count
suppressed_after_recenter_frame_count
raw_position_axes.dominant_axis
applied_position_axes.dominant_axis
tracking_quality.right_hand_tracked_rate
calibration_summary.translation_offset_norm
calibration_summary.rotation_offset_angle_deg
```

`run_mvp0_offline_diagnostics.py`의 의미:

```text
preflight:
  live runner, smoke runner, Isaac teleop script, OpenXR runtime, API, ALVR/SteamVR process 상태를 확인한다.

recording:
  latest trajectory/evaluation pairing, source metadata, lifecycle, timestamps, action dimensions,
  raw/aligned XR pose, retargeted action, robot/object state를 확인한다.

calibration:
  raw/applied action jump, per-axis movement, recenter count, control filter metadata,
  tracking quality, calibration offset을 확인한다.
```

로그 파일은 아래에 저장된다.

```text
storage/logs/live_smoke_*_<timestamp>.json
storage/logs/live_smoke_api_<timestamp>.log
storage/logs/live_smoke_init_<timestamp>.log
```

실패 해석:

```text
Preflight 실패:
  uv, curl, python3, ~/run_isaac_handtracking.sh, ALVR Dashboard path, SteamVR runtime path를 확인한다.

API 선택 실패:
  지정한 API_BASE가 잘못됐거나 `/api/episodes`, `/api/admin/kpis`가 500을 반환한다.
  API_BASE를 지정하지 않으면 스크립트가 자동으로 다음 빈 포트를 잡아 local SQLite API를 띄운다.

새 episode가 증가하지 않음:
  Isaac terminal의 `[RDF] Recorder disabled`, API POST 실패, Quest/SteamVR 연결 상태를 확인한다.

latest trajectory에 frame이 없음:
  Isaac을 너무 빨리 닫았거나 handtracking frame extraction이 실패한 것이다.

TRACKING_LOSS가 초반 frame 때문에 크게 나옴:
  developer는 live smoke 로그에서 `[RDF] Waiting for ... consecutive valid handtracking frames`와
  `[RDF] Recording frames started after dropping ... warm-up frames`를 확인한다.
  HMD operator는 terminal 대신 in-HMD panel의 `RECORDING: WARMUP n/N` -> `RECORDING: ON`을 본다.
  계속 높으면 Quest 3에서 손을 HMD 카메라 시야 안에 둔 상태로 연결하고,
  `RDF_WARMUP_VALID_FRAMES=30 ./scripts/run_live_rdf_smoke_test.sh`로 재시도한다.

raw/aligned XR metadata가 없음:
  최신 recorder가 적용되지 않은 것이다. `~/run_isaac_handtracking.sh`가 `--rdf_disable_auto_calibrate`
  옵션을 인식하는지 확인하고 `uv run pytest -q apps/api/tests/test_isaac_runtime_recorder.py`를 실행한다.
```

---

## 4. Local Recorder 경계 확인

Primary adapter command를 확인한다.

```bash
uv run python scripts/record_isaac_episode.py
```

Isaac 실행 스크립트가 존재할 때의 예상 결과:

```text
PRIMARY: ['/home/kangrim/run_isaac_handtracking.sh']
No episode submitted. Use --mock-submit to exercise backend submit flow.
```

Fallback/debug trajectory를 local API에 제출한다.

```bash
uv run python scripts/record_isaac_episode.py --api-base http://localhost:8000 --mock-submit
```

중요:

```text
--mock-submit is fallback/debug only.
It does not prove real Quest/OpenXR/Isaac runtime frame capture.
```

실제 Isaac runtime frame hook을 테스트하려면 API 서버를 먼저 켠다.

```bash
cd ~/robot-data-forge
./scripts/run_local_api_sqlite.sh
```

다른 terminal에서 ALVR/SteamVR/Quest 연결을 끝낸 뒤 recorder를 켜서 Isaac을 실행한다.

```bash
RDF_RECORD=1 ~/run_isaac_handtracking.sh
```

선택 옵션:

```bash
RDF_API_BASE=http://localhost:8000
RDF_CONTRIBUTOR_ID=user_001
RDF_MAX_FRAMES=300
RDF_WARMUP_VALID_FRAMES=10
RDF_DISABLE_AUTO_CALIBRATE=0
RDF_ACTION_FILTER=1
RDF_ACTION_POS_GAIN=0.40
RDF_ACTION_ROT_GAIN=0.35
RDF_ACTION_POS_AXIS_MAP=x,z,y
RDF_ACTION_ROT_AXIS_MAP=x,y,z
```

기대 로그:

```text
[RDF] Recording episode episode_... for task task_...
[RDF] Submitted episode episode_...: status=... success=... score=...
```

API가 실행 중이 아니면 Isaac teleop 자체는 계속 실행되지만 recorder는 비활성화된다. 이 경우 terminal에 `[RDF] Recorder disabled` 로그가 남는다.

수집 결과 확인:

```bash
curl -sS http://localhost:8000/api/episodes
curl -sS http://localhost:8000/api/admin/kpis
```

---

## 5. Episode Lifecycle 디버깅

RDF episode는 Isaac Sim 종료를 기다리지 않고 operator command로 finalize할 수 있다.

상태:

```text
running:
  `/api/episodes/start` 직후 상태다.

success:
  operator가 성공 episode로 finalize했다.

failure:
  operator가 실패 episode로 finalize했다. failure_reason 또는 failure_note를 저장할 수 있다.

reset:
  operator가 environment reset을 눌렀고, 해당 episode가 success/failure가 아닌 reset으로 닫혔다.

incomplete:
  Isaac shutdown, runtime error, 또는 명시적 finalize 없이 종료된 episode다.
```

Isaac 실행 중 command:

```text
N:
  current episode를 success로 finalize하고 새 episode를 시작한다.

F:
  current episode를 failure로 finalize하고 새 episode를 시작한다.

R:
  current episode를 reset으로 finalize하고 environment를 reset한 뒤 새 episode를 시작한다.

P:
  calibration/recenter metadata를 갱신한다. lifecycle finalize는 하지 않는다.
```

`RDF_RECORD=1`로 실행하면 terminal hotkey fallback도 활성화된다.

```text
[RDF] Terminal hotkeys active: P=recenter, N=success, F=failure, R=reset
```

이 로그가 보이면 Isaac viewport가 아니라 실행한 terminal에 focus를 둔 상태에서도 소문자 `p`, `n`, `f`, `r` 입력이 동작한다. 정상 입력 시 아래 로그가 즉시 출력되어야 한다.

```text
[RDF] Calibration/recenter requested
[RDF] Episode finalize requested: status=success reason=operator_success
```

위 로그 없이 terminal에 `p` 또는 `n` 글자만 찍히면 최신 `teleop_se3_agent.py`가 적용되지 않았거나 terminal hotkey가 비활성화된 것이다.

API 확인:

```bash
curl -sS http://localhost:8000/api/episodes
curl -sS "http://localhost:8000/api/episodes?status=success"
curl -sS "http://localhost:8000/api/episodes?status=incomplete"
```

수동 finalize 예시:

```bash
curl -sS -X POST http://localhost:8000/api/episodes/$EPISODE_ID/finalize \
  -H 'Content-Type: application/json' \
  -d '{
    "trajectory": {
      "schema_version": "0.1.0",
      "source": {
        "input_device": "quest3_handtracking",
        "runtime": "steamvr_openxr",
        "simulator": "isaac_lab",
        "robot": "franka",
        "task_name": "Isaac-Stack-Cube-Franka-IK-Rel-v0"
      },
      "frames": [],
      "summary": {"duration_sec": 0.0}
    },
    "episode_status": "incomplete",
    "episode_finalize_reason": "manual_debug_finalize",
    "episode_failure_note": "No frames were recorded."
  }'
```

해석:

```text
response.success:
  evaluator success다.

response.episode_status:
  operator lifecycle status다.

Episode.accepted:
  evaluator success이면서 lifecycle status가 success일 때만 true다.

completed_episodes KPI:
  success/failure/reset/legacy completed를 센다. 데이터 품질 지표로 해석하면 안 된다.
```

---

## 6. XR 시점 불일치 UX 디버깅

증상:

```text
Quest 3에서 Isaac AR 화면은 따라오지만, 사용자의 실제 시점/손 위치와 robot workspace의 기준점이 맞지 않아 조작이 불편하다.
```

현재 해석:

```text
OpenXR/SteamVR 연결 자체는 정상이어도 XR anchor, HMD 시작 위치, Franka/table 위치, hand retargeting 기준 좌표가 서로 어긋나면 조작 UX가 나빠진다.
이 문제는 trajectory 품질에도 영향을 주므로 MVP-0의 단순 편의 문제가 아니라 collection quality issue로 취급한다.
또한 camera/HMD geometry가 빠지면 downstream visual policy나 view-conditioned loader가 같은 action을 어떤 시점 조건에서 해석해야 하는지 알 수 없으므로 dataset readiness issue로 취급한다.
```

현재 primary 운영 절차는 robot-space start box recenter다. 세부 계약은 [`docs/experiments/hmd/hmd_recenter_start_box.md`](../experiments/hmd/hmd_recenter_start_box.md)를 기준으로 한다.

Camera-conditioning-ready debug 판정:

```text
PASS:
  - raw HMD/operator camera pose가 frame timestamp와 함께 저장된다.
  - world, robot_base, end_effector, task/object, camera/operator_view transform chain을 복원할 수 있다.
  - task target, held object, EEF/fingertip visibility 또는 projection smoke 결과가 summary에 남는다.
  - robot/world action과 camera/operator-view derived action이 raw label을 덮어쓰지 않고 별도 field로 남는다.

FAIL:
  - HMD에서 방향이 틀려 보이는데 camera pose/anchor/yaw provenance가 trajectory에 없다.
  - camera extrinsics/intrinsics/time alignment가 없어 visual-policy conditioning이 불가능하다.
  - task object가 HMD/camera view 밖에 있었는지 알 수 없다.
```

즉시 시도할 운영 절차:

```text
1. Quest 3에서 ALVR 연결 후 SteamVR/handtracking이 안정될 때까지 기다린다.
2. Isaac/AR session이 열리면 HMD 안에서 /World/RDFRecenterStartBox가 보이는지 확인한다.
3. 손을 HMD camera 시야 안에 둔다.
4. setup-only control로 robot EEF/fingertip을 start box 안에 넣는다.
5. box가 blue 상태가 되면 움직이지 말고 hold한다.
6. box가 green 또는 HMD text가 RECENTER: OK가 되면 실제 task 조작을 시작한다.
7. view yaw 자체가 크게 어긋나면 Isaac/AR session을 닫고 `RDF_XR_ANCHOR_YAW_OFFSET_DEG=45` 또는 `-45`로 재실행한다.
8. SteamVR room forward 자체가 틀어진 느낌이면 Quest/SteamVR recenter 후 다시 시작한다.
```

필수 env:

```text
RDF_RECENTER_MODE=robot_start_box
RDF_RECENTER_BOX_CENTER_SOURCE=hole_target_approach
RDF_RECENTER_BOX_APPROACH_OFFSET=0,0,0.08
RDF_RECENTER_BOX_RANDOM_OFFSET=0.02,0.02,0.01
RDF_RECENTER_BOX_VISUAL=0
RDF_BLOCK_TELEOP_UNTIL_RECENTER=1
RDF_RECENTER_SETUP_CONTROL=1
```

정상 로그:

```text
[RDF] Robot start recenter box reset: center_source=hole_target_approach ... random_offset=[...]
[RDF][RECENTER] mode=robot_start_box ... inside=True valid_hand=True ready=True ...
[RDF] Auto recenter applied after robot start-box hold ...
[RDF] Calibration/recenter requested: reason=auto_robot_start_box
```

문제 해석:

```text
start box가 HMD/AR에서 보이지 않음:
  wireframe이 필요하면 RDF_RECENTER_BOX_VISUAL=1, IsaacLab patch 적용 여부를 확인한다.

시작하자마자 바로 recenter됨:
  box center가 reset robot pose로 잡힌 상태일 가능성이 크다.
  기본 center source는 hole_target_approach여야 한다.

box 안에 들어갔는데 recenter가 안 됨:
  right-hand tracking validity, RDF_AUTO_RECENTER_VALID_FRAMES, box half extents를 확인한다.

recenter 전부터 recording frame이 저장됨:
  RDF_BLOCK_TELEOP_UNTIL_RECENTER=1 계약이 깨진 것이다.
```

Terminal `P` command는 fallback/debug command다. Recorded metadata의 raw/aligned XR pose와 RDF action filter smoothing state를 다시 맞추지만, primary HMD collection flow에서는 start-box recenter를 사용한다. `P` command도 Isaac OpenXR anchor rotation을 바꾸지는 않는다.

---

## 7. Evaluator Quality Gate 디버깅

`ForgeEval`은 task success뿐 아니라 XR/runtime 품질도 기록한다. 현재 추가된 quality gate는 다음 네 가지다.

```text
tracking_loss_after_warmup
retargeting_jump_max
latency quality gate
jitter quality gate
```

Threshold key:

```json
{
  "max_tracking_loss_after_warmup": 0.3,
  "max_retargeting_jump": 0.25,
  "max_average_input_latency_ms": 120,
  "max_input_latency_ms": 250,
  "max_frame_interval_jitter_ms": 50
}
```

해석:

```text
TRACKING_LOSS:
  warm-up 이후에도 right_hand_tracked=false 또는 xr_frame_valid=false frame 비율이 threshold를 넘었다.

RETARGETING_JUMP:
  retargeted action 또는 aligned/raw right wrist pose의 frame-to-frame jump가 threshold를 넘었다.

SCENE_STATE_DISCONTINUITY:
  하나의 recorded trajectory 안에서 `metadata.task_state.hole_position` 또는
  `hole_target_position` 같은 static task target이 2cm 이상 순간 이동했다.
  이 경우 controller target 계산 문제가 아니라 hidden env reset, task-state teleport,
  또는 recorder reset-boundary 누락으로 보고 training eligible에서 제외한다.

INPUT_LATENCY:
  metadata.input_latency_ms의 평균 또는 최대값이 threshold를 넘었다.

FRAME_JITTER:
  frame timestamp 간격의 최대 deviation이 threshold를 넘었다.
```

Backward compatibility:

```text
retargeting_jump, latency, jitter는 threshold가 있을 때만 실패 gate로 적용된다.
따라서 예전 trajectory에 latency metadata가 없거나 timestamp 간격이 거칠어도 기존 success 판정을 깨지 않는다.
tracking_loss_after_warmup은 기존 tracking_loss_rate > 0.3 동작을 보존하기 위해 기본 threshold 0.3을 사용한다.
scene_state_discontinuity는 peg-in-hole evaluator에서만 적용되며, dynamic EEF/object/peg jump는
진단 event로 기록하되 static task target jump가 있을 때만 hard reject한다.
```

Targeted test:

```bash
cd ~/robot-data-forge
uv run pytest -q apps/api/tests/test_evaluator.py
```

전체 backend regression:

```bash
uv run pytest -q apps/api/tests
uv run python -m compileall -q apps/api/app apps/api/tests scripts
```

---

## 8. Dataset Export 디버깅

관련 파일:

```text
apps/api/app/routers/datasets.py
apps/api/app/services/exporter.py
apps/api/app/services/storage.py
apps/api/tests/test_dataset_export_regressions.py
```

경로 안전 규칙:

```text
User-provided dataset name is display-only.
Export filename must be server-generated dataset_id.
```

필터링 규칙:

```text
only_success=true:
  ForgeCurate is applied.

only_success=false:
  success and failed episodes are exported.
```

Regression test:

```bash
uv run pytest -q apps/api/tests/test_dataset_export_regressions.py
```

---

## 9. Offline HDF5 Export 디버깅

Offline HDF5 export는 live recorder를 건드리지 않는다. 기존 JSON trajectory를 읽어 training-ready baseline format으로 변환한다.

기본 success-only export:

```bash
cd ~/robot-data-forge
uv run python scripts/export_rdf_to_hdf5.py \
  --storage-root storage \
  --output storage/exports/rdf_success_dataset.hdf5
```

failure/reset/incomplete까지 포함하는 debug export:

```bash
uv run python scripts/export_rdf_to_hdf5.py \
  --storage-root storage \
  --output storage/exports/rdf_debug_dataset.hdf5 \
  --include-failure \
  --include-reset \
  --include-incomplete
```

현재 저장된 trajectory가 Isaac shutdown으로 닫힌 legacy `incomplete` episode뿐이면 기본 success-only export는 아래처럼 실패하는 것이 정상이다.

```text
export failed: No trajectories matched the requested lifecycle filter (success).
```

이 경우 debug 목적이면 `--include-incomplete`를 붙인다. Training dataset 목적이면 Isaac 실행 중 `N`으로 success finalize한 episode를 먼저 수집해야 한다.

HDF5 구조 확인:

```bash
uv run python - <<'PY'
import h5py
path = "storage/exports/rdf_success_dataset.hdf5"
with h5py.File(path, "r") as h5:
    print(list(h5.keys()))
    print([x.decode() if isinstance(x, bytes) else x for x in h5["episodes"]["episode_ids"][()]])
PY
```

Sanity checker:

```bash
uv run python scripts/inspect_rdf_hdf5.py storage/exports/rdf_success_dataset.hdf5 --pretty
```

주요 출력 해석:

```text
episode_count:
  export된 episode 수다.

episode_statuses:
  success/failure/reset/incomplete 분포다.

action_dimensions:
  raw_action, retargeted_robot_action의 frame당 dimension이다.

timestamp_monotonic:
  false면 frame time이 역전된 것이므로 export를 training에 쓰기 전에 원인을 확인한다.

retargeting_action_jump_max:
  retargeted_robot_action 사이의 최대 jump다. 갑자기 큰 값이면 조작 좌표계나 action extraction을 확인한다.

evaluation_metrics_available:
  false면 해당 episode에 연결된 evaluation metrics가 없거나 빈 object다. Export는 계속 가능하지만 learning/debug 분석 정보가 부족하다.

lifecycle_metadata_available:
  false면 episode lifecycle metadata가 빠진 것이다. 신규 recording에서는 없어야 한다.
```

Exporter regression:

```bash
uv run pytest -q apps/api/tests/test_offline_hdf5_export.py
```

대표 실패 원인:

```text
missing required field schema_version:
  trajectory JSON이 RDF schema를 따르지 않는다.

source missing required fields:
  input_device/runtime/simulator/robot/task_name 중 누락된 값이 있다.

success episode has no frames:
  training export 대상인 success episode에 학습 가능한 frame이 없다.

Some evaluation JSON files have no trajectory_id/episode_id:
  legacy evaluation 파일을 여러 trajectory 중 어떤 episode에 붙일지 알 수 없다.
  이 경우 trajectory 자체는 export하지만 evaluation metrics는 비워질 수 있다.

evaluation metrics empty:
  evaluation JSON은 연결됐지만 metrics object가 비어 있다.
  Export는 실패하지 않지만 quality/latency/jitter 분석이 제한된다.
```

---

## 10. 알려진 Gap

아직 구현되지 않은 항목:

```text
1. Quest/OpenXR/Isaac 실기기 연결 상태에서 recorder 제출 검증
2. MVP-0 Go Criteria measurement with 100 real trajectories
3. MVP-1 learning uplift validation
4. Full LeRobot Dataset v3 export
```

Mock test 통과를 MVP-0 Go Criteria 충족으로 해석하면 안 된다.

---

## 11. Frontend 디버깅

Web 의존성을 설치한다.

```bash
cd ~/robot-data-forge/apps/web
npm install
```

Build를 실행한다.

```bash
npm run build
```

Frontend dev server를 실행한다.

```bash
npm run dev
```

기본 API base:

```text
http://localhost:8000
```

Override:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

Page가 API unavailable state를 표시하면 먼저 다음을 확인한다.

```bash
curl -sS http://localhost:8000/health
```

그 다음 아래 endpoint를 확인한다.

```bash
curl -sS http://localhost:8000/api/admin/kpis
curl -sS http://localhost:8000/api/tasks
curl -sS http://localhost:8000/api/datasets
```

## 12. Quality Metadata 확인

Episode finalize 후 sync/usability/segment metadata가 생성됐는지 확인한다.

```bash
EPISODE_ID=episode_xxx
TRAJECTORY_ID=traj_xxx

curl -sS "http://localhost:8000/api/episodes/${EPISODE_ID}/sync-metrics"
curl -sS "http://localhost:8000/api/episodes/${EPISODE_ID}/usability"
curl -sS "http://localhost:8000/api/trajectories/${TRAJECTORY_ID}/segments"
curl -sS http://localhost:8000/api/admin/kpis
```

확인할 핵심 field:

```text
sync_metrics.metrics_json.timestamp_monotonic
sync_metrics.metrics_json.sync_error_ms_mean
sync_metrics.metrics_json.warnings
usability.score
usability.usable
usability.rejection_reasons_json
segments[].phase
admin.kpis.curation
admin.kpis.data_usability
```

주의:

- `sync_error_ms_mean=null`이면 현재 recorder frame에 sync error measurement가 없다는 뜻이다.
- `sync_error_ms_unavailable` warning은 export 실패가 아니라 측정 gap이다.
- `UNKNOWN` action segment는 phase metadata가 아직 없다는 뜻이다. 실패가 아니라 segmentation signal 부재다.
- `contact_sequence_score=0.5`는 contact sequence가 측정되지 않은 conservative placeholder다.
- MVP-1 `peg_in_hole` task에서 `metadata.task_state`가 있으면 evaluator는 insertion-specific metric을 사용한다.
- `ALIGNMENT_ERROR`는 peg/hole 축 정렬 오차가 threshold보다 크다는 뜻이다.
- `INSUFFICIENT_INSERTION_DEPTH`는 peg가 threshold만큼 삽입되지 않았다는 뜻이다.

## 13. Live Smoke 결과 해석

기능 검증 목적의 live smoke에서는 task를 실제로 성공시키지 않아도 된다. 이 경우 아래 값은 정상적으로 0일 수 있다.

```text
task_success_rate: 0.0
accepted_trajectory_rate: 0.0
exported episodes: []
```

해석:

- `P/N/F/R` 로그가 찍히고 episode가 `running`으로 남지 않으면 lifecycle command는 통과다.
- `trajectory_id`, `evaluation_id`, `sync_metrics`, `usability`가 생성되면 data pipeline은 통과다.
- `accepted_trajectory_rate=0.0`은 evaluator 기준 성공 trajectory가 없다는 뜻이다.
- `episodes: []` export는 `only_success=true`에서 accepted trajectory가 없으면 정상이다.

실패로 봐야 하는 경우:

```text
P/N/F/R 입력 로그가 없음
episode가 계속 running/recording 상태로 남음
trajectory_id가 없음
evaluation_id가 없음
sync-metrics endpoint가 404
usability endpoint가 404
```

Task 누적 확인:

```bash
curl -sS 'http://localhost:8000/api/episodes?started_after=2026-05-03T14:48:00Z'
curl -sS 'http://localhost:8000/api/admin/kpis?started_after=2026-05-03T14:48:00Z'
curl -sS 'http://localhost:8000/api/admin/kpis?task_id=task_719a38538a64&started_after=2026-05-03T14:48:00Z'
```

정상 live collection에서는 같은 Isaac task session의 여러 episode가 같은 `task_id` 아래에 모여야 한다.

`started_after`에는 `Z` suffix를 쓰는 것을 권장한다. `+00:00` offset을 shell query string에 직접 넣으면 `+`가 space로 해석될 수 있다.

## 14. MVP-1 Offline Readiness Bundle

실제 HMD를 쓰기 전, MVP-1 `peg_in_hole` 데이터 계약이 CLI에서 닫히는지 확인한다.

```bash
cd ~/robot-data-forge
uv run python scripts/run_mvp1_offline_readiness.py --clean
```

상세 report:

```bash
uv run python scripts/run_mvp1_offline_readiness.py --clean --pretty
```

생성되는 주요 artifact:

```text
storage/mvp1_readiness/readiness_report.json
storage/mvp1_readiness/curation_manifest.json
storage/mvp1_readiness/split_manifest.json
storage/mvp1_readiness/dataset_card.json
storage/mvp1_readiness/curated_vs_uncurated_experiment_manifest.json
storage/mvp1_readiness/rdf_mvp1_curated_readiness.hdf5
storage/mvp1_readiness/hdf5_inspection.json
```

HDF5 sanity check:

```bash
uv run python scripts/inspect_rdf_hdf5.py storage/mvp1_readiness/rdf_mvp1_curated_readiness.hdf5 --pretty
```

정상 기준:

```text
RDF MVP-1 offline readiness: PASS
raw=8
accepted=4
rejected=4
phases include APPROACH, ALIGN, CONTACT, INSERT, SEAT, RELEASE
learning_results_measured: false
hdf5 inspection issues: []
```

해석:

- 이 bundle은 synthetic/offline fixture다. 실제 Quest/Isaac live evidence가 아니다.
- `curated_vs_uncurated_uplift`는 의도적으로 `null`이다.
- learning KPI는 실제 policy A/B 평가 전까지 측정값처럼 표시하면 안 된다.
- 이 bundle의 목적은 evaluator, phase metadata, usability, curator, split manifest, dataset card, HDF5 sanity path가 같은 schema로 연결되는지 확인하는 것이다.

## 15. MVP-1 Proof Audit

MVP-1을 실제로 증명했다고 말할 수 있는지 gate별로 확인한다.

```bash
cd ~/robot-data-forge
uv run python scripts/run_mvp1_proof_audit.py --pretty
```

현재 정상적인 중간 상태는 `status=partial`이다.

```text
offline_readiness_passed: true
mvp1_phase_coverage_ready: true
curation_manifest_ready: true
split_manifest_ready: true
dataset_card_ready: true
hdf5_sanity_ready: true
no_fake_learning_uplift: true
real_insertion_trajectory_present: false
trainer_dry_run_passed: false
curated_vs_uncurated_policy_uplift_measured: false
```

해석:

- `partial`은 실패가 아니다.
- CLI/schema/export/curation proof는 준비됐지만, 실제 Quest/Isaac insertion trajectory와 policy A/B uplift가 아직 없다는 뜻이다.
- `real_insertion_trajectory_present`는 `storage/trajectories` 안에서 `peg_in_hole` 또는 `connector` 계열 task이며, `metadata.task_state`가 있고, synthetic fixture가 아닌 trajectory만 인정한다.
- `trainer_dry_run_passed`는 export artifact가 실제 policy trainer loader와 dry-run 또는 1 epoch smoke까지 연결되기 전까지 false여야 한다.
- `curated_vs_uncurated_policy_uplift_measured`는 실제 held-out policy 평가 결과가 들어오기 전까지 false여야 한다.

MVP-1 staged 해석:

- `MVP-1A`: real insertion trajectory + `metadata.task_state` + phase/eval/curation/export가 통과한 상태.
- `MVP-1B`: export artifact가 실제 trainer loader와 dry-run 또는 1 epoch smoke에 연결된 상태.
- `MVP-1C`: curated vs uncurated held-out policy uplift가 측정된 상태.
- full customer/investor MVP-1 proof는 `MVP-1C` 이후에만 주장한다.

현재 CLI 축약 출력은 다음 형태가 정상이다.

```text
RDF MVP-1 proof audit: PARTIAL
stage=offline_readiness
next_stage=MVP-1A
required_gates=7/10
```

CI처럼 full proof가 아니면 실패 처리하려면:

```bash
uv run python scripts/run_mvp1_proof_audit.py --strict
```

현재는 `--strict`가 non-zero를 반환하는 것이 맞다. 아직 full MVP-1 proof가 아니기 때문이다.

## 16. MVP-1A Live Insertion Run

MVP-1A의 목적은 Stack-Cube smoke가 아니라 실제 Isaac insertion task에서 `metadata.task_state`가 저장되는지 확인하는 것이다. 현재 runner는 `Isaac-Forge-PegInsert-Direct-v0`를 MVP-1A 기본 후보로 사용한다.

```bash
cd ~/robot-data-forge
RDF_RECORD=1 \
RDF_ISAAC_TASK=Isaac-Forge-PegInsert-Direct-v0 \
RDF_TASK_TYPE=peg_in_hole \
RDF_MAX_FRAMES=900 \
RDF_WARMUP_VALID_FRAMES=10 \
RDF_ACTION_POS_GAIN=0.36 \
RDF_ACTION_ROT_GAIN=0.22 \
RDF_ACTION_SMOOTHING_ALPHA=0.40 \
RDF_TELEOP_CONTROL_MODE=auto \
RDF_OPERATOR_FOLLOW_PRESET=responsive \
RDF_DEBUG_ACTION_EVERY=20 \
RDF_DEBUG_MOTION_EVERY=20 \
RDF_VISUAL_DEBUG=1 \
RDF_VISUAL_DEBUG_EVERY=1 \
RDF_VISUAL_DEBUG_INPUT_SCALE=0.25 \
RDF_RECENTER_MODE=robot_start_box \
RDF_RECENTER_BOX_CENTER_SOURCE=hole_target_approach \
RDF_RECENTER_BOX_APPROACH_OFFSET=0,0,0.08 \
RDF_RECENTER_BOX_RANDOM_OFFSET=0.02,0.02,0.01 \
RDF_RECENTER_BOX_VISUAL=0 \
RDF_BLOCK_TELEOP_UNTIL_RECENTER=1 \
RDF_RECENTER_SETUP_CONTROL=1 \
~/run_isaac_handtracking.sh
```

기본 asset 해석:

```text
Isaac-Forge-PegInsert-Direct-v0
peg_asset_name  = held_asset
hole_asset_name = fixed_asset
```

필요하면 명시적으로 override한다.

```bash
RDF_PEG_ASSET_NAME=held_asset
RDF_HOLE_ASSET_NAME=fixed_asset
RDF_PEG_TIP_LOCAL_OFFSET=0,0,0
RDF_HOLE_TARGET_LOCAL_OFFSET=0,0,0
RDF_INSERTION_AXIS_WORLD=0,0,-1
```

실행 순서:

1. SteamVR와 ALVR 연결을 먼저 안정화한다.
2. 위 명령으로 Isaac을 실행한다.
3. Isaac이 뜨면 `Start XR` 또는 `Start AR`을 누른다.
4. Quest 3를 착용하고 손 추적이 안정될 때까지 몇 초 기다린다.
5. HMD/Isaac 화면에서 `/World/RDFRecenterStartBox`와 visual marker가 보이는지 확인한다. green은 현재 robot fingertip, cyan은 hand delta target, yellow는 이번 step robot target, magenta는 Forge hole 기준 target이다.
6. setup-only control로 robot EEF/fingertip을 start box 안에 넣고, box가 blue인 상태에서 hold한다.
7. `RECENTER: OK` 또는 green box를 확인한 뒤 실제 insertion 조작을 시작한다.
8. 터미널에서 `action_debug`의 `raw_xyz`, `filtered_xyz`, `step_xyz`와 `motion_debug`의 `eef_delta_norm`이 변하는지 확인한다.
9. 최소 수십 초 조작한 뒤 `N` 또는 `F`로 explicit finalize한다.
10. Isaac을 닫은 뒤 아래 검증을 실행한다.

```bash
uv run python scripts/verify_latest_rdf_recording.py --pretty
uv run python scripts/analyze_teleop_calibration.py --latest --pretty
uv run python scripts/run_mvp1_proof_audit.py --pretty
```

성공적으로 저장된 MVP-1A 후보 trajectory는 다음 조건을 만족해야 한다.

```text
source.input_device = quest3_handtracking
source.runtime = steamvr_openxr
source.simulator = isaac_lab
source.task_name = Isaac-Forge-PegInsert-Direct-v0
frames[].metadata.task_state exists
summary.task_state_source = isaac_scene_assets
summary.task_state_frame_count > 0
```

주의:

- `run_mvp1_proof_audit.py`가 `stage=MVP-1A`로 올라가더라도 full MVP-1 proof는 아니다.
- `trainer_dry_run_passed=false`면 아직 MVP-1B가 아니다.
- `curated_vs_uncurated_policy_uplift_measured=false`면 아직 MVP-1C가 아니다.
- Direct insertion task는 기존 ManagerBased stack task와 control semantics가 다르므로, 조작감 gain/axis map은 live run 후 계속 조정해야 한다.
- Primary HMD collection에서는 `P` recenter에 의존하지 않는다. `P`는 RDF recording metadata/action-filter 상태를 갱신하는 fallback/debug command이며, Isaac OpenXR control anchor 자체를 바꾸지 않는다.
- `Isaac-Forge-PegInsert-Direct-v0` / `Isaac-Factory-PegInsert-Direct-v0`는 6D relative delta action을 쓰며, gripper action 없이 fingertip target을 작은 범위에서 움직인다. 손 위치 mirror가 아니라 손목 움직임의 변화량이 action으로 들어간다고 해석해야 한다.
- visual marker는 진단용 표시이며 trajectory action 값이나 evaluator 결과를 바꾸지 않는다. 화면이 복잡하면 `RDF_VISUAL_DEBUG=0`으로 끌 수 있다.

## 17. MVP-1B Trainer Loader Smoke

MVP-1B의 목적은 full learning uplift가 아니라, exported dataset이 실제 trainer-style loader와 dry-run 또는 1 epoch smoke에 들어가는지 증명하는 것이다.

먼저 readiness artifact를 준비한다.

```bash
cd ~/robot-data-forge
uv run python scripts/run_mvp1_offline_readiness.py --clean
```

그다음 trainer smoke를 실행한다.

```bash
uv run python scripts/run_mvp1_trainer_smoke.py --pretty
```

이 스크립트는 다음을 검증한다.

- `storage/mvp1_readiness/rdf_mvp1_curated_readiness.hdf5`를 연다.
- `split_manifest.json`의 train/validation/test episode가 HDF5에 존재하는지 확인한다.
- observation/action/timestamp array가 finite하고 frame count가 맞는지 확인한다.
- train split으로 deterministic NumPy BC-style batch를 만들고 one small optimization epoch를 실행한다.
- 결과를 `storage/mvp1_readiness/trainer_smoke_report.json`에 저장한다.
- `curated_vs_uncurated_experiment_manifest.json`의 `training_readiness`를 갱신한다.

성공 출력의 핵심은 다음이다.

```text
loader_smoke_passed=true
trainer_dry_run_passed=true
one_epoch_smoke_passed=true
learning_results_measured=false
curated_vs_uncurated_uplift=null
```

그 뒤 proof audit를 다시 실행한다.

```bash
uv run python scripts/run_mvp1_proof_audit.py --pretty
```

MVP-1A live insertion evidence와 trainer smoke가 모두 있으면 staged output은 다음처럼 올라간다.

```text
current_stage=MVP-1B
next_stage=MVP-1C
passed_required_gates=9/10
missing_required_gates=[curated_vs_uncurated_policy_uplift_measured]
```

주의:

- 이 smoke는 policy 성능 향상을 증명하지 않는다.
- `linear_bc_numpy_smoke`는 schema/loader/trainer-path sanity check용이다.
- `curated_vs_uncurated_uplift`는 실제 held-out A/B policy evaluation 전까지 반드시 `null`이어야 한다.

## 18. MVP-1B Live Export Smoke

기본 MVP-1B smoke는 offline readiness HDF5를 사용한다. 더 강한 증거가 필요하면 HMD를 다시 착용하지 않고, 이미 저장된 MVP-1A live trajectory를 export/trainer smoke에 연결한다.

```bash
cd ~/robot-data-forge
uv run python scripts/run_mvp1_live_export_smoke.py --clean --pretty
uv run python scripts/run_mvp1_proof_audit.py --pretty
```

이 경로는 다음을 수행한다.

- `storage/trajectories`에서 real Quest/SteamVR/OpenXR/Isaac insertion trajectory를 찾는다.
- synthetic readiness fixture는 live evidence로 인정하지 않는다.
- 선택한 trajectory와 matching evaluation을 `storage/mvp1_live_export/raw/`로 복사한다.
- `storage/mvp1_live_export/rdf_mvp1_live_export_smoke.hdf5`를 생성한다.
- `storage/mvp1_live_export/split_manifest.json`을 생성한다.
- HDF5 inspector와 trainer smoke를 실행한다.
- proof audit가 읽는 `storage/mvp1_readiness/curated_vs_uncurated_experiment_manifest.json`의 `training_readiness`에 live-export evidence path를 반영한다.

성공 출력의 핵심은 다음이다.

```text
RDF MVP-1B live export smoke: PASS
trainer_dry_run_passed=True
one_epoch_smoke_passed=True
learning_results_measured=False
curated_vs_uncurated_uplift=None
```

proof audit의 trainer gate evidence는 다음처럼 live bundle을 가리켜야 한다.

```text
evidence_source=mvp1a_live_export_bundle
hdf5_path=storage/mvp1_live_export/rdf_mvp1_live_export_smoke.hdf5
live_trajectory_ids=[...]
sample_count > 0
```

주의:

- 이 작업에는 HMD가 필요 없다.
- split manifest는 single live episode를 train/validation/test 이름에 재사용하는 smoke-only split이다.
- 따라서 이 split은 loader/trainer path sanity check 전용이며, MVP-1C policy uplift 평가에는 사용하면 안 된다.
- full MVP-1 proof는 여전히 MVP-1C의 held-out curated-vs-uncurated policy result가 있어야 한다.

## 19. MVP-1C Policy Uplift Smoke

MVP-1C의 최종 목표는 held-out policy rollout에서 curated dataset이 uncurated baseline보다 더 좋은 결과를 만드는지 측정하는 것이다. 현재 CLI smoke는 그 전 단계로, offline readiness fixture에서 deterministic BC-style proxy experiment를 실행한다.

```bash
cd ~/robot-data-forge
uv run python scripts/run_mvp1c_policy_uplift_smoke.py --pretty
uv run python scripts/run_mvp1_proof_audit.py --pretty
```

이 smoke는 다음을 비교한다.

- baseline A: uncurated success-lifecycle episodes
- baseline B: curated accepted episodes
- held-out: readiness split의 test episode
- metric: action prediction score, `1 / (1 + mse)`

현재 이 smoke는 full MVP-1C proof가 아니다.

```text
evidence_tier=offline_proxy_smoke
proof_eligible=false
learning_results_measured=false
curated_vs_uncurated_uplift=null
```

현재 readiness fixture 기준 관찰된 proxy 결과:

```text
uncurated_score=0.9670253734580941
curated_score=0.9327330477860399
proxy_delta=-0.0342923256720542
proxy_uplift_positive=false
```

해석:

- 이 결과는 curated가 실제 policy 성능을 올렸다는 증거가 아니다.
- 오히려 현재 작은 curated train set만으로는 uncurated baseline보다 나은 action-prediction proxy가 나오지 않는다는 경고다.
- MVP-1C를 닫으려면 실제 held-out rollout/evaluation evidence가 필요하다.
- proof audit는 `evidence_tier=heldout_policy_eval` 또는 `real_heldout_policy_eval`, `proof_eligible=true`, `primary_metric=policy_success_rate` 없이는 full MVP-1C로 승격하지 않는다.
- `real_heldout_policy_eval`은 HMD live accepted trajectory가 포함된 경우에만 쓴다. Headless Isaac A/B만으로는 `heldout_policy_eval`을 쓴다.

## 20. MVP-1C Real Policy Eval Ingest

실제 held-out rollout을 수행한 뒤에는 그 결과를 JSON으로 저장하고 다음 CLI로 ingest한다. 이 단계는 offline proxy가 아니라 실제 policy success-rate 결과만 받는다.

```bash
cd ~/robot-data-forge
uv run python scripts/run_mvp1c_real_policy_eval.py \
  --input storage/mvp1_readiness/policy_eval_input.json \
  --pretty
uv run python scripts/run_mvp1_proof_audit.py --pretty
```

입력 JSON의 최소 구조는 다음과 같다.

```json
{
  "schema_version": "rdf_mvp1c_policy_eval_input_v0.1.0",
  "evidence_tier": "heldout_policy_eval",
  "primary_metric": "policy_success_rate",
  "task_type": "peg_in_hole",
  "eval_suite": {
    "id": "peg_insert_heldout_v1",
    "held_out": true,
    "split": "held_out_pose_clearance",
    "task_type": "peg_in_hole"
  },
  "baseline": {
    "name": "uncurated_success_lifecycle_policy",
    "dataset_view": "uncurated_success_lifecycle",
    "rollout_results": [
      {"rollout_id": "b_001", "scenario_id": "s_001", "success": true}
    ]
  },
  "candidate": {
    "name": "curated_accepted_policy",
    "dataset_view": "curated_accepted",
    "rollout_results": [
      {"rollout_id": "c_001", "scenario_id": "s_001", "success": true}
    ]
  }
}
```

CLI가 요구하는 핵심 조건:

- `evidence_tier=heldout_policy_eval` 또는 HMD live accepted trajectory 포함 시 `real_heldout_policy_eval`
- `primary_metric=policy_success_rate`
- `rollout_success_rate`는 secondary metric
- `eval_suite.held_out=true`
- baseline 이름 또는 dataset view가 `uncurated`를 명시
- candidate 이름 또는 dataset view가 `curated`를 명시
- 기본값 기준 policy당 rollout 10개 이상

결과 해석:

- valid real eval이지만 curated가 uncurated보다 낮으면 manifest에는 실제 측정값이 기록되고 `no_fake_learning_uplift` gate는 통과한다.
- 단, positive uplift가 아니므로 `curated_vs_uncurated_policy_uplift_measured` gate는 실패하고 stage는 MVP-1B에 남는다.
- positive real held-out uplift일 때만 proof audit가 MVP-1C로 승격한다.

## 21. MVP-1C Headless A/B Eval Bundle

HMD 없이 MVP-1C의 다음 단계를 준비하려면 uncurated/curated train artifact와 held-out eval template을 만든다.

```bash
cd ~/robot-data-forge
uv run python scripts/run_mvp1c_headless_eval_bundle.py --clean --pretty
```

생성되는 주요 파일:

```text
storage/mvp1c_headless_eval/baseline_uncurated/mvp1c_uncurated_success_lifecycle_train.hdf5
storage/mvp1c_headless_eval/candidate_curated/mvp1c_curated_accepted_train.hdf5
storage/mvp1c_headless_eval/heldout_suite_manifest.json
storage/mvp1c_headless_eval/policy_eval_input_template.json
storage/mvp1c_headless_eval/headless_eval_bundle_report.json
```

이 bundle은 다음을 수행한다.

- baseline A: uncurated success-lifecycle train set export
- candidate B: curated accepted train set export
- validation/test ids를 held-out suite scaffold로 기록
- `run_mvp1c_real_policy_eval.py`에 넣을 input template 생성

주의:

- 이 script는 policy rollout을 실행하지 않는다.
- 이 script만으로 MVP-1C가 통과되면 안 된다.
- `policy_eval_input_template.json`의 `rollout_results`를 실제 headless policy rollout 결과로 채운 뒤에만 ingest한다.

다음 명령은 template을 실제 결과로 채운 뒤 실행한다.

```bash
uv run python scripts/run_mvp1c_real_policy_eval.py \
  --input storage/mvp1c_headless_eval/policy_eval_input_template.json \
  --pretty
uv run python scripts/run_mvp1_proof_audit.py --pretty
```

## 22. MVP-1C Rollout Result Adapter

headless trainer/evaluator가 CSV 또는 JSON rollout 결과를 만들면 adapter로 template에 꽂는다.

```bash
cd ~/robot-data-forge
uv run python scripts/run_mvp1c_rollout_result_adapter.py \
  --template storage/mvp1c_headless_eval/policy_eval_input_template.json \
  --baseline-results path/to/baseline_rollouts.csv \
  --candidate-results path/to/candidate_rollouts.json \
  --output storage/mvp1c_headless_eval/policy_eval_input.json \
  --policy-class ACT \
  --trainer your_headless_trainer
```

지원 입력:

- CSV: `rollout_id,scenario_id,success`
- JSON list: `[{"rollout_id": "...", "scenario_id": "...", "success": true}]`
- JSON object: `{"rollout_results": [...]}`
- aggregate JSON: `{"rollout_count": 20, "success_count": 12}`

adapter는 experiment manifest를 갱신하지 않는다. 변환 후에는 real eval ingest를 실행한다.

```bash
uv run python scripts/run_mvp1c_real_policy_eval.py \
  --input storage/mvp1c_headless_eval/policy_eval_input.json \
  --pretty
uv run python scripts/run_mvp1_proof_audit.py --pretty
```

주의:

- adapter output이 positive여도 그 자체는 proof가 아니다.
- `run_mvp1c_real_policy_eval.py`가 valid real held-out input으로 판정해야 한다.
- 예시/fixture rollout 결과는 `--no-update-manifest`로만 검증한다.

## 23. MVP-1C Isaac Headless Policy A/B Smoke

HUD/HMD 없이 Isaac Forge peg-insert env에서 baseline/candidate policy rollout smoke를 실행할 수 있다.

```bash
cd ~/robot-data-forge
/home/kangrim/IsaacLab/_isaac_sim/python.sh \
  scripts/run_mvp1c_isaac_policy_ab_smoke.py \
  --rollouts-per-policy 2 \
  --max-steps 80 \
  --pretty
```

action representation mismatch를 진단하려면 fitted policy action을 clip 전 scale up할 수 있다.

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh \
  scripts/run_mvp1c_isaac_policy_ab_smoke.py \
  --rollouts-per-policy 2 \
  --max-steps 80 \
  --action-scale 20 \
  --pretty
```

산출물:

```text
storage/mvp1c_isaac_policy_ab_smoke/isaac_policy_ab_smoke_report.json
storage/mvp1c_isaac_policy_ab_smoke/baseline_rollouts.csv
storage/mvp1c_isaac_policy_ab_smoke/candidate_rollouts.csv
storage/mvp1c_isaac_policy_ab_smoke/policy_eval_input.json
```

현재 smoke 결과:

```text
action_scale=20.0
baseline_success_rate=0.0
candidate_success_rate=0.0
rollouts_per_policy=2
evidence_tier=isaac_headless_policy_eval_smoke
proof_eligible=false
```

해석:

- Isaac headless rollout path는 실제로 실행된다.
- 현재 readiness fixture 기반 lightweight BC policy는 `--action-scale 20`에서도 insertion success를 만들지 못했다.
- 단순 scale 문제가 아니라 train fixture/action representation/policy capacity 쪽 gap일 가능성이 높다.
- 이 결과는 full MVP-1C proof가 아니다.
- proof audit는 계속 `current_stage=MVP-1B`, `next_stage=MVP-1C`, gates `9/10`에 남아야 한다.

주의:

- 이 smoke는 현재 synthetic/readiness train bundle을 사용한다.
- 실제 MVP-1C claim에는 real insertion train set, proof-grade held-out scenarios, 충분한 rollout count가 필요하다.
- `simulation_app.close()`는 결과 JSON 작성 전에 프로세스를 끝낼 수 있으므로 runner는 결과를 먼저 기록하고 프로세스 자연 종료에 맡긴다.

## 24. MVP-1C Final HUD Data Ingest Preflight

새 HUD/Quest 데이터를 넣기 직전 상태인지 확인한다. 이 명령은 MVP-1C를 통과시키지 않고, 마지막 fresh data ingest와 held-out policy A/B evaluation만 남았는지 점검한다.

전체 1-7 실행 절차는 `docs/MVP1C_FULL_PROOF_EXECUTION_GUIDE.md`를 따른다. 브라우저에서 한 번에 보려면 `docs/MVP1C_FULL_PROOF_EXECUTION_GUIDE.html`을 연다.

```bash
cd ~/robot-data-forge
uv run python scripts/run_mvp1c_final_hud_ingest_preflight.py \
  --refresh-headless-bundle \
  --pretty
```

산출물:

```text
storage/mvp1c_final_hud_ingest_preflight/preflight_report.json
storage/mvp1c_final_hud_ingest_preflight/proof_audit_snapshot.json
storage/mvp1c_final_hud_ingest_preflight/final_hud_ingest_runbook.md
```

현재 결과:

```text
ready_for_final_hud_ingest=true
full_mvp1c_claimed=false
current_stage=MVP-1B
next_stage=MVP-1C
missing_required_gates=["curated_vs_uncurated_policy_uplift_measured"]
```

fresh HUD 데이터가 생긴 뒤 마지막 검증 순서:

```bash
uv run python scripts/run_mvp0_offline_diagnostics.py
uv run python scripts/run_mvp1_live_export_smoke.py --clean --pretty
uv run python scripts/run_mvp1c_headless_eval_bundle.py --clean --pretty
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

주의:

- 이 preflight가 `true`여도 full MVP-1C proof는 아니다.
- 실제 pass 조건은 `run_mvp1c_real_policy_eval.py`가 real held-out input을 받아 positive curated-minus-uncurated success-rate delta를 기록하는 것이다.
- minimum은 policy당 10 rollout이고, 고객/투자자 proof로는 policy당 50회 이상 rollout이 더 방어 가능하다.


## HMD axis debug short wrapper

When the operator reports direction mismatch, prefer the short wrapper over a long env command so `RDF_ISAAC_TASK`, axis map, yaw offset, and recenter-box visibility cannot drift silently. The HMD operator should watch the in-HMD guidance panel, not terminal text.

Latest observed symptom under the current attempts: hand-right appears to drive robot-down. The next controlled hypothesis is:

```bash
cd ~/robot-data-forge
./scripts/run_hmd_axis_debug.sh right-down-fix
```

This forces:

```text
RDF_ISAAC_TASK=Isaac-Forge-PegInsert-Direct-v0
RDF_ACTION_POS_AXIS_MAP=-z,y,x
RDF_ACTION_POS_YAW_OFFSET_DEG=0
RDF_RECENTER_BOX_VISUAL=0
```

If the latest file is zero-frame, inspect it explicitly:

```bash
uv run python scripts/verify_latest_rdf_recording.py --include-empty-latest --pretty
```

Then analyze the latest non-empty trajectory:

```bash
uv run python scripts/analyze_hmd_motion_mapping.py --latest --pretty --output storage/hmd_motion_mapping/latest_mapping_report.json
```


### HMD free-motion branch for start-box deadlock

If the operator cannot move the robot into the start box, do not continue axis-map testing. First bypass the start-box gate and prove hand input can move the robot at all:

```bash
cd ~/robot-data-forge
./scripts/run_hmd_axis_debug.sh free-motion
```

This is diagnostic only, not Gate A collection. It forces `RDF_RECENTER_MODE=first_valid_hand`, `RDF_BLOCK_TELEOP_UNTIL_RECENTER=0`, `RDF_RECENTER_SETUP_CONTROL=0`, and `RDF_RECENTER_BOX_VISUAL=0`. If the robot still does not move in this mode, inspect `action_debug` and `motion_debug` logs before changing axes again.

## 25. raw-wrist-direct가 여전히 로봇을 따라오지 않는 경우

`./scripts/run_hmd_axis_debug.sh raw-wrist-direct` 실행 후 operator가 “손동작을 로봇이 따라오지 않는다”고 보고하면, 먼저 controller/mapping보다 tracking gate를 확인한다.

최근 physical run `traj_b804823e845a`의 판정은 다음과 같다.

```text
recording schema/action contract: PASS
control_mode: raw_wrist_direct_ee_target
H7 Isaac EEF follows command direction: PASS
H9 handtracking loss/jitter: WARN
H13 valid wrist pose spikes: WARN
H14 controller target accumulation drift: PASS
H15 scene-state discontinuity: PASS
failure_reason: TRACKING_LOSS
```

핵심 해석:

- `raw_wrist_direct_ee_target` path는 활성화되어 있다.
- EEF는 명령이 실제로 들어간 구간에서는 대체로 명령 방향을 따른다.
- 그러나 많은 frame이 `invalid_right_hand`, `tracking_resume_warmup`, `raw_wrist_spike_reacquire_pending` 때문에 hold된다.
- 이 상태에서 axis/gain을 바꾸면 tracking 문제를 mapping 문제처럼 오진할 수 있다.

확인 명령:

```bash
cd ~/robot-data-forge
uv run python scripts/verify_latest_rdf_recording.py \
  --include-empty-latest \
  --storage-root storage \
  --pretty

uv run python scripts/analyze_hmd_motion_mapping.py \
  --latest \
  --pretty \
  --output storage/hmd_motion_mapping/latest_mapping_report.json
```

판정 기준:

- `failure_reason=TRACKING_LOSS` 또는 `H9 WARN`이면 Gate A collection을 중단한다.
- `H13 WARN`이면 raw wrist pose spike가 남아 있다는 뜻이므로 axis/gain 튜닝을 중단한다.
- `H14 PASS`이면 target accumulation 가설은 우선 배제한다.
- `H15 PASS`이면 이번 run에서 sim reset/teleport가 주 원인은 아니다.

운영자 조치:

1. Quest handtracking이 HMD 내부에서 안정적으로 보이는지 먼저 확인한다.
2. 손을 카메라 시야 중앙에 두고 강한 backlight/가림/빠른 flick motion을 피한다.
3. HMD panel의 `RECENTER`/tracking 상태가 안정된 뒤 움직임을 판단한다.
4. `raw_wrist_spike_reacquire_pending`이 반복되면 손동작을 줄이는 것이 아니라 tracking 환경을 먼저 안정화한다.

HMD 실증 전 코드상 방어선:

- `./scripts/run_hmd_axis_debug.sh raw-wrist-direct`는 기본 `RDF_WARMUP_VALID_FRAMES=15`, `RDF_AUTO_RECENTER_VALID_FRAMES=15`, `RDF_AUTO_RECENTER_STABLE_M=0.03`을 사용한다.
- `first_valid_hand` recenter는 valid frame 개수만 보지 않고 연속 right-wrist jump가 `RDF_AUTO_RECENTER_STABLE_M` 이하인지 확인한다.
- 불안정하면 terminal에 `AUTO_RECENTER_UNSTABLE_RIGHT_WRIST`를 남기고 recenter window를 다시 쌓는다.
- evaluator는 저장된 trajectory의 `action.raw_wrist_direct.valid_to_valid_jump_m`가 `max_raw_wrist_valid_to_valid_jump_m` 기본 `0.10m`를 넘으면 `RAW_WRIST_JUMP`로 `training_eligible=false`를 기록한다.

현재 상태에서는 `handtracking loss 과다`가 #30.3 No-Go 신호이므로, 이 문제가 사라지기 전에는 accepted trajectory collection이나 axis/gain 결론을 내리지 않는다.

## 26. Frontend lint/build가 interactive prompt에서 멈추는 경우

증상:

```bash
npm --prefix apps/web run lint
```

위 명령이 실제 lint error를 내기 전에 Next.js ESLint setup prompt에서 멈추면, `apps/web`에 명시적 ESLint CLI 구성이 없는 상태다.

현재 정상 경로:

```bash
cd ~/robot-data-forge
npm --prefix apps/web ci
npm --prefix apps/web run lint
npm --prefix apps/web run build
npm --prefix apps/web audit --audit-level=moderate
```

현재 기대값:

```text
lint: eslint .
build: Next.js production build PASS
audit: found 0 vulnerabilities
```

판정 기준:

- `next lint`가 다시 script에 들어오면 non-interactive agent/CI 환경에서 실패할 수 있다.
- 내부 route 이동은 raw `<a href="/path">` 대신 `next/link`의 `Link`를 사용한다.
- `postcss` advisory가 재발하면 먼저 `apps/web/package.json`의 `overrides.postcss`가 유지되는지 확인한다.
- `npm audit fix --force`는 Next major downgrade/upgrade를 유발할 수 있으므로 바로 실행하지 않는다.

## 27. HMD 로그를 복붙하지 않고 수집/판정하는 방법

`./scripts/run_hmd_axis_debug.sh raw-wrist-direct`는 이제 실행 전체 stdout/stderr를 자동으로 저장한다.

기본 저장 위치:

```text
storage/logs/hmd_axis_debug/hmd_axis_debug_<timestamp>_<mode>.log
storage/logs/hmd_axis_debug/hmd_axis_debug_<timestamp>_<mode>.log.summary.json
```

수동으로 최신 artifact를 다시 요약하려면:

```bash
cd ~/robot-data-forge
uv run python scripts/summarize_hmd_run_log.py \
  --pretty \
  --output storage/logs/latest_hmd_run_summary.json
```

특정 로그 파일을 기준으로 요약하려면:

```bash
uv run python scripts/summarize_hmd_run_log.py \
  --log-file storage/logs/hmd_axis_debug/<log-file>.log \
  --pretty \
  --output storage/logs/hmd_axis_debug/<log-file>.summary.json
```

판정 규칙:

- `AUTO_RECENTER_UNSTABLE_RIGHT_WRIST > 0`: 아직 수집 금지.
- `failure_reason=RAW_WRIST_JUMP`: task 실패가 아니라 입력 품질 실패. 수집 금지.
- `failure_reason=TRACKING_LOSS`: axis/gain 튜닝 보류. handtracking 환경 먼저 개선.
- `H13_status != PASS`: valid-to-valid wrist spike가 남아 있음. Gate A collection 금지.
- `right_hand_tracked_rate < 0.95` 또는 `xr_frame_valid_rate < 0.95`: tracking 품질 부족. Gate A collection 금지.

요약 출력에서 바로 볼 값:

```text
failure_reason
tracking_loss_rate
right_hand_tracked_rate
xr_frame_valid_rate
H13_status
raw_wrist_jump_max_m
gate_a_collection_allowed
axis_gain_tuning_allowed
reasons
```

## 28. Gate 0 XR Input Stream Viability 실행 절차

Gate A collection은 이제 손 추적 입력 스트림이 먼저 Gate 0을 통과해야 재개할 수 있다. Gate 0은 task success를 보지 않고, Quest/OpenXR right-wrist pose stream이 로봇 action label을 만들 만큼 안정적인지만 본다.

실행 모드:

```bash
cd ~/robot-data-forge
./scripts/run_hmd_axis_debug.sh gate0-all
```

`gate0-all`은 HMD를 한 번 착용한 상태에서 네 가지 Gate 0 diagnostic을 순서대로 실행한다. 단일 명령으로 다음 순서를 돈다.

```text
gate0-static
→ gate0-slow-motion
→ gate0-recenter
→ gate0-reacquire
```

개별 단계만 다시 돌릴 때는 아래 명령을 사용한다.

```bash
./scripts/run_hmd_axis_debug.sh gate0-static
./scripts/run_hmd_axis_debug.sh gate0-slow-motion
./scripts/run_hmd_axis_debug.sh gate0-recenter
./scripts/run_hmd_axis_debug.sh gate0-reacquire
```

각 모드 의미:

| mode | 목적 |
|---|---|
| `gate0-static` | 손을 거의 움직이지 않을 때 wrist pose가 튀지 않는지 확인 |
| `gate0-slow-motion` | 작은 slow motion에서 tracking loss / raw wrist jump가 없는지 확인 |
| `gate0-recenter` | recenter가 stable-window 후에만 허용되는지 확인 |
| `gate0-reacquire` | 손 추적 loss 후 reacquire/resume이 stable-window를 거치는지 확인 |
| `gate0-all` | 위 네 가지 diagnostic을 순서대로 실행하고 aggregate report를 생성 |

출력 artifact:

```text
storage/logs/hmd_axis_debug/hmd_axis_debug_<timestamp>_<mode>.log
storage/logs/hmd_axis_debug/hmd_axis_debug_<timestamp>_<mode>.log.summary.json
storage/logs/hmd_axis_debug/hmd_axis_debug_<timestamp>_<mode>.log.gate0.json
storage/logs/hmd_axis_debug/hmd_axis_debug_<timestamp>_gate0-all.log.gate0_all.json
```

수동 재판정:

```bash
uv run python scripts/run_gate0_xr_input_viability.py \
  --latest \
  --test-type static \
  --log-file storage/logs/hmd_axis_debug/<log-file>.log \
  --output storage/logs/hmd_axis_debug/<log-file>.gate0.json \
  --pretty
```

Gate 0에서 확인하는 핵심 값:

```text
right_hand_tracked_rate
xr_frame_valid_rate
raw_wrist_jump_count
tracking_loss_count
tracking_loss_duration_ms
auto_recenter_unstable_count
wrist_position_delta_p95
wrist_position_delta_max
frame_drop_rate
input_latency_ms
H13 PASS/FAIL
```

판정 규칙:

- `gate0_pass=false`이면 Gate A collection은 계속 금지한다.
- `RAW_WRIST_JUMP`는 task failure가 아니라 input quality failure다.
- `TRACKING_LOSS`가 반복되면 axis/gain 튜닝을 중단하고 handtracking 환경을 먼저 수정한다.
- `AUTO_RECENTER_UNSTABLE_RIGHT_WRIST`가 반복되면 recenter 전에 손 pose가 안정되지 않은 것이다.
- `H13=FAIL`이면 valid-to-valid raw wrist jump가 남아 있으므로 training data로 승격하지 않는다.
- invalid/unstable tracking frame은 interpolation하지 않는다. recorder는 robot action을 hold하고 `metadata.action_hold` / `metadata.hold_reason`으로 남긴다.

Gate A 재개 조건:

```text
gate0_pass=true
H13=PASS
right_hand_tracked_rate >= 0.95
xr_frame_valid_rate >= 0.95
raw_wrist_jump_count == 0
tracking_loss_count == 0
auto_recenter_unstable_count == 0
```

`scripts/run_collection_loop.sh`는 명시적 Gate A collection entrypoint이므로 최신 `*.gate0_all.json` aggregate report가 없거나 `gate0_all_pass=true` / `gate_a_collection_allowed=true`가 아니면 시작 전에 종료한다. 또한 aggregate schema, 네 개 stage 순서/개수, stage별 pass/allow/failure reason, matched input source, 단일 source id, report freshness를 검증한다. Smoke/debug/proof/audit script는 이 hard block 대상이 아니며, Gate 0 evidence를 만들거나 기존 artifact를 검증하는 용도로 계속 실행할 수 있다.

## MVP-1+ Robot Embodiment Adapter Proof 실행

여러 robot embodiment adapter가 같은 normalized trajectory contract를 emit하고
같은 data trust gate를 통과하는지 확인하려면 다음 명령을 사용한다.

```bash
uv run python scripts/run_mvp1plus_embodiment_proof.py --clean --pretty
```

성공 조건:

```text
passed=true
adapter_count=4
accepted_count=4
rejected_count=4
integrated_export.hdf5_export_exists=true
integrated_export.hdf5_inspection_clean=true
integrated_export.trainer_smoke_passed=true
```

기본 artifact 위치:

```text
storage/mvp1plus_embodiment_proof/
```

UR industrial adapter는 기본적으로 repo-local file-backed recorded-log fixture를
사용한다.

```text
fixtures/mvp1plus/universal_robots_ur_recorded_log_fixture/
```

다른 UR recorded/log directory를 검증하려면 같은 file shape를 가진 directory를
명시한다.

```bash
uv run python scripts/run_mvp1plus_embodiment_proof.py \
  --output-dir /tmp/rdf_mvp1plus_custom_ur \
  --ur-recorded-log-dir /path/to/ur_recorded_log_dir \
  --clean --pretty
```

Custom source directory에는 반드시 다음 파일이 있어야 한다.

```text
metadata.json
accepted_command_state.jsonl
rejected_command_state.jsonl
```

UR lineage evidence를 확인할 때는 proof JSON에서 UR adapter proof를 조회한다.

```bash
uv run python scripts/run_mvp1plus_embodiment_proof.py --clean --pretty > /tmp/rdf_mvp1plus.json
jq '.adapter_proofs[]
  | select(.adapter_id=="universal_robots_ur_industrial_arm")
  | .lineage_evidence
  | {source_evidence_type, source_bundle_sha256, projected_bundle_sha256}' /tmp/rdf_mvp1plus.json
```

예상 boundary:

```text
source_evidence_type=file_backed_recorded_log_fixture
source_bundle_sha256 is non-empty
projected_bundle_sha256 is non-empty
```

중요한 debugging boundary:

- `Franka`, `ROBOTIS SH5 / ROS2-DDS`, `Universal Robots UR`는 recorded/log-backed 또는 generated external-style proof source다.
- 이 proof는 physical robot readiness, live ROS2/DDS runtime, UR/RTDE runtime, real robot success, HMD readiness, policy uplift를 주장하지 않는다.
- `raw_xr_right_wrist_pose`와 `aligned_xr_right_wrist_pose`는 기존 HDF5 exporter/trainer 호환 placeholder다. HMD evidence로 해석하면 안 된다.
- `--clean`은 `storage/` 또는 system temp 하위 output만 삭제한다. repo root, home, repo parent 같은 unsafe path는 `ValueError: refusing to clean unsafe output_dir`로 막는다.
- Lineage hash mismatch가 나면 validator를 약하게 하지 말고 source files 또는 projected artifact 생성 경로가 바뀌었는지 확인한다.

Malformed source evidence를 확인할 때는 adapter projection을 직접 호출한다.

```python
from pathlib import Path

from app.services.robot_embodiment_adapters import RobotEmbodimentAdapterRegistry

adapter = RobotEmbodimentAdapterRegistry.create("franka_research_arm")
result = adapter.project_source_evidence(
    source_dir=Path("/tmp/bad_source"),
    output_dir=Path("/tmp/bad_projection"),
)
print(result.passed)
print(result.issues)
```

`accepted_command_state.jsonl`이나 `rejected_command_state.jsonl`이 `{}` 같은
malformed row이면 `command.vector missing`, `quality.rejection_reason
mismatch` 같은 structured issue가 나와야 한다. 이 경우 validator를 약하게
하지 말고 source evidence를 고친다.

## MVP-2 UR Policy A/B Harness 실행

MVP-2 Rebase first slice를 실행하려면 다음 명령을 사용한다.

```bash
uv run python scripts/run_mvp2_ur_policy_ab_harness.py --clean --refresh-mvp1plus --pretty
```

성공 조건:

```text
passed=true
harness_ready=true
rollout_ingest_contract_ready=true
learning_results_measured=false
learning_proven=false
proof_eligible=false
```

기본 artifact 위치:

```text
storage/mvp2_policy_ab_harness/
```

필수 artifact:

```text
mvp2_policy_ab_harness_report.json
mvp2_policy_eval_input_template.json
mvp2_heldout_suite_manifest.json
baseline_uncurated/baseline_uncurated_train.hdf5
candidate_curated/candidate_curated_train.hdf5
rollout_ingest_contract_fixture/ingest_contract_report.json
```

Proof audit에 MVP-2 harness summary를 연결하려면 다음 명령을 사용한다.

```bash
uv run python scripts/run_mvp1_proof_audit.py \
  --mvp2-policy-ab-harness-report storage/mvp2_policy_ab_harness/mvp2_policy_ab_harness_report.json \
  --output storage/mvp1_proof/proof_audit.json \
  --pretty
```

주의:

- `mvp2_policy_ab_harness` summary는 readiness summary다.
- Schema-only rollout fixture의 success rate는 ingest contract sanity 값이며
  policy uplift evidence가 아니다. Baseline/candidate fixture rate는
  non-comparative로 유지되어야 한다.
- UR source는 `file_backed_recorded_log_fixture` lineage gate를 통과해야 한다.
  기존 MVP-1+ output을 재사용하더라도 source/projected bundle hash가 없거나
  file-backed lineage가 아니면 harness가 실패해야 한다. 또한 lineage path와
  실제 `projected_inputs` path, per-file hash, byte size, bundle hash가 모두
  일치해야 한다.
- `passed`와 `harness_ready`는 lineage gate, UR contract validation, non-empty
  baseline/candidate export, clean HDF5 inspection, rollout ingest contract,
  schema fixture non-policy flags가 모두 true일 때만 true가 된다.
- `--clean` 없이 재실행하더라도 harness-managed output directory는 먼저
  reset되어 stale trajectory/evaluation/rollout fixture가 export에 섞이면 안 된다.
- `learning_results_measured=false`, `curated_vs_uncurated_uplift=null`,
  `learning_proven=false`, `proof_eligible=false`가 유지되어야 한다.
- 이 harness는 live UR/RTDE runtime, physical UR readiness, real robot success,
  HMD readiness를 주장하지 않는다.
- UR normalized contract validation이 실패하면 validator를 약하게 하지 말고
  MVP-1+ UR projected source, curation, export, trainer artifact lineage를 먼저
  확인한다.

## MVP-2 Learning-Proven Policy Eval 실행

MVP-2를 Closed로 판단하려면 harness readiness나 default local offline proxy가
아니라 positive external proof-grade held-out policy uplift report가 필요하다.
기본 명령은 deterministic local proxy를 생성하며, 이 결과는 MVP-2를 close하지
않는다.

```bash
uv run python scripts/run_mvp2_learning_proven_policy_eval.py \
  --clean \
  --refresh-harness \
  --refresh-mvp1plus \
  --pretty
```

기본 local proxy 실행의 기대 boundary:

```text
passed=true
learning_results_measured=true
learning_proven=false
proof_eligible=false
candidate_success_rate > baseline_success_rate
curated_vs_uncurated_uplift > 0
evidence_tier=local_offline_policy_eval_proxy
validator_evidence_tier=null
artifact_paths.policy_eval_input=null
artifact_paths.policy_eval_report=null
blockers contains "Local offline deterministic proxy cannot close MVP-2."
```

기본 artifact 위치:

```text
storage/mvp2_learning_proven_policy_eval/
```

필수 artifact:

```text
mvp2_learning_proven_report.json
mvp2_local_offline_heldout_suite_manifest.json
baseline_local_offline_rollouts.json
candidate_local_offline_rollouts.json
```

외부 trainer/evaluator에게 넘길 held-out rollout proof package template은 다음
명령으로 생성한다.

```bash
uv run python scripts/run_mvp2_learning_proven_policy_eval.py \
  --write-external-proof-template \
  --clean \
  --refresh-harness \
  --refresh-mvp1plus \
  --pretty
```

생성 위치:

```text
storage/mvp2_learning_proven_policy_eval/external_policy_eval_template/
```

생성 artifact:

```text
external_policy_eval_request.json
baseline_external_rollouts.template.json
candidate_external_rollouts.template.json
external_policy_eval_template_report.json
```

Template package의 기대 boundary:

```text
passed=true
proof_ready=false
mvp2_closed=false
template_is_not_evidence=true
required_final_source_kind=external_heldout_policy_eval
heldout_suite.scenario_ids=["TODO_external_heldout_scenario_00"]
```

주의: 이 template은 evidence가 아니다. `baseline_external_rollouts.template.json`,
`candidate_external_rollouts.template.json`를 그대로 `--baseline-results`,
`--candidate-results`에 넣으면 wrapper가 validator 호출 전에 차단해야 한다.

External proof-grade rollout result를 주입하면 `mvp2_policy_eval_input.json`와
`mvp2_policy_eval_report.json`가 추가로 생성되고, 다음 조건이 모두 맞을 때만
MVP-2 Closed가 된다.

```text
learning_results_measured=true
learning_proven=true
proof_eligible=true
evidence_tier=external_heldout_policy_eval
validator_evidence_tier=heldout_policy_eval
candidate_success_rate > baseline_success_rate
curated_vs_uncurated_uplift > 0
```

External rollout JSON은 최소한 다음 provenance를 포함해야 한다.

```json
{
  "source_kind": "external_heldout_policy_eval",
  "proof_role": "external_trainer_policy_eval",
  "policy_artifact_id": "external_policy_artifact_id",
  "trainer": "external_eval_runner",
  "eval_runner": "external_heldout_eval_runner",
  "heldout_suite": {
    "id": "external_ur_heldout_policy_eval_suite",
    "held_out": true,
    "task_type": "connector_insertion",
    "source_kind": "external_trainer_eval_suite",
    "proof_role": "external_policy_eval_suite",
    "scenario_ids": ["scenario_0"]
  },
  "rollout_results": [
    {"rollout_id": "external_rollout_0", "scenario_id": "scenario_0", "success": true}
  ]
}
```

`heldout_suite.id` 또는 `heldout_suite.scenario_ids`에 `schema_only`가 남아 있으면
proof-grade external evidence가 아니다. 이 경우 wrapper는
`run_mvp1c_real_policy_eval.py` 호출 전에 차단해야 한다.

현재 MVP-2 harness HDF5로 Isaac headless smoke를 실행한 결과도 Closed 조건을
만족하지 못했다.

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh \
  scripts/run_mvp1c_isaac_policy_ab_smoke.py \
  --baseline-hdf5 storage/mvp2_policy_ab_harness/baseline_uncurated/baseline_uncurated_train.hdf5 \
  --candidate-hdf5 storage/mvp2_policy_ab_harness/candidate_curated/candidate_curated_train.hdf5 \
  --template storage/mvp2_policy_ab_harness/mvp2_policy_eval_input_template.json \
  --output-dir /tmp/rdf-mvp2-isaac-rollout-check \
  --rollouts-per-policy 10 \
  --max-steps 150 \
  --seed-start 9100 \
  --action-scale 1.0 \
  --evidence-tier isaac_headless_policy_eval_smoke \
  --pretty
```

결과:

```text
passed=true
evidence_tier=isaac_headless_policy_eval_smoke
proof_eligible=false
baseline_success_rate=0.0
candidate_success_rate=0.0
```

`--action-scale 20` diagnostic도 2 rollout smoke에서 baseline/candidate 모두
`0.0`이었다. 따라서 현재 lightweight linear BC smoke와 fixture-scale UR harness
데이터로는 positive curated > uncurated held-out policy uplift를 주장할 수 없다.

Negative 또는 tie 결과를 재현하려면 다음 profile을 사용한다.

```bash
uv run python scripts/run_mvp2_learning_proven_policy_eval.py \
  --clean \
  --refresh-harness \
  --offline-profile negative \
  --pretty

uv run python scripts/run_mvp2_learning_proven_policy_eval.py \
  --clean \
  --refresh-harness \
  --offline-profile tie \
  --pretty
```

이 경우도 local proxy이므로 예상 boundary는 다음과 같다.

```text
passed=true
learning_results_measured=true
learning_proven=false
proof_eligible=false
```

Schema-only rollout fixture를 직접 넣으면 proof validator 호출 전에 차단되어야
한다.

```bash
uv run python scripts/run_mvp2_learning_proven_policy_eval.py \
  --clean \
  --baseline-results storage/mvp2_policy_ab_harness/rollout_ingest_contract_fixture/baseline_rollouts.schema_fixture.json \
  --candidate-results storage/mvp2_policy_ab_harness/rollout_ingest_contract_fixture/candidate_rollouts.schema_fixture.json \
  --pretty
```

예상 boundary:

```text
learning_results_measured=false
learning_proven=false
proof_eligible=false
validator_evidence_tier=null
artifact_paths.policy_eval_report=null
blockers contains "Schema-only rollout ingest fixture cannot close MVP-2."
```

Proof audit에 MVP-2 Closed report를 연결하려면 다음 명령을 사용한다.

```bash
uv run python scripts/run_mvp1_proof_audit.py \
  --mvp2-learning-proven-report storage/mvp2_learning_proven_policy_eval/mvp2_learning_proven_report.json \
  --output storage/mvp1_proof/proof_audit.json \
  --pretty
```

주의:

- `run_mvp2_learning_proven_policy_eval.py`는 policy를 train하거나 live rollout을
  실행하지 않는다.
- Local offline path는 deterministic quality signal로 proxy rollout outcome을
  만든다. 이 경로는 positive delta가 있어도 `learning_proven=false`다.
- 더 강한 claim은 외부 trainer/evaluator rollout result를 `--baseline-results`,
  `--candidate-results`로 주입해야 한다.
- `run_mvp1c_real_policy_eval.py`의 validator rule을 약하게 만들면 안 된다.
- Harness의 `mvp2_ur_policy_ab_schema_only_heldout_suite`는 proof-grade eval suite가
  아니다. External proof path의 policy eval input/report는 external held-out suite
  id/source_kind/proof_role을 보존해야 한다.
- 이 report는 real robot success, physical UR readiness, HMD/OpenXR readiness,
  Isaac rollout evidence를 주장하지 않는다.

### MVP-2A transition / policy readiness 확인

현재 UR harness는 candidate curated train view에 대해 `run_mvp2_learning_sanity.py`를
자동 실행하고 다음 artifact를 생성한다.

```bash
uv run python scripts/run_mvp2_ur_policy_ab_harness.py \
  --clean \
  --refresh-mvp1plus \
  --pretty
```

확인할 파일:

```text
storage/mvp2_policy_ab_harness/mvp2a_transition_policy_readiness_report.json
storage/mvp2_policy_ab_harness/mvp2a_policy_trainer_selection_report.json
storage/mvp2_policy_ab_harness/candidate_curated/mvp2_learning_sanity_report.json
storage/mvp2_policy_ab_harness/candidate_curated/curation_manifest.json
storage/mvp2_policy_ab_harness/candidate_curated/split_manifest.json
```

현재 예상 결과:

```text
harness_ready=true
mvp2a_transition_policy_readiness.passed=true
mvp2a_policy_ab_ready=true
stronger_policy_trainer_selected=true
selected_policy_class=phase_conditioned_sequence_bc_policy_v0
selected_trainer=rdf_phase_conditioned_sequence_bc_trainer_contract_v0
next_recommended_gate=external_heldout_policy_rollout_generation
candidate transition phases present=["APPROACH", "CONTACT", "INSERT", "SEAT"]
candidate transition phases missing=[]
candidate train_set_overfit_passed=true
learning_proven=false
```

해석:

- HDF5 export와 loader/train-set overfit sanity는 현재 candidate view를 읽을 수 있다.
- candidate view는 이제 `APPROACH`, `CONTACT`, `INSERT`, `SEAT` transition coverage를
  모두 포함한다.
- stronger policy/trainer contract는
  `phase_conditioned_sequence_bc_policy_v0` /
  `rdf_phase_conditioned_sequence_bc_trainer_contract_v0`로 선택됐다.
- 이 readiness pass는 policy training이나 positive uplift 증거가 아니다.
- MVP-2 Closed 실패 사유는 이제 proof-grade external held-out rollout JSON의
  positive curated > uncurated uplift 부재로 분리해서 기록해야 한다.

### MVP-2 phase-conditioned local proxy eval 실행

`MVP-2A` readiness가 통과한 뒤 phase-conditioned local proxy evidence를 생성하려면
다음 명령을 사용한다. 이 명령은 positive proxy delta를 보존하지만 MVP-2 Closed를
주장하지 않는다.

```bash
uv run python scripts/run_mvp2_phase_conditioned_external_eval.py \
  --clean \
  --refresh-harness \
  --refresh-mvp1plus \
  --pretty
```

예상 핵심 결과:

```text
passed=true
mvp2_closed=false
proxy_results_measured=true
learning_results_measured=true
learning_proven=false
proof_eligible=false
evidence_tier=local_phase_conditioned_policy_eval_proxy
validator_evidence_tier=null
baseline_success_rate=0.4
candidate_success_rate=0.9
curated_vs_uncurated_uplift=0.5
```

생성되는 주요 파일:

```text
storage/mvp2_phase_conditioned_local_eval_proxy/mvp2_phase_conditioned_local_eval_proxy_report.json
storage/mvp2_phase_conditioned_local_eval_proxy/phase_conditioned_proxy_rollouts/baseline_uncurated_proxy_rollouts.json
storage/mvp2_phase_conditioned_local_eval_proxy/phase_conditioned_proxy_rollouts/candidate_curated_proxy_rollouts.json
storage/mvp2_phase_conditioned_local_eval_proxy/mvp2_learning_proven_policy_eval/mvp2_learning_proven_report.json
```

Proof audit에 연결하면 local proxy evidence가 MVP-2 proof로 승격되지 않는지 확인할
수 있다.

```bash
uv run python scripts/run_mvp1_proof_audit.py \
  --mvp2-policy-ab-harness-report storage/mvp2_policy_ab_harness/mvp2_policy_ab_harness_report.json \
  --mvp2-learning-proven-report storage/mvp2_phase_conditioned_local_eval_proxy/mvp2_learning_proven_policy_eval/mvp2_learning_proven_report.json \
  --output storage/mvp1_proof/proof_audit.json \
  --pretty
```

확인할 값:

```text
learning_proven_policy_uplift_achieved=false
mvp2_learning_proven_policy_eval.learning_proven=false
mvp2_policy_uplift_proof.learning_proven=false
summary.learning_proven=false
```

주의:

- 이 경로는 offline phase-conditioned held-out task-state proxy evaluator다.
- positive proxy delta가 있어도 MVP-2 Closed evidence가 아니다.
- real robot success, physical UR readiness, Isaac runtime success,
  HMD/OpenXR readiness를 주장하지 않는다.
- `run_mvp2_learning_proven_policy_eval.py`와
  `run_mvp1c_real_policy_eval.py` validator를 우회하면 안 된다.
- schema-only rollout fixture, default local deterministic proxy, phase-conditioned
  local proxy는 모두 MVP-2 Closed evidence가 아니다.
- `--clean --refresh-harness --refresh-mvp1plus` proof commands는 shared
  `storage/`를 갱신하므로 순차 실행한다.

### MVP-2B dedicated Isaac proof evaluator 실행

MVP-2B runner는 전용 connector insertion proof evaluator의 artifact shape를
생성한다. 현재 deterministic backend는 CI와 plumbing 검증용이며, MVP-2 Closed
proof가 아니다.

```bash
uv run python scripts/run_mvp2b_isaac_proof_evaluator.py \
  --clean \
  --skip-isaac \
  --pretty
```

예상 boundary:

```text
passed=true
mvp2_closed=false
learning_proven=false
proof_eligible=false
runtime_backend=skipped
```

deterministic evaluator backend로 기존 MVP-2 learning validator ingest까지
검증하려면 다음을 실행한다.

```bash
uv run python scripts/run_mvp2b_isaac_proof_evaluator.py \
  --clean \
  --use-deterministic-eval-backend \
  --pretty
```

예상 핵심 결과:

```text
passed=true
runtime_backend=deterministic_test_backend
proof_runtime=test_only_not_isaac
learning_validator.learning_proven=true
learning_validator.proof_eligible=true
baseline_success_rate=0.4
candidate_success_rate=0.7
curated_vs_uncurated_uplift=0.3
mvp2_closed=false
proof_eligible=false
blockers contains "Dedicated Isaac runtime gate did not pass."
```

주요 artifact:

```text
storage/mvp2b_isaac_proof_evaluator/scenario_manifest.json
storage/mvp2b_isaac_proof_evaluator/curation_manifest.json
storage/mvp2b_isaac_proof_evaluator/baseline_uncurated_train.hdf5
storage/mvp2b_isaac_proof_evaluator/candidate_curated_train.hdf5
storage/mvp2b_isaac_proof_evaluator/baseline_policy_artifact.json
storage/mvp2b_isaac_proof_evaluator/candidate_policy_artifact.json
storage/mvp2b_isaac_proof_evaluator/external_rollouts/baseline_external_rollouts.json
storage/mvp2b_isaac_proof_evaluator/external_rollouts/candidate_external_rollouts.json
storage/mvp2b_isaac_proof_evaluator/mvp2_learning_proven_policy_eval/mvp2_learning_proven_report.json
storage/mvp2b_isaac_proof_evaluator/visual_evidence/metric_trace_comparison.png
```

MVP-2B closure rule:

```text
existing_evaluator.learning_proven=true
AND existing_evaluator.proof_eligible=true
AND runtime_gate.passed=true
AND runtime_backend=isaac_runtime
AND proof_runtime=dedicated_isaac_connector_insertion_evaluator
AND curated_vs_uncurated_uplift >= 0.20
```

주의:

- `--skip-isaac`와 `--use-deterministic-eval-backend`는 절대 MVP-2를 닫지 않는다.
- deterministic backend가 positive uplift JSON을 만들더라도 top-level
  `mvp2_closed=false`, `proof_eligible=false`를 유지해야 한다.
- HMD/OpenXR, smoke-only result, local proxy, schema/template artifact, visual-only
  evidence는 계속 MVP-2 proof로 쓰지 않는다.
- actual Isaac runtime backend는 구현되어 있다. 다음 명령은 실제
  `Isaac-Factory-PegInsert-Direct-v0` headless rollout을 실행한다.

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2b_isaac_proof_evaluator.py \
  --output-dir /tmp/rdf-mvp2b-isaac-runtime-signed-offset-step150-scale20 \
  --clean \
  --rollouts-per-policy 20 \
  --max-steps 150 \
  --action-scale 20 \
  --bootstrap-iterations 200 \
  --pretty
```

현재 확인된 actual Isaac 결과:

```text
runtime_backend=isaac_runtime
proof_runtime=dedicated_isaac_connector_insertion_evaluator
runtime_gate.passed=true
actual_rollouts_per_policy=20
baseline_success_rate=0.0
candidate_success_rate=0.0
curated_vs_uncurated_uplift=0.0
mvp2_closed=false
proof_eligible=false
```

해석:

- runtime gate 통과는 Isaac task가 실행되고 rollout artifact가 생성됐다는 뜻이다.
- MVP-2 Closed는 아니다. positive curated > uncurated held-out uplift가 없다.
- candidate는 일부 rollout에서 `insertion_depth_m=0.034`까지 도달하지만,
  lateral/orientation/stability gate를 동시에 10 consecutive step 만족하지 못한다.
- 같은 held-out manifest 결과를 본 뒤 `success_metric`, threshold,
  hyperparameter, action scale을 사후 조정해서 close하면 안 된다.
- 다음 유효 디버깅 방향은 새 pre-registered calibration/train slice다.
  held-out과 분리된 calibration split에서 action adapter를 선택하고, fresh
  held-out manifest로 다시 proof attempt를 해야 한다.

## MVP-2C Isaac Training / Calibration Slice

MVP-2C runner:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2c-skip-pretty \
  --clean \
  --skip-isaac \
  --pretty
```

위 명령은 artifact shape와 non-closing boundary만 확인한다.

```text
runtime_backend=skipped
train_generation_runtime_backend=deterministic_test_backend
mvp2_closed=false
mvp2c_close_minimum_passed=false
```

Deterministic backend smoke:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2c-deterministic-pretty \
  --clean \
  --use-deterministic-eval-backend \
  --rollouts-per-policy 20 \
  --bootstrap-iterations 200 \
  --pretty
```

이 경로는 positive uplift가 나와도 절대 MVP-2C를 닫지 않는다.

```text
runtime_backend=deterministic_test_backend
train_generation_runtime_backend=deterministic_test_backend
baseline_success_rate=0.4
candidate_success_rate=0.7
curated_vs_uncurated_uplift=0.3
learning_validator.evidence_tier=local_phase_conditioned_policy_eval_proxy
learning_validator.proof_eligible=false
mvp2_closed=false
mvp2c_close_minimum_passed=false
```

Actual Isaac runtime attempt:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2c-isaac-runtime-final \
  --clean \
  --rollouts-per-policy 20 \
  --max-steps 150 \
  --action-scale 20 \
  --bootstrap-iterations 200
```

최신 actual held-out 결과:

```text
runtime_backend=isaac_runtime
runtime_gate.passed=true
proof_runtime=dedicated_isaac_connector_insertion_evaluator
train_generation_runtime_backend=deterministic_test_backend
train_generation_runtime_gate.runtime_backend=isaac_runtime_import_probe_only
train_generation_runtime_gate.passed=false
actual_rollouts_per_policy=20
baseline_success_rate=0.0
candidate_success_rate=0.0
curated_vs_uncurated_uplift=0.0
mvp2_closed=false
mvp2c_close_minimum_passed=false
stronger_public_evidence_target_passed=false
```

Post-review hardening 이후 현재 코드 기준:

```text
Isaac import probe만으로는 train_generation_runtime_gate.passed=true가 되지 않는다.
actual_train_generation_evidence=true와
training_trajectory_source=isaac_runtime_scripted_expert_rollout이 있어야 한다.
현재 MVP-2C train material은 deterministic domain generator이므로
train_generation_runtime_backend=deterministic_test_backend로 fail-closed된다.
```

해석:

- MVP-2C code path와 actual Isaac runtime dispatch는 동작한다.
- held-out runtime gate가 통과해도 actual Isaac train-generation evidence와 positive
  curated > uncurated held-out uplift가 모두 없으면 MVP-2C는 닫히지 않는다.
- 같은 held-out 결과를 본 뒤 success metric, threshold, action scale,
  baseline mix, selector score, policy hyperparameter를 사후 조정하면 안 된다.
- 공개/투자자-facing 문구에서는 20-rollout result를 engineering minimum으로만
  표현하고, `stronger_public_evidence_target_passed=true` 전에는 robust benchmark
  claim을 하지 않는다.

### 2026-06-11 최신 actual adapter attempt

`isaac_signed_xy_downward_servo_v0` adapter는 현재 다음 runtime config를 사용한다.

```text
xy_source=state_feedback
xy_state_feedback_gain=4.0
xy_action_clip=0.035
z_action_scale=24.0
z_action_clip=0.12
rotation_action_scale=1.0
stable_hold_action=[0.0, 0.0, -0.02, 0.0, 0.0, 0.0, 1.0]
```

최신 actual run:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2c-isaac-adapter-v6 \
  --clean \
  --rollouts-per-policy 20 \
  --max-steps 150 \
  --bootstrap-iterations 200
```

결과:

```text
runtime_backend=isaac_runtime
runtime_gate.passed=true
baseline_success_rate=0.15
candidate_success_rate=0.15
curated_vs_uncurated_uplift=0.0
train_generation_runtime_backend=deterministic_test_backend
mvp2_closed=false
```

해석:

- actual Isaac evaluator는 실행된다.
- 현재 adapter는 일부 성공 삽입을 만들지만 curated candidate와 uncurated baseline을
  분리하지 못한다.
- `held_out=6000-6019` 결과를 본 상태에서 success metric, threshold, baseline mix,
  selector score, action scale, policy hyperparameter를 더 조정하면 p-hacking risk가
  있다.
- 다음 디버깅은 새 pre-registered slice에서 해야 한다.

## MVP-2D Oracle Repair Debug Flow

Use this flow when actual Isaac train-generation or held-out A/B fails after the
MVP-2D oracle repair.

1. First verify oracle viability:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/check_peg_insert_viability.py \
  --task Isaac-Factory-PegInsert-Direct-v0 \
  --seed 7000 \
  --oracle-steps 220 \
  --replay-scope accepted \
  --output /tmp/rdf-mvp2d-factory-oracle-repair.json \
  --pretty
```

Expected repaired evidence:

```text
scripted_oracle_passed=true
policy_loop_viability=true
selected_success_evaluator=rdf_peg_in_hole
horizon_limited=true
effective_steps=145
```

If this fails, debug `target_held_base_pos`, `fixed_pos_delta_m`,
`reset_or_target_jump_detected`, and `max_episode_length` before running any
policy A/B.

2. Then run train-generation plus held-out only on a fresh pre-registered
   scenario profile:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2d-full-proof-v04 \
  --clean \
  --scenario-profile v0_4 \
  --rollouts-per-policy 20 \
  --max-steps 145 \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --action-scale 1.0 \
  --pretty
```

Latest known non-closing result:

```text
train_generation_runtime_gate.passed=true
train_generation_runtime_gate.generated_success_count=5
baseline_success_rate=0.15
candidate_success_rate=0.15
curated_vs_uncurated_uplift=0.0
mvp2_closed=false
```

Interpretation:

- Oracle repair is no longer the active blocker.
- Actual Isaac train-generation can produce success traces.
- The active blocker is now policy/trainer separation: candidate does not beat
  baseline on fresh held-out success.

Do not:

- lower RDF thresholds after seeing `v0_3` or `v0_4`;
- retune action scale, selector score, or baseline mix against those held-out
  results;
- claim MVP-2 Closed from oracle success or train-generation success alone.

Next valid debug branch:

- pre-register a new `v0_5` slice;
- improve candidate policy/trainer or calibration-only adapter selection before
  held-out;
- freeze on calibration only;
- run one fresh held-out A/B and close only if uplift is positive and at least
  `0.20`.

## MVP-2D v0.5 Residual Servo BC Debug Flow

Use this flow for the `v0_5` residual-servo BC proof slice.

1. Run the train-generation probe only. Do not run held-out yet.

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2d-v05-train-gate \
  --clean \
  --scenario-profile v0_5 \
  --train-generation-probe-only \
  --max-steps 145 \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

Close-precondition for this gate:

```text
runtime_backend=isaac_runtime
generated_success_count >= 20
required_success_count=20
success_trace_cap=40
actual_train_generation_evidence=true
```

Latest known result:

```text
/tmp/rdf-mvp2d-v05-train-gate/train_generation_runtime_gate.json
passed=false
generated_rollout_count=40
generated_success_count=5
required_success_count=20
actual_train_generation_evidence=false
```

2. If `generated_success_count < 20`, stop. Do not run held-out A/B.

The runner should report:

```text
heldout_schedule.scheduled=false
heldout_schedule.blocked_by_train_generation_gate=true
mvp2_closed=false
```

3. Only after the train-generation gate passes, run the full proof:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2d-v05-full-proof \
  --clean \
  --scenario-profile v0_5 \
  --rollouts-per-policy 20 \
  --max-steps 145 \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --action-scale 1.0 \
  --pretty
```

Do not:

- run held-out `18000-18019` after a failed train-generation gate;
- lower the `20` success-trace minimum after seeing the failed gate;
- tune against held-out output and reuse the same held-out range;
- claim MVP-2 Closed from residual trainer artifacts or skip/deterministic runs.

## MVP-2E v0.6a Runtime Capture-radius Preflight Debug Flow

Use this flow before running the v0.6 repair probe or fixed 40-run train gate.
The preflight is geometry/runtime evidence only; it cannot close MVP-2.

1. Run the runtime capture-radius preflight.

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2e-v06a-capture-radius \
  --clean \
  --scenario-profile v0_6 \
  --capture-radius-probe-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

Expected artifacts:

```text
/tmp/rdf-mvp2e-v06a-capture-radius/capture_radius_probe.json
/tmp/rdf-mvp2e-v06a-capture-radius/chamfer_preflight.json
/tmp/rdf-mvp2e-v06a-capture-radius/capture_radius_preflight_result.json
```

2. Interpret the branch.

```text
Branch A/B:
  repair_probe_allowed=true
  train_generation_gate_allowed=false
  train_generation_gate_status=pending_repair_probe
  next valid step: repair probe only

Branch C:
  repair_probe_allowed=false
  train_generation_gate_allowed=false
  train_generation_gate_status=blocked_by_preflight
  next valid step: debug runtime preflight, not repair/held-out
```

Latest known result:

```text
preflight_branch=B
runtime_loaded=true
capture_radius_m=approximate
runtime_error="v0_6a capture-radius trial exceeded runtime deadline"
repair_probe_allowed=true
train_generation_gate_allowed=false
train_generation_gate_status=pending_repair_probe
```

Branch B repair probe was run on 2026-06-11:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2e-v06a-capture-radius \
  --scenario-profile v0_6 \
  --train-generation-probe-only \
  --repair-probe-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

Latest repair probe result:

```text
runtime_backend=isaac_runtime
runtime_gate.passed=true
green_light_for_40_run_gate=false
hard_stop=true
hold_mode_passed=false
lateral_success_mode_passed=false
lateral_divergence_stopped=false

seed 16023: env_native_max_consecutive_success_steps=0,
            rdf_peg_in_hole_metric.summary.success=true
seed 16042: env_native_max_consecutive_success_steps=0,
            rdf_peg_in_hole_metric.summary.success=true
seed 16096: env_native_max_consecutive_success_steps=0,
            rdf_peg_in_hole_metric.summary.success=true
```

Interpretation:

- This is a correct fail-closed result, not an Isaac runtime crash.
- Fixed 40-run train-generation gate remains blocked.
- The next debug target is the semantic mismatch between RDF secondary geometry
  and env-native `_get_curr_successes`, not held-out evaluation.

Before running the fixed 40 train gate, verify:

```text
repair_probe_gate.green_light_for_40_run_gate=true
repair_probe_gate.proof_runtime=isaac_scripted_expert_repair_probe
repair_probe_gate.probe_seeds=[16023, 16042, 16096]
repair_probe_gate.chamfer_preflight.chamfer_preflight_sha256 matches the current v0.6a preflight
repair_probe_gate.v0_6a_post_repair_probe_gate.green_light_for_40_run_gate=true
repair_probe_gate.repair_probe_gate_sha256 validates
recomputed evaluate_v06_repair_probe_gate(repair_probe_gate.probe_results) matches
  hold_mode_passed
  lateral_success_mode_passed
  lateral_divergence_stopped
  green_light_for_40_run_gate
  hard_stop
```

Without that repair green light, the train-generation gate must report:

```text
reason=v0_6_repair_probe_not_green
runtime_backend=isaac_runtime_not_started
```

Next diagnostic order:

- instrument env-native `_get_curr_successes` inputs and per-keypoint distances
  during the same three repair probe seeds;
- compare native keypoint/threshold conditions against RDF `relative_x_m`,
  `relative_y_m`, `lateral_error_m`, `insertion_depth_m`, and
  `orientation_error_deg`;
- verify whether `insertion_depth_m` and RDF lateral geometry are computed in
  the same frame and task semantics as the Factory native success function;
- only after that mismatch is explained, decide whether the controller,
  trace schema, or success extraction needs a minimal repair.

If Branch C occurs in a future capture-radius preflight run, debug in this order:

- verify `_held_asset` teleport changes `held_pos` after `write_root_pose_to_sim`;
- verify `_get_curr_successes` is available after teleport and no-action stepping;
- verify whether the zero-offset pose should be checked before vertical push;
- verify whether the Direct Factory task action dimension maps `action[2]` to the intended vertical push;
- if empirical probing remains untrustworthy, use runtime USD stage inspection as the fallback diagnostic.

Do not:

- open held-out `21000-21049`;
- run the fixed 40 train gate;
- run repair probe without verified Branch A/B `chamfer_preflight.json` and matching
  `capture_radius_probe.json`;
- treat an abbreviated `repair_probe_gate.json` with only
  `green_light_for_40_run_gate=true` as valid proof;
- treat a hash-valid `repair_probe_gate.json` as valid when top-level gate flags
  do not match recomputed per-seed `probe_results`;
- change env-native success authority or `stable_steps_required=10` from this blocker.

## MVP-2E v0.6b RDF/native Metric Repair Debug Flow

v0.6b supersedes the v0.6a interpretation where RDF secondary geometry appeared
to pass while Factory env-native success remained false.

The v0.6b repair records Factory native base/target diagnostics directly:

```text
env_native_diagnostics_source=factory_utils_base_target
env_native_z_disp_m
env_native_height_threshold_m
env_native_success_mask
env_native_success
held_base_pose_w
target_held_base_pose_w
legacy_positive_z_disp_m
runtime_depth_feature_m
```

The semantic validator must pass before any repair gate can be considered:

```text
repair_probe_gate.v0_6b_native_metric_trace_validation.valid=true
repair_probe_gate.v0_6b_native_metric_trace_validation.validated_trace_count > 0
```

Latest known v0.6b runtime command:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2e-v06b-native-metric-repair \
  --scenario-profile v0_6 \
  --train-generation-probe-only \
  --repair-probe-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

Latest v0.6b result:

```text
runtime_backend=isaac_runtime
runtime_gate.passed=true
v0_6b_native_metric_trace_validation.valid=true
validated_trace_count=450
green_light_for_40_run_gate=false
hard_stop=true

seed 16023: env_native_max_consecutive_success_steps=0,
            min_z_disp=0.036099,
            runtime_depth_feature_m=0.0,
            rdf_peg_in_hole_metric.summary.success=false
seed 16042: env_native_max_consecutive_success_steps=0,
            min_z_disp=0.031983,
            runtime_depth_feature_m=0.0,
            rdf_peg_in_hole_metric.summary.success=false
seed 16096: env_native_max_consecutive_success_steps=0,
            min_z_disp=0.039618,
            runtime_depth_feature_m=0.0,
            rdf_peg_in_hole_metric.summary.success=false
```

Interpretation:

- This is a correct fail-closed result.
- The v0.6a RDF/env-native semantic mismatch is resolved.
- RDF secondary geometry no longer claims success when native seating progress is zero.
- The current blocker is controller/action behavior: the probe stays in
  `APPROACH` with `env_native_z_disp_m` roughly 32-49mm above target while the
  native height threshold is 1mm.

Next diagnostic order:

- inspect active phase transition and z-gate conditions for the three probe seeds;
- verify the action adapter sends a nonzero downward component after alignment;
- compare commanded z action, actual held base z displacement, and phase label per step;
- verify whether lateral divergence cap uses max initial offset in a way that
  marks already-hard lateral probes as divergence even after late centering;
- only after this controller/action diagnosis should INSERT push, correction gain,
  or phase transition thresholds be changed.

Do not:

- weaken `env_native_success` or `stable_steps_required=10`;
- use `legacy_positive_z_disp_m` as `runtime_depth_feature_m`;
- promote RDF secondary geometry to closure authority;
- run fixed 40-run train-generation gate until
  `green_light_for_40_run_gate=true` and v0.6b semantic validation passes;
- open held-out `21000-21049`.

## MVP-2E v0.6c controller/action diagnosis

v0.6c는 success metric을 바꾸지 않고 controller/action path만 계측한다.

재현 명령:

```bash
mkdir -p /tmp/rdf-mvp2e-v06c-controller-action-diagnosis
cp /tmp/rdf-mvp2e-v06b-native-metric-repair/chamfer_preflight.json \
  /tmp/rdf-mvp2e-v06c-controller-action-diagnosis/chamfer_preflight.json
cp /tmp/rdf-mvp2e-v06b-native-metric-repair/capture_radius_probe.json \
  /tmp/rdf-mvp2e-v06c-controller-action-diagnosis/capture_radius_probe.json
cp /tmp/rdf-mvp2e-v06b-native-metric-repair/capture_radius_preflight_result.json \
  /tmp/rdf-mvp2e-v06c-controller-action-diagnosis/capture_radius_preflight_result.json

/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2e-v06c-controller-action-diagnosis \
  --scenario-profile v0_6 \
  --train-generation-probe-only \
  --repair-probe-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

핵심 artifact:

```text
/tmp/rdf-mvp2e-v06c-controller-action-diagnosis/controller_action_diagnosis.json
```

현재 v0.6c 결과:

```text
diagnosis_complete=true
root_cause_hypothesis=controller_phase_vocabulary_mismatch_blocks_z_motion
trace_rows=450
rows_with_diagnostics=450
raw_negative_z_action_steps=450
pre_controller_negative_z_action_steps=450
final_negative_z_action_steps=0
z_motion_suppressed_steps=450
phase_vocabulary_mismatch_steps=450
z_motion_block_reason_counts.controller_phase_vocabulary_mismatch=450
heldout_opened=false
fixed_40_run_gate_opened=false
```

해석:

- raw policy와 pre-controller adapter는 음수 z push를 만든다.
- final action에서는 z가 0으로 억제된다.
- `v06_phase_controller_step()`는 `ALIGN/DESCEND/INSERT/HOLD` 상태를 기대하지만
  trace row는 `APPROACH/CONTACT/INSERT/SEAT` phase vocabulary를 전달한다.
- 그 결과 active controller가 `APPROACH`를 인식하지 못하고 `z_motion_allowed=false`로
  유지한다.

다음 fix 전 제한:

- 40-run train-generation gate 실행 금지.
- held-out `21000-21049` 접근 금지.
- `env_native_success`, `stable_steps_required=10`, native height threshold 완화 금지.
- 다음 변경은 controller phase vocabulary/state persistence만 겨냥해야 한다.

## MVP-2E v0.6d controller phase vocabulary fix

v0.6d는 success metric을 바꾸지 않고 trace phase vocabulary를 active controller
vocabulary로 변환한다.

핵심 변경:

```text
APPROACH -> ALIGN
CONTACT  -> DESCEND
INSERT   -> INSERT
SEAT     -> HOLD
```

재현 명령:

```bash
rm -rf /tmp/rdf-mvp2e-v06d-controller-phase-fix
mkdir -p /tmp/rdf-mvp2e-v06d-controller-phase-fix
cp /tmp/rdf-mvp2e-v06c-controller-action-diagnosis/chamfer_preflight.json \
  /tmp/rdf-mvp2e-v06d-controller-phase-fix/chamfer_preflight.json
cp /tmp/rdf-mvp2e-v06c-controller-action-diagnosis/capture_radius_probe.json \
  /tmp/rdf-mvp2e-v06d-controller-phase-fix/capture_radius_probe.json
cp /tmp/rdf-mvp2e-v06c-controller-action-diagnosis/capture_radius_preflight_result.json \
  /tmp/rdf-mvp2e-v06d-controller-phase-fix/capture_radius_preflight_result.json

/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2e-v06d-controller-phase-fix \
  --scenario-profile v0_6 \
  --train-generation-probe-only \
  --repair-probe-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

핵심 artifact:

```text
/tmp/rdf-mvp2e-v06d-controller-phase-fix/repair_probe_gate.json
```

현재 v0.6d 결과:

```text
green_light_for_40_run_gate=false
hard_stop=true
v0_6b_native_metric_trace_validation.valid=true
phase_vocabulary_mismatch_steps=0
final_negative_z_action_steps=269
root_cause_hypothesis=physics_or_action_mapping_does_not_convert_negative_z_to_seating_progress
```

해석:

- v0.6c의 `controller_phase_vocabulary_mismatch_blocks_z_motion` blocker는 해결됐다.
- final action에서 negative z가 실제로 나온다.
- repair probe는 아직 green이 아니다.
- `16042`는 env-native success를 달성했지만 diagnostic divergence cap이
  high-initial-lateral probe에 부적합해 fail 처리된다.
- `16096`은 align에 너무 오래 걸려 horizon 내 env-native 10-consec success에 실패한다.

다음 진단 순서:

- v0.6d 결과를 소급 통과 처리하지 않는다.
- v0.6e를 별도 pre-registered slice로 분리한다.
- diagnostic-only divergence rule을 high-initial-lateral probe에 맞게 재검토한다.
- severe seed `16096`의 align authority / horizon usage를 trace로 먼저 분석한다.
- 그 전까지 fixed 40-run train gate와 held-out `21000-21049`는 계속 금지다.

## MVP-2E v0.6e repair-probe-only result

v0.6e는 다음 경계를 추가한다.

```text
capture_radius_m must be numeric.
capture-radius probe must be geometry-isolated:
  xy_correction_enabled=false
  yaw_correction_enabled=false
  z_push_mode=straight_down_bounded
env-native 10-consecutive success is primary authority.
secondary divergence diagnostics cannot veto env-native pass.
z push is blocked while lateral_error_m > capture_radius_m.
fixed 40-run gate and held-out 21000-21049 remain closed.
```

재현 명령:

```bash
rm -rf /tmp/rdf-mvp2e-v06e-repair-probe-green
mkdir -p /tmp/rdf-mvp2e-v06e-repair-probe-green

/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2e-v06e-repair-probe-green \
  --scenario-profile v0_6 \
  --capture-radius-probe-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty

/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2e-v06e-repair-probe-green \
  --scenario-profile v0_6 \
  --train-generation-probe-only \
  --repair-probe-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

핵심 artifact:

```text
/tmp/rdf-mvp2e-v06e-repair-probe-green/capture_radius_preflight_result.json
/tmp/rdf-mvp2e-v06e-repair-probe-green/controller_repair_config.json
/tmp/rdf-mvp2e-v06e-repair-probe-green/repair_probe_gate.json
```

현재 v0.6e 결과:

```text
capture_radius_m=0.0001
preflight_branch=B
runtime_error=v0_6a capture-radius trial exceeded runtime deadline
direction max successful deltas:
  +x=0.0002
  -x=0.0002
  +y=0.0001
  -y=0.0001

green_light_for_40_run_gate=false
hard_stop=true
fixed_40_run_gate_opened=false
heldout_opened=false

16023 env_native_rollout_success=false, max_consecutive=0, max_insertion_depth_m=0
16042 env_native_rollout_success=false, max_consecutive=0, max_insertion_depth_m=0
16096 env_native_rollout_success=false, max_consecutive=0, max_insertion_depth_m=0
```

해석:

- numeric capture radius 문제는 해결됐다.
- runtime capture probe는 모든 방향에서 최소 `0.0001m` straight-down success를 확인했다.
- 하지만 `capture_radius_m=0.0001`을 그대로 z-push gate로 쓰면 repair probe seed들이
  모두 `APPROACH`에 머문다.
- 세 seed 모두 lateral을 충분히 줄였지만 `lateral_error_m <= 0.0001` 조건에는 도달하지
  못해 z descent가 억제되고, 결과적으로 `max_insertion_depth_m=0`이다.
- 이는 코드 crash가 아니라 fail-closed stop condition이다.

다음 진단 순서:

- v0.6e 결과를 소급 통과 처리하지 않는다.
- fixed 40-run train gate를 열지 않는다.
- held-out `21000-21049`에 접근하지 않는다.
- 다음 slice에서 `straight-down capture_radius_m`을 z-gate threshold로 직접 쓰는 설계가
  너무 보수적인지 재검토한다.
- 재검토는 새 spec/plan으로 진행한다. 기존 v0.6e 결과를 보고 threshold를 임의 완화하지
  않는다.

## MVP-2E v0.6f approach capture gate 해석

v0.6f는 v0.6e 결과를 소급 통과시키지 않는다. `capture_radius_m=0.0001`은 계속
geometry-isolated straight-down lower bound로 보존한다.

핵심 구분:

```text
straight_down_capture_radius_m:
  xy/yaw correction 없이 straight-down bounded push에서 측정한 geometry lower bound

approach_lateral_gate_m:
  controller-assisted z descent를 허용하는 pre-registered approach gate
```

중요한 규칙:

```text
env_native_max_consecutive_success_steps >= 10 만 seed pass authority다.
secondary diagnostic은 env-native pass를 veto하지 못한다.
green_light_for_40_run_gate=false이면 fixed 40-run gate를 열지 않는다.
held-out 21000-21049는 계속 봉인한다.
```

재현 계획 문서:

```text
docs/superpowers/specs/2026-06-11-mvp2e-v06f-approach-capture-gate-design.md
docs/superpowers/plans/2026-06-11-mvp2e-v06f-approach-capture-gate.md
```

## MVP-2E v0.6f approach capture gate runtime result

v0.6f는 `capture_radius_m=0.0001`을 straight-down geometry lower bound로
보존하고, controller-assisted z descent에는 별도 approach gate를 사용한다.

```text
approach_lateral_gate_m = max(0.0010, 10.0 * straight_down_capture_radius_m)
z_push_gate = lateral_error_m <= approach_lateral_gate_m
success_authority = env_native_10_consecutive
```

재현 명령:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2e-v06f-approach-capture-gate \
  --scenario-profile v0_6 \
  --capture-radius-probe-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty

/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2e-v06f-approach-capture-gate \
  --scenario-profile v0_6 \
  --train-generation-probe-only \
  --repair-probe-only \
  --repair-probe-controller-version v0_6f \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

핵심 artifact:

```text
/tmp/rdf-mvp2e-v06f-approach-capture-gate/capture_radius_preflight_result.json
/tmp/rdf-mvp2e-v06f-approach-capture-gate/controller_repair_config.json
/tmp/rdf-mvp2e-v06f-approach-capture-gate/repair_probe_gate.json
```

현재 결과:

```text
capture_radius_m=0.0001
approach_lateral_gate_m=0.001
green_light_for_40_run_gate=false
hard_stop=true
failure_mode=repair_probe_not_green
all_probe_seeds_never_descended=false
fixed_40_run_gate_opened=false
heldout_opened=false

16023:
  env_native_seed_pass=false
  env_native_max_consecutive_success_steps=0
  max_insertion_depth_m=0.022587
  last_10_median_lateral_error_m=0.000212

16042:
  env_native_seed_pass=true
  env_native_max_consecutive_success_steps=10
  max_insertion_depth_m=0.02498

16096:
  env_native_seed_pass=false
  env_native_max_consecutive_success_steps=0
  max_insertion_depth_m=0.002396
  last_10_median_lateral_error_m=0.0007255
  convergence.non_seated_lateral_converged=false
  convergence.regression_detected=true
```

해석:

- v0.6f는 v0.6e보다 진척이 있다. `16042`는 env-native 10-consecutive success를
  회복했다.
- 하지만 repair probe green은 아니다.
- corrected guard 기준으로 `all_probe_seeds_never_descended=false`다. 즉 이전의
  "모든 seed가 하강하지 않았다" 해석은 nested RDF depth를 못 읽은 진단 오류였다.
- 현재 blocker는 다음 두 가지다.
  - `16023`: lateral이 충분히 수렴했지만 env-native hold window를 만들지 못한다.
  - `16096`: approach gate 안으로 들어온 뒤 tail에서 regression이 발생한다.
- `v0_6c_controller_action_diagnosis`는 `final_negative_z_action_steps=151`,
  `z_motion_allowed=151`을 기록한다. 따라서 다음 진단은 z-gate blockade가 아니라
  hold/contact/late-regression behavior를 봐야 한다.

금지:

- v0.6f 결과로 fixed 40-run train gate를 열지 않는다.
- held-out `21000-21049`를 열지 않는다.
- env-native 10-consecutive success authority를 완화하지 않는다.
- secondary RDF/diagnostic metric으로 env-native pass를 veto하거나 대체하지 않는다.

## MVP-2E v0.6f reset-boundary diagnosis

v0.6f repair probe 실패를 해석할 때는 controller failure와 episode reset boundary를 먼저 분리한다.

새 진단 helper:

```text
summarize_v06f_reset_boundary_diagnosis(trace_rows)
```

감지 기준:

```text
fixed_asset_pose_w 또는 held_asset_pose_w consecutive delta >= 0.01m
AND
insertion_depth_m 이 0.001m 이하로 reset-like drop
AND
step counter가 감소하지 않음
```

`step`이 `149 -> 0`처럼 감소하는 경우는 여러 trace file을 이어붙인 파일 경계이므로 reset-like jump로
계산하지 않는다.

현재 v0.6f 실제 trace 진단:

```text
/tmp/rdf-mvp2e-v06f-approach-capture-gate/reset_boundary_diagnosis.json
reset_like_jump_detected=true
reset_like_jump_count=2
reset_like_jump_steps=[148, 148]
heldout_opened=false
fixed_40_run_gate_opened=false
```

첫 번째 reset-like jump:

```text
from_step=147
to_step=148
pre_reset_phase=SEAT
post_reset_phase=APPROACH
pre_reset_insertion_depth_m=0.022587
post_reset_insertion_depth_m=0.0
fixed_asset_delta_m=0.097859
held_asset_delta_m=0.095631
```

해석:

- `16023`은 reset 직전 `insertion_depth_m=0.022587`, `lateral_error_m=0.000228`까지 접근했다.
- `16096`도 step 148에서 reset-like jump가 관측된다.
- 따라서 다음 controller 변경 전, reset 이후 tail이 convergence/regression 진단을 오염하는지 먼저
  분리해야 한다.

다음 valid debugging slice:

```text
1. episode reset boundary를 artifact에 seed별로 기록한다.
2. reset 이후 row를 secondary convergence/regression diagnosis에서 제외할지 spec으로 고정한다.
3. fixed 40-run train gate는 repair probe green 전까지 열지 않는다.
4. held-out 21000-21049는 계속 봉인한다.
5. horizon increase는 현재 stop condition이므로 단순 해법으로 쓰지 않는다.
```

## Stage 0 proof evidence preservation

2026-06-12 reboot 이후 `/tmp/rdf-*` proof evidence가 소실된 사실이 확인됐다.
이후 Isaac proof run은 `/tmp`를 primary evidence 위치로 사용하지 않는다.

기본 위치:

```text
storage/proof_evidence/<slice>/
```

현재 Stage 0 적용 runner:

```text
scripts/run_mvp2b_isaac_proof_evaluator.py
scripts/run_mvp2c_isaac_training_calibration.py
```

각 run은 다음 파일을 생성해야 한다.

```text
storage/proof_evidence/<slice>/evidence_manifest.json
```

manifest 확인 절차:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py --skip-isaac --pretty
python -m json.tool storage/proof_evidence/mvp2c_isaac_training_calibration/evidence_manifest.json
```

확인해야 할 필드:

```text
schema_version=rdf_proof_evidence_manifest_v0.1.0
proof_slice
output_dir
reproducible_command
files[].path
files[].sha256
files[].size_bytes
evidence_manifest_sha256
```

주의:

- `evidence_manifest.json`은 자기 자신을 file list에서 제외한다.
- 대형 trace/HDF5 artifact는 계속 gitignored일 수 있다.
- git에 남기는 것은 manifest와 sha256 증거다.
- 소실된 `/tmp` artifact를 소급 재구성해 기존 증거처럼 주장하지 않는다.
- fixed 40-run gate와 held-out A/B는 이 보존 체계 위에서만 진행한다.
- 기존 proof evidence가 남아 있으면 `--clean`으로 지우지 않는다. 재실행이 필요하면
  먼저 evidence manifest와 핵심 gate JSON을 보존한 뒤 별도 slice/output dir을 사용한다.

## MVP-2E v0.6g reset-boundary handling

v0.6g부터 Isaac rollout loop는 env reset boundary를 넘지 않는다. 실제
Isaac run에서 Factory env의 timeout reset은 `env.step()` 이후 trace row에
반영되므로, `env.max_episode_length - 1`만으로는 reset 후 row가 한 줄 섞일 수
있다. 따라서 v0.6g artifact는 post-step reset guard를 명시한다.

적용 규칙:

```text
env_reset_boundary_steps = env.max_episode_length
env_reset_post_step_guard_steps = 2
effective_rollout_budget_steps = min(success_metric.max_steps, env_reset_boundary_steps - env_reset_post_step_guard_steps)
seat_deadline_steps = effective_rollout_budget_steps - stable_steps_required
horizon_increase_applied = false
```

중요한 해석:

- 이 변경은 horizon 증가가 아니다.
- `max_steps=150`과 `stable_steps_required=10`은 그대로 유지한다.
- env reset 이후 row는 secondary convergence/regression diagnostic에서 제외한다.
- env-native success authority를 완화하거나 대체하지 않는다.
- post-reset row exclusion은 diagnostic 정합용이며 success 보정용이 아니다.

repair probe gate에서 확인할 새 필드:

```text
env_reset_post_step_guard_steps
v0_6g_post_reset_tail_handling.post_reset_rows_excluded
v0_6g_post_reset_tail_handling.per_seed.<seed>.first_excluded_row_index
v0_6g_post_reset_tail_handling.per_seed.<seed>.excluded_row_count
```

실제 Isaac 확인 명령:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 --train-generation-probe-only --repair-probe-only \
  --repair-probe-controller-version v0_6f \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 --device cuda:0 --pretty
```

2026-06-12 실제 A3 결과:

```text
repair_probe_gate_sha256=73a8148344374eeac4bc2abf751b61835fc65947431688bedf1005a7beb35207
green_light_for_40_run_gate=false
hard_stop=true
fixed_40_run_gate_opened=false
heldout_opened=false
reset_like_jump_count=0
post_reset_rows_excluded=false
seed 16042: env-native 10-consecutive success 유지
seed 16023: lateral은 안정됐지만 max_insertion_depth_m=0.022587로 under-insertion
seed 16096: near band 안에 들어왔지만 last-K median regression이 남아 non-seated converged=false
```

분기:

- `green_light_for_40_run_gate=true`이면 fixed 40-run train-generation gate로 이동한다.
- `16023`이 여전히 deadline을 못 맞추면 Phase B v0.6h pacing으로 이동한다.
- `16096`의 regression이 post-reset 제외 후에도 남으면 controller 결함으로 이관한다.
- held-out `21000-21049`는 열지 않는다.

## MVP-2 Phase E expressibility sanity blocker

2026-06-12 기준 MVP-2 Closed를 막는 현재 blocker는 repair probe나 40-run gate가 아니라
candidate policy expressibility다.

현재 gate 상태:

```text
repair_probe_gate.green_light_for_40_run_gate=true
train_generation_runtime_gate.passed=true
generated_success_count=28 / generated_rollout_count=40
expressibility_sanity_gate.passed=false
expressibility success_count=0 / rollout_count=5
heldout_opened=false
heldout_21000_21049_accessed=false
```

정확한 해석:

- scripted expert / controller는 v0.6i 기준으로 repair probe를 green으로 만들었고,
  fixed 40-run train-generation gate도 `28/40`으로 통과했다.
- HDF5 train views와 policy artifacts는 생성됐다.
- 그러나 candidate policy가 학습에 사용된 train-success seed 5개에서도 env-native
  10-consecutive success를 하나도 만들지 못했다.
- 따라서 policy가 expert의 gated behavior를 표현하지 못하거나, policy output과
  action adapter target 사이에 mismatch가 있을 가능성이 현재 1순위다.

다음 진단 순서:

1. `storage/proof_evidence/mvp2c_isaac_training_calibration/expressibility_sanity_gate.json`
   의 `trace_paths` 5개를 기준으로 candidate policy rollout 실패 양상을 확인한다.
2. 같은 seed의 successful expert trace와 candidate policy trace를 비교한다.
   - phase feature가 같은 의미로 들어가는지
   - z action이 ALIGN 단계에서 0으로 유지되고 DESCEND/INSERT에서 내려가는지
   - xy correction 방향과 scale이 expert와 같은 부호/범위인지
   - policy artifact의 action normalization / inverse adapter가 train-generation trace와 일치하는지
3. held-out `21000-21049`는 열지 않는다.
4. calibration presignal도 expressibility gate가 통과하기 전에는 실행하지 않는다.
5. policy/trainer 변경이 필요하면 새 pre-registered profile로 분리한다. 현재 failed
   expressibility 결과를 보고 기존 profile의 metric/threshold를 완화하지 않는다.

확인 명령:

```bash
python -m json.tool storage/proof_evidence/mvp2c_isaac_training_calibration/expressibility_sanity_gate.json
python -m json.tool storage/proof_evidence/mvp2c_isaac_training_calibration/train_generation_runtime_gate.json
python -m json.tool storage/proof_evidence/mvp2c_isaac_training_calibration/mvp2c_isaac_training_calibration_report.json
```

금지:

- expressibility `0/5` 상태에서 calibration 또는 held-out A/B를 실행하지 않는다.
- deterministic/proxy/synthetic fixture로 MVP-2 Closed를 주장하지 않는다.
- env-native success authority, `stable_steps=10`, `max_steps=150`을 완화하지 않는다.
- held-out 결과를 보고 policy class, feature schema, adapter, baseline mix를 바꾸지 않는다.

## MVP-2E v0.7a behavior-state phase relabel next slice

현재 expressibility blocker의 다음 pre-registered spec:

```text
docs/superpowers/specs/2026-06-12-mvp2e-v07a-behavior-state-phase-relabel-design.md
```

핵심 변경:

```text
old depth-derived phase:
  APPROACH / CONTACT / INSERT / SEAT

new behavior-state phase:
  ALIGN   = lateral_error_m > 0.001
  DESCEND = lateral_error_m <= 0.001 AND insertion_depth_m < 0.03
  HOLD    = lateral_error_m <= 0.001 AND insertion_depth_m >= 0.03
```

진단 의도:

- 기존 `APPROACH` phase 안에 `z≈0` 정렬 행동과 `z=-0.16` 하강 행동이 섞여
  linear BC가 "항상 하강"으로 붕괴했다.
- v0.7a는 기존 `phase`를 덮어쓰지 않고 `behavior_state_phase`를 새 derived field로
  추가한다.
- baseline과 candidate 모두 같은 relabel rule, feature schema, trainer, hyperparameter,
  action adapter를 사용한다.
- `offline_train_fit_gate`를 통과하기 전에는 Isaac expressibility를 실행하지 않는다.

추가 금지:

- v0.7a implementation 중 offline fit threshold 또는 aggregation rule을 결과 보고 바꾸지 않는다.
- `v0_7b` residual servo BC는 v0.7a 실패 후 별도 spec으로만 진행한다.

## MVP-2E v0.7a behavior-state phase relabel 실행/해석

`v0_7a`는 새 Isaac train-generation을 만들지 않는다. 먼저 기존 v0.6 parent
artifacts를 offline relabel한다.

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7a \
  --offline-relabel-only \
  --pretty
```

성공적으로 실행되어도 `offline_train_fit_gate.passed=false`일 수 있다. 2026-06-12
현재 parent data 기준 결과는 다음과 같다.

```text
parent_artifact_hash_verdict.passed=true
parent_cleanliness.passed=true
offline_train_fit_gate.passed=false
failure_reason=required_phase_missing
candidate_phase_row_counts: ALIGN=68256, DESCEND=54592, HOLD=0
baseline_phase_row_counts: ALIGN=2560, DESCEND=0, HOLD=0
heldout_21000_21049_accessed=false
```

이 상태는 runtime 오류가 아니라 fail-closed evidence다. frozen behavior-state rule의
`HOLD = lateral_error_m <= 0.001 AND insertion_depth_m >= 0.03` 조건을 parent v0.6
rows가 충족하지 못했다는 뜻이다. 이 threshold를 결과 보고 완화하지 않는다.

`offline_train_fit_gate.passed=true`일 때만 Isaac expressibility를 실행한다.

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7a \
  --expressibility-sanity-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

현재처럼 offline gate가 false이면 아래 명령은 Isaac을 시작하지 않고 차단된다.

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7a \
  --expressibility-sanity-only \
  --pretty
```

예상 결과:

```text
runtime_backend=isaac_runtime_not_started
reason=missing_passed_v0_7a_offline_train_fit_gate
heldout_21000_21049_accessed=false
```

금지:

- `offline_train_fit_gate.passed=false` 상태에서 calibration presignal 또는 held-out A/B를 실행하지 않는다.
- `HOLD=0`을 없애기 위해 v0.7a threshold를 결과 보고 완화하지 않는다.
- v0.7a 실패를 v0.7b residual servo BC success로 소급 해석하지 않는다.

추가 guard:

- `--policy-slice v0_7a`는 `--offline-relabel-only` 또는 `--expressibility-sanity-only`와 함께 사용할 때만 유효하다.
- full build path는 아직 `v0_7a`를 end-to-end로 구현하지 않았으므로 아래 형태는 즉시 실패해야 한다.

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7a \
  --skip-isaac
```

예상 결과:

```text
ValueError: --policy-slice v0_7a is only valid with --offline-relabel-only or --expressibility-sanity-only
```

`offline_train_fit_gate.json` 해석:

- `parent_artifact_hash_verdict.passed=true`에는 `selected_action_adapter.json` file/payload hash도 포함된다.
- baseline은 report-only이므로 missing phase가 있어도 gate authority가 아니다.
- baseline missing phase metric은 숨기지 않고 `baseline_same_metrics_report_only` 아래에 `null` metric으로 기록된다.

예:

```text
baseline_same_metrics_report_only.metric_status=report_only_required_phase_missing
baseline_same_metrics_report_only.candidate_z_mae_max=null
```

## MVP-2E v0.7a.1 env-native HOLD relabel 실행/해석

`v0_7a_1`은 `v0_7a` artifacts를 수정하지 않는 child slice다. 핵심 차이는
`HOLD`를 `insertion_depth_m` 같은 geometry proxy로 만들지 않고,
`env_native_success` / `env_native_success_mask`에서 직접 읽는다는 점이다.

```text
HOLD    = env_native_success_mask == true
DESCEND = not HOLD AND lateral_error_m <= 0.001
ALIGN   = not HOLD AND lateral_error_m > 0.001
```

`seat_depth_threshold_m` 또는 `SUCCESS_METRIC.insertion_depth_m_min`를
`v0_7a_1` relabel config에 다시 넣으면 안 된다. geometry 값은 report-only다.

offline relabel 실행:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7a_1 \
  --offline-relabel-only \
  --pretty
```

2026-06-12 현재 parent artifacts 기준 최신 결과:

```text
parent_proof_chain_verdict.passed=true
candidate_trace_enriched_rows=1280
candidate_trace_missing_rows=121568
candidate_authenticated_rows_used=1280
candidate_phase_row_counts: ALIGN=1280, DESCEND=0, HOLD=0
candidate_min_hold_rows_per_success_trace=0
offline_train_fit_gate.passed=false
failure_reason=required_phase_missing
future_calibration_blocked_reason=candidate_offline_fit_failed
heldout_21000_21049_accessed=false
baseline_report_only_status=report_only_env_native_mask_missing
```

이 상태는 코드 런타임 실패가 아니라 의도된 fail-closed다. trace hydration은 동작했지만,
parent `candidate_curated_train.hdf5`에서 runtime trace와 매칭된 train rows가 trace 초반
window에만 존재했고, 실제 env-native seated/HOLD window가 해당 HDF5 row set에 포함되지 않았다.
따라서 `HOLD=0`이 정직한 결과이며, 이 상태에서 policy artifact 생성, calibration, held-out A/B를
열면 안 된다.

expressibility sanity guard:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7a_1 \
  --expressibility-sanity-only \
  --pretty
```

현재 예상 결과:

```text
exit status: non-zero expected
runtime_backend=isaac_runtime_not_started
reason=missing_passed_v0_7a_1_offline_train_fit_gate
heldout_21000_21049_accessed=false
```

다음 valid step은 threshold 완화가 아니다. `v0_7a_1`의 결론은 "env-native authority가
맞지만 기존 parent HDF5 train view가 seated runtime window를 담지 않는다"이다. 다음 spec은
runtime trace rows에서 full-horizon train view를 만들거나, 이미 deferred 된 `v0_7b`
residual servo BC fallback으로 넘어가야 한다. 두 경우 모두 held-out `21000-21049`는 계속
봉인한다.

## MVP-2E v0.7a.2 trace-native train view 실행/해석

`v0_7a_2`는 `v0_7a_1`의 blocker였던 parent HDF5 row window 손실을 우회한다.
primary row source는 parent HDF5가 아니라 actual Isaac train-generation trace JSON이다.

```text
candidate rows = train_generation_runtime_gate.generated_success_trace_paths full trace rows
baseline rows  = train_generation_runtime_gate.generated_trace_paths full trace rows
HOLD authority = env_native_success_mask
```

offline 실행:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7a_2 \
  --offline-relabel-only \
  --pretty
```

2026-06-12 현재 결과:

```text
artifact_dir=storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7a_2_trace_native_train_view
candidate_curated_train_v0_7a_2.hdf5 exists
baseline_uncurated_train_v0_7a_2.hdf5 exists
candidate_policy_artifact_v0_7a_2.json exists
baseline_policy_artifact_v0_7a_2.json exists
candidate_phase_row_counts: ALIGN=1973, DESCEND=1422, HOLD=284
baseline_phase_row_counts: ALIGN=3321, DESCEND=1826, HOLD=308
candidate_min_hold_rows_per_success_trace=10
candidate_min_consecutive_hold_rows_per_success_trace=10
offline_train_fit_gate_v0_7a_2.passed=true
heldout_21000_21049_accessed=false
```

즉 `v0_7a_2`는 train-view blocker를 해소했고, phase-conditioned NumPy BC가 expert trace
rows를 offline metric 기준으로 fit할 수 있음을 보였다. 이 결과는 Phase E 실행 허가일 뿐,
MVP-2 Closed 또는 held-out uplift 증명이 아니다.

Phase E 실행:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7a_2 \
  --expressibility-sanity-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

2026-06-12 현재 결과:

```text
runtime_backend=isaac_runtime
rollout_count=5
success_count=0
required_success_count=2
passed=false
reason=candidate policy did not pass train-split expressibility sanity.
heldout_21000_21049_accessed=false
```

이 상태는 의도된 fail-closed다. offline fit은 통과했지만 실제 Isaac rollout에서 정책이
train-split expressibility sanity gate를 통과하지 못했다. calibration, held-out A/B,
MVP-2 Closed 선언은 금지된다.

다음 valid step은 threshold 완화가 아니라 `v0_7b` residual servo BC spec이다. 이유는
trace-native rows와 env-native HOLD authority는 통과했지만, 순수 phase-conditioned linear BC
policy class가 Isaac rollout으로 transfer되지 않았기 때문이다.

## MVP-2E v0.7b residual servo BC 실행/해석

`v0_7b`는 full-action BC를 반복하지 않는다. baseline과 candidate가 같은 frozen base geometry
servo를 공유하고, policy는 residual만 학습한다.

```text
actual_trace_action = base_servo_action + learned_residual
residual_target = actual_trace_action - base_servo_action
```

중요한 claim boundary:

- `v0_7b`는 MVP-2 Closed가 아니다.
- `v0_7b`는 held-out `21000-21049`를 열지 않는다.
- recovery overlay는 shared source만 허용한다.
- policy-specific rollout trace, 특히 prior `v0_7a_2` candidate Phase E trace는 train recovery source로 쓰지 않는다.
- recovery source가 없거나 실패/empty이면 offline build는 policy artifact를 만들지 않고 fail-closed해야 한다.

shared recovery induction 실행:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7b \
  --recovery-overlay-induction-only \
  --pretty
```

현재 구현 상태에서 이 명령은 실제 Isaac trace를 만들지 않고 다음처럼 닫힌다.

```text
passed=false
runtime_backend=isaac_runtime_not_started
reason=shared_train_recovery_induction_requires_actual_isaac_runtime
```

이 출력은 정상적인 fail-closed 상태다. proof가 아니며, 다음 단계는 실제 Isaac runtime으로 shared recovery
trace를 생성하는 것이다.

offline residual build 실행:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7b \
  --offline-relabel-only \
  --pretty
```

현재 recovery source가 실패/empty이면 다음처럼 닫혀야 한다.

```text
failed_closed=true
failure_reason=recovery_overlay_source_unavailable
mvp2_closed=false
heldout_21000_21049_accessed=false
```

이 상태에서 `candidate_policy_artifact_v0_7b.json`, `baseline_policy_artifact_v0_7b.json`,
`candidate_curated_train_v0_7b.hdf5`, `baseline_uncurated_train_v0_7b.hdf5`가 없는 것은 정상이다.
비어 있는 recovery source를 조용히 받아들이면 안 된다.

Phase E expressibility 실행:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7b \
  --expressibility-sanity-only \
  --pretty
```

`offline_residual_fit_gate_v0_7b.passed=true` 전에는 Isaac을 시작하지 않고 다음처럼 닫혀야 한다.

```text
exit_code=1
passed=false
runtime_backend=isaac_runtime_not_started
reason=missing_passed_v0_7b_offline_residual_fit_gate
```

다음 valid step:

1. 실제 Isaac runtime으로 `shared_train_recovery_induction_v0_7b.json`에 `passed=true`와 recovery traces를 만든다.
2. `--offline-relabel-only`를 다시 실행해 residual HDF5와 policy artifacts를 만든다.
3. offline residual fit gate가 통과한 뒤에만 `--expressibility-sanity-only`를 실행한다.
4. Phase E가 통과해도 calibration freeze와 sealed held-out A/B positive uplift 전까지 MVP-2 Closed로 표기하지 않는다.

2026-06-12 최신 상태:

shared recovery induction은 실제 Isaac runtime으로 통과했다.

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7b \
  --recovery-overlay-induction-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

```text
passed=true
runtime_backend=isaac_runtime
trace_path_count=5
rollout_count=5
source_seeds=[19003,19012,19129,19030,19119]
heldout_21000_21049_accessed=false
```

그 다음 offline residual build도 통과했다.

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7b \
  --offline-relabel-only \
  --pretty
```

```text
offline_residual_fit_gate_v0_7b.passed=true
candidate_gate_passed=true
phase_e_candidate_expressibility_unblocked=true
future_ab_ready=true
heldout_21000_21049_accessed=false
```

주의: 위 `future_ab_ready=true`는 `v0_7b` historical artifact의 당시 의미다.
`v0_7d` 이후에는 offline gate 통과만으로 A/B readiness를 true로 만들지 않는다.
`future_ab_ready`는 actual Isaac Phase E 통과와 calibration freeze 이후에만 열 수 있다.

하지만 actual Isaac Phase E는 fail-closed됐다.

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7b \
  --expressibility-sanity-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

```text
passed=false
runtime_backend=isaac_runtime
rollout_count=5
success_count=0
required_success_count=2
reason=candidate policy did not pass train-split expressibility sanity.
heldout_21000_21049_accessed=false
```

해석:

```text
v0_7b recovered the missing shared recovery source and offline residual artifacts.
The remaining blocker is actual closed-loop action authority, not artifact generation.
```

Phase E trace 진단:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7b_residual_servo_bc/
  expressibility_sanity_gate_v0_7b.json
  isaac_runtime_expressibility_sanity_v0_7b/isaac_runtime_heldout_rollout_traces/*
```

관측된 패턴:

```text
all 5 rollouts: env_native_max_consecutive_success_steps=0
metric phase: mostly APPROACH/ALIGN
max insertion depth: 0.0
base_servo_z: about -0.001
residual_z: large positive or negative
post_adapter_z: often saturated at +0.16 or -0.16
```

즉 learned residual이 base servo의 z gate를 우회하고 있다. `v0_7b`에서 이것을 사후 패치해
Phase E를 다시 돌리는 것은 pre-registration을 깨므로 하지 않는다.

다음 valid step:

```text
Write v0_7c spec/plan for residual action authority gating.
The likely design is:
  base_servo_action + residual_prediction is still the policy form,
  but behavior-state z authority must be enforced after residual reconstruction,
  and offline gates must catch ALIGN-state post-adapter z saturation/sign violations.

Do not open calibration or held-out 21000-21049 before a fresh Phase E pass.
```

## 2026-06-12 - v0.7c Phase E fail-closed debugging note

`v0_7c`는 `v0_7b`의 residual z bypass를 막기 위해 post-residual action
authority filter를 추가한 slice다.

재생성 순서:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7c \
  --offline-relabel-only \
  --pretty
```

기대 상태:

```text
offline_residual_fit_gate_v0_7c.passed=true
offline_action_authority_gate_v0_7c.passed=true
heldout_21000_21049_accessed=false
```

actual Isaac Phase E:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7c \
  --expressibility-sanity-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

현재 결과:

```text
passed=false
runtime_backend=isaac_runtime
rollout_count=5
success_count=0
required_success_count=2
heldout_21000_21049_accessed=false
```

관련 artifact:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7c_residual_action_authority_gate/
  expressibility_sanity_gate_v0_7c.json
  isaac_runtime_expressibility_sanity_v0_7c/isaac_runtime_heldout_rollout_traces/*.json
```

진단 체크:

```text
controller_action_diagnostics.residual_z_after_authority == 0.0 in ALIGN
controller_action_diagnostics.raw_action_after_authority[2] == -0.001 in ALIGN
controller_action_diagnostics.post_adapter_action_vector[2] == -0.032 in ALIGN
env_native_max_consecutive_success_steps == 0
```

해석:

- `v0_7c` filter는 learned residual z를 정상적으로 제거한다.
- 남은 문제는 residual이 아니라 base servo의 `ALIGN` z authority다.
- `ALIGN`에서 base servo가 `-0.001` z를 내고, adapter가 이를 `-0.032`로
  스케일해 아직 centered/stable이 아닌 상태에서도 하강한다.
- 따라서 `v0_7c`를 사후 수정하지 말고 새 pre-registered slice에서
  `ALIGN` post-adapter z motion까지 막아야 한다.

다음 valid step:

```text
v0_7d candidate:
  ALIGN z authority = no post-adapter z motion until env-native centering is stable
  offline gate = ALIGN post-adapter z == 0 plus residual z == 0
  keep held-out 21000-21049 sealed
  rerun offline gates, then Phase E only
```

## MVP-2E harness-gated closure diagnostic

`v0_7d`를 바로 만들지 않고, 현재 `v0_7c` evidence를 먼저 harness로 분류한다.
이 모드는 artifact-only이며 Isaac, training, calibration, held-out을 실행하지 않는다.

실행:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7c \
  --harness-gated-closure-only \
  --pretty
```

주의:

```text
--harness-gated-closure-only --clean  # 금지. 기존 v0.7c evidence를 삭제하면 안 됨.
```

생성 artifact:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/harness_gated_closure/
  mvp2e_harness_config.json
  harness_trace_index.json
  mvp2e_harness_report.json
  harness_research_rationale.json
  mvp2e_harness_gate_manifest.json
```

현재 진단 결과:

```text
root_cause_status=classified
primary_root_cause_class=ACTION_AUTHORITY_POST_ADAPTER_Z_LEAK
secondary_root_cause_candidates=[BASE_SERVO_PREMATURE_DESCENT]
recommended_downstream_slice=v0_7d_action_authority_post_adapter_z_gate
trace_count=5
heldout_21000_21049_accessed=false
mvp2_closed=false
```

핵심 해석:

- H0 passed: scenario/evaluator/held-out seal은 유지된다.
- H1/H2 failed: `ALIGN`에서 `residual_z_after_authority == 0.0`이지만
  `post_adapter_action_vector[2] == -0.032`가 되어 adapter 이후 하강이 재도입된다.
- H3 failed: base servo 또는 adapter 조합이 centered/stable 전 하강을 만든다.
- H4 passed: fixed 40-run train-generation gate는 28/40으로 유지된다.
- H14 passed: `isaac_runtime_heldout_rollout_traces` directory name은 legacy diagnostic
  label이며 protected seed `21000-21049` 접근이 아니다.
- H15 passed: baseline/candidate adapter, authority hash, trainer/schema fairness는
  현재 evidence에서 공유된다.

다음 디버깅 규칙:

- `mvp2e_harness_report.json` 없이는 `v0_7d`를 만들지 않는다.
- missing required H1/H2/H3/H15 evidence이면 downstream slice 추천은 `null`이어야 한다.
- legacy path label의 `heldout` 문자열만 보고 held-out leakage로 판단하지 않는다.
- held-out leakage는 protected seed `21000-21049` 접근으로만 판정한다.

## MVP-2E harness review reinforcement

외부 검수 반영 후 harness report는 다음 추가 의미를 갖는다.

```text
H12 failed:
  stable_hold_uses_geometry_thresholds_instead_of_env_native_mask

secondary_root_cause_candidates:
  BASE_SERVO_PREMATURE_DESCENT
  PHASE_LABEL_RUNTIME_MISMATCH

recommended_downstream_repair_requirements:
  enforce_config_independent_post_adapter_z_authority
  block_align_z_motion_after_final_action_mutation_until_centered
  replace_stable_hold_geometry_thresholds_with_env_native_mask
```

중요 해석:

- H1/H2는 여전히 primary blocker다. `ALIGN`에서 adapter 이후 z motion이
  재도입된다.
- H12는 현재 v0.7c가 착좌에 도달하지 못했기 때문에 직접 원인은 아니지만,
  착좌 후 10-consecutive env-native hold window를 쌓는 단계에서 다음 blocker가
  될 수 있는 authority mismatch다.
- close-critical harness가 `not_evaluated`이면 close-critical pass가 아니다.
  `unevaluated_close_critical_harnesses`가 비어 있지 않으면 MVP-2 closed를 주장할 수 없다.
- `stable_hold_depth_m`, `stable_hold_lateral_m`, `stable_hold_orientation_deg`는
  report-only diagnostic으로만 허용한다. hold readiness authority로 쓰면 fail-closed한다.

다음 spec:

```text
docs/superpowers/specs/2026-06-12-mvp2e-v07d-action-authority-post-adapter-z-gate-design.md
```

## MVP-2E v0.7d review-fix debugging contract

`v0_7d`는 `v0_7c` harness report가 먼저 classified 상태여야 생성된다.

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7c \
  --harness-gated-closure-only \
  --pretty
```

요구되는 parent evidence:

```text
root_cause_status=classified
primary_root_cause_class=ACTION_AUTHORITY_POST_ADAPTER_Z_LEAK
recommended_downstream_slice=v0_7d_action_authority_post_adapter_z_gate
protected_heldout_21000_21049_accessed=false
calibration_opened=false
```

그 다음에만 `v0_7d` offline artifact를 생성한다.

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --offline-relabel-only \
  --policy-slice v0_7d \
  --pretty
```

현재 통과 기준:

```text
offline_final_action_authority_gate_v0_7d.passed=true
phase_e_candidate_expressibility_unblocked=true
future_ab_ready=false
future_ab_ready_source=requires_actual_phase_e_pass_and_calibration_freeze
candidate_align_final_z_violation_count=0
baseline_align_final_z_violation_count=0
stable_hold_authority=env_native_success_mask
heldout_21000_21049_accessed=false
```

디버깅 규칙:

- `stable_hold` readiness는 `env_native_success_mask`만 authority로 인정한다.
- `stable_hold_depth_m`, `stable_hold_lateral_m`, `stable_hold_orientation_deg`는
  selected-adapter diagnostic일 뿐 hold authority가 아니다.
- `v0_7d` child policy artifact는 parent `authority_filter_config_sha256`와
  `final_post_adapter_authority_config.inherited_authority_filter_config_sha256`가
  일치해야 한다. Runtime evaluator도 이 mismatch를 즉시 거부한다.
- `v0_7d` child policy artifact와 offline gate는
  `selected_action_adapter_config`와 해당 sha256 lineage도 요구한다. config가 없으면
  adapter simulation이 `{}` default로 진행되지 않고 fail-closed된다.
- Runtime evaluator도 `v0_7d`에서는 selected adapter 실행 전에
  `selected_action_adapter_config` 존재와 sha256 일치를 검증한다. 누락 또는 stale hash는
  `v0_7d_selected_action_adapter_config_missing` /
  `v0_7d_selected_action_adapter_config_hash_mismatch`로 fail-closed되어야 한다.
- `future_ab_ready=false`가 정상이다. offline gate는 Phase E 실행 가능 여부만
  의미한다.
- `--harness-gated-closure-only --policy-slice v0_7d`는 CLI에서 거부된다.
  harness-gated closure report는 parent `v0_7c` classified evidence 보존용이고,
  `v0_7d` child slice는 `offline_final_action_authority_gate_v0_7d.json`으로
  검증한다.

v0.7d 구현 전 금지선:

- selected action adapter config를 결과에 맞춰 재선택하지 않는다.
- env-native success threshold, `stable_steps=10`, `max_steps=150`을 바꾸지 않는다.
- calibration이나 held-out `21000-21049`를 열지 않는다.
- `adapter_not_instrumented` 또는 `no_v06_controller`를 final z gate bypass 조건으로
  사용하지 않는다.

## MVP-2E v0.7d implementation guardrails

승인된 plan:

```text
docs/superpowers/plans/2026-06-12-mvp2e-v07d-action-authority-post-adapter-z-gate.md
```

v0.7d offline artifact build는 반드시 explicit safe mode로만 실행한다.

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --offline-relabel-only \
  --policy-slice v0_7d \
  --pretty
```

다음 명령 형태는 implicit full/offline run으로 취급하지 말고 거부해야 한다.

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7d \
  --pretty
```

v0.7d debug 순서:

1. RED tests를 먼저 추가한다.
2. runtime full inference path가 다음 순서로 실행되는지 확인한다.

```text
v0_7c base servo
-> v0_7c residual/pre-adapter authority
-> selected action adapter
-> v0_7d final post-adapter authority
-> env.step action
```

3. offline adapter simulation이 runtime adapter semantics와 parity를 갖는지
   테스트한다.
4. H12는 `selected_action_adapter_config`의 geometry threshold를 수정하지 말고,
   top-level `stable_hold_authority`와
   `final_post_adapter_authority_config.stable_hold_authority`를 확인한다.
5. `offline_final_action_authority_gate_v0_7d.json`이 `passed=true`가 되기 전에는
   Isaac Phase E를 실행하지 않는다.

계속 금지되는 것:

- calibration open
- held-out `21000-21049` access
- `mvp2_closed=true`
- `policy_uplift_proven=true`
- `selected_action_adapter.json` 또는 historical `v0_7c` artifact mutation

## MVP-2E v0.7d action-authority debug result

`v0_7d`는 `v0_7c` artifact를 patch하지 않고 child slice로 생성한다.

핵심 runtime 순서:

```text
v0_7c residual/base policy
-> v0_7c pre-adapter residual authority
-> selected_action_adapter
-> v0_7d final_post_adapter_z_authority
-> Isaac final action
```

검증된 offline gate:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_7d_action_authority_post_adapter_z_gate/
    offline_final_action_authority_gate_v0_7d.json
```

통과 조건:

```text
passed=true
candidate_align_final_z_violation_count=0
baseline_align_final_z_violation_count=0
candidate_bad_block_reason_count=0
baseline_bad_block_reason_count=0
stable_hold_authority=env_native_success_mask
future_ab_ready=false
future_ab_ready_source=requires_actual_phase_e_pass_and_calibration_freeze
heldout_21000_21049_accessed=false
```

`v0_7d`에서 HDF5 training view도 child slice metadata를 가져야 한다.

```text
schema_version=rdf_mvp2e_v07d_action_authority_manifest_v0.1.0
policy_slice=v0_7d
final_post_adapter_authority_id=final_post_adapter_z_authority_gate_v0_7d
stable_hold_authority=env_native_success_mask
```

다음 runtime 실행 순서:

1. `offline_final_action_authority_gate_v0_7d.passed=true`를 확인한다.
2. 그 다음에만 actual Isaac Phase E expressibility sanity를 실행한다.
3. Phase E threshold는 기존 값 그대로 유지한다.

```text
rollout_count=5
required_success_count=2
success_authority=env_native_10_consecutive
```

해석 주의:

- `v0_7d` builder는 classified `v0_7c` harness report를 parent evidence로
  요구한다. 공용 harness report를 보존하려면 먼저 `v0_7c` harness-only 결과를
  유지한다.
- `--harness-gated-closure-only --policy-slice v0_7d`는 공용 harness report를
  덮어쓰지 못하도록 CLI에서 fail-closed된다.
- `v0_7d` 자체의 offline authority gate는
  `offline_final_action_authority_gate_v0_7d.json`을 기준으로 본다.
- H12가 `passed`이면 stable-hold authority가 env-native mask로 이동했다는 뜻이다.
- Phase E를 실행하기 전까지 `v0_7d`는 train-split runtime success 증거가 아니다.

계속 금지되는 것:

- calibration open
- held-out `21000-21049` access
- selected action adapter reselection
- env-native success threshold 완화
- `mvp2_closed=true`
- `policy_uplift_proven=true`

## MVP-2E v0.7e shared hysteresis parity repair

`v0_7e`는 `v0_7d` child slice 위에 shared rollout-local hysteresis authority를
추가한 repair slice다. 이 slice는 Phase E를 바로 실행하지 않고, 먼저 offline
gate 3개가 모두 통과해야 한다.

Offline artifact build:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --offline-relabel-only \
  --policy-slice v0_7e \
  --pretty
```

확인할 artifact:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_7e_shared_hysteresis_parity_repair/
    offline_hysteresis_parity_gate_v0_7e.json
    attribution_preservation_gate_v0_7e.json
    final_action_authority_regression_gate_v0_7e.json
    v0_7e_shared_hysteresis_parity_manifest.json
```

Phase E를 열 수 있는 최소 offline 조건:

```text
offline_hysteresis_parity_gate_v0_7e.passed=true
attribution_preservation_gate_v0_7e.passed=true
final_action_authority_regression_gate_v0_7e.passed=true
phase_e_candidate_expressibility_unblocked=true
heldout_21000_21049_accessed=false
calibration_opened=false
mvp2_closed=false
policy_uplift_proven=false
```

`attribution_preservation_gate_v0_7e`는 shared hysteresis가 baseline/candidate
차이를 지워버리는지를 막는 gate다. 다음 값이 fail이면 Phase E를 실행하지 않는다.

```text
same_shared_infrastructure_equalities_all_true
candidate_baseline_policy_artifacts_differ
candidate_baseline_final_action_delta_l2_mean > 1e-6
candidate_baseline_final_action_delta_nonzero_fraction >= 0.10
```

현재 artifact 기준:

```text
offline_hysteresis_parity_gate_v0_7e.passed=true
attribution_preservation_gate_v0_7e.passed=true
final_action_authority_regression_gate_v0_7e.passed=true
phase_e_candidate_expressibility_unblocked=true
future_ab_ready=false
mvp2_closed=false
policy_uplift_proven=false
heldout_21000_21049_accessed=false
calibration_opened=false
```

다음 runtime command는 위 offline 조건이 모두 true일 때만 실행한다.

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7e \
  --expressibility-sanity-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

해석 주의:

- `v0_7e` offline gate pass는 actual Isaac policy success가 아니다.
- Phase E success 기준은 그대로 `>=2/5` env-native 10-consecutive다.
- Phase E가 실패하면, next slice는 새 harness report로 원인을 다시 분류한다.
- Phase E가 통과해도 MVP-2 Closed가 아니다. calibration freeze와 sealed held-out
  A/B positive uplift가 추가로 필요하다.

## MVP-2E v0.8b/v0.8c actual held-out shortfall debugging

`v0_8b`는 actual Isaac held-out closure를 실행한 slice다. 이 slice는 fresh
held-out `26000-26049`를 열었고 실패했으므로, 해당 range는 이후 closure에
재사용하지 않는다.

v0.8b closure command:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_8b \
  --scenario-aware-seat-window-authority-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

Observed result:

```text
baseline_success_rate=0.76
candidate_success_rate=0.88
curated_vs_uncurated_uplift=0.12
mvp2_closed=false
```

v0.8c artifact-only diagnosis command:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_8c \
  --heldout-shortfall-diagnosis-only \
  --pretty
```

Key artifact:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_8c_heldout_shortfall_diagnosis/v0_8c_shortfall_diagnosis.json
```

Interpretation:

```text
late_seat_window_shortfall: reaches success too late for 10-step hold
centered_under_depth_progress: centered but insertion depth does not progress enough
off_center_no_capture: z opens outside effective capture region and depth stays zero
```

Do not fix v0.8b by reusing `26000-26049`. The next closure attempt must use a
new pre-registered held-out range, with `27000-27049` reserved as the next
candidate.

## MVP-2 v0.14 closure spent held-out rule

`v0_14_comparator_provenance_row_balance`는 actual Isaac held-out
`40000-40049`를 열어서 MVP-2 Closed를 달성했다. 이 range는 이제 audit evidence로
보존해야 하지만 future tuning이나 future closure proof에 재사용하면 안 된다.

최종 증거:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_14_comparator_provenance_row_balance/
    heldout_closure_gate_v0_14.json
```

Closure result:

```text
calibration_39000_39029:
  baseline=5/30
  candidate=26/30
  uplift=+0.70

heldout_40000_40049:
  baseline=5/50
  candidate=40/50
  uplift=+0.70
  mvp2_closed=true
  policy_uplift_proven=true
```

금지:

- `40000-40049` 결과를 보고 policy, comparator, adapter, threshold, metric,
  curation rule을 조정하지 않는다.
- `40000-40049`를 다른 slice의 closure proof로 재사용하지 않는다.
- `40000-40049`를 “새 held-out”처럼 문서화하지 않는다.
- 기존 `heldout_closure_gate_v0_14.json` 또는 root `heldout_closure_gate.json`이
  `40000-40049` spent 상태를 표시하면
  `--comparator-provenance-row-balance-runtime`을 다시 실행하지 않는다. 현재
  runtime은 이 상태를 감지하면 Isaac 실행 또는 fresh artifact 재작성 전에
  `v0_14_heldout_40000_40049_already_spent_audit_only`로 fail-closed한다.

허용:

- `40000-40049` artifact를 audit, provenance 확인, buyer-facing limitation 설명,
  regression fixture 설계 참고 자료로 보존한다.
- future closure attempt는 fresh pre-registered held-out range를 별도로 잡고,
  calibration pass 전에는 열지 않는다.

## MVP-3A target fixture pose variant spent held-out rule

`mvp3a_target_fixture_pose_variant`는 actual Isaac held-out `42000-42049`를
열어서 MVP-3A Proof-Infrastructure Closed와 Learning-Proven Addendum을 달성했다.
이 range는 이제 audit evidence로 보존해야 하지만 future tuning이나 future
closure proof에 재사용하면 안 된다.

최종 proof package:

```text
docs/proof/mvp3a_target_fixture_pose_variant_proof_package/
  package_manifest.json
```

검증 명령:

```bash
python3 scripts/verify_proof_package.py \
  docs/proof/mvp3a_target_fixture_pose_variant_proof_package/package_manifest.json
```

Closure result:

```text
calibration_41000_41029:
  baseline=5/30
  candidate=30/30

heldout_42000_42049:
  baseline=8/50
  candidate=48/50
  uplift=+0.80
  package_status=proof_infrastructure_closed
  learning_result=positive_uplift
  learning_proven_addendum=present
```

금지:

- `42000-42049` 결과를 보고 policy, comparator, adapter, threshold, metric,
  trainer, curation rule을 조정하지 않는다.
- `42000-42049`를 다른 slice의 closure proof로 재사용하지 않는다.
- `42000-42049`를 “새 held-out”처럼 문서화하지 않는다.
- MVP-3B 이후 task/source expansion에서 `42000-42049`를 tuning evidence로
  사용하지 않는다.

허용:

- `42000-42049` artifact를 audit, provenance 확인, buyer-facing limitation 설명,
  regression fixture 설계 참고 자료로 보존한다.
- future MVP-3B proof attempt는 fresh pre-registered held-out range를 별도로
  잡고, `40000-40049`와 `42000-42049` 모두와 disjoint해야 한다.
