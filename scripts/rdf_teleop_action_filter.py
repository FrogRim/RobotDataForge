#!/usr/bin/env python3
"""Small Robot Data Forge teleop action filter.

This module is intentionally standard-library only. It is imported from the
Isaac Sim Python process and tested from the Robot Data Forge uv environment.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Any

AxisMap = tuple[tuple[int, float], tuple[int, float], tuple[int, float]]

IDENTITY_AXIS_MAP: AxisMap = ((0, 1.0), (1, 1.0), (2, 1.0))
AXIS_INDEX = {"x": 0, "y": 1, "z": 2}


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def parse_signed_axis_map(spec: str | None) -> AxisMap:
    """Parse a signed axis map like ``x,y,z`` or ``x,-z,y``.

    The parsed map returns three output axes. Each output axis selects one input
    axis and an optional sign. All three source axes must be used exactly once.
    """

    if spec is None or not spec.strip():
        return IDENTITY_AXIS_MAP

    parts = [part.strip().lower() for part in spec.split(",")]
    if len(parts) != 3:
        raise ValueError(f"axis map must have exactly 3 comma-separated axes: {spec!r}")

    parsed: list[tuple[int, float]] = []
    used: set[int] = set()
    for part in parts:
        sign = 1.0
        axis = part
        if axis.startswith("+"):
            axis = axis[1:]
        elif axis.startswith("-"):
            sign = -1.0
            axis = axis[1:]
        if axis not in AXIS_INDEX:
            raise ValueError(f"unsupported axis {part!r}; expected x, y, or z")
        index = AXIS_INDEX[axis]
        if index in used:
            raise ValueError(f"axis map must use each axis once: {spec!r}")
        used.add(index)
        parsed.append((index, sign))

    return (parsed[0], parsed[1], parsed[2])


def format_axis_map(axis_map: AxisMap) -> str:
    axes = ("x", "y", "z")
    return ",".join(f"{'-' if sign < 0 else ''}{axes[index]}" for index, sign in axis_map)


@dataclass(frozen=True)
class RdfTeleopActionFilterConfig:
    enabled: bool = True
    position_gain: float = 0.45
    rotation_gain: float = 0.35
    position_deadzone: float = 0.0015
    rotation_deadzone: float = 0.01
    smoothing_alpha: float = 0.45
    position_axis_map: AxisMap = IDENTITY_AXIS_MAP
    rotation_axis_map: AxisMap = IDENTITY_AXIS_MAP

    @classmethod
    def from_env(cls, environ: dict[str, str] | None = None) -> "RdfTeleopActionFilterConfig":
        if environ is None:
            environ = os.environ

        def env_float(name: str, default: float) -> float:
            value = environ.get(name)
            if value is None or not value.strip():
                return default
            try:
                return float(value)
            except ValueError:
                return default

        def env_bool(name: str, default: bool) -> bool:
            value = environ.get(name)
            if value is None:
                return default
            return value.strip().lower() not in {"0", "false", "no", "off"}

        return cls(
            enabled=env_bool("RDF_ACTION_FILTER", True),
            position_gain=env_float("RDF_ACTION_POS_GAIN", 0.45),
            rotation_gain=env_float("RDF_ACTION_ROT_GAIN", 0.35),
            position_deadzone=env_float("RDF_ACTION_POS_DEADZONE", 0.0015),
            rotation_deadzone=env_float("RDF_ACTION_ROT_DEADZONE", 0.01),
            smoothing_alpha=env_float("RDF_ACTION_SMOOTHING_ALPHA", 0.45),
            position_axis_map=parse_signed_axis_map(environ.get("RDF_ACTION_POS_AXIS_MAP", "x,y,z")),
            rotation_axis_map=parse_signed_axis_map(environ.get("RDF_ACTION_ROT_AXIS_MAP", "x,y,z")),
        ).normalized()

    def normalized(self) -> "RdfTeleopActionFilterConfig":
        return RdfTeleopActionFilterConfig(
            enabled=bool(self.enabled),
            position_gain=max(0.0, float(self.position_gain)),
            rotation_gain=max(0.0, float(self.rotation_gain)),
            position_deadzone=max(0.0, float(self.position_deadzone)),
            rotation_deadzone=max(0.0, float(self.rotation_deadzone)),
            smoothing_alpha=_clamp(float(self.smoothing_alpha), 0.0, 1.0),
            position_axis_map=self.position_axis_map,
            rotation_axis_map=self.rotation_axis_map,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "position_gain": self.position_gain,
            "rotation_gain": self.rotation_gain,
            "position_deadzone": self.position_deadzone,
            "rotation_deadzone": self.rotation_deadzone,
            "smoothing_alpha": self.smoothing_alpha,
            "position_axis_map": format_axis_map(self.position_axis_map),
            "rotation_axis_map": format_axis_map(self.rotation_axis_map),
        }


@dataclass(frozen=True)
class RdfTeleopActionFilterResult:
    raw_action: list[float]
    applied_action: list[float]
    metadata: dict[str, Any]


class RdfTeleopActionFilter:
    """Post-process relative teleop actions before ``env.step``."""

    def __init__(self, config: RdfTeleopActionFilterConfig | None = None) -> None:
        self.config = (config or RdfTeleopActionFilterConfig()).normalized()
        self._previous_position = [0.0, 0.0, 0.0]
        self._previous_rotation = [0.0, 0.0, 0.0]
        self._suppress_next = False
        self._last_recenter_reason: str | None = None
        self._last_suppressed = False

    def recenter(self, reason: str = "operator_command") -> None:
        self._previous_position = [0.0, 0.0, 0.0]
        self._previous_rotation = [0.0, 0.0, 0.0]
        self._suppress_next = True
        self._last_recenter_reason = reason

    def apply(self, action: list[float] | tuple[float, ...]) -> RdfTeleopActionFilterResult:
        raw = [float(value) for value in action]
        if not self.config.enabled:
            return RdfTeleopActionFilterResult(raw, list(raw), self.snapshot(applied=False))

        position = raw[:3] if len(raw) >= 3 else []
        rotation = raw[3:6] if len(raw) >= 6 else []
        tail = raw[6:] if len(raw) >= 6 else raw[3:]

        suppressed = False
        if self._suppress_next:
            position = [0.0, 0.0, 0.0] if position else []
            rotation = [0.0, 0.0, 0.0] if rotation else []
            self._suppress_next = False
            suppressed = True
        else:
            if position:
                position = self._process_vector(
                    position,
                    axis_map=self.config.position_axis_map,
                    gain=self.config.position_gain,
                    deadzone=self.config.position_deadzone,
                    previous=self._previous_position,
                )
                self._previous_position = position
            if rotation:
                rotation = self._process_vector(
                    rotation,
                    axis_map=self.config.rotation_axis_map,
                    gain=self.config.rotation_gain,
                    deadzone=self.config.rotation_deadzone,
                    previous=self._previous_rotation,
                )
                self._previous_rotation = rotation

        self._last_suppressed = suppressed
        applied = [*position, *rotation, *tail]
        return RdfTeleopActionFilterResult(raw, applied, self.snapshot(applied=True))

    def snapshot(self, applied: bool = True) -> dict[str, Any]:
        return {
            "name": "rdf_teleop_action_filter",
            "applied": bool(applied),
            "config": self.config.to_dict(),
            "last_recenter_reason": self._last_recenter_reason,
            "suppressed_after_recenter": self._last_suppressed,
        }

    def _process_vector(
        self,
        vector: list[float],
        axis_map: AxisMap,
        gain: float,
        deadzone: float,
        previous: list[float],
    ) -> list[float]:
        remapped = [vector[index] * sign for index, sign in axis_map]
        deadzoned = [0.0 if abs(value) < deadzone else value for value in remapped]
        gained = [value * gain for value in deadzoned]
        alpha = self.config.smoothing_alpha
        if alpha >= 1.0:
            return gained
        return [alpha * current + (1.0 - alpha) * previous_value for current, previous_value in zip(gained, previous)]
