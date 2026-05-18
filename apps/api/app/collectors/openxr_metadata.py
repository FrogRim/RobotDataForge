from __future__ import annotations


def normalize_openxr_metadata(metadata: dict) -> dict:
    return {
        "right_hand_tracked": bool(metadata.get("right_hand_tracked", True)),
        "left_hand_tracked": bool(metadata.get("left_hand_tracked", False)),
        "pinch_strength": float(metadata.get("pinch_strength", 0.0)),
        "tracking_confidence": float(metadata.get("tracking_confidence", 1.0)),
        "xr_frame_valid": bool(metadata.get("xr_frame_valid", True)),
        "input_latency_ms": metadata.get("input_latency_ms"),
        "sim_fps": metadata.get("sim_fps"),
    }
