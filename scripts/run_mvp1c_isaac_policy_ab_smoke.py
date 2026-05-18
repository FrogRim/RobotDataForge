#!/usr/bin/env python3
"""Run an MVP-1C Isaac headless policy A/B rollout smoke.

This script is the local bridge from the MVP-1C HDF5 bundle to actual Isaac
rollout logs. It trains two lightweight behavior-cloning policies from the
baseline/candidate HDF5 files, runs them in the Forge peg-insert task, and
writes rollout CSV files plus an MVP-1C policy-eval input JSON.

By default this is smoke evidence, not full MVP-1C proof. Use
``heldout_policy_eval`` only for the final headless Isaac held-out suite, and
reserve ``real_heldout_policy_eval`` for evidence that includes HMD live
accepted trajectories.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any

import h5py
import numpy as np


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from run_mvp1c_rollout_result_adapter import build_policy_eval_input, stable_json


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE_DIR = ROOT / "storage" / "mvp1c_headless_eval"
DEFAULT_OUTPUT_DIR = ROOT / "storage" / "mvp1c_isaac_policy_ab_smoke"
DEFAULT_BASELINE_HDF5 = (
    DEFAULT_BUNDLE_DIR / "baseline_uncurated" / "mvp1c_uncurated_success_lifecycle_train.hdf5"
)
DEFAULT_CANDIDATE_HDF5 = (
    DEFAULT_BUNDLE_DIR / "candidate_curated" / "mvp1c_curated_accepted_train.hdf5"
)
DEFAULT_TEMPLATE = DEFAULT_BUNDLE_DIR / "policy_eval_input_template.json"
SCHEMA_VERSION = "rdf_mvp1c_isaac_policy_ab_smoke_v0.1.0"
SMOKE_EVIDENCE_TIER = "isaac_headless_policy_eval_smoke"
PROOF_ELIGIBLE_EVIDENCE_TIERS = {"heldout_policy_eval", "real_heldout_policy_eval"}
OBSERVATION_FIELDS = (
    "end_effector_position",
    "object_position",
    "raw_xr_right_wrist_pose",
    "aligned_xr_right_wrist_pose",
)
ACTION_FIELD = "retargeted_robot_action"


@dataclass(frozen=True)
class TrainingData:
    episode_ids: list[str]
    observations: np.ndarray
    actions: np.ndarray
    issues: list[str]


@dataclass(frozen=True)
class LinearBcPolicy:
    name: str
    weights: np.ndarray
    obs_mean: np.ndarray
    obs_std: np.ndarray
    action_dim: int

    def predict(self, observations: np.ndarray) -> np.ndarray:
        x = np.asarray(observations, dtype=np.float64)
        if x.ndim == 1:
            x = x.reshape(1, -1)
        x_norm = (x - self.obs_mean) / self.obs_std
        x_aug = np.concatenate([x_norm, np.ones((x_norm.shape[0], 1), dtype=np.float64)], axis=1)
        actions = x_aug @ self.weights
        return np.clip(actions, -1.0, 1.0).astype(np.float32)


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload) + "\n", encoding="utf-8")


def _decode(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    if isinstance(value, np.bytes_):
        return bytes(value).decode("utf-8")
    return str(value)


def _matrix(h5: h5py.File, path: str) -> np.ndarray | None:
    dataset = h5.get(path)
    if not isinstance(dataset, h5py.Dataset):
        return None
    data = dataset[()]
    if not np.issubdtype(data.dtype, np.number):
        return None
    if data.ndim == 1:
        data = data.reshape(-1, 1)
    if data.ndim != 2:
        return None
    return np.asarray(data, dtype=np.float64)


def _episode_ids(h5: h5py.File) -> list[str]:
    dataset = h5.get("episodes/episode_ids")
    if not isinstance(dataset, h5py.Dataset):
        return []
    return [_decode(value) for value in dataset[()]]


def load_policy_training_data(
    hdf5_path: Path,
    *,
    observation_fields: tuple[str, ...] = OBSERVATION_FIELDS,
    action_field: str = ACTION_FIELD,
) -> TrainingData:
    issues: list[str] = []
    episode_ids: list[str] = []
    observations_all: list[np.ndarray] = []
    actions_all: list[np.ndarray] = []

    with h5py.File(hdf5_path, "r") as h5:
        episode_ids = _episode_ids(h5)
        if not episode_ids:
            issues.append("HDF5 has no episode ids")
        for episode_id in episode_ids:
            obs_parts: list[np.ndarray] = []
            frame_count: int | None = None
            for field_name in observation_fields:
                matrix = _matrix(h5, f"observations/{episode_id}/{field_name}")
                if matrix is None:
                    issues.append(f"{episode_id}: missing numeric observation {field_name}")
                    continue
                if frame_count is None:
                    frame_count = matrix.shape[0]
                elif matrix.shape[0] != frame_count:
                    issues.append(f"{episode_id}: observation frame count mismatch for {field_name}")
                obs_parts.append(matrix)

            actions = _matrix(h5, f"actions/{episode_id}/{action_field}")
            if actions is None:
                issues.append(f"{episode_id}: missing numeric action {action_field}")
                continue
            if frame_count is None:
                frame_count = actions.shape[0]
            elif actions.shape[0] != frame_count:
                issues.append(f"{episode_id}: action frame count mismatch")
            if frame_count == 0:
                issues.append(f"{episode_id}: zero frames")
                continue
            if not obs_parts:
                continue
            observations = np.concatenate(obs_parts, axis=1)
            if not np.isfinite(observations).all():
                issues.append(f"{episode_id}: observations contain non-finite values")
                continue
            if not np.isfinite(actions).all():
                issues.append(f"{episode_id}: actions contain non-finite values")
                continue
            observations_all.append(observations)
            actions_all.append(actions)

    if observations_all:
        observations_np = np.concatenate(observations_all, axis=0)
        actions_np = np.concatenate(actions_all, axis=0)
    else:
        observations_np = np.zeros((0, 0), dtype=np.float64)
        actions_np = np.zeros((0, 0), dtype=np.float64)
    if observations_np.shape[0] != actions_np.shape[0]:
        issues.append("observation/action sample count mismatch")
    return TrainingData(
        episode_ids=episode_ids,
        observations=observations_np,
        actions=actions_np,
        issues=issues,
    )


def fit_linear_bc_policy(
    name: str,
    training_data: TrainingData,
    *,
    ridge: float = 1.0e-4,
) -> tuple[LinearBcPolicy | None, list[str]]:
    issues = list(training_data.issues)
    x = training_data.observations
    y = training_data.actions
    if x.size == 0 or y.size == 0:
        issues.append(f"{name}: empty training arrays")
        return None, issues
    if x.shape[0] != y.shape[0]:
        issues.append(f"{name}: observation/action sample count mismatch")
        return None, issues

    obs_mean = x.mean(axis=0, keepdims=True)
    obs_std = x.std(axis=0, keepdims=True)
    obs_std = np.where(obs_std < 1.0e-6, 1.0, obs_std)
    x_norm = (x - obs_mean) / obs_std
    x_aug = np.concatenate([x_norm, np.ones((x_norm.shape[0], 1), dtype=np.float64)], axis=1)
    lhs = x_aug.T @ x_aug
    lhs += ridge * np.eye(lhs.shape[0], dtype=np.float64)
    rhs = x_aug.T @ y
    try:
        weights = np.linalg.solve(lhs, rhs)
    except np.linalg.LinAlgError:
        weights = np.linalg.pinv(lhs) @ rhs
    if not np.isfinite(weights).all():
        issues.append(f"{name}: fitted weights contain non-finite values")
        return None, issues
    return LinearBcPolicy(
        name=name,
        weights=weights,
        obs_mean=obs_mean,
        obs_std=obs_std,
        action_dim=y.shape[1],
    ), issues


def write_rollout_csv(path: Path, rollouts: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["rollout_id", "scenario_id", "seed", "success", "failure_reason", "steps"]
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for rollout in rollouts:
            writer.writerow({key: rollout.get(key, "") for key in fieldnames})


def _success_rate(rollouts: list[dict[str, Any]]) -> float | None:
    if not rollouts:
        return None
    return sum(1 for row in rollouts if row.get("success") is True) / len(rollouts)


def _set_policy_eval_evidence_tier(path: Path, evidence_tier: str) -> dict[str, Any]:
    payload = read_json(path)
    payload["evidence_tier"] = evidence_tier
    if evidence_tier == SMOKE_EVIDENCE_TIER:
        payload.setdefault("limitations", []).append(
            "This input was generated as Isaac headless smoke evidence and is not proof-eligible by default."
        )
    elif evidence_tier == "heldout_policy_eval":
        payload.setdefault("limitations", []).append(
            "This input is headless Isaac held-out policy evaluation evidence; use real_heldout_policy_eval only when HMD live accepted trajectories are included."
        )
    write_json(path, payload)
    return payload


def build_policy_eval_input_from_rollouts(
    *,
    template_path: Path,
    baseline_csv: Path,
    candidate_csv: Path,
    output_path: Path,
    evidence_tier: str,
    policy_class: str,
    trainer: str,
) -> dict[str, Any]:
    report = build_policy_eval_input(
        template_path=template_path,
        baseline_results_path=baseline_csv,
        candidate_results_path=candidate_csv,
        output_path=output_path,
        baseline_policy_id="rdf_linear_bc_uncurated_isaac_smoke",
        candidate_policy_id="rdf_linear_bc_curated_isaac_smoke",
        policy_class=policy_class,
        trainer=trainer,
    )
    policy_eval_input = _set_policy_eval_evidence_tier(output_path, evidence_tier)
    report["policy_eval_input"] = policy_eval_input
    report["evidence_tier"] = evidence_tier
    return report


def _extract_isaac_policy_features(env: Any) -> np.ndarray:
    unwrapped = getattr(env, "unwrapped", env)
    if hasattr(unwrapped, "_compute_intermediate_values"):
        unwrapped._compute_intermediate_values(dt=unwrapped.physics_dt)
    fingertip_pos = unwrapped.fingertip_midpoint_pos.detach().cpu().numpy()
    fingertip_quat = unwrapped.fingertip_midpoint_quat.detach().cpu().numpy()
    held_pos = unwrapped.held_pos.detach().cpu().numpy()
    pose = np.concatenate([fingertip_pos, fingertip_quat], axis=1)
    return np.concatenate([fingertip_pos, held_pos, pose, pose], axis=1)


def _curr_successes(env: Any) -> np.ndarray:
    unwrapped = getattr(env, "unwrapped", env)
    check_rot = getattr(unwrapped.cfg_task, "name", "") == "nut_thread"
    success_tensor = unwrapped._get_curr_successes(
        success_threshold=unwrapped.cfg_task.success_threshold,
        check_rot=check_rot,
    )
    return success_tensor.detach().cpu().numpy().astype(bool)


def run_isaac_policy_rollouts(
    *,
    baseline_policy: LinearBcPolicy,
    candidate_policy: LinearBcPolicy,
    task: str,
    device: str,
    rollouts_per_policy: int,
    max_steps: int,
    seed_start: int,
    action_scale: float,
    headless: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from isaaclab.app import AppLauncher

    app_launcher = AppLauncher(
        {
            "headless": headless,
            "device": device,
            "enable_cameras": False,
        }
    )
    simulation_app = app_launcher.app

    import gymnasium as gym
    import torch

    import isaaclab_tasks  # noqa: F401
    from isaaclab_tasks.utils import parse_env_cfg

    env = None
    try:
        env_cfg = parse_env_cfg(task, device=device, num_envs=1)
        env_cfg.seed = seed_start
        env = gym.make(task, cfg=env_cfg).unwrapped

        def run_one(policy: LinearBcPolicy, label: str, rollout_index: int) -> dict[str, Any]:
            seed = seed_start + rollout_index
            np.random.seed(seed)
            torch.manual_seed(seed)
            try:
                env.reset(seed=seed)
            except TypeError:
                env.reset()
            success_seen = False
            executed_steps = 0
            for step in range(max_steps):
                features = _extract_isaac_policy_features(env)
                action_np = np.clip(policy.predict(features) * action_scale, -1.0, 1.0)
                if action_np.shape[1] != getattr(env, "action_space", action_np).shape[0]:
                    action_np = action_np[:, : env.action_space.shape[0]]
                action = torch.as_tensor(action_np, dtype=torch.float32, device=env.device)
                env.step(action)
                executed_steps = step + 1
                successes = _curr_successes(env)
                if bool(successes[0]):
                    success_seen = True
                    break
                if not simulation_app.is_running():
                    break
            return {
                "rollout_id": f"{label}_{rollout_index:04d}",
                "scenario_id": f"isaac_seed_{seed}",
                "seed": seed,
                "success": success_seen,
                "failure_reason": "" if success_seen else "no_success_within_max_steps",
                "steps": executed_steps,
            }

        baseline_rollouts = [run_one(baseline_policy, "baseline", index) for index in range(rollouts_per_policy)]
        candidate_rollouts = [run_one(candidate_policy, "candidate", index) for index in range(rollouts_per_policy)]
        return baseline_rollouts, candidate_rollouts
    finally:
        if env is not None:
            env.close()
        # Do not call simulation_app.close() here. In Isaac Sim 5.1 this can
        # terminate the Python process before the caller writes result files.
        # The app is released when this short-lived process exits.


def run_policy_ab_smoke(
    *,
    baseline_hdf5: Path,
    candidate_hdf5: Path,
    template_path: Path,
    output_dir: Path,
    task: str,
    device: str,
    rollouts_per_policy: int,
    max_steps: int,
    seed_start: int,
    action_scale: float,
    headless: bool,
    evidence_tier: str,
    skip_isaac: bool,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    baseline_data = load_policy_training_data(baseline_hdf5)
    candidate_data = load_policy_training_data(candidate_hdf5)
    baseline_policy, baseline_issues = fit_linear_bc_policy("baseline", baseline_data)
    candidate_policy, candidate_issues = fit_linear_bc_policy("candidate", candidate_data)

    issues = [f"baseline: {issue}" for issue in baseline_issues]
    issues.extend(f"candidate: {issue}" for issue in candidate_issues)
    warnings = [
        "Default evidence is smoke-only; do not claim MVP-1C unless train/eval data is proof-grade held-out insertion data.",
    ]

    baseline_rollouts: list[dict[str, Any]] = []
    candidate_rollouts: list[dict[str, Any]] = []
    if baseline_policy is not None and candidate_policy is not None and not skip_isaac:
        try:
            baseline_rollouts, candidate_rollouts = run_isaac_policy_rollouts(
                baseline_policy=baseline_policy,
                candidate_policy=candidate_policy,
                task=task,
                device=device,
                rollouts_per_policy=rollouts_per_policy,
                max_steps=max_steps,
                seed_start=seed_start,
                action_scale=action_scale,
                headless=headless,
            )
        except Exception as exc:
            issues.append(f"isaac rollout failed: {exc}")
    elif skip_isaac:
        warnings.append("Isaac rollout skipped; policy fitting only.")

    baseline_csv = output_dir / "baseline_rollouts.csv"
    candidate_csv = output_dir / "candidate_rollouts.csv"
    write_rollout_csv(baseline_csv, baseline_rollouts)
    write_rollout_csv(candidate_csv, candidate_rollouts)

    policy_eval_input_path = output_dir / "policy_eval_input.json"
    adapter_report: dict[str, Any] | None = None
    if baseline_rollouts and candidate_rollouts:
        adapter_report = build_policy_eval_input_from_rollouts(
            template_path=template_path,
            baseline_csv=baseline_csv,
            candidate_csv=candidate_csv,
            output_path=policy_eval_input_path,
            evidence_tier=evidence_tier,
            policy_class="linear_bc_numpy_isaac_smoke",
            trainer="rdf_linear_bc_isaac_headless_smoke",
        )
    else:
        warnings.append("Rollout CSVs are empty; policy eval input was not generated.")

    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "passed": not issues and bool(baseline_rollouts) and bool(candidate_rollouts),
        "proof_eligible": evidence_tier in PROOF_ELIGIBLE_EVIDENCE_TIERS,
        "evidence_tier": evidence_tier,
        "task": task,
        "device": device,
        "rollouts_per_policy": rollouts_per_policy,
        "max_steps": max_steps,
        "seed_start": seed_start,
        "action_scale": action_scale,
        "baseline": {
            "hdf5_path": str(baseline_hdf5),
            "episode_ids": baseline_data.episode_ids,
            "sample_count": int(baseline_data.observations.shape[0]),
            "observation_dim": int(baseline_data.observations.shape[1]) if baseline_data.observations.ndim == 2 else 0,
            "action_dim": int(baseline_data.actions.shape[1]) if baseline_data.actions.ndim == 2 else 0,
            "rollout_csv": str(baseline_csv),
            "success_rate": _success_rate(baseline_rollouts),
        },
        "candidate": {
            "hdf5_path": str(candidate_hdf5),
            "episode_ids": candidate_data.episode_ids,
            "sample_count": int(candidate_data.observations.shape[0]),
            "observation_dim": int(candidate_data.observations.shape[1]) if candidate_data.observations.ndim == 2 else 0,
            "action_dim": int(candidate_data.actions.shape[1]) if candidate_data.actions.ndim == 2 else 0,
            "rollout_csv": str(candidate_csv),
            "success_rate": _success_rate(candidate_rollouts),
        },
        "policy_eval_input_path": str(policy_eval_input_path) if adapter_report is not None else None,
        "adapter_report": adapter_report,
        "issues": issues,
        "warnings": warnings,
    }
    write_json(output_dir / "isaac_policy_ab_smoke_report.json", report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-hdf5", type=Path, default=DEFAULT_BASELINE_HDF5)
    parser.add_argument("--candidate-hdf5", type=Path, default=DEFAULT_CANDIDATE_HDF5)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--task", default="Isaac-Forge-PegInsert-Direct-v0")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--rollouts-per-policy", type=int, default=10)
    parser.add_argument("--max-steps", type=int, default=150)
    parser.add_argument("--seed-start", type=int, default=7100)
    parser.add_argument(
        "--action-scale",
        type=float,
        default=1.0,
        help="Multiply fitted policy actions before clipping to [-1, 1]. Diagnostic for action-representation mismatch.",
    )
    parser.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--evidence-tier",
        default=SMOKE_EVIDENCE_TIER,
        choices=(SMOKE_EVIDENCE_TIER, "heldout_policy_eval", "real_heldout_policy_eval"),
    )
    parser.add_argument(
        "--skip-isaac",
        action="store_true",
        help="Only fit policies and validate HDF5 inputs. Does not generate rollout results.",
    )
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_policy_ab_smoke(
        baseline_hdf5=args.baseline_hdf5,
        candidate_hdf5=args.candidate_hdf5,
        template_path=args.template,
        output_dir=args.output_dir,
        task=args.task,
        device=args.device,
        rollouts_per_policy=args.rollouts_per_policy,
        max_steps=args.max_steps,
        seed_start=args.seed_start,
        action_scale=args.action_scale,
        headless=args.headless,
        evidence_tier=args.evidence_tier,
        skip_isaac=args.skip_isaac,
    )
    if args.pretty:
        print(stable_json(report))
    else:
        status = "PASS" if report["passed"] else "FAIL"
        print(f"RDF MVP-1C Isaac policy A/B smoke: {status}")
        print(f"baseline_success_rate={report['baseline']['success_rate']}")
        print(f"candidate_success_rate={report['candidate']['success_rate']}")
        print(f"evidence_tier={report['evidence_tier']}")
        print(f"report={args.output_dir / 'isaac_policy_ab_smoke_report.json'}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
