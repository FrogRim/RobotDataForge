#!/usr/bin/env python3
"""Apply a real recorded-action replay report to a live trajectory.

This script is intentionally offline. It consumes a replay report produced by
``scripts/check_peg_insert_viability.py`` and writes the replay evidence into
``trajectory.summary.action_replay_gate``. Live export curation only promotes
HMD trajectories after this field is present and passed.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPLAY_REPORT = ROOT / "storage" / "logs" / "peg_insert_viability_report.json"
DEFAULT_TRAJECTORY_DIR = ROOT / "storage" / "trajectories"
DEFAULT_SQLITE_DB = ROOT / "storage" / "local_api.sqlite"
SCHEMA_VERSION = "rdf_live_action_replay_gate_v0.1.0"


def stable_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload) + "\n", encoding="utf-8")


def _replay_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    checks = report.get("checks") if isinstance(report.get("checks"), dict) else {}
    rows = checks.get("accepted_replays") if isinstance(checks.get("accepted_replays"), list) else []
    return [row for row in rows if isinstance(row, dict)]


def _match_row(
    report: dict[str, Any],
    *,
    trajectory_id: str,
    replay_mode: str,
    action_field: str,
) -> dict[str, Any] | None:
    for row in _replay_rows(report):
        if row.get("trajectory_id") != trajectory_id:
            continue
        if row.get("mode") != replay_mode:
            continue
        if row.get("action_field") != action_field:
            continue
        return row
    return None


def _trajectory_path(trajectory_dir: Path, trajectory_id: str) -> Path:
    return trajectory_dir / f"{trajectory_id}.json"


def _update_sqlite_summary(sqlite_db: Path, trajectory_id: str, summary: dict[str, Any]) -> bool:
    if not sqlite_db.exists():
        return False
    with sqlite3.connect(sqlite_db) as connection:
        cursor = connection.execute(
            "UPDATE trajectories SET summary = ? WHERE id = ?",
            (json.dumps(summary, ensure_ascii=False), trajectory_id),
        )
        connection.commit()
        return cursor.rowcount > 0


def apply_live_replay_gate(
    *,
    replay_report_path: Path,
    trajectory_path: Path,
    replay_mode: str = "native_direct",
    action_field: str = "retargeted_robot_action",
    require_pass: bool = True,
    sqlite_db: Path | None = DEFAULT_SQLITE_DB,
) -> dict[str, Any]:
    report = read_json(replay_report_path)
    trajectory = read_json(trajectory_path)
    trajectory_id = str(trajectory.get("id") or trajectory_path.stem)
    row = _match_row(
        report,
        trajectory_id=trajectory_id,
        replay_mode=replay_mode,
        action_field=action_field,
    )
    if row is None:
        raise SystemExit(
            f"No replay row found for trajectory={trajectory_id} mode={replay_mode} action_field={action_field}"
        )
    if require_pass and row.get("passed") is not True:
        raise SystemExit(f"Replay row did not pass for trajectory={trajectory_id}: {row.get('passed')!r}")
    before = row.get("before") if isinstance(row.get("before"), dict) else {}
    started_in_success = before.get("success") is True
    limitations = [
        "This verifies simulator recorded-action replay only.",
        "This does not claim real robot replay.",
        "This gate must be regenerated if trajectory actions or success criteria change.",
    ]
    if started_in_success:
        limitations.append(
            "Replay reset was already inside the selected success criteria; this verifies a stable success hold, not an approach-to-success transition."
        )

    gate = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "passed": row.get("passed") is True,
        "trajectory_id": trajectory_id,
        "episode_id": row.get("episode_id") or trajectory.get("episode_id"),
        "replay_report_path": str(replay_report_path),
        "trajectory_path": str(trajectory_path),
        "replay_mode": row.get("mode"),
        "action_field": row.get("action_field"),
        "requested_success_evaluator": row.get("requested_success_evaluator"),
        "selected_success_evaluator": row.get("selected_success_evaluator"),
        "success_step": row.get("success_step"),
        "frame_count": row.get("frame_count"),
        "missing_action_count": row.get("missing_action_count"),
        "replay_seed": row.get("replay_seed"),
        "replay_seed_source": row.get("replay_seed_source"),
        "started_in_success": started_in_success,
        "before": row.get("before"),
        "after": row.get("after"),
        "limitations": limitations,
    }

    summary = trajectory.setdefault("summary", {})
    if not isinstance(summary, dict):
        summary = {}
        trajectory["summary"] = summary
    summary["action_replay_gate"] = gate
    write_json(trajectory_path, trajectory)

    sqlite_updated = False
    if sqlite_db is not None:
        sqlite_updated = _update_sqlite_summary(sqlite_db, trajectory_id, summary)

    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": gate["created_at"],
        "passed": gate["passed"],
        "trajectory_id": trajectory_id,
        "episode_id": gate["episode_id"],
        "replay_report_path": str(replay_report_path),
        "trajectory_path": str(trajectory_path),
        "sqlite_db": str(sqlite_db) if sqlite_db else None,
        "sqlite_updated": sqlite_updated,
        "action_replay_gate": gate,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-report", type=Path, default=DEFAULT_REPLAY_REPORT)
    parser.add_argument("--trajectory", type=Path)
    parser.add_argument("--trajectory-id")
    parser.add_argument("--trajectory-dir", type=Path, default=DEFAULT_TRAJECTORY_DIR)
    parser.add_argument("--replay-mode", default="native_direct", choices=("native_direct", "metric_delta_to_native"))
    parser.add_argument("--action-field", default="retargeted_robot_action")
    parser.add_argument("--allow-failed", action="store_true")
    parser.add_argument("--sqlite-db", type=Path, default=DEFAULT_SQLITE_DB)
    parser.add_argument("--no-sqlite-update", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.trajectory is None and not args.trajectory_id:
        raise SystemExit("Provide --trajectory or --trajectory-id")
    trajectory_path = args.trajectory or _trajectory_path(args.trajectory_dir, str(args.trajectory_id))
    result = apply_live_replay_gate(
        replay_report_path=args.replay_report,
        trajectory_path=trajectory_path,
        replay_mode=args.replay_mode,
        action_field=args.action_field,
        require_pass=not args.allow_failed,
        sqlite_db=None if args.no_sqlite_update else args.sqlite_db,
    )
    if args.pretty:
        print(stable_json(result))
    else:
        status = "PASS" if result["passed"] else "FAIL"
        print(f"RDF live replay gate: {status}")
        print(f"trajectory={result['trajectory_id']}")
        print(f"sqlite_updated={result['sqlite_updated']}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
