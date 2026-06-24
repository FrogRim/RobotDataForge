#!/usr/bin/env python3
"""Independent verifier for the two-profile LeRobot public dataset matrix package."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from pathlib import PurePosixPath
import struct
import tempfile
from typing import Any, TypeGuard
from urllib.request import urlopen


RAW_ROW_SCHEMA_VERSION = "rdf_public_lerobot_raw_row_v0.1.0"
CONVERTED_ROW_SCHEMA_VERSION = "rdf_public_lerobot_state_action_row_v0.1.0"
CANONICAL_ROW_DIGEST_ALGORITHM = "json.dumps(sort_keys=True,separators=(',',':'),ensure_ascii=False)+sha256"
SPENT_RANGES = ((40000, 40049), (42000, 42049))


@dataclass(frozen=True)
class Profile:
    profile_id: str
    repo_id: str
    source_file: str
    robot_type: str
    license: str
    episode_index: int
    frame_start: int
    frame_count: int
    observation_state_dim: int
    action_dim: int
    required_upstream_files: tuple[str, ...]

    @property
    def expected_slice_rule(self) -> dict[str, int | str]:
        return {
            "slice_rule": "first_episode_first_n_frames",
            "episode_index": self.episode_index,
            "frame_start": self.frame_start,
            "frame_count": self.frame_count,
        }


PROFILES = (
    Profile(
        profile_id="lerobot_aloha_static_coffee",
        repo_id="lerobot/aloha_static_coffee",
        source_file="data/chunk-000/file-000.parquet",
        robot_type="aloha",
        license="mit",
        episode_index=0,
        frame_start=0,
        frame_count=8,
        observation_state_dim=14,
        action_dim=14,
        required_upstream_files=("data/chunk-000/file-000.parquet", "meta/info.json", "README.md"),
    ),
    Profile(
        profile_id="lerobot_svla_so100_pickplace",
        repo_id="lerobot/svla_so100_pickplace",
        source_file="data/chunk-000/file-000.parquet",
        robot_type="so100",
        license="apache-2.0",
        episode_index=0,
        frame_start=0,
        frame_count=8,
        observation_state_dim=6,
        action_dim=6,
        required_upstream_files=("data/chunk-000/file-000.parquet", "meta/info.json", "README.md"),
    ),
)
PROFILE_BY_ID = {profile.profile_id: profile for profile in PROFILES}
REQUIRED_PROFILE_IDS = tuple(profile.profile_id for profile in PROFILES)
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
    "generic lerobot parser support",
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
    "not a ",
    "without ",
    "no ",
)
CLAUSE_DELIMITERS = ".!?;:\n"


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
    def __init__(
        self,
        manifest_path: Path,
        *,
        deep_hdf5: bool = False,
        refetch_public_source: bool = False,
        reextract_public_source: bool = False,
    ) -> None:
        self.manifest_path = manifest_path
        self.package_root = manifest_path.parent
        self.data_root = self.package_root / "data"
        self.deep_hdf5 = deep_hdf5
        self.refetch_public_source = refetch_public_source
        self.reextract_public_source = reextract_public_source
        self.manifest: dict[str, Any] = {}
        self.artifact_index: dict[str, Any] = {}
        self.config: dict[str, Any] = {}
        self.summary: dict[str, Any] = {}
        self.profile_state: dict[str, dict[str, Any]] = {}
        self.recomputed: dict[str, Any] = {}

    def run(self) -> Report:
        checks = [
            self._check_hash_integrity(),
            self._check_matrix_config_and_summary(),
        ]
        for profile in PROFILES:
            checks.extend(self._check_profile(profile))
        checks.extend(
            [
                self._check_matrix_variety(),
                self._check_non_claims(),
                self._check_forbidden_claims_and_spent_ranges(),
            ]
        )
        if self.deep_hdf5:
            for profile in PROFILES:
                checks.append(self._check_deep_hdf5(profile))
        if self.refetch_public_source:
            for profile in PROFILES:
                checks.append(self._check_refetch_public_source(profile))
        if self.reextract_public_source:
            for profile in PROFILES:
                checks.append(self._check_reextract_public_source(profile))
        self.recomputed["profile_count"] = len(PROFILES)
        self.recomputed["profiles"] = list(REQUIRED_PROFILE_IDS)
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
            return Check("hash_integrity", not failures, "; ".join(failures[:8]))
        except Exception as exc:
            return Check("hash_integrity", False, f"{type(exc).__name__}: {exc}")

    def _check_matrix_config_and_summary(self) -> Check:
        try:
            self.config = _read_json(self.data_root / "config.json")
            self.summary = _read_json(self.data_root / "matrix_summary.json")
            resolver = _read_json(self.data_root / "profile_resolver_report.json")
            issues: list[str] = []
            for label, payload in (("manifest", self.manifest), ("config", self.config), ("summary", self.summary)):
                if payload.get("package_status") != "external_data_evaluated":
                    issues.append(f"{label} package_status mismatch")
                if payload.get("required_profiles") != list(REQUIRED_PROFILE_IDS):
                    issues.append(f"{label} required_profiles mismatch")
            if self.config.get("full_lerobot_parser_claimed") is not False:
                issues.append("config full_lerobot_parser_claimed must be false")
            if self.manifest.get("full_lerobot_parser_claimed") is not False:
                issues.append("manifest full_lerobot_parser_claimed must be false")
            if resolver.get("ok") is not True or resolver.get("selected_profile_id") != "lerobot_svla_so100_pickplace":
                issues.append("resolver report must select SO-100 profile")
            profile_ids = [item.get("profile_id") for item in self.summary.get("profile_summaries", []) if isinstance(item, dict)]
            if profile_ids != list(REQUIRED_PROFILE_IDS):
                issues.append("matrix_summary profile_summaries mismatch")
            return Check("matrix_config_summary", not issues, "; ".join(issues))
        except Exception as exc:
            return Check("matrix_config_summary", False, f"{type(exc).__name__}: {exc}")

    def _check_profile(self, profile: Profile) -> list[Check]:
        return [
            self._check_profile_required_files(profile),
            self._check_profile_public_source_binding(profile),
            self._check_profile_refetch_receipt(profile),
            self._check_profile_raw_rows(profile),
            self._check_profile_extraction_receipt(profile),
            self._check_profile_conversion_parity(profile),
            self._check_profile_contract_reports(profile),
            self._check_profile_hdf5_receipt(profile),
        ]

    def _check_profile_required_files(self, profile: Profile) -> Check:
        root = self._profile_root(profile)
        required = {
            "source/public_source_binding.json",
            "source/upstream_file_hashes.json",
            "source/refetch_receipt.json",
            "source/extraction_receipt.json",
            "source/slice_selection_report.json",
            "source/lerobot_raw_rows.jsonl",
            "source/lerobot_feature_schema.json",
            "source/LICENSE.txt",
            "conversion/rdf_converted_rows.jsonl",
            "conversion/semantic_mapping_report.json",
            "conversion/conversion_manifest.json",
            "contracts/normalized_state_action_contract.json",
            "contracts/validator_report.json",
            "export/dataset.hdf5",
            "export/hdf5_inspection_report.json",
            "export/deep_hdf5_receipt.json",
            "export/trainer_smoke_report.json",
            "reports/buyer_data_evaluation_report.json",
            "profile_metadata.json",
        }
        files = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
        missing = sorted(required - files)
        return Check(f"{profile.profile_id}:required_files", not missing, f"missing {missing}" if missing else "")

    def _check_profile_public_source_binding(self, profile: Profile) -> Check:
        try:
            root = self._profile_root(profile)
            binding = _read_json(root / "source" / "public_source_binding.json")
            upstream = _read_json(root / "source" / "upstream_file_hashes.json")
            self._state(profile)["binding"] = binding
            self._state(profile)["upstream"] = upstream
            issues: list[str] = []
            if binding.get("repo_id") != profile.repo_id:
                issues.append("repo_id mismatch")
            if binding.get("source_file") != profile.source_file:
                issues.append("source_file mismatch")
            if binding.get("dataset_card_robot_type") != profile.robot_type:
                issues.append("robot_type mismatch")
            if binding.get("license") != profile.license:
                issues.append("license mismatch")
            if binding.get("provenance_trust_tier") != "refetchable_public_source":
                issues.append("provenance_trust_tier mismatch")
            if binding.get("full_dataset_verdict_claimed") is not False:
                issues.append("full_dataset_verdict_claimed must be false")
            if binding.get("audited_slice_verdict_claimed") is not True:
                issues.append("audited_slice_verdict_claimed must be true")
            revision = binding.get("resolved_revision")
            if not _commit_sha_shaped(revision):
                issues.append("resolved_revision must be pinned 40-character sha")
            for label, payload in (("upstream", upstream),):
                if payload.get("repo_id") != profile.repo_id:
                    issues.append(f"{label} repo_id mismatch")
                if payload.get("resolved_revision") != revision:
                    issues.append(f"{label} revision mismatch")
            files = upstream.get("files")
            if not isinstance(files, dict):
                issues.append("upstream files must be object")
            else:
                if set(files) != set(profile.required_upstream_files):
                    issues.append("upstream file set mismatch")
                for filename, meta in files.items():
                    if not isinstance(meta, dict) or not _sha256_shaped(meta.get("sha256")):
                        issues.append(f"{filename}: sha missing")
                    if str(revision) not in str(meta.get("source_url", "")):
                        issues.append(f"{filename}: source_url not revision-bound")
            return Check(f"{profile.profile_id}:public_source_binding", not issues, "; ".join(issues))
        except Exception as exc:
            return Check(f"{profile.profile_id}:public_source_binding", False, f"{type(exc).__name__}: {exc}")

    def _check_profile_refetch_receipt(self, profile: Profile) -> Check:
        try:
            receipt = _read_json(self._profile_root(profile) / "source" / "refetch_receipt.json")
            upstream = self._state(profile).get("upstream", {})
            files_payload = upstream.get("files") if isinstance(upstream, dict) else None
            files: dict[str, Any] = files_payload if isinstance(files_payload, dict) else {}
            issues: list[str] = []
            if receipt.get("repo_id") != profile.repo_id:
                issues.append("repo_id mismatch")
            if receipt.get("matched") is not True:
                issues.append("matched must be true")
            checked = receipt.get("files_checked")
            checked_paths = [item.get("path") for item in checked if isinstance(item, dict)] if isinstance(checked, list) else []
            if not isinstance(checked, list) or not all(isinstance(path, str) for path in checked_paths) or set(checked_paths) != set(files):
                issues.append("checked paths mismatch")
            else:
                for item in checked:
                    if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                        issues.append("invalid checked file entry")
                        continue
                    path = item["path"]
                    meta = files.get(path)
                    if not isinstance(meta, dict):
                        issues.append("missing upstream metadata")
                        continue
                    if item.get("declared_sha256") != meta.get("sha256"):
                        issues.append(f"{path}: declared sha mismatch")
                    if item.get("declared_sha256") != item.get("refetched_sha256") or item.get("matched") is not True:
                        issues.append(f"{path}: refetch mismatch")
            return Check(f"{profile.profile_id}:refetch_receipt", not issues, "; ".join(issues))
        except Exception as exc:
            return Check(f"{profile.profile_id}:refetch_receipt", False, f"{type(exc).__name__}: {exc}")

    def _check_profile_raw_rows(self, profile: Profile) -> Check:
        try:
            root = self._profile_root(profile)
            rows = _read_jsonl(root / "source" / "lerobot_raw_rows.jsonl")
            slice_report = _read_json(root / "source" / "slice_selection_report.json")
            feature_schema = _read_json(root / "source" / "lerobot_feature_schema.json")
            binding = self._state(profile).get("binding", {})
            issues = _validate_raw_rows(rows, slice_report.get("slice_rule"), profile=profile, revision=binding.get("resolved_revision"))
            if slice_report.get("source_file") != profile.source_file:
                issues.append("slice report source_file mismatch")
            if slice_report.get("row_count") != len(rows):
                issues.append("slice report row_count mismatch")
            if slice_report.get("raw_row_sha256s") != [_canonical_row_digest(row) for row in rows]:
                issues.append("slice report raw row digests mismatch")
            if feature_schema.get("observation_state_dim") != profile.observation_state_dim:
                issues.append("feature_schema observation dim mismatch")
            if feature_schema.get("action_dim") != profile.action_dim:
                issues.append("feature_schema action dim mismatch")
            self._state(profile)["raw_rows"] = rows
            return Check(f"{profile.profile_id}:raw_rows", not issues, "; ".join(issues))
        except Exception as exc:
            return Check(f"{profile.profile_id}:raw_rows", False, f"{type(exc).__name__}: {exc}")

    def _check_profile_extraction_receipt(self, profile: Profile) -> Check:
        try:
            root = self._profile_root(profile)
            receipt = _read_json(root / "source" / "extraction_receipt.json")
            feature_schema = _read_json(root / "source" / "lerobot_feature_schema.json")
            rows = self._state(profile).get("raw_rows", [])
            upstream = self._state(profile).get("upstream", {})
            source_hash = upstream.get("files", {}).get(profile.source_file, {}).get("sha256") if isinstance(upstream, dict) else None
            raw_file_sha = _sha256_file(root / "source" / "lerobot_raw_rows.jsonl")
            row_digests = [_canonical_row_digest(row) for row in rows]
            issues: list[str] = []
            if receipt.get("repo_id") != profile.repo_id:
                issues.append("repo_id mismatch")
            if receipt.get("source_file") != profile.source_file:
                issues.append("source_file mismatch")
            if receipt.get("canonical_row_digest_algorithm") != CANONICAL_ROW_DIGEST_ALGORITHM:
                issues.append("canonical digest algorithm mismatch")
            if receipt.get("source_file_byte_sha256") != source_hash:
                issues.append("source file byte sha mismatch")
            if receipt.get("feature_schema_sha256") != _sha256_bytes(_canonical_json_bytes(feature_schema)):
                issues.append("feature schema sha mismatch")
            if receipt.get("raw_row_sha256s") != row_digests:
                issues.append("row digest mismatch")
            if receipt.get("included_raw_jsonl_sha256") != raw_file_sha:
                issues.append("included raw jsonl sha mismatch")
            if receipt.get("reextracted_raw_jsonl_sha256") != raw_file_sha:
                issues.append("reextracted raw jsonl sha mismatch")
            if receipt.get("matched") is not True:
                issues.append("receipt matched must be true")
            return Check(f"{profile.profile_id}:extraction_receipt", not issues, "; ".join(issues))
        except Exception as exc:
            return Check(f"{profile.profile_id}:extraction_receipt", False, f"{type(exc).__name__}: {exc}")

    def _check_profile_conversion_parity(self, profile: Profile) -> Check:
        try:
            root = self._profile_root(profile)
            converted = _read_jsonl(root / "conversion" / "rdf_converted_rows.jsonl")
            mapping = _read_json(root / "conversion" / "semantic_mapping_report.json")
            manifest = _read_json(root / "conversion" / "conversion_manifest.json")
            rows = self._state(profile).get("raw_rows", [])
            expected = [_convert_row(row, robot_type=profile.robot_type) for row in rows]
            issues: list[str] = []
            if converted != expected:
                issues.append("converted rows are not deterministic parity from raw rows")
            if mapping.get("fabricated_fields") != []:
                issues.append("mapping fabricated_fields must be empty")
            if mapping.get("source_robot_type") != profile.robot_type:
                issues.append("mapping robot_type mismatch")
            if mapping.get("observation_state_dim") != profile.observation_state_dim:
                issues.append("mapping observation dim mismatch")
            if mapping.get("action_dim") != profile.action_dim:
                issues.append("mapping action dim mismatch")
            if manifest.get("input_raw_row_sha256s") != [_canonical_row_digest(row) for row in rows]:
                issues.append("input digest mismatch")
            if manifest.get("converted_row_sha256s") != [_sha256_bytes(_canonical_json_bytes(row)) for row in converted]:
                issues.append("converted digest mismatch")
            for index, row in enumerate(converted):
                forbidden = _find_forbidden_fields(row)
                if forbidden:
                    issues.append(f"row {index} forbidden fields {forbidden}")
            self._state(profile)["converted_rows"] = converted
            return Check(f"{profile.profile_id}:conversion_parity", not issues, "; ".join(issues))
        except Exception as exc:
            return Check(f"{profile.profile_id}:conversion_parity", False, f"{type(exc).__name__}: {exc}")

    def _check_profile_contract_reports(self, profile: Profile) -> Check:
        try:
            root = self._profile_root(profile)
            contract = _read_json(root / "contracts" / "normalized_state_action_contract.json")
            validator = _read_json(root / "contracts" / "validator_report.json")
            trainer = _read_json(root / "export" / "trainer_smoke_report.json")
            buyer = _read_json(root / "reports" / "buyer_data_evaluation_report.json")
            converted = self._state(profile).get("converted_rows", [])
            issues: list[str] = []
            row_count = len(converted)
            for label, payload in (("contract", contract), ("validator", validator), ("buyer", buyer)):
                if payload.get("row_count") != row_count:
                    issues.append(f"{label} row_count mismatch")
            for label, payload in (("contract", contract), ("validator", validator), ("buyer", buyer), ("trainer", trainer)):
                if payload.get("observation_state_dim") != profile.observation_state_dim:
                    issues.append(f"{label} observation dim mismatch")
                if payload.get("action_dim") != profile.action_dim:
                    issues.append(f"{label} action dim mismatch")
            if validator.get("ok") is not True:
                issues.append("validator must pass")
            if contract.get("robot_type") != profile.robot_type:
                issues.append("contract robot_type mismatch")
            if contract.get("visual_data_ignored") is not True or contract.get("camera_visual_policy_readiness") is not False:
                issues.append("contract visual boundary mismatch")
            if buyer.get("full_source_verdict_claimed") is not False:
                issues.append("buyer full_source_verdict_claimed must be false")
            if buyer.get("audited_slice_verdict_claimed") is not True:
                issues.append("buyer audited_slice_verdict_claimed must be true")
            if trainer.get("trainer") != "generic_state_action_trainer_smoke" or trainer.get("passed") is not True:
                issues.append("trainer smoke must pass")
            return Check(f"{profile.profile_id}:contract_reports", not issues, "; ".join(issues))
        except Exception as exc:
            return Check(f"{profile.profile_id}:contract_reports", False, f"{type(exc).__name__}: {exc}")

    def _check_profile_hdf5_receipt(self, profile: Profile) -> Check:
        try:
            root = self._profile_root(profile)
            hdf5_path = root / "export" / "dataset.hdf5"
            hdf5_bytes = hdf5_path.read_bytes()
            receipt = _read_json(root / "export" / "deep_hdf5_receipt.json")
            report = _read_json(root / "export" / "hdf5_inspection_report.json")
            converted = self._state(profile).get("converted_rows", [])
            state_blob = _float32_blob(converted, "observation_state")
            action_blob = _float32_blob(converted, "learning_action")
            state_hash = _sha256_bytes(state_blob)
            action_hash = _sha256_bytes(action_blob)
            issues: list[str] = []
            if report.get("passed") is not True:
                issues.append("hdf5 inspection must pass")
            if report.get("hdf5_sha256") != _sha256_bytes(hdf5_bytes):
                issues.append("hdf5 report sha mismatch")
            if receipt.get("matched") is not True:
                issues.append("deep receipt matched must be true")
            if receipt.get("row_count") != len(converted):
                issues.append("deep receipt row_count mismatch")
            if receipt.get("converted_row_sha256s") != [_sha256_bytes(_canonical_json_bytes(row)) for row in converted]:
                issues.append("deep receipt converted digest mismatch")
            if receipt.get("expected_observation_state_sha256") != state_hash:
                issues.append("expected state hash mismatch")
            if receipt.get("expected_learning_action_sha256") != action_hash:
                issues.append("expected action hash mismatch")
            if receipt.get("hdf5_observation_state_sha256") != state_hash:
                issues.append("hdf5 state hash mismatch")
            if receipt.get("hdf5_learning_action_sha256") != action_hash:
                issues.append("hdf5 action hash mismatch")
            if hdf5_bytes.count(state_blob) != 1:
                issues.append("HDF5 does not contain expected observation_state float32 payload exactly once")
            if hdf5_bytes.count(action_blob) != 1:
                issues.append("HDF5 does not contain expected learning_action float32 payload exactly once")
            return Check(f"{profile.profile_id}:hdf5_receipt", not issues, "; ".join(issues))
        except Exception as exc:
            return Check(f"{profile.profile_id}:hdf5_receipt", False, f"{type(exc).__name__}: {exc}")

    def _check_matrix_variety(self) -> Check:
        issues: list[str] = []
        summaries = self.summary.get("profile_summaries")
        if not isinstance(summaries, list):
            return Check("matrix_variety", False, "profile_summaries must be list")
        robot_types = {item.get("robot_type") for item in summaries if isinstance(item, dict)}
        dims = {(item.get("observation_state_dim"), item.get("action_dim")) for item in summaries if isinstance(item, dict)}
        if robot_types != {profile.robot_type for profile in PROFILES}:
            issues.append("robot_type variety mismatch")
        if dims != {(profile.observation_state_dim, profile.action_dim) for profile in PROFILES}:
            issues.append("state/action dim variety mismatch")
        if len(robot_types) != len(PROFILES):
            issues.append("profiles must have distinct robot_type values")
        if len(dims) != len(PROFILES):
            issues.append("profiles must have distinct state/action dims")
        if self.summary.get("variety_gate", {}).get("passed") is not True:
            issues.append("summary variety_gate must pass")
        return Check("matrix_variety", not issues, "; ".join(issues))

    def _check_non_claims(self) -> Check:
        try:
            attestation = _read_json(self.data_root / "non_claims_attestation.json")
            issues: list[str] = []
            for label, claims in (
                ("attestation", attestation.get("non_claims")),
                ("manifest", self.manifest.get("non_claims")),
                ("config", self.config.get("non_claims")),
                ("summary", self.summary.get("non_claims")),
            ):
                if set(claims or {}) != NON_CLAIM_KEYS:
                    issues.append(f"{label} non_claim keys mismatch")
                if isinstance(claims, dict):
                    for key, value in claims.items():
                        if value is not False:
                            issues.append(f"{label} {key} must be false")
            for profile in PROFILES:
                buyer = _read_json(self._profile_root(profile) / "reports" / "buyer_data_evaluation_report.json")
                claims = buyer.get("non_claims")
                if set(claims or {}) != NON_CLAIM_KEYS:
                    issues.append(f"{profile.profile_id} buyer non_claim keys mismatch")
                if isinstance(claims, dict):
                    for key, value in claims.items():
                        if value is not False:
                            issues.append(f"{profile.profile_id} buyer {key} must be false")
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

    def _check_deep_hdf5(self, profile: Profile) -> Check:
        try:
            import h5py
            import numpy as np

            hdf5_path = self._profile_root(profile) / "export" / "dataset.hdf5"
            with h5py.File(hdf5_path, "r") as h5:
                episode_id = h5["episodes/episode_ids"][0].decode("utf-8")
                states = np.asarray(h5[f"observations/{episode_id}/observation_state"][()], dtype=np.float32)
                actions = np.asarray(h5[f"actions/{episode_id}/learning_action"][()], dtype=np.float32)
            converted = self._state(profile).get("converted_rows", [])
            expected_states = np.asarray([row["observation_state"] for row in converted], dtype=np.float32)
            expected_actions = np.asarray([row["learning_action"] for row in converted], dtype=np.float32)
            if not np.array_equal(states, expected_states):
                return Check(f"{profile.profile_id}:deep_hdf5", False, "observation_state arrays mismatch")
            if not np.array_equal(actions, expected_actions):
                return Check(f"{profile.profile_id}:deep_hdf5", False, "learning_action arrays mismatch")
            return Check(f"{profile.profile_id}:deep_hdf5", True)
        except Exception as exc:
            return Check(f"{profile.profile_id}:deep_hdf5", False, f"{type(exc).__name__}: {exc}")

    def _check_refetch_public_source(self, profile: Profile) -> Check:
        try:
            binding = self._state(profile).get("binding", {})
            upstream = self._state(profile).get("upstream", {})
            issues: list[str] = []
            for filename, meta in upstream.get("files", {}).items():
                actual = _sha256_bytes(_fetch_url(_hf_resolve_url(profile.repo_id, binding["resolved_revision"], filename)))
                if actual != meta.get("sha256"):
                    issues.append(f"{filename}: public refetch sha mismatch")
            return Check(f"{profile.profile_id}:refetch_public_source", not issues, "; ".join(issues))
        except Exception as exc:
            return Check(f"{profile.profile_id}:refetch_public_source", False, f"{type(exc).__name__}: {exc}")

    def _check_reextract_public_source(self, profile: Profile) -> Check:
        try:
            import pyarrow.parquet as pq

            feature_schema = _read_json(self._profile_root(profile) / "source" / "lerobot_feature_schema.json")
            columns = _feature_schema_columns(feature_schema)
            binding = self._state(profile).get("binding", {})
            with tempfile.TemporaryDirectory(prefix=f"rdf_reextract_{profile.profile_id}_") as tmp:
                parquet_path = Path(tmp) / "source.parquet"
                parquet_path.write_bytes(_fetch_url(_hf_resolve_url(profile.repo_id, binding["resolved_revision"], profile.source_file)))
                table = pq.read_table(parquet_path, columns=columns)
                rows = _extract_rows_from_pyarrow_table(table, profile=profile, revision=binding["resolved_revision"])
            expected = [_canonical_row_digest(row) for row in self._state(profile).get("raw_rows", [])]
            actual = [_canonical_row_digest(row) for row in rows]
            if actual != expected:
                return Check(f"{profile.profile_id}:reextract_public_source", False, "re-extracted row digests mismatch")
            return Check(f"{profile.profile_id}:reextract_public_source", True)
        except Exception as exc:
            return Check(f"{profile.profile_id}:reextract_public_source", False, f"{type(exc).__name__}: {exc}")

    def _profile_root(self, profile: Profile) -> Path:
        return self.data_root / "profiles" / profile.profile_id

    def _state(self, profile: Profile) -> dict[str, Any]:
        return self.profile_state.setdefault(profile.profile_id, {})


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
            failures.append("artifact data_path must be string")
            continue
        parsed = PurePosixPath(data_path)
        if parsed.is_absolute() or parsed.parts[:1] != ("data",) or any(part in {"", ".", ".."} for part in parsed.parts):
            failures.append(f"{data_path}: artifact path must be normalized under data/")
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


def _validate_raw_rows(rows: list[dict[str, Any]], slice_rule: Any, *, profile: Profile, revision: Any) -> list[str]:
    issues: list[str] = []
    if not isinstance(slice_rule, dict):
        return ["slice_rule must be object"]
    for key, expected in profile.expected_slice_rule.items():
        if slice_rule.get(key) != expected:
            issues.append(f"slice_rule {key} mismatch")
    if len(rows) != profile.frame_count:
        issues.append("raw row count mismatch")
    expected_frames = list(range(profile.frame_start, profile.frame_start + profile.frame_count))
    actual_frames: list[int] = []
    previous_timestamp: float | None = None
    state_dim: int | None = None
    action_dim: int | None = None
    for index, row in enumerate(rows):
        if row.get("schema_version") != RAW_ROW_SCHEMA_VERSION:
            issues.append(f"row {index}: schema mismatch")
        if row.get("repo_id") != profile.repo_id:
            issues.append(f"row {index}: repo_id mismatch")
        if row.get("resolved_revision") != revision:
            issues.append(f"row {index}: revision mismatch")
        if row.get("source_file") != profile.source_file:
            issues.append(f"row {index}: source_file mismatch")
        if row.get("episode_index") != profile.episode_index:
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
            state_dim = len(state) if state_dim is None else state_dim
            if len(state) != state_dim:
                issues.append(f"row {index}: observation.state dimension drift")
        if not _numeric_vector(action):
            issues.append(f"row {index}: action must be numeric vector")
        else:
            action_dim = len(action) if action_dim is None else action_dim
            if len(action) != action_dim:
                issues.append(f"row {index}: action dimension drift")
        if row.get("source_row_sha256") != _canonical_row_digest(row):
            issues.append(f"row {index}: source_row_sha256 mismatch")
    if actual_frames != expected_frames:
        issues.append(f"frame sequence mismatch: {actual_frames}")
    if state_dim != profile.observation_state_dim:
        issues.append(f"observation dim mismatch: {state_dim}")
    if action_dim != profile.action_dim:
        issues.append(f"action dim mismatch: {action_dim}")
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


def _extract_rows_from_pyarrow_table(table: Any, *, profile: Profile, revision: str) -> list[dict[str, Any]]:
    rows = table.to_pylist()
    selected = [
        row
        for row in rows
        if row.get("episode_index") == profile.episode_index
        and profile.frame_start <= row.get("frame_index", -1) < profile.frame_start + profile.frame_count
    ]
    selected = sorted(selected, key=lambda row: row["frame_index"])
    return [
        _normalize_source_row(row, repo_id=profile.repo_id, resolved_revision=revision, source_file=profile.source_file)
        for row in selected
    ]


def _normalize_source_row(source_row: dict[str, Any], *, repo_id: str, resolved_revision: str, source_file: str) -> dict[str, Any]:
    row = {
        "schema_version": RAW_ROW_SCHEMA_VERSION,
        "repo_id": repo_id,
        "resolved_revision": resolved_revision,
        "source_file": source_file,
        "episode_index": int(source_row["episode_index"]),
        "frame_index": int(source_row["frame_index"]),
        "timestamp": float(source_row["timestamp"]),
        "observation.state": [float(value) for value in source_row["observation.state"]],
        "action": [float(value) for value in source_row["action"]],
    }
    for optional in ("task_index", "index", "next.done", "next.success", "observation.effort"):
        if optional in source_row:
            row[optional] = source_row[optional]
    row["source_row_sha256"] = _canonical_row_digest(row)
    return row


def _feature_schema_columns(feature_schema: dict[str, Any]) -> list[str]:
    columns = feature_schema.get("columns")
    if not isinstance(columns, list):
        raise ValueError("feature schema columns must be list")
    names: list[str] = []
    for column in columns:
        if not isinstance(column, dict) or not isinstance(column.get("name"), str):
            raise ValueError("feature schema column entries must include name")
        names.append(column["name"])
    required = {"episode_index", "frame_index", "timestamp", "observation.state", "action"}
    missing = required.difference(names)
    if missing:
        raise ValueError(f"feature schema missing required columns: {sorted(missing)}")
    return names


def _float32_blob(rows: list[dict[str, Any]], key: str) -> bytes:
    out = bytearray()
    for row in rows:
        values = row.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            out.extend(struct.pack("<f", float(value)))
    return bytes(out)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: top-level JSON must be object")
    return payload


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


def _canonical_row_digest(row: dict[str, Any]) -> str:
    return _sha256_bytes(_canonical_json_bytes({key: value for key, value in row.items() if key != "source_row_sha256"}))


def _canonical_json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _commit_sha_shaped(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(char in "0123456789abcdef" for char in value)


def _sha256_shaped(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _numeric_vector(value: Any) -> TypeGuard[list[int | float]]:
    return isinstance(value, list) and bool(value) and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value)


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _find_forbidden_fields(payload: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_path = f"{path}.{key}" if path else key
            if key in FORBIDDEN_FIELDS:
                found.append(key_path)
            found.extend(_find_forbidden_fields(value, key_path))
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            found.extend(_find_forbidden_fields(item, f"{path}[{index}]"))
    return found


def _scan_forbidden_true_claims(payload: Any, label: str, issues: list[str]) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in NON_CLAIM_KEYS and value is True:
                issues.append(f"{label}: forbidden claim {key}=true")
            if key in FORBIDDEN_FIELDS:
                issues.append(f"{label}: forbidden fabricated field {key}")
            _scan_forbidden_true_claims(value, label, issues)
    elif isinstance(payload, list):
        for item in payload:
            _scan_forbidden_true_claims(item, label, issues)


def _scan_forbidden_text_values(payload: Any, label: str, issues: list[str]) -> None:
    if isinstance(payload, dict):
        for value in payload.values():
            _scan_forbidden_text_values(value, label, issues)
    elif isinstance(payload, list):
        for value in payload:
            _scan_forbidden_text_values(value, label, issues)
    elif isinstance(payload, str):
        _scan_text(payload, label, issues)


def _scan_text(text: str, label: str, issues: list[str]) -> None:
    lowered = " ".join(text.lower().replace("_", " ").replace("-", " ").split())
    for phrase in FORBIDDEN_TEXT_CLAIM_PHRASES:
        normalized = " ".join(phrase.replace("-", " ").split())
        index = lowered.find(normalized)
        while index != -1:
            if not _forbidden_phrase_is_directly_negated(lowered, index):
                issues.append(f"{label}: forbidden prose claim '{phrase}'")
                break
            index = lowered.find(normalized, index + 1)


def _forbidden_phrase_is_directly_negated(lowered_text: str, phrase_index: int) -> bool:
    clause_start = max(lowered_text.rfind(delimiter, 0, phrase_index) for delimiter in CLAUSE_DELIMITERS) + 1
    prefix = lowered_text[clause_start:phrase_index].strip()
    direct_markers = tuple(marker.strip() for marker in NEGATION_MARKERS)
    return any(prefix.endswith(marker) for marker in direct_markers)


def _scan_seed_values(payload: Any, label: str, issues: list[str]) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_l = str(key).lower()
            if "seed" in key_l:
                _scan_seed_scalar(value, f"{label}.{key}", issues)
            _scan_seed_values(value, label, issues)
    elif isinstance(payload, list):
        for value in payload:
            _scan_seed_values(value, label, issues)


def _scan_seed_scalar(value: Any, label: str, issues: list[str]) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        for low, high in SPENT_RANGES:
            if low <= value <= high:
                issues.append(f"{label}: spent seed {value} reused")
    elif isinstance(value, list):
        for item in value:
            _scan_seed_scalar(item, label, issues)
    elif isinstance(value, dict):
        for item in value.values():
            _scan_seed_scalar(item, label, issues)


def _fetch_url(url: str) -> bytes:
    with urlopen(url, timeout=30) as response:
        return response.read()


def _hf_resolve_url(repo_id: str, revision: str, filename: str) -> str:
    return f"https://huggingface.co/datasets/{repo_id}/resolve/{revision}/{filename}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--deep-hdf5", action="store_true")
    parser.add_argument("--refetch-public-source", action="store_true")
    parser.add_argument("--reextract-public-source", action="store_true")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = Auditor(
        args.manifest,
        deep_hdf5=args.deep_hdf5,
        refetch_public_source=args.refetch_public_source,
        reextract_public_source=args.reextract_public_source,
    ).run()
    if args.json:
        print(
            json.dumps(
                {
                    "ok": report.ok,
                    "checks": [check.__dict__ for check in report.checks],
                    "recomputed": report.recomputed,
                },
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
        )
    else:
        print(f"VERDICT: {'VERIFIED' if report.ok else 'FAILED'}")
        for check in report.checks:
            print(f"{'PASS' if check.passed else 'FAIL'}: {check.name}" + (f" — {check.details}" if check.details else ""))
        print(f"profile_count={report.recomputed.get('profile_count', 0)}")
        print(f"profiles={','.join(report.recomputed.get('profiles', []))}")
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
