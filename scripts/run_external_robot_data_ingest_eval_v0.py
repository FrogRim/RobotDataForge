#!/usr/bin/env python3
"""Run External Robot Data Ingest / Evaluation v0.

This runner evaluates an externally attested JSONL command/state drop through
RDF's existing adapter projection path. It does not prove physical origin,
real robot readiness, live runtime support, policy uplift, or deployment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
SCRIPTS_ROOT = ROOT / "scripts"
for path in (API_ROOT, SCRIPTS_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from app.services.external_robot_data_ingest import (  # noqa: E402
    PACKAGE_STATUS_EXTERNAL_DATA_EVALUATED,
    PACKAGE_STATUS_EXTERNAL_INGEST_CONTRACT_READY,
    build_adapter_staging_source,
    validate_external_source_dir,
    verify_adapter_staging_source,
)
from app.services.robot_embodiment_adapters import RobotEmbodimentAdapterRegistry  # noqa: E402
from export_rdf_to_hdf5 import export_hdf5  # noqa: E402
from inspect_rdf_hdf5 import inspect_hdf5  # noqa: E402
from run_mvp1_trainer_smoke import run_trainer_smoke  # noqa: E402


DEFAULT_OUTPUT_DIR = ROOT / "storage" / "external_robot_data_ingest_eval_v0"
DEFAULT_PACKAGE_DIR = ROOT / "docs" / "proof" / "external_robot_data_ingest_eval_v0_proof_package"
REPORT_SCHEMA_VERSION = "rdf_external_robot_data_ingest_eval_report_v0.1.0"
PACKAGE_MANIFEST_SCHEMA_VERSION = "rdf_external_robot_data_ingest_eval_package_manifest_v0.1.0"
PACKAGE_CONFIG_SCHEMA_VERSION = "rdf_external_robot_data_ingest_eval_package_config_v0.1.0"
ARTIFACT_INDEX_SCHEMA_VERSION = "rdf_external_robot_data_ingest_eval_artifact_index_v0.1.0"
NON_CLAIMS_SCHEMA_VERSION = "rdf_external_robot_data_ingest_eval_non_claims_v0.1.0"
BUYER_REPORT_SCHEMA_VERSION = "rdf_external_robot_data_ingest_eval_buyer_report_v0.1.0"
NON_CLAIMS = {
    "real_robot_success": False,
    "physical_robot_readiness": False,
    "deployable_policy_readiness": False,
    "visual_policy_performance": False,
    "hmd_openxr_readiness": False,
    "live_ur_rtde_support": False,
    "live_franka_hardware_support": False,
    "live_ros2_dds_bridge_readiness": False,
    "universal_robot_support": False,
    "marketplace_readiness": False,
    "production_certification": False,
    "sim_to_real_proven": False,
    "general_robot_intelligence": False,
    "policy_uplift_or_learning_proven": False,
}


def stable_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload) + "\n", encoding="utf-8")


def artifact_path(path: Path | None) -> str | None:
    if path is None:
        return None
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def run_external_ingest_eval(
    *,
    external_source_dir: Path | str,
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    clean: bool = False,
    package_status: str = PACKAGE_STATUS_EXTERNAL_INGEST_CONTRACT_READY,
) -> dict[str, Any]:
    source_dir = Path(external_source_dir)
    output_path = Path(output_dir)
    if clean and output_path.exists():
        _assert_safe_clean_output_dir(output_path)
        shutil.rmtree(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    validation = validate_external_source_dir(source_dir, package_status=package_status)
    staging_dir = output_path / "data" / "staging"
    projection_dir = output_path / "projection"

    staging_report = None
    staging_verification = None
    projection = None
    contract_export = None
    selected_adapter_id = None
    if validation.ok:
        staging_report = build_adapter_staging_source(source_dir, staging_dir)
        selected_adapter_id = staging_report.selected_adapter_id
        if staging_report.ok:
            staging_verification = verify_adapter_staging_source(source_dir, staging_dir)
        if staging_verification is not None and staging_verification.ok:
            adapter = RobotEmbodimentAdapterRegistry.create(staging_verification.selected_adapter_id)
            projection = adapter.project_source_evidence(source_dir=staging_dir, output_dir=projection_dir)
            if projection.passed:
                contract_export = _run_contract_export_trainer_smoke(
                    adapter=adapter,
                    staging_dir=staging_dir,
                    projection_dir=projection_dir,
                    projected_inputs=projection.projected_inputs,
                    output_path=output_path,
                )

    gates = {
        "source_validation_passed": validation.ok,
        "staging_derivation_passed": staging_report is not None and staging_report.ok,
        "staging_derivation_verified": staging_verification is not None and staging_verification.ok,
        "adapter_projection_passed": projection is not None and projection.passed,
        "normalized_contract_emitted": contract_export is not None and contract_export["normalized_contract_emitted"],
        "hdf5_exported": contract_export is not None and contract_export["hdf5_exported"],
        "hdf5_inspection_clean": contract_export is not None and contract_export["hdf5_inspection_clean"],
        "trainer_smoke_passed": contract_export is not None and contract_export["trainer_smoke_passed"],
    }
    evaluated = (
        package_status == PACKAGE_STATUS_EXTERNAL_DATA_EVALUATED
        and gates["source_validation_passed"]
        and gates["staging_derivation_passed"]
        and gates["staging_derivation_verified"]
        and gates["adapter_projection_passed"]
        and gates["normalized_contract_emitted"]
        and gates["hdf5_exported"]
        and gates["hdf5_inspection_clean"]
        and gates["trainer_smoke_passed"]
    )
    status = PACKAGE_STATUS_EXTERNAL_DATA_EVALUATED if evaluated else PACKAGE_STATUS_EXTERNAL_INGEST_CONTRACT_READY
    artifact_paths = _artifact_paths(
        output_path=output_path,
        staging_dir=staging_dir if staging_report is not None else None,
        projection=projection.projected_inputs if projection is not None and projection.passed else {},
        contract_export=contract_export or {},
    )
    issues = [
        *validation.issues,
        *(staging_report.issues if staging_report is not None else []),
        *(staging_verification.issues if staging_verification is not None else []),
        *(projection.issues if projection is not None else []),
        *((contract_export or {}).get("issues") or []),
    ]
    report = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "package_status": package_status,
        "status": status,
        "stop_reason": None if evaluated else _stop_reason(validation_ok=validation.ok, requested_status=package_status),
        "external_source_dir": str(source_dir),
        "output_dir": str(output_path),
        "selected_adapter_id": selected_adapter_id,
        "counts": {
            "accepted_rows": validation.accepted_count,
            "rejected_rows": validation.rejected_count,
        },
        "gates": gates,
        "issues": _dedupe(issues),
        "source_file_hashes": validation.source_file_hashes,
        "artifact_paths": artifact_paths,
        "export_trainer_evidence": (contract_export or {}).get("export_trainer_evidence"),
        "non_claims": dict(NON_CLAIMS),
        "provenance_trust_boundary": (
            "RDF recomputes ingest/evaluation consistency from included rows and hashes. "
            "Offline verification does not cryptographically prove physical external origin."
        ),
    }
    write_json(output_path / "external_ingest_eval_report.json", report)
    return report


def build_external_ingest_proof_package(
    *,
    package_dir: Path | str = DEFAULT_PACKAGE_DIR,
    external_source_dir: Path | str,
    clean: bool = False,
    package_status: str = PACKAGE_STATUS_EXTERNAL_INGEST_CONTRACT_READY,
) -> dict[str, Any]:
    package_path = Path(package_dir)
    if clean and package_path.exists():
        _assert_safe_clean_package_dir(package_path)
        shutil.rmtree(package_path)
    data_dir = package_path / "data"
    source_dir = data_dir / "source"
    reports_dir = data_dir / "reports"
    source_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    work_dir = package_path / ".build_work"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    run_report = run_external_ingest_eval(
        external_source_dir=external_source_dir,
        output_dir=work_dir,
        clean=False,
        package_status=package_status,
    )
    external_source_included = run_report["status"] == PACKAGE_STATUS_EXTERNAL_DATA_EVALUATED
    if external_source_included:
        _copy_evaluated_artifacts_into_package(
            package_path=package_path,
            source_path=Path(external_source_dir),
            run_report=run_report,
        )
    else:
        _write_contract_ready_source_evidence(source_dir, run_report=run_report)

    config = _package_config(run_report=run_report, external_source_included=external_source_included)
    buyer_report = _buyer_report(run_report=run_report, external_source_included=external_source_included)
    non_claims = {
        "schema_version": NON_CLAIMS_SCHEMA_VERSION,
        "non_claims": dict(NON_CLAIMS),
        "all_false_required": True,
    }
    write_json(data_dir / "config.json", config)
    write_json(reports_dir / "run_report.json", run_report)
    write_json(reports_dir / "buyer_data_evaluation_report.json", buyer_report)
    write_json(data_dir / "non_claims_attestation.json", non_claims)

    artifact_index = {
        "schema_version": ARTIFACT_INDEX_SCHEMA_VERSION,
        "artifact_index": _build_artifact_index(package_path, include_artifact_index=False),
    }
    write_json(data_dir / "artifact_index.json", artifact_index)
    manifest = {
        "schema_version": PACKAGE_MANIFEST_SCHEMA_VERSION,
        "package_name": "external_robot_data_ingest_eval_v0_proof_package",
        "package_status": run_report["status"],
        "external_source_included": external_source_included,
        "verdict_source_of_truth": "data/",
        "verifier": "scripts/verify_external_robot_data_ingest_package.py",
        "artifact_index": _build_artifact_index(package_path, include_artifact_index=True),
        "non_claims": dict(NON_CLAIMS),
        "provenance_trust_boundary": run_report["provenance_trust_boundary"],
    }
    write_json(package_path / "package_manifest.json", manifest)
    _write_package_readme(package_path, manifest)
    if work_dir.exists():
        shutil.rmtree(work_dir)
    return manifest


def _artifact_paths(
    *,
    output_path: Path,
    staging_dir: Path | None,
    projection: dict[str, Any],
    contract_export: dict[str, Any],
) -> dict[str, str | None]:
    return {
        "report": artifact_path(output_path / "external_ingest_eval_report.json"),
        "staging_metadata": artifact_path(staging_dir / "metadata.json") if staging_dir is not None else None,
        "staging_derivation_report": (
            artifact_path(staging_dir / "staging_derivation_report.json") if staging_dir is not None else None
        ),
        "projection_manifest": projection.get("projection_manifest"),
        "accepted_trajectory": projection.get("accepted_trajectory"),
        "accepted_evaluation": projection.get("accepted_evaluation"),
        "rejected_trajectory": projection.get("rejected_trajectory"),
        "rejected_evaluation": projection.get("rejected_evaluation"),
        "curation_manifest": projection.get("curation_manifest"),
        "split_manifest": projection.get("split_manifest"),
        "normalized_contract": artifact_path(contract_export.get("normalized_contract")),
        "contract_proof": artifact_path(contract_export.get("contract_proof")),
        "hdf5_export": artifact_path(contract_export.get("hdf5_export")),
        "hdf5_inspection": artifact_path(contract_export.get("hdf5_inspection")),
        "trainer_smoke_report": artifact_path(contract_export.get("trainer_smoke_report")),
    }


def _package_config(*, run_report: dict[str, Any], external_source_included: bool) -> dict[str, Any]:
    return {
        "schema_version": PACKAGE_CONFIG_SCHEMA_VERSION,
        "status": run_report["status"],
        "package_status": run_report["status"],
        "allowed_future_status": PACKAGE_STATUS_EXTERNAL_DATA_EVALUATED,
        "external_source_included": external_source_included,
        "external_source_required_for_external_data_evaluated": True,
        "row_contract": {
            "accepted_rows_min": 4,
            "rejected_rows_exact": 1,
            "accepted_source_file": "data/source/accepted_command_state.jsonl",
            "rejected_source_file": "data/source/rejected_command_state.jsonl",
        },
        "provenance_trust_boundary": run_report["provenance_trust_boundary"],
        "spent_ranges_audit_only_no_reuse": [[40000, 40049], [42000, 42049]],
        "non_claims": dict(NON_CLAIMS),
    }


def _buyer_report(*, run_report: dict[str, Any], external_source_included: bool) -> dict[str, Any]:
    return {
        "schema_version": BUYER_REPORT_SCHEMA_VERSION,
        "claim": run_report["status"],
        "external_ingest_contract_ready": True,
        "external_data_evaluated": external_source_included,
        "what_is_proven": (
            "RDF has a verifier/package contract for external JSONL command-state ingest."
            if not external_source_included
            else "Included external/source-attested rows were evaluated through RDF ingest gates."
        ),
        "what_is_missing": (
            "No actual external/public recorded robot source rows are included in this package."
            if not external_source_included
            else "Offline verification cannot cryptographically prove physical origin."
        ),
        "provenance_trust_boundary": run_report["provenance_trust_boundary"],
        "counts": dict(run_report["counts"]),
        "gates": dict(run_report["gates"]),
        "non_claims": dict(NON_CLAIMS),
    }


def _write_contract_ready_source_evidence(source_dir: Path, *, run_report: dict[str, Any]) -> None:
    write_json(source_dir / "source_file_hashes.json", run_report["source_file_hashes"])
    write_json(
        source_dir / "source_availability_report.json",
        {
            "schema_version": "rdf_external_source_availability_report_v0.1.0",
            "external_source_included": False,
            "external_data_evaluated": False,
            "checked_source_dir": run_report["external_source_dir"],
            "stop_reason": run_report["stop_reason"],
            "required_for_external_data_evaluated": [
                "metadata.json",
                "accepted_command_state.jsonl",
                "rejected_command_state.jsonl",
                "PROVENANCE.md or public source binding",
            ],
        },
    )


def _copy_evaluated_artifacts_into_package(
    *,
    package_path: Path,
    source_path: Path,
    run_report: dict[str, Any],
) -> None:
    data_dir = package_path / "data"
    source_dir = data_dir / "source"
    staging_dir = data_dir / "staging"
    projections_dir = data_dir / "projections"
    contracts_dir = data_dir / "contracts"
    export_dir = data_dir / "export"
    for path in (source_dir, staging_dir, projections_dir, contracts_dir, export_dir):
        path.mkdir(parents=True, exist_ok=True)

    for name in ("metadata.json", "accepted_command_state.jsonl", "rejected_command_state.jsonl", "PROVENANCE.md", "LICENSE.txt"):
        src = source_path / name
        if src.exists() and src.is_file():
            shutil.copy2(src, source_dir / name)
    write_json(source_dir / "source_file_hashes.json", run_report["source_file_hashes"])
    write_json(
        source_dir / "provenance_attestation.json",
        {
            "schema_version": "rdf_external_provenance_attestation_v0.1.0",
            "source_dir": run_report["external_source_dir"],
            "trust_boundary": run_report["provenance_trust_boundary"],
        },
    )

    artifact_paths = run_report["artifact_paths"]
    copy_pairs = {
        "staging_metadata": staging_dir / "metadata.json",
        "staging_derivation_report": staging_dir / "staging_derivation_report.json",
        "projection_manifest": projections_dir / "projection_manifest.json",
        "accepted_trajectory": projections_dir / "accepted_trajectory.json",
        "accepted_evaluation": projections_dir / "accepted_evaluation.json",
        "rejected_trajectory": projections_dir / "rejected_trajectory.json",
        "rejected_evaluation": projections_dir / "rejected_evaluation.json",
        "curation_manifest": projections_dir / "curation_manifest.json",
        "split_manifest": projections_dir / "split_manifest.json",
        "normalized_contract": contracts_dir / "normalized_trajectory_contract.json",
        "contract_proof": contracts_dir / "validator_report.json",
        "hdf5_export": export_dir / "dataset.hdf5",
        "hdf5_inspection": export_dir / "hdf5_inspection_report.json",
        "trainer_smoke_report": export_dir / "trainer_smoke_report.json",
    }
    for key, dst in copy_pairs.items():
        src_value = artifact_paths.get(key)
        if src_value:
            shutil.copy2(_resolve_artifact_path(src_value), dst)


def _resolve_artifact_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return ROOT / path


def _build_artifact_index(package_path: Path, *, include_artifact_index: bool) -> list[dict[str, Any]]:
    data_dir = package_path / "data"
    entries: list[dict[str, Any]] = []
    for path in sorted(data_dir.rglob("*")):
        if not path.is_file():
            continue
        if not include_artifact_index and path.name == "artifact_index.json":
            continue
        entries.append(
            {
                "data_path": path.relative_to(package_path).as_posix(),
                "file_sha256": _sha256_file(path),
                "byte_size": path.stat().st_size,
                "hash_convention": "file_bytes",
            }
        )
    return entries


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_package_readme(package_path: Path, manifest: dict[str, Any]) -> None:
    package_path.mkdir(parents=True, exist_ok=True)
    package_path.joinpath("README.md").write_text(
        "\n".join(
            [
                "# External Robot Data Ingest / Evaluation v0 Proof Package",
                "",
                "This package is an RDF external recorded-log ingest contract package.",
                "",
                "## Status",
                "",
                f"`package_status={manifest['package_status']}`",
                f"`external_source_included={str(manifest['external_source_included']).lower()}`",
                "",
                "When `external_source_included=false`, this package does not claim that external robot data was evaluated.",
                "It only proves that the contract, package shape, non-claim boundary, and verifier surface are ready.",
                "Until semantic parity checks are implemented, the verifier intentionally rejects `external_data_evaluated` packages.",
                "",
                "## Provenance Trust Boundary",
                "",
                manifest["provenance_trust_boundary"],
                "",
                "## Non-Claims",
                "",
                "No real robot success, physical robot readiness, live UR/RTDE support, live Franka hardware support,",
                "live ROS2-DDS bridge readiness, HMD/OpenXR readiness, deployable policy readiness, visual policy",
                "performance, marketplace readiness, production certification, sim-to-real proof, general robot",
                "intelligence, policy uplift, or learning-proven value is claimed.",
                "",
                "## Verify",
                "",
                "```bash",
                "python3 scripts/verify_external_robot_data_ingest_package.py \\",
                "  docs/proof/external_robot_data_ingest_eval_v0_proof_package/package_manifest.json",
                "```",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _run_contract_export_trainer_smoke(
    *,
    adapter: Any,
    staging_dir: Path,
    projection_dir: Path,
    projected_inputs: dict[str, Any],
    output_path: Path,
) -> dict[str, Any]:
    hdf5_dir = output_path / "hdf5"
    contract_dir = output_path / "normalized_contracts"
    hdf5_dir.mkdir(parents=True, exist_ok=True)
    contract_dir.mkdir(parents=True, exist_ok=True)

    adapter_id = str(projected_inputs.get("metadata", {}).get("adapter_id") or adapter.profile.adapter_id)
    hdf5_path = hdf5_dir / f"{adapter_id}.external_ingest.hdf5"
    inspection_path = hdf5_dir / f"{adapter_id}.external_ingest.inspection.json"
    trainer_smoke_path = hdf5_dir / f"{adapter_id}.external_ingest.trainer_smoke.json"
    contract_path = contract_dir / f"{adapter_id}.external_ingest.normalized_trajectory_contract.json"
    proof_path = contract_dir / f"{adapter_id}.external_ingest.contract_proof.json"

    export_hdf5(
        output_path=hdf5_path,
        trajectories_dir=Path(projected_inputs["trajectories_dir"]),
        evaluations_dir=Path(projected_inputs["evaluations_dir"]),
        include_statuses={"success"},
    )
    inspection = inspect_hdf5(hdf5_path)
    write_json(inspection_path, inspection)
    trainer = run_trainer_smoke(
        hdf5_path=hdf5_path,
        split_manifest_path=Path(projected_inputs["split_manifest"]),
        output_path=trainer_smoke_path,
        experiment_manifest_path=None,
    )
    emission = adapter.emit_contract(
        source_dir=staging_dir,
        projected_dir=projection_dir,
        projected_inputs=projected_inputs,
        export_artifacts={
            "hdf5_export": hdf5_path,
            "trainer_smoke_report": trainer_smoke_path,
        },
    )
    export_trainer_evidence = {
        "hdf5_export_exists": hdf5_path.exists(),
        "hdf5_inspection_clean": inspection.get("issues") == [],
        "trainer_smoke_passed": trainer.get("passed") is True,
        "learning_results_measured": trainer.get("learning_results_measured") is True,
    }
    if emission.contract:
        evidence = emission.contract.get("robot_embodiment_adapter_evidence")
        if isinstance(evidence, dict):
            evidence["export_trainer_evidence"] = dict(export_trainer_evidence)
        write_json(contract_path, emission.contract)
    if emission.proof:
        emission.proof["export_trainer_evidence"] = dict(export_trainer_evidence)
        emission.proof["contract"] = emission.contract
        write_json(proof_path, emission.proof)

    issues = [
        *(inspection.get("issues") or []),
        *(trainer.get("issues") or []),
        *emission.issues,
    ]
    return {
        "normalized_contract": contract_path if emission.contract else None,
        "contract_proof": proof_path if emission.proof else None,
        "hdf5_export": hdf5_path,
        "hdf5_inspection": inspection_path,
        "trainer_smoke_report": trainer_smoke_path,
        "normalized_contract_emitted": bool(emission.contract) and emission.passed,
        "hdf5_exported": hdf5_path.exists(),
        "hdf5_inspection_clean": inspection.get("issues") == [],
        "trainer_smoke_passed": trainer.get("passed") is True,
        "export_trainer_evidence": export_trainer_evidence,
        "issues": _dedupe(issues),
    }


def _stop_reason(*, validation_ok: bool, requested_status: str) -> str | None:
    if validation_ok and requested_status == PACKAGE_STATUS_EXTERNAL_INGEST_CONTRACT_READY:
        return "source validated but package requested contract-ready status"
    if not validation_ok:
        return "no eligible external source rows available"
    return None


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _assert_safe_clean_output_dir(output_dir: Path) -> None:
    resolved = output_dir.resolve()
    repo_root = ROOT.resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    allowed_roots = {
        (repo_root / "storage").resolve(),
        temp_root,
    }
    forbidden = {
        Path("/").resolve(),
        Path.home().resolve(),
        repo_root,
        repo_root.parent,
    }
    if (
        resolved in forbidden
        or resolved in allowed_roots
        or not any(_is_relative_to(resolved, allowed) for allowed in allowed_roots)
    ):
        raise ValueError(f"refusing to clean unsafe output_dir: {resolved}")


def _assert_safe_clean_package_dir(package_dir: Path) -> None:
    resolved = package_dir.resolve()
    repo_root = ROOT.resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    allowed_roots = {
        (repo_root / "docs" / "proof").resolve(),
        temp_root,
    }
    forbidden = {
        Path("/").resolve(),
        Path.home().resolve(),
        repo_root,
        repo_root.parent,
        (repo_root / "docs").resolve(),
        (repo_root / "docs" / "proof").resolve(),
    }
    if (
        resolved in forbidden
        or resolved in allowed_roots
        or not any(_is_relative_to(resolved, allowed) for allowed in allowed_roots)
    ):
        raise ValueError(f"refusing to clean unsafe package_dir: {resolved}")


def _dedupe(issues: list[str]) -> list[str]:
    return list(dict.fromkeys(issues))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--external-source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE_DIR)
    parser.add_argument(
        "--package-status",
        choices=(PACKAGE_STATUS_EXTERNAL_INGEST_CONTRACT_READY, PACKAGE_STATUS_EXTERNAL_DATA_EVALUATED),
        default=PACKAGE_STATUS_EXTERNAL_INGEST_CONTRACT_READY,
    )
    parser.add_argument("--build-package", action="store_true")
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.build_package:
        report = build_external_ingest_proof_package(
            package_dir=args.package_dir,
            external_source_dir=args.external_source_dir,
            clean=args.clean,
            package_status=args.package_status,
        )
        if args.pretty:
            print(stable_json(report))
        else:
            print(json.dumps(report, sort_keys=True))
        return 0
    report = run_external_ingest_eval(
        external_source_dir=args.external_source_dir,
        output_dir=args.output_dir,
        clean=args.clean,
        package_status=args.package_status,
    )
    if args.pretty:
        print(stable_json(report))
    else:
        print(json.dumps(report, sort_keys=True))
    return 0 if report["issues"] == [] or report["status"] == PACKAGE_STATUS_EXTERNAL_INGEST_CONTRACT_READY else 1


if __name__ == "__main__":
    raise SystemExit(main())
