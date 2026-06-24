#!/usr/bin/env python3
"""Verify the External Robot Data Ingest / Evaluation v0 package.

The verifier is intentionally stdlib-only. It reads the package data files,
recomputes hashes and status consistency, and refuses to promote a contract-ready
package into an external-data-evaluated claim without included source rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


PACKAGE_STATUS_CONTRACT_READY = "external_ingest_contract_ready"
PACKAGE_STATUS_EXTERNAL_DATA_EVALUATED = "external_data_evaluated"
SPENT_RANGES = ((40000, 40049), (42000, 42049))
FORBIDDEN_TRUE_CLAIMS = {
    "real_robot_success",
    "physical_robot_readiness",
    "deployable_policy_readiness",
    "visual_policy_performance",
    "hmd_openxr_readiness",
    "live_ur_rtde_support",
    "live_franka_hardware_support",
    "live_ros2_dds_bridge_readiness",
    "universal_robot_support",
    "marketplace_readiness",
    "production_certification",
    "sim_to_real_proven",
    "general_robot_intelligence",
    "policy_uplift_or_learning_proven",
}


def verify_package(manifest_path: Path) -> dict[str, Any]:
    issues: list[str] = []
    package_dir = manifest_path.parent
    manifest = _read_json(manifest_path, issues, label="package_manifest")
    data_dir = package_dir / "data"

    if not isinstance(manifest.get("artifact_index"), list):
        issues.append("package_manifest artifact_index must be list")
    else:
        issues.extend(_verify_manifest_artifact_index(package_dir, manifest["artifact_index"]))

    config = _read_json(data_dir / "config.json", issues, label="data/config.json")
    artifact_index = _read_json(data_dir / "artifact_index.json", issues, label="data/artifact_index.json")
    buyer = _read_json(
        data_dir / "reports" / "buyer_data_evaluation_report.json",
        issues,
        label="data/reports/buyer_data_evaluation_report.json",
    )
    non_claims = _read_json(data_dir / "non_claims_attestation.json", issues, label="data/non_claims_attestation.json")
    source_availability = _read_json(
        data_dir / "source" / "source_availability_report.json",
        issues,
        label="data/source/source_availability_report.json",
    )
    source_hashes = _read_json(data_dir / "source" / "source_file_hashes.json", issues, label="data/source/source_file_hashes.json")

    status = str(manifest.get("package_status") or "")
    external_source_included = manifest.get("external_source_included")
    _verify_status_contract(
        issues,
        manifest=manifest,
        config=config,
        buyer=buyer,
        source_availability=source_availability,
        source_hashes=source_hashes,
    )
    _verify_data_artifact_index(package_dir, artifact_index, issues)
    _verify_non_claims(manifest, config, buyer, non_claims, issues)
    _verify_readme_non_claims(package_dir / "README.md", issues)
    _verify_spent_ranges(package_dir, issues)

    if status == PACKAGE_STATUS_CONTRACT_READY:
        _verify_contract_ready_package(package_dir, external_source_included, issues)
    elif status == PACKAGE_STATUS_EXTERNAL_DATA_EVALUATED:
        _verify_external_data_evaluated_package(package_dir, external_source_included, issues)
    else:
        issues.append(f"unknown package_status: {status}")

    return {
        "ok": not issues,
        "status": status,
        "external_source_included": external_source_included,
        "issues": _dedupe(issues),
    }


def _verify_manifest_artifact_index(package_dir: Path, artifact_index: list[Any]) -> list[str]:
    issues: list[str] = []
    seen: set[str] = set()
    for entry in artifact_index:
        if not isinstance(entry, dict):
            issues.append("artifact_index entry must be object")
            continue
        data_path = entry.get("data_path")
        if not isinstance(data_path, str) or not data_path.startswith("data/"):
            issues.append("artifact_index data_path must be data-relative string")
            continue
        if data_path in seen:
            issues.append(f"{data_path} duplicate artifact index entry")
        seen.add(data_path)
        path = package_dir / data_path
        if not path.exists() or not path.is_file():
            issues.append(f"{data_path} missing")
            continue
        actual_hash = _sha256_file(path)
        if entry.get("file_sha256") != actual_hash:
            issues.append(f"{data_path} sha256 mismatch")
        if entry.get("byte_size") != path.stat().st_size:
            issues.append(f"{data_path} byte_size mismatch")
        if entry.get("hash_convention") != "file_bytes":
            issues.append(f"{data_path} hash_convention mismatch")
    return issues


def _verify_data_artifact_index(package_dir: Path, artifact_index: dict[str, Any], issues: list[str]) -> None:
    entries = artifact_index.get("artifact_index")
    if not isinstance(entries, list):
        issues.append("data/artifact_index.json artifact_index must be list")
        return
    indexed = {entry.get("data_path") for entry in entries if isinstance(entry, dict)}
    expected = {
        path.relative_to(package_dir).as_posix()
        for path in sorted((package_dir / "data").rglob("*"))
        if path.is_file() and path.name != "artifact_index.json"
    }
    if indexed != expected:
        issues.append("data/artifact_index.json does not match package data files")
    for entry in entries:
        if not isinstance(entry, dict):
            issues.append("data/artifact_index entry must be object")
            continue
        data_path = entry.get("data_path")
        if not isinstance(data_path, str):
            issues.append("data/artifact_index data_path must be string")
            continue
        path = package_dir / data_path
        if path.exists() and entry.get("file_sha256") != _sha256_file(path):
            issues.append(f"{data_path} data artifact sha256 mismatch")


def _verify_status_contract(
    issues: list[str],
    *,
    manifest: dict[str, Any],
    config: dict[str, Any],
    buyer: dict[str, Any],
    source_availability: dict[str, Any],
    source_hashes: dict[str, Any],
) -> None:
    status = manifest.get("package_status")
    included = manifest.get("external_source_included")
    if config.get("status") != status:
        issues.append("config.status does not match package_manifest.package_status")
    if config.get("package_status") != status:
        issues.append("config.package_status does not match package_manifest.package_status")
    if config.get("external_source_included") != included:
        issues.append("config.external_source_included mismatch")
    if buyer.get("claim") != status:
        issues.append("buyer report claim mismatch")
    if buyer.get("external_data_evaluated") != (status == PACKAGE_STATUS_EXTERNAL_DATA_EVALUATED):
        issues.append("buyer report external_data_evaluated mismatch")
    if source_availability.get("external_source_included") != included:
        issues.append("source availability external_source_included mismatch")
    if status == PACKAGE_STATUS_CONTRACT_READY and source_hashes != {}:
        issues.append("contract-ready package source_file_hashes must be empty")


def _verify_non_claims(
    manifest: dict[str, Any],
    config: dict[str, Any],
    buyer: dict[str, Any],
    non_claims: dict[str, Any],
    issues: list[str],
) -> None:
    attested = non_claims.get("non_claims")
    if set(manifest.get("non_claims") or {}) != FORBIDDEN_TRUE_CLAIMS:
        issues.append("package_manifest non_claim keys mismatch")
    if set(config.get("non_claims") or {}) != FORBIDDEN_TRUE_CLAIMS:
        issues.append("config non_claim keys mismatch")
    if set(buyer.get("non_claims") or {}) != FORBIDDEN_TRUE_CLAIMS:
        issues.append("buyer report non_claim keys mismatch")
    if set(attested or {}) != FORBIDDEN_TRUE_CLAIMS:
        issues.append("non_claims_attestation keys mismatch")
    for label, payload in (
        ("package_manifest", manifest.get("non_claims")),
        ("config", config.get("non_claims")),
        ("buyer report", buyer.get("non_claims")),
        ("non_claims_attestation", attested),
    ):
        if isinstance(payload, dict):
            for key, value in payload.items():
                if key in FORBIDDEN_TRUE_CLAIMS and value is not False:
                    issues.append(f"{label} forbidden claim {key} must be false")
    _scan_forbidden_true_claims(manifest, "package_manifest", issues)
    _scan_forbidden_true_claims(config, "config", issues)
    _scan_forbidden_true_claims(buyer, "buyer report", issues)
    _scan_forbidden_true_claims(non_claims, "non_claims_attestation", issues)


def _verify_readme_non_claims(readme_path: Path, issues: list[str]) -> None:
    try:
        text = readme_path.read_text(encoding="utf-8").lower()
    except OSError as exc:
        issues.append(f"README unreadable: {exc}")
        return
    for key in FORBIDDEN_TRUE_CLAIMS:
        lowered = key.lower()
        true_patterns = (
            f"{lowered}: true",
            f"{lowered}=true",
            f'"{lowered}": true',
            f'"{lowered}":true',
        )
        if any(pattern in text for pattern in true_patterns):
            issues.append(f"README forbidden claim {key} leaked true")


def _verify_contract_ready_package(package_dir: Path, external_source_included: Any, issues: list[str]) -> None:
    if external_source_included is not False:
        issues.append("contract-ready package must set external_source_included=false")
    forbidden_rows = (
        package_dir / "data" / "source" / "metadata.json",
        package_dir / "data" / "source" / "accepted_command_state.jsonl",
        package_dir / "data" / "source" / "rejected_command_state.jsonl",
    )
    for path in forbidden_rows:
        if path.exists():
            issues.append(f"contract-ready package must not include {path.relative_to(package_dir).as_posix()}")


def _verify_external_data_evaluated_package(package_dir: Path, external_source_included: Any, issues: list[str]) -> None:
    issues.append(
        "external_data_evaluated verifier requires semantic parity artifacts before enablement"
    )
    if external_source_included is not True:
        issues.append("external_data_evaluated package must set external_source_included=true")
    source_dir = package_dir / "data" / "source"
    required = ("metadata.json", "accepted_command_state.jsonl", "rejected_command_state.jsonl")
    for name in required:
        if not (source_dir / name).exists():
            issues.append(f"external_data_evaluated package missing data/source/{name}")
    accepted = _read_jsonl(source_dir / "accepted_command_state.jsonl", issues, label="accepted source rows")
    rejected = _read_jsonl(source_dir / "rejected_command_state.jsonl", issues, label="rejected source rows")
    if len(accepted) < 4:
        issues.append("external_data_evaluated accepted_rows < 4")
    if len(rejected) != 1:
        issues.append("external_data_evaluated rejected_rows must equal 1")


def _verify_spent_ranges(package_dir: Path, issues: list[str]) -> None:
    for path in sorted((package_dir / "data").rglob("*.json")):
        payload = _read_json(path, issues, label=path.relative_to(package_dir).as_posix())
        _scan_seed_values(payload, path.relative_to(package_dir).as_posix(), issues)
    for path in sorted((package_dir / "data").rglob("*.jsonl")):
        for row in _read_jsonl(path, issues, label=path.relative_to(package_dir).as_posix()):
            _scan_seed_values(row, path.relative_to(package_dir).as_posix(), issues)


def _scan_seed_values(payload: Any, label: str, issues: list[str], key_path: str = "") -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            next_path = f"{key_path}.{key}" if key_path else str(key)
            if "seed" in str(key).lower():
                for seed in _iter_ints(value):
                    if _in_spent_range(seed):
                        issues.append(f"{label} seed-like field {next_path} reuses spent seed {seed}")
            _scan_seed_values(value, label, issues, next_path)
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            _scan_seed_values(item, label, issues, f"{key_path}[{index}]")


def _scan_forbidden_true_claims(payload: Any, label: str, issues: list[str]) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in FORBIDDEN_TRUE_CLAIMS and value is True:
                issues.append(f"{label} forbidden claim {key} leaked true")
            _scan_forbidden_true_claims(value, label, issues)
    elif isinstance(payload, list):
        for item in payload:
            _scan_forbidden_true_claims(item, label, issues)


def _iter_ints(value: Any) -> list[int]:
    if isinstance(value, bool):
        return []
    if isinstance(value, int):
        return [value]
    if isinstance(value, list):
        out: list[int] = []
        for item in value:
            out.extend(_iter_ints(item))
        return out
    if isinstance(value, dict):
        out = []
        for item in value.values():
            out.extend(_iter_ints(item))
        return out
    return []


def _in_spent_range(value: int) -> bool:
    return any(start <= value <= end for start, end in SPENT_RANGES)


def _read_json(path: Path, issues: list[str], *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        issues.append(f"{label} invalid json: {exc}")
        return {}
    if not isinstance(payload, dict):
        issues.append(f"{label} must be object")
        return {}
    return payload


def _read_jsonl(path: Path, issues: list[str], *, label: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        issues.append(f"{label} unreadable: {exc}")
        return []
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            issues.append(f"{label} line {index} invalid json: {exc}")
            continue
        if isinstance(row, dict):
            rows.append(row)
        else:
            issues.append(f"{label} line {index} must be object")
    return rows


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dedupe(issues: list[str]) -> list[str]:
    return list(dict.fromkeys(issues))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_manifest", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = verify_package(args.package_manifest)
    if result["ok"]:
        print("VERDICT: VERIFIED")
        print(f"status={result['status']}")
        print(f"external_source_included={str(result['external_source_included']).lower()}")
        return 0
    print("VERDICT: FAILED")
    print(f"status={result['status']}")
    print(f"external_source_included={str(result['external_source_included']).lower()}")
    for issue in result["issues"]:
        print(f"- {issue}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
