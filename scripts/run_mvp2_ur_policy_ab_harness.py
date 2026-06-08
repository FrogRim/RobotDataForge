#!/usr/bin/env python3
"""Build the MVP-2 UR policy A/B harness without claiming policy uplift."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
API_ROOT = ROOT / "apps" / "api"
for path in (SCRIPT_DIR, API_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.services.normalized_trajectory_contract import NormalizedTrajectoryContractValidator  # noqa: E402
from export_rdf_to_hdf5 import export_hdf5  # noqa: E402
from inspect_rdf_hdf5 import inspect_hdf5  # noqa: E402
from run_mvp1c_rollout_result_adapter import build_policy_eval_input  # noqa: E402
from run_mvp1plus_embodiment_proof import (  # noqa: E402
    DEFAULT_OUTPUT_DIR as DEFAULT_MVP1PLUS_OUTPUT_DIR,
    build_mvp1plus_embodiment_proof,
)


SCHEMA_VERSION = "rdf_mvp2_ur_policy_ab_harness_v0.1.0"
POLICY_EVAL_INPUT_SCHEMA_VERSION = "rdf_mvp2_policy_eval_input_v0.1.0"
HELDOUT_SUITE_SCHEMA_VERSION = "rdf_mvp2_heldout_suite_manifest_v0.1.0"
INGEST_CONTRACT_SCHEMA_VERSION = "rdf_mvp2_rollout_ingest_contract_v0.1.0"
DEFAULT_OUTPUT_DIR = ROOT / "storage" / "mvp2_policy_ab_harness"
UR_ADAPTER_ID = "universal_robots_ur_industrial_arm"
REQUIRED_SOURCE_FILE_KEYS = (
    "metadata_json",
    "accepted_command_state_jsonl",
    "rejected_command_state_jsonl",
)
REQUIRED_PROJECTED_ARTIFACT_KEYS = (
    "accepted_trajectory",
    "accepted_evaluation",
    "rejected_trajectory",
    "rejected_evaluation",
    "curation_manifest",
    "split_manifest",
    "projection_manifest",
)
MANAGED_OUTPUT_DIRS = (
    "baseline_uncurated",
    "candidate_curated",
    "rollout_ingest_contract_fixture",
)
MANAGED_OUTPUT_FILES = (
    "mvp2_policy_ab_harness_report.json",
    "mvp2_policy_eval_input_template.json",
    "mvp2_heldout_suite_manifest.json",
)


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload) + "\n", encoding="utf-8")


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _artifact_record_path(record: dict[str, Any]) -> Path:
    raw_path = record.get("path")
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError("lineage artifact record path missing")
    path = Path(raw_path)
    return path if path.is_absolute() else ROOT / path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _bundle_sha256(records: dict[str, dict[str, Any]]) -> str:
    digest_payload = {
        key: {
            "path": value["path"],
            "sha256": value["sha256"],
            "byte_size": value["byte_size"],
        }
        for key, value in sorted(records.items())
    }
    return hashlib.sha256(stable_json(digest_payload).encode("utf-8")).hexdigest()


def _validate_lineage_records(
    records: Any,
    *,
    required_keys: tuple[str, ...],
    record_type: str,
    projected_inputs: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    if not isinstance(records, dict):
        raise ValueError(f"{record_type} missing")
    record_keys = set(records)
    required_key_set = set(required_keys)
    if record_keys != required_key_set:
        missing = sorted(required_key_set - record_keys)
        extra = sorted(record_keys - required_key_set)
        raise ValueError(f"{record_type} key mismatch: missing={missing}, extra={extra}")
    verified: dict[str, dict[str, Any]] = {}
    for key in required_keys:
        record = records[key]
        if not isinstance(record, dict):
            raise ValueError(f"{record_type}.{key} must be an object")
        path = _artifact_record_path(record)
        if not path.exists():
            raise ValueError(f"{record_type}.{key} path does not exist: {path}")
        if projected_inputs is not None:
            projected_path_raw = projected_inputs.get(key)
            if not isinstance(projected_path_raw, str) or not projected_path_raw:
                raise ValueError(f"projected_inputs.{key} missing")
            if Path(projected_path_raw).resolve() != path.resolve():
                raise ValueError(f"{record_type}.{key} path does not match projected_inputs.{key}")
        expected_sha = record.get("sha256")
        expected_size = record.get("byte_size")
        actual_sha = _sha256_file(path)
        actual_size = path.stat().st_size
        if expected_sha != actual_sha:
            raise ValueError(f"{record_type}.{key} sha256 mismatch")
        if expected_size != actual_size:
            raise ValueError(f"{record_type}.{key} byte_size mismatch")
        verified[key] = {
            "path": record["path"],
            "sha256": actual_sha,
            "byte_size": actual_size,
        }
    return verified


def _is_safe_clean_target(path: Path) -> bool:
    resolved = path.resolve()
    repo_root = ROOT.resolve()
    storage_root = (repo_root / "storage").resolve()
    tmp_root = Path("/tmp").resolve()
    forbidden = {
        Path("/").resolve(),
        Path.home().resolve(),
        repo_root,
        repo_root.parent.resolve(),
        storage_root,
        tmp_root,
    }
    if resolved in forbidden:
        return False
    return _is_relative_to(resolved, storage_root) or _is_relative_to(resolved, tmp_root)


def _prepare_output_dir(output_dir: Path, *, clean: bool) -> None:
    if not _is_safe_clean_target(output_dir):
        raise ValueError(f"refusing unsafe MVP-2 harness output path: {output_dir}")
    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def _reset_managed_outputs(output_dir: Path) -> None:
    if not _is_safe_clean_target(output_dir):
        raise ValueError(f"refusing to reset unsafe MVP-2 harness output path: {output_dir}")
    for name in MANAGED_OUTPUT_DIRS:
        path = output_dir / name
        if path.exists():
            shutil.rmtree(path)
    for name in MANAGED_OUTPUT_FILES:
        path = output_dir / name
        if path.exists():
            path.unlink()


def _load_or_refresh_mvp1plus(
    *,
    mvp1plus_output_dir: Path,
    refresh_mvp1plus: bool,
) -> dict[str, Any]:
    proof_path = mvp1plus_output_dir / "mvp1plus_embodiment_proof.json"
    if refresh_mvp1plus or not proof_path.exists():
        return build_mvp1plus_embodiment_proof(mvp1plus_output_dir, clean=refresh_mvp1plus)
    return read_json(proof_path)


def _ur_adapter_proof(mvp1plus_proof: dict[str, Any]) -> dict[str, Any]:
    adapter_proofs = mvp1plus_proof.get("adapter_proofs")
    if not isinstance(adapter_proofs, list):
        raise ValueError("MVP-1+ proof adapter_proofs must be a list")
    for proof in adapter_proofs:
        if isinstance(proof, dict) and proof.get("adapter_id") == UR_ADAPTER_ID:
            return proof
    raise ValueError(f"MVP-1+ proof does not contain {UR_ADAPTER_ID}")


def _ur_contract_path(mvp1plus_output_dir: Path, ur_proof: dict[str, Any]) -> Path:
    explicit_path = ur_proof.get("normalized_contract_path")
    if isinstance(explicit_path, str) and explicit_path:
        return Path(explicit_path)
    return mvp1plus_output_dir / "normalized_contracts" / f"{UR_ADAPTER_ID}_normalized_trajectory_contract.json"


def _validate_ur_contract(contract_path: Path) -> None:
    contract = read_json(contract_path)
    issues = NormalizedTrajectoryContractValidator().validate_learning_eligibility(contract)
    if issues:
        raise ValueError(f"UR normalized contract failed learning eligibility: {issues}")


def _validate_ur_file_backed_lineage(ur_proof: dict[str, Any]) -> dict[str, Any]:
    lineage = ur_proof.get("lineage_evidence")
    if not isinstance(lineage, dict):
        raise ValueError("UR file-backed lineage gate failed: lineage_evidence missing")
    source_files = lineage.get("source_files")
    projected_artifacts = lineage.get("projected_artifacts")
    projected_inputs = ur_proof.get("projected_inputs")
    source_provenance = lineage.get("source_provenance")
    issues: list[str] = []
    if lineage.get("source_evidence_type") != "file_backed_recorded_log_fixture":
        issues.append("source_evidence_type must be file_backed_recorded_log_fixture")
    if not isinstance(projected_inputs, dict):
        issues.append("projected_inputs missing")
    if not isinstance(source_provenance, dict) or source_provenance.get("recorded_log_backed") is not True:
        issues.append("recorded_log_backed provenance missing")
    if issues:
        raise ValueError(f"UR file-backed lineage gate failed: {issues}")
    try:
        verified_source_files = _validate_lineage_records(
            source_files,
            required_keys=REQUIRED_SOURCE_FILE_KEYS,
            record_type="source_files",
        )
        verified_projected_artifacts = _validate_lineage_records(
            projected_artifacts,
            required_keys=REQUIRED_PROJECTED_ARTIFACT_KEYS,
            record_type="projected_artifacts",
            projected_inputs=projected_inputs,
        )
    except ValueError as exc:
        raise ValueError(f"UR file-backed lineage gate failed: {exc}") from exc
    source_bundle_sha256 = _bundle_sha256(verified_source_files)
    projected_bundle_sha256 = _bundle_sha256(verified_projected_artifacts)
    if lineage.get("source_bundle_sha256") != source_bundle_sha256:
        raise ValueError("UR file-backed lineage gate failed: source_bundle_sha256 mismatch")
    if lineage.get("projected_bundle_sha256") != projected_bundle_sha256:
        raise ValueError("UR file-backed lineage gate failed: projected_bundle_sha256 mismatch")
    return {
        "passed": True,
        "file_backed_recorded_log_fixture": True,
        "source_bundle_sha256": source_bundle_sha256,
        "projected_bundle_sha256": projected_bundle_sha256,
        "source_file_count": len(verified_source_files),
        "projected_artifact_count": len(verified_projected_artifacts),
        "source_files_verified": True,
        "projected_artifacts_verified": True,
    }


def _copy_json(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


def _copy_view(
    *,
    output_root: Path,
    view_name: str,
    trajectory_paths: list[Path],
    evaluation_paths: list[Path],
) -> dict[str, Any]:
    raw_dir = output_root / view_name / "raw"
    trajectories_dir = raw_dir / "trajectories"
    evaluations_dir = raw_dir / "evaluations"
    for path in trajectory_paths:
        _copy_json(path, trajectories_dir / path.name)
    for path in evaluation_paths:
        _copy_json(path, evaluations_dir / path.name)
    return {
        "view_name": view_name,
        "raw_dir": str(raw_dir),
        "trajectories_dir": str(trajectories_dir),
        "evaluations_dir": str(evaluations_dir),
        "trajectory_count": len(trajectory_paths),
        "evaluation_count": len(evaluation_paths),
    }


def _dataset_views(output_dir: Path, ur_proof: dict[str, Any]) -> dict[str, Any]:
    projected = ur_proof.get("projected_inputs")
    if not isinstance(projected, dict):
        raise ValueError("UR proof projected_inputs must be an object")
    accepted_trajectory = Path(str(projected["accepted_trajectory"]))
    accepted_evaluation = Path(str(projected["accepted_evaluation"]))
    rejected_trajectory = Path(str(projected["rejected_trajectory"]))
    rejected_evaluation = Path(str(projected["rejected_evaluation"]))
    baseline = _copy_view(
        output_root=output_dir,
        view_name="baseline_uncurated",
        trajectory_paths=[accepted_trajectory, rejected_trajectory],
        evaluation_paths=[accepted_evaluation, rejected_evaluation],
    )
    candidate = _copy_view(
        output_root=output_dir,
        view_name="candidate_curated",
        trajectory_paths=[accepted_trajectory],
        evaluation_paths=[accepted_evaluation],
    )
    return {"baseline": baseline, "candidate": candidate}


def _export_view(view: dict[str, Any], output_path: Path, *, include_statuses: set[str]) -> dict[str, Any]:
    result = export_hdf5(
        output_path=output_path,
        trajectories_dir=Path(str(view["trajectories_dir"])),
        evaluations_dir=Path(str(view["evaluations_dir"])),
        include_statuses=include_statuses,
    )
    inspection = inspect_hdf5(output_path)
    inspection_path = output_path.with_suffix(".inspection.json")
    write_json(inspection_path, inspection)
    return {
        "hdf5_path": str(output_path),
        "inspection_path": str(inspection_path),
        "episode_ids": result.exported_episode_ids,
        "skipped_by_status": result.skipped_by_status,
        "inspection_clean": inspection.get("issues", []) == [],
        "include_statuses": sorted(include_statuses),
    }


def _episode_ids_from_export(export: dict[str, Any]) -> list[str]:
    ids = export.get("episode_ids")
    return [str(item) for item in ids] if isinstance(ids, list) else []


def _write_heldout_suite(output_dir: Path, candidate_export: dict[str, Any]) -> dict[str, Any]:
    episode_ids = _episode_ids_from_export(candidate_export)
    scenario_ids = [f"schema_only_scenario_for_{episode_id}" for episode_id in episode_ids]
    manifest = {
        "schema_version": HELDOUT_SUITE_SCHEMA_VERSION,
        "id": "mvp2_ur_policy_ab_schema_only_heldout_suite",
        "held_out": True,
        "task_type": "connector_insertion",
        "scenario_ids": scenario_ids or ["schema_only_scenario_for_ur_harness"],
        "source": "schema_only_harness_template",
        "limitations": [
            "Held-out suite is a harness template, not a proof-grade policy evaluation suite.",
            "Real MVP-2 learning-proven proof requires external held-out rollout results.",
        ],
    }
    write_json(output_dir / "mvp2_heldout_suite_manifest.json", manifest)
    return manifest


def _write_policy_eval_template(
    *,
    output_dir: Path,
    heldout_suite: dict[str, Any],
    baseline_export: dict[str, Any],
    candidate_export: dict[str, Any],
) -> dict[str, Any]:
    template = {
        "schema_version": POLICY_EVAL_INPUT_SCHEMA_VERSION,
        "evidence_tier": "schema_only_rollout_ingest_contract",
        "primary_metric": "policy_success_rate",
        "task_type": heldout_suite["task_type"],
        "eval_suite": {
            "id": heldout_suite["id"],
            "held_out": True,
            "task_type": heldout_suite["task_type"],
            "scenario_ids": heldout_suite["scenario_ids"],
            "heldout_manifest_path": str(output_dir / "mvp2_heldout_suite_manifest.json"),
        },
        "baseline": {
            "name": "baseline_uncurated_recorded_log_harness_policy",
            "dataset_view": "baseline_uncurated_recorded_log_harness",
            "dataset_id": "mvp2_ur_baseline_uncurated_recorded_log_harness",
            "train_hdf5_path": baseline_export["hdf5_path"],
            "train_episode_ids": baseline_export["episode_ids"],
            "policy_class": "schema_only_external_policy",
            "trainer": "schema_only_external_trainer_contract",
            "rollout_results": [],
        },
        "candidate": {
            "name": "candidate_curated_accepted_policy",
            "dataset_view": "candidate_curated_accepted",
            "dataset_id": "mvp2_ur_candidate_curated_accepted",
            "train_hdf5_path": candidate_export["hdf5_path"],
            "train_episode_ids": candidate_export["episode_ids"],
            "policy_class": "schema_only_external_policy",
            "trainer": "schema_only_external_trainer_contract",
            "rollout_results": [],
        },
        "claim_boundary": {
            "learning_results_measured": False,
            "curated_vs_uncurated_uplift": None,
            "proof_eligible": False,
        },
    }
    write_json(output_dir / "mvp2_policy_eval_input_template.json", template)
    return template


def _write_schema_rollout_fixtures(output_dir: Path, heldout_suite: dict[str, Any]) -> dict[str, Path]:
    fixture_dir = output_dir / "rollout_ingest_contract_fixture"
    scenario_ids = heldout_suite["scenario_ids"] or ["schema_only_scenario"]
    baseline = {
        "fixture_kind": "schema_only_rollout_ingest_contract",
        "rollout_results": [
            {"rollout_id": "baseline_schema_0001", "scenario_id": scenario_ids[0], "success": True},
            {"rollout_id": "baseline_schema_0002", "scenario_id": scenario_ids[0], "success": False},
        ],
    }
    candidate = {
        "fixture_kind": "schema_only_rollout_ingest_contract",
        "rollout_results": [
            {"rollout_id": "candidate_schema_0001", "scenario_id": scenario_ids[0], "success": True},
            {"rollout_id": "candidate_schema_0002", "scenario_id": scenario_ids[0], "success": False},
        ],
    }
    baseline_path = fixture_dir / "baseline_rollouts.schema_fixture.json"
    candidate_path = fixture_dir / "candidate_rollouts.schema_fixture.json"
    write_json(baseline_path, baseline)
    write_json(candidate_path, candidate)
    return {"baseline": baseline_path, "candidate": candidate_path}


def _run_schema_ingest_contract(output_dir: Path, fixture_paths: dict[str, Path]) -> dict[str, Any]:
    report = build_policy_eval_input(
        template_path=output_dir / "mvp2_policy_eval_input_template.json",
        baseline_results_path=fixture_paths["baseline"],
        candidate_results_path=fixture_paths["candidate"],
        output_path=output_dir / "rollout_ingest_contract_fixture" / "mvp2_policy_eval_input.schema_fixture.json",
        baseline_policy_id="schema_only_baseline_policy",
        candidate_policy_id="schema_only_candidate_policy",
        policy_class="schema_only_external_policy",
        trainer="schema_only_external_trainer_contract",
    )
    metadata = report["adapter_metadata"]
    contract = {
        "schema_version": INGEST_CONTRACT_SCHEMA_VERSION,
        "passed": report["passed"],
        "fixture_kind": "schema_only_rollout_ingest_contract",
        "proof_eligible": False,
        "learning_results_measured": False,
        "curated_vs_uncurated_uplift": None,
        "baseline_rollout_count": metadata["baseline_rollout_count"],
        "candidate_rollout_count": metadata["candidate_rollout_count"],
        "policy_eval_input_path": report["output_path"],
        "baseline_success_rate": metadata["baseline_success_rate"],
        "candidate_success_rate": metadata["candidate_success_rate"],
        "schema_fixture_metrics": {
            "baseline_success_rate": metadata["baseline_success_rate"],
            "candidate_success_rate": metadata["candidate_success_rate"],
            "non_comparative": True,
            "must_not_be_used_for_policy_uplift": True,
        },
        "limitations": [
            "Schema fixture validates rollout ingest shape only.",
            "Schema fixture is not held-out policy evaluation evidence.",
            "Schema fixture success rates are intentionally non-comparative.",
            "Schema fixture must not update the learning manifest.",
        ],
    }
    write_json(output_dir / "rollout_ingest_contract_fixture" / "ingest_contract_report.json", contract)
    return contract


def _proof_source(ur_proof: dict[str, Any], *, contract_path: Path) -> dict[str, Any]:
    lineage = ur_proof.get("lineage_evidence") if isinstance(ur_proof.get("lineage_evidence"), dict) else {}
    contract_builder = ur_proof.get("contract_builder") if isinstance(ur_proof.get("contract_builder"), dict) else {}
    contract = ur_proof.get("contract") if isinstance(ur_proof.get("contract"), dict) else {}
    source_profile = contract.get("source_profile") if isinstance(contract.get("source_profile"), dict) else {}
    return {
        "adapter_id": UR_ADAPTER_ID,
        "adapter_version": contract_builder.get("builder_version"),
        "builder_id": contract_builder.get("builder_id"),
        "robot_embodiment": source_profile.get("robot"),
        "source_evidence_type": lineage.get("source_evidence_type"),
        "contract_path": str(contract_path),
        "validator_backend": "NormalizedTrajectoryContractValidator",
        "lineage_evidence": lineage,
    }


def build_mvp2_ur_policy_ab_harness(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    mvp1plus_output_dir: Path = DEFAULT_MVP1PLUS_OUTPUT_DIR,
    clean: bool = False,
    refresh_mvp1plus: bool = False,
) -> dict[str, Any]:
    _prepare_output_dir(output_dir, clean=clean)
    _reset_managed_outputs(output_dir)
    mvp1plus = _load_or_refresh_mvp1plus(
        mvp1plus_output_dir=mvp1plus_output_dir,
        refresh_mvp1plus=refresh_mvp1plus,
    )
    ur_proof = _ur_adapter_proof(mvp1plus)
    lineage_gate = _validate_ur_file_backed_lineage(ur_proof)
    contract_path = _ur_contract_path(mvp1plus_output_dir, ur_proof)
    _validate_ur_contract(contract_path)

    views = _dataset_views(output_dir, ur_proof)
    baseline_export = _export_view(
        views["baseline"],
        output_dir / "baseline_uncurated" / "baseline_uncurated_train.hdf5",
        include_statuses={"success", "failure"},
    )
    candidate_export = _export_view(
        views["candidate"],
        output_dir / "candidate_curated" / "candidate_curated_train.hdf5",
        include_statuses={"success"},
    )
    heldout_suite = _write_heldout_suite(output_dir, candidate_export)
    template = _write_policy_eval_template(
        output_dir=output_dir,
        heldout_suite=heldout_suite,
        baseline_export=baseline_export,
        candidate_export=candidate_export,
    )
    fixtures = _write_schema_rollout_fixtures(output_dir, heldout_suite)
    ingest_contract = _run_schema_ingest_contract(output_dir, fixtures)
    schema_fixture_metrics = ingest_contract.get("schema_fixture_metrics", {})
    gates = {
        "lineage_gate_passed": lineage_gate["passed"],
        "ur_contract_validation_passed": True,
        "baseline_export_nonempty": bool(baseline_export["episode_ids"]),
        "candidate_export_nonempty": bool(candidate_export["episode_ids"]),
        "baseline_hdf5_inspection_clean": baseline_export["inspection_clean"],
        "candidate_hdf5_inspection_clean": candidate_export["inspection_clean"],
        "rollout_ingest_contract_ready": ingest_contract["passed"],
        "schema_fixture_non_comparative": schema_fixture_metrics.get("non_comparative") is True,
        "schema_fixture_not_policy_uplift": schema_fixture_metrics.get("must_not_be_used_for_policy_uplift") is True,
    }
    harness_ready = all(gates.values())

    claim_boundary = {
        "learning_results_measured": False,
        "curated_vs_uncurated_uplift": None,
        "learning_proven": False,
        "proof_eligible": False,
        "policy_uplift_claimed": False,
        "real_robot_success_claimed": False,
        "physical_robot_readiness_claimed": False,
        "hmd_readiness_claimed": False,
    }
    report = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "passed": harness_ready,
        "harness_ready": harness_ready,
        "rollout_ingest_contract_ready": ingest_contract["passed"],
        "learning_results_measured": False,
        "curated_vs_uncurated_uplift": None,
        "learning_proven": False,
        "proof_eligible": False,
        "proof_source": _proof_source(ur_proof, contract_path=contract_path),
        "lineage_gate": lineage_gate,
        "gates": gates,
        "dataset_views": views,
        "exports": {"baseline": baseline_export, "candidate": candidate_export},
        "heldout_suite": heldout_suite,
        "policy_eval_input_template": template,
        "rollout_ingest_contract": ingest_contract,
        "claim_boundary": claim_boundary,
        "artifact_paths": {
            "report": str(output_dir / "mvp2_policy_ab_harness_report.json"),
            "policy_eval_input_template": str(output_dir / "mvp2_policy_eval_input_template.json"),
            "heldout_suite_manifest": str(output_dir / "mvp2_heldout_suite_manifest.json"),
            "baseline_hdf5": baseline_export["hdf5_path"],
            "candidate_hdf5": candidate_export["hdf5_path"],
            "ingest_contract_report": str(output_dir / "rollout_ingest_contract_fixture" / "ingest_contract_report.json"),
        },
        "limitations": [
            "This is a policy A/B harness readiness artifact, not policy uplift evidence.",
            "The rollout ingest fixture is schema-only.",
            "The UR source is file-backed recorded-log fixture evidence, not physical UR readiness.",
        ],
    }
    write_json(output_dir / "mvp2_policy_ab_harness_report.json", report)
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--mvp1plus-output-dir", type=Path, default=DEFAULT_MVP1PLUS_OUTPUT_DIR)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--refresh-mvp1plus", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_mvp2_ur_policy_ab_harness(
        output_dir=args.output_dir,
        mvp1plus_output_dir=args.mvp1plus_output_dir,
        clean=args.clean,
        refresh_mvp1plus=args.refresh_mvp1plus,
    )
    if args.pretty:
        print(stable_json(report))
    else:
        status = "PASS" if report["passed"] else "FAIL"
        print(f"RDF MVP-2 UR policy A/B harness: {status}")
        print(f"harness_ready={report['harness_ready']}")
        print(f"rollout_ingest_contract_ready={report['rollout_ingest_contract_ready']}")
        print(f"learning_results_measured={report['learning_results_measured']}")
        print(f"learning_proven={report['learning_proven']}")
        print(f"output={args.output_dir}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
