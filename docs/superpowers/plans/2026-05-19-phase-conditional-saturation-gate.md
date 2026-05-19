# Phase-Conditional Native Action Saturation Gate Implementation Plan

> **For agentic workers:** Follow standard Codex workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the aggregate-ratio saturation gate — in both the offline API evaluator and the live Isaac HMD curation gate — with a phase-conditional gate that hard-fails only on SEAT saturation, treating INSERT saturation as a soft warning metric.

**Architecture:** Two parallel changes. (1) `evaluator.py`: `_native_action_saturation` returns a 3-tuple; gate changes from `aggregate > 0.05` to `seat_ratio > 0.30`. (2) `teleop_se3_agent.py`: `RdfLiveCurationGate` gains `_frame_phase` and `max_seat_action_saturation_ratio`; the hard fail moves from aggregate to SEAT-only. Both changes use the same threshold and the same phase-reading fallback chain, keeping them consistent.

**Tech Stack:** Python 3.11+, pytest, ruff

---

## File Map

| File | Change |
|---|---|
| `apps/api/app/services/evaluator.py` | Add `SEAT_SAT_FAIL_THRESHOLD`, `_frame_phase`; rewrite `_native_action_saturation`; update `add_evaluation_semantics` (2 locations) |
| `apps/api/tests/test_evaluator.py` | Add `import pytest`; add 8 new tests (5 unit + 3 integration); no existing tests change |
| `/home/kangrim/IsaacLab/scripts/environments/teleoperation/teleop_se3_agent.py` | Add CLI arg + env var; add `_frame_phase` to `RdfLiveCurationGate`; add `max_seat_action_saturation_ratio` param; update `evaluate()` and `_maybe_print`; update instantiation site |

---

## Background

Current `_native_action_saturation` (evaluator.py lines 227-254):
- Computes aggregate saturation ratio across all phases
- Fails when aggregate ratio > 0.05
- INSERT phase saturation (operator using max-speed step during insertion) is conflated with SEAT saturation (post-success pushing)

Diagnostic result (from `storage/mvp2_curation_diagnostic/mvp2_curation_diagnostic_report.json`):
- `episode_bce9413e23ad`: INSERT=228, SEAT=18, sat_INSERT=0.18, sat_SEAT=0.00 → wrongly rejected
- `episode_32010d9a68e6`: INSERT=234, SEAT=42, sat_INSERT=0.20, sat_SEAT=0.19 → wrongly rejected
- Both have Gate A coverage (CONTACT≥1, INSERT≥20, SEAT≥8) and are the only transition-rich episodes

Target behavior:
- SEAT saturation > 0.30 → hard fail (both episodes pass: 0.00 and 0.19 < 0.30)
- INSERT saturation → stored as metric, no gate
- Aggregate ratio → still stored (backwards compatibility, cross-validation)

---

## Task 1: Rewrite `_native_action_saturation`

**Files:**
- Modify: `apps/api/app/services/evaluator.py` (lines 227-254, plus add constant and helper above)
- Test: `apps/api/tests/test_evaluator.py`

- [ ] **Step 1.1: Add `import pytest` to test file**

In `apps/api/tests/test_evaluator.py`, add at the top:

```python
from __future__ import annotations

import pytest

from app.services.evaluator import (
    _native_action_saturation,
    add_evaluation_semantics,
    evaluate_trajectory,
)
```

Replace the existing single import line:
```python
from app.services.evaluator import evaluate_trajectory
```

- [ ] **Step 1.2: Write 5 failing unit tests**

Append to `apps/api/tests/test_evaluator.py` (before the `if __name__ == "__main__"` block):

```python
# ---------------------------------------------------------------------------
# _native_action_saturation — phase-conditional unit tests
# ---------------------------------------------------------------------------

def _sat_frame(phase: str, *, saturated: bool) -> dict:
    value = 1.0 if saturated else 0.0
    return {
        "metadata": {"action_phase": phase},
        "action": {"native_isaac_action": [value, 0.0, 0.0, 0.0, 0.0, 0.0]},
    }


def test_native_action_saturation_insert_heavy_passes() -> None:
    # Mirrors episode_bce9413e23ad: INSERT sat 18%, SEAT sat 0%
    frames = (
        [_sat_frame("INSERT", saturated=True)] * 18
        + [_sat_frame("INSERT", saturated=False)] * 82
        + [_sat_frame("SEAT", saturated=False)] * 18
        + [_sat_frame("CONTACT", saturated=False)] * 2
    )
    status, ratio, phase_ratios = _native_action_saturation(frames)
    assert status == "pass"
    assert ratio == pytest.approx(0.15)
    assert phase_ratios["INSERT"] == pytest.approx(0.18)
    assert phase_ratios.get("SEAT", 0.0) == pytest.approx(0.0)


def test_native_action_saturation_seat_above_threshold_fails() -> None:
    # SEAT saturation 40/100 = 0.40 > 0.30 → fail
    frames = (
        [_sat_frame("SEAT", saturated=True)] * 40
        + [_sat_frame("SEAT", saturated=False)] * 60
    )
    status, ratio, phase_ratios = _native_action_saturation(frames)
    assert status == "fail"
    assert phase_ratios["SEAT"] == pytest.approx(0.40)


def test_native_action_saturation_seat_below_threshold_passes() -> None:
    # SEAT saturation 25/100 = 0.25 < 0.30 → pass
    frames = (
        [_sat_frame("SEAT", saturated=True)] * 25
        + [_sat_frame("SEAT", saturated=False)] * 75
    )
    status, ratio, phase_ratios = _native_action_saturation(frames)
    assert status == "pass"
    assert phase_ratios["SEAT"] == pytest.approx(0.25)


def test_native_action_saturation_gripper_excluded_from_sat() -> None:
    # index 6 = gripper = 1.0; arm DOF [0..5] all 0.0 → not saturated
    frame = {
        "metadata": {"action_phase": "SEAT"},
        "action": {"native_isaac_action": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0]},
    }
    status, ratio, phase_ratios = _native_action_saturation([frame])
    assert status == "pass"
    assert ratio == pytest.approx(0.0)
    assert phase_ratios.get("SEAT", 0.0) == pytest.approx(0.0)


def test_native_action_saturation_no_action_returns_unknown() -> None:
    frames = [{"metadata": {"action_phase": "INSERT"}, "action": {}}]
    status, ratio, phase_ratios = _native_action_saturation(frames)
    assert status == "unknown"
    assert ratio is None
    assert phase_ratios == {}
```

- [ ] **Step 1.3: Run tests to confirm they fail**

```bash
cd /home/kangrim/robot-data-forge
uv run pytest apps/api/tests/test_evaluator.py -k "native_action_saturation" -v
```

Expected: 5 failures — `ImportError: cannot import name '_native_action_saturation'` or type errors from the 2-tuple return.

- [ ] **Step 1.4: Add constant, `_frame_phase` helper, and rewrite `_native_action_saturation` in `evaluator.py`**

In `apps/api/app/services/evaluator.py`, add after line 36 (after `REQUIRED_SOURCE_FIELDS`):

```python
SEAT_SAT_FAIL_THRESHOLD = 0.30
```

Add the `_frame_phase` helper before `_native_action_saturation` (around line 226):

```python
def _frame_phase(frame: dict[str, Any]) -> str:
    metadata = frame.get("metadata") or {}
    phase = metadata.get("action_phase")
    if isinstance(phase, str) and phase.strip():
        return phase.strip().upper()
    task_state = metadata.get("task_state") or {}
    phase = task_state.get("action_phase")
    if isinstance(phase, str) and phase.strip():
        return phase.strip().upper()
    phase = frame.get("action_phase")
    if isinstance(phase, str) and phase.strip():
        return phase.strip().upper()
    return "UNKNOWN"
```

Replace `_native_action_saturation` (lines 227-254) with:

```python
def _native_action_saturation(
    frames: list[dict[str, Any]],
) -> tuple[str, float | None, dict[str, float]]:
    """Return (status, aggregate_ratio, phase_ratios).

    Hard-fails only when SEAT saturation exceeds SEAT_SAT_FAIL_THRESHOLD.
    INSERT saturation is a soft warning stored as a metric only.
    """
    total = 0
    saturated = 0
    phase_total: dict[str, int] = {}
    phase_saturated: dict[str, int] = {}

    for frame in frames:
        action = frame.get("action")
        if not isinstance(action, dict):
            continue
        candidates: list[Any] = [
            action.get("native_isaac_action"),
            (action.get("executed_control") or {}).get("native_isaac_action")
            if isinstance(action.get("executed_control"), dict)
            else None,
            action.get("applied"),
        ]
        vector = None
        for candidate in candidates:
            vector = _vector_or_none(candidate)
            if vector:
                break
        if not vector:
            continue

        is_sat = any(abs(v) >= 0.999 for v in vector[:6])
        total += 1
        if is_sat:
            saturated += 1

        phase = _frame_phase(frame)
        phase_total[phase] = phase_total.get(phase, 0) + 1
        if is_sat:
            phase_saturated[phase] = phase_saturated.get(phase, 0) + 1

    if total == 0:
        return "unknown", None, {}

    aggregate_ratio = saturated / total
    phase_ratios: dict[str, float] = {
        phase: phase_saturated.get(phase, 0) / count
        for phase, count in phase_total.items()
    }

    seat_ratio = phase_ratios.get("SEAT", 0.0)
    status = "fail" if seat_ratio > SEAT_SAT_FAIL_THRESHOLD else "pass"
    return status, aggregate_ratio, phase_ratios
```

- [ ] **Step 1.5: Run tests to confirm they pass**

```bash
uv run pytest apps/api/tests/test_evaluator.py -k "native_action_saturation" -v
```

Expected: `5 passed`

---

## Task 2: Update `add_evaluation_semantics` + integration tests

**Files:**
- Modify: `apps/api/app/services/evaluator.py` (line 302, lines 363-376)
- Test: `apps/api/tests/test_evaluator.py`

- [ ] **Step 2.1: Write 3 failing integration tests**

Append to `apps/api/tests/test_evaluator.py` (after the Task 1 tests):

```python
# ---------------------------------------------------------------------------
# add_evaluation_semantics — phase-conditional integration tests
# ---------------------------------------------------------------------------

def _make_sat_trajectory(insert_sat_ratio: float, seat_sat_ratio: float) -> tuple[dict, list[dict]]:
    """Build a minimal trajectory + frame list for saturation testing."""
    insert_sat = int(100 * insert_sat_ratio)
    insert_clear = 100 - insert_sat
    seat_sat = int(100 * seat_sat_ratio)
    seat_clear = 100 - seat_sat
    frames = (
        [_sat_frame("INSERT", saturated=True)] * insert_sat
        + [_sat_frame("INSERT", saturated=False)] * insert_clear
        + [_sat_frame("SEAT", saturated=True)] * seat_sat
        + [_sat_frame("SEAT", saturated=False)] * seat_clear
    )
    trajectory = {"frames": frames, "summary": {}}
    return trajectory, frames


def test_add_evaluation_semantics_stores_phase_ratios() -> None:
    trajectory, _ = _make_sat_trajectory(insert_sat_ratio=0.20, seat_sat_ratio=0.0)
    metrics = add_evaluation_semantics(
        {}, trajectory, success=True, failure_reason=None
    )
    dq = metrics["data_quality"]
    assert "native_action_saturation_phase_ratios" in dq
    assert "native_action_saturation_seat_ratio" in dq
    assert dq["native_action_saturation_phase_ratios"]["INSERT"] == pytest.approx(0.20)
    assert dq["native_action_saturation_seat_ratio"] == pytest.approx(0.0)


def test_add_evaluation_semantics_insert_saturation_does_not_block() -> None:
    # INSERT sat 20%, SEAT sat 0% → native_action_saturation = "pass"
    trajectory, _ = _make_sat_trajectory(insert_sat_ratio=0.20, seat_sat_ratio=0.0)
    metrics = add_evaluation_semantics(
        {}, trajectory, success=True, failure_reason=None
    )
    dq = metrics["data_quality"]
    assert dq["native_action_saturation"] == "pass"
    assert "NATIVE_ACTION_SATURATION" not in dq["quality_failure_reasons"]


def test_add_evaluation_semantics_seat_saturation_above_threshold_blocks() -> None:
    # SEAT sat 40% > 0.30 → native_action_saturation = "fail"
    trajectory, _ = _make_sat_trajectory(insert_sat_ratio=0.0, seat_sat_ratio=0.40)
    metrics = add_evaluation_semantics(
        {}, trajectory, success=True, failure_reason=None
    )
    dq = metrics["data_quality"]
    assert dq["native_action_saturation"] == "fail"
    assert "NATIVE_ACTION_SATURATION" in dq["quality_failure_reasons"]
```

- [ ] **Step 2.2: Run tests to confirm they fail**

```bash
uv run pytest apps/api/tests/test_evaluator.py -k "add_evaluation_semantics" -v
```

Expected: 3 failures — `ValueError: too many values to unpack` on line 302 of `evaluator.py` (2-tuple unpack from new 3-tuple return).

- [ ] **Step 2.3: Update `add_evaluation_semantics` in `evaluator.py`**

**Change 1** — line 302, unpack 3-tuple:

```python
# Before:
native_action_saturation, native_action_saturation_ratio = _native_action_saturation(frames)

# After:
native_action_saturation, native_action_saturation_ratio, native_action_saturation_phase_ratios = _native_action_saturation(frames)
```

**Change 2** — `data_quality` dict (around lines 363-376), add two new fields:

```python
enriched["data_quality"] = {
    "replay_verified": replay_verified,
    "action_contract_valid": action_contract_valid,
    "action_contract_status": action_contract_status,
    "retargeting_jump": retargeting_jump,
    "native_action_saturation": native_action_saturation,
    "native_action_saturation_ratio": native_action_saturation_ratio,
    "native_action_saturation_phase_ratios": native_action_saturation_phase_ratios,
    "native_action_saturation_seat_ratio": native_action_saturation_phase_ratios.get("SEAT", 0.0),
    "sync_quality": sync_quality,
    "control_quality": "fail"
    if data_quality_reasons or action_contract_status == "fail"
    else "unknown"
    if action_contract_status != "pass"
    else "pass",
    "quality_failure_reasons": sorted(set(data_quality_reasons)),
}
```

- [ ] **Step 2.4: Run the full evaluator test suite**

```bash
uv run pytest apps/api/tests/test_evaluator.py -v
```

Expected: all tests pass including pre-existing ones (`test_evaluator_success`, `test_evaluator_retargeting_jump_gate`, `test_peg_in_hole_task_state_success`, etc.)

- [ ] **Step 2.5: Lint check**

```bash
uvx ruff check apps/api/app/services/evaluator.py apps/api/tests/test_evaluator.py
uvx ruff format --check apps/api/app/services/evaluator.py apps/api/tests/test_evaluator.py
```

Expected: no issues. If format diff, run `uvx ruff format <file>` then re-check.

- [ ] **Step 2.6: Commit**

```bash
git add apps/api/app/services/evaluator.py apps/api/tests/test_evaluator.py
git commit -m "feat: phase-conditional native action saturation gate

Replace aggregate-ratio hard fail with SEAT-only saturation gate.
INSERT saturation is now a soft warning metric only.

- SEAT sat > 0.30 → fail (was: aggregate > 0.05)
- Unlocks 2 Gate A episodes previously rejected by INSERT saturation
- Stores phase_ratios and seat_ratio in data_quality for observability
- gate_match_failure_count=0 confirms prior gate was internally consistent"
```

---

## Task 3: Update live `RdfLiveCurationGate` in `teleop_se3_agent.py`

**Files:**
- Modify: `/home/kangrim/IsaacLab/scripts/environments/teleoperation/teleop_se3_agent.py`

**Context:** `RdfLiveCurationGate.evaluate()` (line 1386) currently computes aggregate saturation ratio and hard-fails when `aggregate > max_native_action_saturation_ratio (0.05)`. This is what triggers episode reset during HMD data collection. No existing unit tests for this class (Isaac Lab top-level imports prevent isolated testing — runtime verification required).

- [ ] **Step 3.1: Add CLI arg and env var**

In `teleop_se3_agent.py`, add after the existing `--rdf_live_curation_max_native_action_saturation_ratio` block (after line 285):

```python
parser.add_argument(
    "--rdf_live_curation_max_seat_action_saturation_ratio",
    type=float,
    default=env_float("RDF_LIVE_CURATION_MAX_SEAT_ACTION_SATURATION_RATIO", 0.30),
    help=(
        "Maximum SEAT-phase action saturation ratio before live curation hard-fails. "
        "INSERT saturation is recorded as a metric only and does not gate."
    ),
)
```

Also update the help text of the **existing** `--rdf_live_curation_max_native_action_saturation_ratio` arg (around line 281) so it no longer implies it controls the hard fail:

```python
parser.add_argument(
    "--rdf_live_curation_max_native_action_saturation_ratio",
    type=float,
    default=env_float("RDF_LIVE_CURATION_MAX_NATIVE_ACTION_SATURATION_RATIO", 0.05),
    help=(
        "Aggregate native action saturation ratio — recorded for observability only. "
        "Hard fail is controlled by --rdf_live_curation_max_seat_action_saturation_ratio."
    ),
)
```

- [ ] **Step 3.2: Add `_frame_phase` staticmethod and `max_seat_action_saturation_ratio` to `RdfLiveCurationGate`**

In `__init__` (line 1301), add parameter after `max_native_action_saturation_ratio`:

```python
def __init__(
    self,
    *,
    min_frames: int,
    max_native_action_saturation_ratio: float,
    max_seat_action_saturation_ratio: float,
    max_retargeting_jump: float,
    max_tracking_loss_rate: float,
    print_every: int,
) -> None:
    self.min_frames = max(0, int(min_frames))
    self.max_native_action_saturation_ratio = max(0.0, min(1.0, float(max_native_action_saturation_ratio)))
    self.max_seat_action_saturation_ratio = max(0.0, min(1.0, float(max_seat_action_saturation_ratio)))
    self.max_retargeting_jump = max(0.0, float(max_retargeting_jump))
    self.max_tracking_loss_rate = max(0.0, min(1.0, float(max_tracking_loss_rate)))
    self.print_every = max(0, int(print_every))
    self._last_status = None
    self._last_reason_text = None
```

Add `_frame_phase` staticmethod before `evaluate()` (after `_retargeting_vector`, around line 1385):

```python
@staticmethod
def _frame_phase(frame: dict) -> str:
    """Read action_phase using same fallback chain as offline evaluator."""
    metadata = frame.get("metadata") or {}
    phase = metadata.get("action_phase")
    if isinstance(phase, str) and phase.strip():
        return phase.strip().upper()
    task_state = metadata.get("task_state") or {}
    phase = task_state.get("action_phase")
    if isinstance(phase, str) and phase.strip():
        return phase.strip().upper()
    phase = frame.get("action_phase")
    if isinstance(phase, str) and phase.strip():
        return phase.strip().upper()
    return "UNKNOWN"
```

- [ ] **Step 3.3: Rewrite saturation block in `evaluate()`**

Replace lines 1392-1396 (aggregate saturation computation):

```python
# Before:
action_vectors = [vector for frame in frames if (vector := self._action_vector(frame)) is not None]
saturated_count = sum(
    1 for vector in action_vectors if any(abs(value) >= 0.999 for value in vector[:6])
)
saturation_ratio = saturated_count / len(action_vectors) if action_vectors else None
```

With:

```python
action_sat_pairs: list[tuple[str, bool]] = []
for frame in frames:
    vector = self._action_vector(frame)
    if vector is None:
        continue
    is_sat = any(abs(v) >= 0.999 for v in vector[:6])
    action_sat_pairs.append((self._frame_phase(frame), is_sat))

saturated_count = sum(1 for _, is_sat in action_sat_pairs if is_sat)
saturation_ratio = saturated_count / len(action_sat_pairs) if action_sat_pairs else None
seat_pairs = [(ph, s) for ph, s in action_sat_pairs if ph == "SEAT"]
seat_saturation_ratio = (
    sum(1 for _, s in seat_pairs if s) / len(seat_pairs) if seat_pairs else 0.0
)
```

- [ ] **Step 3.4: Update the saturation gate check in `evaluate()`**

Replace lines 1420-1425 (gate logic):

```python
# Before:
if saturation_ratio is None:
    pending_reasons.append("ACTION_SATURATION:UNKNOWN")
elif saturation_ratio > self.max_native_action_saturation_ratio:
    fail_reasons.append(
        f"NATIVE_ACTION_SATURATION:{saturation_ratio:.3f}>{self.max_native_action_saturation_ratio:.3f}"
    )
```

With:

```python
if saturation_ratio is None:
    pending_reasons.append("ACTION_SATURATION:UNKNOWN")
elif seat_saturation_ratio > self.max_seat_action_saturation_ratio:
    fail_reasons.append(
        f"NATIVE_ACTION_SATURATION:SEAT={seat_saturation_ratio:.3f}>{self.max_seat_action_saturation_ratio:.3f}"
    )
```

- [ ] **Step 3.5: Update the result dict in `evaluate()`**

Replace lines 1447-1450 (result dict saturation fields):

```python
# Before:
"native_action_saturation_ratio": saturation_ratio,
"native_action_saturation_max": self.max_native_action_saturation_ratio,
"native_action_saturated_frames": saturated_count,
"native_action_frame_count": len(action_vectors),
```

With:

```python
"native_action_saturation_ratio": saturation_ratio,
"native_action_saturation_max": self.max_native_action_saturation_ratio,
"native_action_saturated_frames": saturated_count,
"native_action_frame_count": len(action_sat_pairs),
"native_action_saturation_seat_ratio": seat_saturation_ratio,
"native_action_saturation_seat_max": self.max_seat_action_saturation_ratio,
```

- [ ] **Step 3.6: Update `_maybe_print`**

Replace lines 1474-1475 (saturation display):

```python
# Before:
f"sat={_rdf_fmt_metric(result.get('native_action_saturation_ratio'), 3)}<="
f"{_rdf_fmt_metric(result.get('native_action_saturation_max'), 3)} "
```

With:

```python
f"sat_agg={_rdf_fmt_metric(result.get('native_action_saturation_ratio'), 3)} "
f"sat_seat={_rdf_fmt_metric(result.get('native_action_saturation_seat_ratio'), 3)}<="
f"{_rdf_fmt_metric(result.get('native_action_saturation_seat_max'), 3)} "
```

- [ ] **Step 3.7: Update the instantiation site**

Replace lines 2683-2698:

```python
live_curation_gate = RdfLiveCurationGate(
    min_frames=args_cli.rdf_live_curation_min_frames,
    max_native_action_saturation_ratio=args_cli.rdf_live_curation_max_native_action_saturation_ratio,
    max_seat_action_saturation_ratio=args_cli.rdf_live_curation_max_seat_action_saturation_ratio,
    max_retargeting_jump=args_cli.rdf_live_curation_max_retargeting_jump,
    max_tracking_loss_rate=args_cli.rdf_live_curation_max_tracking_loss_rate,
    print_every=args_cli.rdf_task_guidance_every,
)
print(
    "[RDF] Live curation gate enabled: auto-finalize requires live-checkable quality. "
    f"min_frames={args_cli.rdf_live_curation_min_frames} "
    f"max_seat_action_saturation_ratio="
    f"{args_cli.rdf_live_curation_max_seat_action_saturation_ratio} "
    f"max_retargeting_jump={args_cli.rdf_live_curation_max_retargeting_jump} "
    f"max_tracking_loss_rate={args_cli.rdf_live_curation_max_tracking_loss_rate} "
    f"on_fail={args_cli.rdf_live_curation_on_fail}"
)
```

- [ ] **Step 3.8: Syntax and consistency verification**

`py_compile` verifies syntax only — it does not verify gate behavior at runtime.

```bash
python3 -m py_compile /home/kangrim/IsaacLab/scripts/environments/teleoperation/teleop_se3_agent.py && echo "OK"
```

Expected: `OK`.

Verify no stale `action_vectors` references remain inside `evaluate()`:

```bash
grep -n "action_vectors" /home/kangrim/IsaacLab/scripts/environments/teleoperation/teleop_se3_agent.py
```

Expected: no matches.

**Verification scope summary:**

| What | How | When |
|---|---|---|
| `evaluator.py` correctness | `pytest`, `ruff` | Tasks 1–2 |
| `teleop_se3_agent.py` syntax | `py_compile` + grep | Step 3.8 |
| Live gate behavior (sat_agg, sat_seat logged correctly, no spurious reset) | HMD collection smoke session — check `[RDF][LIVE_CURATION]` log lines for `sat_seat` field | Next live smoke after merge |

- [ ] **Step 3.9: Commit**

```bash
cd /home/kangrim/IsaacLab
git add scripts/environments/teleoperation/teleop_se3_agent.py
git commit -m "feat: phase-conditional live curation gate for HMD collection

Replace aggregate saturation hard-fail with SEAT-phase-only gate.
INSERT saturation no longer triggers reset during data collection.

- New param: max_seat_action_saturation_ratio (default 0.30, env: RDF_LIVE_CURATION_MAX_SEAT_ACTION_SATURATION_RATIO)
- SEAT sat > 0.30 → hard fail; aggregate ratio still recorded for observability
- _frame_phase uses same metadata fallback chain as offline evaluator
- Consistent threshold (0.30) with offline evaluator change in robot-data-forge"
```

---

## Task 4: Handoff and task tracking

**Files:**
- Update: `/home/kangrim/robot-data-forge/tasks/todo.md`
- Update: `/home/kangrim/robot-data-forge/Handoff.md` (if exists)
- Update: `/home/kangrim/robot-data-forge/docs/WORKLOG.md` (if exists)

- [ ] **Step 4.1: Update `tasks/todo.md`**

Create or append to `/home/kangrim/robot-data-forge/tasks/todo.md`:

```markdown
## Phase-Conditional Saturation Gate — 2026-05-19

- [x] Task 1: `_native_action_saturation` rewritten (SEAT-only hard fail, 5 unit tests)
- [x] Task 2: `add_evaluation_semantics` updated (phase_ratios stored, 3 integration tests)
- [x] Task 3: `RdfLiveCurationGate` updated (SEAT gate, new env var, py_compile verified)
- [ ] Runtime verification: next HMD live smoke — confirm sat_seat log field present, no spurious INSERT reset

## Verification results
- pytest apps/api/tests/test_evaluator.py: all passed
- ruff check: clean
- py_compile teleop_se3_agent.py: OK
- Live HMD smoke: PENDING (next collection session)
```

- [ ] **Step 4.2: Update `Handoff.md`**

If `/home/kangrim/robot-data-forge/Handoff.md` exists, prepend:

```markdown
## 2026-05-19 — Phase-conditional saturation gate

**What changed:**
- `evaluator.py`: INSERT saturation no longer gates training_eligible; SEAT > 0.30 is the new hard fail
- `teleop_se3_agent.py`: live curation gate uses same SEAT-only threshold; aggregate ratio still logged
- New env var: `RDF_LIVE_CURATION_MAX_SEAT_ACTION_SATURATION_RATIO` (default 0.30)

**Why:**
- Diagnostic (run_mvp2_curation_diagnostic.py) confirmed 2 Gate A episodes wrongly rejected by INSERT saturation
- INSERT saturation = max-speed EE step, not bad teleop (bounded direct EE mode)

**Pending:**
- Live HMD smoke to confirm no INSERT-triggered reset; check `sat_seat` in `[RDF][LIVE_CURATION]` logs
- Collect more episodes under new gate; target ≥10 Gate A episodes before policy training
```

---

## Self-Review

**Spec coverage:**
- ✅ INSERT saturation: no gate (Tasks 1, 3), stored as metric
- ✅ SEAT saturation > 0.30: hard fail in both offline (Task 1) and live gate (Task 3)
- ✅ Aggregate ratio: still stored in both evaluator (Task 2) and live gate (Task 3) for observability
- ✅ `add_evaluation_semantics` stores `native_action_saturation_phase_ratios` and `native_action_saturation_seat_ratio` (Task 2)
- ✅ Live gate result keys match offline: `native_action_saturation_seat_ratio`, `native_action_saturation_seat_max` (Task 3 Step 3.5)
- ✅ Existing `--rdf_live_curation_max_native_action_saturation_ratio` help text updated — no longer implies hard gate (Task 3 Step 3.1)
- ✅ New env var `RDF_LIVE_CURATION_MAX_SEAT_ACTION_SATURATION_RATIO` (Task 3 Step 3.1)
- ✅ `_frame_phase` fallback chain identical in both files: metadata → task_state → frame-level → UNKNOWN
- ✅ `curator.py` not touched; diagnostic script not touched
- ✅ Handoff and task tracking in Task 4

**Placeholder scan:** None found. All steps contain actual code.

**Type consistency:**
- `_native_action_saturation` returns `tuple[str, float | None, dict[str, float]]` — consistent in Task 1 tests and Task 2 unpack.
- `native_action_saturation_phase_ratios` is `dict[str, float]` — `.get("SEAT", 0.0)` is valid.
- `action_sat_pairs` is `list[tuple[str, bool]]` — consistent in Task 3 Steps 3.3–3.5.
- `native_action_saturation_seat_ratio` / `native_action_saturation_seat_max` used consistently in Steps 3.5 and 3.6.
- `_sat_frame` defined once in Task 1.2, reused in Task 2.1 via `_make_sat_trajectory`.

**Risk:**
- Task 3 has no automated tests (Isaac Lab top-level imports prevent isolated testing). Mitigation: `py_compile` + grep in Step 3.8. Behavioral verification requires a live HMD session — documented in verification scope table (Step 3.8) and Task 4.
- The existing `test_evaluator_retargeting_jump_gate` checks `data_quality` keys. Two new keys added are additive — does not break it.
