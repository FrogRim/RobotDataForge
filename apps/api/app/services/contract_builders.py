from __future__ import annotations

from dataclasses import dataclass
import copy
from typing import Any, Protocol, runtime_checkable

from app.services.adapter_contract_emitters import (
    AdapterContractEmitter,
    AdapterContractEmitterProfile,
    ROBOT_EMBODIMENT_ADAPTER_EMITTER_KIND,
)


CONTRACT_BUILDER_SCHEMA_VERSION = "rdf_contract_builder_v0.1.0"
ROBOT_EMBODIMENT_CONTRACT_BUILDER_KIND = "robot_embodiment_contract_builder"


@dataclass(frozen=True)
class ContractBuilderEmissionResult:
    contract: dict[str, Any]
    contract_builder: dict[str, Any]
    contract_emitter: dict[str, Any]


@runtime_checkable
class ContractBuilder(Protocol):
    adapter_id: str
    adapter_name: str
    builder_kind: str
    builder_version: str

    def build_contract(self, contract_template: dict[str, Any]) -> ContractBuilderEmissionResult:
        """Emit a normalized trajectory contract for one adapter source."""


class _BaseContractBuilder:
    builder_version = CONTRACT_BUILDER_SCHEMA_VERSION

    def __init__(
        self,
        *,
        adapter_id: str,
        adapter_name: str,
        builder_kind: str,
        emitter_kind: str,
        source_profile: dict[str, Any],
        builder_name: str | None = None,
    ) -> None:
        self.adapter_id = adapter_id
        self.adapter_name = adapter_name
        self.builder_kind = builder_kind
        self.emitter_kind = emitter_kind
        self.source_profile = copy.deepcopy(source_profile)
        self.builder_name = builder_name or adapter_name

    def build_contract(self, contract_template: dict[str, Any]) -> ContractBuilderEmissionResult:
        emission = AdapterContractEmitter(
            AdapterContractEmitterProfile(
                adapter_id=self.adapter_id,
                adapter_name=self.adapter_name,
                emitter_kind=self.emitter_kind,
                source_profile=self.source_profile,
                contract_evidence=self._contract_evidence(contract_template),
            )
        ).emit(contract_template)
        contract = emission.contract
        contract_builder = self._build_contract_builder(contract, emission.contract_emitter)
        contract["contract_builder"] = copy.deepcopy(contract_builder)
        return ContractBuilderEmissionResult(
            contract=contract,
            contract_builder=contract_builder,
            contract_emitter=emission.contract_emitter,
        )

    def _contract_evidence(self, contract_template: dict[str, Any]) -> dict[str, dict[str, Any]] | None:
        return None

    def _build_contract_builder(
        self,
        contract: dict[str, Any],
        contract_emitter: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "schema_version": CONTRACT_BUILDER_SCHEMA_VERSION,
            "builder_id": f"{self.builder_kind}:{self.adapter_id}:{self.builder_version}",
            "builder_name": self.builder_name,
            "builder_kind": self.builder_kind,
            "builder_version": self.builder_version,
            "adapter_id": self.adapter_id,
            "adapter_name": self.adapter_name,
            "emitted_contract_schema_version": contract.get("schema_version"),
            "contract_emitter_id": contract_emitter.get("emitter_id"),
        }


class RobotEmbodimentContractBuilder(_BaseContractBuilder):
    adapter_role: str

    def __init__(
        self,
        *,
        adapter_id: str,
        adapter_name: str,
        adapter_role: str,
        source_profile: dict[str, Any],
        robot_embodiment_profile: dict[str, Any],
        command_state_stream_profile: dict[str, Any],
    ) -> None:
        super().__init__(
            adapter_id=adapter_id,
            adapter_name=adapter_name,
            builder_kind=ROBOT_EMBODIMENT_CONTRACT_BUILDER_KIND,
            emitter_kind=ROBOT_EMBODIMENT_ADAPTER_EMITTER_KIND,
            source_profile=source_profile,
        )
        self.adapter_role = adapter_role
        self.robot_embodiment_profile = copy.deepcopy(robot_embodiment_profile)
        self.command_state_stream_profile = copy.deepcopy(command_state_stream_profile)

    def _contract_evidence(self, contract_template: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {
            "robot_embodiment_adapter_evidence": self._robot_embodiment_adapter_evidence(contract_template),
        }

    def _robot_embodiment_adapter_evidence(self, contract_template: dict[str, Any]) -> dict[str, Any]:
        command_profile = self.command_state_stream_profile
        contract_roles = sorted((contract_template.get("required_action_roles") or {}).keys())
        return {
            "adapter_id": self.adapter_id,
            "adapter_role": self.adapter_role,
            "fixture_basis": "builder_static_profile",
            "robot_embodiment_profile": copy.deepcopy(self.robot_embodiment_profile),
            "command_state_stream_profile": copy.deepcopy(command_profile),
            "source_provenance": {
                "builder_source_profile": copy.deepcopy(self.source_profile),
            },
            "command_action_semantics": {
                "command_interface": command_profile["command_interface"],
                "action_representation": "normalized_robot_action_contract",
                "contract_roles": contract_roles,
                "semantics_boundary": "recorded_log_projection_contract_compatibility_not_robot_runtime_support",
            },
            "state_metadata": {
                "stream_id": command_profile["stream_id"],
                "transport": command_profile["transport"],
                "state_interface": command_profile["state_interface"],
                "state_sample_source": "recorded_command_state_projection",
            },
            "replay_consistency_evidence": {
                "validator": "NormalizedTrajectoryContractValidator",
                "ingress_gate": "validate_ingress_contract",
                "learning_gate": "validate_learning_eligibility",
                "replay_or_consistency_checked": True,
                "evidence_level": "builder_static_profile",
            },
            "curation_evidence": {
                "curation_gate_required": True,
                "accepted_rejected_manifest_required": True,
                "training_eligibility_gate": "curation",
            },
            "limitations": [
                "Recorded/log-backed contract compatibility only.",
                "No physical robot readiness claimed.",
                "No real robot control claimed.",
                "No policy transfer or policy uplift claimed.",
            ],
            "support_boundary": "recorded_log_contract_compatibility_only",
        }


class FrankaContractBuilder(RobotEmbodimentContractBuilder):
    def __init__(self) -> None:
        super().__init__(
            adapter_id="franka_research_arm",
            adapter_name="Franka Adapter",
            adapter_role="baseline_research_arm_adapter",
            source_profile={
                "input_device": "scripted_fixture",
                "runtime": "research_arm_command_state_fixture",
                "robot": "franka",
            },
            robot_embodiment_profile={
                "embodiment_class": "research_arm",
                "manipulator_family": "franka",
                "proof_role": "baseline_research_arm",
            },
            command_state_stream_profile={
                "stream_id": "franka_fixture_command_state_stream",
                "transport": "fixture_command_state",
                "command_interface": "joint_and_ee_delta_command_fixture",
                "state_interface": "fixture_joint_and_ee_state",
            },
        )


class RobotisSh5Ros2DdsContractBuilder(RobotEmbodimentContractBuilder):
    def __init__(self) -> None:
        super().__init__(
            adapter_id="robotis_sh5_ros2_dds",
            adapter_name="ROBOTIS SH5 / ROS2-DDS Adapter",
            adapter_role="ros2_dds_command_state_bridge_adapter",
            source_profile={
                "input_device": "scripted_fixture",
                "runtime": "ros2_dds_command_state_fixture",
                "robot": "robotis_sh5",
            },
            robot_embodiment_profile={
                "embodiment_class": "ros2_manipulator",
                "manipulator_family": "robotis_sh5",
                "proof_role": "ros2_dds_command_state_bridge",
            },
            command_state_stream_profile={
                "stream_id": "robotis_sh5_ros2_dds_fixture_command_state_stream",
                "transport": "ros2_dds",
                "command_interface": "ros2_joint_trajectory_command_fixture",
                "state_interface": "ros2_joint_state_stream_fixture",
            },
        )


class UniversalRobotsUrContractBuilder(RobotEmbodimentContractBuilder):
    def __init__(self) -> None:
        super().__init__(
            adapter_id="universal_robots_ur_industrial_arm",
            adapter_name="Universal Robots UR Adapter",
            adapter_role="industrial_arm_adapter",
            source_profile={
                "input_device": "scripted_fixture",
                "runtime": "industrial_arm_command_state_fixture",
                "robot": "universal_robots_ur",
            },
            robot_embodiment_profile={
                "embodiment_class": "industrial_arm",
                "manipulator_family": "universal_robots_ur",
                "proof_role": "industrial_arm",
            },
            command_state_stream_profile={
                "stream_id": "universal_robots_ur_fixture_command_state_stream",
                "transport": "industrial_command_state_fixture",
                "command_interface": "industrial_arm_command_fixture",
                "state_interface": "industrial_arm_state_stream_fixture",
            },
        )
