from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast


CONTRACT_SCHEMA_VERSION = "rdf_lerobot_state_action_contract_v0.1.0"


@dataclass(frozen=True)
class LeRobotStateActionContractReport:
    ok: bool
    issues: list[str] = field(default_factory=list)
    row_count: int = 0
    observation_state_dim: int = 0
    action_dim: int = 0


class LeRobotStateActionContractValidator:
    """Validate generic public-LeRobot state/action semantics.

    This is deliberately separate from the EEF/object trajectory validator so a
    LeRobot source cannot satisfy RDF's physical pose contract by fabrication.
    """

    forbidden_claim_keys = {
        "real_robot_readiness",
        "physical_robot_readiness",
        "visual_policy_performance",
        "deployable_policy_readiness",
        "policy_uplift",
        "learning_proven_value",
    }

    def validate_rows(self, rows: list[dict[str, Any]], *, expected_robot_type: str = "aloha") -> LeRobotStateActionContractReport:
        issues: list[str] = []
        if not rows:
            issues.append("converted row set is empty")
            return LeRobotStateActionContractReport(ok=False, issues=issues)

        state_dim: int | None = None
        action_dim: int | None = None
        last_timestamp_by_episode: dict[int, float] = {}
        for index, row in enumerate(rows):
            if row.get("schema_version") != "rdf_public_lerobot_state_action_row_v0.1.0":
                issues.append(f"row {index}: schema_version mismatch")
            if row.get("source_robot_type") != expected_robot_type:
                issues.append(f"row {index}: source_robot_type mismatch")
            state = row.get("observation_state")
            action = row.get("learning_action")
            if not _numeric_vector(state):
                issues.append(f"row {index}: observation_state must be numeric vector")
                continue
            if not _numeric_vector(action):
                issues.append(f"row {index}: learning_action must be numeric vector")
                continue
            state_values = [float(value) for value in cast(list[int | float], state)]
            action_values = [float(value) for value in cast(list[int | float], action)]
            if state_dim is None:
                state_dim = len(state_values)
            elif len(state_values) != state_dim:
                issues.append(f"row {index}: observation_state dimension drift")
            if action_dim is None:
                action_dim = len(action_values)
            elif len(action_values) != action_dim:
                issues.append(f"row {index}: learning_action dimension drift")

            episode = _int_value(row.get("episode_index"))
            timestamp = _float_value(row.get("timestamp"))
            if episode is None:
                issues.append(f"row {index}: missing numeric episode_index")
                continue
            if timestamp is None:
                issues.append(f"row {index}: missing numeric timestamp")
                continue
            previous = last_timestamp_by_episode.get(episode)
            if previous is not None and timestamp < previous:
                issues.append(f"row {index}: timestamp is not monotonic within episode")
            last_timestamp_by_episode[episode] = timestamp

            quality = row.get("quality")
            if not isinstance(quality, dict) or quality.get("accepted_for_export") is not True:
                issues.append(f"row {index}: quality.accepted_for_export must be true")
            _scan_forbidden_true_claims(row, issues, label=f"row {index}")

        return LeRobotStateActionContractReport(
            ok=not issues,
            issues=list(dict.fromkeys(issues)),
            row_count=len(rows),
            observation_state_dim=state_dim or 0,
            action_dim=action_dim or 0,
        )

    def build_contract(self, rows: list[dict[str, Any]], *, source_binding: dict[str, Any]) -> dict[str, Any]:
        report = self.validate_rows(rows, expected_robot_type=str(source_binding.get("dataset_card_robot_type") or "aloha"))
        return {
            "schema_version": CONTRACT_SCHEMA_VERSION,
            "source_format": "LeRobot public dataset audited slice",
            "source_kind": source_binding.get("source_kind") or "public_lerobot_aloha_audited_slice",
            "repo_id": source_binding.get("repo_id"),
            "resolved_revision": source_binding.get("resolved_revision"),
            "robot_type": source_binding.get("dataset_card_robot_type"),
            "row_count": report.row_count,
            "observation_state_dim": report.observation_state_dim,
            "action_dim": report.action_dim,
            "visual_data_ignored": True,
            "camera_visual_policy_readiness": False,
            "task_success_labels_measured": False,
            "accepted_slice_evaluated": report.ok,
            "full_source_verdict_claimed": False,
            "audited_slice_verdict_claimed": True,
        }


def _numeric_vector(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value)


def _int_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    return None


def _float_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _scan_forbidden_true_claims(payload: Any, issues: list[str], *, label: str) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in LeRobotStateActionContractValidator.forbidden_claim_keys and value is True:
                issues.append(f"{label}: forbidden claim {key} leaked true")
            _scan_forbidden_true_claims(value, issues, label=label)
    elif isinstance(payload, list):
        for item in payload:
            _scan_forbidden_true_claims(item, issues, label=label)
