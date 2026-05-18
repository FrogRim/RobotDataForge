from __future__ import annotations

import math


def euclidean(a: list[float] | tuple[float, ...], b: list[float] | tuple[float, ...]) -> float:
    if len(a) != len(b):
        return float("inf")
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b, strict=True)))


def path_length(points: list[list[float]]) -> float:
    if len(points) < 2:
        return 0.0
    return sum(euclidean(points[i - 1], points[i]) for i in range(1, len(points)))


def downsample(points: list[list[float]], n: int) -> list[list[float]]:
    if not points or n <= 0:
        return []
    if len(points) <= n:
        return points
    step = (len(points) - 1) / max(n - 1, 1)
    return [points[round(i * step)] for i in range(n)]
