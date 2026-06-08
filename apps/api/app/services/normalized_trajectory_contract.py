from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Callable


TRAJECTORY_CONTRACT_SCHEMA_VERSION = "rdf_normalized_trajectory_contract_v0.1.0"
DEFAULT_CONTRACT_NAME = "hmd_free_robot_action_trajectory_contract"
DEFAULT_REQUIRED_SOURCE_FIELDS = ["input_device", "runtime", "simulator", "robot", "task_name"]
REQUIRED_ACTION_ROLE_KEYS = ("teleop_intent", "executed_control", "learning_action", "retargeted_robot_action")
REQUIRED_ACTION_ROLE_FIELDS = ("role", "source", "representation", "coordinate_frame")
NORMALIZED_TRAJECTORY_CONTRACT_FIELD_PATHS = [
    "trajectory.schema_version",
    "trajectory.source.input_device",
    "trajectory.source.runtime",
    "trajectory.source.simulator",
    "trajectory.source.robot",
    "trajectory.source.task_name",
    "trajectory.frames[].action.teleop_intent",
    "trajectory.frames[].action.executed_control",
    "trajectory.frames[].action.learning_action",
    "trajectory.frames[].action.retargeted_robot_action",
    "trajectory.summary.action_replay_gate",
    "evaluation.metrics.data_quality",
    "curation_manifest.accepted",
    "curation_manifest.rejected",
    "trainer_smoke_report.passed",
]


@dataclass(frozen=True)
class NormalizedTrajectoryContractResult:
    passed: bool
    contract: dict[str, Any]
    issues: list[str]


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    return data


def _first_frame_action(trajectory: dict[str, Any]) -> dict[str, Any]:
    for frame in trajectory.get("frames", []):
        if isinstance(frame, dict) and isinstance(frame.get("action"), dict):
            return frame["action"]
    return {}


def _action_role_contract(action: dict[str, Any], key: str) -> dict[str, Any]:
    payload = action.get(key)
    if not isinstance(payload, dict):
        return {
            "role": None,
            "source": None,
            "representation": None,
            "coordinate_frame": None,
        }
    return {
        "role": payload.get("role"),
        "source": payload.get("source"),
        "representation": payload.get("representation"),
        "coordinate_frame": payload.get("coordinate_frame"),
    }


def _frame_action_role_coverage(trajectory: dict[str, Any]) -> dict[str, Any]:
    frames = trajectory.get("frames")
    if not isinstance(frames, list):
        return {
            "checked_frame_count": 0,
            "missing": ["trajectory.frames missing"],
            "mismatched": [],
        }

    missing: list[str] = []
    mismatched: list[str] = []
    checked_frame_count = 0
    canonical_action = _first_frame_action(trajectory)
    canonical_roles = {
        key: _action_role_contract(canonical_action, key)
        for key in REQUIRED_ACTION_ROLE_KEYS
    }
    for index, frame in enumerate(frames):
        if not isinstance(frame, dict):
            missing.append(f"frames[{index}] not object")
            continue
        action = frame.get("action")
        if not isinstance(action, dict):
            missing.append(f"frames[{index}].action missing")
            continue
        checked_frame_count += 1
        for key in REQUIRED_ACTION_ROLE_KEYS:
            role = action.get(key)
            if not isinstance(role, dict):
                missing.append(f"frames[{index}].action.{key} missing")
                continue
            for field in REQUIRED_ACTION_ROLE_FIELDS:
                value = role.get(field)
                if not value:
                    missing.append(f"frames[{index}].action.{key}.{field} missing")
                    continue
                expected_value = canonical_roles[key].get(field)
                if expected_value and value != expected_value:
                    mismatched.append(
                        f"frames[{index}].action.{key}.{field} expected {expected_value} got {value}"
                    )

    return {
        "checked_frame_count": checked_frame_count,
        "missing": missing,
        "mismatched": mismatched,
    }


class NormalizedTrajectoryContractValidator:
    def __init__(
        self,
        *,
        proof_id: str = "rdf_data_trust_layer_hmd_free_fixture_v0",
        contract_name: str = DEFAULT_CONTRACT_NAME,
        required_source_fields: list[str] | None = None,
        artifact_path_formatter: Callable[[Path], str] | None = None,
    ) -> None:
        self.proof_id = proof_id
        self.contract_name = contract_name
        self.required_source_fields = list(required_source_fields or DEFAULT_REQUIRED_SOURCE_FIELDS)
        self.artifact_path_formatter = artifact_path_formatter or (lambda path: str(path))

    def build_from_artifacts(
        self,
        *,
        accepted_trajectory: Path,
        accepted_evaluation: Path,
        curation_manifest: Path,
        hdf5_path: Path,
        trainer_smoke_report: Path,
    ) -> NormalizedTrajectoryContractResult:
        trajectory = _read_json(accepted_trajectory)
        evaluation = _read_json(accepted_evaluation)
        curation = _read_json(curation_manifest)
        trainer = _read_json(trainer_smoke_report)
        action = _first_frame_action(trajectory)
        data_quality = ((evaluation.get("metrics") or {}).get("data_quality") or {})
        contract = {
            "schema_version": TRAJECTORY_CONTRACT_SCHEMA_VERSION,
            "proof_id": self.proof_id,
            "contract_name": self.contract_name,
            "trajectory_schema_version": trajectory.get("schema_version"),
            "source_profile": trajectory.get("source") or {},
            "required_source_fields": list(self.required_source_fields),
            "field_paths": list(NORMALIZED_TRAJECTORY_CONTRACT_FIELD_PATHS),
            "required_action_roles": {
                key: _action_role_contract(action, key)
                for key in REQUIRED_ACTION_ROLE_KEYS
            },
            "frame_action_role_coverage": _frame_action_role_coverage(trajectory),
            "action_contract_versions": {
                "action_contract_version": action.get("action_contract_version"),
                "replay_contract_version": action.get("replay_contract_version"),
            },
            "replay_gate": (trajectory.get("summary") or {}).get("action_replay_gate") or {},
            "training_eligibility_gates": {
                "task_outcome": {
                    "evaluation_success": evaluation.get("success"),
                    "failure_reason": evaluation.get("failure_reason"),
                },
                "data_quality": {
                    "replay_verified": data_quality.get("replay_verified"),
                    "action_contract_status": data_quality.get("action_contract_status"),
                    "action_contract_valid": data_quality.get("action_contract_valid"),
                    "control_quality": data_quality.get("control_quality"),
                    "quality_failure_reasons": data_quality.get("quality_failure_reasons"),
                },
                "curation": {
                    "accepted_count": curation.get("accepted_count"),
                    "rejected_count": curation.get("rejected_count"),
                    "curation_rules": curation.get("curation_rules"),
                },
                "export": {
                    "hdf5_export_generated": hdf5_path.exists(),
                    "trainer_smoke_passed": trainer.get("passed") is True,
                    "learning_results_measured": trainer.get("learning_results_measured"),
                    "curated_vs_uncurated_uplift": trainer.get("curated_vs_uncurated_uplift"),
                },
            },
            "claim_boundaries": {
                "hmd_readiness_claimed": False,
                "physical_robot_readiness_claimed": False,
                "gate_a_collection_allowed": False,
                "policy_uplift_claimed": False,
            },
            "artifact_paths": {
                "accepted_trajectory": self.artifact_path_formatter(accepted_trajectory),
                "accepted_evaluation": self.artifact_path_formatter(accepted_evaluation),
                "curation_manifest": self.artifact_path_formatter(curation_manifest),
                "hdf5_export": self.artifact_path_formatter(hdf5_path),
                "trainer_smoke_report": self.artifact_path_formatter(trainer_smoke_report),
            },
        }
        issues = self.validate_learning_eligibility(contract)
        return NormalizedTrajectoryContractResult(
            passed=not issues,
            contract=contract,
            issues=issues,
        )

    def validate(self, contract: dict[str, Any]) -> list[str]:
        return self.validate_learning_eligibility(contract)

    def validate_ingress_contract(self, contract: dict[str, Any]) -> list[str]:
        issues: list[str] = []
        issues.extend(self._validate_source_profile(contract))
        issues.extend(self._validate_action_roles(contract))
        issues.extend(self._validate_frame_action_role_coverage(contract))
        issues.extend(self._validate_optional_replay_gate(contract))
        issues.extend(self._validate_claim_boundaries(contract))
        return issues

    def validate_learning_eligibility(self, contract: dict[str, Any]) -> list[str]:
        issues = self.validate_ingress_contract(contract)
        issues.extend(self._validate_required_replay_gate(contract))
        issues.extend(self._validate_training_eligibility_gates(contract))
        return issues

    def _validate_source_profile(self, contract: dict[str, Any]) -> list[str]:
        issues: list[str] = []
        source = contract.get("source_profile")
        if not isinstance(source, dict):
            issues.append("source_profile missing")
            source = {}
        for field in self.required_source_fields:
            if not source.get(field):
                issues.append(f"source.{field} missing")
        return issues

    @staticmethod
    def _validate_action_roles(contract: dict[str, Any]) -> list[str]:
        issues: list[str] = []
        action_roles = contract.get("required_action_roles")
        if not isinstance(action_roles, dict):
            issues.append("required_action_roles missing")
            action_roles = {}
        for key in REQUIRED_ACTION_ROLE_KEYS:
            role = action_roles.get(key)
            if not isinstance(role, dict):
                issues.append(f"action.{key} missing")
                continue
            for field in REQUIRED_ACTION_ROLE_FIELDS:
                if not role.get(field):
                    issues.append(f"action.{key}.{field} missing")
        return issues

    @staticmethod
    def _validate_frame_action_role_coverage(contract: dict[str, Any]) -> list[str]:
        coverage = contract.get("frame_action_role_coverage")
        if not isinstance(coverage, dict):
            return ["frame_action_role_coverage missing"]

        issues: list[str] = []
        if int(coverage.get("checked_frame_count") or 0) < 1:
            issues.append("frame_action_role_coverage.checked_frame_count less than 1")
        for key in ("missing", "mismatched"):
            values = coverage.get(key)
            if not isinstance(values, list):
                issues.append(f"frame_action_role_coverage.{key} not list")
            else:
                issues.extend(str(issue) for issue in values)
        return issues

    @staticmethod
    def _validate_optional_replay_gate(contract: dict[str, Any]) -> list[str]:
        replay_gate = contract.get("replay_gate")
        if replay_gate in (None, {}):
            return []
        if not isinstance(replay_gate, dict) or replay_gate.get("passed") is not True:
            return ["replay_gate.passed not true"]
        return []

    @staticmethod
    def _validate_required_replay_gate(contract: dict[str, Any]) -> list[str]:
        replay_gate = contract.get("replay_gate")
        if not isinstance(replay_gate, dict) or replay_gate.get("passed") is not True:
            return ["replay_gate.passed not true"]
        return []

    @staticmethod
    def _validate_training_eligibility_gates(contract: dict[str, Any]) -> list[str]:
        issues: list[str] = []
        gates = contract.get("training_eligibility_gates")
        if not isinstance(gates, dict):
            return ["training_eligibility_gates missing"]

        task_outcome = gates.get("task_outcome")
        if not isinstance(task_outcome, dict):
            issues.append("training_eligibility_gates.task_outcome missing")
        else:
            if task_outcome.get("evaluation_success") is not True:
                issues.append("task_outcome.evaluation_success not true")
            if task_outcome.get("failure_reason") is not None:
                issues.append("task_outcome.failure_reason not null")

        data_quality = gates.get("data_quality")
        if not isinstance(data_quality, dict):
            issues.append("training_eligibility_gates.data_quality missing")
        else:
            if data_quality.get("replay_verified") is not True:
                issues.append("data_quality.replay_verified not true")
            if data_quality.get("action_contract_status") != "pass":
                issues.append("data_quality.action_contract_status not pass")
            if data_quality.get("action_contract_valid") is not True:
                issues.append("data_quality.action_contract_valid not true")
            if data_quality.get("control_quality") != "pass":
                issues.append("data_quality.control_quality not pass")
            if data_quality.get("quality_failure_reasons") not in ([], None):
                issues.append("data_quality.quality_failure_reasons not empty")

        curation = gates.get("curation")
        if not isinstance(curation, dict):
            issues.append("training_eligibility_gates.curation missing")
        elif int(curation.get("accepted_count") or 0) < 1:
            issues.append("curation.accepted_count less than 1")

        export = gates.get("export")
        if not isinstance(export, dict):
            issues.append("training_eligibility_gates.export missing")
        else:
            if export.get("hdf5_export_generated") is not True:
                issues.append("export.hdf5_export_generated not true")
            if export.get("trainer_smoke_passed") is not True:
                issues.append("export.trainer_smoke_passed not true")
            if export.get("learning_results_measured") is not False:
                issues.append("export.learning_results_measured not false")
            if export.get("curated_vs_uncurated_uplift") is not None:
                issues.append("export.curated_vs_uncurated_uplift not null")
        return issues

    @staticmethod
    def _validate_claim_boundaries(contract: dict[str, Any]) -> list[str]:
        issues: list[str] = []
        boundaries = contract.get("claim_boundaries")
        if not isinstance(boundaries, dict):
            issues.append("claim_boundaries missing")
        else:
            for field in (
                "hmd_readiness_claimed",
                "physical_robot_readiness_claimed",
                "gate_a_collection_allowed",
                "policy_uplift_claimed",
            ):
                if boundaries.get(field) is not False:
                    issues.append(f"claim_boundaries.{field} not false")
        return issues
