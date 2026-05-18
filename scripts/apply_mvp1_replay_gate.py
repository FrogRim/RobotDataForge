#!/usr/bin/env python3
"""Apply recorded-action replay results to MVP-1 readiness artifacts.

This script is intentionally offline. It consumes a replay report produced by
``scripts/check_peg_insert_viability.py`` and writes replay-verified manifest
artifacts. It does not run Isaac itself.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_READINESS_DIR = ROOT / "storage" / "mvp1_readiness"
DEFAULT_REPLAY_REPORT = ROOT / "storage" / "logs" / "peg_insert_viability_report.json"

CONTRACT_SCHEMA_VERSION = "rdf_action_replay_contract_v0.1.0"
GATE_SCHEMA_VERSION = "rdf_mvp1_replay_gate_v0.1.0"


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return data


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload) + "\n", encoding="utf-8")


def action_replay_contract(*, replay_mode: str, action_field: str) -> dict[str, Any]:
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "name": "mvp1c_recorded_action_replay_contract",
        "scope": "MVP-1C proof material",
        "task_family": "peg_in_hole_or_connector_insertion",
        "replay_mode": replay_mode,
        "action_field": action_field,
        "accepted_material_rule": "A trajectory may be promoted into the curated accepted dataset only if its recorded actions replay successfully under this contract.",
        "policy_eval_rule": "Curated-vs-uncurated policy A/B must train from replay-verified episode pools when this gate is present.",
        "live_promotion_rule": "HMD live trajectories may be used as collection/export smoke evidence without this gate, but may not be treated as accepted dataset material before replay verification.",
        "success_metric": "environment _get_curr_successes or equivalent task success evaluator",
        "initial_state_rule": "Recorded-action replay is valid only when the simulator resets to the recorded initial state. Offline fixtures may express this as summary.action_replay_contract.initial_state.seed; live HMD trajectories need equivalent reset-state provenance before accepted promotion.",
        "non_goals": [
            "This contract does not claim real robot replay.",
            "This contract does not replace held-out policy evaluation.",
            "This contract does not turn synthetic/offline fixtures into HMD live evidence.",
        ],
    }


def split_ids(ids: list[str]) -> dict[str, list[str]]:
    if len(ids) >= 4:
        return {"train": ids[:2], "validation": ids[2:3], "test": ids[3:4]}
    if len(ids) == 3:
        return {"train": ids[:1], "validation": ids[1:2], "test": ids[2:3]}
    if len(ids) == 2:
        return {"train": ids[:1], "validation": [], "test": ids[1:2]}
    return {"train": ids, "validation": [], "test": []}


def pool_blockers(*, baseline_ids: list[str], candidate_ids: list[str], split: dict[str, list[str]]) -> list[str]:
    blockers: list[str] = []
    heldout_ids = set(split.get("validation", []) + split.get("test", []))
    baseline_train_ids = [episode_id for episode_id in baseline_ids if episode_id not in heldout_ids]
    candidate_train_ids = [episode_id for episode_id in candidate_ids if episode_id not in heldout_ids]
    if not baseline_train_ids:
        blockers.append("baseline replay-verified train set is empty")
    if not candidate_train_ids:
        blockers.append("candidate replay-verified train set is empty")
    if not heldout_ids:
        blockers.append("replay-verified held-out validation/test set is empty")
    return blockers


def _index_files(directory: Path, *, key: str) -> dict[str, Path]:
    index: dict[str, Path] = {}
    if not directory.exists():
        return index
    for path in sorted(directory.glob("*.json")):
        try:
            payload = read_json(path)
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        value = payload.get(key)
        if isinstance(value, str):
            index[value] = path
    return index


def _copy_episode_artifacts(
    *,
    readiness_dir: Path,
    episode_ids: list[str],
    destination_dir: Path,
) -> list[str]:
    copied: list[str] = []
    traj_index = _index_files(readiness_dir / "raw" / "trajectories", key="episode_id")
    eval_index = _index_files(readiness_dir / "raw" / "evaluations", key="episode_id")
    traj_dest = destination_dir / "trajectories"
    eval_dest = destination_dir / "evaluations"
    traj_dest.mkdir(parents=True, exist_ok=True)
    eval_dest.mkdir(parents=True, exist_ok=True)
    for episode_id in episode_ids:
        traj_path = traj_index.get(episode_id)
        if traj_path is None:
            continue
        shutil.copy2(traj_path, traj_dest / traj_path.name)
        copied.append(episode_id)
        eval_path = eval_index.get(episode_id)
        if eval_path is not None:
            shutil.copy2(eval_path, eval_dest / eval_path.name)
    return copied


def _replay_results(report: dict[str, Any], *, replay_mode: str) -> dict[str, dict[str, Any]]:
    checks = report.get("checks") if isinstance(report.get("checks"), dict) else {}
    rows = checks.get("accepted_replays") if isinstance(checks.get("accepted_replays"), list) else []
    results: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        if row.get("mode") != replay_mode:
            continue
        episode_id = row.get("episode_id")
        if isinstance(episode_id, str):
            results[episode_id] = row
    return results


def apply_replay_gate(
    *,
    readiness_dir: Path,
    replay_report_path: Path,
    replay_mode: str = "native_direct",
    action_field: str = "retargeted_robot_action",
) -> dict[str, Any]:
    curation = read_json(readiness_dir / "curation_manifest.json")
    experiment = read_json(readiness_dir / "curated_vs_uncurated_experiment_manifest.json")
    replay_report = read_json(replay_report_path)
    replay_by_episode = _replay_results(replay_report, replay_mode=replay_mode)

    baseline_ids = [str(value) for value in experiment.get("baseline_a_uncurated_success_lifecycle_episode_ids", [])]
    candidate_ids = [str(value) for value in experiment.get("baseline_b_curated_accepted_episode_ids", [])]
    accepted_ids = [str(value) for value in curation.get("accepted_episode_ids", [])]

    replay_verified_ids = [episode_id for episode_id in baseline_ids if replay_by_episode.get(episode_id, {}).get("passed") is True]
    replay_failed_ids = [episode_id for episode_id in baseline_ids if replay_by_episode.get(episode_id, {}).get("passed") is not True]
    baseline_verified_ids = [episode_id for episode_id in baseline_ids if episode_id in replay_verified_ids]
    candidate_verified_ids = [episode_id for episode_id in candidate_ids if episode_id in replay_verified_ids]
    accepted_failed_ids = [episode_id for episode_id in accepted_ids if episode_id not in candidate_verified_ids]

    contract = action_replay_contract(replay_mode=replay_mode, action_field=action_field)
    contract_path = readiness_dir / "action_replay_contract.json"
    write_json(contract_path, contract)

    replay_split = split_ids(candidate_verified_ids)
    split_manifest = {
        "schema_version": "rdf_split_manifest_v0.1.0",
        "created_at": datetime.now(UTC).isoformat(),
        "strategy": "deterministic_replay_verified_split",
        "source": str(replay_report_path),
        "contract_path": str(contract_path),
        "splits": replay_split,
        "held_out_definition": "Replay-verified fixture split; replace with real held-out pose/clearance/connector variants for customer proof.",
    }
    split_path = readiness_dir / "split_manifest_replay_verified.json"
    write_json(split_path, split_manifest)

    copied_baseline = _copy_episode_artifacts(
        readiness_dir=readiness_dir,
        episode_ids=baseline_verified_ids,
        destination_dir=readiness_dir / "raw_replay_verified",
    )
    copied_candidate = _copy_episode_artifacts(
        readiness_dir=readiness_dir,
        episode_ids=candidate_verified_ids,
        destination_dir=readiness_dir / "curated_replay_verified",
    )
    blockers = pool_blockers(
        baseline_ids=baseline_verified_ids,
        candidate_ids=candidate_verified_ids,
        split=replay_split,
    )
    pool_ready = not blockers

    gate = {
        "schema_version": GATE_SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "replay_report_path": str(replay_report_path),
        "action_replay_contract_path": str(contract_path),
        "split_manifest_path": str(split_path),
        "replay_mode": replay_mode,
        "action_field": action_field,
        "baseline_source_episode_ids": baseline_ids,
        "candidate_source_episode_ids": candidate_ids,
        "replay_verified_episode_ids": replay_verified_ids,
        "replay_failed_episode_ids": replay_failed_ids,
        "baseline_a_replay_verified_success_lifecycle_episode_ids": baseline_verified_ids,
        "baseline_b_replay_verified_curated_accepted_episode_ids": candidate_verified_ids,
        "accepted_replay_failed_episode_ids": accepted_failed_ids,
        "accepted_replay_verified_count": len(candidate_verified_ids),
        "accepted_source_count": len(candidate_ids),
        "accepted_replay_viability": bool(candidate_ids) and len(candidate_verified_ids) == len(candidate_ids),
        "pool_ready_for_policy_ab": pool_ready,
        "pool_blockers": blockers,
        "copied_baseline_episode_ids": copied_baseline,
        "copied_candidate_episode_ids": copied_candidate,
        "limitations": [
            "This gate is necessary but not sufficient for full MVP-1C.",
            "A/B proof still requires measured held-out policy_success_rate uplift.",
            "Synthetic/offline replay verification is not HMD live accepted evidence.",
        ],
    }
    gate_path = readiness_dir / "replay_gate_manifest.json"
    write_json(gate_path, gate)

    experiment["action_replay_contract"] = contract
    experiment["replay_gate"] = {
        "manifest_path": str(gate_path),
        "contract_path": str(contract_path),
        "split_manifest_path": str(split_path),
        "replay_mode": replay_mode,
        "action_field": action_field,
        "pool_ready_for_policy_ab": gate["pool_ready_for_policy_ab"],
        "accepted_replay_viability": gate["accepted_replay_viability"],
    }
    experiment["baseline_a_replay_verified_success_lifecycle_episode_ids"] = baseline_verified_ids
    experiment["baseline_b_replay_verified_curated_accepted_episode_ids"] = candidate_verified_ids
    experiment.setdefault("required_future_evidence", []).append(
        "Use replay-verified episode pools for policy A/B when replay_gate_manifest.json is present."
    )
    write_json(readiness_dir / "curated_vs_uncurated_experiment_manifest.json", experiment)

    return gate


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--readiness-dir", type=Path, default=DEFAULT_READINESS_DIR)
    parser.add_argument("--replay-report", type=Path, default=DEFAULT_REPLAY_REPORT)
    parser.add_argument("--replay-mode", default="native_direct", choices=("native_direct", "metric_delta_to_native"))
    parser.add_argument("--action-field", default="retargeted_robot_action")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    gate = apply_replay_gate(
        readiness_dir=args.readiness_dir,
        replay_report_path=args.replay_report,
        replay_mode=args.replay_mode,
        action_field=args.action_field,
    )
    if args.pretty:
        print(stable_json(gate))
    else:
        status = "PASS" if gate["pool_ready_for_policy_ab"] else "FAIL"
        print(f"RDF MVP-1 replay gate: {status}")
        print(
            "replay_verified: "
            f"baseline={len(gate['baseline_a_replay_verified_success_lifecycle_episode_ids'])} "
            f"candidate={len(gate['baseline_b_replay_verified_curated_accepted_episode_ids'])}"
        )
    return 0 if gate["pool_ready_for_policy_ab"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
