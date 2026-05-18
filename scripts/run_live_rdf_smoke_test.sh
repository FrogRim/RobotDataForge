#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API_HOST="${API_HOST:-127.0.0.1}"
API_PORT_START="${API_PORT_START:-8000}"
DATABASE_URL="${DATABASE_URL:-sqlite:///./storage/local_api.sqlite}"
STORAGE_ROOT="${STORAGE_ROOT:-storage}"
RDF_MAX_FRAMES="${RDF_MAX_FRAMES:-300}"
RDF_WARMUP_VALID_FRAMES="${RDF_WARMUP_VALID_FRAMES:-10}"
RDF_DISABLE_AUTO_CALIBRATE="${RDF_DISABLE_AUTO_CALIBRATE:-0}"
RDF_ACTION_FILTER="${RDF_ACTION_FILTER:-1}"
RDF_ACTION_POS_GAIN="${RDF_ACTION_POS_GAIN:-0.45}"
RDF_ACTION_ROT_GAIN="${RDF_ACTION_ROT_GAIN:-0.35}"
RDF_ACTION_POS_DEADZONE="${RDF_ACTION_POS_DEADZONE:-0.0015}"
RDF_ACTION_ROT_DEADZONE="${RDF_ACTION_ROT_DEADZONE:-0.01}"
RDF_ACTION_SMOOTHING_ALPHA="${RDF_ACTION_SMOOTHING_ALPHA:-0.45}"
RDF_ACTION_POS_AXIS_MAP="${RDF_ACTION_POS_AXIS_MAP:-x,y,z}"
RDF_ACTION_ROT_AXIS_MAP="${RDF_ACTION_ROT_AXIS_MAP:-x,y,z}"
RDF_DEBUG_ACTION_EVERY="${RDF_DEBUG_ACTION_EVERY:-0}"
RDF_DEBUG_MOTION_EVERY="${RDF_DEBUG_MOTION_EVERY:-0}"
RDF_FORGE_ACTION_ADAPTER="${RDF_FORGE_ACTION_ADAPTER:-1}"
RDF_TELEOP_CONTROL_MODE="${RDF_TELEOP_CONTROL_MODE:-auto}"
RDF_DIRECT_EE_POS_GAIN="${RDF_DIRECT_EE_POS_GAIN:-0.18}"
RDF_DIRECT_EE_ROT_GAIN="${RDF_DIRECT_EE_ROT_GAIN:-0.25}"
RDF_DIRECT_EE_MAX_STEP_M="${RDF_DIRECT_EE_MAX_STEP_M:-0.06}"
RDF_DIRECT_EE_MAX_ROT_STEP_RAD="${RDF_DIRECT_EE_MAX_ROT_STEP_RAD:-0.20}"
RDF_DIRECT_EE_SMOOTHING_ALPHA="${RDF_DIRECT_EE_SMOOTHING_ALPHA:-0.95}"
RDF_DIRECT_EE_DEADZONE_M="${RDF_DIRECT_EE_DEADZONE_M:-0.0001}"
RDF_DIRECT_EE_WORKSPACE_RADIUS_M="${RDF_DIRECT_EE_WORKSPACE_RADIUS_M:-0.35}"
RDF_OPERATOR_FOLLOW_PRESET="${RDF_OPERATOR_FOLLOW_PRESET:-safe}"
RDF_OPERATOR_FOLLOW_WORKSPACE_GAIN="${RDF_OPERATOR_FOLLOW_WORKSPACE_GAIN:--1}"
RDF_OPERATOR_FOLLOW_MAX_STEP_M="${RDF_OPERATOR_FOLLOW_MAX_STEP_M:--1}"
RDF_OPERATOR_FOLLOW_SMOOTHING_ALPHA="${RDF_OPERATOR_FOLLOW_SMOOTHING_ALPHA:--1}"
RDF_OPERATOR_FOLLOW_DEADZONE_M="${RDF_OPERATOR_FOLLOW_DEADZONE_M:--1}"
RDF_OPERATOR_FOLLOW_WORKSPACE_RADIUS_M="${RDF_OPERATOR_FOLLOW_WORKSPACE_RADIUS_M:--1}"
RDF_CARTESIAN_DELTA_POS_GAIN="${RDF_CARTESIAN_DELTA_POS_GAIN:-3.0}"
RDF_CARTESIAN_DELTA_ROT_GAIN="${RDF_CARTESIAN_DELTA_ROT_GAIN:-1.0}"
RDF_CARTESIAN_DELTA_EMA="${RDF_CARTESIAN_DELTA_EMA:-1.0}"
RDF_VISUAL_DEBUG="${RDF_VISUAL_DEBUG:-0}"
RDF_VISUAL_DEBUG_EVERY="${RDF_VISUAL_DEBUG_EVERY:-1}"
RDF_VISUAL_DEBUG_SIZE="${RDF_VISUAL_DEBUG_SIZE:-18}"
RDF_VISUAL_DEBUG_INPUT_SCALE="${RDF_VISUAL_DEBUG_INPUT_SCALE:-0.25}"
RDF_TASK_GUIDANCE="${RDF_TASK_GUIDANCE:-1}"
RDF_TASK_GUIDANCE_EVERY="${RDF_TASK_GUIDANCE_EVERY:-20}"
RDF_TASK_GUIDANCE_PANEL="${RDF_TASK_GUIDANCE_PANEL:-1}"
RDF_TASK_GUIDANCE_PANEL_SIZE="${RDF_TASK_GUIDANCE_PANEL_SIZE:-1.0}"
RDF_TASK_GUIDANCE_PANEL_SOURCE="${RDF_TASK_GUIDANCE_PANEL_SOURCE:-/_xr/stage/xrCamera}"
RDF_TASK_GUIDANCE_PANEL_TRANSLATION="${RDF_TASK_GUIDANCE_PANEL_TRANSLATION:-1.05,0.25,-1.25}"
RDF_TASK_GUIDANCE_PRIMITIVE_FALLBACK="${RDF_TASK_GUIDANCE_PRIMITIVE_FALLBACK:-0}"
RDF_GUIDANCE_PEG_TIP_DISTANCE_MAX="${RDF_GUIDANCE_PEG_TIP_DISTANCE_MAX:-}"
RDF_GUIDANCE_PEG_AXIS_ALIGNMENT_MAX_RAD="${RDF_GUIDANCE_PEG_AXIS_ALIGNMENT_MAX_RAD:-}"
RDF_GUIDANCE_INSERTION_DEPTH_MIN="${RDF_GUIDANCE_INSERTION_DEPTH_MIN:-}"
RDF_INSERTION_AXIS_WORLD="${RDF_INSERTION_AXIS_WORLD:-}"
RDF_SUCCESS_READY_HOLD_SEC="${RDF_SUCCESS_READY_HOLD_SEC:-1.5}"
RDF_AUTO_SUCCESS_FINALIZE="${RDF_AUTO_SUCCESS_FINALIZE:-0}"
RDF_AUTO_FINALIZE_REQUIRE_LIVE_CURATION="${RDF_AUTO_FINALIZE_REQUIRE_LIVE_CURATION:-0}"
RDF_LIVE_CURATION_MIN_FRAMES="${RDF_LIVE_CURATION_MIN_FRAMES:-60}"
RDF_LIVE_CURATION_MAX_NATIVE_ACTION_SATURATION_RATIO="${RDF_LIVE_CURATION_MAX_NATIVE_ACTION_SATURATION_RATIO:-0.05}"
RDF_LIVE_CURATION_MAX_RETARGETING_JUMP="${RDF_LIVE_CURATION_MAX_RETARGETING_JUMP:-1.50}"
RDF_LIVE_CURATION_MAX_TRACKING_LOSS_RATE="${RDF_LIVE_CURATION_MAX_TRACKING_LOSS_RATE:-0.05}"
RDF_LIVE_CURATION_ON_FAIL="${RDF_LIVE_CURATION_ON_FAIL:-hold}"
RDF_TERMINAL_HOTKEYS="${RDF_TERMINAL_HOTKEYS:-0}"
RDF_AUTO_RECENTER_ON_FIRST_VALID="${RDF_AUTO_RECENTER_ON_FIRST_VALID:-1}"
RDF_AUTO_RECENTER_VALID_FRAMES="${RDF_AUTO_RECENTER_VALID_FRAMES:-10}"
RDF_EXIT_AFTER_FINALIZE="${RDF_EXIT_AFTER_FINALIZE:-0}"
RDF_XR_ANCHOR_POS="${RDF_XR_ANCHOR_POS:--0.1,-0.5,-1.05}"
RDF_XR_ANCHOR_ROT="${RDF_XR_ANCHOR_ROT:-0.866,0,0,-0.5}"
RDF_XR_ANCHOR_YAW_OFFSET_DEG="${RDF_XR_ANCHOR_YAW_OFFSET_DEG:-0}"
RDF_CONTRIBUTOR_ID="${RDF_CONTRIBUTOR_ID:-user_001}"
RDF_ISAAC_TASK="${RDF_ISAAC_TASK:-Isaac-Stack-Cube-Franka-IK-Rel-v0}"
ISAAC_RUNNER="${ISAAC_RUNNER:-$HOME/run_isaac_handtracking.sh}"
ALVR_DASHBOARD="${ALVR_DASHBOARD:-$HOME/.local/share/ALVR-Launcher/installations/v20.14.1/alvr_streamer_linux/bin/alvr_dashboard}"
STEAMVR_VRMONITOR="${STEAMVR_VRMONITOR:-$HOME/.steam/debian-installation/steamapps/common/SteamVR/bin/vrmonitor.sh}"
SKIP_ISAAC=0
KEEP_API=0
PROMPT_READY=1
START_XR=1

for arg in "$@"; do
  case "$arg" in
    --skip-isaac)
      SKIP_ISAAC=1
      ;;
    --keep-api)
      KEEP_API=1
      ;;
    --no-prompt)
      PROMPT_READY=0
      ;;
    --no-start-xr)
      START_XR=0
      ;;
    -h|--help)
      cat <<'EOF'
Usage:
  ./scripts/run_live_rdf_smoke_test.sh [--skip-isaac] [--keep-api] [--no-prompt] [--no-start-xr]

Environment:
  API_BASE             Use an already-running API. If unset, this script starts a local SQLite API.
  API_PORT_START       First local port to try. Default: 8000
  DATABASE_URL         Default: sqlite:///./storage/local_api.sqlite
  STORAGE_ROOT         Default: storage
  RDF_MAX_FRAMES       Default: 300
  RDF_WARMUP_VALID_FRAMES Default: 10
  RDF_DISABLE_AUTO_CALIBRATE Default: 0
  RDF_ACTION_FILTER    Default: 1
  RDF_ACTION_POS_GAIN  Default: 0.45
  RDF_ACTION_ROT_GAIN  Default: 0.35
  RDF_ACTION_POS_DEADZONE Default: 0.0015
  RDF_ACTION_ROT_DEADZONE Default: 0.01
  RDF_ACTION_SMOOTHING_ALPHA Default: 0.45
  RDF_ACTION_POS_AXIS_MAP Default: x,y,z
  RDF_ACTION_ROT_AXIS_MAP Default: x,y,z
  RDF_DEBUG_ACTION_EVERY Default: 0
  RDF_DEBUG_MOTION_EVERY Default: 0 (0이면 RDF_DEBUG_ACTION_EVERY 주기를 재사용)
  RDF_FORGE_ACTION_ADAPTER Default: 1
  RDF_TELEOP_CONTROL_MODE Default: auto (Forge PegInsert에서는 bounded_direct_ee_target)
  RDF_DIRECT_EE_POS_GAIN Default: 0.18
  RDF_DIRECT_EE_ROT_GAIN Default: 0.25
  RDF_DIRECT_EE_MAX_STEP_M Default: 0.06
  RDF_DIRECT_EE_MAX_ROT_STEP_RAD Default: 0.20
  RDF_DIRECT_EE_SMOOTHING_ALPHA Default: 0.95
  RDF_DIRECT_EE_DEADZONE_M Default: 0.0001
  RDF_DIRECT_EE_WORKSPACE_RADIUS_M Default: 0.35
  RDF_OPERATOR_FOLLOW_PRESET Default: safe (safe|fast|responsive)
  RDF_OPERATOR_FOLLOW_* Default: -1 means preset default
  RDF_CARTESIAN_DELTA_POS_GAIN Default: 3.0
  RDF_CARTESIAN_DELTA_ROT_GAIN Default: 1.0
  RDF_CARTESIAN_DELTA_EMA Default: 1.0
  RDF_VISUAL_DEBUG   Default: 0 (1이면 Isaac/HMD 화면에 RDF debug marker 표시)
  RDF_VISUAL_DEBUG_EVERY Default: 1
  RDF_VISUAL_DEBUG_SIZE Default: 18
  RDF_VISUAL_DEBUG_INPUT_SCALE Default: 0.25 (표시 전용 hand delta marker scale)
  RDF_TASK_GUIDANCE  Default: 1 (task_state 기반 SUCCESS_READY status 출력)
  RDF_TASK_GUIDANCE_EVERY Default: 20
  RDF_TASK_GUIDANCE_PANEL Default: 1 (HMD 안에 recenter/SUCCESS_READY 상태판 표시)
  RDF_TASK_GUIDANCE_PANEL_SIZE Default: 1.0
  RDF_TASK_GUIDANCE_PANEL_SOURCE Default: /_xr/stage/xrCamera
  RDF_TASK_GUIDANCE_PANEL_TRANSLATION Default: 1.05,0.25,-1.25
  RDF_TASK_GUIDANCE_PRIMITIVE_FALLBACK Default: 0 (XR text widget 실패 시 crude primitive fallback)
  RDF_GUIDANCE_PEG_TIP_DISTANCE_MAX Optional guidance-only distance threshold, e.g. 0.060 for practice
  RDF_GUIDANCE_PEG_AXIS_ALIGNMENT_MAX_RAD Optional guidance-only alignment threshold, e.g. 1.10 for practice
  RDF_GUIDANCE_INSERTION_DEPTH_MIN Optional guidance-only depth threshold, e.g. 0.012 for practice
  RDF_INSERTION_AXIS_WORLD Optional insertion depth projection axis, e.g. 0,0,1 for visual practice
  RDF_SUCCESS_READY_HOLD_SEC Default: 1.5
  RDF_AUTO_SUCCESS_FINALIZE Default: 0 (1이면 SUCCESS_READY hold 후 자동 success finalize)
  RDF_AUTO_FINALIZE_REQUIRE_LIVE_CURATION Default: 0 (1이면 live quality gate 통과 시에만 auto finalize)
  RDF_LIVE_CURATION_MIN_FRAMES Default: 60
  RDF_LIVE_CURATION_MAX_NATIVE_ACTION_SATURATION_RATIO Default: 0.05
  RDF_LIVE_CURATION_MAX_RETARGETING_JUMP Default: 1.50
  RDF_LIVE_CURATION_MAX_TRACKING_LOSS_RATE Default: 0.05
  RDF_LIVE_CURATION_ON_FAIL Default: hold (hold|reset)
  RDF_TERMINAL_HOTKEYS Default: 0 (1이면 P/N/F/R terminal fallback 사용)
  RDF_AUTO_RECENTER_ON_FIRST_VALID Default: 1
  RDF_AUTO_RECENTER_VALID_FRAMES Default: 10
  RDF_EXIT_AFTER_FINALIZE Default: 0 (1이면 finalize 후 Isaac loop 종료)
  RDF_XR_ANCHOR_POS Default: -0.1,-0.5,-1.05
  RDF_XR_ANCHOR_ROT Default: 0.866,0,0,-0.5
  RDF_XR_ANCHOR_YAW_OFFSET_DEG Default: 0
  RDF_CONTRIBUTOR_ID   Default: user_001
  RDF_ISAAC_TASK       Default: Isaac-Stack-Cube-Franka-IK-Rel-v0
  ISAAC_RUNNER         Default: ~/run_isaac_handtracking.sh
  ALVR_DASHBOARD       Default: ALVR v20.14.1 dashboard path
  STEAMVR_VRMONITOR    Default: SteamVR vrmonitor.sh path

Notes:
  - ALVR Dashboard and SteamVR are started automatically unless --no-start-xr is used.
  - Quest-side ALVR connection is still manual. Close Isaac after the short test run.
  - If port 8000 is occupied by a broken API, this script starts a managed API on the next free port.
EOF
      exit 0
      ;;
    *)
      echo "[RDF][FAIL] Unknown argument: $arg" >&2
      exit 2
      ;;
  esac
done

RUN_ID="$(date +%Y%m%d_%H%M%S)"
LOG_DIR="$ROOT/$STORAGE_ROOT/logs"
mkdir -p "$LOG_DIR"

API_PID=""
API_PGROUP=""
SELECTED_API_BASE="${API_BASE:-}"
STEP_NO=0
CURRENT_STAGE="startup"

log() {
  printf '[RDF][%s] %s\n' "$(date '+%H:%M:%S')" "$*"
}

step() {
  STEP_NO=$((STEP_NO + 1))
  CURRENT_STAGE="$*"
  printf '\n[RDF][STEP %02d] %s\n' "$STEP_NO" "$*"
}

ok() {
  log "OK: $*"
}

warn() {
  log "WARN: $*" >&2
}

fail() {
  log "FAIL: $*" >&2
  exit 1
}

on_error() {
  local code=$?
  warn "예상하지 못한 오류: stage='${CURRENT_STAGE}', line=${BASH_LINENO[0]}, exit=${code}"
}

cleanup() {
  if [[ -n "$API_PID" && "$KEEP_API" != "1" ]]; then
    if kill -0 "$API_PID" 2>/dev/null; then
      log "managed local API 종료: pid=$API_PID"
      if [[ -n "$API_PGROUP" ]]; then
        kill -- "-$API_PGROUP" 2>/dev/null || true
      else
        kill "$API_PID" 2>/dev/null || true
      fi

      for _ in $(seq 1 20); do
        if ! kill -0 "$API_PID" 2>/dev/null; then
          wait "$API_PID" 2>/dev/null || true
          return 0
        fi
        sleep 0.2
      done

      warn "managed local API가 정상 종료되지 않아 강제 종료합니다: pid=$API_PID"
      if [[ -n "$API_PGROUP" ]]; then
        kill -KILL -- "-$API_PGROUP" 2>/dev/null || true
      else
        kill -KILL "$API_PID" 2>/dev/null || true
      fi
      wait "$API_PID" 2>/dev/null || true
    fi
  elif [[ -n "$API_PID" && "$KEEP_API" == "1" ]]; then
    log "managed local API 유지: pid=$API_PID base=$SELECTED_API_BASE"
  fi
}

trap on_error ERR
trap cleanup EXIT

curl_to_file() {
  local url="$1"
  local out="$2"
  local status
  status="$(curl -sS --max-time 10 -o "$out" -w "%{http_code}" "$url" 2>"$out.curl.err" || true)"
  if [[ -s "$out.curl.err" ]]; then
    sed 's/^/[RDF][curl] /' "$out.curl.err" >&2 || true
  fi
  rm -f "$out.curl.err"
  printf '%s' "$status"
}

assert_json() {
  local file="$1"
  python3 - "$file" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    json.load(handle)
PY
}

probe_api() {
  local base="$1"
  local tmp_dir
  tmp_dir="$(mktemp -d)"

  local health_status episodes_status kpis_status
  health_status="$(curl_to_file "$base/health" "$tmp_dir/health.json")"
  if [[ "$health_status" != "200" ]]; then
    rm -rf "$tmp_dir"
    return 1
  fi

  episodes_status="$(curl_to_file "$base/api/episodes" "$tmp_dir/episodes.json")"
  if [[ "$episodes_status" != "200" ]]; then
    rm -rf "$tmp_dir"
    return 2
  fi

  kpis_status="$(curl_to_file "$base/api/admin/kpis" "$tmp_dir/kpis.json")"
  if [[ "$kpis_status" != "200" ]]; then
    rm -rf "$tmp_dir"
    return 3
  fi

  if ! assert_json "$tmp_dir/episodes.json" >/dev/null 2>&1; then
    rm -rf "$tmp_dir"
    return 4
  fi
  if ! assert_json "$tmp_dir/kpis.json" >/dev/null 2>&1; then
    rm -rf "$tmp_dir"
    return 5
  fi

  rm -rf "$tmp_dir"
  return 0
}

find_free_port() {
  python3 - "$API_HOST" "$API_PORT_START" <<'PY'
import socket
import sys

host = sys.argv[1]
start = int(sys.argv[2])

for port in range(start, start + 50):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            continue
        print(port)
        raise SystemExit(0)

raise SystemExit("no free port found")
PY
}

fetch_json_endpoint() {
  local path="$1"
  local out="$2"
  local status
  status="$(curl_to_file "$SELECTED_API_BASE$path" "$out")"
  if [[ "$status" != "200" ]]; then
    warn "endpoint failed: GET $path status=$status"
    if [[ -s "$out" ]]; then
      sed 's/^/[RDF][body] /' "$out" >&2 || true
    fi
    return 1
  fi
  assert_json "$out"
}

json_len() {
  local file="$1"
  python3 - "$file" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    value = json.load(handle)
print(len(value) if isinstance(value, list) else 0)
PY
}

start_managed_api() {
  local port="$1"
  local init_log="$LOG_DIR/live_smoke_init_${RUN_ID}.log"
  local api_log="$LOG_DIR/live_smoke_api_${RUN_ID}.log"

  step "Local SQLite API 초기화"
  log "DATABASE_URL=$DATABASE_URL"
  log "STORAGE_ROOT=$STORAGE_ROOT"
  DATABASE_URL="$DATABASE_URL" STORAGE_ROOT="$STORAGE_ROOT" uv run python scripts/init_local_db.py >"$init_log" 2>&1
  ok "DB init 완료: $init_log"

  step "Local SQLite API 시작"
  log "API log: $api_log"
  setsid env DATABASE_URL="$DATABASE_URL" STORAGE_ROOT="$STORAGE_ROOT" \
    uv run uvicorn app.main:app --app-dir apps/api --host "$API_HOST" --port "$port" \
    >"$api_log" 2>&1 &
  API_PID=$!
  API_PGROUP=$API_PID
  SELECTED_API_BASE="http://$API_HOST:$port"

  for _ in $(seq 1 80); do
    if probe_api "$SELECTED_API_BASE" >/dev/null 2>&1; then
      ok "API 준비 완료: $SELECTED_API_BASE"
      return 0
    fi
    if ! kill -0 "$API_PID" 2>/dev/null; then
      warn "API process가 조기 종료됨. 로그 tail:"
      tail -n 80 "$api_log" >&2 || true
      return 1
    fi
    sleep 0.5
  done

  warn "API 준비 timeout. 로그 tail:"
  tail -n 80 "$api_log" >&2 || true
  return 1
}

start_xr_stack() {
  if [[ "$START_XR" != "1" ]]; then
    step "XR stack 자동 시작 생략"
    warn "--no-start-xr 모드입니다. ALVR/SteamVR/Quest 연결은 사용자가 이미 끝냈다고 가정합니다."
    return 0
  fi

  step "XR stack 시작"
  if [[ -z "${DISPLAY:-}" && -z "${WAYLAND_DISPLAY:-}" ]]; then
    warn "DISPLAY/WAYLAND_DISPLAY가 비어 있습니다. GUI session terminal에서 실행해야 ALVR/SteamVR 창이 열립니다."
  fi

  if pgrep -u "$USER" -x alvr_dashboard >/dev/null 2>&1; then
    ok "ALVR Dashboard process 감지"
  else
    if [[ ! -x "$ALVR_DASHBOARD" ]]; then
      fail "ALVR Dashboard 실행 파일을 찾지 못했습니다: $ALVR_DASHBOARD"
    fi
    local alvr_log="$LOG_DIR/live_smoke_alvr_${RUN_ID}.log"
    log "ALVR Dashboard 시작: $ALVR_DASHBOARD"
    log "ALVR log: $alvr_log"
    setsid "$ALVR_DASHBOARD" >"$alvr_log" 2>&1 &
    sleep 3
    if pgrep -u "$USER" -x alvr_dashboard >/dev/null 2>&1; then
      ok "ALVR Dashboard 시작 확인"
    else
      warn "ALVR Dashboard process가 아직 감지되지 않습니다. 로그를 확인하세요: $alvr_log"
    fi
  fi

  if ! pgrep -u "$USER" -x vrserver >/dev/null 2>&1; then
    log "ALVR Dashboard가 SteamVR을 자체 실행할 수 있어 최대 35초 대기합니다."
    for _ in $(seq 1 35); do
      if pgrep -u "$USER" -x vrserver >/dev/null 2>&1; then
        ok "ALVR 경유 SteamVR vrserver 시작 확인"
        break
      fi
      sleep 1
    done
  fi

  if pgrep -u "$USER" -x vrserver >/dev/null 2>&1; then
    ok "SteamVR vrserver process 감지"
  else
    if [[ ! -x "$STEAMVR_VRMONITOR" ]]; then
      fail "SteamVR vrmonitor.sh를 찾지 못했습니다: $STEAMVR_VRMONITOR"
    fi
    local steamvr_log="$LOG_DIR/live_smoke_steamvr_${RUN_ID}.log"
    log "SteamVR 시작: $STEAMVR_VRMONITOR"
    log "SteamVR log: $steamvr_log"
    setsid env \
      __GLX_VENDOR_LIBRARY_NAME=nvidia \
      __NV_PRIME_RENDER_OFFLOAD=1 \
      VK_DRIVER_FILES=/usr/share/vulkan/icd.d/nvidia_icd.json \
      "$STEAMVR_VRMONITOR" >"$steamvr_log" 2>&1 &

    for _ in $(seq 1 90); do
      if pgrep -u "$USER" -x vrserver >/dev/null 2>&1; then
        ok "SteamVR vrserver 시작 확인"
        break
      fi
      sleep 1
    done
  fi

  if pgrep -u "$USER" -x vrserver >/dev/null 2>&1; then
    ok "SteamVR 준비 완료"
  else
    fail "SteamVR vrserver가 시작되지 않았습니다. ALVR/SteamVR 로그를 확인하세요."
  fi
}

capture_snapshot() {
  local label="$1"
  local episodes_file="$LOG_DIR/live_smoke_${label}_episodes_${RUN_ID}.json"
  local kpis_file="$LOG_DIR/live_smoke_${label}_kpis_${RUN_ID}.json"

  fetch_json_endpoint "/api/episodes" "$episodes_file"
  fetch_json_endpoint "/api/admin/kpis" "$kpis_file"

  printf '%s\t%s\t%s\n' "$(json_len "$episodes_file")" "$episodes_file" "$kpis_file"
}

print_kpi_summary() {
  local kpis_file="$1"
  python3 - "$kpis_file" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    kpis = json.load(handle)

collection = kpis.get("collection", {})
xr = kpis.get("xr_runtime", {})
evaluation = kpis.get("evaluation", {})

print(f"recorded_episodes={collection.get('recorded_episodes')}")
print(f"completed_episodes={collection.get('completed_episodes')}")
print(f"replayable_trajectory_rate={collection.get('replayable_trajectory_rate')}")
print(f"hand_tracking_loss_rate={xr.get('hand_tracking_loss_rate')}")
print(f"frame_drop_rate={xr.get('frame_drop_rate')}")
print(f"task_success_rate={evaluation.get('task_success_rate')}")
print(f"accepted_trajectory_rate={evaluation.get('accepted_trajectory_rate')}")
PY
}

latest_episode_info() {
  local episodes_file="$1"
  python3 - "$episodes_file" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    episodes = json.load(handle)

if not episodes:
    print("\t\t\t")
    raise SystemExit(0)

episode = episodes[0]
print(
    f"{episode.get('id', '')}\t"
    f"{episode.get('trajectory_id') or ''}\t"
    f"{episode.get('evaluation_id') or ''}\t"
    f"{episode.get('status') or ''}"
)
PY
}

validate_latest_artifacts() {
  local episodes_file="$1"
  local latest_info latest_episode_id latest_trajectory_id latest_evaluation_id latest_status
  latest_info="$(latest_episode_info "$episodes_file")"
  IFS=$'\t' read -r latest_episode_id latest_trajectory_id latest_evaluation_id latest_status <<<"$latest_info"

  if [[ -z "$latest_episode_id" ]]; then
    fail "episode가 없습니다. Isaac recorder가 API에 제출하지 못했습니다."
  fi

  log "latest_episode_id=$latest_episode_id status=$latest_status"
  log "latest_trajectory_id=${latest_trajectory_id:-none}"
  log "latest_evaluation_id=${latest_evaluation_id:-none}"

  case "$latest_status" in
    success|failure|reset|incomplete|completed)
      ;;
    *)
      fail "latest episode status가 terminal lifecycle 상태가 아닙니다: $latest_status"
      ;;
  esac
  if [[ "$latest_status" == "incomplete" ]]; then
    warn "latest episode가 incomplete입니다. Isaac 종료 전 N/F/R로 explicit finalize하지 않은 경우 정상입니다."
  fi
  if [[ -z "$latest_trajectory_id" || -z "$latest_evaluation_id" ]]; then
    fail "latest episode에 trajectory_id 또는 evaluation_id가 없습니다."
  fi

  local trajectory_file="$LOG_DIR/live_smoke_latest_trajectory_${RUN_ID}.json"
  local evaluation_file="$LOG_DIR/live_smoke_latest_evaluation_${RUN_ID}.json"
  fetch_json_endpoint "/api/trajectories/$latest_trajectory_id" "$trajectory_file"
  fetch_json_endpoint "/api/evaluations/$latest_evaluation_id" "$evaluation_file"

  python3 - "$trajectory_file" "$evaluation_file" <<'PY'
import json
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    trajectory = json.load(handle)
with open(sys.argv[2], "r", encoding="utf-8") as handle:
    evaluation = json.load(handle)

source = trajectory.get("source") or {}
required = ["input_device", "runtime", "simulator", "robot", "task_name"]
missing = [key for key in required if not source.get(key)]
if missing:
    raise SystemExit(f"trajectory source missing required fields: {missing}")

frames = trajectory.get("frames") or []
if not frames:
    raise SystemExit("trajectory has no frames")

first_frame = frames[0]
metadata = first_frame.get("metadata") or {}
action = first_frame.get("action") or {}
required_metadata = ["raw_xr", "aligned_xr", "retargeted"]
missing_metadata = [key for key in required_metadata if key not in metadata]
if missing_metadata:
    raise SystemExit(f"trajectory frame missing RDF XR metadata fields: {missing_metadata}")
if "retargeted_robot_action" not in action:
    raise SystemExit("trajectory frame action missing retargeted_robot_action")
for action_key in ("raw", "applied"):
    if action_key not in action:
        raise SystemExit(f"trajectory frame action missing {action_key}")

print(f"trajectory_frames={len(frames)}")
print(f"trajectory_source={source}")
print(
    "trajectory_xr_metadata="
    f"raw_xr={bool(metadata.get('raw_xr'))} "
    f"aligned_calibration_valid={metadata.get('aligned_xr', {}).get('calibration_valid')} "
    f"retargeted_action={bool(action.get('retargeted_robot_action'))} "
    f"control_filter={bool(action.get('control_filter') or metadata.get('retargeted', {}).get('control_filter'))}"
)
print(
    "evaluation="
    f"success={evaluation.get('success')} "
    f"score={evaluation.get('score')} "
    f"quality_score={evaluation.get('quality_score')} "
    f"failure_reason={evaluation.get('failure_reason')}"
)
PY
}

step "Preflight"
command -v uv >/dev/null 2>&1 || fail "uv 명령을 찾을 수 없습니다."
command -v curl >/dev/null 2>&1 || fail "curl 명령을 찾을 수 없습니다."
command -v python3 >/dev/null 2>&1 || fail "python3 명령을 찾을 수 없습니다."
[[ -f "apps/api/app/main.py" ]] || fail "repo root가 아닙니다: $ROOT"
[[ -x "$ISAAC_RUNNER" ]] || fail "Isaac runner가 실행 가능하지 않습니다: $ISAAC_RUNNER"
ok "repo=$ROOT"
ok "isaac_runner=$ISAAC_RUNNER"
if [[ "$SKIP_ISAAC" != "1" && "$START_XR" == "1" ]]; then
  [[ -x "$ALVR_DASHBOARD" ]] || fail "ALVR Dashboard가 실행 가능하지 않습니다: $ALVR_DASHBOARD"
  [[ -x "$STEAMVR_VRMONITOR" ]] || fail "SteamVR vrmonitor.sh가 실행 가능하지 않습니다: $STEAMVR_VRMONITOR"
  ok "alvr_dashboard=$ALVR_DASHBOARD"
  ok "steamvr_vrmonitor=$STEAMVR_VRMONITOR"
fi

XR_RUNTIME_PATH="$HOME/.steam/debian-installation/steamapps/common/SteamVR/steamxr_linux64.json"
if [[ -f "$XR_RUNTIME_PATH" ]]; then
  ok "SteamVR OpenXR runtime 확인: $XR_RUNTIME_PATH"
else
  warn "SteamVR OpenXR runtime JSON을 찾지 못했습니다: $XR_RUNTIME_PATH"
fi

step "API 선택"
if [[ -n "$SELECTED_API_BASE" ]]; then
  log "사용자 지정 API_BASE 사용: $SELECTED_API_BASE"
  probe_api "$SELECTED_API_BASE" || fail "지정한 API_BASE가 health/DB endpoint probe를 통과하지 못했습니다."
  ok "기존 API 사용 가능"
else
  default_base="http://$API_HOST:$API_PORT_START"
  if probe_api "$default_base" >/dev/null 2>&1; then
    SELECTED_API_BASE="$default_base"
    ok "기존 API 재사용: $SELECTED_API_BASE"
  else
    free_port="$(find_free_port)"
    if [[ "$free_port" != "$API_PORT_START" ]]; then
      warn "$default_base 가 비어 있지 않거나 DB endpoint가 실패합니다. port $free_port 로 managed API를 시작합니다."
    fi
    start_managed_api "$free_port"
  fi
fi

step "실행 전 API snapshot"
pre_snapshot="$(capture_snapshot pre)"
IFS=$'\t' read -r PRE_COUNT PRE_EPISODES_FILE PRE_KPIS_FILE <<<"$pre_snapshot"
ok "pre recorded_episodes=$PRE_COUNT"
log "pre episodes json: $PRE_EPISODES_FILE"
log "pre kpis json: $PRE_KPIS_FILE"

if [[ "$SKIP_ISAAC" == "1" ]]; then
  step "Isaac 실행 생략"
  warn "--skip-isaac 모드입니다. API/script 검증만 수행합니다."
else
  start_xr_stack

  if [[ "$PROMPT_READY" == "1" ]]; then
    printf '\n[RDF][READY] Quest 3에서 ALVR 앱을 열고 PC 연결/handtracking을 확인한 뒤 Enter를 누르세요. 취소하려면 Ctrl+C.\n'
    read -r _
  fi

  step "Isaac handtracking recorder 실행"
  log "RDF_API_BASE=$SELECTED_API_BASE"
  log "RDF_MAX_FRAMES=$RDF_MAX_FRAMES"
  log "RDF_WARMUP_VALID_FRAMES=$RDF_WARMUP_VALID_FRAMES"
  log "RDF_DISABLE_AUTO_CALIBRATE=$RDF_DISABLE_AUTO_CALIBRATE"
  log "RDF_ACTION_FILTER=$RDF_ACTION_FILTER"
  log "RDF_ACTION_POS_GAIN=$RDF_ACTION_POS_GAIN"
  log "RDF_ACTION_ROT_GAIN=$RDF_ACTION_ROT_GAIN"
  log "RDF_ACTION_POS_AXIS_MAP=$RDF_ACTION_POS_AXIS_MAP"
  log "RDF_ACTION_ROT_AXIS_MAP=$RDF_ACTION_ROT_AXIS_MAP"
  log "RDF_DEBUG_ACTION_EVERY=$RDF_DEBUG_ACTION_EVERY"
  log "RDF_DEBUG_MOTION_EVERY=$RDF_DEBUG_MOTION_EVERY"
  log "RDF_FORGE_ACTION_ADAPTER=$RDF_FORGE_ACTION_ADAPTER"
  log "RDF_TELEOP_CONTROL_MODE=$RDF_TELEOP_CONTROL_MODE"
  log "RDF_DIRECT_EE_POS_GAIN=$RDF_DIRECT_EE_POS_GAIN"
  log "RDF_DIRECT_EE_ROT_GAIN=$RDF_DIRECT_EE_ROT_GAIN"
  log "RDF_DIRECT_EE_MAX_STEP_M=$RDF_DIRECT_EE_MAX_STEP_M"
  log "RDF_DIRECT_EE_MAX_ROT_STEP_RAD=$RDF_DIRECT_EE_MAX_ROT_STEP_RAD"
  log "RDF_DIRECT_EE_SMOOTHING_ALPHA=$RDF_DIRECT_EE_SMOOTHING_ALPHA"
  log "RDF_DIRECT_EE_DEADZONE_M=$RDF_DIRECT_EE_DEADZONE_M"
  log "RDF_DIRECT_EE_WORKSPACE_RADIUS_M=$RDF_DIRECT_EE_WORKSPACE_RADIUS_M"
  log "RDF_OPERATOR_FOLLOW_PRESET=$RDF_OPERATOR_FOLLOW_PRESET"
  log "RDF_OPERATOR_FOLLOW_WORKSPACE_GAIN=$RDF_OPERATOR_FOLLOW_WORKSPACE_GAIN"
  log "RDF_OPERATOR_FOLLOW_MAX_STEP_M=$RDF_OPERATOR_FOLLOW_MAX_STEP_M"
  log "RDF_OPERATOR_FOLLOW_SMOOTHING_ALPHA=$RDF_OPERATOR_FOLLOW_SMOOTHING_ALPHA"
  log "RDF_OPERATOR_FOLLOW_DEADZONE_M=$RDF_OPERATOR_FOLLOW_DEADZONE_M"
  log "RDF_OPERATOR_FOLLOW_WORKSPACE_RADIUS_M=$RDF_OPERATOR_FOLLOW_WORKSPACE_RADIUS_M"
  log "RDF_CARTESIAN_DELTA_POS_GAIN=$RDF_CARTESIAN_DELTA_POS_GAIN"
  log "RDF_CARTESIAN_DELTA_ROT_GAIN=$RDF_CARTESIAN_DELTA_ROT_GAIN"
  log "RDF_CARTESIAN_DELTA_EMA=$RDF_CARTESIAN_DELTA_EMA"
  log "RDF_VISUAL_DEBUG=$RDF_VISUAL_DEBUG"
  log "RDF_VISUAL_DEBUG_EVERY=$RDF_VISUAL_DEBUG_EVERY"
  log "RDF_VISUAL_DEBUG_SIZE=$RDF_VISUAL_DEBUG_SIZE"
  log "RDF_VISUAL_DEBUG_INPUT_SCALE=$RDF_VISUAL_DEBUG_INPUT_SCALE"
  log "RDF_TASK_GUIDANCE=$RDF_TASK_GUIDANCE"
  log "RDF_TASK_GUIDANCE_EVERY=$RDF_TASK_GUIDANCE_EVERY"
  log "RDF_TASK_GUIDANCE_PANEL=$RDF_TASK_GUIDANCE_PANEL"
  log "RDF_TASK_GUIDANCE_PANEL_SIZE=$RDF_TASK_GUIDANCE_PANEL_SIZE"
  log "RDF_TASK_GUIDANCE_PANEL_SOURCE=$RDF_TASK_GUIDANCE_PANEL_SOURCE"
  log "RDF_TASK_GUIDANCE_PANEL_TRANSLATION=$RDF_TASK_GUIDANCE_PANEL_TRANSLATION"
  log "RDF_TASK_GUIDANCE_PRIMITIVE_FALLBACK=$RDF_TASK_GUIDANCE_PRIMITIVE_FALLBACK"
  log "RDF_GUIDANCE_PEG_TIP_DISTANCE_MAX=${RDF_GUIDANCE_PEG_TIP_DISTANCE_MAX:-<strict>}"
  log "RDF_GUIDANCE_PEG_AXIS_ALIGNMENT_MAX_RAD=${RDF_GUIDANCE_PEG_AXIS_ALIGNMENT_MAX_RAD:-<strict>}"
  log "RDF_GUIDANCE_INSERTION_DEPTH_MIN=${RDF_GUIDANCE_INSERTION_DEPTH_MIN:-<strict>}"
  log "RDF_INSERTION_AXIS_WORLD=${RDF_INSERTION_AXIS_WORLD:-<default>}"
  log "RDF_SUCCESS_READY_HOLD_SEC=$RDF_SUCCESS_READY_HOLD_SEC"
  log "RDF_AUTO_SUCCESS_FINALIZE=$RDF_AUTO_SUCCESS_FINALIZE"
  log "RDF_AUTO_FINALIZE_REQUIRE_LIVE_CURATION=$RDF_AUTO_FINALIZE_REQUIRE_LIVE_CURATION"
  log "RDF_LIVE_CURATION_MIN_FRAMES=$RDF_LIVE_CURATION_MIN_FRAMES"
  log "RDF_LIVE_CURATION_MAX_NATIVE_ACTION_SATURATION_RATIO=$RDF_LIVE_CURATION_MAX_NATIVE_ACTION_SATURATION_RATIO"
  log "RDF_LIVE_CURATION_MAX_RETARGETING_JUMP=$RDF_LIVE_CURATION_MAX_RETARGETING_JUMP"
  log "RDF_LIVE_CURATION_MAX_TRACKING_LOSS_RATE=$RDF_LIVE_CURATION_MAX_TRACKING_LOSS_RATE"
  log "RDF_LIVE_CURATION_ON_FAIL=$RDF_LIVE_CURATION_ON_FAIL"
  log "RDF_TERMINAL_HOTKEYS=$RDF_TERMINAL_HOTKEYS"
  log "RDF_AUTO_RECENTER_ON_FIRST_VALID=$RDF_AUTO_RECENTER_ON_FIRST_VALID"
  log "RDF_AUTO_RECENTER_VALID_FRAMES=$RDF_AUTO_RECENTER_VALID_FRAMES"
  log "RDF_EXIT_AFTER_FINALIZE=$RDF_EXIT_AFTER_FINALIZE"
  log "RDF_XR_ANCHOR_POS=$RDF_XR_ANCHOR_POS"
  log "RDF_XR_ANCHOR_ROT=$RDF_XR_ANCHOR_ROT"
  log "RDF_XR_ANCHOR_YAW_OFFSET_DEG=$RDF_XR_ANCHOR_YAW_OFFSET_DEG"
  log "RDF_ISAAC_TASK=$RDF_ISAAC_TASK"
  log "Isaac이 열리면 손을 몇 초 움직인 뒤 Isaac 창을 닫으세요. 닫히면 자동 검증을 시작합니다."

  set +e
  RDF_RECORD=1 \
    RDF_API_BASE="$SELECTED_API_BASE" \
    RDF_REPO_ROOT="$ROOT" \
    RDF_CONTRIBUTOR_ID="$RDF_CONTRIBUTOR_ID" \
    RDF_MAX_FRAMES="$RDF_MAX_FRAMES" \
    RDF_WARMUP_VALID_FRAMES="$RDF_WARMUP_VALID_FRAMES" \
    RDF_DISABLE_AUTO_CALIBRATE="$RDF_DISABLE_AUTO_CALIBRATE" \
    RDF_ACTION_FILTER="$RDF_ACTION_FILTER" \
    RDF_ACTION_POS_GAIN="$RDF_ACTION_POS_GAIN" \
    RDF_ACTION_ROT_GAIN="$RDF_ACTION_ROT_GAIN" \
    RDF_ACTION_POS_DEADZONE="$RDF_ACTION_POS_DEADZONE" \
    RDF_ACTION_ROT_DEADZONE="$RDF_ACTION_ROT_DEADZONE" \
    RDF_ACTION_SMOOTHING_ALPHA="$RDF_ACTION_SMOOTHING_ALPHA" \
    RDF_ACTION_POS_AXIS_MAP="$RDF_ACTION_POS_AXIS_MAP" \
    RDF_ACTION_ROT_AXIS_MAP="$RDF_ACTION_ROT_AXIS_MAP" \
    RDF_DEBUG_ACTION_EVERY="$RDF_DEBUG_ACTION_EVERY" \
    RDF_DEBUG_MOTION_EVERY="$RDF_DEBUG_MOTION_EVERY" \
    RDF_FORGE_ACTION_ADAPTER="$RDF_FORGE_ACTION_ADAPTER" \
    RDF_TELEOP_CONTROL_MODE="$RDF_TELEOP_CONTROL_MODE" \
    RDF_DIRECT_EE_POS_GAIN="$RDF_DIRECT_EE_POS_GAIN" \
    RDF_DIRECT_EE_ROT_GAIN="$RDF_DIRECT_EE_ROT_GAIN" \
    RDF_DIRECT_EE_MAX_STEP_M="$RDF_DIRECT_EE_MAX_STEP_M" \
    RDF_DIRECT_EE_MAX_ROT_STEP_RAD="$RDF_DIRECT_EE_MAX_ROT_STEP_RAD" \
    RDF_DIRECT_EE_SMOOTHING_ALPHA="$RDF_DIRECT_EE_SMOOTHING_ALPHA" \
    RDF_DIRECT_EE_DEADZONE_M="$RDF_DIRECT_EE_DEADZONE_M" \
    RDF_DIRECT_EE_WORKSPACE_RADIUS_M="$RDF_DIRECT_EE_WORKSPACE_RADIUS_M" \
    RDF_OPERATOR_FOLLOW_PRESET="$RDF_OPERATOR_FOLLOW_PRESET" \
    RDF_OPERATOR_FOLLOW_WORKSPACE_GAIN="$RDF_OPERATOR_FOLLOW_WORKSPACE_GAIN" \
    RDF_OPERATOR_FOLLOW_MAX_STEP_M="$RDF_OPERATOR_FOLLOW_MAX_STEP_M" \
    RDF_OPERATOR_FOLLOW_SMOOTHING_ALPHA="$RDF_OPERATOR_FOLLOW_SMOOTHING_ALPHA" \
    RDF_OPERATOR_FOLLOW_DEADZONE_M="$RDF_OPERATOR_FOLLOW_DEADZONE_M" \
    RDF_OPERATOR_FOLLOW_WORKSPACE_RADIUS_M="$RDF_OPERATOR_FOLLOW_WORKSPACE_RADIUS_M" \
    RDF_CARTESIAN_DELTA_POS_GAIN="$RDF_CARTESIAN_DELTA_POS_GAIN" \
    RDF_CARTESIAN_DELTA_ROT_GAIN="$RDF_CARTESIAN_DELTA_ROT_GAIN" \
    RDF_CARTESIAN_DELTA_EMA="$RDF_CARTESIAN_DELTA_EMA" \
    RDF_VISUAL_DEBUG="$RDF_VISUAL_DEBUG" \
    RDF_VISUAL_DEBUG_EVERY="$RDF_VISUAL_DEBUG_EVERY" \
    RDF_VISUAL_DEBUG_SIZE="$RDF_VISUAL_DEBUG_SIZE" \
    RDF_VISUAL_DEBUG_INPUT_SCALE="$RDF_VISUAL_DEBUG_INPUT_SCALE" \
    RDF_TASK_GUIDANCE="$RDF_TASK_GUIDANCE" \
    RDF_TASK_GUIDANCE_EVERY="$RDF_TASK_GUIDANCE_EVERY" \
    RDF_TASK_GUIDANCE_PANEL="$RDF_TASK_GUIDANCE_PANEL" \
    RDF_TASK_GUIDANCE_PANEL_SIZE="$RDF_TASK_GUIDANCE_PANEL_SIZE" \
    RDF_TASK_GUIDANCE_PANEL_SOURCE="$RDF_TASK_GUIDANCE_PANEL_SOURCE" \
    RDF_TASK_GUIDANCE_PANEL_TRANSLATION="$RDF_TASK_GUIDANCE_PANEL_TRANSLATION" \
    RDF_TASK_GUIDANCE_PRIMITIVE_FALLBACK="$RDF_TASK_GUIDANCE_PRIMITIVE_FALLBACK" \
    RDF_GUIDANCE_PEG_TIP_DISTANCE_MAX="$RDF_GUIDANCE_PEG_TIP_DISTANCE_MAX" \
    RDF_GUIDANCE_PEG_AXIS_ALIGNMENT_MAX_RAD="$RDF_GUIDANCE_PEG_AXIS_ALIGNMENT_MAX_RAD" \
    RDF_GUIDANCE_INSERTION_DEPTH_MIN="$RDF_GUIDANCE_INSERTION_DEPTH_MIN" \
    RDF_INSERTION_AXIS_WORLD="$RDF_INSERTION_AXIS_WORLD" \
    RDF_SUCCESS_READY_HOLD_SEC="$RDF_SUCCESS_READY_HOLD_SEC" \
    RDF_AUTO_SUCCESS_FINALIZE="$RDF_AUTO_SUCCESS_FINALIZE" \
    RDF_AUTO_FINALIZE_REQUIRE_LIVE_CURATION="$RDF_AUTO_FINALIZE_REQUIRE_LIVE_CURATION" \
    RDF_LIVE_CURATION_MIN_FRAMES="$RDF_LIVE_CURATION_MIN_FRAMES" \
    RDF_LIVE_CURATION_MAX_NATIVE_ACTION_SATURATION_RATIO="$RDF_LIVE_CURATION_MAX_NATIVE_ACTION_SATURATION_RATIO" \
    RDF_LIVE_CURATION_MAX_RETARGETING_JUMP="$RDF_LIVE_CURATION_MAX_RETARGETING_JUMP" \
    RDF_LIVE_CURATION_MAX_TRACKING_LOSS_RATE="$RDF_LIVE_CURATION_MAX_TRACKING_LOSS_RATE" \
    RDF_LIVE_CURATION_ON_FAIL="$RDF_LIVE_CURATION_ON_FAIL" \
    RDF_TERMINAL_HOTKEYS="$RDF_TERMINAL_HOTKEYS" \
    RDF_AUTO_RECENTER_ON_FIRST_VALID="$RDF_AUTO_RECENTER_ON_FIRST_VALID" \
    RDF_AUTO_RECENTER_VALID_FRAMES="$RDF_AUTO_RECENTER_VALID_FRAMES" \
    RDF_EXIT_AFTER_FINALIZE="$RDF_EXIT_AFTER_FINALIZE" \
    RDF_XR_ANCHOR_POS="$RDF_XR_ANCHOR_POS" \
    RDF_XR_ANCHOR_ROT="$RDF_XR_ANCHOR_ROT" \
    RDF_XR_ANCHOR_YAW_OFFSET_DEG="$RDF_XR_ANCHOR_YAW_OFFSET_DEG" \
    RDF_ISAAC_TASK="$RDF_ISAAC_TASK" \
    "$ISAAC_RUNNER"
  ISAAC_STATUS=$?
  set -e

  if [[ "$ISAAC_STATUS" -eq 0 ]]; then
    ok "Isaac runner 정상 종료"
  else
    warn "Isaac runner exit=$ISAAC_STATUS. 그래도 사후 API 제출 여부를 확인합니다."
  fi
fi

step "실행 후 API snapshot"
post_snapshot="$(capture_snapshot post)"
IFS=$'\t' read -r POST_COUNT POST_EPISODES_FILE POST_KPIS_FILE <<<"$post_snapshot"
ok "post recorded_episodes=$POST_COUNT"
log "post episodes json: $POST_EPISODES_FILE"
log "post kpis json: $POST_KPIS_FILE"

if [[ "$SKIP_ISAAC" != "1" ]]; then
  if (( POST_COUNT <= PRE_COUNT )); then
    fail "새 episode가 증가하지 않았습니다. recorder 로그의 [RDF] Recorder disabled 또는 API POST 실패 메시지를 확인하세요."
  fi
  validate_latest_artifacts "$POST_EPISODES_FILE"
else
  warn "--skip-isaac 모드라 새 episode 증가는 검사하지 않습니다."
fi

step "KPI 요약"
print_kpi_summary "$POST_KPIS_FILE" | sed 's/^/[RDF][KPI] /'

step "완료"
ok "live smoke script 완료"
log "사용한 API: $SELECTED_API_BASE"
log "로그 폴더: $LOG_DIR"
