#!/usr/bin/env python3
"""Independent verifier for MVP-3C Isaac Sim embodiment-source packages."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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

OPENED_RANGE_KEYS = ("calibration", "heldout", "tuning", "closure")

REQUIRED_PREFLIGHT_FIELDS = (
    "asset_loaded",
    "articulation_detected",
    "joint_state_readable",
    "action_command_writable",
    "runtime_metadata_recorded",
)

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

NON_LEARNING_PROVEN_FALSE_KEYS = (
    "learning_results_measured",
    "policy_uplift",
    "learning_proven_value",
)

EXPECTED_CONTRACT_SOURCE = {
    "input_device": "isaac_sim_command_state_log",
    "runtime": "isaac_sim",
    "simulator": "isaac_sim",
    "task_name": "mvp3c_isaac_sim_embodiment_source",
}

EXPECTED_SOURCE_KIND = "isaac_sim_runtime_backed_command_state_log"

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
    "live ur hardware support",
    "live franka hardware support",
    "live ros2 dds runtime support",
    "franka hardware support",
    "ur hardware support",
    "ros2 bridge support",
    "public sample import",
    "public sample evidence",
    "db migration",
    "production auth",
    "real robot readiness",
    "production robot support",
)

TEXT_NEGATED_MARKERS = (
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

XR_FORBIDDEN_VALUES = (
    "quest3_handtracking",
    "steamvr_openxr",
    "alvr",
)

MIN_VECTOR_LENGTH = 1
MAX_JOINT_VECTOR_LENGTH = 16
EEF_POSE_LENGTH = 7


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
            "status": "unknown",
            "embodiments": [],
            "accepted_count": 0,
            "rejected_count": 0,
            "embodiment_counts": {},
        }

    def run(self) -> Report:
        checks: list[Check] = []
        checks.append(self._check_hash_integrity())
        checks.append(self._check_data_coverage())
        checks.append(self._check_embodiment_set_exactness())
        checks.append(self._check_synthetic_non_closure())
        checks.append(self._check_runtime_capture_source())
        checks.append(self._check_runtime_metadata())
        checks.append(self._check_preflight_required_fields())
        checks.append(self._check_source_log_completeness())
        checks.append(self._check_runtime_capture_binding())
        checks.append(self._check_source_projection_hash_binding())
        checks.append(self._check_accepted_rejected_counts())
        checks.append(self._check_contract_source_fields())
        checks.append(self._check_contract_action_roles())
        checks.append(self._check_frame_action_role_coverage())
        checks.append(self._check_non_claims_false())
        checks.append(self._check_forbidden_claims())
        checks.append(self._check_spent_no_reuse_exact())
        checks.append(self._check_opened_ranges_empty())
        checks.append(self._check_summary_cache_consistency())
        return Report(checks=checks, recomputed=self.recomputed)

    def _check_hash_integrity(self) -> Check:
        try:
            self.manifest = _read_json(self.manifest_path)
            manifest_entries = self._manifest_entries()
            manifest_failures = self._verify_entries(manifest_entries)

            artifact_index_path = self.data_root / "artifact_index.json"
            self.artifact_index = _read_json(artifact_index_path)
            artifact_entries = self._artifact_entries()
            artifact_failures = self._verify_entries(artifact_entries)
            self.indexed_paths = {entry["data_path"] for entry in artifact_entries}

            failures = manifest_failures + artifact_failures
            if failures:
                return Check("hash_integrity", False, "; ".join(failures[:8]))
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
            internal_required = data_files - {"data/artifact_index.json"}
            missing_manifest = sorted(data_files - manifest_paths)
            missing_artifact = sorted(internal_required - artifact_paths)
            unindexed = sorted(data_files - manifest_paths - artifact_paths)
            if missing_manifest or missing_artifact or unindexed:
                return Check(
                    "data_coverage",
                    False,
                    f"missing_manifest={missing_manifest}; "
                    f"missing_artifact={missing_artifact}; unindexed={unindexed}",
                )
            return Check("data_coverage", True)
        except Exception as exc:
            return Check("data_coverage", False, f"{type(exc).__name__}: {exc}")

    def _check_embodiment_set_exactness(self) -> Check:
        try:
            config = self._data_json("config.json")
            required = config.get("required_embodiments")
            source_dirs = sorted(
                path.name
                for path in (self.data_root / "source_logs").iterdir()
                if path.is_dir()
            )
            self.recomputed["embodiments"] = source_dirs
            failures: list[str] = []
            if required != list(REQUIRED_EMBODIMENTS):
                failures.append(f"required_embodiments={required!r}")
            if source_dirs != list(REQUIRED_EMBODIMENTS):
                failures.append(f"source_dirs={source_dirs!r}")
            for embodiment_id in REQUIRED_EMBODIMENTS:
                expected_paths = (
                    f"data/runtime_metadata/{embodiment_id}_runtime_metadata.json",
                    f"data/preflight/{embodiment_id}_preflight.json",
                    f"data/contracts/{embodiment_id}_normalized_trajectory_contract.json",
                    f"data/adapter_results/{embodiment_id}_adapter_result.json",
                )
                for rel_path in expected_paths:
                    if not (self.package_root / rel_path).exists():
                        failures.append(f"missing {rel_path}")
            if failures:
                return Check("embodiment_set_exactness", False, "; ".join(failures[:8]))
            return Check("embodiment_set_exactness", True)
        except Exception as exc:
            return Check("embodiment_set_exactness", False, f"{type(exc).__name__}: {exc}")

    def _check_synthetic_non_closure(self) -> Check:
        try:
            config = self._data_json("config.json")
            manifest_status = self.manifest.get("claims", {}).get("status")
            requested_status = config.get("requested_status")
            synthetic = config.get("synthetic_verifier_fixture") is True
            closure_assertion = config.get("closure_assertion") is True
            runtime_evidence_captured = config.get("runtime_evidence_captured") is True
            if synthetic:
                self.recomputed["status"] = "synthetic_verifier_fixture"
                if (
                    manifest_status == "isaac_sim_embodiment_source_closed"
                    or requested_status == "isaac_sim_embodiment_source_closed"
                    or closure_assertion
                ):
                    return Check(
                        "synthetic_non_closure",
                        False,
                        "synthetic fixture attempted original closure",
                    )
                return Check("synthetic_non_closure", True)
            if not runtime_evidence_captured:
                return Check(
                    "synthetic_non_closure",
                    False,
                    "non-synthetic package lacks runtime_evidence_captured",
                )
            expected_status = (
                "isaac_sim_embodiment_source_closed"
                if closure_assertion
                else "runtime_evidence_captured"
            )
            self.recomputed["status"] = expected_status
            if manifest_status != expected_status or requested_status != expected_status:
                return Check(
                    "synthetic_non_closure",
                    False,
                    f"status drift manifest={manifest_status!r} requested={requested_status!r}",
                )
            return Check("synthetic_non_closure", True)
        except Exception as exc:
            return Check("synthetic_non_closure", False, f"{type(exc).__name__}: {exc}")

    def _check_runtime_capture_source(self) -> Check:
        try:
            config = self._data_json("config.json")
            capture_path = self.data_root / "runtime_capture.json"
            synthetic = config.get("synthetic_verifier_fixture") is True
            if synthetic:
                if capture_path.exists():
                    return Check(
                        "runtime_capture_source",
                        False,
                        "synthetic fixture must not include runtime_capture.json",
                    )
                return Check("runtime_capture_source", True)

            rel_path = "data/runtime_capture.json"
            if not capture_path.exists():
                return Check("runtime_capture_source", False, "missing data/runtime_capture.json")
            if rel_path not in self.indexed_paths:
                return Check("runtime_capture_source", False, "runtime_capture.json not hash-bound")
            source_ref = config.get("runtime_capture_source")
            if not isinstance(source_ref, dict):
                return Check("runtime_capture_source", False, "config.runtime_capture_source missing")
            if source_ref.get("data_path") != rel_path:
                return Check("runtime_capture_source", False, "runtime_capture_source data_path mismatch")
            if source_ref.get("sha256") != _sha256(capture_path):
                return Check("runtime_capture_source", False, "runtime_capture_source sha256 mismatch")

            payload = _read_json(capture_path)
            failures: list[str] = []
            if payload.get("status") != "runtime_evidence_captured":
                failures.append("status mismatch")
            if payload.get("evidence_kind") != "isaac_sim_runtime_backed_source_log":
                failures.append("evidence_kind mismatch")
            embodiments = payload.get("embodiments")
            if not isinstance(embodiments, dict):
                failures.append("embodiments missing")
                embodiments = {}
            if sorted(embodiments) != list(REQUIRED_EMBODIMENTS):
                failures.append(f"embodiments={sorted(embodiments)!r}")
            for embodiment_id in REQUIRED_EMBODIMENTS:
                entry = embodiments.get(embodiment_id)
                if not isinstance(entry, dict):
                    failures.append(f"{embodiment_id}: entry missing")
                    continue
                runtime_metadata = entry.get("runtime_metadata")
                preflight = entry.get("preflight")
                source_rows = entry.get("source_rows")
                if not isinstance(runtime_metadata, dict):
                    failures.append(f"{embodiment_id}: runtime_metadata missing")
                    continue
                if not isinstance(preflight, dict):
                    failures.append(f"{embodiment_id}: preflight missing")
                    continue
                if not isinstance(source_rows, dict):
                    failures.append(f"{embodiment_id}: source_rows missing")
                    continue
                if runtime_metadata.get("capture_origin") != "isaac_sim_process":
                    failures.append(f"{embodiment_id}: capture_origin mismatch")
                for key in ("asset_path", "prim_path"):
                    if not isinstance(runtime_metadata.get(key), str) or not runtime_metadata[key]:
                        failures.append(f"{embodiment_id}: {key} missing")
                if runtime_metadata != self._data_json(
                    f"runtime_metadata/{embodiment_id}_runtime_metadata.json"
                ):
                    failures.append(f"{embodiment_id}: runtime_metadata package mismatch")
                if preflight != self._data_json(f"preflight/{embodiment_id}_preflight.json"):
                    failures.append(f"{embodiment_id}: preflight package mismatch")
                for split, filename in (
                    ("accepted", "accepted_command_state.jsonl"),
                    ("rejected", "rejected_command_state.jsonl"),
                ):
                    rows = source_rows.get(split)
                    accepted = split == "accepted"
                    if not isinstance(rows, list) or not rows:
                        failures.append(f"{embodiment_id}: {split} rows missing")
                        continue
                    if rows != self._source_rows(embodiment_id, filename):
                        failures.append(f"{embodiment_id}: {split} rows package mismatch")
                    for row_index, row in enumerate(rows):
                        failures.extend(
                            _validate_source_row_semantics(
                                row,
                                embodiment_id=embodiment_id,
                                accepted=accepted,
                                label=f"{embodiment_id}: runtime {split} row {row_index}",
                            )
                        )
            if failures:
                return Check("runtime_capture_source", False, "; ".join(failures[:8]))
            return Check("runtime_capture_source", True)
        except Exception as exc:
            return Check("runtime_capture_source", False, f"{type(exc).__name__}: {exc}")

    def _check_runtime_metadata(self) -> Check:
        try:
            failures: list[str] = []
            synthetic = self.recomputed.get("status") == "synthetic_verifier_fixture"
            for embodiment_id in REQUIRED_EMBODIMENTS:
                rel_path = f"data/runtime_metadata/{embodiment_id}_runtime_metadata.json"
                metadata = self._data_json(rel_path.removeprefix("data/"))
                expected_capture = _expected_capture_id(embodiment_id)
                if rel_path not in self.indexed_paths:
                    failures.append(f"{embodiment_id}: runtime metadata not hash-bound")
                if metadata.get("embodiment_id") != embodiment_id:
                    failures.append(f"{embodiment_id}: embodiment mismatch")
                if metadata.get("runtime_capture_id") != expected_capture:
                    failures.append(f"{embodiment_id}: runtime_capture_id mismatch")
                if metadata.get("runtime") != "isaac_sim":
                    failures.append(f"{embodiment_id}: runtime={metadata.get('runtime')!r}")
                if metadata.get("simulator") != "isaac_sim":
                    failures.append(f"{embodiment_id}: simulator={metadata.get('simulator')!r}")
                if metadata.get("platform") != "linux":
                    failures.append(f"{embodiment_id}: platform={metadata.get('platform')!r}")
                if (
                    metadata.get("source_kind")
                    != "isaac_sim_runtime_backed_command_state_log"
                ):
                    failures.append(f"{embodiment_id}: source_kind mismatch")
                if synthetic:
                    if metadata.get("capture_origin") != "synthetic_verifier_fixture":
                        failures.append(f"{embodiment_id}: synthetic capture_origin mismatch")
                else:
                    if metadata.get("capture_origin") != "isaac_sim_process":
                        failures.append(f"{embodiment_id}: capture_origin mismatch")
                    for key in ("asset_path", "prim_path"):
                        if not isinstance(metadata.get(key), str) or not metadata[key]:
                            failures.append(f"{embodiment_id}: {key} missing")
            if failures:
                return Check("runtime_metadata", False, "; ".join(failures[:8]))
            return Check("runtime_metadata", True)
        except Exception as exc:
            return Check("runtime_metadata", False, f"{type(exc).__name__}: {exc}")

    def _check_preflight_required_fields(self) -> Check:
        try:
            failures: list[str] = []
            for embodiment_id in REQUIRED_EMBODIMENTS:
                preflight = self._data_json(f"preflight/{embodiment_id}_preflight.json")
                if preflight.get("embodiment_id") != embodiment_id:
                    failures.append(f"{embodiment_id}: embodiment mismatch")
                if preflight.get("runtime_capture_id") != _expected_capture_id(embodiment_id):
                    failures.append(f"{embodiment_id}: runtime_capture_id mismatch")
                for field_name in REQUIRED_PREFLIGHT_FIELDS:
                    if preflight.get(field_name) is not True:
                        failures.append(f"{embodiment_id}: {field_name} is not true")
                rows_emitted = preflight.get("source_log_rows_emitted")
                if not isinstance(rows_emitted, int) or rows_emitted < 2:
                    failures.append(f"{embodiment_id}: source_log_rows_emitted={rows_emitted!r}")
            if failures:
                return Check("preflight_required_fields", False, "; ".join(failures[:8]))
            return Check("preflight_required_fields", True)
        except Exception as exc:
            return Check(
                "preflight_required_fields",
                False,
                f"{type(exc).__name__}: {exc}",
            )

    def _check_source_log_completeness(self) -> Check:
        try:
            failures: list[str] = []
            for embodiment_id in REQUIRED_EMBODIMENTS:
                metadata = self._data_json(f"source_logs/{embodiment_id}/metadata.json")
                if metadata.get("embodiment_id") != embodiment_id:
                    failures.append(f"{embodiment_id}: source metadata embodiment mismatch")
                if metadata.get("runtime_capture_id") != _expected_capture_id(embodiment_id):
                    failures.append(f"{embodiment_id}: source metadata capture mismatch")
                if metadata.get("runtime") != "isaac_sim":
                    failures.append(f"{embodiment_id}: source metadata runtime mismatch")
                if metadata.get("simulator") != "isaac_sim":
                    failures.append(f"{embodiment_id}: source metadata simulator mismatch")
                accepted = self._source_rows(embodiment_id, "accepted_command_state.jsonl")
                rejected = self._source_rows(embodiment_id, "rejected_command_state.jsonl")
                if not accepted:
                    failures.append(f"{embodiment_id}: missing accepted rows")
                if not rejected:
                    failures.append(f"{embodiment_id}: missing rejected rows")
                for row in accepted:
                    if row.get("accepted") is not True:
                        failures.append(f"{embodiment_id}: invalid accepted row")
                for row_index, row in enumerate(accepted):
                    failures.extend(
                        _validate_source_row_semantics(
                            row,
                            embodiment_id=embodiment_id,
                            accepted=True,
                            label=f"{embodiment_id}: accepted row {row_index}",
                        )
                    )
                for row in rejected:
                    if row.get("accepted") is not False:
                        failures.append(f"{embodiment_id}: invalid rejected row")
                for row_index, row in enumerate(rejected):
                    failures.extend(
                        _validate_source_row_semantics(
                            row,
                            embodiment_id=embodiment_id,
                            accepted=False,
                            label=f"{embodiment_id}: rejected row {row_index}",
                        )
                    )
            if failures:
                return Check("source_log_completeness", False, "; ".join(failures[:8]))
            return Check("source_log_completeness", True)
        except Exception as exc:
            return Check("source_log_completeness", False, f"{type(exc).__name__}: {exc}")

    def _check_runtime_capture_binding(self) -> Check:
        try:
            metadata_by_capture = self._runtime_metadata_by_capture()
            failures: list[str] = []
            for embodiment_id in REQUIRED_EMBODIMENTS:
                expected_capture = _expected_capture_id(embodiment_id)
                for row_index, row in enumerate(self._all_source_rows(embodiment_id)):
                    capture_id = row.get("runtime_capture_id")
                    runtime_metadata = (
                        metadata_by_capture.get(capture_id)
                        if isinstance(capture_id, str)
                        else None
                    )
                    prefix = f"{embodiment_id}: row {row_index}"
                    if row.get("embodiment_id") != embodiment_id:
                        failures.append(f"{prefix}: embodiment drift")
                    if row.get("runtime") != "isaac_sim":
                        failures.append(f"{prefix}: runtime={row.get('runtime')!r}")
                    if row.get("simulator") != "isaac_sim":
                        failures.append(f"{prefix}: simulator={row.get('simulator')!r}")
                    if capture_id != expected_capture:
                        failures.append(f"{prefix}: runtime_capture_id={capture_id!r}")
                    if runtime_metadata is None:
                        failures.append(f"{prefix}: missing runtime metadata")
                    elif runtime_metadata.get("embodiment_id") != embodiment_id:
                        failures.append(f"{prefix}: capture resolves to wrong embodiment")
            if failures:
                return Check("runtime_capture_binding", False, "; ".join(failures[:8]))
            return Check("runtime_capture_binding", True)
        except Exception as exc:
            return Check("runtime_capture_binding", False, f"{type(exc).__name__}: {exc}")

    def _check_source_projection_hash_binding(self) -> Check:
        try:
            failures: list[str] = []
            for embodiment_id in REQUIRED_EMBODIMENTS:
                projection = self._projection_manifest(embodiment_id)
                runtime_entry = projection.get("runtime_metadata", {})
                runtime_rel = f"data/runtime_metadata/{embodiment_id}_runtime_metadata.json"
                runtime_path = self.package_root / runtime_rel
                if runtime_entry.get("data_path") != runtime_rel:
                    failures.append(f"{embodiment_id}: runtime metadata path mismatch")
                if runtime_path.exists() and runtime_entry.get("sha256") != _sha256(runtime_path):
                    failures.append(f"{embodiment_id}: runtime metadata hash mismatch")
                source_logs = projection.get("source_logs", {})
                for filename in (
                    "accepted_command_state.jsonl",
                    "rejected_command_state.jsonl",
                ):
                    source_path = (
                        self.data_root / "source_logs" / embodiment_id / filename
                    )
                    rows = _read_jsonl(source_path)
                    entry = source_logs.get(filename, {})
                    if entry.get("sha256") != _sha256(source_path):
                        failures.append(f"{embodiment_id}: {filename} hash mismatch")
                    if entry.get("rows") != len(rows):
                        failures.append(f"{embodiment_id}: {filename} rows mismatch")
                for split, filename in (
                    ("accepted", "accepted_command_state.jsonl"),
                    ("rejected", "rejected_command_state.jsonl"),
                ):
                    source_rows = self._source_rows(embodiment_id, filename)
                    trajectory = self._projection_json(
                        embodiment_id,
                        f"trajectories/{split}.json",
                    )
                    if trajectory.get("embodiment_id") != embodiment_id:
                        failures.append(f"{embodiment_id}: {split} trajectory embodiment mismatch")
                    if trajectory.get("frames") != source_rows:
                        failures.append(f"{embodiment_id}: {split} trajectory frames mismatch")
                for rel_path, expected_hash in projection.get(
                    "projected_artifacts", {}
                ).items():
                    path = self.data_root / "projections" / embodiment_id / rel_path
                    if not path.exists():
                        failures.append(f"{embodiment_id}: missing projection {rel_path}")
                    elif _sha256(path) != expected_hash:
                        failures.append(f"{embodiment_id}: projection hash {rel_path}")
            if failures:
                return Check(
                    "source_projection_hash_binding",
                    False,
                    "; ".join(failures[:8]),
                )
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
            embodiment_counts: dict[str, dict[str, Any]] = {}
            for embodiment_id in REQUIRED_EMBODIMENTS:
                accepted_count = len(
                    self._source_rows(embodiment_id, "accepted_command_state.jsonl")
                )
                rejected_count = len(
                    self._source_rows(embodiment_id, "rejected_command_state.jsonl")
                )
                total_accepted += accepted_count
                total_rejected += rejected_count
                embodiment_counts[embodiment_id] = {
                    "accepted_count": accepted_count,
                    "rejected_count": rejected_count,
                    "runtime_capture_id": _expected_capture_id(embodiment_id),
                }
                curation = self._projection_json(embodiment_id, "curation_manifest.json")
                projection = self._projection_manifest(embodiment_id)
                result = self._data_json(f"adapter_results/{embodiment_id}_adapter_result.json")
                for label, payload in (
                    ("curation_manifest", curation),
                    ("projection_manifest", projection),
                    ("adapter_result", result),
                ):
                    if payload.get("accepted_count") != accepted_count:
                        failures.append(f"{embodiment_id}: {label} accepted mismatch")
                    if payload.get("rejected_count") != rejected_count:
                        failures.append(f"{embodiment_id}: {label} rejected mismatch")
            self.recomputed["accepted_count"] = total_accepted
            self.recomputed["rejected_count"] = total_rejected
            self.recomputed["embodiment_counts"] = embodiment_counts
            if failures:
                return Check("accepted_rejected_counts", False, "; ".join(failures[:8]))
            return Check("accepted_rejected_counts", True)
        except Exception as exc:
            return Check("accepted_rejected_counts", False, f"{type(exc).__name__}: {exc}")

    def _check_contract_source_fields(self) -> Check:
        try:
            failures: list[str] = []
            for embodiment_id in REQUIRED_EMBODIMENTS:
                contract = self._contract(embodiment_id)
                source = contract.get("source", {})
                for key, expected in EXPECTED_CONTRACT_SOURCE.items():
                    if source.get(key) != expected:
                        failures.append(f"{embodiment_id}: source.{key}={source.get(key)!r}")
                if source.get("robot") != embodiment_id:
                    failures.append(f"{embodiment_id}: source.robot={source.get('robot')!r}")
                if contract.get("embodiment_id") != embodiment_id:
                    failures.append(f"{embodiment_id}: contract embodiment mismatch")
            if failures:
                return Check("contract_source_fields", False, "; ".join(failures[:8]))
            return Check("contract_source_fields", True)
        except Exception as exc:
            return Check("contract_source_fields", False, f"{type(exc).__name__}: {exc}")

    def _check_contract_action_roles(self) -> Check:
        try:
            failures: list[str] = []
            required_roles = list(REQUIRED_ACTION_ROLES)
            for embodiment_id in REQUIRED_EMBODIMENTS:
                contract = self._contract(embodiment_id)
                if contract.get("required_action_roles") != required_roles:
                    failures.append(f"{embodiment_id}: required_action_roles mismatch")
                coverage = contract.get("frame_action_role_coverage", {})
                for role in REQUIRED_ACTION_ROLES:
                    role_coverage = coverage.get(role, {})
                    if role_coverage.get("present") is not True:
                        failures.append(f"{embodiment_id}: {role} not present")
                    if not isinstance(role_coverage.get("frames"), int):
                        failures.append(f"{embodiment_id}: {role} frames missing")
                result = self._data_json(f"adapter_results/{embodiment_id}_adapter_result.json")
                if result.get("required_action_roles_present") != required_roles:
                    failures.append(f"{embodiment_id}: adapter_result roles mismatch")
            if failures:
                return Check("contract_action_roles", False, "; ".join(failures[:8]))
            return Check("contract_action_roles", True)
        except Exception as exc:
            return Check("contract_action_roles", False, f"{type(exc).__name__}: {exc}")

    def _check_frame_action_role_coverage(self) -> Check:
        try:
            failures: list[str] = []
            for embodiment_id in REQUIRED_EMBODIMENTS:
                rows = self._all_source_rows(embodiment_id)
                expected_counts = _frame_action_role_counts(rows)
                coverage = self._contract(embodiment_id).get(
                    "frame_action_role_coverage", {}
                )
                for row_index, row in enumerate(rows):
                    actions = row.get("command_state", {}).get("actions_by_role", {})
                    missing = [role for role in REQUIRED_ACTION_ROLES if role not in actions]
                    if missing:
                        failures.append(f"{embodiment_id}: row {row_index} missing {missing}")
                for role in REQUIRED_ACTION_ROLES:
                    role_coverage = coverage.get(role, {})
                    if role_coverage.get("present") is not (expected_counts[role] > 0):
                        failures.append(f"{embodiment_id}: {role} present mismatch")
                    if role_coverage.get("frames") != expected_counts[role]:
                        failures.append(f"{embodiment_id}: {role} frames mismatch")
            if failures:
                return Check("frame_action_role_coverage", False, "; ".join(failures[:8]))
            return Check("frame_action_role_coverage", True)
        except Exception as exc:
            return Check(
                "frame_action_role_coverage",
                False,
                f"{type(exc).__name__}: {exc}",
            )

    def _check_non_claims_false(self) -> Check:
        try:
            config = self._data_json("config.json")
            attestation = self._data_json("non_claims_attestation.json")
            canonical = set(CANONICAL_FORBIDDEN_CLAIMS)
            failures: list[str] = []
            if set(config.get("non_claims", {}).keys()) != canonical:
                failures.append("config non_claims keys are not canonical")
            if set(attestation.get("forbidden_claims", {}).keys()) != canonical:
                failures.append("attestation forbidden_claims keys are not canonical")
            if config.get("learning_proven_addendum") != "absent":
                failures.append("learning_proven_addendum must be absent")
            for path in self._package_surface_files():
                if path.suffix.lower() == ".json":
                    payload: Any = _read_json(path)
                elif path.suffix.lower() == ".jsonl":
                    payload = _read_jsonl(path)
                else:
                    continue
                rel = path.relative_to(self.package_root).as_posix()
                failures.extend(
                    f"{rel}:{violation}"
                    for violation in _non_learning_proven_field_violations(payload)
                )
            if failures:
                return Check("non_claims_false", False, "; ".join(failures[:8]))
            return Check("non_claims_false", True)
        except Exception as exc:
            return Check("non_claims_false", False, f"{type(exc).__name__}: {exc}")

    def _check_forbidden_claims(self) -> Check:
        try:
            failures: list[str] = []
            for path in self._package_surface_files():
                rel = path.relative_to(self.package_root).as_posix()
                if path.suffix.lower() == ".json":
                    payload: Any = _read_json(path)
                    failures.extend(
                        f"{rel}:{dotted_path}={value!r}"
                        for dotted_path, value in _walk_claim_keys(payload)
                    )
                    failures.extend(
                        f"{rel}:{dotted_path}={value!r}"
                        for dotted_path, value in _walk_forbidden_values(payload)
                    )
                elif path.suffix.lower() == ".jsonl":
                    payload = _read_jsonl(path)
                    failures.extend(
                        f"{rel}:{dotted_path}={value!r}"
                        for dotted_path, value in _walk_claim_keys(payload)
                    )
                    failures.extend(
                        f"{rel}:{dotted_path}={value!r}"
                        for dotted_path, value in _walk_forbidden_values(payload)
                    )
                elif path.suffix.lower() in TEXT_CLAIM_SUFFIXES:
                    failures.extend(
                        f"{rel}:{phrase}" for phrase in _forbidden_text_claims(path)
                    )
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
            non_empty = [
                key for key in OPENED_RANGE_KEYS if opened_ranges.get(key) not in ([], None)
            ]
            missing = [key for key in OPENED_RANGE_KEYS if key not in opened_ranges]
            if non_empty or missing:
                return Check(
                    "opened_ranges_empty",
                    False,
                    f"non_empty={non_empty}; missing={missing}",
                )
            return Check("opened_ranges_empty", True)
        except Exception as exc:
            return Check("opened_ranges_empty", False, f"{type(exc).__name__}: {exc}")

    def _check_summary_cache_consistency(self) -> Check:
        try:
            summary = self._data_json("embodiment_source_summary.json")
            runtime_summary = self._data_json("isaac_sim_runtime_summary.json")
            expected_status = self.recomputed.get("status")
            expected_counts = self.recomputed.get("embodiment_counts", {})
            failures: list[str] = []
            if summary.get("status") != expected_status:
                failures.append(f"summary status={summary.get('status')!r}")
            if runtime_summary.get("status") != expected_status:
                failures.append(f"runtime summary status={runtime_summary.get('status')!r}")
            if summary.get("embodiment_count") != len(REQUIRED_EMBODIMENTS):
                failures.append("summary embodiment_count mismatch")
            if summary.get("required_embodiment_count") != len(REQUIRED_EMBODIMENTS):
                failures.append("summary required_embodiment_count mismatch")
            if summary.get("accepted_count") != self.recomputed.get("accepted_count"):
                failures.append("summary accepted_count mismatch")
            if summary.get("rejected_count") != self.recomputed.get("rejected_count"):
                failures.append("summary rejected_count mismatch")
            for embodiment_id, counts in expected_counts.items():
                if summary.get("embodiments", {}).get(embodiment_id) != counts:
                    failures.append(f"{embodiment_id}: summary counts mismatch")
            for key in NON_LEARNING_PROVEN_FALSE_KEYS:
                if summary.get(key) is not False:
                    failures.append(f"summary {key} must be false")
            if failures:
                return Check("summary_cache_consistency", False, "; ".join(failures[:8]))
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
            raise ValueError("package_manifest.artifact_index must be a list")
        return entries

    def _artifact_entries(self) -> list[dict[str, Any]]:
        entries = self.artifact_index.get("artifact_index", [])
        if not isinstance(entries, list):
            raise ValueError("data/artifact_index.json artifact_index must be a list")
        return entries

    def _verify_entries(self, entries: list[dict[str, Any]]) -> list[str]:
        failures: list[str] = []
        for entry in entries:
            rel_path = entry.get("data_path")
            if not isinstance(rel_path, str):
                failures.append("entry missing data_path")
                continue
            if entry.get("hash_convention") != "file_bytes":
                failures.append(f"{rel_path}: unsupported hash convention")
                continue
            path = self.package_root / rel_path
            if not path.exists():
                failures.append(f"{rel_path}: missing")
                continue
            expected_hash = entry.get("file_sha256")
            actual_hash = _sha256(path)
            if expected_hash != actual_hash:
                failures.append(f"{rel_path}: sha256 mismatch")
        return failures

    def _data_json(self, rel_path: str) -> dict[str, Any]:
        path = self.data_root / rel_path
        return _read_json(path)

    def _projection_manifest(self, embodiment_id: str) -> dict[str, Any]:
        return self._projection_json(embodiment_id, "projection_manifest.json")

    def _projection_json(self, embodiment_id: str, rel_path: str) -> dict[str, Any]:
        return _read_json(self.data_root / "projections" / embodiment_id / rel_path)

    def _contract(self, embodiment_id: str) -> dict[str, Any]:
        return self._data_json(
            f"contracts/{embodiment_id}_normalized_trajectory_contract.json"
        )

    def _source_rows(self, embodiment_id: str, filename: str) -> list[dict[str, Any]]:
        return _read_jsonl(self.data_root / "source_logs" / embodiment_id / filename)

    def _all_source_rows(self, embodiment_id: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        rows.extend(self._source_rows(embodiment_id, "accepted_command_state.jsonl"))
        rows.extend(self._source_rows(embodiment_id, "rejected_command_state.jsonl"))
        return rows

    def _runtime_metadata_by_capture(self) -> dict[str, dict[str, Any]]:
        metadata_by_capture = {}
        for embodiment_id in REQUIRED_EMBODIMENTS:
            metadata = self._data_json(
                f"runtime_metadata/{embodiment_id}_runtime_metadata.json"
            )
            capture_id = metadata.get("runtime_capture_id")
            if isinstance(capture_id, str):
                metadata_by_capture[capture_id] = metadata
        return metadata_by_capture

    def _package_surface_files(self) -> list[Path]:
        files = [self.manifest_path]
        files.extend(path for path in self.data_root.rglob("*") if path.is_file())
        for path in self.package_root.iterdir():
            if path.is_file() and path not in files:
                files.append(path)
        return sorted(files)


def verify_package(manifest_path: str | Path) -> Report:
    return Auditor(Path(manifest_path)).run()


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
    while index < len(body):
        while index < len(body) and body[index].isspace():
            index += 1
        if index >= len(body):
            break
        payload, index = decoder.raw_decode(body, index)
        if not isinstance(payload, dict):
            raise ValueError(f"{path} row must be a JSON object")
        rows.append(payload)
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expected_capture_id(embodiment_id: str) -> str:
    return f"{embodiment_id}_runtime_capture_20260622T010000Z"


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _numeric_vector(
    value: Any,
    *,
    min_len: int = MIN_VECTOR_LENGTH,
    max_len: int | None = MAX_JOINT_VECTOR_LENGTH,
    exact_len: int | None = None,
) -> bool:
    if not isinstance(value, list):
        return False
    if exact_len is not None and len(value) != exact_len:
        return False
    if exact_len is None and len(value) < min_len:
        return False
    if max_len is not None and len(value) > max_len:
        return False
    return all(_is_number(item) for item in value)


def _validate_source_row_semantics(
    row: Any,
    *,
    embodiment_id: str,
    accepted: bool,
    label: str,
) -> list[str]:
    failures: list[str] = []
    if not isinstance(row, dict):
        return [f"{label}: row is not object"]
    if row.get("embodiment_id") != embodiment_id:
        failures.append(f"{label}: embodiment_id={row.get('embodiment_id')!r}")
    if row.get("runtime_capture_id") != _expected_capture_id(embodiment_id):
        failures.append(f"{label}: runtime_capture_id={row.get('runtime_capture_id')!r}")
    if not isinstance(row.get("row_id"), str) or not row["row_id"]:
        failures.append(f"{label}: row_id missing")
    if not _is_number(row.get("timestamp_ns")):
        failures.append(f"{label}: timestamp_ns={row.get('timestamp_ns')!r}")
    if row.get("runtime") != "isaac_sim":
        failures.append(f"{label}: runtime={row.get('runtime')!r}")
    if row.get("simulator") != "isaac_sim":
        failures.append(f"{label}: simulator={row.get('simulator')!r}")
    if row.get("source_kind") != EXPECTED_SOURCE_KIND:
        failures.append(f"{label}: source_kind={row.get('source_kind')!r}")
    if row.get("accepted") is not accepted:
        failures.append(f"{label}: accepted={row.get('accepted')!r}")

    command_state = row.get("command_state")
    if not isinstance(command_state, dict):
        return failures + [f"{label}: command_state missing"]
    if not _numeric_vector(command_state.get("joint_positions")):
        failures.append(f"{label}: joint_positions not numeric vector")
    if not _numeric_vector(command_state.get("joint_velocities")):
        failures.append(f"{label}: joint_velocities not numeric vector")
    if not _numeric_vector(
        command_state.get("eef_pose"),
        max_len=None,
        exact_len=EEF_POSE_LENGTH,
    ):
        failures.append(f"{label}: eef_pose not numeric 7-vector")

    actions = command_state.get("actions_by_role")
    if not isinstance(actions, dict):
        return failures + [f"{label}: actions_by_role missing"]
    for role in REQUIRED_ACTION_ROLES:
        if role not in actions:
            failures.append(f"{label}: missing role {role}")
            continue
        if not _numeric_vector(actions[role]):
            failures.append(f"{label}: role {role} not numeric vector")
    return failures


def _frame_action_role_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {role: 0 for role in REQUIRED_ACTION_ROLES}
    for row in rows:
        actions = row.get("command_state", {}).get("actions_by_role", {})
        if not isinstance(actions, dict):
            continue
        for role in REQUIRED_ACTION_ROLES:
            if role in actions:
                counts[role] += 1
    return counts


def _walk_claim_keys(payload: Any, prefix: str = "") -> list[tuple[str, Any]]:
    findings: list[tuple[str, Any]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            dotted = f"{prefix}.{key}" if prefix else str(key)
            if key in CANONICAL_FORBIDDEN_CLAIMS and value is not False:
                findings.append((dotted, value))
            findings.extend(_walk_claim_keys(value, dotted))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(_walk_claim_keys(value, f"{prefix}[{index}]"))
    return findings


def _walk_forbidden_values(payload: Any, prefix: str = "") -> list[tuple[str, Any]]:
    findings: list[tuple[str, Any]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            dotted = f"{prefix}.{key}" if prefix else str(key)
            findings.extend(_walk_forbidden_values(value, dotted))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            findings.extend(_walk_forbidden_values(value, f"{prefix}[{index}]"))
    elif isinstance(payload, str) and payload in XR_FORBIDDEN_VALUES:
        findings.append((prefix, payload))
    return findings


def _non_learning_proven_field_violations(
    payload: Any,
    prefix: str = "",
) -> list[str]:
    violations: list[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            dotted = f"{prefix}.{key}" if prefix else str(key)
            if key in NON_LEARNING_PROVEN_FALSE_KEYS and value is not False:
                violations.append(f"{dotted} must be false")
            violations.extend(_non_learning_proven_field_violations(value, dotted))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            violations.extend(
                _non_learning_proven_field_violations(value, f"{prefix}[{index}]")
            )
    return violations


def _forbidden_text_claims(path: Path) -> list[str]:
    findings: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        lowered = line.lower()
        for phrase in FORBIDDEN_TEXT_CLAIM_PHRASES:
            index = lowered.find(phrase)
            if index == -1:
                continue
            before = lowered[:index]
            if any(marker in before for marker in TEXT_NEGATED_MARKERS):
                continue
            findings.append(f"line {line_number}: {phrase}")
    return findings


def _print_report(report: Report) -> None:
    verdict = "VERIFIED" if report.ok else "FAILED"
    print(f"VERDICT: {verdict}")
    print(f"status={report.recomputed.get('status')}")
    for check in report.checks:
        state = "PASS" if check.passed else "FAIL"
        details = f" — {check.details}" if check.details else ""
        print(f"{state} {check.name}{details}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify an MVP-3C Isaac Sim embodiment-source proof package."
    )
    parser.add_argument("manifest", type=Path, help="Path to package_manifest.json")
    args = parser.parse_args(argv)

    report = verify_package(args.manifest)
    _print_report(report)
    return report.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
