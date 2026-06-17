# MVP-2B Proof-Grade Evaluator Bridge Implementation Plan

> Superseded on 2026-06-10 by
> `docs/superpowers/plans/2026-06-10-mvp2b-isaac-proof-evaluator.md`.
> This bridge-centered plan is retained for history only. The active plan now
> follows the approved dedicated Isaac connector insertion proof evaluator
> design.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a claim-safe MVP-2B evaluator bridge that runs the selected phase-conditioned policy/trainer contract through an actual held-out evaluator path and closes MVP-2 only if the existing proof validator sees positive curated > uncurated uplift.

**Architecture:** Add a new bridge script that composes the existing MVP-2A UR harness, MVP-1+ UR source-log lineage, the Isaac rollout helper, and the current MVP-2 proof ingest validator. The bridge defaults to smoke-only evidence, can emit proof-grade external rollout JSON only under explicit proof mode, and never sets `learning_proven` without `run_mvp2_learning_proven_policy_eval.py`.

**Tech Stack:** Python 3.11+, pytest, existing JSON/HDF5 helpers, existing MVP-2 harness, existing Isaac headless runner, no new production dependency.

---

## File Structure

- Create `scripts/run_mvp2b_phase_conditioned_eval_bridge.py`
  - Loads MVP-2A harness and selected policy/trainer contract.
  - Loads UR source-log phase/action sequence from MVP-1+ lineage.
  - Runs phase-conditioned baseline/candidate rollout attempts through the Isaac helper when not skipped.
  - Writes smoke report by default.
  - Optionally writes proof-grade external rollout JSON and invokes the existing MVP-2 proof evaluator.

- Create `apps/api/tests/test_mvp2b_phase_conditioned_eval_bridge_script.py`
  - Focused tests for phase loading, sequence policy behavior, selected contract propagation, smoke boundary, and proof JSON guard.

- Modify `scripts/run_mvp1c_isaac_policy_ab_smoke.py`
  - Add a small policy reset hook in `run_isaac_policy_rollouts()` so non-linear sequence policies can reset per rollout.
  - Keep the existing linear BC smoke path backward-compatible.

- Modify `docs/developer/debugging_guide.md`
  - Add the MVP-2B bridge command and explain smoke vs proof mode.

- Modify `docs/developer/worklog.md`, `tasks/todo.md`, `Handoff.md`
  - Record final state and verification evidence after implementation.

No DB migration is required.

## RALPLAN-DR Summary

### Principles

- MVP-2 closes only through positive proof-grade held-out policy uplift.
- The selected MVP-2A policy/trainer contract must be the bridge identity.
- Smoke/runtime evidence is useful but not proof by default.
- Existing proof guards are preserved and must not be weakened.
- Failure to produce positive uplift is a valid outcome and must be reported honestly.

### Decision Drivers

1. Current Isaac smoke runner uses `linear_bc_numpy_isaac_smoke`, not the selected MVP-2A contract.
2. MVP-1+ UR source logs preserve task phases and command vectors while HDF5 metadata does not.
3. `run_mvp2_learning_proven_policy_eval.py` already owns proof-grade external ingest and should remain the closure authority.

### Viable Options

| Option | Pros | Cons | Decision |
|---|---|---|---|
| New MVP-2B bridge script over source logs + Isaac helper + existing proof ingest | Clear boundary, no validator weakening, minimal changes to current smoke script | May still produce no positive uplift | Chosen |
| Rewrite `run_mvp1c_isaac_policy_ab_smoke.py` into the MVP-2B runner | Less file count | Mixes MVP-1C smoke and MVP-2 closure semantics | Rejected |
| Ask user to fill external JSON manually only | Lowest code change | Does not advance evaluator bridge architecture | Rejected |

## Task 1: Add Red Tests For Phase-Conditioned Bridge

**Files:**
- Create: `apps/api/tests/test_mvp2b_phase_conditioned_eval_bridge_script.py`

- [ ] **Step 1: Create focused failing tests**

Add tests that import `scripts/run_mvp2b_phase_conditioned_eval_bridge.py` and assert:

```python
def test_phase_conditioned_bridge_loads_ur_source_phases(tmp_path: Path) -> None:
    script = load_script("run_mvp2b_phase_conditioned_eval_bridge")
    report = script.build_mvp2b_phase_conditioned_eval_bridge(
        output_dir=tmp_path / "bridge",
        harness_output_dir=tmp_path / "harness",
        mvp1plus_output_dir=tmp_path / "mvp1plus",
        clean=True,
        refresh_harness=True,
        refresh_mvp1plus=True,
        skip_isaac=True,
    )
    assert report["selected_policy_class"] == "phase_conditioned_sequence_bc_policy_v0"
    assert report["selected_trainer"] == "rdf_phase_conditioned_sequence_bc_trainer_contract_v0"
    assert report["source_log_lineage"]["accepted_phases"] == ["APPROACH", "CONTACT", "INSERT", "SEAT"]
    assert report["evidence_tier"] == "isaac_headless_policy_eval_smoke"
    assert report["proof_eligible"] is False
    assert report["mvp2_closed"] is False
```

Also add tests for:

```python
def test_phase_conditioned_sequence_policy_resets_and_predicts_7d_actions() -> None: ...
def test_bridge_default_does_not_emit_proof_json_when_isaac_is_skipped(tmp_path: Path) -> None: ...
def test_bridge_proof_json_requires_actual_rollout_rows(tmp_path: Path) -> None: ...
```

- [ ] **Step 2: Run tests and verify RED**

```bash
uv run pytest apps/api/tests/test_mvp2b_phase_conditioned_eval_bridge_script.py -q
```

Expected: fail because script does not exist.

## Task 2: Add Phase-Conditioned Bridge Script

**Files:**
- Create: `scripts/run_mvp2b_phase_conditioned_eval_bridge.py`

- [ ] **Step 1: Implement JSONL phase/action loading**

Implement functions:

```python
def load_phase_action_sequence(path: Path) -> list[dict[str, Any]]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        phase = str(payload["task_phase"]).upper()
        vector = payload["command"]["vector"]
        if len(vector) != 7:
            raise ValueError(f"{path}: command vector must be 7-D")
        records.append({"phase": phase, "action": [float(value) for value in vector]})
    if not records:
        raise ValueError(f"{path}: no phase/action records")
    return records
```

- [ ] **Step 2: Implement sequence policy**

Implement:

```python
@dataclass
class PhaseConditionedSequencePolicy:
    name: str
    records: list[dict[str, Any]]
    action_scale: float = 1.0

    def reset(self, seed: int | None = None) -> None:
        self._index = 0

    def predict(self, observations: np.ndarray) -> np.ndarray:
        batch = observations.shape[0] if observations.ndim == 2 else 1
        index = min(getattr(self, "_index", 0), len(self.records) - 1)
        action = np.asarray(self.records[index]["action"], dtype=np.float32) * self.action_scale
        self._index = min(index + 1, len(self.records) - 1)
        return np.tile(np.clip(action, -1.0, 1.0), (batch, 1))
```

- [ ] **Step 3: Implement bridge report builder**

`build_mvp2b_phase_conditioned_eval_bridge()` must:

1. load or refresh `build_mvp2_ur_policy_ab_harness()`,
2. read `mvp2a_transition_policy_readiness.policy_trainer_selection`,
3. require selected policy/trainer to match MVP-2A constants,
4. read UR source log paths from projection manifest,
5. create baseline/candidate sequence policies,
6. run Isaac only when `skip_isaac=False`,
7. write CSV rollout files,
8. keep default report non-proof.

- [ ] **Step 4: Run focused tests and verify GREEN**

```bash
uv run pytest apps/api/tests/test_mvp2b_phase_conditioned_eval_bridge_script.py -q
```

Expected: pass.

## Task 3: Add Reset Hook To Existing Isaac Rollout Helper

**Files:**
- Modify: `scripts/run_mvp1c_isaac_policy_ab_smoke.py`
- Test: `apps/api/tests/test_mvp2b_phase_conditioned_eval_bridge_script.py`

- [ ] **Step 1: Add helper**

Add near rollout code:

```python
def _reset_policy_for_rollout(policy: Any, seed: int) -> None:
    reset = getattr(policy, "reset", None)
    if callable(reset):
        reset(seed)
```

- [ ] **Step 2: Call helper inside `run_one()` before stepping**

Inside `run_isaac_policy_rollouts().run_one()` after `env.reset(...)`:

```python
_reset_policy_for_rollout(policy, seed)
```

- [ ] **Step 3: Run regression tests**

```bash
uv run pytest apps/api/tests/test_mvp1c_real_policy_eval_script.py apps/api/tests/test_mvp2b_phase_conditioned_eval_bridge_script.py -q
```

Expected: pass.

## Task 4: Wire Proof-Grade External JSON Emission Without Weakening Guards

**Files:**
- Modify: `scripts/run_mvp2b_phase_conditioned_eval_bridge.py`
- Test: `apps/api/tests/test_mvp2b_phase_conditioned_eval_bridge_script.py`

- [ ] **Step 1: Add explicit proof mode flag**

CLI flag:

```text
--emit-external-proof-json
```

Default is false.

- [ ] **Step 2: Build external held-out suite**

Use non-schema suite metadata:

```json
{
  "id": "mvp2b_phase_conditioned_isaac_heldout_suite",
  "held_out": true,
  "task_type": "connector_insertion",
  "source_kind": "external_trainer_eval_suite",
  "proof_role": "external_policy_eval_suite"
}
```

- [ ] **Step 3: Write proof JSON only after actual rollout rows exist**

If either CSV has zero rows, add blocker:

```text
proof_json_not_emitted_without_actual_rollouts
```

If rows exist, write:

```text
baseline_external_rollouts.json
candidate_external_rollouts.json
```

Each file must include `source_kind=external_heldout_policy_eval`,
`proof_role=external_trainer_policy_eval`, selected `policy_class`, selected
`trainer`, `external_evaluator_run`, `heldout_suite`, and `rollout_results`.

- [ ] **Step 4: Invoke existing proof evaluator only for proof JSON**

Call `build_mvp2_learning_proven_policy_eval()` with `baseline_results_path` and
`candidate_results_path`. Copy its result path into the bridge report.

- [ ] **Step 5: Verify guard tests**

```bash
uv run pytest apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py apps/api/tests/test_mvp2b_phase_conditioned_eval_bridge_script.py -q
```

Expected: pass.

## Task 5: Runtime Verification And Documentation

**Files:**
- Modify: `docs/developer/debugging_guide.md`
- Modify: `docs/developer/worklog.md`
- Modify: `tasks/todo.md`
- Modify: `Handoff.md`

- [ ] **Step 1: Run non-Isaac deterministic bridge verification**

```bash
uv run python scripts/run_mvp2b_phase_conditioned_eval_bridge.py --clean --refresh-harness --skip-isaac --pretty
```

Expected:

```text
passed=true
evidence_tier=isaac_headless_policy_eval_smoke
proof_eligible=false
mvp2_closed=false
```

- [ ] **Step 2: Run optional Isaac headless bridge when runtime is available**

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2b_phase_conditioned_eval_bridge.py \
  --clean \
  --refresh-harness \
  --rollouts-per-policy 10 \
  --max-steps 150 \
  --seed-start 9400 \
  --pretty
```

Expected if current data still cannot solve held-out task:

```text
passed=true
mvp2_closed=false
```

- [ ] **Step 3: Run full relevant verification**

```bash
uv run pytest apps/api/tests/test_mvp2b_phase_conditioned_eval_bridge_script.py -q
uv run pytest apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py -q
uv run pytest apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py -q
uv run pytest apps/api/tests/test_mvp1_proof_audit_script.py apps/api/tests/test_mvp1c_real_policy_eval_script.py -q
uv run python -m compileall -q scripts apps/api/app apps/api/tests
uvx ruff check scripts/run_mvp2b_phase_conditioned_eval_bridge.py scripts/run_mvp1c_isaac_policy_ab_smoke.py scripts/run_mvp2_learning_proven_policy_eval.py apps/api/tests/test_mvp2b_phase_conditioned_eval_bridge_script.py apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py
git diff --check
```

- [ ] **Step 4: Update docs**

Record:

- whether Isaac ran,
- baseline/candidate success rates,
- whether proof JSON was emitted,
- whether `run_mvp2_learning_proven_policy_eval.py` closed MVP-2,
- why any non-closure is valid.

## Definition Of Done

- Phase-conditioned bridge exists.
- Bridge uses the selected MVP-2A policy/trainer contract.
- Bridge reads UR phase/action source-log lineage.
- Default bridge result is non-proof smoke.
- Proof JSON can only be emitted from actual rollout rows with external
  provenance.
- Existing proxy/schema/template guards remain intact.
- MVP-2 is closed only if existing proof validator returns positive uplift.
