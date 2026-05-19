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

ATTEMPT=0

log() { printf '[LOOP][%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }

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
    RDF_TELEOP_CONTROL_MODE=bounded_direct_ee_target \
    RDF_AUTO_SUCCESS_FINALIZE=1 \
    RDF_AUTO_FINALIZE_REQUIRE_LIVE_CURATION=1 \
    RDF_LIVE_CURATION_MAX_SEAT_ACTION_SATURATION_RATIO=0.30 \
    RDF_LIVE_CURATION_ON_FAIL=reset \
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
