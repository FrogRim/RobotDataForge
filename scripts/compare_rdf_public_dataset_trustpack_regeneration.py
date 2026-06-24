#!/usr/bin/env python3
"""Compare a generated RDF TrustPack against the closed matrix package."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any


REQUIRED_PROFILE_IDS = (
    "lerobot_aloha_static_coffee",
    "lerobot_svla_so100_pickplace",
)


@dataclass(frozen=True)
class ComparisonResult:
    passed: bool
    issues: tuple[str, ...]
    baseline_digest: str
    generated_digest: str
    profile_digests: dict[str, dict[str, str]]
    html_byte_match: bool


def compare_packages(*, baseline_package_dir: Path, generated_package_dir: Path) -> ComparisonResult:
    baseline_facts = collect_package_facts(baseline_package_dir, include_trustpack_artifacts=False)
    generated_facts = collect_package_facts(generated_package_dir, include_trustpack_artifacts=True)
    issues: list[str] = []
    baseline_core = baseline_facts["core"]
    generated_core = generated_facts["core"]
    if baseline_core != generated_core:
        issues.append("core facts differ")
    registry_issues = _validate_profile_registry(generated_package_dir, generated_core)
    issues.extend(registry_issues)
    html_byte_match = _html_byte_match(generated_package_dir)
    if not html_byte_match:
        issues.append("html copies differ")
    return ComparisonResult(
        passed=not issues,
        issues=tuple(issues),
        baseline_digest=_digest(baseline_core),
        generated_digest=_digest(generated_core),
        profile_digests=generated_facts["profile_digests"],
        html_byte_match=html_byte_match,
    )


def collect_package_facts(package_dir: Path, *, include_trustpack_artifacts: bool) -> dict[str, Any]:
    manifest = _read_json(package_dir / "package_manifest.json")
    config = _read_json(package_dir / "data" / "config.json")
    summary = _read_json(package_dir / "data" / "matrix_summary.json")
    resolver = _read_json(package_dir / "data" / "profile_resolver_report.json")
    non_claims = _read_json(package_dir / "data" / "non_claims_attestation.json").get("non_claims")
    profiles: dict[str, Any] = {}
    profile_digests: dict[str, dict[str, str]] = {}
    for profile_id in REQUIRED_PROFILE_IDS:
        root = package_dir / "data" / "profiles" / profile_id
        raw_rows = _read_jsonl(root / "source" / "lerobot_raw_rows.jsonl")
        converted_rows = _read_jsonl(root / "conversion" / "rdf_converted_rows.jsonl")
        raw_rows_digest = _digest(raw_rows)
        converted_rows_digest = _digest(converted_rows)
        hdf5_file_sha256 = _sha256_file(root / "export" / "dataset.hdf5")
        profile_facts = {
            "metadata": _read_json(root / "profile_metadata.json"),
            "source_binding": _read_json(root / "source" / "public_source_binding.json"),
            "source_schema": _read_json(root / "source" / "lerobot_feature_schema.json"),
            "slice_selection": _read_json(root / "source" / "slice_selection_report.json"),
            "extraction": _read_json(root / "source" / "extraction_receipt.json"),
            "conversion_manifest": _read_json(root / "conversion" / "conversion_manifest.json"),
            "semantic_mapping": _read_json(root / "conversion" / "semantic_mapping_report.json"),
            "contract": _read_json(root / "contracts" / "normalized_state_action_contract.json"),
            "validator": _read_json(root / "contracts" / "validator_report.json"),
            "hdf5_inspection": _read_json(root / "export" / "hdf5_inspection_report.json"),
            "trainer": _read_json(root / "export" / "trainer_smoke_report.json"),
            "buyer_json": _read_json(root / "reports" / "buyer_data_evaluation_report.json"),
            "raw_rows_digest": raw_rows_digest,
            "converted_rows_digest": converted_rows_digest,
            "hdf5_file_sha256": hdf5_file_sha256,
        }
        profiles[profile_id] = profile_facts
        profile_digests[profile_id] = {
            "raw_rows_digest": raw_rows_digest,
            "converted_rows_digest": converted_rows_digest,
            "hdf5_file_sha256": hdf5_file_sha256,
        }
    core = {
        "package_status": manifest.get("package_status"),
        "required_profiles": manifest.get("required_profiles"),
        "config": {
            "package_status": config.get("package_status"),
            "required_profiles": config.get("required_profiles"),
            "profile_count": config.get("profile_count"),
            "full_lerobot_parser_claimed": config.get("full_lerobot_parser_claimed"),
            "audited_slice_verdict_claimed": config.get("audited_slice_verdict_claimed"),
            "full_source_verdict_claimed": config.get("full_source_verdict_claimed"),
        },
        "summary": {
            "package_status": summary.get("package_status"),
            "required_profiles": summary.get("required_profiles"),
            "profile_count": summary.get("profile_count"),
            "profile_summaries": summary.get("profile_summaries"),
            "variety_gate": summary.get("variety_gate"),
        },
        "resolver": {
            "ok": resolver.get("ok"),
            "selected_profile_id": resolver.get("selected_profile_id"),
        },
        "non_claims": non_claims,
        "profiles": profiles,
    }
    facts: dict[str, Any] = {"core": core, "profile_digests": profile_digests}
    if include_trustpack_artifacts:
        facts["trustpack_artifacts"] = {
            "profile_registry_present": (package_dir / "data" / "profile_registry.json").is_file(),
            "buyer_report_present": (package_dir / "data" / "reports" / "buyer_report.html").is_file(),
            "claim_scan_present": (package_dir / "data" / "claim_scan_report.json").is_file(),
        }
    return facts


def report_payload(result: ComparisonResult) -> dict[str, Any]:
    return {
        "schema_version": "rdf_trustpack_regeneration_report_v0.1.0",
        "comparator": "rdf_trustpack_regeneration_comparator_v0.1.0",
        "passed": result.passed,
        "semantic_equivalent": result.passed,
        "issue_count": len(result.issues),
        "compared_profile_count": len(result.profile_digests),
        "compared_profiles": list(REQUIRED_PROFILE_IDS),
        "baseline_core_digest": result.baseline_digest,
        "generated_core_digest": result.generated_digest,
        "profile_digests": result.profile_digests,
        "html_byte_match": result.html_byte_match,
        "report_is_source_of_truth": False,
    }


def write_report(generated_package_dir: Path, result: ComparisonResult) -> Path:
    report_path = generated_package_dir / "data" / "regeneration_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report_payload(result), ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return report_path


def _validate_profile_registry(package_dir: Path, generated_core: dict[str, Any]) -> list[str]:
    registry = _read_json(package_dir / "data" / "profile_registry.json")
    issues: list[str] = []
    if registry.get("package_status") != "external_data_evaluated":
        issues.append("registry package status mismatch")
    if registry.get("required_profiles") != list(REQUIRED_PROFILE_IDS):
        issues.append("registry required profiles mismatch")
    profiles = registry.get("profiles")
    if not isinstance(profiles, list) or [item.get("profile_id") for item in profiles if isinstance(item, dict)] != list(REQUIRED_PROFILE_IDS):
        issues.append("registry profile order mismatch")
        return issues
    summary_by_id = {item["profile_id"]: item for item in generated_core["summary"]["profile_summaries"]}
    for item in profiles:
        if not isinstance(item, dict):
            issues.append("registry profile must be object")
            continue
        summary = summary_by_id.get(item.get("profile_id"))
        if not summary:
            issues.append("registry profile missing from summary")
            continue
        for key in ("repo_id", "resolved_revision", "source_file", "robot_type", "license", "row_count", "observation_state_dim", "action_dim", "trainer_smoke_passed"):
            if item.get(key) != summary.get(key):
                issues.append(f"registry {item.get('profile_id')} {key} mismatch")
        revision = item.get("resolved_revision")
        if not isinstance(revision, str) or len(revision) != 40:
            issues.append(f"registry {item.get('profile_id')} revision must be pinned")
        if item.get("full_lerobot_parser_claimed") is not False:
            issues.append(f"registry {item.get('profile_id')} parser claim must be false")
        if item.get("full_dataset_evaluation_claimed") is not False:
            issues.append(f"registry {item.get('profile_id')} dataset claim must be false")
    if registry.get("new_profile_added") is not False:
        issues.append("registry new_profile_added must be false")
    if registry.get("upstream_rederivation_claimed") is not False:
        issues.append("registry upstream_rederivation_claimed must be false")
    return issues


def _html_byte_match(package_dir: Path) -> bool:
    top_level = package_dir / "buyer_report.html"
    canonical = package_dir / "data" / "reports" / "buyer_report.html"
    return top_level.is_file() and canonical.is_file() and top_level.read_bytes() == canonical.read_bytes()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: JSON root must be object")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"{path}: JSONL row must be object")
        rows.append(payload)
    return rows


def _digest(payload: Any) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-package-dir", type=Path, required=True)
    parser.add_argument("--generated-package-dir", type=Path, required=True)
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = compare_packages(
        baseline_package_dir=args.baseline_package_dir,
        generated_package_dir=args.generated_package_dir,
    )
    report = report_payload(result)
    if args.write_report:
        report["report_path"] = str(write_report(args.generated_package_dir, result))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    else:
        print("regeneration_comparison=PASS" if result.passed else "regeneration_comparison=FAIL")
        if result.issues:
            for issue in result.issues[:8]:
                print(issue)
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
