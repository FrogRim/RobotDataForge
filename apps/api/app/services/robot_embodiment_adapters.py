from __future__ import annotations

from dataclasses import dataclass
import copy
import json
from pathlib import Path
from typing import Any, Iterable

from app.services.contract_builders import (
    FrankaContractBuilder,
    RobotEmbodimentContractBuilder,
    RobotisSh5Ros2DdsContractBuilder,
    UniversalRobotsUrContractBuilder,
)
from app.services.normalized_trajectory_contract import NormalizedTrajectoryContractValidator


ROBOT_EMBODIMENT_ADAPTER_REGISTRY_SCHEMA_VERSION = "rdf_robot_embodiment_adapter_registry_v0.1.0"
ROBOT_EMBODIMENT_ADAPTER_PROOF_SCHEMA_VERSION = "rdf_mvp1plus_robot_embodiment_adapter_result_v0.1.0"
ROBOT_EMBODIMENT_ADAPTER_VERSION = "rdf_robot_embodiment_adapter_v0.1.0"
ROBOT_EMBODIMENT_CONTRACT_PROOF_ID = "rdf_mvp1plus_cross_embodiment_recorded_log_adapter_proof_v0"
ROBOT_EMBODIMENT_CONTRACT_NAME = "mvp1plus_robot_embodiment_recorded_log_contract"
MVP1PLUS_TASK_NAME = "peg_in_hole_mvp1plus_cross_embodiment"
MVP1PLUS_TASK_ID = "task_mvp1plus_cross_embodiment"
MVP1PLUS_TRAJECTORY_SCHEMA_VERSION = "rdf_trajectory_v0.1.0"
MVP1PLUS_CURATION_SCHEMA_VERSION = "rdf_mvp1plus_curation_manifest_v0.1.0"
MVP1PLUS_PROJECTION_SCHEMA_VERSION = "rdf_mvp1plus_embodiment_projection_v0.1.0"
REQUIRED_CONTRACT_ROLES = {
    "teleop_intent",
    "executed_control",
    "learning_action",
    "retargeted_robot_action",
}
DISALLOWED_TRUTHY_CLAIM_KEYS = {
    "real_robot_success",
    "real_robot_success_claimed",
    "physical_robot_readiness",
    "physical_robot_readiness_claimed",
    "live_runtime_support",
    "live_runtime_support_claimed",
    "hmd_readiness",
    "hmd_readiness_claimed",
    "policy_uplift",
    "policy_uplift_claimed",
    "universal_robot_support",
    "universal_robot_support_claimed",
    "public_sample_import",
    "public_sample_import_claimed",
    "public_sample_evidence_claimed",
    "marketplace_readiness",
    "marketplace_readiness_claimed",
    "db_migration",
    "db_migration_claimed",
    "production_auth",
    "production_auth_claimed",
}


class RobotEmbodimentAdapterRegistryError(ValueError):
    """Raised when a robot embodiment adapter registry operation is invalid."""


@dataclass(frozen=True)
class RobotEmbodimentAdapterRegistryProfile:
    schema_version: str
    adapter_id: str
    adapter_name: str
    robot_family: str
    embodiment_class: str
    builder_class: type[RobotEmbodimentContractBuilder]
    adapter_class: type[RobotEmbodimentAdapter]
    capabilities: tuple[str, ...]
    limitations: tuple[str, ...]
    evidence_level: str
    claim_boundary: dict[str, bool]
    adapter_version: str
    rejection_reason: str
    generated_external_style_sample: bool = False

    def to_artifact(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "adapter_id": self.adapter_id,
            "adapter_name": self.adapter_name,
            "robot_family": self.robot_family,
            "embodiment_class": self.embodiment_class,
            "builder_class": self.builder_class.__name__,
            "adapter_class": self.adapter_class.__name__,
            "capabilities": list(self.capabilities),
            "limitations": list(self.limitations),
            "evidence_level": self.evidence_level,
            "claim_boundary": copy.deepcopy(self.claim_boundary),
            "adapter_version": self.adapter_version,
            "rejection_reason": self.rejection_reason,
            "generated_external_style_sample": self.generated_external_style_sample,
        }


@dataclass(frozen=True)
class RobotEmbodimentProjectionResult:
    passed: bool
    adapter_id: str
    projected_inputs: dict[str, Any]
    issues: list[str]


@dataclass(frozen=True)
class RobotEmbodimentAdapterEmissionResult:
    passed: bool
    proof: dict[str, Any]
    contract: dict[str, Any]
    projected_inputs: dict[str, Any]
    issues: list[str]


class UniversalRobotsUrExternalStyleContractBuilder(RobotEmbodimentContractBuilder):
    def __init__(self) -> None:
        super().__init__(
            adapter_id="universal_robots_ur_external_style",
            adapter_name="Universal Robots UR Generated External-Style Adapter",
            adapter_role="industrial_arm_generated_external_style_adapter",
            source_profile={
                "input_device": "recorded_command_state_log",
                "runtime": "generated_external_style_ur_command_state_log",
                "robot": "universal_robots_ur",
            },
            robot_embodiment_profile={
                "embodiment_class": "industrial_arm",
                "manipulator_family": "universal_robots_ur",
                "proof_role": "generated_external_style_industrial_arm",
            },
            command_state_stream_profile={
                "stream_id": "universal_robots_ur_generated_external_style_command_state_stream",
                "transport": "generated_external_style_command_state_log",
                "command_interface": "ur_script_like_pose_delta_fixture",
                "state_interface": "ur_rtde_like_state_snapshot_fixture",
            },
        )


class RobotEmbodimentAdapterRegistry:
    _profiles: dict[str, RobotEmbodimentAdapterRegistryProfile] = {}

    @classmethod
    def build_registry(
        cls,
        profiles: Iterable[RobotEmbodimentAdapterRegistryProfile],
    ) -> dict[str, RobotEmbodimentAdapterRegistryProfile]:
        registry: dict[str, RobotEmbodimentAdapterRegistryProfile] = {}
        for profile in profiles:
            if profile.adapter_id in registry:
                raise RobotEmbodimentAdapterRegistryError(
                    f"duplicate robot embodiment adapter {profile.adapter_id!r}"
                )
            registry[profile.adapter_id] = profile
        return registry

    @classmethod
    def list_profiles(cls) -> list[RobotEmbodimentAdapterRegistryProfile]:
        return list(cls._profiles.values())

    @classmethod
    def get(cls, adapter_id: str) -> RobotEmbodimentAdapterRegistryProfile:
        try:
            return cls._profiles[adapter_id]
        except KeyError as exc:
            raise RobotEmbodimentAdapterRegistryError(
                f"unknown robot embodiment adapter {adapter_id!r}"
            ) from exc

    @classmethod
    def create(
        cls,
        adapter_id: str,
        *,
        validator: NormalizedTrajectoryContractValidator | None = None,
    ) -> RobotEmbodimentAdapter:
        profile = cls.get(adapter_id)
        return profile.adapter_class(profile=profile, validator=validator)


class RobotEmbodimentAdapter:
    def __init__(
        self,
        *,
        profile: RobotEmbodimentAdapterRegistryProfile,
        validator: NormalizedTrajectoryContractValidator | None = None,
    ) -> None:
        self.profile = profile
        self.validator = validator or NormalizedTrajectoryContractValidator(
            proof_id=ROBOT_EMBODIMENT_CONTRACT_PROOF_ID,
            contract_name=ROBOT_EMBODIMENT_CONTRACT_NAME,
        )

    def project_source_evidence(
        self,
        *,
        source_dir: Path,
        output_dir: Path,
    ) -> RobotEmbodimentProjectionResult:
        read_result = self._read_source_evidence(source_dir)
        if read_result["issues"]:
            return RobotEmbodimentProjectionResult(
                passed=False,
                adapter_id=self.profile.adapter_id,
                projected_inputs={},
                issues=read_result["issues"],
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        trajectories_dir = output_dir / "trajectories"
        evaluations_dir = output_dir / "evaluations"
        trajectories_dir.mkdir(parents=True, exist_ok=True)
        evaluations_dir.mkdir(parents=True, exist_ok=True)

        metadata = read_result["metadata"]
        accepted_row = read_result["accepted_rows"][0]
        rejected_row = read_result["rejected_rows"][0]
        accepted_trajectory = _build_projected_trajectory(
            profile=self.profile,
            metadata=metadata,
            row=accepted_row,
            accepted=True,
        )
        rejected_trajectory = _build_projected_trajectory(
            profile=self.profile,
            metadata=metadata,
            row=rejected_row,
            accepted=False,
        )
        accepted_evaluation = _build_projected_evaluation(
            profile=self.profile,
            trajectory=accepted_trajectory,
            row=accepted_row,
            accepted=True,
        )
        rejected_evaluation = _build_projected_evaluation(
            profile=self.profile,
            trajectory=rejected_trajectory,
            row=rejected_row,
            accepted=False,
        )

        accepted_trajectory_path = trajectories_dir / f"{accepted_trajectory['id']}.json"
        rejected_trajectory_path = trajectories_dir / f"{rejected_trajectory['id']}.json"
        accepted_evaluation_path = evaluations_dir / f"{accepted_evaluation['id']}.json"
        rejected_evaluation_path = evaluations_dir / f"{rejected_evaluation['id']}.json"
        _write_json(accepted_trajectory_path, accepted_trajectory)
        _write_json(rejected_trajectory_path, rejected_trajectory)
        _write_json(accepted_evaluation_path, accepted_evaluation)
        _write_json(rejected_evaluation_path, rejected_evaluation)

        curation_manifest = _build_curation_manifest(
            profile=self.profile,
            accepted_trajectory=accepted_trajectory,
            accepted_evaluation=accepted_evaluation,
            rejected_trajectory=rejected_trajectory,
            rejected_evaluation=rejected_evaluation,
        )
        projection_manifest = {
            "schema_version": MVP1PLUS_PROJECTION_SCHEMA_VERSION,
            "adapter_id": self.profile.adapter_id,
            "projection_semantics": {
                "source_evidence": "JSONL + metadata command-state logs",
                "projected_artifact_shape": "RDF-compatible trajectory/evaluation/curation/export inputs",
                "raw_jsonl_is_direct_trainer_input": False,
                "rejected_logs_forced_through_learning_eligibility": False,
            },
            "source_log_paths": {
                "metadata_json": str(source_dir / "metadata.json"),
                "accepted_command_state_jsonl": str(source_dir / "accepted_command_state.jsonl"),
                "rejected_command_state_jsonl": str(source_dir / "rejected_command_state.jsonl"),
            },
            "accepted": {
                "trajectory": str(accepted_trajectory_path),
                "evaluation": str(accepted_evaluation_path),
                "learning_eligibility_candidate": True,
            },
            "rejected": {
                "trajectory": str(rejected_trajectory_path),
                "evaluation": str(rejected_evaluation_path),
                "learning_eligibility_candidate": False,
                "rejection_reason": self.profile.rejection_reason,
            },
            "curation_manifest": str(output_dir / "curation_manifest.json"),
            "split_manifest": str(output_dir / "split_manifest.json"),
        }
        projected_inputs = {
            "metadata": metadata,
            "source_log_paths": projection_manifest["source_log_paths"],
            "trajectories_dir": str(trajectories_dir),
            "evaluations_dir": str(evaluations_dir),
            "accepted_trajectory": str(accepted_trajectory_path),
            "accepted_evaluation": str(accepted_evaluation_path),
            "rejected_trajectory": str(rejected_trajectory_path),
            "rejected_evaluation": str(rejected_evaluation_path),
            "curation_manifest": str(output_dir / "curation_manifest.json"),
            "split_manifest": str(output_dir / "split_manifest.json"),
            "projection_manifest": str(output_dir / "projection_manifest.json"),
            "projection_semantics": projection_manifest["projection_semantics"],
            "accepted": projection_manifest["accepted"],
            "rejected": projection_manifest["rejected"],
        }
        _write_json(output_dir / "curation_manifest.json", curation_manifest)
        _write_json(output_dir / "split_manifest.json", _build_split_manifest([accepted_trajectory["episode_id"]]))
        _write_json(output_dir / "projection_manifest.json", projection_manifest)
        return RobotEmbodimentProjectionResult(
            passed=True,
            adapter_id=self.profile.adapter_id,
            projected_inputs=projected_inputs,
            issues=[],
        )

    def emit_contract(
        self,
        *,
        source_dir: Path,
        projected_dir: Path | None = None,
        projected_inputs: dict[str, Any] | None = None,
        export_artifacts: dict[str, Path | str] | None = None,
    ) -> RobotEmbodimentAdapterEmissionResult:
        uses_preprojected_inputs = projected_inputs is not None
        if not uses_preprojected_inputs:
            return _failed_emission_result(
                self.profile,
                ["preprojected inputs required for contract emission"],
            )
        identity_issues = _validate_projected_inputs_identity(
            projected_inputs or {},
            self.profile,
        )
        if identity_issues:
            return _failed_emission_result(
                self.profile,
                identity_issues,
                projected_inputs=projected_inputs,
            )
        projection = RobotEmbodimentProjectionResult(
            passed=True,
            adapter_id=self.profile.adapter_id,
            projected_inputs=copy.deepcopy(projected_inputs or {}),
            issues=[],
        )
        if export_artifacts is None:
            return _failed_emission_result(
                self.profile,
                ["export artifacts missing for contract validation"],
                projected_inputs=projection.projected_inputs,
            )

        artifacts = {key: Path(value) for key, value in export_artifacts.items()}
        contract_result = self.validator.build_from_artifacts(
            accepted_trajectory=Path(projection.projected_inputs["accepted_trajectory"]),
            accepted_evaluation=Path(projection.projected_inputs["accepted_evaluation"]),
            curation_manifest=Path(projection.projected_inputs["curation_manifest"]),
            hdf5_path=artifacts["hdf5_export"],
            trainer_smoke_report=artifacts["trainer_smoke_report"],
        )
        projected_source_profile = copy.deepcopy(contract_result.contract.get("source_profile") or {})
        builder = self.profile.builder_class()
        emission = builder.build_contract(contract_result.contract)
        contract = emission.contract
        builder_source_profile = copy.deepcopy(
            (contract["robot_embodiment_adapter_evidence"].get("source_provenance") or {}).get(
                "builder_source_profile",
                {},
            )
        )
        contract["source_profile"] = projected_source_profile
        evidence = contract["robot_embodiment_adapter_evidence"]
        metadata = projection.projected_inputs["metadata"]
        evidence["fixture_basis"] = "recorded_log_backed_robot_embodiment_adapter"
        evidence["source_provenance"] = {
            "projected_source_profile": projected_source_profile,
            "builder_source_profile": builder_source_profile,
            "source_evidence_level": self.profile.evidence_level,
            "source_logs": copy.deepcopy(projection.projected_inputs["source_log_paths"]),
            "projection_manifest": projection.projected_inputs["projection_manifest"],
            "generated_external_style_sample": self.profile.generated_external_style_sample,
        }
        evidence["replay_consistency_evidence"]["evidence_level"] = "recorded_log_projection_consistency"
        evidence["curation_evidence"] = _read_json(Path(projection.projected_inputs["curation_manifest"]))
        evidence["projection_evidence"] = {
            "projected_from_jsonl_metadata": True,
            "raw_jsonl_direct_trainer_input": False,
            "projected_inputs": copy.deepcopy(projection.projected_inputs),
        }
        evidence["claim_boundary"] = copy.deepcopy(metadata["claim_boundary"])
        evidence["limitations"] = list(metadata["limitations"])
        evidence["adapter_call_evidence"] = {
            "registry_lookup_performed": True,
            "adapter_id": self.profile.adapter_id,
            "adapter_class": self.profile.adapter_class.__name__,
            "builder_class": self.profile.builder_class.__name__,
            "builder_called": True,
            "validator_checked": True,
            "projected_from_jsonl_metadata": True,
            "uses_preprojected_inputs": uses_preprojected_inputs,
            "raw_jsonl_direct_trainer_input": False,
            "contract_built_from_projected_inputs": True,
            "fixture_clone_prevention": "builder_emission_from_projected_recorded_command_state_logs",
        }

        ingress_issues = self.validator.validate_ingress_contract(contract)
        learning_issues = self.validator.validate_learning_eligibility(contract)
        issues = _dedupe([*contract_result.issues, *ingress_issues, *learning_issues])
        proof = {
            "schema_version": ROBOT_EMBODIMENT_ADAPTER_PROOF_SCHEMA_VERSION,
            "adapter_id": self.profile.adapter_id,
            "registry_lookup": self.profile.to_artifact(),
            "adapter_call": copy.deepcopy(evidence["adapter_call_evidence"]),
            "contract_builder": copy.deepcopy(emission.contract_builder),
            "contract_emitter": copy.deepcopy(emission.contract_emitter),
            "projected_inputs": copy.deepcopy(projection.projected_inputs),
            "curation_evidence": copy.deepcopy(evidence["curation_evidence"]),
            "export_trainer_evidence": {
                "hdf5_export_exists": artifacts["hdf5_export"].exists(),
                "trainer_smoke_passed": _read_json(artifacts["trainer_smoke_report"]).get("passed") is True,
                "uses_projected_inputs": True,
            },
            "claim_boundary": copy.deepcopy(metadata["claim_boundary"]),
            "ingress_passed": not ingress_issues,
            "learning_eligibility_passed": not learning_issues,
            "issues": list(issues),
            "contract": contract,
            "limitations": list(metadata["limitations"]),
        }
        return RobotEmbodimentAdapterEmissionResult(
            passed=not issues,
            proof=proof,
            contract=contract,
            projected_inputs=projection.projected_inputs,
            issues=list(issues),
        )

    def _read_source_evidence(self, source_dir: Path) -> dict[str, Any]:
        required = {
            "metadata": source_dir / "metadata.json",
            "accepted": source_dir / "accepted_command_state.jsonl",
            "rejected": source_dir / "rejected_command_state.jsonl",
        }
        missing = [str(path.name) for path in required.values() if not path.exists()]
        if missing:
            return {
                "metadata": {},
                "accepted_rows": [],
                "rejected_rows": [],
                "issues": [f"missing source evidence: {', '.join(missing)}"],
            }
        try:
            metadata = _read_json(required["metadata"])
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            return {
                "metadata": {},
                "accepted_rows": [],
                "rejected_rows": [],
                "issues": [f"invalid metadata json: {exc}"],
            }
        accepted_rows, accepted_issues = _read_jsonl(required["accepted"], label="accepted jsonl")
        rejected_rows, rejected_issues = _read_jsonl(required["rejected"], label="rejected jsonl")
        issues = [*accepted_issues, *rejected_issues]
        if not accepted_rows:
            issues.append("accepted source evidence empty")
        if not rejected_rows:
            issues.append("rejected source evidence empty")
        if metadata.get("adapter_id") != self.profile.adapter_id:
            issues.append(f"metadata adapter_id mismatch: expected {self.profile.adapter_id}")
        issues.extend(_validate_metadata(metadata, self.profile))
        for index, row in enumerate(accepted_rows, start=1):
            issues.extend(_validate_source_row(row, metadata, self.profile, label=f"accepted jsonl row {index}", accepted=True))
        for index, row in enumerate(rejected_rows, start=1):
            issues.extend(_validate_source_row(row, metadata, self.profile, label=f"rejected jsonl row {index}", accepted=False))
        return {
            "metadata": metadata,
            "accepted_rows": accepted_rows,
            "rejected_rows": rejected_rows,
            "issues": issues,
        }


def _claim_boundary() -> dict[str, bool]:
    return {
        "real_robot_success_claimed": False,
        "physical_robot_readiness_claimed": False,
        "live_runtime_support_claimed": False,
        "hmd_readiness_claimed": False,
        "policy_uplift_claimed": False,
        "universal_robot_support_claimed": False,
        "public_sample_evidence_claimed": False,
    }


def _profile(
    *,
    adapter_id: str,
    adapter_name: str,
    robot_family: str,
    embodiment_class: str,
    builder_class: type[RobotEmbodimentContractBuilder],
    capabilities: tuple[str, ...],
    limitations: tuple[str, ...],
    evidence_level: str,
    rejection_reason: str,
    generated_external_style_sample: bool = False,
) -> RobotEmbodimentAdapterRegistryProfile:
    return RobotEmbodimentAdapterRegistryProfile(
        schema_version=ROBOT_EMBODIMENT_ADAPTER_REGISTRY_SCHEMA_VERSION,
        adapter_id=adapter_id,
        adapter_name=adapter_name,
        robot_family=robot_family,
        embodiment_class=embodiment_class,
        builder_class=builder_class,
        adapter_class=RobotEmbodimentAdapter,
        capabilities=capabilities,
        limitations=limitations,
        evidence_level=evidence_level,
        claim_boundary=_claim_boundary(),
        adapter_version=ROBOT_EMBODIMENT_ADAPTER_VERSION,
        rejection_reason=rejection_reason,
        generated_external_style_sample=generated_external_style_sample,
    )


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_stable_json(payload) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return data


def _read_jsonl(path: Path, *, label: str) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    issues: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        return [], [f"{label} unreadable: {exc}"]
    for index, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            issues.append(f"{label} line {index} invalid json: {exc}")
            continue
        if not isinstance(row, dict):
            issues.append(f"{label} line {index} not object")
            continue
        rows.append(row)
    return rows, issues


def _is_numeric(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    return isinstance(value, int | float)


def _numeric_vector(value: Any, *, min_len: int, max_len: int | None = None) -> bool:
    if not isinstance(value, list) or len(value) < min_len:
        return False
    if max_len is not None and len(value) > max_len:
        return False
    return all(_is_numeric(item) for item in value)


def _validate_metadata(
    metadata: dict[str, Any],
    profile: RobotEmbodimentAdapterRegistryProfile,
) -> list[str]:
    issues: list[str] = []
    for key in (
        "adapter_version",
        "robot_family",
        "embodiment_class",
        "command_state_interface",
        "state_interface",
        "coordinate_frames",
        "evidence_level",
        "source_provenance",
        "claim_boundary",
        "limitations",
    ):
        if not metadata.get(key):
            issues.append(f"metadata.{key} missing")
    issues.extend(_validate_metadata_identity(metadata, profile))
    issues.extend(_validate_metadata_claims(metadata, profile))
    return issues


def _validate_metadata_identity(
    metadata: dict[str, Any],
    profile: RobotEmbodimentAdapterRegistryProfile,
) -> list[str]:
    issues: list[str] = []
    command_profile = profile.builder_class().command_state_stream_profile
    if metadata.get("adapter_version") != profile.adapter_version:
        issues.append("metadata.adapter_version mismatch")
    if metadata.get("robot_family") != profile.robot_family:
        issues.append(f"metadata.robot_family mismatch: expected {profile.robot_family}")
    if metadata.get("embodiment_class") != profile.embodiment_class:
        issues.append(f"metadata.embodiment_class mismatch: expected {profile.embodiment_class}")
    if metadata.get("evidence_level") != profile.evidence_level:
        issues.append(f"metadata.evidence_level mismatch: expected {profile.evidence_level}")
    if metadata.get("command_state_interface") != command_profile["command_interface"]:
        issues.append("metadata.command_state_interface mismatch")
    if metadata.get("command_state_transport") != command_profile["transport"]:
        issues.append("metadata.command_state_transport mismatch")
    if metadata.get("state_interface") != command_profile["state_interface"]:
        issues.append("metadata.state_interface mismatch")
    return issues


def _validate_metadata_claims(
    metadata: dict[str, Any],
    profile: RobotEmbodimentAdapterRegistryProfile,
) -> list[str]:
    issues: list[str] = []
    claim_boundary = metadata.get("claim_boundary")
    if not isinstance(claim_boundary, dict) or claim_boundary != profile.claim_boundary:
        issues.append("metadata.claim_boundary mismatch")
    if isinstance(claim_boundary, dict):
        issues.extend(_validate_no_truthy_claims(claim_boundary, "metadata.claim_boundary"))
    issues.extend(_validate_no_truthy_claims(metadata, "metadata"))
    issues.extend(_validate_source_provenance_claims(metadata, profile))
    if metadata.get("public_sample_evidence_claimed") is not False:
        issues.append("metadata.public_sample_evidence_claimed not false")
    if metadata.get("generated_external_style_sample") is not profile.generated_external_style_sample:
        issues.append("metadata.generated_external_style_sample mismatch")
    return issues


def _validate_no_truthy_claims(data: dict[str, Any], label: str) -> list[str]:
    return [
        f"{label}.{key} must be false"
        for key, value in sorted(data.items())
        if key in DISALLOWED_TRUTHY_CLAIM_KEYS and value is True
    ]


def _validate_source_provenance_claims(
    metadata: dict[str, Any],
    profile: RobotEmbodimentAdapterRegistryProfile,
) -> list[str]:
    source_provenance = metadata.get("source_provenance")
    if not isinstance(source_provenance, dict):
        return ["metadata.source_provenance missing"]
    issues = _validate_no_truthy_claims(source_provenance, "metadata.source_provenance")
    if source_provenance.get("recorded_log_backed") is not True:
        issues.append("metadata.source_provenance.recorded_log_backed not true")
    if source_provenance.get("public_sample_evidence_claimed") is not False:
        issues.append("metadata.source_provenance.public_sample_evidence_claimed not false")
    if source_provenance.get("generated_external_style_sample") is not profile.generated_external_style_sample:
        issues.append("metadata.source_provenance.generated_external_style_sample mismatch")
    return issues


def _validate_projected_inputs_identity(
    projected_inputs: dict[str, Any],
    profile: RobotEmbodimentAdapterRegistryProfile,
) -> list[str]:
    issues: list[str] = []
    metadata = projected_inputs.get("metadata")
    if not isinstance(metadata, dict) or metadata.get("adapter_id") != profile.adapter_id:
        issues.append("projected_inputs.metadata.adapter_id mismatch")
    accepted_trajectory, accepted_evaluation, accepted_issues = _validate_projected_artifact_pair(
        projected_inputs,
        profile,
        status="accepted",
        expected_success=True,
    )
    rejected_trajectory, rejected_evaluation, rejected_issues = _validate_projected_artifact_pair(
        projected_inputs,
        profile,
        status="rejected",
        expected_success=False,
    )
    issues.extend(accepted_issues)
    issues.extend(rejected_issues)
    issues.extend(
        _validate_projected_manifest_links(
            projected_inputs,
            profile,
            accepted_trajectory=accepted_trajectory,
            accepted_evaluation=accepted_evaluation,
            rejected_trajectory=rejected_trajectory,
            rejected_evaluation=rejected_evaluation,
        )
    )
    return issues


def _validate_projected_artifact_pair(
    projected_inputs: dict[str, Any],
    profile: RobotEmbodimentAdapterRegistryProfile,
    *,
    status: str,
    expected_success: bool,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, list[str]]:
    trajectory, trajectory_issues = _read_projected_input_json(
        projected_inputs,
        key=f"{status}_trajectory",
    )
    evaluation, evaluation_issues = _read_projected_input_json(
        projected_inputs,
        key=f"{status}_evaluation",
    )
    issues = [*trajectory_issues, *evaluation_issues]
    if trajectory is not None:
        issues.extend(_validate_projected_trajectory(trajectory, profile, status=status))
    if trajectory is not None and evaluation is not None:
        issues.extend(
            _validate_projected_evaluation(
                evaluation,
                trajectory,
                profile,
                status=status,
                expected_success=expected_success,
            )
        )
    return trajectory, evaluation, issues


def _read_projected_input_json(
    projected_inputs: dict[str, Any],
    *,
    key: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    path = projected_inputs.get(key)
    if not path:
        return None, [f"projected_inputs.{key} missing"]
    try:
        return _read_json(Path(path)), []
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return None, [f"projected_inputs.{key} invalid: {exc}"]


def _validate_projected_trajectory(
    trajectory: dict[str, Any],
    profile: RobotEmbodimentAdapterRegistryProfile,
    *,
    status: str,
) -> list[str]:
    issues: list[str] = []
    label = f"projected_inputs.{status}_trajectory"
    expected_prefix = f"mvp1plus_{profile.adapter_id}_{status}_"
    if not str(trajectory.get("id") or "").startswith(expected_prefix):
        issues.append(f"{label}.id mismatch")
    if not str(trajectory.get("episode_id") or "").startswith(expected_prefix):
        issues.append(f"{label}.episode_id mismatch")
    source = trajectory.get("source")
    if not isinstance(source, dict) or source.get("adapter_id") != profile.adapter_id:
        issues.append(f"{label}.source.adapter_id mismatch")
    return issues


def _validate_projected_evaluation(
    evaluation: dict[str, Any],
    trajectory: dict[str, Any],
    profile: RobotEmbodimentAdapterRegistryProfile,
    *,
    status: str,
    expected_success: bool,
) -> list[str]:
    issues: list[str] = []
    label = f"projected_inputs.{status}_evaluation"
    expected_prefix = f"mvp1plus_{profile.adapter_id}_{status}_"
    if not str(evaluation.get("id") or "").startswith(expected_prefix):
        issues.append(f"{label}.id mismatch")
    if evaluation.get("trajectory_id") != trajectory.get("id"):
        issues.append(f"{label}.trajectory_id mismatch")
    if evaluation.get("episode_id") != trajectory.get("episode_id"):
        issues.append(f"{label}.episode_id mismatch")
    if evaluation.get("success") is not expected_success:
        issues.append(f"{label}.success mismatch")
    if not expected_success and evaluation.get("failure_reason") != profile.rejection_reason:
        issues.append(f"{label}.failure_reason mismatch")
    return issues


def _validate_projected_manifest_links(
    projected_inputs: dict[str, Any],
    profile: RobotEmbodimentAdapterRegistryProfile,
    *,
    accepted_trajectory: dict[str, Any] | None,
    accepted_evaluation: dict[str, Any] | None,
    rejected_trajectory: dict[str, Any] | None,
    rejected_evaluation: dict[str, Any] | None,
) -> list[str]:
    issues: list[str] = []
    issues.extend(
        _validate_curation_manifest_links(
            projected_inputs,
            profile,
            accepted_trajectory=accepted_trajectory,
            accepted_evaluation=accepted_evaluation,
            rejected_trajectory=rejected_trajectory,
            rejected_evaluation=rejected_evaluation,
        )
    )
    issues.extend(
        _validate_split_manifest_links(
            projected_inputs,
            accepted_trajectory=accepted_trajectory,
        )
    )
    issues.extend(_validate_projection_manifest_links(projected_inputs, profile))
    return issues


def _validate_curation_manifest_links(
    projected_inputs: dict[str, Any],
    profile: RobotEmbodimentAdapterRegistryProfile,
    *,
    accepted_trajectory: dict[str, Any] | None,
    accepted_evaluation: dict[str, Any] | None,
    rejected_trajectory: dict[str, Any] | None,
    rejected_evaluation: dict[str, Any] | None,
) -> list[str]:
    curation, issues = _read_projected_input_json(projected_inputs, key="curation_manifest")
    if curation is None:
        return issues
    if curation.get("adapter_id") != profile.adapter_id:
        issues.append("projected_inputs.curation_manifest.adapter_id mismatch")
    issues.extend(
        _validate_curation_item(
            curation,
            section="accepted",
            trajectory=accepted_trajectory,
            evaluation=accepted_evaluation,
        )
    )
    issues.extend(
        _validate_curation_item(
            curation,
            section="rejected",
            trajectory=rejected_trajectory,
            evaluation=rejected_evaluation,
        )
    )
    if curation.get("rejection_reason_distribution") != {profile.rejection_reason: 1}:
        issues.append("projected_inputs.curation_manifest.rejection_reason_distribution mismatch")
    return issues


def _validate_curation_item(
    curation: dict[str, Any],
    *,
    section: str,
    trajectory: dict[str, Any] | None,
    evaluation: dict[str, Any] | None,
) -> list[str]:
    items = curation.get(section)
    if not isinstance(items, list) or len(items) != 1:
        return [f"projected_inputs.curation_manifest.{section} mismatch"]
    item = items[0]
    issues: list[str] = []
    if trajectory is not None and ((item.get("trajectory") or {}).get("id") != trajectory.get("id")):
        issues.append(f"projected_inputs.curation_manifest.{section}.trajectory.id mismatch")
    if evaluation is not None and ((item.get("evaluation") or {}).get("id") != evaluation.get("id")):
        issues.append(f"projected_inputs.curation_manifest.{section}.evaluation.id mismatch")
    return issues


def _validate_split_manifest_links(
    projected_inputs: dict[str, Any],
    *,
    accepted_trajectory: dict[str, Any] | None,
) -> list[str]:
    split, issues = _read_projected_input_json(projected_inputs, key="split_manifest")
    if split is None or accepted_trajectory is None:
        return issues
    train = ((split.get("splits") or {}).get("train") or [])
    if train != [accepted_trajectory.get("episode_id")]:
        issues.append("projected_inputs.split_manifest.train mismatch")
    return issues


def _validate_projection_manifest_links(
    projected_inputs: dict[str, Any],
    profile: RobotEmbodimentAdapterRegistryProfile,
) -> list[str]:
    projection, issues = _read_projected_input_json(projected_inputs, key="projection_manifest")
    if projection is None:
        return issues
    if projection.get("adapter_id") != profile.adapter_id:
        issues.append("projected_inputs.projection_manifest.adapter_id mismatch")
    for section in ("accepted", "rejected"):
        expected = projected_inputs.get(section) or {}
        actual = projection.get(section) or {}
        for artifact in ("trajectory", "evaluation"):
            if expected.get(artifact) and not _same_path(actual.get(artifact), expected.get(artifact)):
                issues.append(f"projected_inputs.projection_manifest.{section}.{artifact} mismatch")
    if not _same_path(projection.get("curation_manifest"), projected_inputs.get("curation_manifest")):
        issues.append("projected_inputs.projection_manifest.curation_manifest mismatch")
    if not _same_path(projection.get("split_manifest"), projected_inputs.get("split_manifest")):
        issues.append("projected_inputs.projection_manifest.split_manifest mismatch")
    return issues


def _same_path(left: Any, right: Any) -> bool:
    if not left or not right:
        return False
    try:
        return Path(left).resolve() == Path(right).resolve()
    except (OSError, TypeError, ValueError):
        return str(left) == str(right)


def _validate_source_row(
    row: dict[str, Any],
    metadata: dict[str, Any],
    profile: RobotEmbodimentAdapterRegistryProfile,
    *,
    label: str,
    accepted: bool,
) -> list[str]:
    issues: list[str] = []
    if not _is_numeric(row.get("timestamp")):
        issues.append(f"{label} timestamp missing")
    if not _is_numeric(row.get("sequence_id")):
        issues.append(f"{label} sequence_id missing")
    issues.extend(_validate_command_row(row, metadata, label=label))
    issues.extend(_validate_state_row(row, metadata, label=label))
    issues.extend(_validate_action_semantics_row(row, label=label))
    issues.extend(_validate_quality_row(row, profile, label=label, accepted=accepted))
    return issues


def _validate_command_row(
    row: dict[str, Any],
    metadata: dict[str, Any],
    *,
    label: str,
) -> list[str]:
    issues: list[str] = []
    command = row.get("command")
    if not isinstance(command, dict):
        issues.append(f"{label} command missing")
        issues.append(f"{label} command.vector missing")
        issues.append(f"{label} command.unit missing")
        return issues
    if command.get("interface") != metadata.get("command_state_interface"):
        issues.append(f"{label} command.interface mismatch")
    if not _numeric_vector(command.get("vector"), min_len=4, max_len=12):
        issues.append(f"{label} command.vector missing")
    if not command.get("unit"):
        issues.append(f"{label} command.unit missing")
    return issues


def _validate_state_row(
    row: dict[str, Any],
    metadata: dict[str, Any],
    *,
    label: str,
) -> list[str]:
    issues: list[str] = []
    state = row.get("state")
    if not isinstance(state, dict):
        issues.append(f"{label} state missing")
        return issues
    if state.get("interface") != metadata.get("state_interface"):
        issues.append(f"{label} state.interface mismatch")
    for key, min_len, max_len in (
        ("end_effector_position", 3, 3),
        ("end_effector_quaternion", 4, 4),
        ("object_position", 3, 3),
        ("object_quaternion", 4, 4),
        ("joint_positions", 1, 16),
    ):
        if not _numeric_vector(state.get(key), min_len=min_len, max_len=max_len):
            issues.append(f"{label} state.{key} missing")
    return issues


def _validate_action_semantics_row(
    row: dict[str, Any],
    *,
    label: str,
) -> list[str]:
    issues: list[str] = []
    semantics = row.get("action_semantics")
    if not isinstance(semantics, dict):
        issues.append(f"{label} action_semantics missing")
        return issues
    if semantics.get("representation") != "robot_delta_ee_pose":
        issues.append(f"{label} action_semantics.representation mismatch")
    if not semantics.get("coordinate_frame"):
        issues.append(f"{label} action_semantics.coordinate_frame missing")
    roles = set(semantics.get("normalized_contract_roles") or [])
    missing_roles = sorted(REQUIRED_CONTRACT_ROLES - roles)
    if missing_roles:
        issues.append(
            f"{label} action_semantics.normalized_contract_roles missing: {', '.join(missing_roles)}"
        )
    return issues


def _validate_quality_row(
    row: dict[str, Any],
    profile: RobotEmbodimentAdapterRegistryProfile,
    *,
    label: str,
    accepted: bool,
) -> list[str]:
    issues: list[str] = []
    quality = row.get("quality")
    if not isinstance(quality, dict):
        issues.append(f"{label} quality missing")
        if not accepted:
            issues.append(f"{label} quality.rejection_reason mismatch")
        return issues
    expected_bool = bool(accepted)
    if quality.get("replay_verified") is not expected_bool:
        issues.append(f"{label} quality.replay_verified mismatch")
    if quality.get("action_contract_valid") is not expected_bool:
        issues.append(f"{label} quality.action_contract_valid mismatch")
    expected_quality = "pass" if accepted else "fail"
    if quality.get("control_quality") != expected_quality:
        issues.append(f"{label} quality.control_quality mismatch")
    if not accepted and quality.get("rejection_reason") != profile.rejection_reason:
        issues.append(f"{label} quality.rejection_reason mismatch")
    return issues


def _action_role(command: list[float], *, role: str, source: str) -> dict[str, Any]:
    return {
        "role": role,
        "source": source,
        "representation": "robot_delta_ee_pose",
        "coordinate_frame": "task_frame",
        "command": list(command),
        "dataset_semantics": "candidate_learning_action_after_projection_and_curation",
    }


def _build_projected_trajectory(
    *,
    profile: RobotEmbodimentAdapterRegistryProfile,
    metadata: dict[str, Any],
    row: dict[str, Any],
    accepted: bool,
) -> dict[str, Any]:
    status = "accepted" if accepted else "rejected"
    trajectory_id = f"mvp1plus_{profile.adapter_id}_{status}_trajectory"
    episode_id = f"mvp1plus_{profile.adapter_id}_{status}_episode"
    command = [float(value) for value in row["command"]["vector"]]
    state = row["state"]
    frame = {
        "t": float(row["timestamp"]),
        "step": int(row["sequence_id"]),
        "end_effector_position": state["end_effector_position"],
        "end_effector_quaternion": state["end_effector_quaternion"],
        "object_position": state["object_position"],
        "object_quaternion": state["object_quaternion"],
        "metadata": {
            "command_state_row": copy.deepcopy(row),
            "robot_family": profile.robot_family,
            "embodiment_class": profile.embodiment_class,
            "raw_xr": {"right_wrist_pose": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]},
            "aligned_xr": {"right_wrist_pose": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]},
            "exporter_compatibility_placeholders": {
                "raw_xr_right_wrist_pose": "zero_pose_exporter_compatibility_only",
                "aligned_xr_right_wrist_pose": "zero_pose_exporter_compatibility_only",
                "hmd_readiness_evidence": False,
            },
            "cube_states": {"object_position": state["object_position"]},
            "retargeted": {"robot_action": command},
        },
        "action": {
            "raw": command,
            "action_contract_version": "rdf_action_contract_v0.1.0",
            "replay_contract_version": "rdf_replay_contract_v0.1.0",
            "teleop_intent": _action_role(command, role="operator_intent", source="recorded_command_state_log"),
            "executed_control": _action_role(command, role="robot_control_command", source="projected_command_state"),
            "learning_action": _action_role(
                command,
                role="candidate_robot_action_for_learning",
                source="projected_command_state",
            ),
            "retargeted_robot_action": _action_role(
                command,
                role="robot_action_for_replay_comparison",
                source="projected_command_state",
            ),
        },
    }
    return {
        "schema_version": MVP1PLUS_TRAJECTORY_SCHEMA_VERSION,
        "id": trajectory_id,
        "episode_id": episode_id,
        "task_id": MVP1PLUS_TASK_ID,
        "source": {
            "input_device": "recorded_command_state_log",
            "runtime": metadata["command_state_interface"],
            "simulator": "recorded_log_projection",
            "robot": profile.robot_family,
            "task_name": MVP1PLUS_TASK_NAME,
            "adapter_id": profile.adapter_id,
            "evidence_level": profile.evidence_level,
        },
        "frames": [frame],
        "summary": {
            "episode_status": "success" if accepted else "failure",
            "action_replay_gate": {
                "passed": accepted,
                "checked": True,
                "source": "projected_command_state_consistency",
            },
            "projection_boundary": "jsonl_metadata_projected_to_rdf_trajectory",
            "learning_eligibility_candidate": accepted,
        },
    }


def _build_projected_evaluation(
    *,
    profile: RobotEmbodimentAdapterRegistryProfile,
    trajectory: dict[str, Any],
    row: dict[str, Any],
    accepted: bool,
) -> dict[str, Any]:
    reason = profile.rejection_reason
    return {
        "schema_version": "rdf_evaluation_v0.1.0",
        "id": f"{trajectory['id']}_evaluation",
        "trajectory_id": trajectory["id"],
        "episode_id": trajectory["episode_id"],
        "success": accepted,
        "failure_reason": None if accepted else reason,
        "metrics": {
            "data_quality": {
                "replay_verified": accepted,
                "action_contract_status": "pass" if accepted else "fail",
                "action_contract_valid": accepted,
                "control_quality": "pass" if accepted else "fail",
                "quality_failure_reasons": [] if accepted else [reason],
                "timestamp_gap_detected": row.get("quality", {}).get("timestamp_gap_detected", False),
            },
            "projection": {
                "projected_from_jsonl_metadata": True,
                "raw_jsonl_direct_trainer_input": False,
            },
        },
    }


def _build_curation_manifest(
    *,
    profile: RobotEmbodimentAdapterRegistryProfile,
    accepted_trajectory: dict[str, Any],
    accepted_evaluation: dict[str, Any],
    rejected_trajectory: dict[str, Any],
    rejected_evaluation: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": MVP1PLUS_CURATION_SCHEMA_VERSION,
        "adapter_id": profile.adapter_id,
        "accepted_count": 1,
        "rejected_count": 1,
        "curation_rules": [
            "replay_action_gate_passed",
            "data_quality_gate_passed",
            "action_contract_valid",
            "export_trainer_gate_required_for_learning_ready",
        ],
        "accepted": [
            {
                "trajectory": {"id": accepted_trajectory["id"]},
                "evaluation": {"id": accepted_evaluation["id"]},
                "reasons": ["accepted_projected_command_state_contract"],
                "learning_eligibility_candidate": True,
            }
        ],
        "rejected": [
            {
                "trajectory": {"id": rejected_trajectory["id"]},
                "evaluation": {"id": rejected_evaluation["id"]},
                "reasons": [profile.rejection_reason],
                "buyer_readable_reason": _buyer_readable_rejection_reason(profile.rejection_reason),
                "evidence_fields": [
                    "evaluation.metrics.data_quality.quality_failure_reasons",
                    "curation_manifest.rejected[].reasons",
                ],
                "learning_eligibility_candidate": False,
            }
        ],
        "rejection_reason_distribution": {profile.rejection_reason: 1},
    }


def _build_split_manifest(episode_ids: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "rdf_split_manifest_v0.1.0",
        "task_id": MVP1PLUS_TASK_ID,
        "strategy": "mvp1plus_single_adapter_projection_split",
        "splits": {
            "train": list(episode_ids),
            "validation": [],
            "test": [],
        },
    }


def _buyer_readable_rejection_reason(reason: str) -> str:
    labels = {
        "ACTION_SATURATION_OR_CONTROL_QUALITY_FAILURE": "Action saturation or control-quality evidence made this trajectory unsuitable for training.",
        "COMMAND_STATE_TIMESTAMP_GAP": "The command-state stream had a timestamp gap, so temporal consistency was not trustworthy.",
        "INDUSTRIAL_ACTION_CONTRACT_MISMATCH": "The industrial-arm command did not satisfy the normalized action contract.",
    }
    return labels.get(reason, reason.replace("_", " ").lower())


def _failed_emission_result(
    profile: RobotEmbodimentAdapterRegistryProfile,
    issues: list[str],
    *,
    projected_inputs: dict[str, Any] | None = None,
) -> RobotEmbodimentAdapterEmissionResult:
    return RobotEmbodimentAdapterEmissionResult(
        passed=False,
        proof={
            "schema_version": ROBOT_EMBODIMENT_ADAPTER_PROOF_SCHEMA_VERSION,
            "adapter_id": profile.adapter_id,
            "registry_lookup": profile.to_artifact(),
            "issues": list(issues),
        },
        contract={},
        projected_inputs=copy.deepcopy(projected_inputs or {}),
        issues=list(issues),
    )


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if value not in seen:
            output.append(value)
            seen.add(value)
    return output


RobotEmbodimentAdapterRegistry._profiles = RobotEmbodimentAdapterRegistry.build_registry(
    [
        _profile(
            adapter_id="franka_research_arm",
            adapter_name="Franka Research-Arm Adapter",
            robot_family="franka",
            embodiment_class="research_arm",
            builder_class=FrankaContractBuilder,
            capabilities=("recorded_command_state_projection", "normalized_contract_emission"),
            limitations=("Generated recorded/log-backed evidence only.", "No physical Franka readiness claimed."),
            evidence_level="generated_recorded_log",
            rejection_reason="ACTION_SATURATION_OR_CONTROL_QUALITY_FAILURE",
        ),
        _profile(
            adapter_id="robotis_sh5_ros2_dds",
            adapter_name="ROBOTIS SH5 / ROS2-DDS Adapter",
            robot_family="robotis_sh5",
            embodiment_class="ros2_dds_manipulator",
            builder_class=RobotisSh5Ros2DdsContractBuilder,
            capabilities=("ros2_dds_command_state_projection", "normalized_contract_emission"),
            limitations=("Generated ROS2/DDS-style log evidence only.", "No live ROS2/DDS runtime claimed."),
            evidence_level="generated_ros2_dds_style_recorded_log",
            rejection_reason="COMMAND_STATE_TIMESTAMP_GAP",
        ),
        _profile(
            adapter_id="universal_robots_ur_industrial_arm",
            adapter_name="Universal Robots UR Industrial-Arm Adapter",
            robot_family="universal_robots_ur",
            embodiment_class="industrial_arm",
            builder_class=UniversalRobotsUrContractBuilder,
            capabilities=("industrial_command_state_projection", "normalized_contract_emission"),
            limitations=("Generated UR-style command-state evidence only.", "No UR/RTDE runtime claimed."),
            evidence_level="generated_recorded_log",
            rejection_reason="INDUSTRIAL_ACTION_CONTRACT_MISMATCH",
        ),
        _profile(
            adapter_id="universal_robots_ur_external_style",
            adapter_name="Universal Robots UR Generated External-Style Adapter",
            robot_family="universal_robots_ur",
            embodiment_class="industrial_arm",
            builder_class=UniversalRobotsUrExternalStyleContractBuilder,
            capabilities=("generated_external_style_projection", "normalized_contract_emission"),
            limitations=(
                "Generated external-style sample only.",
                "No public sample import or public dataset evidence claimed.",
            ),
            evidence_level="generated_external_style_sample",
            rejection_reason="INDUSTRIAL_ACTION_CONTRACT_MISMATCH",
            generated_external_style_sample=True,
        ),
    ]
)
