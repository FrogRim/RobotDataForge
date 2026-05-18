from __future__ import annotations

from app.utils.geometry import euclidean


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def normalized_path_jitter(points: list[list[float]]) -> float:
    if len(points) < 3:
        return 0.0
    velocities = [
        euclidean(points[i - 1], points[i])
        for i in range(1, len(points))
    ]
    if not velocities:
        return 0.0
    mean_velocity = sum(velocities) / len(velocities)
    if mean_velocity <= 1e-9:
        return 0.0
    jitter = sum(abs(v - mean_velocity) for v in velocities) / len(velocities)
    return clamp01(jitter / mean_velocity)
