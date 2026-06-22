from __future__ import annotations

from copy import deepcopy

import pytest

from app.services.proof.closure import derive_closure
from app.services.proof.contracts import (
    CalibrationSelectionReport,
    ClosureThresholds,
    GateInputs,
    LearningReport,
    RuntimeExpectations,
    RuntimeGate,
    TrainRuntimeGate,
)

EXPECTED_BACKEND = "isaac_runtime"
EXPECTED_PROOF_RUNTIME = "dedicated_isaac_connector_insertion_evaluator"
EXPECTED_TRAINING_SOURCE = "isaac_runtime_scripted_expert_rollout"


def _expectations() -> RuntimeExpectations:
    return RuntimeExpectations(
        backend=EXPECTED_BACKEND,
        proof_runtime=EXPECTED_PROOF_RUNTIME,
        training_source=EXPECTED_TRAINING_SOURCE,
    )


def _passing_inputs() -> GateInputs:
    return GateInputs(
        learning_report=LearningReport(
            learning_proven=True,
            proof_eligible=True,
            curated_vs_uncurated_uplift=0.70,
            baseline_success_rate=0.10,
            candidate_success_rate=0.80,
        ),
        runtime_gate=RuntimeGate(
            passed=True,
            runtime_backend=EXPECTED_BACKEND,
            proof_runtime=EXPECTED_PROOF_RUNTIME,
        ),
        train_generation_runtime_gate=TrainRuntimeGate(
            passed=True,
            runtime_backend=EXPECTED_BACKEND,
            actual_train_generation_evidence=True,
            training_trajectory_source=EXPECTED_TRAINING_SOURCE,
        ),
        calibration_selection_report=CalibrationSelectionReport(
            calibration_only_selection_passed=True,
            heldout_excluded=True,
            selected_adapter_frozen_before_heldout=True,
            same_adapter_used_for_baseline_and_candidate=True,
        ),
        heldout_leakage_passed=True,
        actual_rollouts_per_policy=50,
        actual_success_trace_count=1,
    )


def _make_uplift_inconsistent(inputs: GateInputs) -> None:
    inputs.learning_report.baseline_success_rate = 0.79
    inputs.learning_report.candidate_success_rate = 0.80
    inputs.learning_report.curated_vs_uncurated_uplift = 0.70


def test_derive_closure_passes_when_all_eight_gates_pass():
    verdict = derive_closure(inputs=_passing_inputs(), runtime_expectations=_expectations())

    assert verdict.closed is True
    assert verdict.blockers == []
    assert all(verdict.gates.values())
    assert set(verdict.gates) == {
        "train_runtime_matches",
        "heldout_runtime_matches",
        "calibration_selection_matches",
        "heldout_leakage_matches",
        "actual_train_trace_count_matches",
        "post_heldout_guard_matches",
        "learning_matches",
        "rollout_count_matches",
    }


def test_post_heldout_guard_can_be_absent_or_true():
    absent = _passing_inputs()
    explicit = _passing_inputs()
    explicit.post_heldout_guard_passed = True

    assert derive_closure(inputs=absent, runtime_expectations=_expectations()).closed is True
    assert derive_closure(inputs=explicit, runtime_expectations=_expectations()).closed is True


def test_closure_runtime_expectations_are_not_runtime_specific():
    inputs = _passing_inputs()
    inputs.runtime_gate.runtime_backend = "custom_backend"
    inputs.runtime_gate.proof_runtime = "custom_proof_runtime"
    inputs.train_generation_runtime_gate.runtime_backend = "custom_backend"
    inputs.train_generation_runtime_gate.training_trajectory_source = "custom_training_source"
    expectations = RuntimeExpectations(
        backend="custom_backend",
        proof_runtime="custom_proof_runtime",
        training_source="custom_training_source",
    )

    verdict = derive_closure(inputs=inputs, runtime_expectations=expectations)

    assert verdict.closed is True
    assert verdict.gates["train_runtime_matches"] is True
    assert verdict.gates["heldout_runtime_matches"] is True


def test_missing_success_trace_count_blocks_closure():
    inputs = _passing_inputs()
    inputs.actual_success_trace_count = None

    verdict = derive_closure(inputs=inputs, runtime_expectations=_expectations())

    assert verdict.closed is False
    assert verdict.gates["actual_train_trace_count_matches"] is False


@pytest.mark.parametrize("bad_count", [True, "1"])
def test_mutated_non_strict_success_trace_count_blocks_closure(bad_count):
    inputs = _passing_inputs()
    object.__setattr__(inputs, "actual_success_trace_count", bad_count)

    verdict = derive_closure(inputs=inputs, runtime_expectations=_expectations())

    assert verdict.closed is False
    assert verdict.gates["actual_train_trace_count_matches"] is False


@pytest.mark.parametrize("bad_count", [True, "50"])
def test_mutated_non_strict_rollout_count_blocks_closure(bad_count):
    inputs = _passing_inputs()
    object.__setattr__(inputs, "actual_rollouts_per_policy", bad_count)

    verdict = derive_closure(inputs=inputs, runtime_expectations=_expectations())

    assert verdict.closed is False
    assert verdict.gates["rollout_count_matches"] is False


@pytest.mark.parametrize(
    ("mutate", "failed_gate"),
    [
        (
            lambda inputs: setattr(inputs.train_generation_runtime_gate, "passed", False),
            "train_runtime_matches",
        ),
        (
            lambda inputs: setattr(inputs.runtime_gate, "proof_runtime", "other_runtime"),
            "heldout_runtime_matches",
        ),
        (
            lambda inputs: setattr(
                inputs.calibration_selection_report,
                "calibration_only_selection_passed",
                False,
            ),
            "calibration_selection_matches",
        ),
        (
            lambda inputs: setattr(inputs, "heldout_leakage_passed", False),
            "heldout_leakage_matches",
        ),
        (
            lambda inputs: setattr(inputs, "actual_success_trace_count", 0),
            "actual_train_trace_count_matches",
        ),
        (
            lambda inputs: setattr(inputs, "post_heldout_guard_passed", False),
            "post_heldout_guard_matches",
        ),
        (
            lambda inputs: setattr(inputs.learning_report, "curated_vs_uncurated_uplift", 0.19),
            "learning_matches",
        ),
        (
            lambda inputs: setattr(inputs.learning_report, "candidate_success_rate", 0.10),
            "learning_matches",
        ),
        (_make_uplift_inconsistent, "learning_matches"),
        (
            lambda inputs: setattr(inputs, "actual_rollouts_per_policy", 19),
            "rollout_count_matches",
        ),
    ],
)
def test_derive_closure_fails_each_gate(mutate, failed_gate):
    inputs = deepcopy(_passing_inputs())
    mutate(inputs)

    verdict = derive_closure(
        inputs=inputs,
        runtime_expectations=_expectations(),
        thresholds=ClosureThresholds(),
    )

    assert verdict.closed is False
    assert verdict.gates[failed_gate] is False
    assert verdict.blockers
