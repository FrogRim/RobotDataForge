from __future__ import annotations

from typing import Any


def build_dataset_card(
    *,
    dataset_id: str,
    dataset_name: str,
    task: dict[str, Any] | None,
    episodes: list[dict[str, Any]],
    curation_rules: dict[str, Any],
    splits: dict[str, float],
    export_format: str,
) -> dict[str, Any]:
    first_source = None
    for item in episodes:
        source = ((item.get("trajectory") or {}).get("source") or {})
        if source:
            first_source = source
            break

    accepted = [item for item in episodes if ((item.get("curation") or {}).get("accepted") is not False)]
    rejected = [item for item in episodes if ((item.get("curation") or {}).get("accepted") is False)]
    task = task or {}
    return {
        "schema_version": "dataset_card_v0.1.0",
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        "task_description": task.get("description"),
        "task_type": task.get("task_type"),
        "robot": (first_source or {}).get("robot"),
        "simulator": (first_source or {}).get("simulator"),
        "input_device": (first_source or {}).get("input_device"),
        "runtime": (first_source or {}).get("runtime"),
        "num_episodes": len(episodes),
        "num_accepted": len(accepted),
        "num_rejected": len(rejected),
        "success_criteria": task.get("success_criteria", {}),
        "evaluator_version": "forge_eval_v0.2.0",
        "curation_rules": curation_rules,
        "splits": splits,
        "export_format": export_format,
        "limitations": [
            "MVP dataset is generated from Isaac/Quest synthetic teleoperation unless documented otherwise.",
            "LeRobot-compatible export is metadata-ready but not implemented as a full LeRobot Dataset v3 writer.",
            "Unmeasured sync fields are stored as null and must not be treated as measured values.",
        ],
    }
