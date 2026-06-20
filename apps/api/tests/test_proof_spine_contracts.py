from app.services.proof.contracts import (
    CalibrationSelectionReport,
    ClosureThresholds,
    GateInputs,
    LearningReport,
    RuntimeExpectations,
    RuntimeGate,
    TrainRuntimeGate,
)
import pytest
from pydantic import ValidationError


def test_thresholds_v014_defaults():
    thresholds = ClosureThresholds()

    assert thresholds.uplift_min == 0.20
    assert thresholds.min_rollouts_per_policy == 20
    assert thresholds.trace_minimum == 1


def test_gate_inputs_constructs_with_optional_post_guard():
    gate_inputs = GateInputs(
        learning_report=LearningReport(),
        runtime_gate=RuntimeGate(passed=True),
        train_generation_runtime_gate=TrainRuntimeGate(passed=True),
        calibration_selection_report=CalibrationSelectionReport(),
        heldout_leakage_passed=True,
        actual_rollouts_per_policy=50,
    )

    assert gate_inputs.actual_rollouts_per_policy == 50
    assert gate_inputs.post_heldout_guard_passed is None


def test_runtime_expectations_are_injected_values():
    expectations = RuntimeExpectations(
        backend="isaac_runtime",
        proof_runtime="dedicated_isaac_connector_insertion_evaluator",
        training_source="isaac_runtime_scripted_expert_rollout",
    )

    assert expectations.backend == "isaac_runtime"


def test_learning_report_rejects_bool_and_string_numeric_evidence():
    for value in (True, "0.70"):
        with pytest.raises(ValidationError):
            LearningReport(
                learning_proven=True,
                proof_eligible=True,
                curated_vs_uncurated_uplift=value,
                baseline_success_rate=0.10,
                candidate_success_rate=0.80,
            )


def test_proof_boolean_fields_reject_coerced_truthy_values():
    for value in ("true", "yes", 1):
        with pytest.raises(ValidationError):
            RuntimeGate(passed=value)
        with pytest.raises(ValidationError):
            TrainRuntimeGate(passed=value)
        with pytest.raises(ValidationError):
            TrainRuntimeGate(actual_train_generation_evidence=value)
        with pytest.raises(ValidationError):
            CalibrationSelectionReport(heldout_excluded=value)
        with pytest.raises(ValidationError):
            LearningReport(learning_proven=value)


def test_gate_inputs_rejects_bool_and_string_count_evidence():
    base = dict(
        learning_report=LearningReport(
            learning_proven=True,
            proof_eligible=True,
            curated_vs_uncurated_uplift=0.70,
            baseline_success_rate=0.10,
            candidate_success_rate=0.80,
        ),
        runtime_gate=RuntimeGate(passed=True),
        train_generation_runtime_gate=TrainRuntimeGate(passed=True),
        calibration_selection_report=CalibrationSelectionReport(),
        heldout_leakage_passed=True,
        actual_rollouts_per_policy=50,
    )

    for value in (True, "1"):
        with pytest.raises(ValidationError):
            GateInputs(**base, actual_success_trace_count=value)

    for value in (True, "50"):
        with pytest.raises(ValidationError):
            GateInputs(**{**base, "actual_rollouts_per_policy": value})


def test_gate_inputs_rejects_coerced_boolean_evidence():
    base = dict(
        learning_report=LearningReport(
            learning_proven=True,
            proof_eligible=True,
            curated_vs_uncurated_uplift=0.70,
            baseline_success_rate=0.10,
            candidate_success_rate=0.80,
        ),
        runtime_gate=RuntimeGate(passed=True),
        train_generation_runtime_gate=TrainRuntimeGate(passed=True),
        calibration_selection_report=CalibrationSelectionReport(),
        actual_rollouts_per_policy=50,
    )

    for value in ("true", "yes", 1):
        with pytest.raises(ValidationError):
            GateInputs(**base, heldout_leakage_passed=value)
        with pytest.raises(ValidationError):
            GateInputs(**base, heldout_leakage_passed=True, post_heldout_guard_passed=value)


def test_seed_ranges_reject_coerced_endpoints():
    from app.services.proof.contracts import SeedRangeConfig

    for span in ((True, 10001), ("10000", 10001)):
        with pytest.raises(ValidationError):
            SeedRangeConfig(train=span, calibration=[], heldout=(50000, 50049))

    with pytest.raises(ValidationError):
        SeedRangeConfig(train=(10000, 10001), calibration=[(20000, True)], heldout=(50000, 50049))


def test_thresholds_reject_coerced_and_invalid_values():
    for kwargs in (
        {"uplift_min": "0.20"},
        {"uplift_min": True},
        {"uplift_min": -0.01},
        {"min_rollouts_per_policy": "20"},
        {"min_rollouts_per_policy": True},
        {"min_rollouts_per_policy": 0},
        {"trace_minimum": "1"},
        {"trace_minimum": True},
        {"trace_minimum": 0},
    ):
        with pytest.raises(ValidationError):
            ClosureThresholds(**kwargs)


def test_gate_inputs_assignment_validation_rejects_malformed_counts():
    gate_inputs = GateInputs(
        learning_report=LearningReport(
            learning_proven=True,
            proof_eligible=True,
            curated_vs_uncurated_uplift=0.70,
            baseline_success_rate=0.10,
            candidate_success_rate=0.80,
        ),
        runtime_gate=RuntimeGate(passed=True),
        train_generation_runtime_gate=TrainRuntimeGate(passed=True),
        calibration_selection_report=CalibrationSelectionReport(),
        heldout_leakage_passed=True,
        actual_rollouts_per_policy=50,
        actual_success_trace_count=1,
    )

    for value in (True, "1"):
        with pytest.raises(ValidationError):
            gate_inputs.actual_success_trace_count = value
