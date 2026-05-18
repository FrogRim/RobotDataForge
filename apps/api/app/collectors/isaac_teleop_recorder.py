from __future__ import annotations

from typing import Any

from app.collectors.openxr_metadata import normalize_openxr_metadata


def record_frame(sim_state: dict[str, Any], teleop_action: dict[str, Any], xr_metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        "t": float(sim_state.get("t", 0.0)),
        "step": int(sim_state.get("step", 0)),
        "end_effector_position": sim_state.get("end_effector_position", []),
        "end_effector_quaternion": sim_state.get("end_effector_quaternion", []),
        "object_position": sim_state.get("object_position", []),
        "object_quaternion": sim_state.get("object_quaternion", []),
        "action": teleop_action,
        "contacts": sim_state.get("contacts", []),
        "metadata": normalize_openxr_metadata(xr_metadata),
    }
