#!/usr/bin/env python3
"""Run the MVP-0 offline diagnostics bundle.

This script intentionally does not launch Quest, ALVR, SteamVR, or Isaac.
It bundles the checks that can be run before or after a user-managed live run:

1. runtime preflight
2. latest trajectory/evaluation validation
3. teleop calibration/action-filter analysis
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from analyze_teleop_calibration import analyze_trajectory
from check_rdf_runtime_env import DEFAULT_API_BASE, check_environment
from verify_latest_rdf_recording import DEFAULT_STORAGE_ROOT, latest_file, verify_recording


SCHEMA_VERSION = "rdf_mvp0_offline_diagnostics_v0.1.0"


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _trajectory_frame_count(path: Path) -> int:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return 0
    frames = data.get("frames") if isinstance(data, dict) else None
    return len([frame for frame in frames if isinstance(frame, dict)]) if isinstance(frames, list) else 0


def _latest_nonempty_trajectory(storage_root: Path) -> Path | None:
    paths = sorted((storage_root / "trajectories").glob("*.json"), key=lambda path: path.stat().st_mtime)
    for path in reversed(paths):
        if _trajectory_frame_count(path) > 0:
            return path
    return paths[-1] if paths else None


def _next_actions(report: dict[str, Any]) -> list[str]:
    actions: list[str] = []
    preflight = report.get("preflight") or {}
    recording = report.get("recording") or {}
    calibration = report.get("calibration_analysis") or {}

    if not preflight.get("passed"):
        actions.append("Fix FAIL items in preflight before wearing Quest 3.")
    recording_issues = recording.get("issues") or []
    if not recording.get("passed"):
        if any("workspace_alignment_v2 was created after captured frames" in issue for issue in recording_issues):
            actions.append("Increase RDF_MAX_FRAMES and press P earlier so calibrated frames are actually recorded.")
        elif any("trajectory has no frame" in issue for issue in recording_issues):
            actions.append("Use a non-empty finalized trajectory or rerun after hand tracking starts recording frames.")
        else:
            actions.append("Inspect recording.issues and rerun verify_latest_rdf_recording.py with --pretty.")
    aggregate = calibration.get("aggregate") or {}
    if aggregate.get("issue_count"):
        actions.append("Inspect calibration_analysis.trajectories[].issues before using this recording.")
    for trajectory_report in calibration.get("trajectories") or []:
        for recommendation in trajectory_report.get("recommendations") or []:
            if recommendation not in actions:
                actions.append(recommendation)
    if not actions:
        actions.append("Offline diagnostics passed. Next evidence must come from a user-run Quest/Isaac live test.")
    return actions


def run_diagnostics(
    *,
    repo_root: Path,
    home: Path,
    storage_root: Path,
    api_base: str,
    trajectory_path: Path | None,
    allow_legacy: bool,
    require_running_xr: bool,
) -> dict[str, Any]:
    selected_trajectory_path = trajectory_path or _latest_nonempty_trajectory(storage_root)
    trajectory_selection = "explicit" if trajectory_path is not None else "latest_nonempty"
    preflight_report = check_environment(
        repo_root=repo_root,
        home=home,
        api_base=api_base,
        require_running_xr=require_running_xr,
    )
    recording_report = verify_recording(
        storage_root=storage_root,
        trajectory_path=selected_trajectory_path,
        allow_legacy=allow_legacy,
    )

    analysis_reports: list[dict[str, Any]] = []
    analysis_error: str | None = None
    analysis_path = selected_trajectory_path
    if analysis_path is None and recording_report.get("trajectory_path"):
        analysis_path = Path(str(recording_report["trajectory_path"]))
    if analysis_path is None:
        latest = latest_file(storage_root / "trajectories")
        analysis_path = latest

    if analysis_path is not None:
        try:
            analysis_reports.append(analyze_trajectory(analysis_path))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            analysis_error = str(exc)
    else:
        analysis_error = f"No trajectory JSON files found under {storage_root / 'trajectories'}"

    calibration_report = {
        "schema_version": "rdf_teleop_calibration_analysis_v0.1.0",
        "aggregate": {
            "trajectory_count": len(analysis_reports),
            "total_frames": sum(int(item.get("frame_count") or 0) for item in analysis_reports),
            "issue_count": sum(len(item.get("issues") or []) for item in analysis_reports) + (1 if analysis_error else 0),
            "warning_count": sum(len(item.get("warnings") or []) for item in analysis_reports),
            "trajectory_ids": [item.get("trajectory_id") for item in analysis_reports],
        },
        "trajectories": analysis_reports,
        "error": analysis_error,
    }

    passed = (
        bool(preflight_report.get("passed"))
        and bool(recording_report.get("passed"))
        and calibration_report["aggregate"]["issue_count"] == 0
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "passed": passed,
        "goal_scope": "MVP-0 hardening/live validation offline diagnostics",
        "live_quest_isaac_required_for_codex_completion": False,
        "preflight": preflight_report,
        "recording": recording_report,
        "calibration_analysis": calibration_report,
        "trajectory_selection": {
            "mode": trajectory_selection,
            "path": str(selected_trajectory_path) if selected_trajectory_path else None,
        },
    }
    report["next_actions"] = _next_actions(report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RDF MVP-0 offline diagnostics bundle.")
    parser.add_argument("--repo-root", type=Path, default=Path("/home/kangrim/robot-data-forge"))
    parser.add_argument("--home", type=Path, default=Path("/home/kangrim"))
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    parser.add_argument("--api-base", default=DEFAULT_API_BASE)
    parser.add_argument("--trajectory", type=Path, help="Specific trajectory JSON to validate/analyze.")
    parser.add_argument("--allow-legacy", action="store_true", help="Treat new field gaps as warnings where possible.")
    parser.add_argument("--require-running-xr", action="store_true", help="Fail preflight if ALVR/SteamVR are not running.")
    parser.add_argument("--json", action="store_true", help="Print compact JSON.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    return parser.parse_args()


def _print_text(report: dict[str, Any]) -> None:
    print(f"RDF MVP-0 offline diagnostics: {'PASS' if report['passed'] else 'FAIL'}")
    preflight_summary = report["preflight"]["summary"]
    print(
        "preflight: "
        f"pass={preflight_summary['pass']} warn={preflight_summary['warn']} fail={preflight_summary['fail']}"
    )
    print(
        "recording: "
        f"passed={report['recording']['passed']} "
        f"trajectory={report['recording'].get('trajectory_id')} "
        f"frames={report['recording'].get('frame_count')}"
    )
    calibration = report["calibration_analysis"]["aggregate"]
    print(
        "calibration: "
        f"trajectories={calibration['trajectory_count']} "
        f"frames={calibration['total_frames']} "
        f"issues={calibration['issue_count']} "
        f"warnings={calibration['warning_count']}"
    )
    for action in report["next_actions"]:
        print(f"next: {action}")


def main() -> int:
    args = parse_args()
    report = run_diagnostics(
        repo_root=args.repo_root,
        home=args.home,
        storage_root=args.storage_root,
        api_base=args.api_base,
        trajectory_path=args.trajectory,
        allow_legacy=args.allow_legacy,
        require_running_xr=args.require_running_xr,
    )
    if args.pretty:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    elif args.json:
        print(stable_json(report))
    else:
        _print_text(report)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
