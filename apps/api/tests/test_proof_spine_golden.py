from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from app.services.proof.closure import derive_closure
from app.services.proof.contracts import (
    CalibrationSelectionReport,
    GateInputs,
    LearningReport,
    RuntimeExpectations,
    RuntimeGate,
    SeedRangeConfig,
    TrainRuntimeGate,
)
from app.services.proof.leakage_guard import (
    burned_seeds_from_channels,
    check_heldout_leakage,
)
from app.services.proof.seed_discipline import validate_seed_ranges

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "proof_spine"

EXPECTED_SHA256 = {
    "heldout_closure_gate_v0_14.json": (
        "ddb30bc37c8c3c79a5634680d712a836b0923ca407459415a49c1619ca0452fc"
    ),
    "mvp2_learning_proven_report.json": (
        "e20a27469f49ecf3b872f4ae53fcb741533a7700541cc37bcdaca52b34012cd5"
    ),
    "calibration_selection_report.json": (
        "f6fce3a7dba0899a3730c3a772c58e7d7be4b385ae195d5b02310a856db2a215"
    ),
    "train_generation_runtime_gate.json": (
        "99eea2f46f8887c03171d236d60af66fd7c9cfc8436a9e2cc9bcd1e18e33335e"
    ),
}


def _read_json(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text())


def _sha256(name: str) -> str:
    return hashlib.sha256((FIXTURE_DIR / name).read_bytes()).hexdigest()


def _v014_gate_inputs() -> tuple[GateInputs, RuntimeExpectations]:
    gate = _read_json("heldout_closure_gate_v0_14.json")
    learning = _read_json("mvp2_learning_proven_report.json")
    calibration = _read_json("calibration_selection_report.json")
    train_runtime = _read_json("train_generation_runtime_gate.json")

    runtime_gate = gate["runtime_gate"]
    expectations = RuntimeExpectations(
        backend=runtime_gate["runtime_backend"],
        proof_runtime=runtime_gate["proof_runtime"],
        training_source=train_runtime["training_trajectory_source"],
    )
    inputs = GateInputs(
        learning_report=LearningReport(
            learning_proven=learning["learning_proven"],
            proof_eligible=learning["proof_eligible"],
            curated_vs_uncurated_uplift=learning["curated_vs_uncurated_uplift"],
            baseline_success_rate=learning["baseline_success_rate"],
            candidate_success_rate=learning["candidate_success_rate"],
        ),
        runtime_gate=RuntimeGate(
            passed=runtime_gate["passed"],
            runtime_backend=runtime_gate["runtime_backend"],
            proof_runtime=runtime_gate["proof_runtime"],
        ),
        train_generation_runtime_gate=TrainRuntimeGate(
            passed=train_runtime["passed"],
            runtime_backend=train_runtime["runtime_backend"],
            actual_train_generation_evidence=train_runtime["actual_train_generation_evidence"],
            training_trajectory_source=train_runtime["training_trajectory_source"],
        ),
        calibration_selection_report=CalibrationSelectionReport(
            calibration_only_selection_passed=calibration["calibration_only_selection_passed"],
            heldout_excluded=calibration["heldout_excluded"],
            selected_adapter_frozen_before_heldout=calibration[
                "selected_adapter_frozen_before_heldout"
            ],
            same_adapter_used_for_baseline_and_candidate=calibration[
                "same_adapter_used_for_baseline_and_candidate"
            ],
        ),
        heldout_leakage_passed=gate["heldout_leakage_guard"]["passed"] is True,
        actual_rollouts_per_policy=gate["actual_rollouts_per_policy"],
        actual_success_trace_count=train_runtime["generated_success_count"],
    )
    return inputs, expectations


def test_v014_fixture_hashes_are_pinned():
    assert {name: _sha256(name) for name in EXPECTED_SHA256} == EXPECTED_SHA256


def test_v014_closure_reconstruction_matches_archived_verdict():
    gate = _read_json("heldout_closure_gate_v0_14.json")
    learning = _read_json("mvp2_learning_proven_report.json")
    inputs, expectations = _v014_gate_inputs()

    verdict = derive_closure(inputs=inputs, runtime_expectations=expectations)

    assert verdict.closed is True
    assert verdict.closed == gate["mvp2_closed"]
    assert verdict.closed == gate["mvp2c_close_minimum_passed"]
    assert verdict.closed == gate["proof_eligible"]
    assert verdict.closed == learning["learning_proven"]
    assert verdict.blockers == gate["blockers"]
    assert all(verdict.gates.values())


def test_v014_leakage_guard_reconstructs_as_disjoint():
    gate = _read_json("heldout_closure_gate_v0_14.json")
    heldout = burned_seeds_from_channels(
        {"heldout": gate["heldout_leakage_guard"]["heldout_scenario_ids"]}
    )
    burned = burned_seeds_from_channels(
        gate["heldout_leakage_guard"]["checked_channels"],
        include_ranges=[(39000, 39029)],
    )

    report = check_heldout_leakage(held_out=heldout, burned=burned)

    assert report.passed is True
    assert report.overlap == []
    assert gate["heldout_leakage_guard"]["passed"] is True


def test_v014_seed_ranges_are_valid_before_spend_and_rejected_after_spend():
    config = SeedRangeConfig(
        train=(19000, 19359),
        calibration=[(20000, 20029), (39000, 39029)],
        heldout=(40000, 40049),
        pre_closure_burned=[(19000, 19359), (20000, 20029), (39000, 39029)],
    )

    before_spend = validate_seed_ranges(config)
    config.spent_no_reuse = [(40000, 40049)]
    after_spend = validate_seed_ranges(config)

    assert before_spend.passed is True
    assert after_spend.passed is False
    assert any("spent/no-reuse" in violation for violation in after_spend.violations)
