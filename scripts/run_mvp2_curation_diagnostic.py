#!/usr/bin/env python3
"""Run MVP-2 offline curation diagnostics.

This is a read-only diagnostic over stored artifacts. Trajectory JSON frames are
the source of truth for newly computed metrics. Evaluation JSON files are used
only as the recorded baseline for comparing historical gate decisions.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "rdf_mvp2_curation_diagnostic_v0.1.0"
DEFAULT_TRAJECTORIES_DIR = ROOT / "storage" / "trajectories"
DEFAULT_EVALUATIONS_DIR = ROOT / "storage" / "evaluations"
DEFAULT_OUTPUT_DIR = ROOT / "storage" / "mvp2_curation_diagnostic"

SUPPORTED_PHASES = {
    "APPROACH",
    "ALIGN",
    "CONTACT",
    "INSERT",
    "SEAT",
    "STABILIZE",
    "RELEASE",
    "RECOVER",
    "UNKNOWN",
}
SATURATION_PHASES = ("APPROACH", "CONTACT", "INSERT", "SEAT")
ORDERED_PHASES = ("APPROACH", "CONTACT", "INSERT", "SEAT")


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)


def read_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return data


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _normalize_phase(value: Any) -> str | None:
    if value is None:
        return None
    phase = str(value).strip().upper()
    return phase if phase in SUPPORTED_PHASES else None


def read_phase(frame: dict[str, Any]) -> tuple[str, str]:
    """Return (phase, source) using metadata -> task_state -> frame fallback."""
    metadata = _dict_or_empty(frame.get("metadata"))

    phase = _normalize_phase(metadata.get("action_phase"))
    if phase is not None:
        return phase, "metadata"

    task_state = _dict_or_empty(metadata.get("task_state"))
    phase = _normalize_phase(task_state.get("action_phase"))
    if phase is not None:
        return phase, "task_state"

    phase = _normalize_phase(frame.get("action_phase"))
    if phase is not None:
        return phase, "action"

    return "UNKNOWN", "default"


def compute_phase_coverage(frames: list[dict[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    for frame in frames:
        phase, source = read_phase(frame)
        counts[phase] += 1
        source_counts[source] += 1

    total = len(frames)
    rates = {phase: count / total for phase, count in counts.items()} if total else {}
    return {
        "phase_counts": dict(sorted(counts.items())),
        "phase_rates": dict(sorted(rates.items())),
        "phase_source_distribution": dict(sorted(source_counts.items())),
    }


def _float_vector(
    value: Any, *, min_len: int, limit: int | None = None
) -> list[float] | None:
    if not isinstance(value, list) or len(value) < min_len:
        return None
    output: list[float] = []
    for item in value[: limit or len(value)]:
        try:
            output.append(float(item))
        except (TypeError, ValueError):
            return None
    return output


def is_frame_saturated(frame: dict[str, Any], threshold: float = 0.999) -> bool | None:
    """Return saturation for action[:6]; index 6 is gripper and excluded."""
    action = _dict_or_empty(frame.get("action"))
    vector = _float_vector(action.get("native_isaac_action"), min_len=6, limit=6)
    if vector is None:
        return None
    return any(abs(value) >= threshold for value in vector)


def _consecutive_max(flags: list[bool]) -> int:
    max_run = 0
    run = 0
    for flag in flags:
        run = run + 1 if flag else 0
        max_run = max(max_run, run)
    return max_run


def compute_phase_conditional_saturation(
    frames: list[dict[str, Any]], threshold: float
) -> dict[str, Any]:
    phase_flags: dict[str, list[bool]] = {}
    for frame in frames:
        saturated = is_frame_saturated(frame, threshold=threshold)
        if saturated is None:
            continue
        phase, _source = read_phase(frame)
        phase_flags.setdefault(phase, []).append(saturated)

    all_flags = [flag for flags in phase_flags.values() for flag in flags]
    result: dict[str, Any] = {
        "sat_ratio_aggregate": sum(all_flags) / len(all_flags) if all_flags else 0.0,
    }
    for phase in SATURATION_PHASES:
        flags = phase_flags.get(phase, [])
        result[f"sat_ratio_{phase}"] = sum(flags) / len(flags) if flags else 0.0
        result[f"consecutive_sat_max_{phase}"] = _consecutive_max(flags)
    return result


def get_applied_ee_delta(frame: dict[str, Any]) -> list[float] | None:
    """Return physical end-effector delta in meters using the documented fallback chain."""
    action = _dict_or_empty(frame.get("action"))
    control_filter = _dict_or_empty(action.get("control_filter"))
    teleop_control_mode = _dict_or_empty(control_filter.get("teleop_control_mode"))

    delta = _float_vector(
        teleop_control_mode.get("applied_ee_delta_m"), min_len=3, limit=3
    )
    if delta is not None:
        return delta

    executed_control = _dict_or_empty(action.get("executed_control"))
    applied_ee_action = _dict_or_empty(
        executed_control.get("applied_end_effector_action")
    )
    delta = _float_vector(applied_ee_action.get("delta_position"), min_len=3, limit=3)
    if delta is not None:
        return delta

    learning_action = _dict_or_empty(action.get("learning_action"))
    return _float_vector(learning_action.get("command"), min_len=3, limit=3)


def get_command_step_norm(frame: dict[str, Any]) -> float | None:
    action = _dict_or_empty(frame.get("action"))
    control_filter = _dict_or_empty(action.get("control_filter"))
    teleop_control_mode = _dict_or_empty(control_filter.get("teleop_control_mode"))
    value = teleop_control_mode.get("command_step_norm")
    if value is not None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    delta = get_applied_ee_delta(frame)
    if delta is None:
        return None
    return float(sum(axis * axis for axis in delta) ** 0.5)


def get_workspace_clamped(frame: dict[str, Any]) -> bool | None:
    action = _dict_or_empty(frame.get("action"))
    control_filter = _dict_or_empty(action.get("control_filter"))
    teleop_control_mode = _dict_or_empty(control_filter.get("teleop_control_mode"))
    value = teleop_control_mode.get("workspace_clamped")
    return bool(value) if value is not None else None


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    return sorted_values[max(0, int(len(sorted_values) * 0.95) - 1)]


def compute_command_quality(frames: list[dict[str, Any]]) -> dict[str, Any]:
    norms = [
        norm for frame in frames if (norm := get_command_step_norm(frame)) is not None
    ]

    jerks: list[float] = []
    previous_delta: list[float] | None = None
    for frame in frames:
        delta = get_applied_ee_delta(frame)
        if delta is not None and previous_delta is not None:
            jerks.append(
                sum(
                    (current - previous) ** 2
                    for current, previous in zip(delta, previous_delta)
                )
                ** 0.5
            )
        if delta is not None:
            previous_delta = delta

    clamped_values = [
        clamped
        for frame in frames
        if (clamped := get_workspace_clamped(frame)) is not None
    ]

    return {
        "command_step_norm_mean": sum(norms) / len(norms) if norms else None,
        "command_step_norm_p95": _p95(norms),
        "jerk_mean": sum(jerks) / len(jerks) if jerks else None,
        "jerk_p95": _p95(jerks),
        "workspace_clamped_ratio": (
            sum(1 for value in clamped_values if value) / len(clamped_values)
            if clamped_values
            else None
        ),
    }


def compute_gate_judgment(
    phase_counts: dict[str, int], config: dict[str, Any]
) -> dict[str, Any]:
    insert = phase_counts.get("INSERT", 0)
    seat = phase_counts.get("SEAT", 0)
    contact = phase_counts.get("CONTACT", 0)
    approach = phase_counts.get("APPROACH", 0)

    insert_min = int(config["insert_min_frames"])
    seat_min = int(config["seat_min_frames"])
    approach_min = int(config["approach_min_frames"])

    gate_a = contact >= 1 and insert >= insert_min and seat >= seat_min
    gate_b = gate_a and approach >= approach_min
    gate_c = insert >= insert_min

    gate_b_fail_reason: str | None = None
    if gate_a and not gate_b:
        gate_b_fail_reason = (
            "APPROACH_ABSENT" if approach == 0 else "APPROACH_INSUFFICIENT"
        )

    return {
        "gate_A_pass": gate_a,
        "gate_B_pass": gate_b,
        "gate_C_pass": gate_c,
        "gate_B_fail_reason": gate_b_fail_reason,
    }


def compute_cross_validation(
    sat_ratio_recomputed: float,
    recorded_failure_reason: str | None,
    max_ratio: float,
    recorded_native_action_saturation: str | None = None,
) -> dict[str, Any]:
    recomputed_sat_fail = sat_ratio_recomputed > max_ratio
    status = str(recorded_native_action_saturation or "").strip().lower()
    if status == "fail":
        recorded_sat_fail = True
        other_reason = False
    elif status == "pass":
        recorded_sat_fail = False
        other_reason = False
    else:
        recorded_sat_fail = recorded_failure_reason == "NATIVE_ACTION_SATURATION"
        other_reason = (
            recorded_failure_reason is not None
            and recorded_failure_reason != "NATIVE_ACTION_SATURATION"
        )
    gate_match: bool | None = (
        None if other_reason else recomputed_sat_fail == recorded_sat_fail
    )
    return {
        "sat_ratio_recomputed": sat_ratio_recomputed,
        "recomputed_sat_fail": recomputed_sat_fail,
        "recorded_sat_fail": recorded_sat_fail,
        "gate_match": gate_match,
        "gate_match_skipped_reason": "other_failure_reason" if other_reason else None,
    }


def load_eval_index(evaluations_dir: Path) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for path in sorted(evaluations_dir.glob("eval_*.json")):
        try:
            data = read_json_object(path)
        except (json.JSONDecodeError, OSError, ValueError):
            continue
        episode_id = data.get("episode_id")
        if episode_id is not None:
            index[str(episode_id)] = data
    return index


def _bool_or_none(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "pass", "passed", "yes", "1"}:
            return True
        if lowered in {"false", "fail", "failed", "no", "0"}:
            return False
    return bool(value)


def _extract_recorded_state(eval_record: dict[str, Any] | None) -> dict[str, Any]:
    if eval_record is None:
        return {
            "recorded_episode_status": None,
            "recorded_evaluator_success": None,
            "recorded_evaluator_failure_reason": None,
            "recorded_failure_reason": None,
            "recorded_live_curation_status": None,
            "recorded_training_eligible": None,
            "recorded_native_action_saturation": None,
            "recorded_native_action_saturation_ratio": None,
            "recorded_rejection_reasons": [],
            "old_live_gate_pass": None,
            "old_evaluator_pass": None,
        }

    evaluator_failure_reason = eval_record.get("failure_reason")
    success = eval_record.get("success")
    metrics = _dict_or_empty(eval_record.get("metrics"))
    curation = _dict_or_empty(metrics.get("curation"))
    data_quality = _dict_or_empty(metrics.get("data_quality"))
    native_action_saturation = data_quality.get("native_action_saturation")
    native_action_saturation_ratio = data_quality.get("native_action_saturation_ratio")
    raw_rejection_reasons = curation.get("rejection_reasons")
    rejection_reasons = (
        [str(reason) for reason in raw_rejection_reasons if isinstance(reason, str)]
        if isinstance(raw_rejection_reasons, list)
        else []
    )

    # For this diagnostic, a recorded native-action saturation failure is the
    # relevant gate reason even when the evaluator's task failure is generic
    # (for example TIMEOUT) or a different data-quality reason.
    failure_reason = evaluator_failure_reason
    if str(native_action_saturation).strip().lower() == "fail":
        failure_reason = "NATIVE_ACTION_SATURATION"
    elif failure_reason is None:
        for reason in rejection_reasons:
            if reason != "REPLAY_NOT_VERIFIED":
                failure_reason = reason
                break

    training_eligible = eval_record.get("training_eligible")
    if training_eligible is None:
        training_eligible = curation.get("training_eligible")
    if training_eligible is None:
        training_eligible = data_quality.get("training_eligible")

    live_curation_status = curation.get("status")
    if live_curation_status is None:
        live_curation_status = "passed" if failure_reason is None else "failed"

    native_status = str(native_action_saturation).strip().lower()
    if native_status == "fail":
        old_live_gate_pass = False
    elif evaluator_failure_reason is not None:
        old_live_gate_pass = False
    else:
        old_live_gate_pass = True

    return {
        "recorded_episode_status": eval_record.get("status"),
        "recorded_evaluator_success": success,
        "recorded_evaluator_failure_reason": evaluator_failure_reason,
        "recorded_failure_reason": failure_reason,
        "recorded_live_curation_status": live_curation_status,
        "recorded_training_eligible": _bool_or_none(training_eligible),
        "recorded_native_action_saturation": native_action_saturation,
        "recorded_native_action_saturation_ratio": native_action_saturation_ratio,
        "recorded_rejection_reasons": rejection_reasons,
        "old_live_gate_pass": old_live_gate_pass,
        "old_evaluator_pass": _bool_or_none(success),
    }


def _apply_trajectory_recorded_fallbacks(
    recorded: dict[str, Any], trajectory: dict[str, Any]
) -> dict[str, Any]:
    summary = _dict_or_empty(trajectory.get("summary"))
    recorded = dict(recorded)
    if recorded["recorded_episode_status"] is None:
        recorded["recorded_episode_status"] = summary.get("episode_status")

    live_curation = _dict_or_empty(summary.get("live_curation"))
    live_status = summary.get("live_curation_status") or live_curation.get("status")
    if recorded["recorded_live_curation_status"] is None and live_status is not None:
        recorded["recorded_live_curation_status"] = live_status

    live_ready = summary.get("live_curation_ready")
    if recorded["old_live_gate_pass"] is None and live_ready is not None:
        recorded["old_live_gate_pass"] = _bool_or_none(live_ready)

    if recorded["recorded_failure_reason"] is None:
        failure_reason = summary.get("episode_failure_reason")
        if isinstance(failure_reason, str) and failure_reason:
            recorded["recorded_failure_reason"] = failure_reason
            if recorded["old_live_gate_pass"] is None:
                recorded["old_live_gate_pass"] = False

    return recorded


def _phase_order_diagnostic(frames: list[dict[str, Any]]) -> dict[str, Any]:
    phase_order: list[str] = []
    for frame in frames:
        phase, _source = read_phase(frame)
        if not phase_order or phase_order[-1] != phase:
            phase_order.append(phase)

    relevant_order = [phase for phase in phase_order if phase in ORDERED_PHASES]
    max_seen_index = -1
    violations: list[str] = []
    for phase in relevant_order:
        index = ORDERED_PHASES.index(phase)
        if index < max_seen_index:
            violations.append(phase)
        max_seen_index = max(max_seen_index, index)

    return {
        "phase_order": phase_order,
        "phase_order_diagnostic": {
            "expected_order": list(ORDERED_PHASES),
            "observed_relevant_order": relevant_order,
            "order_violation": bool(violations),
            "violating_phases": violations,
        },
    }


def analyze_episode(
    traj_path: Path,
    eval_index: dict[str, dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    trajectory = read_json_object(traj_path)
    episode_id = str(trajectory.get("episode_id", traj_path.stem))
    trajectory_id = str(trajectory.get("id", traj_path.stem))
    raw_frames = trajectory.get("frames")
    frames = raw_frames if isinstance(raw_frames, list) else []

    eval_record = eval_index.get(episode_id)
    recorded = _apply_trajectory_recorded_fallbacks(
        _extract_recorded_state(eval_record),
        trajectory,
    )
    coverage = compute_phase_coverage(frames)
    saturation = compute_phase_conditional_saturation(
        frames, float(config["action_sat_value_threshold"])
    )
    quality = compute_command_quality(frames)
    gates = compute_gate_judgment(coverage["phase_counts"], config)
    cross_validation = compute_cross_validation(
        saturation["sat_ratio_aggregate"],
        recorded["recorded_failure_reason"],
        float(config["max_native_action_sat_ratio"]),
        recorded["recorded_native_action_saturation"],
    )
    order = _phase_order_diagnostic(frames)

    return {
        "episode_id": episode_id,
        "trajectory_id": trajectory_id,
        "trajectory_path": str(traj_path),
        "frame_count": len(frames),
        **recorded,
        **coverage,
        **saturation,
        **quality,
        **cross_validation,
        **gates,
        **order,
    }


def _build_summary(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [episode for episode in episodes if "error" not in episode]
    source_counts: Counter[str] = Counter()
    phase_counts: Counter[str] = Counter()
    for episode in valid:
        source_counts.update(episode.get("phase_source_distribution", {}))
        phase_counts.update(episode.get("phase_counts", {}))

    return {
        "total_episodes": len(episodes),
        "valid_episodes": len(valid),
        "error_episodes": len(episodes) - len(valid),
        "old_live_gate_pass_count": sum(
            1 for episode in valid if episode.get("old_live_gate_pass") is True
        ),
        "old_live_gate_fail_count": sum(
            1 for episode in valid if episode.get("old_live_gate_pass") is False
        ),
        "gate_A_pass_count": sum(1 for episode in valid if episode.get("gate_A_pass")),
        "gate_B_pass_count": sum(1 for episode in valid if episode.get("gate_B_pass")),
        "gate_C_pass_count": sum(1 for episode in valid if episode.get("gate_C_pass")),
        "approach_absent_count": sum(
            1
            for episode in valid
            if episode.get("phase_counts", {}).get("APPROACH", 0) == 0
        ),
        "gate_match_failure_count": sum(
            1 for episode in valid if episode.get("gate_match") is False
        ),
        "old_fail_gate_A_pass_count": sum(
            1
            for episode in valid
            if episode.get("old_live_gate_pass") is False and episode.get("gate_A_pass")
        ),
        "old_fail_gate_C_pass_count": sum(
            1
            for episode in valid
            if episode.get("old_live_gate_pass") is False and episode.get("gate_C_pass")
        ),
        "phase_counts_aggregate": dict(sorted(phase_counts.items())),
        "phase_source_distribution_aggregate": dict(sorted(source_counts.items())),
    }


def run_diagnostic(
    trajectories_dir: Path,
    evaluations_dir: Path,
    output_dir: Path,
    config: dict[str, Any],
    episode_ids: list[str] | None = None,
) -> dict[str, Any]:
    eval_index = load_eval_index(evaluations_dir)
    selected_episode_ids = set(episode_ids or [])
    trajectories = sorted(trajectories_dir.glob("traj_*.json"))

    episodes: list[dict[str, Any]] = []
    for path in trajectories:
        try:
            if selected_episode_ids:
                probe = read_json_object(path)
                if str(probe.get("episode_id", "")) not in selected_episode_ids:
                    continue
            episodes.append(analyze_episode(path, eval_index, config))
        except Exception as exc:  # diagnostic should keep processing other artifacts
            episodes.append({"trajectory_path": str(path), "error": str(exc)})

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "config": dict(config),
        "episodes": episodes,
        "summary": _build_summary(episodes),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "mvp2_curation_diagnostic_report.json"
    output_path.write_text(stable_json(report) + "\n", encoding="utf-8")
    return report


def _gate_label(value: Any) -> str:
    if value is True:
        return "PASS"
    if value is False:
        return "FAIL"
    return "N/A"


def print_table(report: dict[str, Any]) -> None:
    episodes = report.get("episodes", [])
    summary = report.get("summary", {})
    header = (
        f"{'EPISODE':<20} {'FRAMES':>6}  {'OLD':>4}  {'A':>4}  {'B':>4}  {'C':>4}"
        f"  {'SAT_INS':>7}  {'SAT_SEAT':>8}  {'JERK_P95':>8}  FAILURE_REASON"
    )
    print(header)
    print("-" * len(header))
    for episode in episodes:
        if "error" in episode:
            print(f"ERROR {episode.get('trajectory_path', '?')}: {episode['error']}")
            continue

        episode_id = str(episode.get("episode_id", "?"))[:20]
        jerk_p95 = episode.get("jerk_p95")
        jerk_label = f"{jerk_p95:.4f}" if isinstance(jerk_p95, float) else "N/A"
        failure_reason = episode.get("recorded_failure_reason") or "-"
        print(
            f"{episode_id:<20} {episode.get('frame_count', 0):>6}  "
            f"{_gate_label(episode.get('old_live_gate_pass')):>4}  "
            f"{_gate_label(episode.get('gate_A_pass')):>4}  "
            f"{_gate_label(episode.get('gate_B_pass')):>4}  "
            f"{_gate_label(episode.get('gate_C_pass')):>4}  "
            f"{episode.get('sat_ratio_INSERT', 0.0):>7.3f}  "
            f"{episode.get('sat_ratio_SEAT', 0.0):>8.3f}  "
            f"{jerk_label:>8}  {failure_reason}"
        )

    print()
    print(
        f"Total: {summary.get('total_episodes', 0)} | "
        f"A pass: {summary.get('gate_A_pass_count', 0)} | "
        f"B pass: {summary.get('gate_B_pass_count', 0)} | "
        f"C pass: {summary.get('gate_C_pass_count', 0)} | "
        f"APPROACH absent: {summary.get('approach_absent_count', 0)} | "
        f"gate_match failures: {summary.get('gate_match_failure_count', 0)}"
    )


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MVP-2 offline curation diagnostic.")
    parser.add_argument(
        "--trajectories-dir", type=Path, default=DEFAULT_TRAJECTORIES_DIR
    )
    parser.add_argument("--evaluations-dir", type=Path, default=DEFAULT_EVALUATIONS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--insert-min-frames", type=int, default=20)
    parser.add_argument("--seat-min-frames", type=int, default=8)
    parser.add_argument("--approach-min-frames", type=int, default=10)
    parser.add_argument(
        "--action-sat-value-threshold",
        type=float,
        default=0.999,
        help="Per-frame saturation check: abs(native_action) >= threshold.",
    )
    parser.add_argument(
        "--max-native-action-sat-ratio",
        type=float,
        default=0.05,
        help="Ratio gate for cross-validation against recorded curation decisions.",
    )
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--episode-ids", nargs="*")
    return parser


def main() -> int:
    parser = _build_arg_parser()
    args = parser.parse_args()
    config: dict[str, Any] = {
        "insert_min_frames": args.insert_min_frames,
        "seat_min_frames": args.seat_min_frames,
        "approach_min_frames": args.approach_min_frames,
        "action_sat_value_threshold": args.action_sat_value_threshold,
        "max_native_action_sat_ratio": args.max_native_action_sat_ratio,
    }

    report = run_diagnostic(
        trajectories_dir=args.trajectories_dir,
        evaluations_dir=args.evaluations_dir,
        output_dir=args.output_dir,
        config=config,
        episode_ids=args.episode_ids,
    )
    print_table(report)
    if args.pretty:
        print(f"\nReport: {args.output_dir / 'mvp2_curation_diagnostic_report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
