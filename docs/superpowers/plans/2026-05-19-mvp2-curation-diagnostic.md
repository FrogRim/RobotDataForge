# MVP-2 Curation Diagnostic Implementation Plan

> **For agentic workers:** Implement this plan task-by-task using standard Codex workflow. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `scripts/run_mvp2_curation_diagnostic.py`, a read-only offline script that reports per-episode phase coverage, phase-conditional saturation, command quality, and A/B/C gate judgments — without touching curation logic.

**Architecture:** Trajectory JSONs are the source of truth for all new metrics. Evaluation JSONs are loaded once into an index and used only as a comparison baseline (recorded gate decisions). The script scans `storage/trajectories/`, joins with `storage/evaluations/` by `episode_id`, computes diagnostics, writes a JSON report, and prints a terminal table.

**Tech Stack:** Python 3.11+, stdlib only (json, pathlib, argparse, collections, datetime). No h5py, no SQLite, no API. Test runner: pytest.

**Spec:** `docs/superpowers/specs/2026-05-19-mvp2-curation-diagnostic-design.md`

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `scripts/run_mvp2_curation_diagnostic.py` | Create | Main script: all logic + CLI |
| `apps/api/tests/test_mvp2_curation_diagnostic_script.py` | Create | All tests (unit + integration) |

---

## Task 1: Script Scaffold + `read_phase()` + Phase Coverage

**Files:**
- Create: `scripts/run_mvp2_curation_diagnostic.py`
- Create: `apps/api/tests/test_mvp2_curation_diagnostic_script.py`

- [ ] **Step 1.1: Write the failing tests**

```python
# apps/api/tests/test_mvp2_curation_diagnostic_script.py
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def load_script(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


diag = load_script("run_mvp2_curation_diagnostic")


def make_frame(
    phase: str,
    native_action: list[float] | None = None,
    delta_m: list[float] | None = None,
    workspace_clamped: bool = False,
) -> dict:
    return {
        "metadata": {"action_phase": phase},
        "action": {
            "native_isaac_action": native_action or [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "control_filter": {
                "teleop_control_mode": {
                    "applied_ee_delta_m": delta_m or [0.0, 0.0, 0.0],
                    "workspace_clamped": workspace_clamped,
                }
            },
        },
    }


# --- Task 1 tests ---

def test_read_phase_primary_metadata():
    frame = {"metadata": {"action_phase": "INSERT"}, "action": {}}
    phase, source = diag.read_phase(frame)
    assert phase == "INSERT"
    assert source == "metadata"


def test_read_phase_fallback_task_state():
    frame = {"metadata": {"task_state": {"action_phase": "SEAT"}}, "action": {}}
    phase, source = diag.read_phase(frame)
    assert phase == "SEAT"
    assert source == "task_state"


def test_read_phase_fallback_action_level():
    frame = {"metadata": {}, "action_phase": "CONTACT", "action": {}}
    phase, source = diag.read_phase(frame)
    assert phase == "CONTACT"
    assert source == "action"


def test_read_phase_default_unknown():
    frame = {"metadata": {}, "action": {}}
    phase, source = diag.read_phase(frame)
    assert phase == "UNKNOWN"
    assert source == "default"


def test_read_phase_unsupported_value_becomes_unknown():
    frame = {"metadata": {"action_phase": "WIGGLE"}, "action": {}}
    phase, source = diag.read_phase(frame)
    assert phase == "UNKNOWN"
    assert source == "default"


def test_compute_phase_coverage_counts_and_rates():
    frames = (
        [make_frame("INSERT")] * 20
        + [make_frame("SEAT")] * 8
        + [make_frame("CONTACT")] * 2
    )
    result = diag.compute_phase_coverage(frames)
    assert result["phase_counts"]["INSERT"] == 20
    assert result["phase_counts"]["SEAT"] == 8
    assert result["phase_counts"]["CONTACT"] == 2
    assert abs(result["phase_rates"]["INSERT"] - 20 / 30) < 1e-9
    assert result["phase_source_distribution"]["metadata"] == 30
```

- [ ] **Step 1.2: Run to confirm failure**

```bash
cd /home/kangrim/robot-data-forge
uv run pytest apps/api/tests/test_mvp2_curation_diagnostic_script.py::test_read_phase_primary_metadata -v
```
Expected: `ModuleNotFoundError` or `AssertionError` — file doesn't exist yet.

- [ ] **Step 1.3: Create the script scaffold**

```python
# scripts/run_mvp2_curation_diagnostic.py
#!/usr/bin/env python3
"""MVP-2 offline curation diagnostic.

Read-only script. Reports per-episode phase coverage, phase-conditional
saturation, command quality, and A/B/C gate judgments.
Source of truth: storage/trajectories/*.json (raw frames).
Comparison baseline: storage/evaluations/*.json (recorded gate decisions).
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "rdf_mvp2_curation_diagnostic_v0.1.0"
DEFAULT_TRAJECTORIES_DIR = ROOT / "storage" / "trajectories"
DEFAULT_EVALUATIONS_DIR = ROOT / "storage" / "evaluations"
DEFAULT_OUTPUT_DIR = ROOT / "storage" / "mvp2_curation_diagnostic"

SUPPORTED_PHASES = {
    "APPROACH", "ALIGN", "CONTACT", "INSERT",
    "SEAT", "STABILIZE", "RELEASE", "RECOVER", "UNKNOWN",
}


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)


def read_phase(frame: dict[str, Any]) -> tuple[str, str]:
    """Return (phase, source). Fallback: metadata → task_state → action → default."""
    ph = frame.get("metadata", {}).get("action_phase")
    if ph is not None:
        norm = str(ph).strip().upper()
        if norm in SUPPORTED_PHASES:
            return norm, "metadata"

    ph = frame.get("metadata", {}).get("task_state", {}).get("action_phase")
    if ph is not None:
        norm = str(ph).strip().upper()
        if norm in SUPPORTED_PHASES:
            return norm, "task_state"

    ph = frame.get("action_phase")
    if ph is not None:
        norm = str(ph).strip().upper()
        if norm in SUPPORTED_PHASES:
            return norm, "action"

    return "UNKNOWN", "default"


def compute_phase_coverage(frames: list[dict[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    for frame in frames:
        phase, source = read_phase(frame)
        counts[phase] += 1
        source_counts[source] += 1
    total = len(frames) or 1
    rates = {ph: counts[ph] / total for ph in counts}
    return {
        "phase_counts": dict(counts),
        "phase_rates": rates,
        "phase_source_distribution": dict(source_counts),
    }


def main() -> int:
    print("run_mvp2_curation_diagnostic: scaffold only", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 1.4: Run Task 1 tests — all must pass**

```bash
uv run pytest apps/api/tests/test_mvp2_curation_diagnostic_script.py \
  -k "read_phase or phase_coverage" -v
```
Expected: `6 passed`

- [ ] **Step 1.5: Lint**

```bash
uv run ruff check scripts/run_mvp2_curation_diagnostic.py apps/api/tests/test_mvp2_curation_diagnostic_script.py
```
Expected: no errors.

- [ ] **Step 1.6: Commit**

```bash
git add scripts/run_mvp2_curation_diagnostic.py \
        apps/api/tests/test_mvp2_curation_diagnostic_script.py
git commit -m "feat: add MVP-2 curation diagnostic scaffold with read_phase and phase coverage"
```

---

## Task 2: Saturation per Frame + Phase-Conditional Saturation

**Files:**
- Modify: `scripts/run_mvp2_curation_diagnostic.py` (add 3 functions)
- Modify: `apps/api/tests/test_mvp2_curation_diagnostic_script.py` (add tests)

- [ ] **Step 2.1: Write failing tests**

Append to `test_mvp2_curation_diagnostic_script.py`:

```python
# --- Task 2 tests ---

def test_is_frame_saturated_true():
    frame = make_frame("INSERT", native_action=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    assert diag.is_frame_saturated(frame, threshold=0.999) is True


def test_is_frame_saturated_false():
    frame = make_frame("INSERT", native_action=[0.5, 0.0, 0.0, 0.0, 0.0, 0.0])
    assert diag.is_frame_saturated(frame, threshold=0.999) is False


def test_is_frame_saturated_missing_action():
    frame = {"metadata": {}, "action": {}}
    assert diag.is_frame_saturated(frame, threshold=0.999) is None


def test_is_frame_saturated_ignores_gripper():
    # index 6 is gripper (1.0), indices 0-5 are clean → must be False
    frame = make_frame("SEAT", native_action=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0])
    assert diag.is_frame_saturated(frame, threshold=0.999) is False


def test_is_frame_saturated_short_vector_returns_none():
    # fewer than 6 elements → cannot evaluate → None
    frame = make_frame("INSERT", native_action=[1.0, 0.0, 0.0])
    assert diag.is_frame_saturated(frame, threshold=0.999) is None


def test_consecutive_max_basic():
    assert diag._consecutive_max([True, True, False, True]) == 2
    assert diag._consecutive_max([True, True, True]) == 3
    assert diag._consecutive_max([False, False]) == 0
    assert diag._consecutive_max([]) == 0


def test_phase_conditional_saturation_ratios():
    frames = (
        [make_frame("INSERT", native_action=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0])] * 10
        + [make_frame("INSERT", native_action=[0.1, 0.0, 0.0, 0.0, 0.0, 0.0])] * 10
        + [make_frame("SEAT", native_action=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0])] * 5
        + [make_frame("SEAT", native_action=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0])] * 5
    )
    result = diag.compute_phase_conditional_saturation(frames, threshold=0.999)
    assert result["sat_ratio_INSERT"] == 0.5       # 10/20
    assert result["sat_ratio_SEAT"] == 0.5         # 5/10
    assert result["sat_ratio_CONTACT"] == 0.0      # no CONTACT frames
    assert result["consecutive_sat_max_INSERT"] == 10
    assert result["consecutive_sat_max_SEAT"] == 5
    assert 0.0 < result["sat_ratio_aggregate"] < 1.0


def test_phase_conditional_saturation_empty_frames():
    result = diag.compute_phase_conditional_saturation([], threshold=0.999)
    assert result["sat_ratio_aggregate"] == 0.0
    assert result["sat_ratio_INSERT"] == 0.0
```

- [ ] **Step 2.2: Run to confirm failure**

```bash
uv run pytest apps/api/tests/test_mvp2_curation_diagnostic_script.py \
  -k "saturated or consecutive or conditional" -v 2>&1 | tail -5
```
Expected: `AttributeError: module has no attribute 'is_frame_saturated'`

- [ ] **Step 2.3: Add saturation functions to the script**

Add after `compute_phase_coverage` in `scripts/run_mvp2_curation_diagnostic.py`:

```python
def is_frame_saturated(frame: dict[str, Any], threshold: float = 0.999) -> bool | None:
    """Check action[:6] only (gripper is index 6, excluded). Returns None if field absent."""
    action = frame.get("action", {}).get("native_isaac_action")
    if not isinstance(action, list) or len(action) < 6:
        return None
    return any(abs(v) >= threshold for v in action[:6])


def _consecutive_max(flags: list[bool]) -> int:
    max_run = run = 0
    for f in flags:
        run = run + 1 if f else 0
        max_run = max(max_run, run)
    return max_run


def compute_phase_conditional_saturation(
    frames: list[dict[str, Any]], threshold: float
) -> dict[str, Any]:
    phase_flags: dict[str, list[bool]] = {}
    for frame in frames:
        sat = is_frame_saturated(frame, threshold)
        if sat is None:
            continue  # skip frames without native_isaac_action (not in denominator)
        phase, _ = read_phase(frame)
        phase_flags.setdefault(phase, []).append(sat)

    all_flags = [f for flags in phase_flags.values() for f in flags]
    result: dict[str, Any] = {
        "sat_ratio_aggregate": sum(all_flags) / len(all_flags) if all_flags else 0.0,
    }
    for ph in ("APPROACH", "CONTACT", "INSERT", "SEAT"):
        flags = phase_flags.get(ph, [])
        result[f"sat_ratio_{ph}"] = sum(flags) / len(flags) if flags else 0.0
        result[f"consecutive_sat_max_{ph}"] = _consecutive_max(flags)
    return result
```

- [ ] **Step 2.4: Run Task 2 tests — all must pass**

```bash
uv run pytest apps/api/tests/test_mvp2_curation_diagnostic_script.py \
  -k "saturated or consecutive or conditional" -v
```
Expected: `7 passed`

- [ ] **Step 2.5: Run all tests so far**

```bash
uv run pytest apps/api/tests/test_mvp2_curation_diagnostic_script.py -v
```
Expected: `13 passed`

- [ ] **Step 2.6: Commit**

```bash
git add scripts/run_mvp2_curation_diagnostic.py \
        apps/api/tests/test_mvp2_curation_diagnostic_script.py
git commit -m "feat: add phase-conditional saturation diagnostic"
```

---

## Task 3: Command Quality (Step Norm + Jerk + Workspace Clamped)

**Files:**
- Modify: `scripts/run_mvp2_curation_diagnostic.py`
- Modify: `apps/api/tests/test_mvp2_curation_diagnostic_script.py`

Field reading priority:
1. `frame.action.control_filter.teleop_control_mode.command_step_norm` (pre-computed scalar, use directly)
2. `frame.action.control_filter.teleop_control_mode.applied_ee_delta_m` (physical [x,y,z] meters)
3. `frame.action.executed_control.applied_end_effector_action.delta_position`
4. `frame.action.learning_action.command`

- [ ] **Step 3.1: Write failing tests**

Append to test file:

```python
# --- Task 3 tests ---

def make_frame_with_delta(phase: str, delta_m: list[float], clamped: bool = False) -> dict:
    return {
        "metadata": {"action_phase": phase},
        "action": {
            "native_isaac_action": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "control_filter": {
                "teleop_control_mode": {
                    "applied_ee_delta_m": delta_m,
                    "workspace_clamped": clamped,
                }
            },
        },
    }


def test_get_applied_ee_delta_primary():
    frame = make_frame_with_delta("INSERT", [0.01, 0.02, 0.03])
    delta = diag.get_applied_ee_delta(frame)
    assert delta == [0.01, 0.02, 0.03]


def test_get_applied_ee_delta_fallback_executed_control():
    frame = {
        "metadata": {},
        "action": {
            "executed_control": {
                "applied_end_effector_action": {"delta_position": [0.005, 0.0, 0.0]}
            }
        },
    }
    delta = diag.get_applied_ee_delta(frame)
    assert delta == [0.005, 0.0, 0.0]


def test_get_applied_ee_delta_none_when_missing():
    frame = {"metadata": {}, "action": {}}
    assert diag.get_applied_ee_delta(frame) is None


def test_get_command_step_norm_precomputed():
    frame = {
        "metadata": {},
        "action": {
            "control_filter": {
                "teleop_control_mode": {"command_step_norm": 0.025}
            }
        },
    }
    assert diag.get_command_step_norm(frame) == 0.025


def test_get_command_step_norm_computed_from_delta():
    # ||[0.03, 0.04, 0.0]|| = 0.05
    frame = make_frame_with_delta("INSERT", [0.03, 0.04, 0.0])
    norm = diag.get_command_step_norm(frame)
    assert norm is not None
    assert abs(norm - 0.05) < 1e-9


def test_get_workspace_clamped():
    frame_clamped = make_frame_with_delta("INSERT", [0.01, 0.0, 0.0], clamped=True)
    frame_free = make_frame_with_delta("INSERT", [0.01, 0.0, 0.0], clamped=False)
    assert diag.get_workspace_clamped(frame_clamped) is True
    assert diag.get_workspace_clamped(frame_free) is False
    assert diag.get_workspace_clamped({"metadata": {}, "action": {}}) is None


def test_compute_command_quality_basic():
    # 3 frames with known deltas: jerk = ||d[1]-d[0]|| and ||d[2]-d[1]||
    frames = [
        make_frame_with_delta("INSERT", [0.01, 0.0, 0.0]),
        make_frame_with_delta("INSERT", [0.02, 0.0, 0.0]),
        make_frame_with_delta("INSERT", [0.02, 0.0, 0.0]),
    ]
    result = diag.compute_command_quality(frames)
    # norms: 0.01, 0.02, 0.02
    assert abs(result["command_step_norm_mean"] - (0.01 + 0.02 + 0.02) / 3) < 1e-9
    # jerks: ||[0.02]-[0.01]|| = 0.01, ||[0.02]-[0.02]|| = 0.0
    assert abs(result["jerk_mean"] - 0.005) < 1e-9
    assert result["workspace_clamped_ratio"] == 0.0


def test_compute_command_quality_no_frames():
    result = diag.compute_command_quality([])
    assert result["command_step_norm_mean"] is None
    assert result["jerk_mean"] is None
```

- [ ] **Step 3.2: Run to confirm failure**

```bash
uv run pytest apps/api/tests/test_mvp2_curation_diagnostic_script.py \
  -k "delta or norm or clamped or quality" -v 2>&1 | tail -5
```
Expected: `AttributeError`

- [ ] **Step 3.3: Add command quality functions to script**

Add after `compute_phase_conditional_saturation` in the script:

```python
def get_applied_ee_delta(frame: dict[str, Any]) -> list[float] | None:
    """Physical EE delta in meters. Fallback chain: teleop_control_mode → executed_control → learning_action."""
    tcm = frame.get("action", {}).get("control_filter", {}).get("teleop_control_mode", {})
    delta = tcm.get("applied_ee_delta_m")
    if isinstance(delta, list) and len(delta) >= 3:
        return [float(v) for v in delta[:3]]

    delta = (
        frame.get("action", {})
        .get("executed_control", {})
        .get("applied_end_effector_action", {})
        .get("delta_position")
    )
    if isinstance(delta, list) and len(delta) >= 3:
        return [float(v) for v in delta[:3]]

    cmd = frame.get("action", {}).get("learning_action", {}).get("command")
    if isinstance(cmd, list) and len(cmd) >= 3:
        return [float(v) for v in cmd[:3]]

    return None


def get_command_step_norm(frame: dict[str, Any]) -> float | None:
    """Step norm in meters. Uses pre-computed scalar when available."""
    tcm = frame.get("action", {}).get("control_filter", {}).get("teleop_control_mode", {})
    val = tcm.get("command_step_norm")
    if val is not None:
        return float(val)
    delta = get_applied_ee_delta(frame)
    if delta is not None:
        return float(sum(x ** 2 for x in delta) ** 0.5)
    return None


def get_workspace_clamped(frame: dict[str, Any]) -> bool | None:
    tcm = frame.get("action", {}).get("control_filter", {}).get("teleop_control_mode", {})
    val = tcm.get("workspace_clamped")
    return bool(val) if val is not None else None


def _p95(vals: list[float]) -> float | None:
    if not vals:
        return None
    return sorted(vals)[max(0, int(len(vals) * 0.95) - 1)]


def compute_command_quality(frames: list[dict[str, Any]]) -> dict[str, Any]:
    norms = [get_command_step_norm(f) for f in frames]
    norms_valid = [v for v in norms if v is not None]

    deltas = [get_applied_ee_delta(f) for f in frames]
    jerks: list[float] = []
    prev: list[float] | None = None
    for d in deltas:
        if d is not None and prev is not None:
            jerks.append(sum((a - b) ** 2 for a, b in zip(d, prev)) ** 0.5)
        if d is not None:
            prev = d

    clamped_known = [get_workspace_clamped(f) for f in frames if get_workspace_clamped(f) is not None]

    return {
        "command_step_norm_mean": sum(norms_valid) / len(norms_valid) if norms_valid else None,
        "command_step_norm_p95": _p95(norms_valid),
        "jerk_mean": sum(jerks) / len(jerks) if jerks else None,
        "jerk_p95": _p95(jerks),
        "workspace_clamped_ratio": sum(clamped_known) / len(clamped_known) if clamped_known else None,
    }
```

- [ ] **Step 3.4: Run Task 3 tests**

```bash
uv run pytest apps/api/tests/test_mvp2_curation_diagnostic_script.py \
  -k "delta or norm or clamped or quality" -v
```
Expected: `10 passed`

- [ ] **Step 3.5: Run all tests**

```bash
uv run pytest apps/api/tests/test_mvp2_curation_diagnostic_script.py -v
```
Expected: `23 passed`

- [ ] **Step 3.6: Commit**

```bash
git add scripts/run_mvp2_curation_diagnostic.py \
        apps/api/tests/test_mvp2_curation_diagnostic_script.py
git commit -m "feat: add command quality metrics (step norm, jerk, workspace clamped)"
```

---

## Task 4: Gate Judgment (A/B/C) + Cross-Validation

**Files:**
- Modify: `scripts/run_mvp2_curation_diagnostic.py`
- Modify: `apps/api/tests/test_mvp2_curation_diagnostic_script.py`

Gate definitions:
- A: CONTACT >= 1, INSERT >= 20, SEAT >= 8
- B: APPROACH >= 10, CONTACT >= 1, INSERT >= 20, SEAT >= 8
- C: INSERT >= 20

Cross-validation: `gate_match = (recomputed_sat_fail == recorded_sat_fail)`, skipped when `failure_reason` is a different reason.

- [ ] **Step 4.1: Write failing tests**

Append to test file:

```python
# --- Task 4 tests ---

def _cfg() -> dict:
    return {
        "insert_min_frames": 20,
        "seat_min_frames": 8,
        "approach_min_frames": 10,
        "action_sat_value_threshold": 0.999,
        "max_native_action_sat_ratio": 0.05,
    }


def test_gate_a_pass_no_approach_needed():
    counts = {"INSERT": 25, "SEAT": 10, "CONTACT": 3}
    result = diag.compute_gate_judgment(counts, _cfg())
    assert result["gate_A_pass"] is True
    assert result["gate_B_pass"] is False
    assert result["gate_C_pass"] is True
    assert result["gate_B_fail_reason"] == "APPROACH_ABSENT"


def test_gate_b_pass_all_phases():
    counts = {"APPROACH": 15, "CONTACT": 5, "INSERT": 25, "SEAT": 10}
    result = diag.compute_gate_judgment(counts, _cfg())
    assert result["gate_A_pass"] is True
    assert result["gate_B_pass"] is True
    assert result["gate_C_pass"] is True
    assert result["gate_B_fail_reason"] is None


def test_gate_b_fail_approach_insufficient():
    counts = {"APPROACH": 5, "CONTACT": 3, "INSERT": 25, "SEAT": 10}
    result = diag.compute_gate_judgment(counts, _cfg())
    assert result["gate_B_pass"] is False
    assert result["gate_B_fail_reason"] == "APPROACH_INSUFFICIENT"


def test_gate_c_only_insert_present():
    counts = {"INSERT": 25}
    result = diag.compute_gate_judgment(counts, _cfg())
    assert result["gate_A_pass"] is False
    assert result["gate_B_pass"] is False
    assert result["gate_C_pass"] is True


def test_gate_all_fail_no_data():
    result = diag.compute_gate_judgment({}, _cfg())
    assert result["gate_A_pass"] is False
    assert result["gate_B_pass"] is False
    assert result["gate_C_pass"] is False


def test_cross_validation_match_both_fail():
    result = diag.compute_cross_validation(0.20, "NATIVE_ACTION_SATURATION", max_ratio=0.05)
    assert result["recomputed_sat_fail"] is True
    assert result["recorded_sat_fail"] is True
    assert result["gate_match"] is True


def test_cross_validation_mismatch():
    result = diag.compute_cross_validation(0.001, "NATIVE_ACTION_SATURATION", max_ratio=0.05)
    assert result["recomputed_sat_fail"] is False
    assert result["recorded_sat_fail"] is True
    assert result["gate_match"] is False


def test_cross_validation_both_pass():
    result = diag.compute_cross_validation(0.001, None, max_ratio=0.05)
    assert result["recomputed_sat_fail"] is False
    assert result["recorded_sat_fail"] is False
    assert result["gate_match"] is True


def test_cross_validation_other_reason_skipped():
    result = diag.compute_cross_validation(0.20, "RETARGETING_JUMP", max_ratio=0.05)
    assert result["gate_match"] is None
    assert result["gate_match_skipped_reason"] == "other_failure_reason"
```

- [ ] **Step 4.2: Run to confirm failure**

```bash
uv run pytest apps/api/tests/test_mvp2_curation_diagnostic_script.py \
  -k "gate or cross_validation" -v 2>&1 | tail -5
```
Expected: `AttributeError`

- [ ] **Step 4.3: Add gate and cross-validation functions to script**

Add after `compute_command_quality` in the script:

```python
def compute_gate_judgment(
    phase_counts: dict[str, int], config: dict[str, Any]
) -> dict[str, Any]:
    insert = phase_counts.get("INSERT", 0)
    seat = phase_counts.get("SEAT", 0)
    contact = phase_counts.get("CONTACT", 0)
    approach = phase_counts.get("APPROACH", 0)

    insert_min = config["insert_min_frames"]
    seat_min = config["seat_min_frames"]
    approach_min = config["approach_min_frames"]

    gate_a = contact >= 1 and insert >= insert_min and seat >= seat_min
    gate_b = approach >= approach_min and contact >= 1 and insert >= insert_min and seat >= seat_min
    gate_c = insert >= insert_min

    b_fail_reason: str | None = None
    if gate_a and not gate_b:
        b_fail_reason = "APPROACH_ABSENT" if approach == 0 else "APPROACH_INSUFFICIENT"

    return {
        "gate_A_pass": gate_a,
        "gate_B_pass": gate_b,
        "gate_C_pass": gate_c,
        "gate_B_fail_reason": b_fail_reason,
    }


def compute_cross_validation(
    sat_ratio_recomputed: float,
    recorded_failure_reason: str | None,
    max_ratio: float,
) -> dict[str, Any]:
    recomputed_sat_fail = sat_ratio_recomputed > max_ratio  # mirrors live gate: ratio > threshold
    recorded_sat_fail = recorded_failure_reason == "NATIVE_ACTION_SATURATION"
    other_reason = (
        recorded_failure_reason is not None
        and recorded_failure_reason != "NATIVE_ACTION_SATURATION"
    )
    gate_match: bool | None = None if other_reason else (recomputed_sat_fail == recorded_sat_fail)
    return {
        "sat_ratio_recomputed": sat_ratio_recomputed,
        "recomputed_sat_fail": recomputed_sat_fail,
        "recorded_sat_fail": recorded_sat_fail,
        "gate_match": gate_match,
        "gate_match_skipped_reason": "other_failure_reason" if other_reason else None,
    }
```

- [ ] **Step 4.4: Run Task 4 tests**

```bash
uv run pytest apps/api/tests/test_mvp2_curation_diagnostic_script.py \
  -k "gate or cross_validation" -v
```
Expected: `10 passed`

- [ ] **Step 4.5: Run all tests**

```bash
uv run pytest apps/api/tests/test_mvp2_curation_diagnostic_script.py -v
```
Expected: `33 passed`

- [ ] **Step 4.6: Commit**

```bash
git add scripts/run_mvp2_curation_diagnostic.py \
        apps/api/tests/test_mvp2_curation_diagnostic_script.py
git commit -m "feat: add A/B/C gate judgment and cross-validation"
```

---

## Task 5: Episode Analysis + Eval Index + `run_diagnostic()` + JSON Output

**Files:**
- Modify: `scripts/run_mvp2_curation_diagnostic.py`
- Modify: `apps/api/tests/test_mvp2_curation_diagnostic_script.py`

`analyze_episode` receives a pre-built `eval_index: dict[str, dict]` (not the dir path) to avoid re-scanning files per episode. `run_diagnostic` builds the index once.

- [ ] **Step 5.1: Write failing tests**

Append to test file:

```python
# --- Task 5 tests ---

def _make_traj_json(episode_id: str, frames: list[dict]) -> dict:
    return {
        "id": f"traj_{episode_id[:8]}",
        "episode_id": episode_id,
        "schema_version": "v1",
        "source": {},
        "frames": frames,
        "summary": {"episode_status": "reset"},
    }


def _make_eval_json(episode_id: str, failure_reason: str | None) -> dict:
    return {
        "id": f"eval_{episode_id[:8]}",
        "episode_id": episode_id,
        "trajectory_id": f"traj_{episode_id[:8]}",
        "success": failure_reason is None,
        "failure_reason": failure_reason,
        "metrics": {},
    }


def test_load_eval_index(tmp_path: Path):
    ep_id = "episode_abc123"
    eval_data = _make_eval_json(ep_id, "NATIVE_ACTION_SATURATION")
    (tmp_path / "eval_abc123.json").write_text(json.dumps(eval_data), encoding="utf-8")
    (tmp_path / "eval_broken.json").write_text("not json", encoding="utf-8")

    index = diag.load_eval_index(tmp_path)
    assert ep_id in index
    assert index[ep_id]["failure_reason"] == "NATIVE_ACTION_SATURATION"


def test_analyze_episode_full(tmp_path: Path):
    ep_id = "episode_test01"
    frames = (
        [make_frame("CONTACT")] * 3
        + [make_frame("INSERT", native_action=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                      delta_m=[0.025, 0.0, 0.0])] * 25
        + [make_frame("SEAT", delta_m=[0.0, 0.0, 0.0])] * 10
    )
    traj_path = tmp_path / "traj_test01.json"
    traj_path.write_text(json.dumps(_make_traj_json(ep_id, frames)), encoding="utf-8")

    eval_index = {ep_id: _make_eval_json(ep_id, "NATIVE_ACTION_SATURATION")}
    result = diag.analyze_episode(traj_path, eval_index, _cfg())

    assert result["episode_id"] == ep_id
    assert result["frame_count"] == 38
    assert result["gate_A_pass"] is True
    assert result["gate_B_pass"] is False
    assert result["gate_C_pass"] is True
    assert result["recorded_failure_reason"] == "NATIVE_ACTION_SATURATION"
    assert result["old_live_gate_pass"] is False
    assert result["sat_ratio_INSERT"] > 0.0
    assert result["sat_ratio_SEAT"] == 0.0
    assert result["command_step_norm_mean"] is not None


def test_run_diagnostic_creates_report(tmp_path: Path):
    ep_id = "episode_run01"
    frames = (
        [make_frame("CONTACT")] * 2
        + [make_frame("INSERT", delta_m=[0.01, 0.0, 0.0])] * 25
        + [make_frame("SEAT", delta_m=[0.0, 0.0, 0.0])] * 10
    )
    traj_dir = tmp_path / "trajectories"
    eval_dir = tmp_path / "evaluations"
    out_dir = tmp_path / "output"
    traj_dir.mkdir(); eval_dir.mkdir()

    (traj_dir / "traj_run01.json").write_text(
        json.dumps(_make_traj_json(ep_id, frames)), encoding="utf-8"
    )
    (eval_dir / "eval_run01.json").write_text(
        json.dumps(_make_eval_json(ep_id, None)), encoding="utf-8"
    )

    report = diag.run_diagnostic(traj_dir, eval_dir, out_dir, _cfg())

    assert report["schema_version"] == diag.SCHEMA_VERSION
    assert len(report["episodes"]) == 1
    assert report["summary"]["total_episodes"] == 1
    assert report["summary"]["gate_A_pass_count"] == 1
    assert (out_dir / "mvp2_curation_diagnostic_report.json").exists()
```

- [ ] **Step 5.2: Run to confirm failure**

```bash
uv run pytest apps/api/tests/test_mvp2_curation_diagnostic_script.py \
  -k "eval_index or analyze_episode or run_diagnostic" -v 2>&1 | tail -5
```
Expected: `AttributeError`

- [ ] **Step 5.3: Add episode analysis and run_diagnostic to script**

Add after `compute_cross_validation` in the script:

```python
def load_eval_index(evaluations_dir: Path) -> dict[str, dict[str, Any]]:
    """Build {episode_id: eval_record} from all eval_*.json files."""
    index: dict[str, dict[str, Any]] = {}
    for path in evaluations_dir.glob("eval_*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        ep_id = data.get("episode_id")
        if ep_id:
            index[str(ep_id)] = data
    return index


def _extract_recorded_state(eval_record: dict[str, Any] | None) -> dict[str, Any]:
    if eval_record is None:
        return {
            "recorded_episode_status": None,
            "recorded_evaluator_success": None,
            "recorded_failure_reason": None,
            "recorded_live_curation_status": None,
            "recorded_training_eligible": None,
            "old_live_gate_pass": None,
            "old_evaluator_pass": None,
        }
    failure_reason = eval_record.get("failure_reason")
    success = eval_record.get("success")
    metrics = eval_record.get("metrics", {})

    # training_eligible: top-level → metrics.curation → metrics.data_quality
    training_eligible = eval_record.get("training_eligible")
    if training_eligible is None:
        training_eligible = metrics.get("curation", {}).get("training_eligible")
    if training_eligible is None:
        training_eligible = metrics.get("data_quality", {}).get("training_eligible")

    # live_curation_status: metrics.curation.status → derive from failure_reason
    live_curation_status = metrics.get("curation", {}).get("status")
    if live_curation_status is None:
        live_curation_status = "passed" if failure_reason is None else "failed"

    return {
        "recorded_episode_status": eval_record.get("status"),
        "recorded_evaluator_success": success,
        "recorded_failure_reason": failure_reason,
        "recorded_live_curation_status": live_curation_status,
        "recorded_training_eligible": bool(training_eligible) if training_eligible is not None else None,
        "old_live_gate_pass": failure_reason is None,
        "old_evaluator_pass": bool(success) if success is not None else None,
    }


def analyze_episode(
    traj_path: Path,
    eval_index: dict[str, dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    traj = json.loads(traj_path.read_text(encoding="utf-8"))
    episode_id = str(traj.get("episode_id", traj_path.stem))
    trajectory_id = str(traj.get("id", traj_path.stem))
    frames = traj.get("frames", [])

    eval_record = eval_index.get(episode_id)
    recorded = _extract_recorded_state(eval_record)
    # episode_status from traj summary takes priority when eval has none
    if recorded["recorded_episode_status"] is None:
        recorded["recorded_episode_status"] = traj.get("summary", {}).get("episode_status")

    coverage = compute_phase_coverage(frames)
    sat = compute_phase_conditional_saturation(frames, config["action_sat_value_threshold"])
    quality = compute_command_quality(frames)
    gates = compute_gate_judgment(coverage["phase_counts"], config)
    xval = compute_cross_validation(
        sat["sat_ratio_aggregate"],
        recorded["recorded_failure_reason"],
        config["max_native_action_sat_ratio"],
    )
    return {
        "episode_id": episode_id,
        "trajectory_id": trajectory_id,
        "frame_count": len(frames),
        **recorded,
        **coverage,
        **sat,
        **quality,
        **xval,
        **gates,
    }


def _build_summary(episodes: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [e for e in episodes if "error" not in e]
    agg_source: Counter[str] = Counter()
    for e in valid:
        for k, v in e.get("phase_source_distribution", {}).items():
            agg_source[k] += v
    return {
        "total_episodes": len(episodes),
        "valid_episodes": len(valid),
        "gate_A_pass_count": sum(1 for e in valid if e.get("gate_A_pass")),
        "gate_B_pass_count": sum(1 for e in valid if e.get("gate_B_pass")),
        "gate_C_pass_count": sum(1 for e in valid if e.get("gate_C_pass")),
        "approach_absent_count": sum(
            1 for e in valid if e.get("phase_counts", {}).get("APPROACH", 0) == 0
        ),
        "gate_match_failure_count": sum(1 for e in valid if e.get("gate_match") is False),
        "phase_source_distribution_aggregate": dict(agg_source),
    }


def run_diagnostic(
    trajectories_dir: Path,
    evaluations_dir: Path,
    output_dir: Path,
    config: dict[str, Any],
    episode_ids: list[str] | None = None,
) -> dict[str, Any]:
    eval_index = load_eval_index(evaluations_dir)
    traj_paths = sorted(trajectories_dir.glob("traj_*.json"))

    if episode_ids:
        filtered = []
        for p in traj_paths:
            try:
                ep_id = json.loads(p.read_text(encoding="utf-8")).get("episode_id")
                if ep_id in episode_ids:
                    filtered.append(p)
            except (json.JSONDecodeError, OSError):
                pass
        traj_paths = filtered

    episodes: list[dict[str, Any]] = []
    for p in traj_paths:
        try:
            episodes.append(analyze_episode(p, eval_index, config))
        except Exception as exc:
            episodes.append({"trajectory_path": str(p), "error": str(exc)})

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "config": config,
        "episodes": episodes,
        "summary": _build_summary(episodes),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "mvp2_curation_diagnostic_report.json"
    out_path.write_text(stable_json(report) + "\n", encoding="utf-8")
    return report
```

- [ ] **Step 5.4: Run Task 5 tests**

```bash
uv run pytest apps/api/tests/test_mvp2_curation_diagnostic_script.py \
  -k "eval_index or analyze_episode or run_diagnostic" -v
```
Expected: `3 passed`

- [ ] **Step 5.5: Run all tests**

```bash
uv run pytest apps/api/tests/test_mvp2_curation_diagnostic_script.py -v
```
Expected: `36 passed`

- [ ] **Step 5.6: Commit**

```bash
git add scripts/run_mvp2_curation_diagnostic.py \
        apps/api/tests/test_mvp2_curation_diagnostic_script.py
git commit -m "feat: add episode analysis, eval index, and run_diagnostic with JSON output"
```

---

## Task 6: Terminal Table + CLI + Integration Smoke

**Files:**
- Modify: `scripts/run_mvp2_curation_diagnostic.py` (replace `main()` scaffold)
- Modify: `apps/api/tests/test_mvp2_curation_diagnostic_script.py`

- [ ] **Step 6.1: Write failing tests**

Append to test file:

```python
# --- Task 6 tests ---

import subprocess


def test_cli_help():
    result = subprocess.run(
        ["uv", "run", "python", "scripts/run_mvp2_curation_diagnostic.py", "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--trajectories-dir" in result.stdout
    assert "--action-sat-value-threshold" in result.stdout
    assert "--max-native-action-sat-ratio" in result.stdout


def test_cli_runs_with_empty_dirs(tmp_path: Path):
    traj_dir = tmp_path / "trajectories"
    eval_dir = tmp_path / "evaluations"
    out_dir = tmp_path / "output"
    traj_dir.mkdir(); eval_dir.mkdir()

    result = subprocess.run(
        [
            "uv", "run", "python", "scripts/run_mvp2_curation_diagnostic.py",
            "--trajectories-dir", str(traj_dir),
            "--evaluations-dir", str(eval_dir),
            "--output-dir", str(out_dir),
            "--pretty",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert (out_dir / "mvp2_curation_diagnostic_report.json").exists()
    report = json.loads((out_dir / "mvp2_curation_diagnostic_report.json").read_text())
    assert report["summary"]["total_episodes"] == 0


def test_cli_end_to_end(tmp_path: Path):
    ep_id = "episode_e2e01"
    frames = (
        [make_frame("CONTACT")] * 3
        + [make_frame("INSERT", native_action=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                      delta_m=[0.025, 0.0, 0.0])] * 25
        + [make_frame("SEAT", delta_m=[0.001, 0.0, 0.0])] * 10
    )
    traj_dir = tmp_path / "trajectories"
    eval_dir = tmp_path / "evaluations"
    out_dir = tmp_path / "output"
    traj_dir.mkdir(); eval_dir.mkdir()

    (traj_dir / "traj_e2e01.json").write_text(
        json.dumps(_make_traj_json(ep_id, frames)), encoding="utf-8"
    )
    (eval_dir / "eval_e2e01.json").write_text(
        json.dumps(_make_eval_json(ep_id, "NATIVE_ACTION_SATURATION")), encoding="utf-8"
    )

    result = subprocess.run(
        [
            "uv", "run", "python", "scripts/run_mvp2_curation_diagnostic.py",
            "--trajectories-dir", str(traj_dir),
            "--evaluations-dir", str(eval_dir),
            "--output-dir", str(out_dir),
            "--pretty",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads((out_dir / "mvp2_curation_diagnostic_report.json").read_text())
    ep = report["episodes"][0]
    assert ep["gate_A_pass"] is True
    assert ep["old_live_gate_pass"] is False
    assert ep["sat_ratio_INSERT"] > 0.0
    assert ep["sat_ratio_SEAT"] == 0.0
    # INSERT sat is high but SEAT sat is 0 → gate mismatch expected
    assert "gate_match" in ep
```

- [ ] **Step 6.2: Run to confirm failure**

```bash
uv run pytest apps/api/tests/test_mvp2_curation_diagnostic_script.py \
  -k "cli" -v 2>&1 | tail -8
```
Expected: `FAILED` — `--trajectories-dir` not in help output yet.

- [ ] **Step 6.3: Replace `main()` scaffold and add `print_table()`**

Replace the `main()` function and add `print_table` in the script:

```python
def print_table(report: dict[str, Any]) -> None:
    episodes = report.get("episodes", [])
    summary = report.get("summary", {})
    header = (
        f"{'EPISODE':<20} {'FRAMES':>6}  {'OLD':>4}  {'A':>4}  {'B':>4}  {'C':>4}"
        f"  {'SAT_INS':>7}  {'SAT_SEAT':>8}  {'JERK_P95':>8}  FAILURE_REASON"
    )
    print(header)
    print("-" * len(header))
    for ep in episodes:
        if "error" in ep:
            print(f"  ERROR  {ep.get('trajectory_path', '?')}  {ep['error']}")
            continue
        ep_id = str(ep.get("episode_id", "?"))[:18]
        old = "PASS" if ep.get("old_live_gate_pass") else "FAIL"
        a = "PASS" if ep.get("gate_A_pass") else "FAIL"
        b = "PASS" if ep.get("gate_B_pass") else "FAIL"
        c = "PASS" if ep.get("gate_C_pass") else "FAIL"
        sat_ins = f"{ep.get('sat_ratio_INSERT', 0.0):.3f}"
        sat_seat = f"{ep.get('sat_ratio_SEAT', 0.0):.3f}"
        jerk = ep.get("jerk_p95")
        jerk_str = f"{jerk:.4f}" if jerk is not None else "N/A"
        reason = ep.get("recorded_failure_reason") or "-"
        print(
            f"{ep_id:<20} {ep.get('frame_count', 0):>6}  {old:>4}  {a:>4}  {b:>4}  {c:>4}"
            f"  {sat_ins:>7}  {sat_seat:>8}  {jerk_str:>8}  {reason}"
        )
    print()
    print(
        f"Total: {summary.get('total_episodes', 0)} | "
        f"A pass: {summary.get('gate_A_pass_count', 0)} | "
        f"B pass: {summary.get('gate_B_pass_count', 0)} | "
        f"C pass: {summary.get('gate_C_pass_count', 0)} | "
        f"APPROACH absent: {summary.get('approach_absent_count', 0)} | "
        f"gate_match failures: {summary.get('gate_match_failure_count', 0)}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="MVP-2 offline curation diagnostic.")
    parser.add_argument(
        "--trajectories-dir", type=Path, default=DEFAULT_TRAJECTORIES_DIR
    )
    parser.add_argument(
        "--evaluations-dir", type=Path, default=DEFAULT_EVALUATIONS_DIR
    )
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR
    )
    parser.add_argument("--insert-min-frames", type=int, default=20)
    parser.add_argument("--seat-min-frames", type=int, default=8)
    parser.add_argument("--approach-min-frames", type=int, default=10)
    parser.add_argument(
        "--action-sat-value-threshold", type=float, default=0.999,
        help="Per-frame saturation check: abs(native_action) >= threshold"
    )
    parser.add_argument(
        "--max-native-action-sat-ratio", type=float, default=0.05,
        help="Ratio gate for cross-validation (recomputed vs. recorded)"
    )
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--episode-ids", nargs="*")
    args = parser.parse_args()

    config: dict[str, Any] = {
        "insert_min_frames": args.insert_min_frames,
        "seat_min_frames": args.seat_min_frames,
        "approach_min_frames": args.approach_min_frames,
        "action_sat_value_threshold": args.action_sat_value_threshold,
        "max_native_action_sat_ratio": args.max_native_action_sat_ratio,
    }

    report = run_diagnostic(
        trajectories_dir=args.trajectories_dir,
        evaluations_dir=args.evaluations_dir,
        output_dir=args.output_dir,
        config=config,
        episode_ids=args.episode_ids,
    )
    print_table(report)

    out_path = args.output_dir / "mvp2_curation_diagnostic_report.json"
    if args.pretty:
        print(f"\nReport: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6.4: Run Task 6 tests**

```bash
uv run pytest apps/api/tests/test_mvp2_curation_diagnostic_script.py \
  -k "cli" -v
```
Expected: `3 passed`

- [ ] **Step 6.5: Run all tests**

```bash
uv run pytest apps/api/tests/test_mvp2_curation_diagnostic_script.py -v
```
Expected: `39 passed`

- [ ] **Step 6.6: Smoke run against real storage**

```bash
uv run python scripts/run_mvp2_curation_diagnostic.py --pretty
```
Expected: terminal table printed, `storage/mvp2_curation_diagnostic/mvp2_curation_diagnostic_report.json` created, exit 0.

- [ ] **Step 6.7: Compile check**

```bash
python3 -m py_compile scripts/run_mvp2_curation_diagnostic.py
```
Expected: no output (clean).

- [ ] **Step 6.8: Lint**

```bash
uv run ruff check scripts/run_mvp2_curation_diagnostic.py \
                   apps/api/tests/test_mvp2_curation_diagnostic_script.py
```
Expected: no errors.

- [ ] **Step 6.9: Commit**

```bash
git add scripts/run_mvp2_curation_diagnostic.py \
        apps/api/tests/test_mvp2_curation_diagnostic_script.py
git commit -m "feat: add terminal table, CLI, and MVP-2 curation diagnostic complete"
```

---

## Self-Review Checklist

Spec sections verified against tasks:

| Spec requirement | Task |
|---|---|
| action_phase fallback chain (3 sources + UNKNOWN) | Task 1 `read_phase()` |
| phase_source_distribution in output | Task 1 `compute_phase_coverage()` |
| saturation check per frame: abs(v) >= ACTION_SAT_VALUE_THRESHOLD | Task 2 `is_frame_saturated()` |
| sat_ratio_INSERT / sat_ratio_SEAT / sat_ratio_CONTACT | Task 2 `compute_phase_conditional_saturation()` |
| consecutive_sat_max per phase | Task 2 `_consecutive_max()` |
| command step fallback chain (teleop_control_mode → executed_control → learning_action) | Task 3 `get_applied_ee_delta()` |
| command_step_norm pre-computed scalar priority | Task 3 `get_command_step_norm()` |
| workspace_clamped | Task 3 `get_workspace_clamped()` |
| jerk_mean, jerk_p95 | Task 3 `compute_command_quality()` |
| gate A: CONTACT≥1, INSERT≥20, SEAT≥8 | Task 4 `compute_gate_judgment()` |
| gate B: APPROACH≥10 + A criteria | Task 4 `compute_gate_judgment()` |
| gate C: INSERT≥20 | Task 4 `compute_gate_judgment()` |
| gate_B_fail_reason: APPROACH_ABSENT / APPROACH_INSUFFICIENT | Task 4 |
| cross-validation gate_match formula | Task 4 `compute_cross_validation()` |
| gate_match skipped for other failure reasons | Task 4 |
| recorded_episode_status, recorded_evaluator_success, old_live_gate_pass, old_evaluator_pass | Task 5 `_extract_recorded_state()` |
| recorded_failure_reason from eval JSON (comparison only) | Task 5 |
| episode_status from traj summary as fallback | Task 5 `analyze_episode()` |
| load_eval_index (scans once, not per-episode) | Task 5 |
| JSON report with schema_version, config, episodes, summary | Task 5 `run_diagnostic()` |
| APPROACH absent count in summary | Task 5 `_build_summary()` |
| gate_match_failure_count in summary | Task 5 `_build_summary()` |
| --action-sat-value-threshold / --max-native-action-sat-ratio (two separate CLI args) | Task 6 `main()` |
| terminal table: episode_id, frames, old/A/B/C gates, sat_INSERT, sat_SEAT, jerk_p95, failure_reason | Task 6 `print_table()` |
| no SQLite / no API dependency | all tasks — stdlib only |
| input artifacts read-only, writes only to output_dir | Task 5 `run_diagnostic()` |
