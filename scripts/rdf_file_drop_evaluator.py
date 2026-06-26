#!/usr/bin/env python3
"""Local RDF file-drop evaluator CLI.

This alpha CLI is a product surface over the existing MVP-5A profile
contracts. It does not claim external partner data evaluation and does not
replace the independent verifier used for evaluator-run packages.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
from typing import Any
import uuid
import zipfile


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.mvp5a_file_drop_rehearsal import (  # noqa: E402
    PROFILE_IDS,
    build_profile_registry,
    export_profile_hdf5,
    sha256_file,
    stable_json,
    validate_profile_drop,
)


ARTIFACT_ROOT = Path(os.environ.get("RDF_FILE_DROP_EVALUATOR_ARTIFACT_ROOT", ROOT / "artifacts" / "rdf_file_drop_evaluator")).resolve()
RUN_MARKER = ".rdf_file_drop_evaluator_run"
MAX_ZIP_ENTRIES = 128
MAX_ZIP_ENTRY_BYTES = 2_000_000
MAX_ZIP_TOTAL_BYTES = 10_000_000
MAX_FOLDER_ENTRIES = MAX_ZIP_ENTRIES
MAX_FOLDER_ENTRY_BYTES = MAX_ZIP_ENTRY_BYTES
MAX_FOLDER_TOTAL_BYTES = MAX_ZIP_TOTAL_BYTES
NON_CLAIMS = {
    "external_partner_data_evaluated": False,
    "real_robot_data_evaluated": False,
    "real_robot_success": False,
    "hardware_readiness": False,
    "live_ur_rtde_support": False,
    "live_franka_support": False,
    "live_ros2_bridge_readiness": False,
    "policy_uplift": False,
    "production_readiness": False,
}


class CliError(Exception):
    def __init__(self, reason: str, *, details: str | None = None) -> None:
        self.reason = reason
        self.details = details
        super().__init__(reason)


def _emit(payload: dict[str, Any]) -> None:
    print(stable_json(payload))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload) + "\n", encoding="utf-8")


def _error_payload(reason: str, *, details: str | None = None, command: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "passed": False,
        "rejection_reasons": [reason],
    }
    if details:
        payload["details"] = details
    if command:
        payload["command"] = command
    return payload


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _validate_profile_id(profile_id: str) -> None:
    if profile_id not in PROFILE_IDS:
        raise CliError("unsupported_profile", details=f"unknown profile_id: {profile_id}")


def _profile_by_id(profile_id: str) -> dict[str, Any]:
    registry = build_profile_registry()
    for profile in registry["profiles"]:
        if profile["profile_id"] == profile_id:
            return profile
    raise CliError("unsupported_profile", details=f"unknown profile_id: {profile_id}")


def _scan_folder_safety(folder: Path) -> list[str]:
    issues: list[str] = []
    entries = list(folder.rglob("*"))
    if len(entries) > MAX_FOLDER_ENTRIES:
        issues.append("folder_too_many_entries")
    total_size = 0
    for path in folder.rglob("*"):
        if path.is_symlink():
            issues.append("symlink_escape")
            continue
        if path.is_file():
            byte_size = path.stat().st_size
            total_size += byte_size
            if byte_size > MAX_FOLDER_ENTRY_BYTES:
                issues.append("folder_entry_too_large")
    if total_size > MAX_FOLDER_TOTAL_BYTES:
        issues.append("folder_total_too_large")
    return sorted(set(issues))


def _zip_member_is_symlink(info: zipfile.ZipInfo) -> bool:
    mode = info.external_attr >> 16
    return stat.S_ISLNK(mode)


def _safe_extract_zip(zip_path: Path, output_dir: Path) -> None:
    output_root = output_dir.resolve()
    output_root.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(zip_path) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_ZIP_ENTRIES:
            raise CliError("zip_too_many_entries", details=f"{len(entries)} entries > {MAX_ZIP_ENTRIES}")
        total_size = sum(info.file_size for info in entries)
        if total_size > MAX_ZIP_TOTAL_BYTES:
            raise CliError("zip_total_too_large", details=f"{total_size} bytes > {MAX_ZIP_TOTAL_BYTES}")
        for info in entries:
            if info.file_size > MAX_ZIP_ENTRY_BYTES:
                raise CliError("zip_entry_too_large", details=f"{info.filename}: {info.file_size} bytes")
        seen_targets: set[str] = set()
        for info in archive.infolist():
            member_name = info.filename
            member_path = Path(member_name)
            if member_path.is_absolute() or member_name.startswith(("/", "\\")):
                raise CliError("path_traversal", details=f"unsafe absolute zip member: {member_name}")
            if any(part in {"..", ""} for part in member_path.parts):
                raise CliError("path_traversal", details=f"unsafe zip member: {member_name}")
            if _zip_member_is_symlink(info):
                raise CliError("symlink_escape", details=f"zip symlink member rejected: {member_name}")
            target = output_root / member_path
            if not _is_within(target, output_root):
                raise CliError("path_traversal", details=f"unsafe zip member: {member_name}")
            normalized_target = target.resolve(strict=False).relative_to(output_root).as_posix()
            if normalized_target in seen_targets:
                raise CliError("duplicate_zip_member", details=f"duplicate zip target: {member_name}")
            seen_targets.add(normalized_target)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(info) as source, target.open("wb") as dest:
                shutil.copyfileobj(source, dest)


def _resolve_input(input_path: Path, temp_root: Path) -> tuple[Path, str, list[str]]:
    if not input_path.exists():
        return input_path, "missing", ["input_missing"]
    if input_path.is_dir():
        return input_path, "folder", _scan_folder_safety(input_path)
    if input_path.is_file() and input_path.suffix.lower() == ".zip":
        extract_dir = temp_root / "unzipped_drop"
        try:
            _safe_extract_zip(input_path, extract_dir)
        except CliError as exc:
            return extract_dir, "zip", [exc.reason]
        return extract_dir, "zip", _scan_folder_safety(extract_dir)
    return input_path, "unsupported", ["unsupported_input_kind"]


def _validation_payload(result: Any, *, input_path: Path, resolved_path: Path, input_kind: str) -> dict[str, Any]:
    return {
        "ok": result.passed,
        "passed": result.passed,
        "command": "preflight",
        "profile_id": result.profile_id,
        "input_path": str(input_path),
        "resolved_input_path": str(resolved_path),
        "input_kind": input_kind,
        "frame_count": result.frame_count,
        "rejection_reasons": list(result.rejection_reasons),
        "source_file_hashes": result.source_file_hashes,
        "export_eligible": result.export_eligible,
        "trainer_smoke_eligible": result.trainer_smoke_eligible,
        "external_partner_data_evaluated": False,
        "real_robot_data_evaluated": False,
        "hardware_readiness": False,
        "policy_uplift": False,
    }


def _source_file_hashes(source_root: Path) -> dict[str, dict[str, Any]]:
    hashes: dict[str, dict[str, Any]] = {}
    for path in sorted(source_root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(source_root).as_posix()
            hashes[rel] = {"sha256": sha256_file(path), "byte_size": path.stat().st_size}
    return hashes


def _normalized_contract(result: Any, *, profile_id: str) -> dict[str, Any]:
    profile = _profile_by_id(profile_id)
    return {
        "schema_version": "rdf_mvp5b_file_drop_normalized_contract_v0.1.0",
        "profile_id": profile_id,
        "passed": result.passed,
        "frame_count": result.frame_count,
        "state_dim": profile["dof"],
        "action_dim": profile["dof"],
        "action_semantics": profile["action_semantics"],
        "state_semantics": profile["state_semantics"],
        "export_eligible": result.export_eligible,
        "trainer_smoke_eligible": result.trainer_smoke_eligible,
        "rows": [
            {
                "timestamp": row["timestamp"],
                "state_vector": row["state_vector"],
                "action_vector": row["action_vector"],
            }
            for row in result.normalized_rows
        ],
    }


def _copy_source_drop(resolved: Path, run_dir: Path) -> Path:
    source_target = run_dir / "source_drop"
    if source_target.exists():
        shutil.rmtree(source_target)
    shutil.copytree(resolved, source_target, symlinks=False)
    return source_target


def _artifact_role(rel: str) -> str:
    if rel.startswith("source_drop/"):
        return "source_drop"
    if rel.startswith("normalized/"):
        return "normalized_contract"
    if rel.startswith("export/"):
        return "export"
    if rel.startswith("reports/"):
        return "buyer_report"
    if rel.endswith("input_receipt.json"):
        return "input_receipt"
    if rel.endswith("preflight_result.json"):
        return "preflight_result"
    if rel.endswith("evaluation_result.json"):
        return "evaluation_result"
    return "supporting_artifact"


def _artifact_index(run_dir: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(run_dir).as_posix()
        if rel in {"package_manifest.json", "verifier_result.json"}:
            continue
        artifacts.append({"path": rel, "sha256": sha256_file(path), "byte_size": path.stat().st_size, "role": _artifact_role(rel)})
    return artifacts


def _write_buyer_reports(run_dir: Path, *, profile_id: str, result: Any, input_kind: str) -> None:
    report = {
        "schema_version": "rdf_mvp5b_file_drop_buyer_report_v0.1.0",
        "profile_id": profile_id,
        "input_kind": input_kind,
        "passed": result.passed,
        "frame_count": result.frame_count,
        "rejection_reasons": list(result.rejection_reasons),
        "trust_boundary": "pre_real_log_digital_twin_file_drop_rehearsal",
        "proof_source_of_truth": "included_source_drop_and_independent_verifier",
        "non_claims": dict(NON_CLAIMS),
    }
    _write_json(run_dir / "reports" / "buyer_report.json", report)
    status = "PASS" if result.passed else "REJECTED"
    html = f"""<!doctype html>
<html lang=\"en\">
<head><meta charset=\"utf-8\"><title>RDF File-Drop Evaluation</title></head>
<body>
<h1>RDF File-Drop Evaluation Alpha</h1>
<p>Status: <strong>{status}</strong></p>
<p>Profile: <code>{profile_id}</code></p>
<p>Frames: {result.frame_count}</p>
<p>Evidence source of truth: included source_drop plus independent verifier recomputation.</p>
<p>Boundary: pre-real-log digital-twin rehearsal only.</p>
<p>No real-robot, hardware, live-runtime, policy-uplift, production, or external-partner claim.</p>
</body>
</html>
"""
    (run_dir / "reports").mkdir(parents=True, exist_ok=True)
    (run_dir / "reports" / "buyer_report.html").write_text(html, encoding="utf-8")


def _write_package_manifest(run_dir: Path, *, profile_id: str, result: Any, run_id: str) -> Path:
    manifest = {
        "schema_version": "rdf_mvp5b_file_drop_evaluator_run_manifest_v0.1.0",
        "package_kind": "rdf_file_drop_evaluator_run",
        "package_status": "file_drop_rehearsal_run_evaluated",
        "run_id": run_id,
        "profile_id": profile_id,
        "passed": result.passed,
        "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "producer": "scripts/rdf_file_drop_evaluator.py",
        "verifier": "scripts/verify_rdf_file_drop_evaluator_run.py",
        "external_partner_data_evaluated": False,
        "real_robot_data_evaluated": False,
        "generated_by_rdf_sim": True,
        "non_claims": dict(NON_CLAIMS),
        "artifact_index": _artifact_index(run_dir),
    }
    manifest_path = run_dir / "package_manifest.json"
    _write_json(manifest_path, manifest)
    return manifest_path


def cmd_profiles_list(_: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    registry = build_profile_registry()
    payload = {
        "ok": True,
        "command": "profiles list",
        "profile_ids": registry["required_profile_ids"],
        "profile_count": registry["profile_count"],
        "profiles": registry["profiles"],
    }
    return 0, payload


def cmd_profiles_inspect(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    try:
        profile = _profile_by_id(args.profile_id)
    except CliError as exc:
        return 2, _error_payload(exc.reason, details=exc.details, command="profiles inspect")
    return 0, {"ok": True, "command": "profiles inspect", "profile": profile}


def cmd_preflight(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    try:
        _validate_profile_id(args.profile)
    except CliError as exc:
        return 2, _error_payload(exc.reason, details=exc.details, command="preflight")

    input_path = Path(args.input_path)
    with tempfile.TemporaryDirectory(prefix="rdf_file_drop_preflight_") as tmp:
        resolved, input_kind, safety_issues = _resolve_input(input_path, Path(tmp))
        if safety_issues:
            payload = _error_payload(safety_issues[0], command="preflight")
            payload.update(
                {
                    "profile_id": args.profile,
                    "input_path": str(input_path),
                    "resolved_input_path": str(resolved),
                    "input_kind": input_kind,
                    "rejection_reasons": safety_issues,
                }
            )
            return 2, payload
        result = validate_profile_drop(resolved, expected_profile_id=args.profile, case_id="preflight")
        payload = _validation_payload(result, input_path=input_path, resolved_path=resolved, input_kind=input_kind)
        return (0 if result.passed else 2), payload


def _managed_run_dir(path: Path) -> bool:
    return (path / RUN_MARKER).is_file()


def _output_dir(args: argparse.Namespace) -> tuple[Path, str]:
    if args.out:
        out = Path(args.out).resolve()
        if not _is_within(out, ARTIFACT_ROOT):
            raise CliError("unsafe_output_path", details=f"--out must be under {ARTIFACT_ROOT}")
        return out, out.name
    run_id = f"{args.profile}-{uuid.uuid4().hex[:12]}"
    return ARTIFACT_ROOT / run_id, run_id


def cmd_evaluate(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    try:
        _validate_profile_id(args.profile)
    except CliError as exc:
        return 2, _error_payload(exc.reason, details=exc.details, command="evaluate")

    input_path = Path(args.input_path)
    try:
        run_dir, run_id = _output_dir(args)
    except CliError as exc:
        return 2, _error_payload(exc.reason, details=exc.details, command="evaluate")
    if run_dir.exists() and any(run_dir.iterdir()):
        if not args.force:
            return 2, _error_payload("output_exists", details=str(run_dir), command="evaluate")
        if not _managed_run_dir(run_dir):
            return 2, _error_payload("unsafe_output_path", details="--force only deletes managed evaluator-run directories", command="evaluate")

    with tempfile.TemporaryDirectory(prefix="rdf_file_drop_evaluate_") as tmp:
        resolved, input_kind, safety_issues = _resolve_input(input_path, Path(tmp))
        if safety_issues:
            payload = _error_payload(safety_issues[0], command="evaluate")
            payload.update({"profile_id": args.profile, "input_path": str(input_path), "input_kind": input_kind, "rejection_reasons": safety_issues})
            return 2, payload

        if run_dir.exists():
            shutil.rmtree(run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / RUN_MARKER).write_text("rdf_file_drop_evaluator_run\n", encoding="utf-8")
        source_drop = _copy_source_drop(resolved, run_dir)
        result = validate_profile_drop(source_drop, expected_profile_id=args.profile, case_id="evaluator_run")
        source_hashes = _source_file_hashes(source_drop)
        input_receipt = {
            "schema_version": "rdf_mvp5b_file_drop_input_receipt_v0.1.0",
            "profile_id": args.profile,
            "input_path": str(input_path),
            "input_kind": input_kind,
            "source_drop_path": "source_drop",
            "source_file_hashes": source_hashes,
            "generated_by_rdf_sim": True,
            "external_partner_data_evaluated": False,
            "real_robot_data_evaluated": False,
            "non_claims": dict(NON_CLAIMS),
        }
        preflight = _validation_payload(result, input_path=input_path, resolved_path=source_drop, input_kind=input_kind)
        preflight["profile_id"] = args.profile
        preflight["observed_profile_id"] = result.profile_id
        preflight["source_file_hashes"] = source_hashes
        evaluation = {
            "schema_version": "rdf_mvp5b_file_drop_evaluation_result_v0.1.0",
            "profile_id": args.profile,
            "observed_profile_id": result.profile_id,
            "passed": result.passed,
            "frame_count": result.frame_count,
            "rejection_reasons": list(result.rejection_reasons),
            "export_eligible": result.export_eligible,
            "trainer_smoke_eligible": result.trainer_smoke_eligible,
            "external_partner_data_evaluated": False,
            "real_robot_data_evaluated": False,
            "non_claims": dict(NON_CLAIMS),
        }
        _write_json(run_dir / "input_receipt.json", input_receipt)
        _write_json(run_dir / "preflight_result.json", preflight)
        _write_json(run_dir / "evaluation_result.json", evaluation)
        _write_json(run_dir / "normalized" / "normalized_contract.json", _normalized_contract(result, profile_id=args.profile))
        if result.export_eligible:
            export_profile_hdf5(result.profile_id, result.normalized_rows, run_dir / "export")
        _write_buyer_reports(run_dir, profile_id=args.profile, result=result, input_kind=input_kind)
        manifest_path = _write_package_manifest(run_dir, profile_id=args.profile, result=result, run_id=run_id)

    payload = {
        "ok": result.passed,
        "passed": result.passed,
        "command": "evaluate",
        "run_id": run_id,
        "run_dir": str(run_dir),
        "package_manifest": str(manifest_path),
        "profile_id": args.profile,
        "observed_profile_id": result.profile_id,
        "input_kind": input_kind,
        "frame_count": result.frame_count,
        "rejection_reasons": list(result.rejection_reasons),
        "external_partner_data_evaluated": False,
        "real_robot_data_evaluated": False,
    }
    return (0 if result.passed else 2), payload


def cmd_verify(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    target = Path(args.path)
    manifest = target / "package_manifest.json" if target.is_dir() else target
    verifier = ROOT / "scripts" / "verify_rdf_file_drop_evaluator_run.py"
    command = [sys.executable, str(verifier), str(manifest), "--json"]
    if args.deep_hdf5:
        command.insert(-1, "--deep-hdf5")
    try:
        completed = subprocess.run(command, cwd=ROOT, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
    except subprocess.TimeoutExpired as exc:
        return 2, _error_payload("verifier_timeout", details=str(exc), command="verify")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = _error_payload("verifier_output_invalid", details=completed.stderr, command="verify")
    payload["verifier"] = "verify_rdf_file_drop_evaluator_run.py"
    return completed.returncode, payload


def _load_run_json(run_dir: Path, rel_path: str) -> dict[str, Any]:
    target = run_dir / rel_path
    if not target.is_file():
        raise CliError("missing_run_artifact", details=rel_path)
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CliError("invalid_run_artifact", details=rel_path)
    return payload


def cmd_report(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    run_dir = Path(args.path)
    if not run_dir.is_dir():
        return 2, _error_payload("run_dir_missing", details=str(run_dir), command="report")
    try:
        manifest = _load_run_json(run_dir, "package_manifest.json")
        evaluation = _load_run_json(run_dir, "evaluation_result.json")
        buyer_report = _load_run_json(run_dir, "reports/buyer_report.json")
    except (CliError, json.JSONDecodeError) as exc:
        if isinstance(exc, CliError):
            return 2, _error_payload(exc.reason, details=exc.details, command="report")
        return 2, _error_payload("invalid_run_artifact", details=str(exc), command="report")
    return 0, {
        "ok": True,
        "command": "report",
        "run_dir": str(run_dir),
        "package_manifest": str(run_dir / "package_manifest.json"),
        "buyer_report_json": str(run_dir / "reports" / "buyer_report.json"),
        "buyer_report_html": str(run_dir / "reports" / "buyer_report.html"),
        "profile_id": manifest.get("profile_id"),
        "run_id": manifest.get("run_id"),
        "passed": evaluation.get("passed"),
        "frame_count": evaluation.get("frame_count"),
        "rejection_reasons": evaluation.get("rejection_reasons", []),
        "proof_source_of_truth": buyer_report.get("proof_source_of_truth"),
        "non_claims": buyer_report.get("non_claims", {}),
        "verifier_command": [
            sys.executable,
            str(ROOT / "scripts" / "verify_rdf_file_drop_evaluator_run.py"),
            str(run_dir / "package_manifest.json"),
            "--deep-hdf5",
            "--json",
        ],
    }


def cmd_doctor(_: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    verifier = ROOT / "scripts" / "verify_rdf_file_drop_evaluator_run.py"
    registry = build_profile_registry()
    checks = {
        "repo_root_exists": ROOT.is_dir(),
        "artifact_root_under_repo": _is_within(ARTIFACT_ROOT, ROOT),
        "verifier_exists": verifier.is_file(),
        "profile_registry_exact": registry["required_profile_ids"] == list(PROFILE_IDS),
        "no_external_runtime_required": True,
        "non_claims_pinned_false": all(value is False for value in NON_CLAIMS.values()),
    }
    ok = all(checks.values())
    return (0 if ok else 2), {
        "ok": ok,
        "command": "doctor",
        "checks": checks,
        "profile_ids": registry["required_profile_ids"],
        "artifact_root": str(ARTIFACT_ROOT),
        "verifier": str(verifier),
        "external_partner_data_evaluated": False,
        "real_robot_data_evaluated": False,
        "hardware_readiness": False,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    profiles = subcommands.add_parser("profiles")
    profile_subcommands = profiles.add_subparsers(dest="profiles_command", required=True)
    profiles_list = profile_subcommands.add_parser("list")
    profiles_list.add_argument("--json", action="store_true")
    profiles_list.set_defaults(func=cmd_profiles_list)
    profiles_inspect = profile_subcommands.add_parser("inspect")
    profiles_inspect.add_argument("profile_id")
    profiles_inspect.add_argument("--json", action="store_true")
    profiles_inspect.set_defaults(func=cmd_profiles_inspect)

    preflight = subcommands.add_parser("preflight")
    preflight.add_argument("input_path")
    preflight.add_argument("--profile", required=True)
    preflight.add_argument("--json", action="store_true")
    preflight.set_defaults(func=cmd_preflight)

    evaluate = subcommands.add_parser("evaluate")
    evaluate.add_argument("input_path")
    evaluate.add_argument("--profile", required=True)
    evaluate.add_argument("--out")
    evaluate.add_argument("--force", action="store_true")
    evaluate.add_argument("--json", action="store_true")
    evaluate.set_defaults(func=cmd_evaluate)

    verify = subcommands.add_parser("verify")
    verify.add_argument("path")
    verify.add_argument("--deep-hdf5", action="store_true")
    verify.add_argument("--json", action="store_true")
    verify.set_defaults(func=cmd_verify)

    report = subcommands.add_parser("report")
    report.add_argument("path")
    report.add_argument("--json", action="store_true")
    report.set_defaults(func=cmd_report)

    doctor = subcommands.add_parser("doctor")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        rc, payload = args.func(args)
    except CliError as exc:
        rc, payload = 2, _error_payload(exc.reason, details=exc.details, command=getattr(args, "command", None))
    except Exception as exc:  # pragma: no cover - fail-closed CLI guard
        rc, payload = 2, _error_payload("internal_error", details=str(exc), command=getattr(args, "command", None))
    _emit(payload)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
