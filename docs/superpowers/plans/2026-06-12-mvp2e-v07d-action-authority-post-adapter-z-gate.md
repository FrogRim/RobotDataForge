# MVP-2E v0.7d Action Authority Post-Adapter Z Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `v0_7d`, a child MVP-2E policy slice that applies final
post-adapter z-motion authority and env-native stable-hold authority before
any new calibration or held-out A/B work.

**Architecture:** `v0_7d` inherits `v0_7c` residual policy artifacts and selected
adapter, then adds a final action authority layer after the selected action
adapter. It also changes stable-hold readiness from geometry-threshold authority
to env-native success-mask authority while preserving geometry values as
diagnostics only.

**Tech Stack:** Python 3.11, NumPy, HDF5, pytest, existing MVP-2B/MVP-2C proof
scripts.

---

## Source Artifacts

- Spec: `docs/superpowers/specs/2026-06-12-mvp2e-v07d-action-authority-post-adapter-z-gate-design.md`
- Context: `.omx/context/mvp2e-v07d-action-authority-post-adapter-z-gate-20260612T113824Z.md`
- PRD: `.omx/plans/prd-mvp2e-v07d-action-authority-post-adapter-z-gate.md`
- Test spec: `.omx/plans/test-spec-mvp2e-v07d-action-authority-post-adapter-z-gate.md`
- Current harness report:
  `storage/proof_evidence/mvp2c_isaac_training_calibration/harness_gated_closure/mvp2e_harness_report.json`

## RALPLAN-DR Summary

### Principles

1. The final action vector sent to Isaac is the action-authority boundary.
2. Env-native success mask is the only stable-hold closure authority.
3. `v0_7c` remains historical fail-closed evidence and must not be rewritten.
4. Baseline/candidate fairness requires the same adapter, same trainer, same
   feature schema, same final authority config, and same stable-hold authority.
5. Offline gates must fail closed before any Isaac Phase E, calibration, or held-out work.

### Decision Drivers

1. Harness H1/H2 show adapter output reintroduces `ALIGN` z descent after the
   residual authority filter has already run.
2. Harness H12 shows stable-hold readiness still depends on geometry constants,
   creating a likely next authority mismatch after z leak repair.
3. The smallest repair is an authority wrapper after the selected adapter, not a
   new policy class, selected-adapter reselection, or success-metric relaxation.

### Viable Options

**Option A: patch `v0_7c` in place. Rejected.**

This would mutate historical fail-closed evidence and blur which artifact
actually passed or failed.

**Option B: add `v0_7d` with final post-adapter authority. Chosen.**

It preserves evidence lineage, directly fixes the last mutation point, and keeps
candidate/baseline fairness by sharing the wrapper.

**Option C: reselect or retune the selected action adapter. Rejected.**

The adapter was calibration-frozen evidence. Changing it would mix adapter
selection with data-curation effect and weaken MVP-2 attribution.

**Option D: introduce a stronger policy class. Rejected for this slice.**

The current failure is an authority leak, not proven model-capacity failure.
Changing model class before repairing the boundary would expand scope.

## ADR

**Decision:** Create `v0_7d_action_authority_post_adapter_z_gate` as a child
slice with a final post-adapter action-authority contract and env-native
stable-hold authority.

**Drivers:** `v0_7c` post-adapter z leak, stable-hold geometry threshold mismatch,
and the need to preserve sealed held-out and A/B attribution.

**Alternatives considered:** mutate `v0_7c`, retune adapter, or switch model class.

**Why chosen:** It repairs the exact boundary proven by harness evidence with the
smallest scope that still addresses the next likely stable-hold authority blocker.

**Consequences:** `v0_7d` can only claim train-split expressibility progress after
Phase E passes. It still cannot claim policy uplift or MVP-2 Closed.

**Follow-ups:** If `v0_7d` offline gates pass, run actual Isaac Phase E. If Phase E
passes, write a separate calibration freeze plan. If Phase E fails, regenerate the
harness report and do not open held-out.

---

## Review Finding to Test Map

| Finding | Repair in this plan | Required test / artifact |
| --- | --- | --- |
| F-1: `stable_hold_depth_m` / `stable_hold_lateral_m` geometry constants can block env-native hold | `v0_7d` stable-hold authority is top-level `env_native_success_mask`; geometry thresholds remain selected-adapter diagnostics only | `test_v07d_runtime_stable_hold_uses_env_native_mask`, `test_v07d_runtime_does_not_hold_when_geometry_true_but_env_native_false`, `test_v07d_runtime_rejects_geometry_threshold_stable_hold_authority`, H12 v0.7d harness rule |
| F-2: existing post-adapter z gate path is present but uninstrumented / unconnected | Route full `v0_7d` policy inference through `v0_7c` base servo, pre-adapter authority, selected adapter, then final post-adapter authority with no config-dependent bypass | `test_v07d_full_policy_inference_uses_v07c_base_and_final_authority`, `test_v07d_runtime_final_z_gate_is_config_independent` |
| F-3: close-critical `not_evaluated` semantics ambiguous | Close-critical `not_evaluated` keeps `close_critical_passed=false`; v0.7d harness classification remains diagnostic only | `test_mvp2e_harness_close_critical_not_evaluated_fails_closed` |
| F-4: diagnostic tier with `close_critical=true` label conflict | Harness report labels close-critical authority checks as close-critical, not diagnostic-only, while keeping `proof_authority=diagnostic_only_not_closure_authority` | `test_mvp2e_harness_can_classify_v07d_report_shape` |

F-2 is applicable to this slice because the fix must prove `v0_7d` is connected
through the full inference path, not only through the low-level adapter helper.

---

## File Structure

### Modify

- `scripts/run_mvp2b_isaac_proof_evaluator.py`
  - Add `v0_7d` constants and policy-artifact validation.
  - Add final post-adapter authority helper.
  - Route `v0_7d` policy inference through final z gate after selected adapter.
  - Replace stable-hold readiness authority with env-native mask when `v0_7d`.

- `scripts/run_mvp2c_isaac_training_calibration.py`
  - Add `v0_7d` constants/config/hash validation.
  - Build child `v0_7d_action_authority_post_adapter_z_gate` artifacts from
    `v0_7c`.
  - Add `offline_final_action_authority_gate_v0_7d`.
  - Add guarded CLI support for `--policy-slice v0_7d` only with explicit
    offline-build, expressibility-only, or harness-only modes.
  - Add Phase E fail-closed wrapper that requires offline gate pass.

- `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
  - Add RED/GREEN runtime tests for final action authority and stable hold.

- `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
  - Add RED/GREEN artifact, gate, CLI, and harness tests.

- `docs/developer/worklog.md`
- `docs/developer/debugging_guide.md`
- `tasks/todo.md`
- `Handoff.md`

### Create

No new production module is required. Keep the implementation in the existing
MVP-2 proof scripts to match established slice patterns.

### Generated During Execution

- `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7d_action_authority_post_adapter_z_gate/`
  - `v0_7d_final_action_authority_config.json`
  - `candidate_policy_artifact_v0_7d.json`
  - `baseline_policy_artifact_v0_7d.json`
  - `offline_final_action_authority_gate_v0_7d.json`
  - `v0_7d_action_authority_manifest.json`
  - later, only after offline pass:
    `expressibility_sanity_gate_v0_7d.json`

---

## Implementation Steps

### Task 1: RED runtime tests for final action authority

**Files:**

- Modify: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`

- [ ] **Step 1: Add v0.7d helper fixture**

Add a fixture near the existing v0.7c helpers:

```python
def _v07d_policy_artifact(script: Any, *, stable_hold_authority: str = "env_native_success_mask") -> dict[str, Any]:
    config = {
        "schema_version": "rdf_mvp2e_v07d_final_action_authority_config_v0.1.0",
        "policy_slice": "v0_7d",
        "slice_id": "mvp2e_v07d_action_authority_post_adapter_z_gate",
        "final_post_adapter_authority_id": "final_post_adapter_z_authority_gate_v0_7d",
        "inherited_authority_filter_id": script.V07C_AUTHORITY_FILTER_ID,
        "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
        "stable_hold_authority": stable_hold_authority,
        "align_final_z_authority": "zero_after_adapter_until_z_motion_allowed",
        "heldout_21000_21049_accessed": False,
        "candidate_specific": False,
        "baseline_specific": False,
    }
    config["final_post_adapter_authority_config_sha256"] = script._sha256_payload_excluding(
        config,
        "final_post_adapter_authority_config_sha256",
    )
    return {
        "policy_slice": "v0_7d",
        "trainer_family": script.RESIDUAL_TRAINER_FAMILY,
        "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
        "selected_action_adapter_config": {
            "controller_version": "legacy_no_v06_controller",
            "xy_action_scale": 1.0,
            "z_action_scale": 32.0,
            "z_action_clip": 0.16,
            "stable_hold_action": [0.0, 0.0, -0.02, 0.0, 0.0, 0.0, 1.0],
            "stable_hold_depth_m": 0.03,
            "stable_hold_lateral_m": 0.006,
            "stable_hold_orientation_deg": 8.0,
        },
        "base_servo_id": script.V07B_BASE_SERVO_ID,
        "base_servo_config": {
            "base_servo_id": script.V07B_BASE_SERVO_ID,
            "approach_z": -0.001,
            "contact_z": -0.002,
            "insert_z": -0.004,
            "seat_z": -0.0005,
            "xy_gain": 1.0,
            "rotation": 0.0,
            "gripper": 1.0,
        },
        "residual_target_definition": script.V07B_RESIDUAL_TARGET_DEFINITION,
        "stable_hold_authority": stable_hold_authority,
        "final_post_adapter_authority_id": "final_post_adapter_z_authority_gate_v0_7d",
        "final_post_adapter_authority_config": config,
        "final_post_adapter_authority_config_sha256": config["final_post_adapter_authority_config_sha256"],
    }
```

- [ ] **Step 2: Add final z gate test**

```python
def test_v07d_runtime_blocks_align_z_after_selected_adapter_scale() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07d_policy_artifact(script)
    policy["base_servo_config_sha256"] = script._sha256_payload(policy["base_servo_config"])
    raw_action = np.array([0.0, 0.0, -0.001, 0.0, 0.0, 0.0, 1.0], dtype=np.float64)
    metric_row = {
        "phase": "APPROACH",
        "behavior_state_phase": "ALIGN",
        "lateral_error_m": 0.03,
        "orientation_error_deg": 0.0,
        "insertion_depth_m": 0.0,
        "env_native_success": False,
        "env_native_current_consecutive_success_steps": 0,
    }

    action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy,
        raw_action=raw_action,
        action_scale=1.0,
        metric_row=metric_row,
        behavior_state_phase="ALIGN",
    )

    assert diagnostics["pre_final_authority_action_vector"][2] == pytest.approx(-0.032)
    assert action[2] == pytest.approx(0.0)
    assert diagnostics["post_adapter_action_vector"][2] == pytest.approx(0.0)
    assert diagnostics["final_post_adapter_authority_id"] == "final_post_adapter_z_authority_gate_v0_7d"
    assert diagnostics["z_motion_block_reason"] != "adapter_not_instrumented"
```

- [ ] **Step 3: Add config-independent gate test**

```python
def test_v07d_runtime_final_z_gate_is_config_independent() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07d_policy_artifact(script)
    policy["base_servo_config_sha256"] = script._sha256_payload(policy["base_servo_config"])
    policy["selected_action_adapter_config"].pop("controller_version")
    raw_action = np.array([0.0, 0.0, -0.001, 0.0, 0.0, 0.0, 1.0], dtype=np.float64)

    action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy,
        raw_action=raw_action,
        action_scale=1.0,
        metric_row={"phase": "APPROACH", "behavior_state_phase": "ALIGN", "lateral_error_m": 0.02},
        behavior_state_phase="ALIGN",
    )

    assert action[2] == pytest.approx(0.0)
    assert diagnostics["z_motion_block_reason"] in {
        "final_post_adapter_align_z_blocked",
        "alignment_gate_not_satisfied",
    }
```

- [ ] **Step 4: Add stable-hold env-native tests**

```python
def test_v07d_runtime_stable_hold_uses_env_native_mask() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07d_policy_artifact(script)
    policy["base_servo_config_sha256"] = script._sha256_payload(policy["base_servo_config"])

    action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy,
        raw_action=np.zeros(len(script.ACTION_SCHEMA), dtype=np.float64),
        action_scale=1.0,
        metric_row={
            "phase": "SEAT",
            "behavior_state_phase": "HOLD",
            "insertion_depth_m": 0.0245,
            "lateral_error_m": 0.02,
            "orientation_error_deg": 0.0,
            "env_native_success": True,
        },
        behavior_state_phase="HOLD",
    )

    assert diagnostics["stable_hold_authority"] == "env_native_success_mask"
    assert diagnostics["z_motion_block_reason"] == "stable_hold_ready_env_native"
    assert action.tolist() == pytest.approx([0.0, 0.0, -0.02, 0.0, 0.0, 0.0, 1.0])


def test_v07d_runtime_does_not_hold_when_geometry_true_but_env_native_false() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07d_policy_artifact(script)
    policy["base_servo_config_sha256"] = script._sha256_payload(policy["base_servo_config"])

    action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy,
        raw_action=np.zeros(len(script.ACTION_SCHEMA), dtype=np.float64),
        action_scale=1.0,
        metric_row={
            "phase": "SEAT",
            "behavior_state_phase": "HOLD",
            "insertion_depth_m": 0.031,
            "lateral_error_m": 0.001,
            "orientation_error_deg": 0.0,
            "env_native_success": False,
        },
        behavior_state_phase="HOLD",
    )

    assert diagnostics["stable_hold_authority"] == "env_native_success_mask"
    assert diagnostics["z_motion_block_reason"] != "stable_hold_ready_env_native"


def test_v07d_runtime_rejects_geometry_threshold_stable_hold_authority() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07d_policy_artifact(script, stable_hold_authority="geometry_thresholds")
    policy["base_servo_config_sha256"] = script._sha256_payload(policy["base_servo_config"])

    with pytest.raises(ValueError, match="v0_7d_stable_hold_authority_mismatch"):
        script._validated_v07d_final_action_authority_config(policy)
```

- [ ] **Step 5: Add full inference path RED test**

Add one test that does not call `_apply_selected_action_adapter_with_diagnostics`
directly. It must enter the normal policy action inference path and prove
`v0_7d` uses the inherited `v0_7c` base-servo / pre-adapter authority path before
the final post-adapter authority layer.

```python
def test_v07d_full_policy_inference_uses_v07c_base_and_final_authority() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy = _v07d_policy_artifact(script)
    policy["base_servo_config_sha256"] = script._sha256_payload(policy["base_servo_config"])
    metric_row = {
        "phase": "APPROACH",
        "behavior_state_phase": "ALIGN",
        "lateral_error_m": 0.03,
        "orientation_error_deg": 0.0,
        "insertion_depth_m": 0.0,
        "env_native_success": False,
    }

    action, diagnostics = script._infer_policy_action_with_diagnostics(
        policy_artifact=policy,
        metric_row=metric_row,
        behavior_state_phase="ALIGN",
    )

    assert diagnostics["policy_slice"] == "v0_7d"
    assert diagnostics["base_servo_source_policy_slice"] == "v0_7c"
    assert diagnostics["pre_adapter_authority_source_policy_slice"] == "v0_7c"
    assert diagnostics["selected_action_adapter_id"] == "isaac_signed_xy_downward_servo_v0"
    assert diagnostics["final_post_adapter_authority_id"] == "final_post_adapter_z_authority_gate_v0_7d"
    assert action[2] == pytest.approx(0.0)
```

If the repo exposes a differently named full policy inference helper, adapt this
test to that actual function. Do not replace it with another direct adapter
helper test.

- [ ] **Step 6: Run RED**

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  -k "v07d_runtime" -q
```

Expected: FAIL because `v0_7d` constants/helpers/signatures do not exist.

### Task 2: Implement evaluator-side v0.7d runtime authority

**Files:**

- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`

- [ ] **Step 1: Add constants near v0.7c constants**

```python
V07D_POLICY_SLICE_ID = "v0_7d"
V07D_SLICE_ID = "mvp2e_v07d_action_authority_post_adapter_z_gate"
V07D_FINAL_ACTION_AUTHORITY_CONFIG_SCHEMA_VERSION = "rdf_mvp2e_v07d_final_action_authority_config_v0.1.0"
V07D_FINAL_POST_ADAPTER_AUTHORITY_ID = "final_post_adapter_z_authority_gate_v0_7d"
```

- [ ] **Step 2: Add validator**

```python
def _validated_v07d_final_action_authority_config(policy_artifact: dict[str, Any]) -> dict[str, Any]:
    config = policy_artifact.get("final_post_adapter_authority_config")
    top_hash = policy_artifact.get("final_post_adapter_authority_config_sha256")
    if not isinstance(config, dict) or not top_hash:
        raise ValueError("v0_7d_final_authority_metadata_missing")
    if policy_artifact.get("final_post_adapter_authority_id") != V07D_FINAL_POST_ADAPTER_AUTHORITY_ID:
        raise ValueError("v0_7d_final_authority_id_mismatch")
    if (
        config.get("schema_version") != V07D_FINAL_ACTION_AUTHORITY_CONFIG_SCHEMA_VERSION
        or config.get("policy_slice") != V07D_POLICY_SLICE_ID
        or config.get("slice_id") != V07D_SLICE_ID
        or config.get("final_post_adapter_authority_id") != V07D_FINAL_POST_ADAPTER_AUTHORITY_ID
        or config.get("inherited_authority_filter_id") != V07C_AUTHORITY_FILTER_ID
        or config.get("stable_hold_authority") != "env_native_success_mask"
        or config.get("heldout_21000_21049_accessed") is not False
        or config.get("candidate_specific") is not False
        or config.get("baseline_specific") is not False
    ):
        raise ValueError("v0_7d_final_authority_metadata_mismatch")
    expected_hash = _sha256_payload_excluding(config, "final_post_adapter_authority_config_sha256")
    if config.get("final_post_adapter_authority_config_sha256") != expected_hash or top_hash != expected_hash:
        raise ValueError("v0_7d_final_authority_config_hash_mismatch")
    if policy_artifact.get("stable_hold_authority") != "env_native_success_mask":
        raise ValueError("v0_7d_stable_hold_authority_mismatch")
    return dict(config)
```

- [ ] **Step 3: Add env-native stable-hold helper**

```python
def _stable_hold_ready_env_native(*, metric_row: dict[str, Any]) -> bool:
    return bool(metric_row.get("env_native_success", False))
```

Keep `_stable_hold_ready` unchanged for historical slices. For `v0_7d`, validate
`_validated_v07d_final_action_authority_config(policy_artifact)` before any
stable-hold branch and never call `_stable_hold_ready`.

- [ ] **Step 4: Add final authority helper**

```python
def _apply_v07d_final_post_adapter_authority(
    *,
    action: np.ndarray,
    behavior_state_phase: str | None,
    metric_row: dict[str, Any] | None,
    final_authority_config: dict[str, Any],
    current_block_reason: str,
) -> tuple[np.ndarray, dict[str, Any]]:
    before = np.asarray(action, dtype=np.float64).copy()
    after = before.copy()
    phase = str(behavior_state_phase or "").upper()
    z_allowed = True
    reason = current_block_reason
    if phase == "ALIGN":
        z_allowed = False
        after[2] = 0.0
        reason = "final_post_adapter_align_z_blocked"
    diagnostics = {
        "final_post_adapter_authority_id": final_authority_config["final_post_adapter_authority_id"],
        "final_post_adapter_authority_config_sha256": final_authority_config[
            "final_post_adapter_authority_config_sha256"
        ],
        "pre_final_authority_action_vector": _rounded_action(before),
        "final_post_adapter_z_motion_allowed": bool(z_allowed),
        "z_motion_block_reason": reason,
    }
    return np.round(np.clip(after, -1.0, 1.0), 12), diagnostics
```

- [ ] **Step 5: Update `_apply_selected_action_adapter_with_diagnostics` signature**

Change signature to:

```python
def _apply_selected_action_adapter_with_diagnostics(
    *,
    policy_artifact: dict[str, Any],
    raw_action: np.ndarray,
    action_scale: float,
    metric_row: dict[str, Any] | None = None,
    behavior_state_phase: str | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
```

Update existing callers with `behavior_state_phase=behavior_state_phase` where
the value already exists. Keep default `None` for legacy callers.

- [ ] **Step 6: Apply final gate after adapter output**

At the end of `_apply_selected_action_adapter_with_diagnostics`, before return:

```python
    if policy_artifact.get("policy_slice") == V07D_POLICY_SLICE_ID:
        final_authority_config = _validated_v07d_final_action_authority_config(policy_artifact)
        final_action, final_diagnostics = _apply_v07d_final_post_adapter_authority(
            action=final_action,
            behavior_state_phase=behavior_state_phase or diagnostics.get("controller_input_phase"),
            metric_row=metric_row,
            final_authority_config=final_authority_config,
            current_block_reason=block_reason,
        )
        diagnostics.update(final_diagnostics)
    diagnostics["post_adapter_action_vector"] = _rounded_action(final_action)
    return final_action, diagnostics
```

Also apply this path to the generic no-controller branch and stable-hold branch
for `v0_7d`; `v0_7d` must not return early before final authority validation or
final authority diagnostics.

- [ ] **Step 7: Wire `v0_7d` through the full inference path**

Where the evaluator currently checks `policy_slice in {"v0_7b", "v0_7c"}` for
residual base-servo behavior, include `v0_7d`. Where it checks
`policy_slice == "v0_7c"` for pre-adapter authority, include `v0_7d` but record
diagnostics as inherited:

```python
if policy_slice in {V07C_POLICY_SLICE_ID, V07D_POLICY_SLICE_ID}:
    diagnostics["pre_adapter_authority_source_policy_slice"] = V07C_POLICY_SLICE_ID
```

Then apply the selected adapter and finally `_apply_v07d_final_post_adapter_authority`.
The full path must be:

```text
v0_7c base servo
-> v0_7c residual/pre-adapter authority
-> selected action adapter
-> v0_7d final post-adapter authority
-> env.step action
```

- [ ] **Step 8: Run runtime GREEN**

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  -k "v07d_runtime" -q
```

Expected: PASS.

### Task 3: RED training-script tests for v0.7d artifacts and offline gate

**Files:**

- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 0: Add local test fixtures**

```python
def _minimal_v07c_policy_artifact(*, dataset_view_role: str) -> dict[str, Any]:
    adapter_config = {
        "controller_version": "legacy_no_v06_controller",
        "xy_action_scale": 1.0,
        "z_action_scale": 32.0,
        "z_action_clip": 0.16,
        "stable_hold_action": [0.0, 0.0, -0.02, 0.0, 0.0, 0.0, 1.0],
        "stable_hold_depth_m": 0.03,
        "stable_hold_lateral_m": 0.006,
    }
    return {
        "policy_slice": "v0_7c",
        "dataset_view_role": dataset_view_role,
        "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
        "selected_action_adapter_config": adapter_config,
        "authority_filter_config": {"schema_version": "test_v0_7c"},
        "authority_filter_config_sha256": "v07c-authority-sha",
    }


def _minimal_v07d_policy_artifact(
    *,
    final_authority_config: dict[str, Any],
    stable_hold_authority: str = "env_native_success_mask",
) -> dict[str, Any]:
    adapter_config = _minimal_v07c_policy_artifact(dataset_view_role="candidate_curated")[
        "selected_action_adapter_config"
    ]
    adapter_sha = "test-parent-selected-action-adapter-config-sha"
    return {
        "policy_slice": "v0_7d",
        "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
        "selected_action_adapter_config": adapter_config,
        "parent_selected_action_adapter_config_sha256": adapter_sha,
        "effective_v07d_adapter_view_sha256": adapter_sha,
        "authority_filter_config": {"schema_version": "test_v0_7c"},
        "final_post_adapter_authority_config_sha256": final_authority_config[
            "final_post_adapter_authority_config_sha256"
        ],
        "stable_hold_authority": stable_hold_authority,
    }
```

- [ ] **Step 1: Add config test**

```python
def test_v07d_final_action_authority_config_is_hash_stable(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_v07d_final_action_authority_config(
        output_dir=tmp_path,
        inherited_authority_config_sha256="v07c-authority-sha",
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )

    assert config["policy_slice"] == "v0_7d"
    assert config["final_post_adapter_authority_id"] == "final_post_adapter_z_authority_gate_v0_7d"
    assert config["stable_hold_authority"] == "env_native_success_mask"
    script.validate_v07d_final_action_authority_config_contract(config)
```

- [ ] **Step 2: Add artifact parity and immutability tests**

```python
def test_v07d_policy_artifacts_share_final_authority_and_stable_hold(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    base_candidate = _minimal_v07c_policy_artifact(dataset_view_role="candidate_curated")
    base_baseline = _minimal_v07c_policy_artifact(dataset_view_role="baseline_uncurated")
    final_config = script.build_v07d_final_action_authority_config(
        output_dir=tmp_path,
        inherited_authority_config_sha256="v07c-authority-sha",
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )

    candidate = script.build_v07d_policy_artifact_payload(
        base_policy_artifact=base_candidate,
        final_authority_config=final_config,
        dataset_view_role="candidate_curated",
    )
    baseline = script.build_v07d_policy_artifact_payload(
        base_policy_artifact=base_baseline,
        final_authority_config=final_config,
        dataset_view_role="baseline_uncurated",
    )

    assert candidate["final_post_adapter_authority_config_sha256"] == baseline[
        "final_post_adapter_authority_config_sha256"
    ]
    assert candidate["stable_hold_authority"] == baseline["stable_hold_authority"] == "env_native_success_mask"
    assert candidate["selected_action_adapter_id"] == baseline["selected_action_adapter_id"]
    assert candidate["parent_selected_action_adapter_config_sha256"] == baseline[
        "parent_selected_action_adapter_config_sha256"
    ]
    assert candidate["effective_v07d_adapter_view_sha256"] == baseline[
        "effective_v07d_adapter_view_sha256"
    ]


def test_v07d_builds_from_v07c_without_mutating_v07c(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    base_policy = _minimal_v07c_policy_artifact(dataset_view_role="candidate_curated")
    original = copy.deepcopy(base_policy)
    final_config = script.build_v07d_final_action_authority_config(
        output_dir=tmp_path,
        inherited_authority_config_sha256="v07c-authority-sha",
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )

    policy = script.build_v07d_policy_artifact_payload(
        base_policy_artifact=base_policy,
        final_authority_config=final_config,
        dataset_view_role="candidate_curated",
    )

    assert base_policy == original
    assert policy["selected_action_adapter_config"] == original["selected_action_adapter_config"]
    assert "stable_hold_authority" not in policy["selected_action_adapter_config"]
    assert "stable_hold_uses_env_native_mask" not in policy["selected_action_adapter_config"]
```

- [ ] **Step 3: Add offline gate metadata failure test**

```python
def test_v07d_offline_gate_requires_env_native_stable_hold_authority(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_v07d_final_action_authority_config(
        output_dir=tmp_path,
        inherited_authority_config_sha256="v07c-authority-sha",
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    rows = [
        {
            "behavior_state_phase": "ALIGN",
            "base_servo_action": [0.0, 0.0, -0.001, 0.0, 0.0, 0.0, 1.0],
            "relative_x_m": 0.02,
            "relative_y_m": 0.0,
            "phase": "APPROACH",
        }
    ]
    predictions = [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]]
    bad_policy = _minimal_v07d_policy_artifact(
        final_authority_config=config,
        stable_hold_authority="geometry_thresholds",
    )

    gate = script.derive_v07d_offline_final_action_authority_gate(
        candidate_rows=rows,
        baseline_rows=rows,
        candidate_policy_artifact=bad_policy,
        baseline_policy_artifact={**bad_policy, "stable_hold_authority": "env_native_success_mask"},
        final_authority_config=config,
        candidate_predictions=predictions,
        baseline_predictions=predictions,
    )

    assert gate["passed"] is False
    assert gate["failure_reason"] == "stable_hold_authority_mismatch"
```

- [ ] **Step 4: Add offline final-z leak fail-closed test**

```python
def test_v07d_offline_gate_fails_on_corrupted_align_final_z_authority(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_v07d_final_action_authority_config(
        output_dir=tmp_path,
        inherited_authority_config_sha256="v07c-authority-sha",
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    corrupted = dict(config)
    corrupted["align_final_z_authority"] = "passthrough_after_adapter"
    corrupted["final_post_adapter_authority_config_sha256"] = script._sha256_payload_excluding(
        corrupted,
        "final_post_adapter_authority_config_sha256",
    )
    rows = [{
        "behavior_state_phase": "ALIGN",
        "base_servo_action": [0.0, 0.0, -0.001, 0.0, 0.0, 0.0, 1.0],
        "relative_x_m": 0.02,
        "relative_y_m": 0.0,
        "phase": "APPROACH",
    }]
    predictions = [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]]
    policy = _minimal_v07d_policy_artifact(
        final_authority_config=corrupted,
        stable_hold_authority="env_native_success_mask",
    )

    gate = script.derive_v07d_offline_final_action_authority_gate(
        candidate_rows=rows,
        baseline_rows=rows,
        candidate_policy_artifact=policy,
        baseline_policy_artifact=policy,
        final_authority_config=corrupted,
        candidate_predictions=predictions,
        baseline_predictions=predictions,
    )

    assert gate["passed"] is False
    assert gate["failure_reason"] in {
        "final_action_authority_config_invalid",
        "align_final_post_adapter_z_violation",
    }
```

- [ ] **Step 5: Add offline gate pass test**

```python
def test_v07d_offline_gate_passes_when_final_align_z_is_zero(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_v07d_final_action_authority_config(
        output_dir=tmp_path,
        inherited_authority_config_sha256="v07c-authority-sha",
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    rows = [
        {
            "behavior_state_phase": "ALIGN",
            "base_servo_action": [0.0, 0.0, -0.001, 0.0, 0.0, 0.0, 1.0],
            "relative_x_m": 0.02,
            "relative_y_m": 0.0,
            "phase": "APPROACH",
        }
    ]
    predictions = [[0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]]
    policy = _minimal_v07d_policy_artifact(
        final_authority_config=config,
        stable_hold_authority="env_native_success_mask",
    )

    gate = script.derive_v07d_offline_final_action_authority_gate(
        candidate_rows=rows,
        baseline_rows=rows,
        candidate_policy_artifact=policy,
        baseline_policy_artifact=policy,
        final_authority_config=config,
        candidate_predictions=predictions,
        baseline_predictions=predictions,
    )

    assert gate["passed"] is True
    assert gate["derived_from"] == "offline_train_row_action_simulation"
    assert gate["candidate_align_final_z_violation_count"] == 0
    assert gate["baseline_align_final_z_violation_count"] == 0
```

- [ ] **Step 6: Add offline/runtime adapter parity test**

```python
@pytest.mark.parametrize(
    ("behavior_state_phase", "metric_row", "raw_action"),
    [
        (
            "ALIGN",
            {"phase": "APPROACH", "behavior_state_phase": "ALIGN", "lateral_error_m": 0.03},
            [0.0, 0.0, -0.001, 0.0, 0.0, 0.0, 1.0],
        ),
        (
            "DESCEND",
            {"phase": "CONTACT", "behavior_state_phase": "DESCEND", "lateral_error_m": 0.001},
            [0.0, 0.0, -0.002, 0.0, 0.0, 0.0, 1.0],
        ),
        (
            "HOLD",
            {"phase": "SEAT", "behavior_state_phase": "HOLD", "env_native_success": True},
            [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
        ),
    ],
)
def test_v07d_offline_adapter_simulation_matches_runtime_adapter(
    tmp_path: Path,
    behavior_state_phase: str,
    metric_row: dict[str, Any],
    raw_action: list[float],
) -> None:
    train_script = load_script("run_mvp2c_isaac_training_calibration")
    eval_script = load_script("run_mvp2b_isaac_proof_evaluator")
    final_config = train_script.build_v07d_final_action_authority_config(
        output_dir=tmp_path,
        inherited_authority_config_sha256="v07c-authority-sha",
        selected_action_adapter_id="isaac_signed_xy_downward_servo_v0",
    )
    policy = _minimal_v07d_policy_artifact(final_authority_config=final_config)

    offline = train_script._simulate_selected_action_adapter_for_offline_gate(
        raw_action=np.asarray(raw_action, dtype=np.float64),
        policy_artifact=policy,
        row=metric_row,
    )
    runtime, runtime_diag = eval_script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy,
        raw_action=np.asarray(raw_action, dtype=np.float64),
        action_scale=1.0,
        metric_row=metric_row,
        behavior_state_phase=behavior_state_phase,
    )

    assert offline.tolist() == pytest.approx(runtime_diag["pre_final_authority_action_vector"])
    assert runtime.shape == offline.shape
```

This test verifies the offline selected-adapter simulator against the runtime
adapter semantics before final v0.7d authority is applied. It prevents the
offline gate from passing on a simulator that diverges from runtime behavior.

- [ ] **Step 7: Add CLI parsing test**

```python
def test_v07d_cli_mode_requires_v06_profile_and_blocks_full_run(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    args = script.parse_args([
        "--scenario-profile",
        "v0_6",
        "--offline-relabel-only",
        "--policy-slice",
        "v0_7d",
    ])
    assert args.policy_slice == "v0_7d"
    assert args.offline_relabel_only is True

    with pytest.raises(ValueError, match="policy-slice v0_7d requires an explicit safe mode"):
        script.parse_args(["--scenario-profile", "v0_6", "--policy-slice", "v0_7d"])

    with pytest.raises(ValueError, match="policy-slice v0_7d is only valid"):
        script.parse_args(["--scenario-profile", "v0_6", "--policy-slice", "v0_7d", "--run-policy-ab"])
```

- [ ] **Step 8: Run RED**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  -k "v07d or v0_7d or final_action_authority" -q
```

Expected: FAIL because training-script v0.7d helpers do not exist.

### Task 4: Implement training-script v0.7d artifact builder and offline gate

**Files:**

- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Add constants near v0.7c constants**

```python
V07D_POLICY_SLICE_ID = "v0_7d"
V07D_SLICE_ID = "mvp2e_v07d_action_authority_post_adapter_z_gate"
V07D_CHILD_OUTPUT_DIRNAME = "v0_7d_action_authority_post_adapter_z_gate"
V07D_FINAL_ACTION_AUTHORITY_CONFIG_SCHEMA_VERSION = "rdf_mvp2e_v07d_final_action_authority_config_v0.1.0"
V07D_MANIFEST_SCHEMA_VERSION = "rdf_mvp2e_v07d_action_authority_manifest_v0.1.0"
V07D_OFFLINE_FINAL_ACTION_AUTHORITY_GATE_SCHEMA_VERSION = "rdf_mvp2e_v07d_offline_final_action_authority_gate_v0.1.0"
V07D_EXPRESSIBILITY_SANITY_GATE_SCHEMA_VERSION = "rdf_mvp2e_v07d_expressibility_sanity_gate_v0.1.0"
V07D_POLICY_ARTIFACT_SCHEMA_VERSION = "rdf_mvp2e_v07d_policy_artifact_v0.1.0"
V07D_FINAL_POST_ADAPTER_AUTHORITY_ID = "final_post_adapter_z_authority_gate_v0_7d"
```

- [ ] **Step 2: Add config builder and validator**

```python
def build_v07d_final_action_authority_config(
    *,
    output_dir: Path,
    inherited_authority_config_sha256: str,
    selected_action_adapter_id: str,
) -> dict[str, Any]:
    config = {
        "schema_version": V07D_FINAL_ACTION_AUTHORITY_CONFIG_SCHEMA_VERSION,
        "policy_slice": V07D_POLICY_SLICE_ID,
        "slice_id": V07D_SLICE_ID,
        "final_post_adapter_authority_id": V07D_FINAL_POST_ADAPTER_AUTHORITY_ID,
        "inherited_policy_slice": V07C_POLICY_SLICE_ID,
        "inherited_authority_filter_id": V07C_AUTHORITY_FILTER_ID,
        "inherited_authority_filter_config_sha256": inherited_authority_config_sha256,
        "selected_action_adapter_id": selected_action_adapter_id,
        "align_final_z_authority": "zero_after_adapter_until_z_motion_allowed",
        "stable_hold_authority": "env_native_success_mask",
        "stable_hold_uses_env_native_mask": True,
        "heldout_21000_21049_accessed": False,
        "calibration_opened": False,
        "candidate_specific": False,
        "baseline_specific": False,
    }
    config["final_post_adapter_authority_config_sha256"] = _sha256_payload_excluding(
        config,
        "final_post_adapter_authority_config_sha256",
    )
    write_json(output_dir / "v0_7d_final_action_authority_config.json", config)
    return config
```

Add `validate_v07d_final_action_authority_config_contract(config)` mirroring
v0.7c validation and rejecting wrong hash, held-out access, non-env-native
stable hold, candidate-specific, or baseline-specific fields.

- [ ] **Step 3: Add v0.7d policy artifact builder**

```python
def build_v07d_policy_artifact_payload(
    *,
    base_policy_artifact: dict[str, Any],
    final_authority_config: dict[str, Any],
    dataset_view_role: str,
) -> dict[str, Any]:
    parent_adapter_config = dict(base_policy_artifact["selected_action_adapter_config"])
    parent_adapter_config_sha256 = _sha256_payload(parent_adapter_config)
    payload = dict(base_policy_artifact)
    payload.update(
        {
            "policy_slice": V07D_POLICY_SLICE_ID,
            "slice_id": V07D_SLICE_ID,
            "policy_artifact_schema_version": V07D_POLICY_ARTIFACT_SCHEMA_VERSION,
            "parent_policy_slice": V07C_POLICY_SLICE_ID,
            "dataset_view_role": dataset_view_role,
            "selected_action_adapter_config": parent_adapter_config,
            "parent_selected_action_adapter_config_sha256": parent_adapter_config_sha256,
            "effective_v07d_adapter_view_sha256": parent_adapter_config_sha256,
            "selected_action_adapter_lineage": "inherited_unchanged_from_v0_7c",
            "stable_hold_authority": "env_native_success_mask",
            "stable_hold_authority_config_sha256": final_authority_config[
                "final_post_adapter_authority_config_sha256"
            ],
            "final_post_adapter_authority_id": V07D_FINAL_POST_ADAPTER_AUTHORITY_ID,
            "final_post_adapter_authority_config": final_authority_config,
            "final_post_adapter_authority_config_sha256": final_authority_config[
                "final_post_adapter_authority_config_sha256"
            ],
            "heldout_21000_21049_accessed": False,
            "proof_authority": False,
        }
    )
    payload["policy_artifact_sha256"] = _sha256_payload_excluding(payload, "policy_artifact_sha256")
    return payload
```

Do not add `stable_hold_authority` or `stable_hold_uses_env_native_mask` to
`selected_action_adapter_config`. The selected adapter config remains parent
evidence. v0.7d authority lives in `final_post_adapter_authority_config` and
top-level `stable_hold_authority`.

- [ ] **Step 4: Add offline gate helper**

First add the training-side mirror of the runtime helper. It must share the same
field names and z-motion semantics as `_apply_v07d_final_post_adapter_authority`
in `scripts/run_mvp2b_isaac_proof_evaluator.py`.

```python
def apply_v07d_final_post_adapter_authority(
    *,
    action: np.ndarray,
    behavior_state_phase: str | None,
    metric_row: dict[str, Any] | None,
    final_authority_config: dict[str, Any],
    current_block_reason: str,
) -> tuple[np.ndarray, dict[str, Any]]:
    before = np.asarray(action, dtype=np.float64).copy()
    after = before.copy()
    phase = str(behavior_state_phase or "").upper()
    reason = current_block_reason
    z_allowed = True
    if phase == "ALIGN":
        z_allowed = False
        after[2] = 0.0
        reason = "final_post_adapter_align_z_blocked"
    diagnostics = {
        "final_post_adapter_authority_id": final_authority_config["final_post_adapter_authority_id"],
        "final_post_adapter_authority_config_sha256": final_authority_config[
            "final_post_adapter_authority_config_sha256"
        ],
        "pre_final_authority_action_vector": _rounded_action(before),
        "final_post_adapter_z_motion_allowed": bool(z_allowed),
        "z_motion_block_reason": reason,
    }
    return np.round(np.clip(after, -1.0, 1.0), 12), diagnostics
```

Then add the offline gate helper:

Add `_simulate_selected_action_adapter_for_offline_gate(...)` before using it.
It must mirror the runtime selected-adapter math and must not apply final
`v0_7d` authority:

```python
def _simulate_selected_action_adapter_for_offline_gate(
    *,
    raw_action: np.ndarray,
    policy_artifact: dict[str, Any],
    row: dict[str, Any],
) -> np.ndarray:
    adapter_id = policy_artifact.get("selected_action_adapter_id")
    config = policy_artifact.get("selected_action_adapter_config") or {}
    if adapter_id != "isaac_signed_xy_downward_servo_v0":
        raise ValueError("v0_7d_offline_adapter_id_unsupported")
    # Reuse the exact runtime adapter scale/clip/sign convention.
    # Do not copy-paste a second semantic implementation if a shared helper can
    # be extracted without changing legacy behavior.
    return _simulate_isaac_signed_xy_downward_servo_v0(
        raw_action=raw_action,
        adapter_config=config,
        row=row,
    )
```

If the runtime script already has a narrow reusable selected-adapter helper,
extract the pure adapter math into one helper and call it from both runtime and
offline gate code. The parity test above is mandatory either way.

```python
def derive_v07d_offline_final_action_authority_gate(
    *,
    candidate_rows: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
    candidate_policy_artifact: dict[str, Any],
    baseline_policy_artifact: dict[str, Any],
    final_authority_config: dict[str, Any],
    candidate_predictions: list[list[float]] | None = None,
    baseline_predictions: list[list[float]] | None = None,
) -> dict[str, Any]:
    candidate_predictions = candidate_predictions or predict_actions_for_rows(
        candidate_policy_artifact,
        candidate_rows,
    )
    baseline_predictions = baseline_predictions or predict_actions_for_rows(
        baseline_policy_artifact,
        baseline_rows,
    )
    candidate_metrics = _v07d_offline_final_action_metric_block(
        rows=candidate_rows,
        predictions=candidate_predictions,
        policy_artifact=candidate_policy_artifact,
        final_authority_config=final_authority_config,
        prefix="candidate",
    )
    baseline_metrics = _v07d_offline_final_action_metric_block(
        rows=baseline_rows,
        predictions=baseline_predictions,
        policy_artifact=baseline_policy_artifact,
        final_authority_config=final_authority_config,
        prefix="baseline",
    )
    # Fail if adapter/final-authority/stable-hold metadata differ.
    # Fail if parent/effective selected adapter config hashes differ between candidate and baseline.
    # Fail if any offline-simulated ALIGN row has abs(final_post_adapter_action_vector[2]) > 1e-9.
    # Fail if z_motion_block_reason is adapter_not_instrumented or no_v06_controller.
    # Pass only when both candidate and baseline have ALIGN evidence and all checks pass.
```

Add the metric helper:

```python
def _v07d_offline_final_action_metric_block(
    *,
    rows: list[dict[str, Any]],
    predictions: list[list[float]],
    policy_artifact: dict[str, Any],
    final_authority_config: dict[str, Any],
    prefix: str,
) -> dict[str, Any]:
    align_pairs = _phase_rows_with_predictions(rows, predictions, "ALIGN")
    if not align_pairs:
        return {f"{prefix}_align_row_count": 0, f"{prefix}_required_phase_missing": True}
    violations = 0
    bad_reasons = 0
    for row, prediction in align_pairs:
        base = np.asarray(row["base_servo_action"], dtype=np.float64)
        residual = np.asarray(prediction, dtype=np.float64)
        before = base + residual
        pre_adapter, _authority_diag = apply_v07c_action_authority_filter(
            behavior_state_phase=str(row.get("behavior_state_phase") or "ALIGN"),
            base_action=base,
            residual_prediction=residual,
            raw_action_before_authority=before,
            authority_config=policy_artifact["authority_filter_config"],
        )
        adapter_action = _simulate_selected_action_adapter_for_offline_gate(
            raw_action=pre_adapter,
            policy_artifact=policy_artifact,
            row=row,
        )
        final_action, final_diag = apply_v07d_final_post_adapter_authority(
            action=adapter_action,
            behavior_state_phase=str(row.get("behavior_state_phase") or "ALIGN"),
            metric_row=row,
            final_authority_config=final_authority_config,
            current_block_reason="offline_simulated_adapter_output",
        )
        if abs(float(final_action[2])) > 1e-9:
            violations += 1
        if final_diag["z_motion_block_reason"] in {"adapter_not_instrumented", "no_v06_controller"}:
            bad_reasons += 1
    return {
        f"{prefix}_align_row_count": len(align_pairs),
        f"{prefix}_align_final_z_violation_count": violations,
        f"{prefix}_bad_block_reason_count": bad_reasons,
    }
```

Implement exact output fields:

```text
schema_version
policy_slice
slice_id
final_post_adapter_authority_id
candidate_final_post_adapter_authority_config_sha256
baseline_final_post_adapter_authority_config_sha256
candidate_selected_action_adapter_id
baseline_selected_action_adapter_id
candidate_parent_selected_action_adapter_config_sha256
baseline_parent_selected_action_adapter_config_sha256
candidate_effective_v07d_adapter_view_sha256
baseline_effective_v07d_adapter_view_sha256
candidate_stable_hold_authority
baseline_stable_hold_authority
candidate_align_row_count
baseline_align_row_count
candidate_align_final_z_violation_count
baseline_align_final_z_violation_count
candidate_bad_block_reason_count
baseline_bad_block_reason_count
passed
failure_reason
phase_e_candidate_expressibility_unblocked
heldout_21000_21049_accessed
proof_authority
offline_final_action_authority_gate_sha256
```

This gate is fully offline. It must not depend on Phase E trace rows. Runtime
Phase E diagnostics are a later confirmation artifact, not a prerequisite for
offline pass.

- [ ] **Step 5: Add child slice builder**

```python
def build_v07d_action_authority_post_adapter_z_gate_slice(*, output_dir: Path) -> dict[str, Any]:
    parent_dir = output_dir
    v07c_dir = output_dir / V07C_CHILD_OUTPUT_DIRNAME
    v07c_manifest_path = v07c_dir / "v0_7c_residual_action_authority_manifest.json"
    if not v07c_manifest_path.exists():
        build_v07c_residual_action_authority_slice(output_dir=output_dir)
    v07c_manifest = read_json(v07c_manifest_path)
    child_dir = output_dir / V07D_CHILD_OUTPUT_DIRNAME
    child_dir.mkdir(parents=True, exist_ok=True)
    final_config = build_v07d_final_action_authority_config(
        output_dir=child_dir,
        inherited_authority_config_sha256=v07c_manifest["authority_filter_config_sha256"],
        selected_action_adapter_id=v07c_manifest["policy_artifacts"]["candidate"]["selected_action_adapter_id"],
    )
    candidate_policy = build_v07d_policy_artifact_payload(
        base_policy_artifact=read_json(v07c_dir / "candidate_policy_artifact_v0_7c.json"),
        final_authority_config=final_config,
        dataset_view_role="candidate_curated",
    )
    baseline_policy = build_v07d_policy_artifact_payload(
        base_policy_artifact=read_json(v07c_dir / "baseline_policy_artifact_v0_7c.json"),
        final_authority_config=final_config,
        dataset_view_role="baseline_uncurated",
    )
    write_json(child_dir / "candidate_policy_artifact_v0_7d.json", candidate_policy)
    write_json(child_dir / "baseline_policy_artifact_v0_7d.json", baseline_policy)
    candidate_rows = _rows_from_hdf5_metadata(v07c_dir / "candidate_curated_train_v0_7c.hdf5")
    baseline_rows = _rows_from_hdf5_metadata(v07c_dir / "baseline_uncurated_train_v0_7c.hdf5")
    candidate_predictions = predict_actions_for_rows(candidate_policy, candidate_rows)
    baseline_predictions = predict_actions_for_rows(baseline_policy, baseline_rows)
    offline_gate = derive_v07d_offline_final_action_authority_gate(
        candidate_rows=candidate_rows,
        baseline_rows=baseline_rows,
        candidate_policy_artifact=candidate_policy,
        baseline_policy_artifact=baseline_policy,
        final_authority_config=final_config,
        candidate_predictions=candidate_predictions,
        baseline_predictions=baseline_predictions,
    )
    write_json(child_dir / "offline_final_action_authority_gate_v0_7d.json", offline_gate)
```

Important: The offline gate must compute final-action diagnostics from train rows
without Isaac. Do not require Phase E trace rows to make the offline gate pass.

- [ ] **Step 6: Run training-script GREEN**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  -k "v07d or v0_7d or final_action_authority" -q
```

Expected: PASS for new helper/artifact tests. The offline gate should pass or
fail from offline simulation evidence, never from missing Phase E rows.

### Task 5: Add v0.7d CLI and Phase E fail-closed routing

**Files:**

- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Add `v0_7d` to CLI choices**

Update `parse_args` choices:

```python
choices=("v0_6", "v0_7a", "v0_7a_1", "v0_7a_2", "v0_7b", "v0_7c", "v0_7d")
```

Update mode guards so `v0_7d` is valid only for:

- offline artifact build with `--offline-relabel-only --policy-slice v0_7d`;
- Phase E expressibility with `--expressibility-sanity-only --policy-slice v0_7d`;
- later harness diagnosis with explicit harness-only flags.

It must reject bare `--policy-slice v0_7d` unless one of the explicit safe modes
above is present. It must also reject `--run-policy-ab`, calibration, held-out,
or full proof modes.

- [ ] **Step 2: Add offline artifact branch**

In the main execution branch where v0.7c artifacts are built, add:

```python
elif args.policy_slice == "v0_7d" and args.offline_relabel_only:
    artifacts = build_v07d_action_authority_post_adapter_z_gate_slice(output_dir=args.output_dir)
```

This command is the only offline-build entry path:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --offline-relabel-only \
  --policy-slice v0_7d \
  --pretty
```

Do not support `--policy-slice v0_7d --pretty` as an implicit offline build.

- [ ] **Step 3: Add Phase E wrapper**

Add:

```python
def run_v07d_expressibility_sanity_runtime(...):
    child_dir = output_dir / V07D_CHILD_OUTPUT_DIRNAME
    gate_path = child_dir / "offline_final_action_authority_gate_v0_7d.json"
    # fail closed if gate missing/not passed
    # reuse v0.7c probe manifest shape but policy artifact is candidate_policy_artifact_v0_7d.json
    # write expressibility_sanity_gate_v0_7d.json
```

If the offline gate is missing or fails from offline simulation evidence, keep
Phase E blocked and record the reason. Do not relax the gate in code and do not
run Phase E to manufacture evidence for the offline gate.

- [ ] **Step 4: Add CLI branch for expressibility**

Route `--policy-slice v0_7d --expressibility-sanity-only` to
`run_v07d_expressibility_sanity_runtime`.

- [ ] **Step 5: Run CLI tests**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  -k "v07d_cli or v0_7d_cli or expressibility" -q
```

Expected: PASS.

### Task 6: Extend harness report for v0.7d evidence

**Files:**

- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add RED harness test**

```python
def test_mvp2e_harness_close_critical_not_evaluated_fails_closed(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    report = script._build_mvp2e_harness_report_from_records(
        [
            {
                "harness_id": "H12",
                "tier": "close_critical",
                "close_critical": True,
                "status": "not_evaluated",
            }
        ],
    )

    assert report["close_critical_passed"] is False
    assert report["mvp2_closed"] is False


def test_mvp2e_h12_v07d_reads_final_authority_not_selected_adapter_geometry(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    child_dir = tmp_path / script.V07D_CHILD_OUTPUT_DIRNAME
    child_dir.mkdir(parents=True)
    script.write_json(
        child_dir / "candidate_policy_artifact_v0_7d.json",
        {
            "policy_slice": "v0_7d",
            "selected_action_adapter_config": {
                "stable_hold_depth_m": 0.03,
                "stable_hold_lateral_m": 0.006,
            },
            "stable_hold_authority": "env_native_success_mask",
            "final_post_adapter_authority_config": {
                "stable_hold_authority": "env_native_success_mask",
            },
        },
    )

    record = script._mvp2e_h12_record(output_dir=tmp_path, policy_slice="v0_7d")

    assert record["status"] == "passed"
    assert record["tier"] == "close_critical"
    assert record["close_critical"] is True
    assert record["stable_hold_authority"] == "env_native_success_mask"
    assert record["selected_adapter_geometry_thresholds_preserved_as_diagnostics"] is True


def test_mvp2e_harness_can_classify_v07d_report_shape(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    child_dir = tmp_path / script.V07D_CHILD_OUTPUT_DIRNAME
    child_dir.mkdir(parents=True)
    script.write_json(
        child_dir / "offline_final_action_authority_gate_v0_7d.json",
        {
            "schema_version": script.V07D_OFFLINE_FINAL_ACTION_AUTHORITY_GATE_SCHEMA_VERSION,
            "policy_slice": "v0_7d",
            "passed": True,
            "candidate_align_final_z_violation_count": 0,
            "baseline_align_final_z_violation_count": 0,
            "heldout_21000_21049_accessed": False,
        },
    )

    report = script.build_mvp2e_harness_report(output_dir=tmp_path)

    assert report["mvp2_closed"] is False
    assert report["heldout_opened"] is False
    assert report["proof_authority"] == "diagnostic_only_not_closure_authority"
```

- [ ] **Step 2: Update harness discovery carefully**

Keep current `v0_7c` harness behavior stable. Add optional v0.7d fields only if
the child directory exists. Do not make the existing `--harness-gated-closure-only`
mode require v0.7d.

For H12 specifically:

- For historical `v0_7c`, keep the current selected-adapter geometry-threshold
  diagnostic unchanged.
- For `v0_7d`, read `candidate_policy_artifact_v0_7d.json` and evaluate
  top-level `stable_hold_authority` plus
  `final_post_adapter_authority_config.stable_hold_authority`.
- Do not mutate `selected_action_adapter.json` or
  `selected_action_adapter_config`; its geometry thresholds stay diagnostic.
- A `close_critical=true` harness record with `status=not_evaluated` must keep
  `close_critical_passed=false`.
- Close-critical records should use `tier="close_critical"`; do not label them
  as `tier="diagnostic"` while also setting `close_critical=true`.

- [ ] **Step 3: Run harness tests**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  -k "mvp2e_harness or v07d" -q
```

Expected: PASS.

### Task 7: Generate offline artifacts and verify fail-closed boundaries

**Files:**

- Generated: `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7d_action_authority_post_adapter_z_gate/*`

- [ ] **Step 1: Build offline artifacts**

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --offline-relabel-only \
  --policy-slice v0_7d \
  --pretty
```

Expected:

```text
heldout_21000_21049_accessed=false
calibration_opened=false
mvp2_closed=false
```

- [ ] **Step 2: Inspect the offline gate**

Run:

```bash
python - <<'PY'
import json
from pathlib import Path
p = Path("storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7d_action_authority_post_adapter_z_gate/offline_final_action_authority_gate_v0_7d.json")
payload = json.loads(p.read_text())
print("passed=", payload.get("passed"))
print("failure_reason=", payload.get("failure_reason"))
print("heldout=", payload.get("heldout_21000_21049_accessed"))
PY
```

Expected: The gate either passes with real final-action diagnostics, or fails
closed with a specific missing/violation reason. It must not claim MVP-2 closure.

- [ ] **Step 3: Regenerate harness report if v0.7d evidence changes root cause**

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7c \
  --harness-gated-closure-only \
  --pretty
```

Expected: existing v0.7c harness remains historical evidence. If a separate v0.7d
harness mode is implemented, run that separately and keep outputs distinct.

### Task 8: Full verification and documentation

**Files:**

- Modify: `docs/developer/worklog.md`
- Modify: `docs/developer/debugging_guide.md`
- Modify: `tasks/todo.md`
- Modify: `Handoff.md`

- [ ] **Step 1: Run focused tests**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  -k "v07d or v0_7d or final_action_authority or stable_hold_authority or mvp2e_harness" -q
```

Expected: PASS.

- [ ] **Step 2: Run relevant full tests**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -q
```

Expected: PASS.

- [ ] **Step 3: Run static checks**

```bash
uv run python -m compileall -q scripts apps/api/app apps/api/tests
uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py \
  scripts/run_mvp2b_isaac_proof_evaluator.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py
git diff --check
```

Expected: PASS.

- [ ] **Step 4: Update docs**

Append worklog/debugging/Handoff entries with:

```text
v0_7d implemented? yes/no
offline gate passed? yes/no
Phase E run? yes/no
heldout_21000_21049_accessed=false
calibration_opened=false
mvp2_closed=false
next valid step
```

Do not write that policy uplift is proven unless held-out A/B later proves it.

---

## Execution Guidance

### Recommended Agent Staffing

- `executor` for Tasks 1-5.
- `test-engineer` for Task 6 harness coverage if parallel execution is used.
- `verifier` for Task 8 after implementation.
- `critic` or `code-reviewer` for final review before any Phase E execution.

### Reasoning Levels

- Executor: medium.
- Test engineer: medium.
- Verifier: high.
- Architect/reviewer: high.

### Follow-Up Execution Options

1. `$ultragoal` default durable execution:

```text
$ultragoal implement docs/superpowers/plans/2026-06-12-mvp2e-v07d-action-authority-post-adapter-z-gate.md
```

2. `$team` for parallel lanes:

```text
$team implement docs/superpowers/plans/2026-06-12-mvp2e-v07d-action-authority-post-adapter-z-gate.md
```

Suggested split:

- Lane A: evaluator runtime authority tests and implementation.
- Lane B: training-script artifact/offline gate tests and implementation.
- Lane C: harness/docs/verification.

3. `$ralph` fallback only if the user explicitly wants a single-owner persistent
verification loop instead of durable ultragoal tracking.

## Team Verification Path

If using `$team`, all lanes must converge on:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -q
uv run python -m compileall -q scripts apps/api/app apps/api/tests
uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py \
  scripts/run_mvp2b_isaac_proof_evaluator.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py
git diff --check
```

## Claim Boundaries

Allowed after offline-only implementation:

```text
v0.7d action-authority repair has been implemented and locally verified.
```

Allowed only after actual Isaac Phase E passes:

```text
v0.7d passed train-split expressibility sanity.
```

Still forbidden:

```text
MVP-2 Closed
policy uplift proven
curated > uncurated held-out improvement proven
real robot success
physical readiness
HMD/OpenXR readiness
visual policy performance
deployable policy
```

## Self-Review

- Spec coverage: covered final post-adapter authority, env-native stable hold,
  train/eval parity metadata, offline gate, Phase E gate, and claim boundaries.
- Placeholder scan: no unresolved placeholders, no open-ended test steps.
- Type consistency: uses `V07D_*`, `final_post_adapter_authority_*`, and
  `stable_hold_authority` consistently across tests, runtime, artifact builder,
  and docs.
