#!/usr/bin/env python3
"""Independent verifier for the LeRobot public ALOHA audited-slice package."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from pathlib import PurePosixPath
import struct
import tempfile
from typing import Any, cast
from urllib.request import urlopen


RAW_ROW_SCHEMA_VERSION = "rdf_public_lerobot_raw_row_v0.1.0"
CONVERTED_ROW_SCHEMA_VERSION = "rdf_public_lerobot_state_action_row_v0.1.0"
CANONICAL_ROW_DIGEST_ALGORITHM = "json.dumps(sort_keys=True,separators=(',',':'),ensure_ascii=False)+sha256"
# This verifier is intentionally for the ALOHA public audited-slice profile only.
# A second LeRobot dataset should introduce an explicit slice profile instead of
# weakening these constants into implicit generic support.
EXPECTED_REPO_ID = "lerobot/aloha_static_coffee"
EXPECTED_SOURCE_FILE = "data/chunk-000/file-000.parquet"
EXPECTED_ROBOT_TYPE = "aloha"
EXPECTED_EPISODE_INDEX = 0
EXPECTED_FRAME_START = 0
EXPECTED_FRAME_COUNT = 8
EXPECTED_SLICE_RULE = {
    "slice_rule": "first_episode_first_n_frames",
    "episode_index": EXPECTED_EPISODE_INDEX,
    "frame_start": EXPECTED_FRAME_START,
    "frame_count": EXPECTED_FRAME_COUNT,
}
SPENT_RANGES = ((40000, 40049), (42000, 42049))
REQUIRED_FILES = {
    "data/source/public_source_binding.json",
    "data/source/upstream_file_hashes.json",
    "data/source/refetch_receipt.json",
    "data/source/extraction_receipt.json",
    "data/source/slice_selection_report.json",
    "data/source/lerobot_raw_rows.jsonl",
    "data/source/lerobot_feature_schema.json",
    "data/source/LICENSE.txt",
    "data/conversion/rdf_converted_rows.jsonl",
    "data/conversion/semantic_mapping_report.json",
    "data/conversion/conversion_manifest.json",
    "data/contracts/normalized_state_action_contract.json",
    "data/contracts/validator_report.json",
    "data/export/dataset.hdf5",
    "data/export/hdf5_inspection_report.json",
    "data/export/deep_hdf5_receipt.json",
    "data/export/trainer_smoke_report.json",
    "data/reports/buyer_data_evaluation_report.json",
    "data/non_claims_attestation.json",
    "data/config.json",
    "data/artifact_index.json",
}
NON_CLAIM_KEYS = {
    "full_lerobot_parser_support",
    "full_dataset_evaluation",
    "real_robot_success",
    "physical_robot_readiness",
    "live_hardware_support",
    "live_aloha_support",
    "live_ur_rtde_support",
    "live_franka_hardware_support",
    "live_ros2_dds_bridge_readiness",
    "visual_policy_performance",
    "policy_uplift",
    "learning_proven_value",
    "deployable_policy_readiness",
    "marketplace_readiness",
    "production_certification",
    "sim_to_real_proven",
    "general_robot_intelligence",
}
FORBIDDEN_FIELDS = {
    "end_effector_position",
    "end_effector_quaternion",
    "object_position",
    "object_quaternion",
    "robot_family_claimed",
    "robot_family",
    "ur_hardware_support",
    "franka_hardware_support",
    "ros2_bridge_support",
    "rtde_support",
    "task_success",
}
FORBIDDEN_TEXT_CLAIM_PHRASES = (
    "full lerobot parser support",
    "full dataset evaluation",
    "real robot success",
    "physical robot readiness",
    "live hardware support",
    "live aloha support",
    "live ur rtde support",
    "live franka hardware support",
    "live ros2 dds bridge readiness",
    "visual policy performance",
    "policy uplift",
    "learning proven value",
    "deployable policy readiness",
    "marketplace readiness",
    "production certification",
    "sim to real",
    "sim-to-real",
    "general robot intelligence",
)
NEGATION_MARKERS = (
    "does not claim",
    "do not claim",
    "not claim",
    "no claim",
    "does not prove",
    "do not prove",
    "not prove",
    "not supported",
    "does not support",
    "do not support",
    "no ",
    "without ",
    "not a ",
)


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


class Auditor:
    def __init__(self, manifest_path: Path, *, deep_hdf5: bool = False, refetch_public_source: bool = False, reextract_public_source: bool = False) -> None:
        self.manifest_path = manifest_path
        self.package_root = manifest_path.parent
        self.data_root = self.package_root / "data"
        self.deep_hdf5 = deep_hdf5
        self.refetch_public_source = refetch_public_source
        self.reextract_public_source = reextract_public_source
        self.manifest: dict[str, Any] = {}
        self.artifact_index: dict[str, Any] = {}
        self.binding: dict[str, Any] = {}
        self.upstream_hashes: dict[str, Any] = {}
        self.raw_rows: list[dict[str, Any]] = []
        self.converted_rows: list[dict[str, Any]] = []
        self.recomputed: dict[str, Any] = {}

    def run(self) -> Report:
        checks = [
            self._check_hash_integrity(),
            self._check_required_files(),
            self._check_public_source_binding(),
            self._check_refetch_receipt(),
            self._check_raw_rows(),
            self._check_extraction_receipt(),
            self._check_conversion_parity(),
            self._check_contract_and_reports(),
            self._check_hdf5_receipt_consistency(),
            self._check_non_claims(),
            self._check_forbidden_claims_and_spent_ranges(),
        ]
        if self.deep_hdf5:
            checks.append(self._check_deep_hdf5())
        if self.refetch_public_source:
            checks.append(self._check_refetch_public_source())
        if self.reextract_public_source:
            checks.append(self._check_reextract_public_source())
        return Report(checks=checks, recomputed=self.recomputed)

    def _check_hash_integrity(self) -> Check:
        try:
            self.manifest = _read_json(self.manifest_path)
            manifest_entries = self.manifest.get("artifact_index")
            if not isinstance(manifest_entries, list):
                return Check("hash_integrity", False, "package_manifest artifact_index must be list")
            failures = _verify_entries(self.package_root, manifest_entries)
            self.artifact_index = _read_json(self.data_root / "artifact_index.json")
            artifact_entries = self.artifact_index.get("artifact_index")
            if not isinstance(artifact_entries, list):
                return Check("hash_integrity", False, "data/artifact_index artifact_index must be list")
            failures.extend(_verify_entries(self.package_root, artifact_entries))
            if failures:
                return Check("hash_integrity", False, "; ".join(failures[:8]))
            return Check("hash_integrity", True)
        except Exception as exc:
            return Check("hash_integrity", False, f"{type(exc).__name__}: {exc}")

    def _check_required_files(self) -> Check:
        data_files = {
            path.relative_to(self.package_root).as_posix()
            for path in self.data_root.rglob("*")
            if path.is_file()
        }
        missing = sorted(REQUIRED_FILES - data_files)
        if missing:
            return Check("required_files", False, f"missing {missing}")
        extra_critical = [path for path in data_files if "storage/" in path or path.startswith("storage/")]
        if extra_critical:
            return Check("required_files", False, f"storage reference in data files: {extra_critical}")
        return Check("required_files", True)

    def _check_public_source_binding(self) -> Check:
        try:
            self.binding = _read_json(self.data_root / "source" / "public_source_binding.json")
            self.upstream_hashes = _read_json(self.data_root / "source" / "upstream_file_hashes.json")
            issues: list[str] = []
            if self.manifest.get("package_status") != "external_data_evaluated":
                issues.append("package_status must be external_data_evaluated")
            if self.manifest.get("external_source_included") is not True:
                issues.append("external_source_included must be true")
            if self.binding.get("repo_id") != EXPECTED_REPO_ID:
                issues.append("repo_id mismatch")
            revision = self.binding.get("resolved_revision")
            if not _commit_sha_shaped(revision):
                issues.append("resolved_revision must be a pinned 40-character lowercase commit sha")
            if self.binding.get("source_file") != EXPECTED_SOURCE_FILE:
                issues.append("source_file mismatch")
            if self.binding.get("license") != "mit":
                issues.append("license must be mit")
            if self.binding.get("dataset_card_robot_type") != EXPECTED_ROBOT_TYPE:
                issues.append("dataset_card_robot_type must be aloha")
            if self.binding.get("provenance_trust_tier") != "refetchable_public_source":
                issues.append("provenance_trust_tier mismatch")
            if self.binding.get("full_dataset_verdict_claimed") is not False:
                issues.append("full_dataset_verdict_claimed must be false")
            if self.binding.get("audited_slice_verdict_claimed") is not True:
                issues.append("audited_slice_verdict_claimed must be true")
            config = _read_json(self.data_root / "config.json")
            for label, payload in (("manifest", self.manifest), ("config", config), ("upstream_file_hashes", self.upstream_hashes)):
                if payload.get("repo_id") != self.binding.get("repo_id"):
                    issues.append(f"{label} repo_id mismatch")
                if payload.get("resolved_revision") != self.binding.get("resolved_revision"):
                    issues.append(f"{label} resolved_revision mismatch")
            files = self.upstream_hashes.get("files")
            if not isinstance(files, dict) or not files:
                issues.append("upstream_file_hashes.files must be non-empty object")
            else:
                required_upstream = {EXPECTED_SOURCE_FILE, "meta/info.json", "README.md"}
                if not required_upstream <= set(files):
                    issues.append("upstream hashes missing required source files")
                for name, meta in files.items():
                    if not isinstance(meta, dict) or not _sha256_shaped(meta.get("sha256")):
                        issues.append(f"{name}: sha256 missing or malformed")
                    elif str(self.binding.get("resolved_revision")) not in str(meta.get("source_url", "")):
                        issues.append(f"{name}: source_url is not bound to resolved_revision")
            return Check("public_source_binding", not issues, "; ".join(issues))
        except Exception as exc:
            return Check("public_source_binding", False, f"{type(exc).__name__}: {exc}")

    def _check_refetch_receipt(self) -> Check:
        try:
            receipt = _read_json(self.data_root / "source" / "refetch_receipt.json")
            files = self.upstream_hashes.get("files") if isinstance(self.upstream_hashes, dict) else {}
            issues: list[str] = []
            if receipt.get("repo_id") != self.binding.get("repo_id"):
                issues.append("repo_id mismatch")
            if receipt.get("resolved_revision") != self.binding.get("resolved_revision"):
                issues.append("resolved_revision mismatch")
            if receipt.get("matched") is not True:
                issues.append("receipt matched must be true")
            checked = receipt.get("files_checked")
            if not isinstance(checked, list) or not checked:
                issues.append("files_checked must be non-empty list")
            else:
                checked_paths = {item.get("path") for item in checked if isinstance(item, dict)}
                if checked_paths != set(cast(dict[str, Any], files)):
                    issues.append("refetch receipt checked paths differ from upstream files")
                for item in checked:
                    if not isinstance(item, dict):
                        issues.append("files_checked entry must be object")
                        continue
                    path = item.get("path")
                    meta = files.get(path) if isinstance(files, dict) else None
                    if not isinstance(meta, dict):
                        issues.append(f"{path}: missing upstream hash metadata")
                        continue
                    if item.get("declared_sha256") != meta.get("sha256"):
                        issues.append(f"{path}: declared sha mismatch")
                    if item.get("declared_sha256") != item.get("refetched_sha256"):
                        issues.append(f"{path}: refetched sha mismatch")
                    if item.get("matched") is not True:
                        issues.append(f"{path}: matched must be true")
                    if item.get("revision") != self.binding.get("resolved_revision"):
                        issues.append(f"{path}: revision mismatch")
            return Check("refetch_receipt", not issues, "; ".join(issues))
        except Exception as exc:
            return Check("refetch_receipt", False, f"{type(exc).__name__}: {exc}")

    def _check_raw_rows(self) -> Check:
        try:
            self.raw_rows = _read_jsonl(self.data_root / "source" / "lerobot_raw_rows.jsonl")
            slice_report = _read_json(self.data_root / "source" / "slice_selection_report.json")
            feature_schema = _read_json(self.data_root / "source" / "lerobot_feature_schema.json")
            issues = _validate_raw_rows(
                self.raw_rows,
                slice_report.get("slice_rule"),
                repo_id=self.binding.get("repo_id"),
                resolved_revision=self.binding.get("resolved_revision"),
                source_file=self.binding.get("source_file"),
            )
            if slice_report.get("source_file") != self.binding.get("source_file"):
                issues.append("slice_selection_report source_file mismatch")
            if slice_report.get("row_count") != len(self.raw_rows):
                issues.append("slice_selection_report row_count mismatch")
            if slice_report.get("raw_row_sha256s") != [_canonical_row_digest(row) for row in self.raw_rows]:
                issues.append("slice_selection_report raw_row_sha256s mismatch")
            if feature_schema.get("observation_state_dim") != 14:
                issues.append("feature_schema observation_state_dim must be 14")
            if feature_schema.get("action_dim") != 14:
                issues.append("feature_schema action_dim must be 14")
            self.recomputed.update(
                {
                    "row_count": len(self.raw_rows),
                    "observation_state_dim": len(self.raw_rows[0].get("observation.state", [])) if self.raw_rows else 0,
                    "action_dim": len(self.raw_rows[0].get("action", [])) if self.raw_rows else 0,
                }
            )
            return Check("raw_rows", not issues, "; ".join(issues))
        except Exception as exc:
            return Check("raw_rows", False, f"{type(exc).__name__}: {exc}")

    def _check_extraction_receipt(self) -> Check:
        try:
            receipt = _read_json(self.data_root / "source" / "extraction_receipt.json")
            feature_schema = _read_json(self.data_root / "source" / "lerobot_feature_schema.json")
            feature_schema_sha = _sha256_bytes(_canonical_json_bytes(feature_schema))
            raw_file_sha = _sha256_file(self.data_root / "source" / "lerobot_raw_rows.jsonl")
            issues: list[str] = []
            if receipt.get("repo_id") != self.binding.get("repo_id"):
                issues.append("repo_id mismatch")
            if receipt.get("resolved_revision") != self.binding.get("resolved_revision"):
                issues.append("resolved_revision mismatch")
            if receipt.get("source_file") != self.binding.get("source_file"):
                issues.append("source_file mismatch")
            if receipt.get("canonical_row_digest_algorithm") != CANONICAL_ROW_DIGEST_ALGORITHM:
                issues.append("canonical row digest algorithm mismatch")
            if receipt.get("extractor_implementation") != "independent_public_source_reextractor":
                issues.append("extractor implementation mismatch")
            if not receipt.get("reextract_command"):
                issues.append("missing reextract_command")
            if not isinstance(receipt.get("dependency_versions"), dict) or not receipt["dependency_versions"]:
                issues.append("missing dependency_versions")
            if receipt.get("feature_schema_sha256") != feature_schema_sha:
                issues.append("feature_schema_sha256 mismatch")
            source_file = self.binding.get("source_file")
            source_hash = self.upstream_hashes.get("files", {}).get(source_file, {}).get("sha256")
            if receipt.get("source_file_byte_sha256") != source_hash:
                issues.append("source_file_byte_sha256 mismatch")
            row_digests = [_canonical_row_digest(row) for row in self.raw_rows]
            if receipt.get("raw_row_sha256s") != row_digests:
                issues.append("raw_row_sha256s mismatch")
            if receipt.get("included_raw_jsonl_sha256") != raw_file_sha:
                issues.append("included raw jsonl sha mismatch")
            if receipt.get("reextracted_raw_jsonl_sha256") != raw_file_sha:
                issues.append("reextracted raw jsonl sha mismatch")
            if receipt.get("matched") is not True:
                issues.append("receipt matched must be true")
            return Check("extraction_receipt", not issues, "; ".join(issues))
        except Exception as exc:
            return Check("extraction_receipt", False, f"{type(exc).__name__}: {exc}")

    def _check_conversion_parity(self) -> Check:
        try:
            self.converted_rows = _read_jsonl(self.data_root / "conversion" / "rdf_converted_rows.jsonl")
            mapping_report = _read_json(self.data_root / "conversion" / "semantic_mapping_report.json")
            conversion_manifest = _read_json(self.data_root / "conversion" / "conversion_manifest.json")
            expected = [_convert_row(row, robot_type="aloha") for row in self.raw_rows]
            issues: list[str] = []
            if self.converted_rows != expected:
                issues.append("converted rows are not deterministic parity from raw rows")
            if mapping_report.get("fabricated_fields") != []:
                issues.append("semantic_mapping_report fabricated_fields must be empty")
            if mapping_report.get("canonical_source_rejected_examples_present") is not False:
                issues.append("canonical_source_rejected_examples_present must be false")
            if mapping_report.get("accepted_rejected_pair_claimed") is not False:
                issues.append("accepted_rejected_pair_claimed must be false")
            if conversion_manifest.get("input_raw_row_sha256s") != [_canonical_row_digest(row) for row in self.raw_rows]:
                issues.append("conversion_manifest input digests mismatch")
            if conversion_manifest.get("converted_row_sha256s") != [_sha256_bytes(_canonical_json_bytes(row)) for row in self.converted_rows]:
                issues.append("conversion_manifest converted digests mismatch")
            for index, row in enumerate(self.converted_rows):
                forbidden = _find_forbidden_fields(row)
                if forbidden:
                    issues.append(f"converted row {index} forbidden fields: {forbidden}")
            return Check("conversion_parity", not issues, "; ".join(issues))
        except Exception as exc:
            return Check("conversion_parity", False, f"{type(exc).__name__}: {exc}")

    def _check_contract_and_reports(self) -> Check:
        try:
            contract = _read_json(self.data_root / "contracts" / "normalized_state_action_contract.json")
            validator = _read_json(self.data_root / "contracts" / "validator_report.json")
            buyer = _read_json(self.data_root / "reports" / "buyer_data_evaluation_report.json")
            config = _read_json(self.data_root / "config.json")
            trainer = _read_json(self.data_root / "export" / "trainer_smoke_report.json")
            issues: list[str] = []
            row_count = len(self.converted_rows)
            state_dim = len(self.converted_rows[0]["observation_state"]) if self.converted_rows else 0
            action_dim = len(self.converted_rows[0]["learning_action"]) if self.converted_rows else 0
            for label, payload in (("contract", contract), ("validator", validator), ("buyer", buyer)):
                if payload.get("row_count") != row_count:
                    issues.append(f"{label} row_count mismatch")
            if validator.get("ok") is not True:
                issues.append("validator_report ok must be true")
            if contract.get("observation_state_dim") != state_dim or validator.get("observation_state_dim") != state_dim:
                issues.append("observation_state_dim mismatch")
            if contract.get("action_dim") != action_dim or validator.get("action_dim") != action_dim:
                issues.append("action_dim mismatch")
            if contract.get("visual_data_ignored") is not True:
                issues.append("contract visual_data_ignored must be true")
            if contract.get("camera_visual_policy_readiness") is not False:
                issues.append("camera_visual_policy_readiness must be false")
            if buyer.get("full_source_verdict_claimed") is not False:
                issues.append("buyer full_source_verdict_claimed must be false")
            if buyer.get("audited_slice_verdict_claimed") is not True:
                issues.append("buyer audited_slice_verdict_claimed must be true")
            if trainer.get("trainer") != "generic_state_action_trainer_smoke" or trainer.get("passed") is not True:
                issues.append("generic trainer smoke must pass")
            if config.get("package_status") != "external_data_evaluated":
                issues.append("config package_status mismatch")
            return Check("contract_reports", not issues, "; ".join(issues))
        except Exception as exc:
            return Check("contract_reports", False, f"{type(exc).__name__}: {exc}")

    def _check_hdf5_receipt_consistency(self) -> Check:
        try:
            receipt = _read_json(self.data_root / "export" / "deep_hdf5_receipt.json")
            hdf5_report = _read_json(self.data_root / "export" / "hdf5_inspection_report.json")
            hdf5_path = self.data_root / "export" / "dataset.hdf5"
            hdf5_bytes = hdf5_path.read_bytes()
            expected_state_blob = _float32_blob(self.converted_rows, "observation_state")
            expected_action_blob = _float32_blob(self.converted_rows, "learning_action")
            expected_state_hash = _sha256_bytes(expected_state_blob)
            expected_action_hash = _sha256_bytes(expected_action_blob)
            issues: list[str] = []
            if receipt.get("matched") is not True:
                issues.append("deep_hdf5_receipt matched must be true")
            if receipt.get("row_count") != len(self.converted_rows):
                issues.append("deep_hdf5_receipt row_count mismatch")
            if hdf5_report.get("passed") is not True:
                issues.append("hdf5 inspection must pass")
            if hdf5_report.get("hdf5_sha256") != _sha256_bytes(hdf5_bytes):
                issues.append("hdf5 inspection sha mismatch")
            if receipt.get("converted_row_sha256s") != [_sha256_bytes(_canonical_json_bytes(row)) for row in self.converted_rows]:
                issues.append("deep_hdf5_receipt converted row digest mismatch")
            if receipt.get("expected_observation_state_sha256") != expected_state_hash:
                issues.append("expected observation hash does not match converted rows")
            if receipt.get("expected_learning_action_sha256") != expected_action_hash:
                issues.append("expected action hash does not match converted rows")
            if receipt.get("hdf5_observation_state_sha256") != expected_state_hash:
                issues.append("deep_hdf5_receipt observation hash mismatch")
            if receipt.get("hdf5_learning_action_sha256") != expected_action_hash:
                issues.append("deep_hdf5_receipt action hash mismatch")
            if hdf5_bytes.count(expected_state_blob) != 1:
                issues.append("dataset.hdf5 does not contain the expected observation_state float32 payload exactly once")
            if hdf5_bytes.count(expected_action_blob) != 1:
                issues.append("dataset.hdf5 does not contain the expected learning_action float32 payload exactly once")
            return Check("hdf5_receipt_consistency", not issues, "; ".join(issues))
        except Exception as exc:
            return Check("hdf5_receipt_consistency", False, f"{type(exc).__name__}: {exc}")

    def _check_non_claims(self) -> Check:
        try:
            non_claims = _read_json(self.data_root / "non_claims_attestation.json").get("non_claims")
            buyer = _read_json(self.data_root / "reports" / "buyer_data_evaluation_report.json")
            config = _read_json(self.data_root / "config.json")
            issues: list[str] = []
            for label, claims in (("non_claims", non_claims), ("buyer", buyer.get("non_claims")), ("config", config.get("non_claims")), ("manifest", self.manifest.get("non_claims"))):
                if set(claims or {}) != NON_CLAIM_KEYS:
                    issues.append(f"{label} keys mismatch")
                if isinstance(claims, dict):
                    for key, value in claims.items():
                        if value is not False:
                            issues.append(f"{label} {key} must be false")
            return Check("non_claims", not issues, "; ".join(issues))
        except Exception as exc:
            return Check("non_claims", False, f"{type(exc).__name__}: {exc}")

    def _check_forbidden_claims_and_spent_ranges(self) -> Check:
        issues: list[str] = []
        for path in sorted(self.package_root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(self.package_root).as_posix()
            if path.suffix == ".json":
                payload = _read_json(path)
                _scan_forbidden_true_claims(payload, rel, issues)
                _scan_seed_values(payload, rel, issues)
                _scan_forbidden_text_values(payload, rel, issues)
            elif path.suffix == ".jsonl":
                for row in _read_jsonl(path):
                    _scan_forbidden_true_claims(row, rel, issues)
                    _scan_seed_values(row, rel, issues)
                    _scan_forbidden_text_values(row, rel, issues)
            elif path.suffix in {".md", ".txt"}:
                _scan_text(path.read_text(encoding="utf-8"), rel, issues)
        return Check("claim_and_spent_boundary", not issues, "; ".join(issues[:8]))

    def _check_deep_hdf5(self) -> Check:
        try:
            import h5py
            import numpy as np

            with h5py.File(self.data_root / "export" / "dataset.hdf5", "r") as h5:
                episode_id = h5["episodes/episode_ids"][0].decode("utf-8")
                states = np.asarray(h5[f"observations/{episode_id}/observation_state"][()], dtype=np.float32)
                actions = np.asarray(h5[f"actions/{episode_id}/learning_action"][()], dtype=np.float32)
            expected_states = np.asarray([row["observation_state"] for row in self.converted_rows], dtype=np.float32)
            expected_actions = np.asarray([row["learning_action"] for row in self.converted_rows], dtype=np.float32)
            if not np.array_equal(states, expected_states):
                return Check("deep_hdf5", False, "observation_state arrays mismatch")
            if not np.array_equal(actions, expected_actions):
                return Check("deep_hdf5", False, "learning_action arrays mismatch")
            return Check("deep_hdf5", True)
        except Exception as exc:
            return Check("deep_hdf5", False, f"{type(exc).__name__}: {exc}")

    def _check_refetch_public_source(self) -> Check:
        try:
            files = self.upstream_hashes.get("files", {})
            issues: list[str] = []
            for name, meta in files.items():
                expected = meta.get("sha256")
                actual = _sha256_bytes(_fetch_url(_hf_resolve_url(self.binding["repo_id"], self.binding["resolved_revision"], name)))
                if actual != expected:
                    issues.append(f"{name}: public refetch sha mismatch")
            return Check("refetch_public_source", not issues, "; ".join(issues))
        except Exception as exc:
            return Check("refetch_public_source", False, f"{type(exc).__name__}: {exc}")

    def _check_reextract_public_source(self) -> Check:
        try:
            import pyarrow.parquet as pq

            source_file = self.binding["source_file"]
            with tempfile.TemporaryDirectory(prefix="rdf_lerobot_reextract_") as tmp:
                path = Path(tmp) / "source.parquet"
                path.write_bytes(_fetch_url(_hf_resolve_url(self.binding["repo_id"], self.binding["resolved_revision"], source_file)))
                table = pq.read_table(
                    path,
                    columns=[
                        "episode_index",
                        "frame_index",
                        "timestamp",
                        "observation.state",
                        "action",
                        "next.done",
                        "index",
                        "task_index",
                    ],
                )
                rows = _extract_rows_from_pyarrow_table(
                    table,
                    repo_id=self.binding["repo_id"],
                    resolved_revision=self.binding["resolved_revision"],
                    source_file=source_file,
                )
            if [_canonical_row_digest(row) for row in rows] != [_canonical_row_digest(row) for row in self.raw_rows]:
                return Check("reextract_public_source", False, "re-extracted row digests mismatch")
            return Check("reextract_public_source", True)
        except Exception as exc:
            return Check("reextract_public_source", False, f"{type(exc).__name__}: {exc}")


def _verify_entries(package_root: Path, entries: list[Any]) -> list[str]:
    failures: list[str] = []
    seen: set[str] = set()
    data_root = (package_root / "data").resolve()
    for entry in entries:
        if not isinstance(entry, dict):
            failures.append("artifact entry must be object")
            continue
        data_path = entry.get("data_path")
        if not isinstance(data_path, str):
            failures.append("artifact data_path must be data-relative")
            continue
        parsed = PurePosixPath(data_path)
        if parsed.is_absolute() or parsed.parts[:1] != ("data",) or any(part in {"", ".", ".."} for part in parsed.parts):
            failures.append(f"{data_path}: artifact data_path must be normalized under data/")
            continue
        if data_path in seen:
            failures.append(f"{data_path}: duplicate artifact entry")
        seen.add(data_path)
        path = package_root / data_path
        try:
            resolved = path.resolve()
            if not resolved.is_relative_to(data_root):
                failures.append(f"{data_path}: artifact path escapes data/")
                continue
        except OSError as exc:
            failures.append(f"{data_path}: cannot resolve path: {exc}")
            continue
        if not path.exists():
            failures.append(f"{data_path}: missing")
            continue
        if entry.get("file_sha256") != _sha256_file(path):
            failures.append(f"{data_path}: sha256 mismatch")
        if entry.get("byte_size") != path.stat().st_size:
            failures.append(f"{data_path}: byte_size mismatch")
        if entry.get("hash_convention") != "file_bytes":
            failures.append(f"{data_path}: hash_convention mismatch")
    return failures


def _validate_raw_rows(
    rows: list[dict[str, Any]],
    slice_rule: Any,
    *,
    repo_id: Any,
    resolved_revision: Any,
    source_file: Any,
) -> list[str]:
    issues: list[str] = []
    if not isinstance(slice_rule, dict):
        return ["slice_rule must be object"]
    for key, expected in EXPECTED_SLICE_RULE.items():
        if slice_rule.get(key) != expected:
            issues.append(f"slice_rule {key} mismatch")
    if len(rows) != EXPECTED_FRAME_COUNT:
        issues.append("raw row count does not match slice frame_count")
    expected_frames = list(range(EXPECTED_FRAME_START, EXPECTED_FRAME_START + EXPECTED_FRAME_COUNT))
    previous_timestamp: float | None = None
    state_dim: int | None = None
    action_dim: int | None = None
    actual_frames: list[int] = []
    for index, row in enumerate(rows):
        if row.get("schema_version") != RAW_ROW_SCHEMA_VERSION:
            issues.append(f"row {index}: schema_version mismatch")
        if row.get("repo_id") != repo_id:
            issues.append(f"row {index}: repo_id mismatch")
        if row.get("resolved_revision") != resolved_revision:
            issues.append(f"row {index}: resolved_revision mismatch")
        if row.get("source_file") != source_file:
            issues.append(f"row {index}: source_file mismatch")
        if row.get("episode_index") != EXPECTED_EPISODE_INDEX:
            issues.append(f"row {index}: episode_index mismatch")
        if isinstance(row.get("frame_index"), int) and not isinstance(row.get("frame_index"), bool):
            actual_frames.append(row["frame_index"])
        else:
            issues.append(f"row {index}: frame_index must be int")
        timestamp = _float_or_none(row.get("timestamp"))
        if timestamp is None:
            issues.append(f"row {index}: timestamp must be numeric")
        elif previous_timestamp is not None and timestamp < previous_timestamp:
            issues.append(f"row {index}: timestamp is not monotonic")
        previous_timestamp = timestamp
        state = row.get("observation.state")
        action = row.get("action")
        if not _numeric_vector(state):
            issues.append(f"row {index}: observation.state must be numeric vector")
        else:
            state_values = cast(list[int | float], state)
            if state_dim is None:
                state_dim = len(state_values)
            elif len(state_values) != state_dim:
                issues.append(f"row {index}: observation.state dimension drift")
        if not _numeric_vector(action):
            issues.append(f"row {index}: action must be numeric vector")
        else:
            action_values = cast(list[int | float], action)
            if action_dim is None:
                action_dim = len(action_values)
            elif len(action_values) != action_dim:
                issues.append(f"row {index}: action dimension drift")
        if row.get("source_row_sha256") != _canonical_row_digest(row):
            issues.append(f"row {index}: source_row_sha256 mismatch")
    if actual_frames != expected_frames:
        issues.append(f"frame sequence mismatch: {actual_frames}")
    if state_dim != 14:
        issues.append(f"expected ALOHA observation.state dim 14, got {state_dim}")
    if action_dim != 14:
        issues.append(f"expected ALOHA action dim 14, got {action_dim}")
    return issues


def _convert_row(row: dict[str, Any], *, robot_type: str) -> dict[str, Any]:
    return {
        "schema_version": CONVERTED_ROW_SCHEMA_VERSION,
        "source_kind": "public_lerobot_dataset_slice",
        "source_robot_type": robot_type,
        "repo_id": row.get("repo_id"),
        "resolved_revision": row.get("resolved_revision"),
        "source_file": row.get("source_file"),
        "source_row_sha256": row.get("source_row_sha256"),
        "episode_index": row.get("episode_index"),
        "frame_index": row.get("frame_index"),
        "timestamp": row.get("timestamp"),
        "observation_state": [float(value) for value in row.get("observation.state", [])],
        "learning_action": [float(value) for value in row.get("action", [])],
        "action_semantics": {
            "representation": "lerobot_action_vector",
            "coordinate_frame": "source_dataset_native_frame",
            "normalized_contract_roles": ["source_action", "learning_action"],
        },
        "quality": {
            "state_action_numeric": True,
            "timestamp_monotonic": True,
            "dimension_consistent": True,
            "accepted_for_export": True,
            "rejection_reason": None,
        },
    }


def _extract_rows_from_pyarrow_table(table: Any, *, repo_id: str, resolved_revision: str, source_file: str) -> list[dict[str, Any]]:
    rows = []
    for row in table.to_pylist():
        if row.get("episode_index") == 0 and 0 <= row.get("frame_index", -1) < 8:
            normalized = {
                "schema_version": RAW_ROW_SCHEMA_VERSION,
                "repo_id": repo_id,
                "resolved_revision": resolved_revision,
                "source_file": source_file,
                "episode_index": int(row["episode_index"]),
                "frame_index": int(row["frame_index"]),
                "timestamp": float(row["timestamp"]),
                "observation.state": [float(value) for value in row["observation.state"]],
                "action": [float(value) for value in row["action"]],
            }
            for optional in ("task_index", "index", "next.done", "next.success", "observation.effort"):
                if optional in row:
                    normalized[optional] = row[optional]
            normalized["source_row_sha256"] = _canonical_row_digest(normalized)
            rows.append(normalized)
    rows = sorted(rows, key=_row_frame_index)
    if [row["frame_index"] for row in rows] != list(range(8)):
        raise ValueError("re-extracted frames do not match expected 0..7")
    return rows


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: JSON must be object")
    return payload


def _row_frame_index(row: dict[str, object]) -> int:
    value = row["frame_index"]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("frame_index must be int")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"{path}: line {line_number} must be object")
        rows.append(payload)
    return rows


def _canonical_json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_row_digest(row: dict[str, Any]) -> str:
    without_digest = {key: value for key, value in row.items() if key != "source_row_sha256"}
    return _sha256_bytes(_canonical_json_bytes(without_digest))


def _sha256_shaped(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _commit_sha_shaped(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(ch in "0123456789abcdef" for ch in value)


def _float32_blob(rows: list[dict[str, Any]], key: str) -> bytes:
    values: list[float] = []
    for row in rows:
        values.extend(float(value) for value in row[key])
    return b"".join(struct.pack("<f", value) for value in values)


def _numeric_vector(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value)


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _find_forbidden_fields(payload: Any, path: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_path = f"{path}.{key}" if path else str(key)
            if key in FORBIDDEN_FIELDS:
                hits.append(key_path)
            hits.extend(_find_forbidden_fields(value, key_path))
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            hits.extend(_find_forbidden_fields(item, f"{path}[{index}]"))
    return hits


def _scan_forbidden_true_claims(payload: Any, label: str, issues: list[str]) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in NON_CLAIM_KEYS and value is True:
                issues.append(f"{label}: forbidden claim {key} leaked true")
            _scan_forbidden_true_claims(value, label, issues)
    elif isinstance(payload, list):
        for item in payload:
            _scan_forbidden_true_claims(item, label, issues)


def _scan_seed_values(payload: Any, label: str, issues: list[str], key_path: str = "") -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            next_path = f"{key_path}.{key}" if key_path else str(key)
            if "seed" in str(key).lower():
                for seed in _iter_ints(value):
                    if any(start <= seed <= end for start, end in SPENT_RANGES):
                        issues.append(f"{label}: seed-like field {next_path} reuses spent seed {seed}")
            _scan_seed_values(value, label, issues, next_path)
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            _scan_seed_values(item, label, issues, f"{key_path}[{index}]")


def _scan_forbidden_text_values(payload: Any, label: str, issues: list[str]) -> None:
    if isinstance(payload, dict):
        for value in payload.values():
            _scan_forbidden_text_values(value, label, issues)
    elif isinstance(payload, list):
        for item in payload:
            _scan_forbidden_text_values(item, label, issues)
    elif isinstance(payload, str):
        _scan_text(payload, label, issues)


def _scan_text(text: str, label: str, issues: list[str]) -> None:
    lowered = " ".join(text.lower().split())
    for phrase in FORBIDDEN_TEXT_CLAIM_PHRASES:
        start = 0
        while True:
            index = lowered.find(phrase, start)
            if index < 0:
                break
            raw_context = lowered[max(0, index - 96): index]
            boundary = max(raw_context.rfind("."), raw_context.rfind(";"), raw_context.rfind("!"), raw_context.rfind("?"))
            context = raw_context[boundary + 1:] if boundary >= 0 else raw_context
            if not any(marker in context for marker in NEGATION_MARKERS):
                issues.append(f"{label}: non-negated forbidden prose phrase '{phrase}'")
            start = index + len(phrase)


def _iter_ints(value: Any) -> list[int]:
    if isinstance(value, bool):
        return []
    if isinstance(value, int):
        return [value]
    if isinstance(value, list):
        output: list[int] = []
        for item in value:
            output.extend(_iter_ints(item))
        return output
    if isinstance(value, dict):
        output = []
        for item in value.values():
            output.extend(_iter_ints(item))
        return output
    return []


def _fetch_url(url: str) -> bytes:
    with urlopen(url, timeout=60) as response:
        return response.read()


def _hf_resolve_url(repo_id: str, revision: str, filename: str) -> str:
    return f"https://huggingface.co/datasets/{repo_id}/resolve/{revision}/{filename}"


def verify_package(
    manifest_path: Path,
    *,
    deep_hdf5: bool = False,
    refetch_public_source: bool = False,
    reextract_public_source: bool = False,
) -> Report:
    return Auditor(
        manifest_path,
        deep_hdf5=deep_hdf5,
        refetch_public_source=refetch_public_source,
        reextract_public_source=reextract_public_source,
    ).run()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_manifest", type=Path)
    parser.add_argument("--deep-hdf5", action="store_true")
    parser.add_argument("--refetch-public-source", action="store_true")
    parser.add_argument("--reextract-public-source", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = verify_package(
        args.package_manifest,
        deep_hdf5=args.deep_hdf5,
        refetch_public_source=args.refetch_public_source,
        reextract_public_source=args.reextract_public_source,
    )
    if report.ok:
        print("VERDICT: VERIFIED")
    else:
        print("VERDICT: FAILED")
    for check in report.checks:
        status = "PASS" if check.passed else "FAIL"
        suffix = f" - {check.details}" if check.details else ""
        print(f"{status}: {check.name}{suffix}")
    print(f"row_count={report.recomputed.get('row_count', 'unknown')}")
    print(f"observation_state_dim={report.recomputed.get('observation_state_dim', 'unknown')}")
    print(f"action_dim={report.recomputed.get('action_dim', 'unknown')}")
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
