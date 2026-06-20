from __future__ import annotations

from .contracts import ClosureThresholds, ClosureVerdict, GateInputs, RuntimeExpectations


def _numeric(value: float | int | None) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if not isinstance(value, int | float):
        return None
    return float(value)


def _strict_int_at_least(value: object, minimum: int) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and isinstance(minimum, int)
        and not isinstance(minimum, bool)
        and value >= minimum
    )


def _uplift_matches_rates(
    *,
    uplift: float | None,
    baseline_rate: float | None,
    candidate_rate: float | None,
) -> bool:
    if uplift is None or baseline_rate is None or candidate_rate is None:
        return False
    return abs(uplift - (candidate_rate - baseline_rate)) <= 1e-9


def derive_closure(
    *,
    inputs: GateInputs,
    runtime_expectations: RuntimeExpectations,
    thresholds: ClosureThresholds | None = None,
) -> ClosureVerdict:
    """Derive the producer-side 8-gate closure verdict."""

    thresholds = thresholds or ClosureThresholds()
    learning = inputs.learning_report
    runtime = inputs.runtime_gate
    train_runtime = inputs.train_generation_runtime_gate
    calibration = inputs.calibration_selection_report

    uplift = _numeric(learning.curated_vs_uncurated_uplift)
    baseline_rate = _numeric(learning.baseline_success_rate)
    candidate_rate = _numeric(learning.candidate_success_rate)

    gates = {
        "train_runtime_matches": (
            train_runtime.passed is True
            and train_runtime.runtime_backend == runtime_expectations.backend
            and train_runtime.actual_train_generation_evidence is True
            and train_runtime.training_trajectory_source == runtime_expectations.training_source
        ),
        "heldout_runtime_matches": (
            runtime.passed is True
            and runtime.runtime_backend == runtime_expectations.backend
            and runtime.proof_runtime == runtime_expectations.proof_runtime
        ),
        "calibration_selection_matches": (
            calibration.calibration_only_selection_passed is True
            and calibration.heldout_excluded is True
            and calibration.selected_adapter_frozen_before_heldout is True
            and calibration.same_adapter_used_for_baseline_and_candidate is True
        ),
        "heldout_leakage_matches": inputs.heldout_leakage_passed is True,
        "actual_train_trace_count_matches": _strict_int_at_least(
            inputs.actual_success_trace_count,
            thresholds.trace_minimum,
        ),
        "post_heldout_guard_matches": inputs.post_heldout_guard_passed is not False,
        "learning_matches": (
            learning.learning_proven is True
            and learning.proof_eligible is True
            and uplift is not None
            and uplift >= thresholds.uplift_min
            and baseline_rate is not None
            and candidate_rate is not None
            and candidate_rate > baseline_rate
            and _uplift_matches_rates(
                uplift=uplift,
                baseline_rate=baseline_rate,
                candidate_rate=candidate_rate,
            )
        ),
        "rollout_count_matches": _strict_int_at_least(
            inputs.actual_rollouts_per_policy,
            thresholds.min_rollouts_per_policy,
        ),
    }

    blockers = _blockers_for(gates, thresholds)
    return ClosureVerdict(closed=all(gates.values()), gates=gates, blockers=blockers)


def _blockers_for(gates: dict[str, bool], thresholds: ClosureThresholds) -> list[str]:
    blockers: list[str] = []
    messages = {
        "train_runtime_matches": "training runtime evidence did not match expectations",
        "heldout_runtime_matches": "held-out runtime evidence did not match expectations",
        "calibration_selection_matches": "calibration-only selection guard did not pass",
        "heldout_leakage_matches": "held-out leakage guard did not pass",
        "actual_train_trace_count_matches": (
            f"success trace count was below {thresholds.trace_minimum}"
        ),
        "post_heldout_guard_matches": "post-held-out guard failed",
        "learning_matches": (
            f"learning evidence did not prove positive uplift >= {thresholds.uplift_min}"
        ),
        "rollout_count_matches": (
            "held-out rollout count was below "
            f"{thresholds.min_rollouts_per_policy} per policy"
        ),
    }
    for gate_name, passed in gates.items():
        if not passed:
            blockers.append(messages[gate_name])
    return blockers
