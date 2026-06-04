#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODE="free-motion"
IS_GATE0_MODE=0
IS_GATE0_ALL=0
RDF_GATE0_TEST_TYPE=""
if [[ $# -gt 0 ]]; then
  case "$1" in
    -h|--help)
      MODE="--help"
      shift
      ;;
    --*)
      # Keep the current default debug mode and pass all flags through to
      # run_live_rdf_smoke_test.sh. This makes the common shorthand
      # `./scripts/run_hmd_axis_debug.sh --no-start-xr` safe.
      ;;
    *)
      MODE="$1"
      shift
      ;;
  esac
fi

case "$MODE" in
  baseline)
    RDF_AXIS_MAP="x,z,y"
    RDF_YAW_OFFSET="0"
    RDF_CONTROL_MODE="bounded_direct_ee_target"
    MODE_NOTE="current RDF/OpenXR Y-up baseline"
    ;;
  free-motion)
    RDF_AXIS_MAP="x,z,y"
    RDF_YAW_OFFSET="0"
    RDF_CONTROL_MODE="bounded_direct_ee_target"
    MODE_NOTE="bypass robot start-box gate to prove hand input can move the robot at all"
    ;;
  raw-wrist-direct)
    RDF_AXIS_MAP="x,z,y"
    RDF_YAW_OFFSET="0"
    RDF_CONTROL_MODE="raw_wrist_direct_ee_target"
    MODE_NOTE="raw Quest/OpenXR right-wrist translation directly drives bounded end-effector target translation"
    ;;
  gate0-static)
    IS_GATE0_MODE=1
    RDF_GATE0_TEST_TYPE="static"
    RDF_AXIS_MAP="x,z,y"
    RDF_YAW_OFFSET="0"
    RDF_CONTROL_MODE="raw_wrist_direct_ee_target"
    MODE_NOTE="Gate 0 XR input viability: keep right hand static; task success is ignored"
    ;;
  gate0-slow-motion)
    IS_GATE0_MODE=1
    RDF_GATE0_TEST_TYPE="slow_motion"
    RDF_AXIS_MAP="x,z,y"
    RDF_YAW_OFFSET="0"
    RDF_CONTROL_MODE="raw_wrist_direct_ee_target"
    MODE_NOTE="Gate 0 XR input viability: move right hand slowly through a small range; task success is ignored"
    ;;
  gate0-recenter)
    IS_GATE0_MODE=1
    RDF_GATE0_TEST_TYPE="recenter"
    RDF_AXIS_MAP="x,z,y"
    RDF_YAW_OFFSET="0"
    RDF_CONTROL_MODE="raw_wrist_direct_ee_target"
    MODE_NOTE="Gate 0 XR input viability: verify stable-window recenter; task success is ignored"
    ;;
  gate0-reacquire)
    IS_GATE0_MODE=1
    RDF_GATE0_TEST_TYPE="tracking_reacquire"
    RDF_AXIS_MAP="x,z,y"
    RDF_YAW_OFFSET="0"
    RDF_CONTROL_MODE="raw_wrist_direct_ee_target"
    MODE_NOTE="Gate 0 XR input viability: briefly lose/reacquire right hand tracking; task success is ignored"
    ;;
  gate0-all)
    IS_GATE0_ALL=1
    RDF_AXIS_MAP="x,z,y"
    RDF_YAW_OFFSET="0"
    RDF_CONTROL_MODE="raw_wrist_direct_ee_target"
    MODE_NOTE="Gate 0 XR input viability batch: run static, slow-motion, recenter, and reacquire diagnostics in one command"
    ;;
  identity)
    RDF_AXIS_MAP="x,y,z"
    RDF_YAW_OFFSET="0"
    RDF_CONTROL_MODE="bounded_direct_ee_target"
    MODE_NOTE="identity passthrough baseline"
    ;;
  right-down-fix)
    RDF_AXIS_MAP="-z,y,x"
    RDF_YAW_OFFSET="0"
    RDF_CONTROL_MODE="bounded_direct_ee_target"
    MODE_NOTE="hypothesis for observed operator-right -> robot-down: source Z becomes +robot X"
    ;;
  right-down-fix-flipped)
    RDF_AXIS_MAP="z,y,x"
    RDF_YAW_OFFSET="0"
    RDF_CONTROL_MODE="bounded_direct_ee_target"
    MODE_NOTE="same X/Z swap as right-down-fix, opposite left/right sign"
    ;;
  -h|--help|--help-mode)
    cat <<USAGE
Usage:
  ./scripts/run_hmd_axis_debug.sh [mode] [run_live_rdf_smoke_test args...]

Modes:
  free-motion             Default. Bypass start-box gate; prove hand input moves robot before axis tests.
  raw-wrist-direct        Use raw_wrist_direct_ee_target: raw right-wrist pose drives bounded EEF translation.
  gate0-static            Gate 0: static hand viability diagnostic; task success ignored.
  gate0-slow-motion       Gate 0: slow-motion viability diagnostic; task success ignored.
  gate0-recenter          Gate 0: stable-window recenter diagnostic; task success ignored.
  gate0-reacquire         Gate 0: tracking loss/reacquire diagnostic; task success ignored.
  gate0-all               Gate 0 batch: run all four Gate 0 diagnostics in one command.
  right-down-fix          Test RDF_ACTION_POS_AXIS_MAP=-z,y,x after operator-right -> robot-down.
  right-down-fix-flipped  Test RDF_ACTION_POS_AXIS_MAP=z,y,x if right-down-fix mirrors left/right.
  identity                Test RDF_ACTION_POS_AXIS_MAP=x,y,z.
  baseline                Test RDF_ACTION_POS_AXIS_MAP=x,z,y.

Examples:
  ./scripts/run_hmd_axis_debug.sh free-motion
  ./scripts/run_hmd_axis_debug.sh raw-wrist-direct
  ./scripts/run_hmd_axis_debug.sh gate0-static
  ./scripts/run_hmd_axis_debug.sh gate0-all
  ./scripts/run_hmd_axis_debug.sh gate0-reacquire
  ./scripts/run_hmd_axis_debug.sh right-down-fix
  ./scripts/run_hmd_axis_debug.sh --no-start-xr
USAGE
    exit 0
    ;;
  *)
    cat >&2 <<USAGE
Usage:
  ./scripts/run_hmd_axis_debug.sh [mode] [run_live_rdf_smoke_test args...]

Modes:
  free-motion             Bypass start-box gate; prove hand input moves robot before axis tests.
  raw-wrist-direct        Use raw_wrist_direct_ee_target: raw right-wrist pose drives bounded EEF translation.
  gate0-static            Gate 0: static hand viability diagnostic; task success ignored.
  gate0-slow-motion       Gate 0: slow-motion viability diagnostic; task success ignored.
  gate0-recenter          Gate 0: stable-window recenter diagnostic; task success ignored.
  gate0-reacquire         Gate 0: tracking loss/reacquire diagnostic; task success ignored.
  gate0-all               Gate 0 batch: run all four Gate 0 diagnostics in one command.
  right-down-fix          Test RDF_ACTION_POS_AXIS_MAP=-z,y,x after operator-right -> robot-down.
  right-down-fix-flipped  Test RDF_ACTION_POS_AXIS_MAP=z,y,x if right-down-fix mirrors left/right.
  identity                Test RDF_ACTION_POS_AXIS_MAP=x,y,z.
  baseline                Test RDF_ACTION_POS_AXIS_MAP=x,z,y.

Example:
  ./scripts/run_hmd_axis_debug.sh free-motion --no-start-xr
USAGE
    exit 2
    ;;
esac

HMD_LOG_MODE="$(printf '%s' "$MODE" | tr -c 'A-Za-z0-9_.-' '_')"
HMD_LOG_TS="$(date +%Y%m%d_%H%M%S)"
RDF_HMD_LOG_CAPTURE="${RDF_HMD_LOG_CAPTURE:-1}"
RDF_HMD_LOG_DIR="${RDF_HMD_LOG_DIR:-$ROOT/${STORAGE_ROOT:-storage}/logs/hmd_axis_debug}"
RDF_HMD_LOG_FILE="${RDF_HMD_LOG_FILE:-$RDF_HMD_LOG_DIR/hmd_axis_debug_${HMD_LOG_TS}_${HMD_LOG_MODE}.log}"
RDF_HMD_LOG_SUMMARY_FILE="${RDF_HMD_LOG_SUMMARY_FILE:-$RDF_HMD_LOG_FILE.summary.json}"
RDF_GATE0_REPORT_FILE="${RDF_GATE0_REPORT_FILE:-$RDF_HMD_LOG_FILE.gate0.json}"
RDF_GATE0_ALL_REPORT_FILE="${RDF_GATE0_ALL_REPORT_FILE:-$RDF_HMD_LOG_FILE.gate0_all.json}"
export RDF_HMD_LOG_CAPTURE RDF_HMD_LOG_DIR RDF_HMD_LOG_FILE RDF_HMD_LOG_SUMMARY_FILE RDF_GATE0_REPORT_FILE RDF_GATE0_ALL_REPORT_FILE
export RDF_TASK_GUIDANCE_PANEL="${RDF_TASK_GUIDANCE_PANEL:-1}"
export RDF_TASK_GUIDANCE_PANEL_SIZE="${RDF_TASK_GUIDANCE_PANEL_SIZE:-1.25}"
export RDF_TASK_GUIDANCE_PANEL_SOURCE="${RDF_TASK_GUIDANCE_PANEL_SOURCE:-/_xr/stage/xrCamera}"
export RDF_TASK_GUIDANCE_PANEL_TRANSLATION="${RDF_TASK_GUIDANCE_PANEL_TRANSLATION:-0.00,0.10,-1.60}"
export RDF_TASK_GUIDANCE_PANEL_LOOK_AT_CAMERA="${RDF_TASK_GUIDANCE_PANEL_LOOK_AT_CAMERA:-1}"
export RDF_TASK_GUIDANCE_PANEL_BACKGROUND_ALPHA="${RDF_TASK_GUIDANCE_PANEL_BACKGROUND_ALPHA:-0.90}"
export RDF_TASK_GUIDANCE_PANEL_ANCHOR_MODE="${RDF_TASK_GUIDANCE_PANEL_ANCHOR_MODE:-upstream_instruction}"

if [[ "$RDF_HMD_LOG_CAPTURE" == "1" ]]; then
  mkdir -p "$RDF_HMD_LOG_DIR"
  exec > >(tee -a "$RDF_HMD_LOG_FILE") 2>&1
  echo "[RDF][HMD_AXIS_DEBUG] log_capture=enabled"
  echo "[RDF][HMD_AXIS_DEBUG] log_file=$RDF_HMD_LOG_FILE"
  echo "[RDF][HMD_AXIS_DEBUG] log_summary_file=$RDF_HMD_LOG_SUMMARY_FILE"
else
  echo "[RDF][HMD_AXIS_DEBUG] log_capture=disabled"
fi

cat <<INFO
[RDF][HMD_AXIS_DEBUG] mode=$MODE
[RDF][HMD_AXIS_DEBUG] note=$MODE_NOTE
[RDF][HMD_AXIS_DEBUG] forced task=Isaac-Forge-PegInsert-Direct-v0
[RDF][HMD_AXIS_DEBUG] forced RDF_ACTION_POS_AXIS_MAP=$RDF_AXIS_MAP
[RDF][HMD_AXIS_DEBUG] forced RDF_ACTION_POS_YAW_OFFSET_DEG=$RDF_YAW_OFFSET
[RDF][HMD_AXIS_DEBUG] forced RDF_TELEOP_CONTROL_MODE=$RDF_CONTROL_MODE
[RDF][HMD_AXIS_DEBUG] forced RDF_RECENTER_BOX_VISUAL=0 (cyan recenter wire box hidden)
[RDF][HMD_AXIS_DEBUG] HMD panel: visibility-probe XR overlay size=$RDF_TASK_GUIDANCE_PANEL_SIZE translation=$RDF_TASK_GUIDANCE_PANEL_TRANSLATION look_at_camera=$RDF_TASK_GUIDANCE_PANEL_LOOK_AT_CAMERA background_alpha=$RDF_TASK_GUIDANCE_PANEL_BACKGROUND_ALPHA anchor_mode=$RDF_TASK_GUIDANCE_PANEL_ANCHOR_MODE
[RDF][HMD_AXIS_DEBUG] Gate 0 mode=$IS_GATE0_MODE test_type=${RDF_GATE0_TEST_TYPE:-none}
[RDF][HMD_AXIS_DEBUG] HMD operator script:
  - For Gate 0 modes: record input viability only; task success and Gate A collection are blocked.
  - gate0-all: keep HMD on; this wrapper runs the four Gate 0 modes in order.
  - gate0-static: hold the right hand still after tracking appears.
  - gate0-slow-motion: move the right hand slowly in a small range.
  - gate0-recenter: wait for stable-window recenter and do not chase task success.
  - gate0-reacquire: briefly hide/reveal the right hand, then hold still through reacquire.
  - For free-motion: first prove the robot visibly moves with your hand. Then wait for 'RECORDING: ON' before judging/saving evidence.
  - For axis modes: wait for the in-HMD panel to show 'RECENTER: OK' and 'RECORDING: ON'.
  - For unclear motion: trust the HMD panel TRACKING/CONTROL/MOTION/RAW_JUMP lines before terminal text.
  1) move RIGHT only for ~2 sec, then pause
  2) move LEFT only for ~2 sec, then pause
  3) move UP only for ~2 sec, then close Isaac
[RDF][HMD_AXIS_DEBUG] Do not use terminal text as the HMD operator cue.
INFO

export RDF_ISAAC_TASK="Isaac-Forge-PegInsert-Direct-v0"
export RDF_TASK_TYPE="peg_in_hole"
export RDF_MAX_FRAMES="${RDF_MAX_FRAMES:-180}"
export RDF_WARMUP_VALID_FRAMES="${RDF_WARMUP_VALID_FRAMES:-15}"
export RDF_ACTION_POS_AXIS_MAP="$RDF_AXIS_MAP"
export RDF_ACTION_POS_YAW_OFFSET_DEG="$RDF_YAW_OFFSET"
export RDF_RAW_WRIST_POS_AXIS_MAP="$RDF_AXIS_MAP"
export RDF_RAW_WRIST_POS_YAW_OFFSET_DEG="$RDF_YAW_OFFSET"
export RDF_ACTION_POS_GAIN="${RDF_ACTION_POS_GAIN:-0.40}"
export RDF_ACTION_ROT_GAIN="${RDF_ACTION_ROT_GAIN:-0.35}"
export RDF_TELEOP_CONTROL_MODE="$RDF_CONTROL_MODE"
export RDF_DIRECT_EE_POS_GAIN="${RDF_DIRECT_EE_POS_GAIN:-0.18}"
export RDF_DIRECT_EE_ROT_GAIN="${RDF_DIRECT_EE_ROT_GAIN:-0.25}"
export RDF_DIRECT_EE_MAX_STEP_M="${RDF_DIRECT_EE_MAX_STEP_M:-0.04}"
export RDF_DIRECT_EE_MAX_ROT_STEP_RAD="${RDF_DIRECT_EE_MAX_ROT_STEP_RAD:-0.12}"
export RDF_DIRECT_EE_SMOOTHING_ALPHA="${RDF_DIRECT_EE_SMOOTHING_ALPHA:-0.50}"
export RDF_DIRECT_EE_DEADZONE_M="${RDF_DIRECT_EE_DEADZONE_M:-0.003}"
export RDF_DIRECT_EE_WORKSPACE_RADIUS_M="${RDF_DIRECT_EE_WORKSPACE_RADIUS_M:-0.35}"
export RDF_RAW_WRIST_JUMP_WARN_M="${RDF_RAW_WRIST_JUMP_WARN_M:-0.10}"
export RDF_RAW_WRIST_JUMP_REJECT_M="${RDF_RAW_WRIST_JUMP_REJECT_M:-0.15}"
export RDF_RAW_WRIST_REACQUIRE_VALID_FRAMES="${RDF_RAW_WRIST_REACQUIRE_VALID_FRAMES:-3}"
export RDF_RAW_WRIST_REACQUIRE_STABLE_M="${RDF_RAW_WRIST_REACQUIRE_STABLE_M:-0.03}"
export RDF_AUTO_RECENTER_STABLE_M="${RDF_AUTO_RECENTER_STABLE_M:-0.03}"
if [[ "$IS_GATE0_MODE" == "1" ]]; then
  export RDF_GATE0_TEST_TYPE
  export RDF_GATE_A_COLLECTION_BLOCKED="1"
  export RDF_AUTO_SUCCESS_FINALIZE="0"
  export RDF_AUTO_FINALIZE_REQUIRE_LIVE_CURATION="0"
  export RDF_EXIT_AFTER_FINALIZE="0"
  export RDF_LIVE_CURATION_ON_FAIL="hold"
  export RDF_MAX_FRAMES="${RDF_MAX_FRAMES:-240}"
fi
if [[ "$MODE" == "free-motion" || "$MODE" == "raw-wrist-direct" || "$IS_GATE0_MODE" == "1" ]]; then
  export RDF_RECENTER_MODE="first_valid_hand"
  export RDF_AUTO_RECENTER_VALID_FRAMES="${RDF_AUTO_RECENTER_VALID_FRAMES:-15}"
  export RDF_RECENTER_BOX_CENTER_SOURCE="hole_target_approach"
  export RDF_RECENTER_BOX_APPROACH_OFFSET="0,0,0.08"
  export RDF_RECENTER_BOX_RANDOM_OFFSET="0,0,0"
  export RDF_RECENTER_BOX_HALF_EXTENTS="0.09,0.09,0.09"
  export RDF_RECENTER_BOX_VISUAL="0"
  export RDF_BLOCK_TELEOP_UNTIL_RECENTER="0"
  export RDF_RECENTER_SETUP_CONTROL="0"
else
  export RDF_RECENTER_MODE="robot_start_box"
  export RDF_AUTO_RECENTER_VALID_FRAMES="${RDF_AUTO_RECENTER_VALID_FRAMES:-15}"
  export RDF_RECENTER_BOX_CENTER_SOURCE="hole_target_approach"
  export RDF_RECENTER_BOX_APPROACH_OFFSET="0,0,0.08"
  export RDF_RECENTER_BOX_RANDOM_OFFSET="0,0,0"
  export RDF_RECENTER_BOX_HALF_EXTENTS="0.09,0.09,0.09"
  export RDF_RECENTER_BOX_VISUAL="0"
  export RDF_BLOCK_TELEOP_UNTIL_RECENTER="1"
  export RDF_RECENTER_SETUP_CONTROL="1"
fi
export RDF_VISUAL_DEBUG="0"
export RDF_DEBUG_ACTION_EVERY="${RDF_DEBUG_ACTION_EVERY:-1}"
export RDF_DEBUG_MOTION_EVERY="${RDF_DEBUG_MOTION_EVERY:-1}"
export RDF_AUTO_SUCCESS_FINALIZE="0"
export RDF_AUTO_FINALIZE_REQUIRE_LIVE_CURATION="0"
export RDF_EXIT_AFTER_FINALIZE="0"

cat <<INFO
[RDF][HMD_AXIS_DEBUG] recenter_mode=$RDF_RECENTER_MODE block_until_recenter=$RDF_BLOCK_TELEOP_UNTIL_RECENTER setup_control=$RDF_RECENTER_SETUP_CONTROL
INFO

RUN_ARGS=("$@")
if [[ ${#RUN_ARGS[@]} -eq 0 ]]; then
  RUN_ARGS=(--no-start-xr)
fi

if [[ "$IS_GATE0_ALL" == "1" ]]; then
  GATE0_ALL_MODES=(
    "gate0-static"
    "gate0-slow-motion"
    "gate0-recenter"
    "gate0-reacquire"
  )
  GATE0_ALL_REPORTS=()
  ALL_STATUS=0

  cat <<INFO

[RDF][HMD_AXIS_DEBUG] Gate 0 batch sequence:
  1) gate0-static: keep right hand still.
  2) gate0-slow-motion: move right hand slowly in a small range.
  3) gate0-recenter: keep hand stable and let recenter gate prove stability.
  4) gate0-reacquire: briefly hide/reveal right hand, then hold still.
[RDF][HMD_AXIS_DEBUG] Keep the HMD on; no Gate A collection will be resumed by this batch.
INFO

  for child_mode in "${GATE0_ALL_MODES[@]}"; do
    child_log="$RDF_HMD_LOG_DIR/hmd_axis_debug_${HMD_LOG_TS}_${child_mode}.log"
    child_summary="$child_log.summary.json"
    child_report="$child_log.gate0.json"
    GATE0_ALL_REPORTS+=("$child_report")

    cat <<INFO

[RDF][HMD_AXIS_DEBUG] Gate 0 batch starting stage=$child_mode
[RDF][HMD_AXIS_DEBUG] child_log=$child_log
[RDF][HMD_AXIS_DEBUG] child_report=$child_report
INFO

    set +e
    RDF_HMD_LOG_FILE="$child_log" \
      RDF_HMD_LOG_SUMMARY_FILE="$child_summary" \
      RDF_GATE0_REPORT_FILE="$child_report" \
      RDF_GATE0_ALL_PARENT_LOG="$RDF_HMD_LOG_FILE" \
      ./scripts/run_hmd_axis_debug.sh "$child_mode" "${RUN_ARGS[@]}"
    child_status=$?
    set -e
    if [[ "$child_status" -ne 0 ]]; then
      ALL_STATUS="$child_status"
      echo "[RDF][HMD_AXIS_DEBUG] Gate 0 batch stage failed: mode=$child_mode status=$child_status" >&2
    fi
  done

  uv run python - "$RDF_GATE0_ALL_REPORT_FILE" "${GATE0_ALL_MODES[@]}" -- "${GATE0_ALL_REPORTS[@]}" <<'PY'
import json
import sys
from pathlib import Path

separator = sys.argv.index("--")
output_path = Path(sys.argv[1])
modes = sys.argv[2:separator]
report_paths = [Path(path) for path in sys.argv[separator + 1 :]]
stages = []
failure_reasons = set()

for mode, report_path in zip(modes, report_paths, strict=False):
    stage = {
        "mode": mode,
        "report_path": str(report_path),
        "exists": report_path.exists(),
        "gate0_pass": False,
        "failure_reasons": ["MISSING_GATE0_REPORT"],
    }
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            stage["failure_reasons"] = [f"INVALID_GATE0_REPORT:{type(exc).__name__}"]
        else:
            stage["gate0_pass"] = bool(report.get("gate0_pass"))
            stage["gate_a_collection_allowed"] = bool(report.get("gate_a_collection_allowed"))
            stage["failure_reasons"] = list(report.get("failure_reasons") or [])
            stage["input_source"] = report.get("input_source")
            stage["H13"] = report.get("H13")
            stage["metrics"] = report.get("metrics")
    failure_reasons.update(stage["failure_reasons"])
    stages.append(stage)

gate0_all_pass = bool(stages) and all(stage["gate0_pass"] for stage in stages)
input_sources = []
seen_input_sources = set()
for stage in stages:
    input_source = stage.get("input_source")
    if not input_source:
        continue
    key = json.dumps(input_source, sort_keys=True)
    if key not in seen_input_sources:
        seen_input_sources.add(key)
        input_sources.append(input_source)
aggregate = {
    "schema_version": "rdf_gate0_all_report_v0.1.0",
    "gate0_all_pass": gate0_all_pass,
    "gate_a_collection_allowed": gate0_all_pass,
    "stage_order": modes,
    "stages": stages,
    "failure_reasons": sorted(failure_reasons),
    "input_sources": input_sources,
}
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(aggregate, indent=2, sort_keys=True), encoding="utf-8")
print(f"[RDF][GATE0_ALL] report={output_path}")
print(
    "[RDF][GATE0_ALL] "
    f"gate0_all_pass={gate0_all_pass} "
    f"gate_a_collection_allowed={gate0_all_pass} "
    f"failure_reasons={','.join(aggregate['failure_reasons']) or 'none'}"
)
PY

  exit "$ALL_STATUS"
fi

set +e
./scripts/run_live_rdf_smoke_test.sh "${RUN_ARGS[@]}"
RUN_STATUS=$?
set -e

cat <<INFO

[RDF][HMD_AXIS_DEBUG] post-run latest-file check, including zero-frame latest:
INFO
uv run python scripts/verify_latest_rdf_recording.py --include-empty-latest --pretty || true

cat <<INFO

[RDF][HMD_AXIS_DEBUG] post-run latest non-empty mapping analysis:
If this run saved 0 frames, the analyzer below intentionally falls back to the
latest previous non-empty trajectory. Treat that as historical context, not as
proof for the just-finished run.
INFO
uv run python scripts/analyze_hmd_motion_mapping.py \
  --latest \
  --pretty \
  --output storage/hmd_motion_mapping/latest_mapping_report.json || true

cat <<INFO

[RDF][HMD_AXIS_DEBUG] post-run collected log/artifact summary:
INFO
uv run python scripts/summarize_hmd_run_log.py \
  --log-file "$RDF_HMD_LOG_FILE" \
  --output "$RDF_HMD_LOG_SUMMARY_FILE" \
  --pretty || true

if [[ "$IS_GATE0_MODE" == "1" ]]; then
  cat <<INFO

[RDF][HMD_AXIS_DEBUG] Gate 0 XR input stream viability report:
INFO
  uv run python scripts/run_gate0_xr_input_viability.py \
    --latest \
    --test-type "$RDF_GATE0_TEST_TYPE" \
    --log-file "$RDF_HMD_LOG_FILE" \
    --output "$RDF_GATE0_REPORT_FILE" \
    --pretty || true
fi

exit "$RUN_STATUS"
