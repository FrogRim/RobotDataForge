from __future__ import annotations

from dataclasses import dataclass
import copy
from typing import Any


ADAPTER_CONTRACT_EMITTER_SCHEMA_VERSION = "rdf_adapter_contract_emitter_v0.1.0"
ROBOT_EMBODIMENT_ADAPTER_EMITTER_KIND = "robot_embodiment_adapter"
RESERVED_CONTRACT_EVIDENCE_KEYS = frozenset(
    {
        "schema_version",
        "proof_id",
        "contract_name",
        "trajectory_schema_version",
        "source_profile",
        "required_source_fields",
        "field_paths",
        "required_action_roles",
        "frame_action_role_coverage",
        "action_contract_versions",
        "replay_gate",
        "training_eligibility_gates",
        "claim_boundaries",
        "artifact_paths",
        "adapter_contract_emitter",
        "contract_builder",
    }
)


@dataclass(frozen=True)
class AdapterContractEmitterProfile:
    adapter_id: str
    adapter_name: str
    emitter_kind: str
    source_profile: dict[str, Any]
    emitter_version: str = ADAPTER_CONTRACT_EMITTER_SCHEMA_VERSION
    emitter_name: str | None = None
    contract_evidence: dict[str, dict[str, Any]] | None = None


@dataclass(frozen=True)
class AdapterContractEmissionResult:
    contract: dict[str, Any]
    contract_emitter: dict[str, Any]


class AdapterContractEmitter:
    def __init__(self, profile: AdapterContractEmitterProfile) -> None:
        self.profile = profile

    def emit(self, contract_template: dict[str, Any]) -> AdapterContractEmissionResult:
        contract = copy.deepcopy(contract_template)
        contract["source_profile"] = {
            **(contract.get("source_profile") or {}),
            **copy.deepcopy(self.profile.source_profile),
        }
        contract_emitter = self._build_contract_emitter(contract)
        contract["adapter_contract_emitter"] = copy.deepcopy(contract_emitter)
        for evidence_key, evidence in (self.profile.contract_evidence or {}).items():
            if evidence_key in RESERVED_CONTRACT_EVIDENCE_KEYS:
                raise ValueError(f"contract_evidence key {evidence_key!r} is reserved")
            payload = copy.deepcopy(evidence)
            payload["contract_emitter"] = copy.deepcopy(contract_emitter)
            contract[evidence_key] = payload
        return AdapterContractEmissionResult(
            contract=contract,
            contract_emitter=contract_emitter,
        )

    def _build_contract_emitter(self, contract: dict[str, Any]) -> dict[str, Any]:
        emitter_name = self.profile.emitter_name or self.profile.adapter_name
        return {
            "schema_version": ADAPTER_CONTRACT_EMITTER_SCHEMA_VERSION,
            "emitter_id": (
                f"{self.profile.emitter_kind}:{self.profile.adapter_id}:"
                f"{self.profile.emitter_version}"
            ),
            "emitter_name": emitter_name,
            "emitter_kind": self.profile.emitter_kind,
            "emitter_version": self.profile.emitter_version,
            "adapter_id": self.profile.adapter_id,
            "adapter_name": self.profile.adapter_name,
            "emitted_contract_schema_version": contract.get("schema_version"),
        }
