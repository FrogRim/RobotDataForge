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
RDF_ACTION_POS_GAIN=0.45 ./scripts/run_live_rdf_smoke_test.sh
RDF_ACTION_ROT_GAIN=0.35 ./scripts/run_live_rdf_smoke_test.sh
RDF_ACTION_POS_AXIS_MAP=x,y,z ./scripts/run_live_rdf_smoke_test.sh
RDF_CONTRIBUTOR_ID=user_001 ./scripts/run_live_rdf_smoke_test.sh
API_BASE=http://127.0.0.1:8001 ./scripts/run_live_rdf_smoke_test.sh
```

`RDF_WARMUP_VALID_FRAMES`는 recorder가 trajectory frame 저장을 시작하기 전에 요구하는 연속 valid handtracking frame 수다. 기본값은 `10`이다. Quest 3 연결 직후 초반 handtracking false frame이 많이 저장되면 `30`까지 올려서 다시 테스트한다.

`RDF_DISABLE_AUTO_CALIBRATE=1`을 지정하면 첫 valid handtracking frame에서 자동 calibration을 만들지 않는다. 기본값은 `0`이며, recorder는 첫 valid frame에서 raw XR right wrist pose를 현재 robot end-effector pose에 맞추는 `workspace_alignment_v2` calibration metadata를 저장한다. 기존 reader 호환을 위해 `translation_offset`도 계속 저장한다.

`RDF_ACTION_FILTER=1`은 Isaac에 적용하기 전 teleop action을 완만하게 보정한다. 기본값은 다음과 같다.

```text
RDF_ACTION_POS_GAIN=0.45
RDF_ACTION_ROT_GAIN=0.35
RDF_ACTION_POS_DEADZONE=0.0015
RDF_ACTION_ROT_DEADZONE=0.01
RDF_ACTION_SMOOTHING_ALPHA=0.45
RDF_ACTION_POS_AXIS_MAP=x,y,z
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

좌표 방향이 맞지 않으면 axis map을 바꿔서 짧게 테스트한다.

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

시점이 몸 정면과 30-60도 정도 어긋나면 Isaac OpenXR anchor yaw를 조정한다. `P` recenter는 recorder/action-filter 기준만 다시 잡고 XR camera anchor는 돌리지 않는다.

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
  live smoke 로그에서 `[RDF] Waiting for ... consecutive valid handtracking frames`와
  `[RDF] Recording frames started after dropping ... warm-up frames`를 확인한다.
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
RDF_ACTION_POS_GAIN=0.45
RDF_ACTION_ROT_GAIN=0.35
RDF_ACTION_POS_AXIS_MAP=x,y,z
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
```

즉시 시도할 운영 절차:

```text
1. Quest 3에서 ALVR 연결 후 SteamVR home view가 안정될 때까지 기다린다.
2. Isaac에서 Start AR를 누르기 전에 실제 몸 방향을 모니터/작업공간 정면으로 맞춘다.
3. 손이 HMD 카메라 시야 안에 들어온 상태에서 Start AR를 누른다.
4. Start AR 직후 3~5초 동안 손을 정면에 두고 tracking이 안정된 뒤 조작한다.
5. RDF recorder는 첫 valid frame에서 자동 calibration metadata를 만든다.
6. 조작 중 기준점이 틀어졌다고 느껴지면 terminal에 focus를 두고 P를 눌러 RDF calibration/recenter를 다시 요청한다.
7. view yaw 자체가 크게 어긋나면 Isaac/AR session을 닫고 `RDF_XR_ANCHOR_YAW_OFFSET_DEG=45` 또는 `-45`로 재실행한다.
8. SteamVR room forward 자체가 틀어진 느낌이면 Quest/SteamVR recenter 후 다시 시작한다.
```

Recenter command:

```text
P command는 recorded metadata의 raw/aligned XR pose를 다시 맞추고,
RDF action filter의 smoothing state를 reset한다.
또한 recenter 직후 1 frame은 position/rotation command를 0으로 suppress해
operator가 새 기준점에서 다시 움직이기 시작할 수 있게 한다.
단, P command는 Isaac OpenXR anchor rotation을 바꾸지 않는다.
```

개선 구현 후보:

```text
1. XR calibration step
   - episode 시작 전에 HMD pose와 hand pose를 읽어 robot workspace 기준 transform을 저장한다.
   - session metadata에 xr_anchor_pose, hmd_start_pose, retargeting_offset을 남긴다.

2. Retargeter anchor correction
   - 현재 PR은 action filter post-process다.
   - 그래도 view 자체가 맞지 않으면 Isaac OpenXR anchor를 Franka table 중심에 맞추는 별도 변경이 필요하다.

3. Workspace ghost visual
   - end-effector target sphere, hand ray, gripper state indicator를 Isaac scene에 표시한다.
   - 사용자가 "내 손 입력이 robot target으로 어디에 매핑되는지" 즉시 볼 수 있게 한다.

4. Precision mode
   - position gain, rotation gain, smoothing, deadzone을 분리한다.
   - pinch 중에는 이동 gain을 낮추는 fine-control mode를 둔다.

5. Recording quality gate
   - warm-up 이후에도 tracking loss, retargeting jump, input latency가 일정 기준을 넘으면 episode를 invalid 처리한다.
```

MVP 판단:

```text
XR 시점 불일치가 계속되면 많은 trajectory를 수집해도 사람이 조작하기 어렵고 evaluator 실패가 늘어난다.
따라서 100 episode 수집 전에 최소 calibration/recenter/ghost visual 중 하나는 구현하는 것이 좋다.
```

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
5. HMD/Isaac 화면에서 visual marker가 보이는지 확인한다. green은 현재 robot fingertip, cyan은 hand delta target, yellow는 이번 step robot target, magenta는 Forge hole 기준 target이다.
6. 터미널에서 `action_debug`의 `raw_xyz`, `filtered_xyz`, `step_xyz`와 `motion_debug`의 `eef_delta_norm`이 변하는지 확인한다.
7. 손이 정상적으로 움직이는 것을 확인한 뒤 terminal에 focus를 두고 `P`를 한 번 눌러 recenter한다.
8. 최소 수십 초 조작한 뒤 `N` 또는 `F`로 explicit finalize한다.
9. Isaac을 닫은 뒤 아래 검증을 실행한다.

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
- `P` recenter는 RDF recording metadata/action-filter 상태를 갱신한다. 현재 Isaac OpenXR control anchor 자체를 바꾸는 기능은 아니므로, `P`를 눌렀다고 로봇이 손의 절대 위치를 따라오지는 않는다.
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
