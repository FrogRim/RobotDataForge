from __future__ import annotations

from dataclasses import dataclass

from app.adapters.isaac_lab_adapter import IsaacLabAdapter
from app.adapters.mock_sim_adapter import MockSimAdapter


@dataclass(frozen=True)
class AdapterSelection:
    adapter: IsaacLabAdapter | MockSimAdapter
    fallback_used: bool
    reason: str | None


def select_collection_adapter() -> AdapterSelection:
    primary = IsaacLabAdapter()
    if primary.is_available():
        return AdapterSelection(adapter=primary, fallback_used=False, reason=None)
    return AdapterSelection(
        adapter=MockSimAdapter(),
        fallback_used=True,
        reason=f"IsaacLabAdapter unavailable: {primary.script_path}",
    )
