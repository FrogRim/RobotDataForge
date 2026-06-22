from __future__ import annotations

from collections.abc import Sequence

from .contracts import SeedDisciplineReport, SeedRangeConfig
from .leakage_guard import seeds_in_range


def _union(spans: Sequence[tuple[int, int]]) -> set[int]:
    seeds: set[int] = set()
    for span in spans:
        seeds |= seeds_in_range(span)
    return seeds


def validate_seed_ranges(config: SeedRangeConfig) -> SeedDisciplineReport:
    violations: list[str] = []
    train = seeds_in_range(config.train)
    calibration = _union(config.calibration)
    heldout = seeds_in_range(config.heldout)
    burned = _union(config.pre_closure_burned)
    spent_no_reuse = _union(config.spent_no_reuse)

    if train & calibration:
        violations.append("train and calibration ranges overlap")
    if heldout & train:
        violations.append("held-out range overlaps training seeds")
    if heldout & calibration:
        violations.append("held-out range overlaps calibration seeds")
    if heldout & burned:
        violations.append("held-out range overlaps pre-closure burned seeds")
    if train & spent_no_reuse:
        violations.append("training range overlaps configured spent/no-reuse seeds")
    if calibration & spent_no_reuse:
        violations.append("calibration range overlaps configured spent/no-reuse seeds")
    if heldout & spent_no_reuse:
        violations.append("held-out range overlaps configured spent/no-reuse seeds")

    return SeedDisciplineReport(passed=not violations, violations=violations)
