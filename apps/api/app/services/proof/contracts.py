from __future__ import annotations

from typing import Annotated, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt


RateValue: TypeAlias = Annotated[StrictFloat, Field(ge=0.0, le=1.0)]
UpliftValue: TypeAlias = Annotated[StrictFloat, Field(ge=-1.0, le=1.0)]
ThresholdUplift: TypeAlias = Annotated[StrictFloat, Field(ge=0.0, le=1.0)]
PositiveStrictInt: TypeAlias = Annotated[StrictInt, Field(ge=1)]
SeedValue: TypeAlias = Annotated[StrictInt, Field(ge=0)]
SeedRange: TypeAlias = tuple[SeedValue, SeedValue]


class ProofModel(BaseModel):
    model_config = ConfigDict(validate_assignment=True)


class RuntimeExpectations(ProofModel):
    """Injected task/source expectations for a proof slice."""

    backend: str
    proof_runtime: str
    training_source: str


class ClosureThresholds(ProofModel):
    uplift_min: ThresholdUplift = 0.20
    min_rollouts_per_policy: PositiveStrictInt = 20
    trace_minimum: PositiveStrictInt = 1


class RuntimeGate(ProofModel):
    passed: StrictBool = False
    runtime_backend: str | None = None
    proof_runtime: str | None = None


class TrainRuntimeGate(ProofModel):
    passed: StrictBool = False
    runtime_backend: str | None = None
    actual_train_generation_evidence: StrictBool | None = None
    training_trajectory_source: str | None = None


class CalibrationSelectionReport(ProofModel):
    calibration_only_selection_passed: StrictBool | None = None
    heldout_excluded: StrictBool | None = None
    selected_adapter_frozen_before_heldout: StrictBool | None = None
    same_adapter_used_for_baseline_and_candidate: StrictBool | None = None


class LearningReport(ProofModel):
    learning_proven: StrictBool | None = None
    proof_eligible: StrictBool | None = None
    curated_vs_uncurated_uplift: UpliftValue | None = None
    baseline_success_rate: RateValue | None = None
    candidate_success_rate: RateValue | None = None


class GateInputs(ProofModel):
    learning_report: LearningReport
    runtime_gate: RuntimeGate
    train_generation_runtime_gate: TrainRuntimeGate
    calibration_selection_report: CalibrationSelectionReport
    heldout_leakage_passed: StrictBool
    actual_rollouts_per_policy: StrictInt
    actual_success_trace_count: StrictInt | None = None
    post_heldout_guard_passed: StrictBool | None = None


class ClosureVerdict(ProofModel):
    closed: StrictBool
    gates: dict[str, StrictBool]
    blockers: list[str] = Field(default_factory=list)


class LeakageReport(ProofModel):
    passed: StrictBool
    overlap: list[int] = Field(default_factory=list)
    burned_count: int
    held_out_count: int


class SeedRangeConfig(ProofModel):
    train: SeedRange
    calibration: list[SeedRange]
    heldout: SeedRange
    pre_closure_burned: list[SeedRange] = Field(default_factory=list)
    spent_no_reuse: list[SeedRange] = Field(default_factory=list)


class SeedDisciplineReport(ProofModel):
    passed: StrictBool
    violations: list[str] = Field(default_factory=list)
