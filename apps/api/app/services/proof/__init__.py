"""Producer-side proof integrity spine for repeatable proof packages."""

from .closure import derive_closure
from .contracts import (
    CalibrationSelectionReport,
    ClosureThresholds,
    ClosureVerdict,
    GateInputs,
    LearningReport,
    LeakageReport,
    RuntimeExpectations,
    RuntimeGate,
    SeedDisciplineReport,
    SeedRangeConfig,
    TrainRuntimeGate,
)
from .leakage_guard import burned_seeds_from_channels, check_heldout_leakage, seeds_in_range
from .seed_discipline import validate_seed_ranges

__all__ = [
    "CalibrationSelectionReport",
    "ClosureThresholds",
    "ClosureVerdict",
    "GateInputs",
    "LearningReport",
    "LeakageReport",
    "RuntimeExpectations",
    "RuntimeGate",
    "SeedDisciplineReport",
    "SeedRangeConfig",
    "TrainRuntimeGate",
    "burned_seeds_from_channels",
    "check_heldout_leakage",
    "derive_closure",
    "seeds_in_range",
    "validate_seed_ranges",
]
