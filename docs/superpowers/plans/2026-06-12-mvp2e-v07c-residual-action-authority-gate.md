# MVP-2E v0.7c Residual Action Authority Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans`
> or `superpowers:subagent-driven-development` to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `v0_7c`, a residual servo BC policy slice that applies a
frozen post-residual action authority gate before the selected action adapter.

**Architecture:** `v0_7c` inherits `v0_7b` residual targets and shared recovery
source. It adds an authority filter between `base_action + residual_prediction`
and `selected_action_adapter`, suppressing residual z only during `ALIGN`.

**Tech Stack:** Python 3.11, NumPy, HDF5, pytest, existing MVP-2B/MVP-2C proof
scripts.

---

## Source Artifacts

- Spec: `docs/superpowers/specs/2026-06-12-mvp2e-v07c-residual-action-authority-gate-design.md`
- Context: `.omx/context/mvp2e-v07c-residual-action-authority-gate-20260612T094416Z.md`
- PRD: `.omx/plans/prd-mvp2e-v07c-residual-action-authority-gate.md`
- Test spec: `.omx/plans/test-spec-mvp2e-v07c-residual-action-authority-gate.md`

## RALPLAN-DR Summary

### Principles

1. `v0_7b` remains historical fail-closed evidence; do not mutate it into a success.
2. Env-native 10-consecutive success remains the only Phase E pass authority.
3. Baseline/candidate fairness requires the same base servo, same authority filter,
   same adapter, same trainer, and same feature schema.
4. Action authority must be enforced after residual reconstruction and before adapter.
5. Fail closed before Isaac if offline artifacts cannot prove the authority contract.

### Decision Drivers

1. `v0_7b` recovery and offline gates passed, but actual Isaac Phase E failed `0/5`.
2. Trace diagnostics show residual z bypasses the base servo ALIGN z gate.
3. The smallest direct fix is an explicit post-residual authority layer, not a
   stronger model class or threshold relaxation.

### Viable Options

**Option A: offline residual target checks only. Rejected.**

It can catch some bad artifacts but cannot prevent runtime residual z from
violating the base servo gate under covariate shift.

**Option B: post-residual action authority gate. Chosen.**

It directly fixes the missing boundary and keeps baseline/candidate fairness by
sharing the exact same filter and adapter.

**Option C: stronger model class. Rejected for this slice.**

It changes policy capacity before fixing the known action authority bug and
would mix architecture effect with curation effect.

## ADR

**Decision:** Add `v0_7c` as a child slice with `frozen_residual_action_authority_gate_v0_7c`.

**Drivers:** v0.7b closed-loop failure, trace-proven z authority bypass, and
need to preserve A/B attribution.

**Alternatives considered:** offline-only checks and stronger model class.

**Why chosen:** It is the minimal boundary repair that directly addresses the
observed failure mode without opening held-out or changing the success metric.

**Consequences:** The final MVP-2 claim becomes "curated-vs-uncurated residual
policy under the same action-authority scaffold." Phase E may still fail, and
that must remain fail-closed evidence.

**Follow-ups:** If Phase E passes, write a separate calibration freeze plan. If
Phase E fails, diagnose `v0_7c` traces without opening held-out.

---

## Implementation Steps

### Task 1: RED tests for v0.7c contracts

**Files:**
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
- Modify: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`

- [ ] **Step 1: Add training-script tests**

Add tests named:

```python
def test_v07c_action_authority_config_is_hash_stable_and_shared(tmp_path: Path) -> None: ...
def test_v07c_authority_filter_suppresses_align_residual_z() -> None: ...
def test_v07c_authority_filter_preserves_descend_and_hold_residual_z() -> None: ...
def test_v07c_offline_action_authority_gate_detects_align_z_violation(tmp_path: Path) -> None: ...
def test_v07c_offline_gates_block_phase_e_until_both_pass(tmp_path: Path) -> None: ...
def test_v07c_policy_artifacts_share_authority_filter_and_adapter(tmp_path: Path) -> None: ...
def test_v07c_reuses_only_shared_v07b_recovery_source(tmp_path: Path) -> None: ...
def test_v07c_policy_slice_rejects_full_run_and_parses_modes(tmp_path: Path) -> None: ...
```

- [ ] **Step 2: Add runtime evaluator tests**

Add tests named:

```python
def test_v07c_runtime_fails_closed_without_authority_metadata() -> None: ...
def test_v07c_runtime_logs_before_after_authority_and_adapter() -> None: ...
def test_v07c_runtime_align_z_authority_applied_before_adapter() -> None: ...
def test_v07c_runtime_descend_keeps_residual_z_before_adapter() -> None: ...
```

- [ ] **Step 3: Run RED command**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  -k "v07c or v0_7c or action_authority" -q
```

Expected: FAIL because `v0_7c` helpers and runtime metadata do not exist yet.

### Task 2: Add v0.7c constants, config, and authority filter helpers

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Add constants near the v0.7b block**

```python
V07C_POLICY_SLICE_ID = "v0_7c"
V07C_SLICE_ID = "mvp2e_v07c_residual_action_authority_gate"
V07C_CHILD_OUTPUT_DIRNAME = "v0_7c_residual_action_authority_gate"
V07C_ACTION_AUTHORITY_CONFIG_SCHEMA_VERSION = "rdf_mvp2e_v07c_action_authority_config_v0.1.0"
V07C_MANIFEST_SCHEMA_VERSION = "rdf_mvp2e_v07c_residual_action_authority_manifest_v0.1.0"
V07C_OFFLINE_ACTION_AUTHORITY_GATE_SCHEMA_VERSION = "rdf_mvp2e_v07c_offline_action_authority_gate_v0.1.0"
V07C_POLICY_ARTIFACT_SCHEMA_VERSION = "rdf_mvp2e_v07c_policy_artifact_v0.1.0"
V07C_AUTHORITY_FILTER_ID = "frozen_residual_action_authority_gate_v0_7c"
```

- [ ] **Step 2: Add config builder**

Add:

```python
def build_v07c_action_authority_config(
    *,
    output_dir: Path,
    residual_servo_config: dict[str, Any],
    selected_action_adapter_id: str,
) -> dict[str, Any]:
    ...
```

The returned payload must include all fields listed in the PRD and
the full config/hash contract from the spec:

```text
schema_version
policy_slice
slice_id
authority_filter_id
base_servo_id
base_servo_config_sha256
residual_target_definition
behavior_phase_rule_version
selected_action_adapter_id
align_z_authority
descend_z_authority
hold_z_authority
heldout_21000_21049_accessed
candidate_specific
baseline_specific
authority_filter_config_sha256
```

`candidate_specific` and `baseline_specific` must both be `false`.
`authority_filter_config_sha256` is computed from canonical JSON excluding
the `authority_filter_config_sha256` field itself.

- [ ] **Step 3: Add validator**

Add:

```python
def validate_v07c_action_authority_config_contract(config: dict[str, Any]) -> None:
    ...
```

It must raise on wrong policy slice, wrong base servo id, wrong residual target
definition, wrong hash, or held-out access.

- [ ] **Step 4: Add authority filter**

Add:

```python
def apply_v07c_action_authority_filter(
    *,
    behavior_state_phase: str,
    base_action: np.ndarray,
    residual_prediction: np.ndarray,
    raw_action_before_authority: np.ndarray,
    authority_config: dict[str, Any],
) -> tuple[np.ndarray, dict[str, Any]]:
    ...
```

Required behavior:

```text
ALIGN: after[2] = base_action[2]
DESCEND/HOLD: after == before
```

- [ ] **Step 5: Run focused tests**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  -k "v07c_action_authority_config or v07c_authority_filter" -q
```

Expected: PASS for helper tests.

### Task 3: Add runtime authority filter to evaluator

**Files:**
- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`

- [ ] **Step 1: Add v0.7c constants**

```python
V07C_POLICY_SLICE_ID = "v0_7c"
V07C_AUTHORITY_FILTER_ID = "frozen_residual_action_authority_gate_v0_7c"
```

- [ ] **Step 2: Add strict metadata validation**

Extend residual runtime validation so `policy_slice == "v0_7c"` requires:

```text
authority_filter_id
authority_filter_config
authority_filter_config_sha256
base_servo_id=frozen_base_geometry_servo_v0_7b
residual_target_definition=actual_trace_action_minus_frozen_base_geometry_servo_action
```

Missing or mismatched metadata raises a v0.7c-specific fail-closed error.
Add explicit mismatch handling for:

```text
wrong authority_filter_id
mismatched authority_filter_config_sha256
wrong base_servo_id
wrong residual_target_definition
heldout_21000_21049_accessed=true
```

- [ ] **Step 3: Apply authority before adapter**

In `_predict_policy_action_with_diagnostics`, after computing
`raw_action = base_servo_action + residual_prediction`, branch for `v0_7c`:

```python
raw_action_before_authority = raw_action.copy()
raw_action_after_authority, authority_diagnostics = apply_v07c...
raw_action = raw_action_after_authority
```

Then let existing selected action adapter apply to `raw_action`.

- [ ] **Step 4: Extend diagnostics**

Diagnostics must include:

```text
behavior_state_phase
base_servo_action
residual_prediction
raw_action_before_authority
raw_action_after_authority
post_adapter_action_vector
authority_filter_id
authority_filter_config_sha256
align_residual_z_suppressed
residual_z_before_authority
residual_z_after_authority
z_authority_source
```

- [ ] **Step 5: Run runtime tests**

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  -k "v07c_runtime or action_authority" -q
```

Expected: PASS.

### Task 4: Build v0.7c offline artifacts

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Add v0.7c row/policy builder**

Implement:

```python
def build_v07c_residual_action_authority_slice(*, output_dir: Path) -> dict[str, Any]:
    ...
```

It should reuse `v0_7b` residualized rows and shared recovery source validation,
then write v0.7c HDF5 and policy artifacts with authority metadata.

- [ ] **Step 2: Add offline action authority gate**

Implement:

```python
def derive_v07c_offline_action_authority_gate(
    *,
    candidate_rows: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
    candidate_policy_artifact: dict[str, Any],
    baseline_policy_artifact: dict[str, Any],
    candidate_predictions: list[np.ndarray] | None = None,
    baseline_predictions: list[np.ndarray] | None = None,
    authority_config: dict[str, Any],
) -> dict[str, Any]:
    ...
```

The gate must be artifact-backed. It must either consume precomputed
candidate/baseline predictions or compute them internally from the supplied
policy artifacts, then validate:

```text
candidate_policy_artifact.policy_slice == baseline_policy_artifact.policy_slice == v0_7c
candidate_policy_artifact.authority_filter_id == baseline_policy_artifact.authority_filter_id
candidate_policy_artifact.authority_filter_config_sha256 == baseline_policy_artifact.authority_filter_config_sha256
candidate_policy_artifact.selected_action_adapter_id == baseline_policy_artifact.selected_action_adapter_id
candidate_policy_artifact.base_servo_config_sha256 == baseline_policy_artifact.base_servo_config_sha256
candidate_policy_artifact.trainer == baseline_policy_artifact.trainer
candidate_policy_artifact.hyperparameters == baseline_policy_artifact.hyperparameters
heldout_21000_21049_accessed == false for both artifacts
```

It must fail closed on adapter/hash/config mismatch before computing pass
metrics. A helper-only check over rows is insufficient.

Required pass metrics are from the spec:

```text
candidate_align_row_count > 0
baseline_align_row_count > 0
candidate_align_z_suppression_rate == 1.0
baseline_align_z_suppression_rate == 1.0
candidate_align_raw_z_equals_base_z_rate >= 0.999
baseline_align_raw_z_equals_base_z_rate >= 0.999
candidate_align_residual_z_after_authority_abs_max <= 1e-9
baseline_align_residual_z_after_authority_abs_max <= 1e-9
candidate_authority_filter_config_sha256 == baseline_authority_filter_config_sha256
candidate_selected_action_adapter_id == baseline_selected_action_adapter_id
heldout_21000_21049_accessed == false
```

- [ ] **Step 3: Add manifest**

Write `v0_7c_residual_action_authority_manifest.json` with:

```text
failed_closed=false on success
heldout_21000_21049_accessed=false
source_v0_7b_recovery_sha256
authority_filter_config_sha256
```

- [ ] **Step 4: Run offline build**

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 --policy-slice v0_7c \
  --offline-relabel-only --pretty
```

Expected:

```text
offline_residual_fit_gate_v0_7c.passed=true
offline_action_authority_gate_v0_7c.passed=true
heldout_21000_21049_accessed=false
```

### Task 5: Add CLI routing and Phase E guard

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Add parser choice**

Include `v0_7c` in `--policy-slice` choices.

- [ ] **Step 2: Reject full run**

Normal full run with `--policy-slice v0_7c` must fail with a clear message.

- [ ] **Step 3: Add expressibility runtime function**

Implement:

```python
def run_v07c_expressibility_sanity_runtime(...) -> dict[str, Any]:
    ...
```

It must fail closed before Isaac if either offline gate is missing or failed.

- [ ] **Step 4: Run guard test**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  -k "v07c_offline_gates_block_phase_e or v07c_policy_slice" -q
```

Expected: PASS.

### Task 6: Actual Isaac Phase E

**Files:**
- Writes artifacts under:
  `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7c_residual_action_authority_gate/`

- [ ] **Step 1: Run actual Isaac Phase E only after offline gates pass**

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 --policy-slice v0_7c \
  --expressibility-sanity-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 --device cuda:0 --pretty
```

- [ ] **Step 2: Interpret result**

If `success_count >= 2/5`, record Phase E pass and next valid step is a separate
calibration freeze plan.

If `success_count < 2/5`, checkpoint fail-closed and do not open calibration or
held-out.

### Task 7: Docs and final verification

**Files:**
- Modify: `docs/developer/worklog.md`
- Modify: `docs/developer/debugging_guide.md`
- Modify: `Handoff.md`
- Modify: `tasks/todo.md`

- [ ] **Step 1: Update docs**

Record:

```text
changed files
v0_7c offline gate result
v0_7c Phase E result
heldout_21000_21049_accessed=false
next valid step
MVP-2 Closed status
```

- [ ] **Step 2: Run regression verification**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  -k "v07c or v0_7c or action_authority" -q

uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  -k "v07a or v0_7a or v07a1 or v0_7a_1 or v07a2 or v0_7a_2 or v07b or v0_7b or v07c or v0_7c or residual_servo or action_authority" -q

uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -q

uv run python -m compileall -q scripts apps/api/app apps/api/tests

uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py \
  scripts/run_mvp2b_isaac_proof_evaluator.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py

git diff --check
```

Expected: all pass, or failures are reported with exact reason.

## Execution Handoff

Default execution path:

```bash
$ultragoal implement docs/superpowers/plans/2026-06-12-mvp2e-v07c-residual-action-authority-gate.md
```

Do not use `$team` unless implementation needs parallel disjoint file ownership.
Do not use `$ralph` unless explicitly selected as a fallback.
