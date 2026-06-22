#!/usr/bin/env python3
"""Independent verifier for MVP-3B source-adapter matrix proof packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REQUIRED_ADAPTERS = (
    "franka_research_arm",
    "robotis_sh5_ros2_dds",
    "universal_robots_ur_industrial_arm",
)

REQUIRED_ACTION_ROLES = (
    "teleop_intent",
    "executed_control",
    "learning_action",
    "retargeted_robot_action",
)

EXACT_SPENT_NO_REUSE = [[40000, 40049], [42000, 42049]]

OPENED_RANGE_KEYS = ("calibration", "heldout", "tuning", "closure")

CANONICAL_FORBIDDEN_CLAIMS = (
    "real_robot_success",
    "real_robot_success_claimed",
    "physical_robot_readiness",
    "physical_robot_readiness_claimed",
    "deployable_policy_readiness",
    "visual_policy_performance",
    "hmd_openxr_collection_readiness",
    "hmd_readiness",
    "hmd_readiness_claimed",
    "marketplace_readiness",
    "marketplace_readiness_claimed",
    "production_certification",
    "universal_robot_support",
    "universal_robot_support_claimed",
    "policy_uplift",
    "policy_uplift_claimed",
    "learning_proven_value",
    "live_runtime_support",
    "live_runtime_support_claimed",
    "live_ur_runtime_support",
    "live_ros2_dds_runtime_support",
    "franka_hardware_support",
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

TEXT_CLAIM_SUFFIXES = (".md", ".txt")

FORBIDDEN_TEXT_CLAIM_PHRASES = (
    "real robot success",
    "physical robot readiness",
    "deployable policy readiness",
    "visual policy performance",
    "hmd openxr collection readiness",
    "hmd readiness",
    "marketplace readiness",
    "production certification",
    "universal robot support",
    "policy uplift",
    "learning proven value",
    "live runtime support",
    "live ur runtime support",
    "live ros2 dds runtime support",
    "franka hardware support",
    "public sample import",
    "public sample evidence",
    "db migration",
    "production auth",
    "real robot readiness",
    "production robot support",
)

TEXT_CLAIM_POSITIVE_MARKERS = (
    "claim",
    "claims",
    "claimed",
    "claiming",
    "prove",
    "proves",
    "proved",
    "support",
    "supports",
    "supported",
    "ready",
    "readiness",
    "success",
)

TEXT_CLAIM_NEGATED_MARKERS = (
    "does not claim",
    "do not claim",
    "doesn't claim",
    "don't claim",
    "not claim",
    "no claim",
    "not supported",
    "unsupported",
    "does not support",
    "do not support",
    "doesn't support",
    "don't support",
    "not ready",
    "no ",
    "without ",
)

EXPECTED_CONTRACT_SOURCE = {
    "input_device": "recorded_command_state_fixture",
    "runtime": "generated_or_file_backed_recorded_log_fixture",
    "simulator": "none_recorded_log_projection",
    "task_name": "mvp3b_source_adapter_matrix",
}


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    details: str = ""


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)
    recomputed: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def exit_code(self) -> int:
        return 0 if self.ok else 1

    def failures(self) -> list[Check]:
        return [check for check in self.checks if not check.passed]


class Auditor:
    def __init__(self, manifest_path: Path) -> None:
        self.manifest_path = manifest_path
        self.package_root = manifest_path.parent
        self.data_root = self.package_root / "data"
        self.manifest: dict[str, Any] = {}
        self.artifact_index: dict[str, Any] = {}
        self.indexed_paths: set[str] = set()
        self.recomputed: dict[str, Any] = {
            "status": "source_adapter_infrastructure_closed",
            "adapters": [],
            "accepted_count": 0,
            "rejected_count": 0,
            "adapter_counts": {},
        }

    def run(self) -> Report:
        checks: list[Check] = []
        checks.append(self._check_hash_integrity())
        checks.append(self._check_data_coverage())
        checks.append(self._check_adapter_set_exactness())
        checks.append(self._check_source_log_completeness())
        checks.append(self._check_metadata_profile_consistency())
        checks.append(self._check_source_projection_hash_binding())
        checks.append(self._check_accepted_rejected_counts())
        checks.append(self._check_contract_source_fields())
        checks.append(self._check_contract_action_roles())
        checks.append(self._check_frame_action_role_coverage())
        checks.append(self._check_non_claims_false())
        checks.append(self._check_forbidden_claims())
        checks.append(self._check_spent_no_reuse_exact())
        checks.append(self._check_opened_ranges_empty())
        checks.append(self._check_learning_proven_addendum_absent())
        checks.append(self._check_summary_cache_consistency())
        return Report(checks=checks, recomputed=self.recomputed)

    def _check_hash_integrity(self) -> Check:
        try:
            self.manifest = _read_json(self.manifest_path)
            manifest_entries = self._manifest_entries()
            manifest_failures = self._verify_entries(manifest_entries)

            artifact_index_path = self.package_root / "data" / "artifact_index.json"
            self.artifact_index = _read_json(artifact_index_path)
            artifact_entries = self._artifact_entries()
            artifact_failures = self._verify_entries(artifact_entries)
            self.indexed_paths = {entry["data_path"] for entry in artifact_entries}

            failures = manifest_failures + artifact_failures
            if failures:
                return Check("hash_integrity", False, "; ".join(failures[:5]))
            return Check("hash_integrity", True)
        except Exception as exc:
            return Check("hash_integrity", False, f"{type(exc).__name__}: {exc}")

    def _check_data_coverage(self) -> Check:
        try:
            if not self.data_root.exists():
                return Check("data_coverage", False, "missing data/")
            data_files = {
                path.relative_to(self.package_root).as_posix()
                for path in self.data_root.rglob("*")
                if path.is_file()
            }
            manifest_paths = {entry["data_path"] for entry in self._manifest_entries()}
            artifact_paths = {entry["data_path"] for entry in self._artifact_entries()}
            unindexed = sorted(data_files - manifest_paths - artifact_paths)
            missing_from_manifest = sorted(data_files - manifest_paths)
            internal_artifact_required = data_files - {"data/artifact_index.json"}
            missing_from_artifact = sorted(internal_artifact_required - artifact_paths)
            if unindexed or missing_from_manifest or missing_from_artifact:
                details = []
                if unindexed:
                    details.append(f"unindexed={unindexed}")
                if missing_from_manifest:
                    details.append(f"missing_manifest={missing_from_manifest}")
                if missing_from_artifact:
                    details.append(f"missing_artifact_index={missing_from_artifact}")
                return Check("data_coverage", False, "; ".join(details))
            return Check("data_coverage", True)
        except Exception as exc:
            return Check("data_coverage", False, f"{type(exc).__name__}: {exc}")

    def _check_adapter_set_exactness(self) -> Check:
        try:
            registry = self._data_json("adapter_registry_snapshot.json")
            adapters = [
                item.get("adapter_id")
                for item in registry.get("adapters", [])
                if isinstance(item, dict)
            ]
            self.recomputed["adapters"] = adapters
            config = self._data_json("config.json")
            required = config.get("required_adapters")
            if adapters != list(REQUIRED_ADAPTERS):
                return Check("adapter_set_exactness", False, f"adapters={adapters}")
            if required != list(REQUIRED_ADAPTERS):
                return Check("adapter_set_exactness", False, f"required_adapters={required}")
            return Check("adapter_set_exactness", True)
        except Exception as exc:
            return Check("adapter_set_exactness", False, f"{type(exc).__name__}: {exc}")

    def _check_source_log_completeness(self) -> Check:
        try:
            failures: list[str] = []
            for adapter_id in REQUIRED_ADAPTERS:
                source_dir = self.data_root / "source_logs" / adapter_id
                metadata = _read_json(source_dir / "metadata.json")
                if metadata.get("adapter_id") != adapter_id:
                    failures.append(f"{adapter_id}: metadata adapter mismatch")
                accepted = _read_jsonl(source_dir / "accepted_command_state.jsonl")
                rejected = _read_jsonl(source_dir / "rejected_command_state.jsonl")
                if not accepted:
                    failures.append(f"{adapter_id}: missing accepted rows")
                if not rejected:
                    failures.append(f"{adapter_id}: missing rejected rows")
                for row in accepted:
                    if row.get("adapter_id") != adapter_id or row.get("accepted") is not True:
                        failures.append(f"{adapter_id}: invalid accepted row")
                for row in rejected:
                    if row.get("adapter_id") != adapter_id or row.get("accepted") is not False:
                        failures.append(f"{adapter_id}: invalid rejected row")
                projection_manifest = self._projection_manifest(adapter_id)
                source_logs = projection_manifest.get("source_logs", {})
                for filename, rows in (
                    ("accepted_command_state.jsonl", accepted),
                    ("rejected_command_state.jsonl", rejected),
                ):
                    entry = source_logs.get(filename, {})
                    expected_path = source_dir / filename
                    if entry.get("sha256") != _sha256(expected_path):
                        failures.append(f"{adapter_id}: {filename} source hash mismatch")
                    if entry.get("rows") != len(rows):
                        failures.append(f"{adapter_id}: {filename} row count mismatch")
            if failures:
                return Check("source_log_completeness", False, "; ".join(failures[:8]))
            return Check("source_log_completeness", True)
        except Exception as exc:
            return Check("source_log_completeness", False, f"{type(exc).__name__}: {exc}")

    def _check_metadata_profile_consistency(self) -> Check:
        try:
            config = self._data_json("config.json")
            profile = config.get("source_evidence_level")
            registry = self._data_json("adapter_registry_snapshot.json")
            registry_by_adapter = {
                item.get("adapter_id"): item
                for item in registry.get("adapters", [])
                if isinstance(item, dict)
            }
            failures: list[str] = []
            for adapter_id in REQUIRED_ADAPTERS:
                metadata = self._source_metadata(adapter_id)
                registry_entry = registry_by_adapter.get(adapter_id, {})
                if metadata.get("source_profile") != profile:
                    failures.append(f"{adapter_id}: source_profile mismatch")
                if metadata.get("robot_family") != registry_entry.get("robot_family"):
                    failures.append(f"{adapter_id}: robot_family mismatch")
                if registry_entry.get("runtime") != "recorded_log_fixture":
                    failures.append(f"{adapter_id}: registry runtime mismatch")
                if metadata.get("runtime") != "recorded_log_fixture":
                    failures.append(f"{adapter_id}: metadata runtime mismatch")
            if failures:
                return Check("metadata_profile_consistency", False, "; ".join(failures))
            return Check("metadata_profile_consistency", True)
        except Exception as exc:
            return Check("metadata_profile_consistency", False, f"{type(exc).__name__}: {exc}")

    def _check_source_projection_hash_binding(self) -> Check:
        try:
            failures: list[str] = []
            for adapter_id in REQUIRED_ADAPTERS:
                projection_manifest = self._projection_manifest(adapter_id)
                for rel_path, expected_hash in projection_manifest.get(
                    "projected_artifacts", {}
                ).items():
                    path = self.data_root / "projections" / adapter_id / rel_path
                    if not path.exists():
                        failures.append(f"{adapter_id}: missing projection {rel_path}")
                    elif _sha256(path) != expected_hash:
                        failures.append(f"{adapter_id}: projection hash mismatch {rel_path}")
            if failures:
                return Check("source_projection_hash_binding", False, "; ".join(failures))
            return Check("source_projection_hash_binding", True)
        except Exception as exc:
            return Check(
                "source_projection_hash_binding",
                False,
                f"{type(exc).__name__}: {exc}",
            )

    def _check_accepted_rejected_counts(self) -> Check:
        try:
            failures: list[str] = []
            total_accepted = 0
            total_rejected = 0
            adapter_counts: dict[str, dict[str, int]] = {}
            for adapter_id in REQUIRED_ADAPTERS:
                accepted = _read_jsonl(
                    self.data_root
                    / "source_logs"
                    / adapter_id
                    / "accepted_command_state.jsonl"
                )
                rejected = _read_jsonl(
                    self.data_root
                    / "source_logs"
                    / adapter_id
                    / "rejected_command_state.jsonl"
                )
                accepted_count = len(accepted)
                rejected_count = len(rejected)
                total_accepted += accepted_count
                total_rejected += rejected_count
                adapter_counts[adapter_id] = {
                    "accepted_count": accepted_count,
                    "rejected_count": rejected_count,
                }
                projection_manifest = self._projection_manifest(adapter_id)
                curation = self._projection_json(adapter_id, "curation_manifest.json")
                result = self._data_json(f"adapter_results/{adapter_id}_adapter_result.json")
                for label, payload in (
                    ("projection_manifest", projection_manifest),
                    ("curation_manifest", curation),
                    ("adapter_result", result),
                ):
                    if payload.get("accepted_count") != accepted_count:
                        failures.append(f"{adapter_id}: {label} accepted_count mismatch")
                    if payload.get("rejected_count") != rejected_count:
                        failures.append(f"{adapter_id}: {label} rejected_count mismatch")
            self.recomputed["accepted_count"] = total_accepted
            self.recomputed["rejected_count"] = total_rejected
            self.recomputed["adapter_counts"] = adapter_counts
            if failures:
                return Check("accepted_rejected_counts", False, "; ".join(failures))
            return Check("accepted_rejected_counts", True)
        except Exception as exc:
            return Check("accepted_rejected_counts", False, f"{type(exc).__name__}: {exc}")

    def _check_contract_source_fields(self) -> Check:
        try:
            failures: list[str] = []
            for adapter_id in REQUIRED_ADAPTERS:
                contract = self._contract(adapter_id)
                source = contract.get("source", {})
                for key, expected in EXPECTED_CONTRACT_SOURCE.items():
                    if source.get(key) != expected:
                        failures.append(f"{adapter_id}: source.{key}={source.get(key)!r}")
                if source.get("robot") != adapter_id:
                    failures.append(f"{adapter_id}: source.robot={source.get('robot')!r}")
                if contract.get("adapter_id") != adapter_id:
                    failures.append(f"{adapter_id}: contract adapter mismatch")
            if failures:
                return Check("contract_source_fields", False, "; ".join(failures))
            return Check("contract_source_fields", True)
        except Exception as exc:
            return Check("contract_source_fields", False, f"{type(exc).__name__}: {exc}")

    def _check_contract_action_roles(self) -> Check:
        try:
            failures: list[str] = []
            required_roles = list(REQUIRED_ACTION_ROLES)
            for adapter_id in REQUIRED_ADAPTERS:
                contract = self._contract(adapter_id)
                if contract.get("required_action_roles") != required_roles:
                    failures.append(f"{adapter_id}: required_action_roles mismatch")
                coverage = contract.get("frame_action_role_coverage", {})
                for role in REQUIRED_ACTION_ROLES:
                    role_coverage = coverage.get(role, {})
                    if role_coverage.get("present") is not True:
                        failures.append(f"{adapter_id}: {role} not present in contract")
                    if not isinstance(role_coverage.get("frames"), int):
                        failures.append(f"{adapter_id}: {role} frame count missing")
                result = self._data_json(f"adapter_results/{adapter_id}_adapter_result.json")
                if result.get("required_action_roles_present") != required_roles:
                    failures.append(f"{adapter_id}: adapter_result roles mismatch")
            if failures:
                return Check("contract_action_roles", False, "; ".join(failures))
            return Check("contract_action_roles", True)
        except Exception as exc:
            return Check("contract_action_roles", False, f"{type(exc).__name__}: {exc}")

    def _check_frame_action_role_coverage(self) -> Check:
        try:
            failures: list[str] = []
            for adapter_id in REQUIRED_ADAPTERS:
                rows = []
                rows.extend(
                    _read_jsonl(
                        self.data_root
                        / "source_logs"
                        / adapter_id
                        / "accepted_command_state.jsonl"
                    )
                )
                rows.extend(
                    _read_jsonl(
                        self.data_root
                        / "source_logs"
                        / adapter_id
                        / "rejected_command_state.jsonl"
                    )
                )
                for index, row in enumerate(rows):
                    actions = row.get("command_state", {}).get("actions_by_role", {})
                    missing = [role for role in REQUIRED_ACTION_ROLES if role not in actions]
                    if missing:
                        failures.append(f"{adapter_id}: row {index} missing {missing}")
                expected_counts = _frame_action_role_counts(rows)
                contract_coverage = self._contract(adapter_id).get(
                    "frame_action_role_coverage", {}
                )
                for role in REQUIRED_ACTION_ROLES:
                    count = expected_counts[role]
                    role_coverage = contract_coverage.get(role, {})
                    if role not in contract_coverage:
                        continue
                    if role_coverage.get("present") is not (count > 0):
                        failures.append(
                            f"{adapter_id}: {role} present="
                            f"{role_coverage.get('present')!r}, expected={count > 0!r}"
                        )
                    if role_coverage.get("frames") != count:
                        failures.append(
                            f"{adapter_id}: {role} frames="
                            f"{role_coverage.get('frames')!r}, expected={count}"
                        )
            if failures:
                return Check("frame_action_role_coverage", False, "; ".join(failures[:8]))
            return Check("frame_action_role_coverage", True)
        except Exception as exc:
            return Check("frame_action_role_coverage", False, f"{type(exc).__name__}: {exc}")

    def _check_non_claims_false(self) -> Check:
        try:
            config = self._data_json("config.json")
            attestation = self._data_json("non_claims_attestation.json")
            config_keys = set(config.get("non_claims", {}).keys())
            attestation_keys = set(attestation.get("forbidden_claims", {}).keys())
            canonical = set(CANONICAL_FORBIDDEN_CLAIMS)
            contract_smoke = config.get("contract_smoke", {})
            failures: list[str] = []
            if config_keys != canonical:
                failures.append("config non_claims keys are not canonical")
            if attestation_keys != canonical:
                failures.append("attestation forbidden_claims keys are not canonical")
            for key in ("learning_results_measured", "policy_uplift", "learning_proven_value"):
                if contract_smoke.get(key) is not False:
                    failures.append(f"contract_smoke.{key} must be false")
            if failures:
                return Check("non_claims_false", False, "; ".join(failures))
            return Check("non_claims_false", True)
        except Exception as exc:
            return Check("non_claims_false", False, f"{type(exc).__name__}: {exc}")

    def _check_forbidden_claims(self) -> Check:
        try:
            failures: list[str] = []
            for path in self._package_surface_files():
                if path.suffix.lower() == ".json":
                    payload = _read_json(path)
                elif path.suffix.lower() == ".jsonl":
                    payload = _read_jsonl(path)
                else:
                    if path.suffix.lower() in TEXT_CLAIM_SUFFIXES:
                        rel = path.relative_to(self.package_root).as_posix()
                        failures.extend(
                            f"{rel}:{phrase}" for phrase in _forbidden_text_claims(path)
                        )
                    continue
                rel = path.relative_to(self.package_root).as_posix()
                for dotted_path, value in _walk_claim_keys(payload):
                    if value is not False:
                        failures.append(f"{rel}:{dotted_path}={value!r}")
            if failures:
                return Check("forbidden_claims", False, "; ".join(failures[:8]))
            return Check("forbidden_claims", True)
        except Exception as exc:
            return Check("forbidden_claims", False, f"{type(exc).__name__}: {exc}")

    def _check_spent_no_reuse_exact(self) -> Check:
        try:
            config = self._data_json("config.json")
            if config.get("spent_no_reuse") != EXACT_SPENT_NO_REUSE:
                return Check(
                    "spent_no_reuse_exact",
                    False,
                    f"spent_no_reuse={config.get('spent_no_reuse')!r}",
                )
            return Check("spent_no_reuse_exact", True)
        except Exception as exc:
            return Check("spent_no_reuse_exact", False, f"{type(exc).__name__}: {exc}")

    def _check_opened_ranges_empty(self) -> Check:
        try:
            config = self._data_json("config.json")
            opened_ranges = config.get("opened_ranges", {})
            failures = [
                key
                for key in OPENED_RANGE_KEYS
                if opened_ranges.get(key) not in ([], None)
            ]
            missing = [key for key in OPENED_RANGE_KEYS if key not in opened_ranges]
            if failures or missing:
                return Check(
                    "opened_ranges_empty",
                    False,
                    f"non_empty={failures}; missing={missing}",
                )
            return Check("opened_ranges_empty", True)
        except Exception as exc:
            return Check("opened_ranges_empty", False, f"{type(exc).__name__}: {exc}")

    def _check_learning_proven_addendum_absent(self) -> Check:
        try:
            config = self._data_json("config.json")
            if config.get("learning_proven_addendum") != "absent":
                return Check(
                    "learning_proven_addendum_absent",
                    False,
                    f"learning_proven_addendum={config.get('learning_proven_addendum')!r}",
                )
            return Check("learning_proven_addendum_absent", True)
        except Exception as exc:
            return Check(
                "learning_proven_addendum_absent",
                False,
                f"{type(exc).__name__}: {exc}",
            )

    def _check_summary_cache_consistency(self) -> Check:
        try:
            summary = self._data_json("source_adapter_matrix_summary.json")
            adapter_counts = self.recomputed.get("adapter_counts", {})
            failures: list[str] = []
            expected = {
                "status": "source_adapter_infrastructure_closed",
                "adapter_count": len(REQUIRED_ADAPTERS),
                "required_adapter_count": len(REQUIRED_ADAPTERS),
                "accepted_count": self.recomputed.get("accepted_count"),
                "rejected_count": self.recomputed.get("rejected_count"),
            }
            for key, value in expected.items():
                if summary.get(key) != value:
                    failures.append(f"{key}={summary.get(key)!r}, expected={value!r}")
            if summary.get("adapters") != adapter_counts:
                failures.append("adapters count map mismatch")
            if summary.get("cached_summary_only") is not True:
                failures.append("cached_summary_only must be true")
            if failures:
                return Check("summary_cache_consistency", False, "; ".join(failures))
            return Check("summary_cache_consistency", True)
        except Exception as exc:
            return Check(
                "summary_cache_consistency",
                False,
                f"{type(exc).__name__}: {exc}",
            )

    def _manifest_entries(self) -> list[dict[str, Any]]:
        entries = self.manifest.get("artifact_index", [])
        if not isinstance(entries, list):
            raise ValueError("package_manifest artifact_index must be a list")
        return entries

    def _artifact_entries(self) -> list[dict[str, Any]]:
        entries = self.artifact_index.get("artifact_index", [])
        if not isinstance(entries, list):
            raise ValueError("data/artifact_index.json artifact_index must be a list")
        return entries

    def _verify_entries(self, entries: list[dict[str, Any]]) -> list[str]:
        failures: list[str] = []
        for entry in entries:
            if not isinstance(entry, dict):
                failures.append("artifact entry is not an object")
                continue
            rel_path = entry.get("data_path")
            expected_hash = entry.get("file_sha256")
            if not isinstance(rel_path, str) or not isinstance(expected_hash, str):
                failures.append(f"invalid artifact entry={entry!r}")
                continue
            path = self.package_root / rel_path
            if not path.exists():
                failures.append(f"missing {rel_path}")
            elif _sha256(path) != expected_hash:
                failures.append(f"sha256 mismatch {rel_path}")
        return failures

    def _data_json(self, rel_path: str) -> dict[str, Any]:
        return _read_json(self.data_root / rel_path)

    def _projection_json(self, adapter_id: str, rel_path: str) -> dict[str, Any]:
        return _read_json(self.data_root / "projections" / adapter_id / rel_path)

    def _projection_manifest(self, adapter_id: str) -> dict[str, Any]:
        return self._projection_json(adapter_id, "projection_manifest.json")

    def _source_metadata(self, adapter_id: str) -> dict[str, Any]:
        return _read_json(self.data_root / "source_logs" / adapter_id / "metadata.json")

    def _contract(self, adapter_id: str) -> dict[str, Any]:
        return self._data_json(
            f"contracts/{adapter_id}_normalized_trajectory_contract.json"
        )

    def _package_surface_files(self) -> list[Path]:
        paths = [self.manifest_path]
        paths.extend(path for path in self.package_root.iterdir() if path.is_file())
        if self.data_root.exists():
            paths.extend(path for path in self.data_root.rglob("*") if path.is_file())
        return sorted(set(paths))


def verify_package(manifest_path: Path) -> Report:
    return Auditor(manifest_path).run()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    decoder = json.JSONDecoder()
    body = path.read_text(encoding="utf-8")
    index = 0
    row_number = 0
    while index < len(body):
        while index < len(body) and body[index].isspace():
            index += 1
        if index >= len(body):
            break
        payload, index = decoder.raw_decode(body, index)
        row_number += 1
        if not isinstance(payload, dict):
            raise ValueError(f"{path}:row {row_number} must contain a JSON object")
        rows.append(payload)
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frame_action_role_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {role: 0 for role in REQUIRED_ACTION_ROLES}
    for row in rows:
        actions = row.get("command_state", {}).get("actions_by_role", {})
        for role in REQUIRED_ACTION_ROLES:
            if role in actions:
                counts[role] += 1
    return counts


def _walk_claim_keys(payload: Any, prefix: str = "") -> list[tuple[str, Any]]:
    found: list[tuple[str, Any]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            dotted = f"{prefix}.{key}" if prefix else str(key)
            if key in CANONICAL_FORBIDDEN_CLAIMS:
                found.append((dotted, value))
            found.extend(_walk_claim_keys(value, dotted))
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            dotted = f"{prefix}[{index}]"
            found.extend(_walk_claim_keys(item, dotted))
    return found


def _forbidden_text_claims(path: Path) -> list[str]:
    text = _normalize_claim_text(path.read_text(encoding="utf-8"))
    failures: list[str] = []
    for phrase in FORBIDDEN_TEXT_CLAIM_PHRASES:
        start = text.find(phrase)
        while start != -1:
            if _is_positive_claim_context(text, phrase, start):
                failures.append(phrase)
                break
            start = text.find(phrase, start + len(phrase))
    return failures


def _normalize_claim_text(text: str) -> str:
    normalized = text.lower().replace("-", " ").replace("_", " ")
    return " ".join(normalized.split())


def _is_positive_claim_context(text: str, phrase: str, start: int) -> bool:
    prefix = _local_claim_prefix(text, start)
    context = prefix + phrase
    if any(marker in prefix for marker in TEXT_CLAIM_NEGATED_MARKERS):
        return False
    return any(marker in context for marker in TEXT_CLAIM_POSITIVE_MARKERS)


def _local_claim_prefix(text: str, start: int) -> str:
    prefix = text[max(0, start - 240) : start]
    boundary = max(prefix.rfind(separator) for separator in (".", "!", "?", ";"))
    for marker in (", but ", " but ", ", however ", " however "):
        boundary = max(boundary, prefix.rfind(marker))
    if boundary == -1:
        return prefix
    return prefix[boundary + 1 :]


def _format_report(report: Report) -> str:
    status = "VERIFIED" if report.ok else "FAILED"
    lines = [f"VERDICT: {status}"]
    for check in report.checks:
        result = "PASS" if check.passed else "FAIL"
        suffix = f" - {check.details}" if check.details else ""
        lines.append(f"{result}: {check.name}{suffix}")
    lines.append("RECOMPUTED:")
    lines.append(json.dumps(report.recomputed, ensure_ascii=False, sort_keys=True, indent=2))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify an MVP-3B source-adapter matrix proof package without importing "
            "producer services."
        )
    )
    parser.add_argument("manifest_path", type=Path, help="Path to package_manifest.json")
    args = parser.parse_args(argv)

    report = verify_package(args.manifest_path)
    print(_format_report(report))
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
