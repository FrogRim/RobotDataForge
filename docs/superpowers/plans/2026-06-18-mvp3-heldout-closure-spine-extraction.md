# Held-Out / Closure Integrity Spine Extraction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the task/source-agnostic held-out/closure integrity spine (seed discipline + leakage guard + 8-gate closure) into a clean `apps/api/app/services/proof/` package without touching `run_mvp2c`. Golden tests assert archive-stored closure verdict fields match and reconstructed 8 gates are true; they do not claim per-gate artifact identity because the v0.14 closure artifact does not store per-gate booleans.

**Architecture:** A new Pydantic-typed package re-implements the closure contract with Isaac-specific constants lifted to injected `RuntimeExpectations` parameters. The MVP-3 spine intentionally adds fail-closed hardening for missing success-trace counts, strict proof evidence coercion rejection, empty held-out rejection, and uplift/rate consistency, so it is not a byte-for-byte or branch-for-branch clone of the v0.14 archive. A golden test pins the extraction against the committed v0.14 closure gate by matching archived final verdict fields and reconstructed passing gates. The spine stays code-independent from `verify_mvp2_package.py` (producer vs independent auditor).

**Tech Stack:** Python 3.11+, Pydantic, pytest. Pure logic — no numpy/h5py/Isaac.

Spec: `docs/superpowers/specs/2026-06-18-mvp3-heldout-closure-spine-extraction-design.md`

**Post-review hardening:** The final implementation uses strict Pydantic
contract fields for proof booleans, rates/uplift, thresholds, and seed range
endpoints; rejects malformed truthy evidence; fails `learning_matches` when
reported uplift disagrees with `candidate_success_rate - baseline_success_rate`;
and treats empty held-out sets as missing evidence rather than passing leakage
proof.

---

## File Structure

```
apps/api/app/services/proof/
  __init__.py            # exports: derive_closure, check_heldout_leakage, validate_seed_ranges + models
  contracts.py           # Pydantic models (inputs + outputs)
  closure.py             # derive_closure(): 8-gate AND, Isaac constants parameterized
  leakage_guard.py       # burned-set derivation + disjointness
  seed_discipline.py     # recorded-range validation + spent/no-reuse
apps/api/tests/
  fixtures/proof_spine/  # copied v0.14 inputs for the golden test (proof package untouched)
    heldout_closure_gate_v0_14.json
    mvp2_learning_proven_report.json
    calibration_selection_report.json
    train_generation_runtime_gate.json
  test_proof_spine_contracts.py
  test_proof_spine_closure.py
  test_proof_spine_leakage.py
  test_proof_spine_seed_discipline.py
  test_proof_spine_independence.py
```

Constants lifted from the archive (used as v0.14 defaults / fixtures):
`ISAAC_PROOF_RUNTIME="dedicated_isaac_connector_insertion_evaluator"`,
`MIN_PROOF_ROLLOUTS_PER_POLICY=20`, training source
`"isaac_runtime_scripted_expert_rollout"`, backend `"isaac_runtime"`, trace minimum `1`.

---

## Task 1: Package skeleton + Pydantic contracts

**Files:**
- Create: `apps/api/app/services/proof/__init__.py`
- Create: `apps/api/app/services/proof/contracts.py`
- Test: `apps/api/tests/test_proof_spine_contracts.py`

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_proof_spine_contracts.py
from app.services.proof.contracts import (
    RuntimeExpectations, ClosureThresholds, GateInputs,
    RuntimeGate, TrainRuntimeGate, CalibrationSelectionReport, LearningReport,
)


def test_thresholds_v014_defaults():
    t = ClosureThresholds()
    assert t.uplift_min == 0.20
    assert t.min_rollouts_per_policy == 20
    assert t.trace_minimum == 1


def test_gate_inputs_constructs():
    gi = GateInputs(
        learning_report=LearningReport(),
        runtime_gate=RuntimeGate(passed=True),
        train_generation_runtime_gate=TrainRuntimeGate(passed=True),
        calibration_selection_report=CalibrationSelectionReport(),
        heldout_leakage_passed=True,
        actual_rollouts_per_policy=50,
    )
    assert gi.actual_rollouts_per_policy == 50
    assert gi.post_heldout_guard_passed is None


def test_runtime_expectations_isaac():
    r = RuntimeExpectations(
        backend="isaac_runtime",
        proof_runtime="dedicated_isaac_connector_insertion_evaluator",
        training_source="isaac_runtime_scripted_expert_rollout",
    )
    assert r.backend == "isaac_runtime"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest apps/api/tests/test_proof_spine_contracts.py -q`
Expected: FAIL — `ModuleNotFoundError: app.services.proof`

- [ ] **Step 3: Write the package + contracts**

```python
# apps/api/app/services/proof/__init__.py
"""Task/source-agnostic held-out & closure integrity spine (MVP-3 enabler).

Re-implements the v0.14 closure contract with Isaac-specific values injected as
parameters. Independent from scripts/verify_mvp2_package.py by design (producer
vs independent auditor); they agree on the contract, never share code.
"""
from .contracts import (  # noqa: F401
    RuntimeExpectations, ClosureThresholds, GateInputs, ClosureVerdict,
    RuntimeGate, TrainRuntimeGate, CalibrationSelectionReport, LearningReport,
    LeakageReport, SeedRangeConfig, SeedDisciplineReport,
)
```

```python
# apps/api/app/services/proof/contracts.py
from __future__ import annotations

from pydantic import BaseModel


class RuntimeExpectations(BaseModel):
    """Injected, task/source-specific expectations (replaces hardcoded Isaac strings)."""
    backend: str
    proof_runtime: str
    training_source: str


class ClosureThresholds(BaseModel):
    uplift_min: float = 0.20
    min_rollouts_per_policy: int = 20
    trace_minimum: int = 1


class RuntimeGate(BaseModel):
    passed: bool = False
    runtime_backend: str | None = None
    proof_runtime: str | None = None


class TrainRuntimeGate(BaseModel):
    passed: bool = False
    runtime_backend: str | None = None
    actual_train_generation_evidence: bool | None = None
    training_trajectory_source: str | None = None


class CalibrationSelectionReport(BaseModel):
    calibration_only_selection_passed: bool | None = None
    heldout_excluded: bool | None = None
    selected_adapter_frozen_before_heldout: bool | None = None
    same_adapter_used_for_baseline_and_candidate: bool | None = None


class LearningReport(BaseModel):
    learning_proven: bool | None = None
    proof_eligible: bool | None = None
    curated_vs_uncurated_uplift: float | None = None
    baseline_success_rate: float | None = None
    candidate_success_rate: float | None = None


class GateInputs(BaseModel):
    learning_report: LearningReport
    runtime_gate: RuntimeGate
    train_generation_runtime_gate: TrainRuntimeGate
    calibration_selection_report: CalibrationSelectionReport
    heldout_leakage_passed: bool
    actual_rollouts_per_policy: int
    actual_success_trace_count: int | None = None
    post_heldout_guard_passed: bool | None = None


class ClosureVerdict(BaseModel):
    closed: bool
    gates: dict[str, bool]
    blockers: list[str]


class LeakageReport(BaseModel):
    passed: bool
    overlap: list[int]
    burned_count: int
    held_out_count: int


class SeedRangeConfig(BaseModel):
    train: tuple[int, int]
    calibration: list[tuple[int, int]]
    heldout: tuple[int, int]
    pre_closure_burned: list[tuple[int, int]] = []
    spent_no_reuse: list[tuple[int, int]] = []


class SeedDisciplineReport(BaseModel):
    passed: bool
    violations: list[str]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest apps/api/tests/test_proof_spine_contracts.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Checkpoint**

Run `git status --short` and record changed files. Do not commit here; commit,
push, and PR require later explicit authorization and Lore protocol.

---

## Task 2: Leakage guard (burned-set derivation + disjointness)

**Files:**
- Create: `apps/api/app/services/proof/leakage_guard.py`
- Test: `apps/api/tests/test_proof_spine_leakage.py`

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_proof_spine_leakage.py
from app.services.proof.leakage_guard import (
    burned_seeds_from_channels, check_heldout_leakage, seeds_in_range,
)


def test_burned_set_from_channels_extracts_trailing_ints():
    channels = {"calibration_selector": ["calibration_20000", "calibration_20001"],
                "training": ["train_failure_19200"]}
    assert burned_seeds_from_channels(channels) == {20000, 20001, 19200}


def test_burned_set_includes_extra_ranges():
    burned = burned_seeds_from_channels({}, include_ranges=[(39000, 39002)])
    assert burned == {39000, 39001, 39002}


def test_disjoint_passes():
    report = check_heldout_leakage(held_out={50000, 50001}, burned={19200, 39000})
    assert report.passed is True and report.overlap == []


def test_overlap_fails():
    report = check_heldout_leakage(held_out={50000, 39000}, burned={39000})
    assert report.passed is False and report.overlap == [39000]


def test_seeds_in_range_inclusive():
    assert seeds_in_range((50000, 50002)) == {50000, 50001, 50002}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest apps/api/tests/test_proof_spine_leakage.py -q`
Expected: FAIL — `ModuleNotFoundError: ...leakage_guard`

- [ ] **Step 3: Write the implementation**

```python
# apps/api/app/services/proof/leakage_guard.py
from __future__ import annotations

import re

from .contracts import LeakageReport


def _trailing_int(label: str) -> int | None:
    m = re.search(r"(\d+)$", str(label))
    return int(m.group(1)) if m else None


def _strict_int_at_least(value: object, minimum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= int(minimum)


def seeds_in_range(span: tuple[int, int]) -> set[int]:
    lo, hi = span
    return set(range(lo, hi + 1))


def burned_seeds_from_channels(
    checked_channels: dict[str, list[str]],
    include_ranges: list[tuple[int, int]] | None = None,
) -> set[int]:
    """Derive the union of already-used seeds from leakage-guard channels, plus
    any explicit extra ranges (e.g. a fresh-calibration band)."""
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
        passed=not overlap,
        overlap=overlap,
        burned_count=len(burned),
        held_out_count=len(held_out),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest apps/api/tests/test_proof_spine_leakage.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Update `__init__.py` exports**

Add to `apps/api/app/services/proof/__init__.py`:

```python
from .leakage_guard import (  # noqa: F401
    burned_seeds_from_channels, check_heldout_leakage, seeds_in_range,
)
```

- [ ] **Step 6: Checkpoint**

Run `git status --short` and record changed files. Do not commit here; commit,
push, and PR require later explicit authorization and Lore protocol.

---

## Task 3: Closure derivation (8-gate AND, parameterized)

**Files:**
- Create: `apps/api/app/services/proof/closure.py`
- Test: `apps/api/tests/test_proof_spine_closure.py`

- [ ] **Step 1: Write the failing test (unit: green case + each gate negative)**

```python
from app.services.proof.closure import derive_closure
from app.services.proof.contracts import (
    RuntimeExpectations, GateInputs, RuntimeGate, TrainRuntimeGate,
    CalibrationSelectionReport, LearningReport,
)

ISAAC = RuntimeExpectations(
    backend="isaac_runtime",
    proof_runtime="dedicated_isaac_connector_insertion_evaluator",
    training_source="isaac_runtime_scripted_expert_rollout",
)


def _passing_inputs() -> GateInputs:
    return GateInputs(
        learning_report=LearningReport(
            learning_proven=True, proof_eligible=True,
            curated_vs_uncurated_uplift=0.70,
            baseline_success_rate=0.10, candidate_success_rate=0.80,
        ),
        runtime_gate=RuntimeGate(
            passed=True, runtime_backend="isaac_runtime",
            proof_runtime="dedicated_isaac_connector_insertion_evaluator",
        ),
        train_generation_runtime_gate=TrainRuntimeGate(
            passed=True, runtime_backend="isaac_runtime",
            actual_train_generation_evidence=True,
            training_trajectory_source="isaac_runtime_scripted_expert_rollout",
        ),
        calibration_selection_report=CalibrationSelectionReport(
            calibration_only_selection_passed=True, heldout_excluded=True,
            selected_adapter_frozen_before_heldout=True,
            same_adapter_used_for_baseline_and_candidate=True,
        ),
        heldout_leakage_passed=True,
        actual_rollouts_per_policy=50,
        actual_success_trace_count=28,
    )


def test_green_case_closes():
    verdict = derive_closure(_passing_inputs(), ISAAC)
    assert verdict.closed is True
    assert all(verdict.gates.values())
    assert verdict.blockers == []


def test_uplift_below_threshold_blocks():
    gi = _passing_inputs()
    gi.learning_report.curated_vs_uncurated_uplift = 0.19
    verdict = derive_closure(gi, ISAAC)
    assert verdict.closed is False
    assert verdict.gates["learning_matches"] is False


def test_rollout_count_below_minimum_blocks():
    gi = _passing_inputs()
    gi.actual_rollouts_per_policy = 19
    verdict = derive_closure(gi, ISAAC)
    assert verdict.closed is False
    assert verdict.gates["rollout_count_matches"] is False


def test_leakage_failure_blocks():
    gi = _passing_inputs()
    gi.heldout_leakage_passed = False
    verdict = derive_closure(gi, ISAAC)
    assert verdict.closed is False
    assert verdict.gates["heldout_leakage_matches"] is False


def test_train_runtime_failure_blocks():
    gi = _passing_inputs()
    gi.train_generation_runtime_gate.passed = False
    verdict = derive_closure(gi, ISAAC)
    assert verdict.closed is False
    assert verdict.gates["train_runtime_matches"] is False


def test_heldout_runtime_mismatch_blocks():
    gi = _passing_inputs()
    gi.runtime_gate.proof_runtime = "wrong_evaluator"
    verdict = derive_closure(gi, ISAAC)
    assert verdict.closed is False
    assert verdict.gates["heldout_runtime_matches"] is False


def test_candidate_not_above_baseline_blocks():
    gi = _passing_inputs()
    gi.learning_report.candidate_success_rate = 0.10
    verdict = derive_closure(gi, ISAAC)
    assert verdict.closed is False
    assert verdict.gates["learning_matches"] is False


def test_calibration_selection_failure_blocks():
    gi = _passing_inputs()
    gi.calibration_selection_report.heldout_excluded = False
    verdict = derive_closure(gi, ISAAC)
    assert verdict.closed is False
    assert verdict.gates["calibration_selection_matches"] is False


def test_trace_count_below_minimum_blocks():
    gi = _passing_inputs()
    gi.actual_success_trace_count = 0
    verdict = derive_closure(gi, ISAAC, )
    assert verdict.gates["actual_train_trace_count_matches"] is False


def test_post_heldout_guard_none_is_ok():
    gi = _passing_inputs()
    gi.post_heldout_guard_passed = None
    assert derive_closure(gi, ISAAC).gates["post_heldout_guard_matches"] is True


def test_post_heldout_guard_false_blocks():
    gi = _passing_inputs()
    gi.post_heldout_guard_passed = False
    verdict = derive_closure(gi, ISAAC)
    assert verdict.closed is False
    assert verdict.gates["post_heldout_guard_matches"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest apps/api/tests/test_proof_spine_closure.py -q`
Expected: FAIL — `ModuleNotFoundError: ...closure`

- [ ] **Step 3: Write the implementation**

```python
# apps/api/app/services/proof/closure.py
from __future__ import annotations

from .contracts import ClosureThresholds, ClosureVerdict, GateInputs, RuntimeExpectations

_BLOCKER_TEXT = {
    "train_runtime_matches": "Closure requires actual runtime train-generation evidence to pass.",
    "heldout_runtime_matches": "Closure requires the dedicated held-out runtime gate to pass.",
    "calibration_selection_matches": "Closure requires the calibration-only adapter selection guard to pass.",
    "heldout_leakage_matches": "Closure requires the held-out leakage guard to pass.",
    "actual_train_trace_count_matches": "Closure requires the train success-trace count to meet the minimum.",
    "post_heldout_guard_matches": "Closure requires the post-held-out guard to pass.",
    "learning_matches": "Closure requires proven learning uplift >= threshold with candidate above baseline.",
    "rollout_count_matches": "Closure requires the minimum rollouts per policy.",
}


def derive_closure(
    inputs: GateInputs,
    runtime: RuntimeExpectations,
    thresholds: ClosureThresholds | None = None,
) -> ClosureVerdict:
    """8-gate AND closure. Runtime/source binding is injected, and missing
    success-trace count is fail-closed for MVP-3 proof reuse."""
    thresholds = thresholds or ClosureThresholds()
    lr = inputs.learning_report
    uplift = lr.curated_vs_uncurated_uplift
    trg = inputs.train_generation_runtime_gate
    rg = inputs.runtime_gate
    csr = inputs.calibration_selection_report

    gates = {
        "train_runtime_matches": (
            trg.passed is True
            and trg.runtime_backend == runtime.backend
            and trg.actual_train_generation_evidence is True
            and trg.training_trajectory_source == runtime.training_source
        ),
        "heldout_runtime_matches": (
            rg.passed is True
            and rg.runtime_backend == runtime.backend
            and rg.proof_runtime == runtime.proof_runtime
        ),
        "calibration_selection_matches": (
            csr.calibration_only_selection_passed is True
            and csr.heldout_excluded is True
            and csr.selected_adapter_frozen_before_heldout is True
            and csr.same_adapter_used_for_baseline_and_candidate is True
        ),
        "heldout_leakage_matches": inputs.heldout_leakage_passed is True,
        "actual_train_trace_count_matches": _strict_int_at_least(
            inputs.actual_success_trace_count,
            thresholds.trace_minimum,
        ),
        "post_heldout_guard_matches": (
            inputs.post_heldout_guard_passed is None or inputs.post_heldout_guard_passed is True
        ),
        "learning_matches": (
            lr.learning_proven is True
            and lr.proof_eligible is True
            and uplift is not None
            and uplift >= thresholds.uplift_min
            and lr.baseline_success_rate is not None
            and lr.candidate_success_rate is not None
            and lr.candidate_success_rate > lr.baseline_success_rate
        ),
        "rollout_count_matches": _strict_int_at_least(
            inputs.actual_rollouts_per_policy,
            thresholds.min_rollouts_per_policy,
        ),
    }
    closed = all(gates.values())
    blockers = [_BLOCKER_TEXT[name] for name, ok in gates.items() if not ok]
    return ClosureVerdict(closed=closed, gates=gates, blockers=blockers)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest apps/api/tests/test_proof_spine_closure.py -q`
Expected: PASS (all closure tests pass)

- [ ] **Step 5: Update `__init__.py` exports**

Add to `apps/api/app/services/proof/__init__.py`:

```python
from .closure import derive_closure  # noqa: F401
```

- [ ] **Step 6: Checkpoint**

Run `git status --short` and record changed files. Do not commit here; commit,
push, and PR require later explicit authorization and Lore protocol.

---

## Task 4: Golden test — archive verdict fields + reconstructed gates (the safety net)

**Files:**
- Create: `apps/api/tests/fixtures/proof_spine/heldout_closure_gate_v0_14.json` (copy)
- Create: `apps/api/tests/fixtures/proof_spine/mvp2_learning_proven_report.json` (copy)
- Create: `apps/api/tests/fixtures/proof_spine/calibration_selection_report.json` (copy)
- Create: `apps/api/tests/fixtures/proof_spine/train_generation_runtime_gate.json` (copy)
- Modify: `apps/api/tests/test_proof_spine_closure.py` (add golden test)

- [ ] **Step 1: Verify source hashes, then copy the four recorded v0.14 inputs into the test fixtures dir**

Run:

```bash
sha256sum storage/proof_evidence/mvp2c_isaac_training_calibration/calibration_selection_report.json
sha256sum storage/proof_evidence/mvp2c_isaac_training_calibration/train_generation_runtime_gate.json
```

Expected:

```text
f6fce3a7dba0899a3730c3a772c58e7d7be4b385ae195d5b02310a856db2a215  storage/proof_evidence/mvp2c_isaac_training_calibration/calibration_selection_report.json
99eea2f46f8887c03171d236d60af66fd7c9cfc8436a9e2cc9bcd1e18e33335e  storage/proof_evidence/mvp2c_isaac_training_calibration/train_generation_runtime_gate.json
```

These must match `calibration_selection_report_sha256` and
`parent_train_generation_runtime_gate_sha256` in
`heldout_closure_gate_v0_14.json`. If either hash differs, stop — the fixture
source is not trusted.

Then run:

```bash
mkdir -p apps/api/tests/fixtures/proof_spine
cp docs/proof/mvp2_learning_proven_evidence_package/data/heldout_closure_gate_v0_14.json \
   docs/proof/mvp2_learning_proven_evidence_package/data/mvp2_learning_proven_report.json \
   apps/api/tests/fixtures/proof_spine/
cp storage/proof_evidence/mvp2c_isaac_training_calibration/calibration_selection_report.json \
   storage/proof_evidence/mvp2c_isaac_training_calibration/train_generation_runtime_gate.json \
   apps/api/tests/fixtures/proof_spine/
```

Expected: 4 files present under `apps/api/tests/fixtures/proof_spine/`, with the
two storage-derived fixtures hash-bound to the closure gate.

- [ ] **Step 2: Write the failing golden test**

Add to `apps/api/tests/test_proof_spine_closure.py`:

```python
import json
from pathlib import Path

from app.services.proof.contracts import GateInputs

FIXTURES = Path(__file__).parent / "fixtures" / "proof_spine"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_golden_v014_closure_reconstructs_archive_verdict():
    """Recorded v0.14 inputs must reproduce stored closure verdict fields.

    The closure artifact does not store per-gate booleans, so this test asserts
    reconstructed gates are all true without claiming per-gate artifact identity.
    """
    gate = _load("heldout_closure_gate_v0_14.json")
    lr_doc = _load("mvp2_learning_proven_report.json")
    csr = _load("calibration_selection_report.json")
    trg = _load("train_generation_runtime_gate.json")

    inputs = GateInputs(
        learning_report=LearningReport(
            learning_proven=lr_doc.get("learning_proven"),
            proof_eligible=lr_doc.get("proof_eligible"),
            curated_vs_uncurated_uplift=gate.get("curated_vs_uncurated_uplift"),
            baseline_success_rate=gate.get("baseline_success_rate"),
            candidate_success_rate=gate.get("candidate_success_rate"),
        ),
        runtime_gate=RuntimeGate(**{
            k: gate["runtime_gate"].get(k)
            for k in ("passed", "runtime_backend", "proof_runtime")
        }),
        train_generation_runtime_gate=TrainRuntimeGate(**{
            k: trg.get(k) for k in (
                "passed", "runtime_backend",
                "actual_train_generation_evidence", "training_trajectory_source",
            )
        }),
        calibration_selection_report=CalibrationSelectionReport(**{
            k: csr.get(k) for k in (
                "calibration_only_selection_passed", "heldout_excluded",
                "selected_adapter_frozen_before_heldout",
                "same_adapter_used_for_baseline_and_candidate",
            )
        }),
        heldout_leakage_passed=gate["heldout_leakage_guard"].get("passed") is True,
        actual_rollouts_per_policy=gate.get("actual_rollouts_per_policy"),
        actual_success_trace_count=trg.get("generated_success_count"),
    )
    verdict = derive_closure(inputs, ISAAC)
    assert verdict.closed is True, verdict.blockers
    assert verdict.closed == gate.get("mvp2_closed")
    assert verdict.closed == gate.get("mvp2c_close_minimum_passed")
    assert verdict.closed == gate.get("proof_eligible")
    assert verdict.closed == lr_doc.get("learning_proven")
    assert verdict.blockers == gate.get("blockers")
    assert all(verdict.gates.values())
```

Note on field sourcing: `learning_proven`/`proof_eligible` come from the learning
report because `heldout_closure_gate_v0_14.json` does not store top-level
`learning_proven`; `curated_vs_uncurated_uplift`/`baseline_success_rate`/
`candidate_success_rate` and `runtime_gate`/`heldout_leakage_guard`/
`actual_rollouts_per_policy` are embedded in the closure gate.

- [ ] **Step 3: Run test to verify it fails (then passes)**

Run: `uv run pytest apps/api/tests/test_proof_spine_closure.py::test_golden_v014_closure_reconstructs_archive_verdict -v`
Expected: PASS (the spine reproduces recorded v0.14 closure verdict fields and
reconstructs all gates true). If it FAILS, the extraction diverges from the
archive evidence — fix the spine, do **not** change the fixture.

- [ ] **Step 4: Add the golden leakage assertion**

Add to `apps/api/tests/test_proof_spine_leakage.py`:

```python
import json
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures" / "proof_spine"


def test_golden_v014_heldout_is_disjoint():
    gate = json.loads((FIXTURES / "heldout_closure_gate_v0_14.json").read_text())
    channels = gate["heldout_leakage_guard"]["checked_channels"]
    burned = burned_seeds_from_channels(channels, include_ranges=[(39000, 39029)])
    held_out = set(range(40000, 40050))
    report = check_heldout_leakage(held_out, burned)
    assert report.passed is True
    assert report.overlap == []
    assert gate["heldout_leakage_guard"].get("passed") is True
```

- [ ] **Step 5: Run both golden tests**

Run: `uv run pytest apps/api/tests/test_proof_spine_closure.py apps/api/tests/test_proof_spine_leakage.py -q`
Expected: PASS (all)

- [ ] **Step 6: Checkpoint**

Run `git status --short` and record changed files. Do not commit here; commit,
push, and PR require later explicit authorization and Lore protocol.

---

## Task 5: Parameterization + independence guards

**Files:**
- Create: `apps/api/tests/test_proof_spine_independence.py`
- Modify: `apps/api/tests/test_proof_spine_closure.py` (add non-Isaac parameterization test)

- [ ] **Step 1: Write the parameterization test (non-Isaac expectations)**

Add to `apps/api/tests/test_proof_spine_closure.py`:

```python
def test_parameterization_non_isaac_runtime():
    """A different (task, source) supplies its own expectations; the AND logic
    is unchanged and still closes when everything matches."""
    other = RuntimeExpectations(
        backend="mujoco_runtime",
        proof_runtime="some_other_evaluator",
        training_source="mujoco_scripted_rollout",
    )
    gi = _passing_inputs()
    gi.runtime_gate.runtime_backend = "mujoco_runtime"
    gi.runtime_gate.proof_runtime = "some_other_evaluator"
    gi.train_generation_runtime_gate.runtime_backend = "mujoco_runtime"
    gi.train_generation_runtime_gate.training_trajectory_source = "mujoco_scripted_rollout"
    verdict = derive_closure(gi, other)
    assert verdict.closed is True


def test_parameterization_rejects_mismatched_backend():
    gi = _passing_inputs()  # inputs say isaac_runtime
    other = RuntimeExpectations(
        backend="mujoco_runtime", proof_runtime="x", training_source="y",
    )
    verdict = derive_closure(gi, other)
    assert verdict.gates["heldout_runtime_matches"] is False
```

- [ ] **Step 2: Write the independence + no-Isaac-constant guard test**

```python
# apps/api/tests/test_proof_spine_independence.py
import ast
from pathlib import Path

PROOF_DIR = Path(__file__).resolve().parents[3] / "apps/api/app/services/proof"
SPINE_FILES = ["closure.py", "leakage_guard.py", "seed_discipline.py", "contracts.py"]


def test_spine_does_not_import_the_independent_verifier():
    """Producer (spine) and auditor (verify_mvp2_package) must not share code."""
    for name in SPINE_FILES:
        path = PROOF_DIR / name
        if not path.exists():
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert "verify_mvp2_package" not in node.module
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "verify_mvp2_package" not in alias.name


def test_spine_has_no_hardcoded_isaac_constants():
    """Isaac-specific strings must be injected, not hardcoded in the spine logic."""
    for name in ("closure.py", "leakage_guard.py", "seed_discipline.py"):
        path = PROOF_DIR / name
        if not path.exists():
            continue
        text = path.read_text()
        assert "isaac_runtime" not in text, f"{name} hardcodes isaac_runtime"
        assert "dedicated_isaac_connector_insertion_evaluator" not in text
```

- [ ] **Step 3: Run the tests to verify they pass**

Run: `uv run pytest apps/api/tests/test_proof_spine_closure.py apps/api/tests/test_proof_spine_independence.py -q`
Expected: PASS. If `test_spine_has_no_hardcoded_isaac_constants` fails, move the
offending string into a `RuntimeExpectations`/`ClosureThresholds` field.

- [ ] **Step 4: Checkpoint**

Run `git status --short` and record changed files. Do not commit here; commit,
push, and PR require later explicit authorization and Lore protocol.

---

## Task 6: Seed-range discipline (recorded-range validation + configured spent/no-reuse rejection)

**Files:**
- Create: `apps/api/app/services/proof/seed_discipline.py`
- Test: `apps/api/tests/test_proof_spine_seed_discipline.py`

- [ ] **Step 1: Write the failing test**

```python
# apps/api/tests/test_proof_spine_seed_discipline.py
from app.services.proof.contracts import SeedRangeConfig
from app.services.proof.seed_discipline import validate_seed_ranges


def _neutral_config() -> SeedRangeConfig:
    return SeedRangeConfig(
        train=(10000, 10359),
        calibration=[(20000, 20029), (30000, 30029)],
        heldout=(50000, 50049),
        pre_closure_burned=[(10000, 10359), (20000, 20029), (30000, 30029)],
    )


def test_neutral_ranges_are_disciplined_before_spend():
    report = validate_seed_ranges(_neutral_config())
    assert report.passed is True and report.violations == []


def test_heldout_overlapping_train_is_rejected():
    cfg = _neutral_config()
    cfg.heldout = (10100, 10120)  # inside train
    report = validate_seed_ranges(cfg)
    assert report.passed is False
    assert any("held-out" in v for v in report.violations)


def test_heldout_inside_pre_closure_burned_is_rejected():
    cfg = _neutral_config()
    cfg.pre_closure_burned = cfg.pre_closure_burned + [(50000, 50049)]
    report = validate_seed_ranges(cfg)
    assert report.passed is False
    assert any("burned" in v for v in report.violations)


def test_configured_spent_no_reuse_heldout_is_rejected():
    cfg = _neutral_config()
    cfg.heldout = (40000, 40049)
    cfg.spent_no_reuse = [(40000, 40049)]
    report = validate_seed_ranges(cfg)
    assert report.passed is False
    assert any("spent/no-reuse" in v for v in report.violations)


def test_train_calibration_overlap_is_rejected():
    cfg = _v014_config()
    cfg.calibration = [(19050, 19060)]  # inside train
    report = validate_seed_ranges(cfg)
    assert report.passed is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest apps/api/tests/test_proof_spine_seed_discipline.py -q`
Expected: FAIL — `ModuleNotFoundError: ...seed_discipline`

- [ ] **Step 3: Write the implementation**

```python
# apps/api/app/services/proof/seed_discipline.py
from __future__ import annotations

from .contracts import SeedDisciplineReport, SeedRangeConfig
from .leakage_guard import seeds_in_range


def _union(spans: list[tuple[int, int]]) -> set[int]:
    out: set[int] = set()
    for span in spans:
        out |= seeds_in_range(span)
    return out


def validate_seed_ranges(config: SeedRangeConfig) -> SeedDisciplineReport:
    """Validate recorded ranges. Spent/no-reuse seeds cannot appear in any
    proof-affecting split (train, calibration, or held-out). This is not an
    allocator."""
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest apps/api/tests/test_proof_spine_seed_discipline.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Update `__init__.py` exports**

Add to `apps/api/app/services/proof/__init__.py`:

```python
from .seed_discipline import validate_seed_ranges  # noqa: F401
```

- [ ] **Step 6: Checkpoint**

Run `git status --short` and record changed files. Do not commit here; commit,
push, and PR require later explicit authorization and Lore protocol.

---

## Task 7: Final verification (archive untouched + full regression)

**Files:** none (verification only)

- [ ] **Step 1: Confirm the archive and the verifier were not modified**

Run: `git diff --stat main -- scripts/run_mvp2c_isaac_training_calibration.py scripts/run_mvp2b_isaac_proof_evaluator.py scripts/verify_mvp2_package.py`
Expected: empty output (zero changes to the archive and the auditor).

- [ ] **Step 2: Run the full spine suite**

Run: `uv run pytest apps/api/tests/test_proof_spine_*.py -q`
Expected: PASS (all spine tests green, including the v0.14 golden).

- [ ] **Step 3: Run the whole test suite + lint**

Run: `uv run pytest -q && uvx ruff check apps/api/app/services/proof apps/api/tests/test_proof_spine_*.py`
Expected: existing suite passes, ruff clean. Known environment-specific skips are acceptable.

- [ ] **Step 4: Confirm the proof package is unchanged**

Run: `python3 scripts/verify_mvp2_package.py docs/proof/mvp2_learning_proven_evidence_package/package_manifest.json | tail -1`
Expected: `VERDICT: VERIFIED` (the extraction did not touch the package).

- [ ] **Step 5: Stop with worktree status**

```bash
git status --short   # report dirty worktree; do not commit
```

Do not commit, push, or open a PR in this plan execution. Report the worktree
status and wait for explicit later authorization if git publication is desired.

---

## Self-Review notes (author)

- **Spec coverage:** module home (Task 1), seed discipline (Task 6), leakage guard
  (Task 2), parameterized closure (Task 3), golden v0.14 (Task 4), independence +
  no-Isaac-constants (Task 5), archive-untouched (Task 7). All success criteria mapped.
- **Type consistency:** `GateInputs`, `RuntimeExpectations`, `ClosureThresholds`,
  `ClosureVerdict`, `LeakageReport`, `SeedRangeConfig`, `SeedDisciplineReport`
  defined in Task 1 and used unchanged in Tasks 3–6. `derive_closure(inputs, runtime,
  thresholds=None)` and `check_heldout_leakage(held_out, burned)` and
  `validate_seed_ranges(config)` signatures consistent across tasks.
- **Import path (resolved):** tests import `app.services.proof...`, matching the
  existing convention (`from app.services.curator import ...`) and the configured
  `pythonpath = ["apps/api"]` in `pyproject.toml`. The independence test resolves the
  spine dir via `Path(__file__).resolve().parents[3] / "apps/api/app/services/proof"`
  (test file is `apps/api/tests/...`, so `parents[3]` is the repo root).
