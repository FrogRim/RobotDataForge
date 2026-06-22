from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from .contracts import LeakageReport


def _trailing_int(label: object) -> int | None:
    match = re.search(r"(\d+)$", str(label))
    if match is None:
        return None
    return int(match.group(1))


def seeds_in_range(span: tuple[int, int]) -> set[int]:
    start, end = span
    if start > end:
        raise ValueError(f"invalid seed range: {span}")
    return set(range(start, end + 1))


def burned_seeds_from_channels(
    checked_channels: Mapping[str, Sequence[object]],
    include_ranges: Sequence[tuple[int, int]] | None = None,
) -> set[int]:
    burned: set[int] = set()
    for labels in checked_channels.values():
        for label in labels:
            value = _trailing_int(label)
            if value is None:
                raise ValueError(f"invalid seed label: {label!r}")
            burned.add(value)
    for span in include_ranges or []:
        burned |= seeds_in_range(span)
    return burned


def check_heldout_leakage(held_out: set[int], burned: set[int]) -> LeakageReport:
    overlap = sorted(held_out & burned)
    return LeakageReport(
        passed=bool(held_out) and not overlap,
        overlap=overlap,
        burned_count=len(burned),
        held_out_count=len(held_out),
    )
