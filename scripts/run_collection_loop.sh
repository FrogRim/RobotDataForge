#!/usr/bin/env bash
# Gate A pass episode 수집 루프.
# 매 iteration마다 smoke test를 1회 실행하고, offline diagnostic의 Gate A count를 확인한다.
# TARGET 도달 시 종료. Ctrl+C로 언제든 중단 가능.
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TARGET="${GATE_A_TARGET:-10}"
DATABASE_URL="${DATABASE_URL:-sqlite:///./storage/local_api.sqlite}"
STORAGE_ROOT="${STORAGE_ROOT:-storage}"
DIAG_OUTPUT_DIR="${DIAG_OUTPUT_DIR:-storage/mvp2_curation_diagnostic}"
RDF_GATE0_REQUIRED_REPORT="${RDF_GATE0_REQUIRED_REPORT:-}"
RDF_GATE0_REPORT_MAX_AGE_SEC="${RDF_GATE0_REPORT_MAX_AGE_SEC:-3600}"
RDF_COLLECTION_LOOP_GATE0_PREFLIGHT_ONLY="${RDF_COLLECTION_LOOP_GATE0_PREFLIGHT_ONLY:-0}"

ATTEMPT=0

log() { printf '[LOOP][%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }

latest_gate0_all_report() {
  if [ -n "$RDF_GATE0_REQUIRED_REPORT" ]; then
    printf '%s\n' "$RDF_GATE0_REQUIRED_REPORT"
    return 0
  fi
  python3 - "$STORAGE_ROOT" <<'PY'
from pathlib import Path
import sys

storage_root = Path(sys.argv[1])
reports = sorted(
    (storage_root / "logs" / "hmd_axis_debug").glob("*.gate0_all.json"),
    key=lambda item: item.stat().st_mtime,
    reverse=True,
)
print(reports[0] if reports else "")
PY
}

require_gate0_pass() {
  local report_path
  report_path="$(latest_gate0_all_report)"
  if [ -z "$report_path" ] || [ ! -f "$report_path" ]; then
    log "ERROR: Gate A collection blocked: missing Gate 0 aggregate report (*.gate0_all.json)"
    log "Run ./scripts/run_hmd_axis_debug.sh gate0-all and require gate0_all_pass=true first."
    exit 42
  fi

  python3 - "$report_path" "$RDF_GATE0_REPORT_MAX_AGE_SEC" <<'PY'
import json
import sys
import time
from pathlib import Path

path = Path(sys.argv[1])
try:
    max_age_sec = float(sys.argv[2])
except (TypeError, ValueError):
    max_age_sec = 0.0


def block(reason, **fields):
    details = " ".join(f"{key}={value}" for key, value in fields.items())
    suffix = f" {details}" if details else ""
    print(f"[LOOP][GATE0] BLOCK report={path} reason={reason}{suffix}")
    raise SystemExit(42)


if max_age_sec <= 0:
    block("INVALID_GATE0_MAX_AGE_SEC", max_age_sec=sys.argv[2])

age_sec = time.time() - path.stat().st_mtime
if age_sec < -1.0 or age_sec > max_age_sec:
    block(
        "STALE_GATE0_REPORT",
        age_sec=f"{age_sec:.1f}",
        max_age_sec=f"{max_age_sec:.1f}",
    )

with path.open(encoding="utf-8") as handle:
    report = json.load(handle)

expected_modes = [
    "gate0-static",
    "gate0-slow-motion",
    "gate0-recenter",
    "gate0-reacquire",
]
if report.get("schema_version") != "rdf_gate0_all_report_v0.1.0":
    block("INVALID_GATE0_SCHEMA", schema=report.get("schema_version"))
if report.get("stage_order") != expected_modes:
    block("INVALID_GATE0_STAGE_ORDER", stage_order=report.get("stage_order"))

stages = report.get("stages")
if not isinstance(stages, list) or len(stages) != len(expected_modes):
    block("INVALID_GATE0_STAGE_COUNT", stage_count=len(stages) if isinstance(stages, list) else "not-list")

source_ids = set()
for expected_mode, stage in zip(expected_modes, stages, strict=True):
    if not isinstance(stage, dict):
        block("INVALID_GATE0_STAGE", mode=expected_mode)
    if stage.get("mode") != expected_mode:
        block("INVALID_GATE0_STAGE_MODE", expected=expected_mode, actual=stage.get("mode"))
    if stage.get("exists") is not True:
        block("MISSING_GATE0_STAGE_REPORT", mode=expected_mode)
    if stage.get("gate0_pass") is not True:
        block("GATE0_STAGE_FAILED", mode=expected_mode)
    if stage.get("gate_a_collection_allowed") is not True:
        block("GATE0_STAGE_COLLECTION_NOT_ALLOWED", mode=expected_mode)
    stage_reasons = stage.get("failure_reasons") or []
    if stage_reasons:
        block("GATE0_STAGE_FAILURE_REASONS", mode=expected_mode, reasons=",".join(map(str, stage_reasons)))
    input_source = stage.get("input_source") or {}
    if input_source.get("adapter_status") != "matched_source" or not input_source.get("source_id"):
        block(
            "INPUT_SOURCE_UNVERIFIED",
            mode=expected_mode,
            adapter_status=input_source.get("adapter_status"),
            source_id=input_source.get("source_id"),
        )
    source_ids.add(str(input_source["source_id"]))
if len(source_ids) != 1:
    block("MIXED_INPUT_SOURCE", source_ids=",".join(sorted(source_ids)))

aggregate_reasons = report.get("failure_reasons") or []
if aggregate_reasons:
    block("GATE0_AGGREGATE_FAILURE_REASONS", reasons=",".join(map(str, aggregate_reasons)))

gate0_all_pass = report.get("gate0_all_pass") is True
gate_a_collection_allowed = report.get("gate_a_collection_allowed") is True
if gate0_all_pass and gate_a_collection_allowed:
    print(f"[LOOP][GATE0] PASS report={path}")
    raise SystemExit(0)

reasons = report.get("failure_reasons") or []
print(
    "[LOOP][GATE0] BLOCK "
    f"report={path} "
    f"gate0_all_pass={gate0_all_pass} "
    f"gate_a_collection_allowed={gate_a_collection_allowed} "
    f"failure_reasons={','.join(map(str, reasons)) or 'none'}"
)
raise SystemExit(42)
PY
}

count_gate_a_episodes() {
  uv run python scripts/run_mvp2_curation_diagnostic.py --output-dir "$DIAG_OUTPUT_DIR" >/tmp/rdf_mvp2_curation_diagnostic_loop.log
  python3 - "$DIAG_OUTPUT_DIR/mvp2_curation_diagnostic_report.json" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    report = json.load(handle)
print(int((report.get("summary") or {}).get("gate_A_pass_count") or 0))
PY
}

log "수집 루프 시작: 목표 Gate A pass episode ${TARGET}개"
log "Ctrl+C로 언제든 중단 가능"
require_gate0_pass
if [ "$RDF_COLLECTION_LOOP_GATE0_PREFLIGHT_ONLY" = "1" ]; then
  log "Gate 0 preflight-only check passed; exiting before collection."
  exit 0
fi

while true; do
  ATTEMPT=$((ATTEMPT + 1))

  CURRENT=$(count_gate_a_episodes)
  log "현재 Gate A pass=${CURRENT} / 목표=${TARGET} (시도 #${ATTEMPT})"

  if [ "${CURRENT}" -ge "${TARGET}" ]; then
    log "목표 달성! Gate A pass=${CURRENT}개. 루프 종료."
    break
  fi

  log "--- Isaac 세션 시작 (시도 #${ATTEMPT}) ---"

  RDF_ISAAC_TASK=Isaac-Forge-PegInsert-Direct-v0 \
    RDF_TASK_TYPE=peg_in_hole \
    RDF_MAX_FRAMES=600 \
    RDF_WARMUP_VALID_FRAMES=10 \
    RDF_ACTION_POS_AXIS_MAP="${RDF_ACTION_POS_AXIS_MAP:-x,z,y}" \
    RDF_TELEOP_CONTROL_MODE=bounded_direct_ee_target \
    RDF_AUTO_SUCCESS_FINALIZE=1 \
    RDF_AUTO_FINALIZE_REQUIRE_LIVE_CURATION=1 \
    RDF_LIVE_CURATION_MAX_SEAT_ACTION_SATURATION_RATIO=0.30 \
    RDF_LIVE_CURATION_ON_FAIL=reset \
    RDF_RECENTER_MODE=robot_start_box \
    RDF_RECENTER_BOX_CENTER_SOURCE=hole_target_approach \
    RDF_RECENTER_BOX_APPROACH_OFFSET=0,0,0.08 \
    RDF_RECENTER_BOX_RANDOM_OFFSET=0.02,0.02,0.01 \
    RDF_RECENTER_BOX_VISUAL="${RDF_RECENTER_BOX_VISUAL:-0}" \
    RDF_BLOCK_TELEOP_UNTIL_RECENTER=1 \
    RDF_RECENTER_SETUP_CONTROL=1 \
    RDF_EXIT_AFTER_FINALIZE=1 \
    DATABASE_URL="$DATABASE_URL" \
    STORAGE_ROOT="$STORAGE_ROOT" \
    "$ROOT/scripts/run_live_rdf_smoke_test.sh" --no-start-xr || true

  log "--- 세션 종료 (시도 #${ATTEMPT}) ---"

  # Isaac/SteamVR 정리 대기
  sleep 3
done

FINAL=$(count_gate_a_episodes)
log "완료: 총 Gate A pass episode ${FINAL}개 수집됨 (총 시도 ${ATTEMPT}회)"
