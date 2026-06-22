#!/usr/bin/env python3
"""Build MVP-3C Isaac Sim embodiment-source proof packages.

This runner can build controlled self-contained packages before live Isaac Sim
evidence exists. Controlled packages are verifier mechanics evidence only; they
do not close the original MVP-3C runtime-backed claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.robot_embodiment_adapters import RobotEmbodimentAdapterRegistry  # noqa: E402
from app.services.robot_embodiment_adapters import RobotEmbodimentAdapter  # noqa: E402


DEFAULT_OUTPUT_DIR = (
    ROOT / "docs" / "proof" / "mvp3c_isaac_sim_embodiment_source_proof_package"
)
DEFAULT_RUNTIME_CAPTURE_OUTPUT = (
    ROOT
    / "storage"
    / "proof_evidence"
    / "mvp3c_isaac_sim_embodiment_source"
    / "runtime_capture.json"
)
DEFAULT_ISAAC_PYTHON = Path("/home/kangrim/IsaacLab/_isaac_sim/python.sh")
CAPTURE_SCRIPT_NAME = "capture_mvp3c_isaac_sim_embodiment_source.py"
PACKAGE_NAME = "mvp3c_isaac_sim_embodiment_source_proof_package"
PACKAGE_CREATED_AT = "2026-06-22T01:00:00Z"
SOURCE_KIND = "isaac_sim_runtime_backed_command_state_log"
TASK_NAME = "mvp3c_isaac_sim_embodiment_source"
REQUIRED_EMBODIMENTS = (
    "franka_panda_isaac_sim",
    "universal_robots_ur10e_isaac_sim",
)
REQUIRED_ACTION_ROLES = (
    "teleop_intent",
    "executed_control",
    "learning_action",
    "retargeted_robot_action",
)
EXACT_SPENT_NO_REUSE = [[40000, 40049], [42000, 42049]]
CANONICAL_FORBIDDEN_CLAIMS = (
    "real_robot_success",
    "real_robot_success_claimed",
    "physical_robot_readiness",
    "physical_robot_readiness_claimed",
    "deployable_policy_readiness",
    "deployable_policy_readiness_claimed",
    "visual_policy_performance",
    "visual_policy_performance_claimed",
    "hmd_openxr_collection_readiness",
    "hmd_openxr_collection_readiness_claimed",
    "hmd_readiness",
    "hmd_readiness_claimed",
    "marketplace_readiness",
    "marketplace_readiness_claimed",
    "production_certification",
    "production_certification_claimed",
    "universal_robot_support",
    "universal_robot_support_claimed",
    "policy_uplift",
    "policy_uplift_claimed",
    "learning_proven_value",
    "learning_proven_value_claimed",
    "live_runtime_support",
    "live_runtime_support_claimed",
    "live_ur_runtime_support",
    "live_ur_runtime_support_claimed",
    "live_ur_hardware_support",
    "live_ur_hardware_support_claimed",
    "live_franka_hardware_support",
    "live_franka_hardware_support_claimed",
    "live_ros2_dds_runtime_support",
    "live_ros2_dds_runtime_support_claimed",
    "franka_hardware_support",
    "franka_hardware_support_claimed",
    "ur_hardware_support",
    "ur_hardware_support_claimed",
    "ros2_bridge_support",
    "ros2_bridge_support_claimed",
    "public_sample_import",
    "public_sample_import_claimed",
    "public_sample_evidence_claimed",
    "db_migration",
    "db_migration_claimed",
    "production_auth",
    "production_auth_claimed",
    "real_robot_readiness_claimed",
    "production_robot_support_claimed",
)
NO_CLAIMS = {key: False for key in CANONICAL_FORBIDDEN_CLAIMS}


def build_mvp3c_isaac_sim_embodiment_source(
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    *,
    clean: bool = False,
    evidence_kind: str = "synthetic_verifier_fixture",
    runtime_capture_report: Path | None = None,
    preflight: bool = False,
    runtime_capture_output: Path = DEFAULT_RUNTIME_CAPTURE_OUTPUT,
    isaac_python: Path = DEFAULT_ISAAC_PYTHON,
    closure_assertion: bool = False,
) -> dict[str, Any]:
    if preflight and runtime_capture_report is None:
        runtime_capture_report = _run_runtime_capture(
            output=runtime_capture_output,
            isaac_python=isaac_python,
        )
    capture_payload = (
        _load_runtime_capture_report(runtime_capture_report)
        if runtime_capture_report is not None
        else None
    )
    synthetic = capture_payload is None and evidence_kind == "synthetic_verifier_fixture"
    runtime_evidence_captured = capture_payload is not None
    if runtime_evidence_captured:
        evidence_kind = "isaac_sim_runtime_backed_source_log"
    status = _package_status(
        synthetic=synthetic,
        runtime_evidence_captured=runtime_evidence_captured,
        closure_assertion=closure_assertion,
    )
    data_dir = _prepare_output_dir(output_dir, clean=clean)
    profiles_by_id = {
        profile.adapter_id: profile
        for profile in RobotEmbodimentAdapterRegistry.list_mvp3c_source_ingress_profiles()
        if profile.adapter_id in REQUIRED_EMBODIMENTS
    }
    missing = [
        embodiment_id
        for embodiment_id in REQUIRED_EMBODIMENTS
        if embodiment_id not in profiles_by_id
    ]
    if missing:
        raise RuntimeError(f"missing MVP-3C source-ingress profiles: {', '.join(missing)}")

    profiles = [profiles_by_id[embodiment_id] for embodiment_id in REQUIRED_EMBODIMENTS]
    runtime_capture_source = None
    if runtime_capture_report is not None:
        runtime_capture_path = data_dir / "runtime_capture.json"
        shutil.copy2(runtime_capture_report, runtime_capture_path)
        runtime_capture_source = {
            "data_path": runtime_capture_path.relative_to(output_dir).as_posix(),
            "sha256": _sha256(runtime_capture_path),
        }

    _write_config(
        data_dir,
        status=status,
        evidence_kind=evidence_kind,
        synthetic=synthetic,
        runtime_evidence_captured=runtime_evidence_captured,
        closure_assertion=closure_assertion,
        runtime_capture_source=runtime_capture_source,
    )
    _write_json(
        data_dir / "non_claims_attestation.json",
        {"scope": TASK_NAME, "forbidden_claims": dict(NO_CLAIMS)},
    )

    outputs = []
    for profile in profiles:
        adapter = RobotEmbodimentAdapterRegistry.create_mvp3c_source_ingress_adapter(
            profile.adapter_id
        )
        outputs.append(
            _write_embodiment_package(
                data_dir=data_dir,
                adapter=adapter,
                status=status,
                synthetic=synthetic,
                capture_payload=capture_payload,
            )
        )

    summary = _write_summaries(
        data_dir,
        outputs=outputs,
        status=status,
        synthetic=synthetic,
    )
    _write_readme(output_dir, status=status, synthetic=synthetic)
    _write_indexes(output_dir)
    return {
        "status": summary["status"],
        "passed": True,
        "package_dir": str(output_dir),
        "package_manifest": str(output_dir / "package_manifest.json"),
        "embodiment_count": summary["embodiment_count"],
        "accepted_count": summary["accepted_count"],
        "rejected_count": summary["rejected_count"],
        "runtime_evidence_captured": runtime_evidence_captured,
        "closure_asserted": closure_assertion,
    }


def _package_status(
    *,
    synthetic: bool,
    runtime_evidence_captured: bool,
    closure_assertion: bool,
) -> str:
    if synthetic:
        if closure_assertion:
            raise ValueError("synthetic fixtures cannot assert MVP-3C closure")
        return "synthetic_verifier_fixture"
    if runtime_evidence_captured and not closure_assertion:
        return "runtime_evidence_captured"
    if runtime_evidence_captured and closure_assertion:
        return "isaac_sim_embodiment_source_closed"
    raise ValueError("non-synthetic packages require runtime capture evidence")


def _run_runtime_capture(*, output: Path, isaac_python: Path) -> Path:
    if not isaac_python.exists():
        raise FileNotFoundError(f"Isaac Sim Python not found: {isaac_python}")
    script = ROOT / "scripts" / CAPTURE_SCRIPT_NAME
    if not script.exists():
        raise FileNotFoundError(f"runtime capture script not found: {script}")
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            str(isaac_python),
            str(script),
            "--output",
            str(output),
            "--pretty",
        ],
        cwd=ROOT,
        check=True,
    )
    return output


def _load_runtime_capture_report(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    if payload.get("status") != "runtime_evidence_captured":
        raise ValueError(f"{path}: status must be runtime_evidence_captured")
    if payload.get("evidence_kind") != "isaac_sim_runtime_backed_source_log":
        raise ValueError(f"{path}: evidence_kind must be isaac_sim_runtime_backed_source_log")
    embodiments = payload.get("embodiments")
    if not isinstance(embodiments, dict):
        raise ValueError(f"{path}: embodiments must be an object")
    missing = [embodiment_id for embodiment_id in REQUIRED_EMBODIMENTS if embodiment_id not in embodiments]
    if missing:
        raise ValueError(f"{path}: missing runtime evidence for {', '.join(missing)}")
    for embodiment_id in REQUIRED_EMBODIMENTS:
        _validate_runtime_capture_entry(
            path=path,
            embodiment_id=embodiment_id,
            entry=embodiments[embodiment_id],
        )
    return payload


def _validate_runtime_capture_entry(
    *,
    path: Path,
    embodiment_id: str,
    entry: Any,
) -> None:
    if not isinstance(entry, dict):
        raise ValueError(f"{path}: {embodiment_id} runtime evidence must be an object")
    runtime_metadata = entry.get("runtime_metadata")
    if not isinstance(runtime_metadata, dict):
        raise ValueError(f"{path}: {embodiment_id} missing runtime_metadata")
    preflight = entry.get("preflight")
    if not isinstance(preflight, dict):
        raise ValueError(f"{path}: {embodiment_id} missing preflight")
    source_rows = entry.get("source_rows")
    if not isinstance(source_rows, dict):
        raise ValueError(f"{path}: {embodiment_id} missing source_rows")

    expected_capture_id = _capture_id(embodiment_id)
    required_metadata = {
        "embodiment_id": embodiment_id,
        "runtime_capture_id": expected_capture_id,
        "runtime": "isaac_sim",
        "simulator": "isaac_sim",
        "platform": "linux",
        "source_kind": SOURCE_KIND,
        "capture_origin": "isaac_sim_process",
    }
    for key, expected in required_metadata.items():
        if runtime_metadata.get(key) != expected:
            raise ValueError(f"{path}: {embodiment_id} runtime_metadata.{key} mismatch")
    for key in ("asset_path", "prim_path"):
        if not isinstance(runtime_metadata.get(key), str) or not runtime_metadata[key]:
            raise ValueError(f"{path}: {embodiment_id} runtime_metadata.{key} missing")

    required_preflight = {
        "embodiment_id": embodiment_id,
        "runtime_capture_id": expected_capture_id,
        "asset_loaded": True,
        "articulation_detected": True,
        "joint_state_readable": True,
        "action_command_writable": True,
        "runtime_metadata_recorded": True,
    }
    for key, expected in required_preflight.items():
        if preflight.get(key) != expected:
            raise ValueError(f"{path}: {embodiment_id} preflight.{key} mismatch")
    if preflight.get("source_log_rows_emitted") != 2:
        raise ValueError(f"{path}: {embodiment_id} preflight.source_log_rows_emitted mismatch")
    for split, accepted in (("accepted", True), ("rejected", False)):
        rows = source_rows.get(split)
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"{path}: {embodiment_id} missing {split} source rows")
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f"{path}: {embodiment_id} {split} source row must be an object")
            if row.get("embodiment_id") != embodiment_id:
                raise ValueError(f"{path}: {embodiment_id} {split} row embodiment mismatch")
            if row.get("runtime_capture_id") != expected_capture_id:
                raise ValueError(f"{path}: {embodiment_id} {split} row capture mismatch")
            if row.get("runtime") != "isaac_sim" or row.get("simulator") != "isaac_sim":
                raise ValueError(f"{path}: {embodiment_id} {split} row runtime mismatch")
            if row.get("source_kind") != SOURCE_KIND:
                raise ValueError(f"{path}: {embodiment_id} {split} row source_kind mismatch")
            if row.get("accepted") is not accepted:
                raise ValueError(f"{path}: {embodiment_id} {split} row accepted mismatch")


def _prepare_output_dir(output_dir: Path, *, clean: bool) -> Path:
    if clean and output_dir.exists():
        _assert_safe_clean_output_dir(output_dir)
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data_dir = output_dir / "data"
    for child in (
        "adapter_results",
        "contracts",
        "preflight",
        "projections",
        "runtime_metadata",
        "source_logs",
    ):
        (data_dir / child).mkdir(parents=True, exist_ok=True)
    return data_dir


def _assert_safe_clean_output_dir(output_dir: Path) -> None:
    resolved = output_dir.resolve()
    default_output = DEFAULT_OUTPUT_DIR.resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if resolved == default_output:
        return
    if _is_relative_to(resolved, temp_root) and resolved != temp_root:
        return
    raise ValueError(f"refusing to clean unsafe output_dir: {resolved}")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _write_config(
    data_dir: Path,
    *,
    status: str,
    evidence_kind: str,
    synthetic: bool,
    runtime_evidence_captured: bool,
    closure_assertion: bool,
    runtime_capture_source: dict[str, Any] | None,
) -> None:
    _write_json(
        data_dir / "config.json",
        {
            "schema_version": "rdf_mvp3c_isaac_sim_embodiment_source_config_v0.1.0",
            "proof_slice": TASK_NAME,
            "claim_tier": "isaac_sim_embodiment_source",
            "changed_variable": "isaac_sim_embodiment_source_pair",
            "required_embodiments": list(REQUIRED_EMBODIMENTS),
            "evidence_kind": evidence_kind,
            "requested_status": status,
            "synthetic_verifier_fixture": synthetic,
            "runtime_evidence_captured": runtime_evidence_captured,
            "closure_assertion": closure_assertion,
            "runtime_capture_source": runtime_capture_source,
            "source_evidence_level": "synthetic_verifier_fixture"
            if synthetic
            else SOURCE_KIND,
            "runtime_expectations": {
                "runtime": "isaac_sim",
                "simulator": "isaac_sim",
                "platform": "linux",
            },
            "spent_no_reuse": EXACT_SPENT_NO_REUSE,
            "opened_ranges": {
                "calibration": [],
                "heldout": [],
                "tuning": [],
                "closure": [],
            },
            "learning_proven_addendum": "absent",
            "non_claims": dict(NO_CLAIMS),
        },
    )


def _write_embodiment_package(
    *,
    data_dir: Path,
    adapter: RobotEmbodimentAdapter,
    status: str,
    synthetic: bool,
    capture_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    profile = adapter.profile
    embodiment_id = profile.adapter_id
    capture_id = _capture_id(embodiment_id)
    source_dir = data_dir / "source_logs" / embodiment_id
    projection_dir = data_dir / "projections" / embodiment_id
    runtime_metadata_path = (
        data_dir / "runtime_metadata" / f"{embodiment_id}_runtime_metadata.json"
    )

    capture_entry = (
        capture_payload.get("embodiments", {}).get(embodiment_id)
        if capture_payload is not None
        else None
    )
    accepted_rows = (
        _captured_source_rows(capture_entry, "accepted")
        if capture_entry is not None
        else _source_rows(profile, accepted=True)
    )
    rejected_rows = (
        _captured_source_rows(capture_entry, "rejected")
        if capture_entry is not None
        else _source_rows(profile, accepted=False)
    )
    accepted_path = source_dir / "accepted_command_state.jsonl"
    rejected_path = source_dir / "rejected_command_state.jsonl"

    _write_json(
        runtime_metadata_path,
        _captured_doc(capture_entry, "runtime_metadata")
        if capture_entry is not None
        else _runtime_metadata(profile, synthetic=synthetic),
    )
    _write_json(
        data_dir / "preflight" / f"{embodiment_id}_preflight.json",
        _captured_doc(capture_entry, "preflight")
        if capture_entry is not None
        else _preflight(profile),
    )
    _write_json(source_dir / "metadata.json", _source_metadata(profile))
    _write_jsonl(accepted_path, accepted_rows)
    _write_jsonl(rejected_path, rejected_rows)

    projection = adapter.project_mvp3c_source_evidence(
        source_dir=source_dir,
        output_dir=projection_dir,
        runtime_metadata_path=runtime_metadata_path,
        contract_path=data_dir / "contracts" / f"{embodiment_id}_normalized_trajectory_contract.json",
    )
    if not projection.passed:
        raise RuntimeError(f"{embodiment_id} MVP-3C projection failed: {projection.issues}")
    _write_json(
        data_dir / "adapter_results" / f"{embodiment_id}_adapter_result.json",
        {
            "embodiment_id": embodiment_id,
            "status": "mvp3c_source_ingress_projection_passed",
            "package_status": status,
            "registry_lookup": profile.to_artifact(),
            "adapter_call_evidence": {
                "registry_create_called": True,
                "project_mvp3c_source_evidence_called": True,
                "projection_method": projection.projected_inputs["projection_method"],
            },
            "accepted_count": projection.projected_inputs["accepted_count"],
            "rejected_count": projection.projected_inputs["rejected_count"],
            "required_action_roles_present": projection.projected_inputs[
                "required_action_roles_present"
            ],
            "learning_results_measured": False,
            "policy_uplift": False,
            "learning_proven_value": False,
        },
    )
    return {
        "embodiment_id": embodiment_id,
        "accepted_count": projection.projected_inputs["accepted_count"],
        "rejected_count": projection.projected_inputs["rejected_count"],
        "runtime_capture_id": capture_id,
    }


def _runtime_metadata(profile, *, synthetic: bool) -> dict[str, Any]:
    return {
        "schema_version": "rdf_mvp3c_runtime_metadata_v0.1.0",
        "embodiment_id": profile.adapter_id,
        "runtime_capture_id": _capture_id(profile.adapter_id),
        "runtime": profile.source_runtime,
        "simulator": profile.source_simulator,
        "platform": "linux",
        "source_kind": profile.source_kind,
        "capture_origin": "synthetic_verifier_fixture"
        if synthetic
        else "isaac_sim_process",
        "real_robot_success": False,
        "physical_robot_readiness": False,
        "live_runtime_support": False,
    }


def _captured_doc(capture_entry: Any, key: str) -> dict[str, Any] | None:
    if not isinstance(capture_entry, dict):
        return None
    payload = capture_entry.get(key)
    if not isinstance(payload, dict):
        return None
    return payload


def _captured_source_rows(capture_entry: Any, split: str) -> list[dict[str, Any]] | None:
    if not isinstance(capture_entry, dict):
        return None
    rows_by_split = capture_entry.get("source_rows")
    if not isinstance(rows_by_split, dict):
        return None
    rows = rows_by_split.get(split)
    if not isinstance(rows, list):
        return None
    return [dict(row) for row in rows if isinstance(row, dict)]


def _preflight(profile) -> dict[str, Any]:
    return {
        "schema_version": "rdf_mvp3c_preflight_v0.1.0",
        "embodiment_id": profile.adapter_id,
        "runtime_capture_id": _capture_id(profile.adapter_id),
        "asset_loaded": True,
        "articulation_detected": True,
        "joint_state_readable": True,
        "action_command_writable": True,
        "source_log_rows_emitted": 2,
        "runtime_metadata_recorded": True,
    }


def _source_metadata(profile) -> dict[str, Any]:
    return {
        "schema_version": "rdf_mvp3c_source_metadata_v0.1.0",
        "adapter_id": profile.adapter_id,
        "embodiment_id": profile.adapter_id,
        "runtime_capture_id": _capture_id(profile.adapter_id),
        "runtime": profile.source_runtime,
        "simulator": profile.source_simulator,
        "source_kind": profile.source_kind,
        "source_ingress_role": profile.source_ingress_role,
        "capabilities": list(profile.capabilities),
        "claim_boundary": dict(profile.claim_boundary),
        "limitations": list(profile.limitations),
        "real_robot_success": False,
        "live_runtime_support": False,
        "hmd_openxr_collection_readiness": False,
    }


def _source_rows(profile, *, accepted: bool) -> list[dict[str, Any]]:
    role_values = {role: [0.1, 0.2, 0.3, 0.4] for role in REQUIRED_ACTION_ROLES}
    return [
        {
            "embodiment_id": profile.adapter_id,
            "runtime_capture_id": _capture_id(profile.adapter_id),
            "row_id": f"{profile.adapter_id}_{'accepted' if accepted else 'rejected'}_0",
            "timestamp_ns": 1_000_000 if accepted else 2_000_000,
            "runtime": profile.source_runtime,
            "simulator": profile.source_simulator,
            "source_kind": profile.source_kind,
            "accepted": accepted,
            "command_state": {
                "joint_positions": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5],
                "joint_velocities": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "eef_pose": [0.0, 0.0, 0.1, 0.0, 0.0, 0.0, 1.0],
                "actions_by_role": role_values,
            },
        }
    ]


def _contract(profile) -> dict[str, Any]:
    frame_count = 2
    return {
        "schema_version": "mvp3c.normalized_trajectory_contract.v1",
        "embodiment_id": profile.adapter_id,
        "source": {
            "input_device": "isaac_sim_command_state_log",
            "runtime": profile.source_runtime,
            "simulator": profile.source_simulator,
            "robot": profile.adapter_id,
            "task_name": TASK_NAME,
        },
        "required_action_roles": list(REQUIRED_ACTION_ROLES),
        "frame_action_role_coverage": {
            role: {"present": True, "frames": frame_count}
            for role in REQUIRED_ACTION_ROLES
        },
        "learning_eligibility_gates": {
            "replay_action_contract": True,
            "trainer_export_smoke": "contract_smoke_only",
            "learning_results_measured": False,
            "policy_uplift": False,
            "learning_proven_value": False,
        },
    }


def _write_summaries(
    data_dir: Path,
    *,
    outputs: list[dict[str, Any]],
    status: str,
    synthetic: bool,
) -> dict[str, Any]:
    embodiment_counts = {
        output["embodiment_id"]: {
            "accepted_count": output["accepted_count"],
            "rejected_count": output["rejected_count"],
            "runtime_capture_id": output["runtime_capture_id"],
        }
        for output in outputs
    }
    summary = {
        "status": status,
        "required_embodiment_count": len(REQUIRED_EMBODIMENTS),
        "embodiment_count": len(outputs),
        "accepted_count": sum(output["accepted_count"] for output in outputs),
        "rejected_count": sum(output["rejected_count"] for output in outputs),
        "embodiments": embodiment_counts,
        "cached_summary_only": True,
        "learning_results_measured": False,
        "policy_uplift": False,
        "learning_proven_value": False,
    }
    _write_json(data_dir / "embodiment_source_summary.json", summary)
    _write_json(
        data_dir / "isaac_sim_runtime_summary.json",
        {
            "status": status,
            "runtime": "isaac_sim",
            "simulator": "isaac_sim",
            "platform": "linux",
            "embodiment_count": len(outputs),
            "synthetic_verifier_fixture": synthetic,
        },
    )
    return summary


def _write_readme(output_dir: Path, *, status: str, synthetic: bool) -> None:
    status_note = (
        "This controlled package is a synthetic verifier fixture and cannot close the "
        "original MVP-3C runtime-backed claim."
        if synthetic
        else "This package is the runtime-backed MVP-3C source/embodiment infrastructure closure package."
    )
    body = [
        "# MVP-3C Isaac Sim Embodiment Source Proof Package",
        "",
        "## Status",
        "",
        f"- package_status: `{status}`",
        f"- runtime_evidence_captured: `{not synthetic}`",
        f"- closure_assertion: `{not synthetic}`",
        f"- evidence_kind: `{'synthetic_verifier_fixture' if synthetic else SOURCE_KIND}`",
        f"- note: {status_note}",
        "",
        "## Claim",
        "",
        "The package verifies that Franka Panda and UR10e Isaac Sim command/state source logs can be recorded, projected through RDF adapter infrastructure, packaged as self-contained evidence, and independently audited from tracked package data.",
        "",
        "The verifier recomputes artifact hashes, required embodiment exactness, source-log completeness, runtime metadata binding, per-row `runtime_capture_id` binding, projection hash binding, accepted/rejected counts, normalized contract action roles, spent range discipline, opened-range emptiness, and forbidden claim boundaries.",
        "",
        "## Verify",
        "",
        "```bash",
        "python3 scripts/verify_mvp3c_isaac_sim_embodiment_source_package.py docs/proof/mvp3c_isaac_sim_embodiment_source_proof_package/package_manifest.json",
        "```",
        "",
        "Expected result:",
        "",
        "```text",
        "VERDICT: VERIFIED",
        f"status={status}",
        "```",
        "",
        "The verifier is stdlib-only and does not import the package builder, the proof spine, Isaac Sim, numpy, or scipy.",
        "",
        "## Evidence Boundary",
        "",
        "- `data/` is the self-contained audit bundle.",
        "- `data/runtime_capture.json` is copied into the package for runtime-backed closure and hash-bound by the manifest.",
        "- `package_manifest.json` and `data/artifact_index.json` hash-lock the data artifacts.",
        "- A local provenance source outside this tracked package was used to build the package, but the verifier audits the copied runtime-capture source in `data/runtime_capture.json` after generation.",
        "- The package opens no calibration, held-out, tuning, or closure seed range.",
        "- The package records spent/no-reuse ranges `40000-40049` and `42000-42049` as audit-only ranges.",
        "- `learning_proven_addendum` is absent.",
        "",
        "## Non-Claims",
        "",
        "- Does not claim real robot success.",
        "- Does not claim real robot readiness.",
        "- Does not claim physical robot readiness.",
        "- Does not claim deployable policy readiness.",
        "- Does not claim visual policy performance.",
        "- Does not claim HMD OpenXR collection readiness.",
        "- Does not claim HMD readiness.",
        "- Does not claim live runtime support.",
        "- Does not claim live UR runtime support.",
        "- Does not claim live UR hardware support.",
        "- Does not claim live Franka hardware support.",
        "- Does not claim live ROS2 DDS runtime support.",
        "- Does not claim ROS2 bridge support.",
        "- Does not claim Franka hardware support.",
        "- Does not claim UR hardware support.",
        "- Does not claim policy uplift.",
        "- Does not claim learning proven value.",
        "- Does not claim marketplace readiness.",
        "- Does not claim production certification.",
        "- Does not claim production auth.",
        "- Does not claim production robot support.",
        "- Does not claim universal robot support.",
        "- Does not claim public sample import.",
        "- Does not claim public sample evidence.",
        "- Does not claim DB migration.",
        "",
        "## Tamper Discipline",
        "",
        "G006/G009 verifies hash-refreshed semantic tamper cases against a copied real package: runtime capture source drift, preflight boolean drift, runtime capture ID drift, source-row embodiment drift, runtime metadata removal, source-row/runtime-metadata mismatch, forbidden claim injection, opened range injection, spent range weakening, count drift, projection binding drift, and required action-role removal.",
    ]
    output_dir.joinpath("README.md").write_text("\n".join(body) + "\n", encoding="utf-8")


def _write_indexes(output_dir: Path) -> None:
    data_dir = output_dir / "data"
    artifact_entries = []
    for path in sorted(data_dir.rglob("*")):
        if path.is_file() and path.name != "artifact_index.json":
            artifact_entries.append(_entry(output_dir, path))
    _write_json(data_dir / "artifact_index.json", {"artifact_index": artifact_entries})

    manifest_entries = [*artifact_entries, _entry(output_dir, data_dir / "artifact_index.json")]
    _write_json(
        output_dir / "package_manifest.json",
        {
            "schema_version": "rdf_mvp3c_isaac_sim_embodiment_source_package_manifest_v0.1.0",
            "package_name": PACKAGE_NAME,
            "created_at": PACKAGE_CREATED_AT,
            "claims": {
                "status": _read_json(data_dir / "embodiment_source_summary.json")["status"],
            },
            "artifact_index": manifest_entries,
            "non_claims": dict(NO_CLAIMS),
        },
    )


def _entry(output_dir: Path, path: Path) -> dict[str, Any]:
    return {
        "data_path": path.relative_to(output_dir).as_posix(),
        "hash_convention": "file_bytes",
        "file_sha256": _sha256(path),
        "byte_size": path.stat().st_size,
    }


def _capture_id(embodiment_id: str) -> str:
    return f"{embodiment_id}_runtime_capture_20260622T010000Z"


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_stable_json(payload) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(_stable_json(row) + "\n" for row in rows), encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="Run Isaac Sim runtime capture before building the package.",
    )
    parser.add_argument(
        "--runtime-capture-report",
        type=Path,
        default=None,
        help="Use an existing runtime_capture.json instead of synthetic evidence.",
    )
    parser.add_argument(
        "--runtime-capture-output",
        type=Path,
        default=DEFAULT_RUNTIME_CAPTURE_OUTPUT,
        help="Path where --preflight writes runtime_capture.json.",
    )
    parser.add_argument("--isaac-python", type=Path, default=DEFAULT_ISAAC_PYTHON)
    parser.add_argument(
        "--closure-assertion",
        action="store_true",
        help="Assert original MVP-3C closure from runtime evidence. G006+ only.",
    )
    parser.add_argument(
        "--evidence-kind",
        choices=("synthetic_verifier_fixture", "isaac_sim_runtime_backed_source_log"),
        default="synthetic_verifier_fixture",
    )
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = build_mvp3c_isaac_sim_embodiment_source(
        output_dir=args.output_dir,
        clean=args.clean,
        evidence_kind=args.evidence_kind,
        runtime_capture_report=args.runtime_capture_report,
        preflight=args.preflight,
        runtime_capture_output=args.runtime_capture_output,
        isaac_python=args.isaac_python,
        closure_assertion=args.closure_assertion,
    )
    if args.pretty:
        print(_stable_json(report))
    else:
        print(f"status={report['status']}")
        print(f"package_manifest={report['package_manifest']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
