# MVP-2E v0.7a.1 Env-Native HOLD Relabel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `v0_7a_1` child policy slice that labels `HOLD` from the env-native success mask instead of a geometry depth constant, then re-run offline relabel/training fit before any Isaac expressibility attempt.

**Architecture:** Preserve historical `v0_7a` behavior and artifacts exactly; introduce `v0_7a_1` as a separate child slice under the same parent `v0_6` proof chain. `v0_7a_1` first enriches parent HDF5 rows from `train_generation_runtime_gate.json.generated_trace_paths`, then uses an env-native mask resolver that reads `env_native_success` directly from enriched metadata rows when present, or hydrates it from hash-checked `runtime_trace_path` evidence before relabeling. Runtime policy prediction must use the same rule as offline relabeling, but only for artifacts explicitly marked as `v0_7a_1`.

**Tech Stack:** Python 3.11+, NumPy, h5py, pytest, IsaacLab lazy runtime, existing `scripts/run_mvp2b_isaac_proof_evaluator.py`, `scripts/run_mvp2c_isaac_training_calibration.py`.

---

## RALPLAN-DR Summary

### Principles

1. Preserve `v0_7a` as historical fail-closed evidence; do not mutate or reinterpret old artifacts.
2. Use env-native success mask as seating authority; geometry values are diagnostic state, not closure authority.
3. Keep held-out `21000-21049` sealed and calibration unscheduled until offline gate and Phase E pass.
4. Apply the same phase rule to baseline and candidate, while candidate metrics remain gate-authority and baseline metrics remain report-only.
5. If honest offline fit or Phase E fails, route to pre-registered `v0_7b` residual servo BC; do not relax thresholds.

### Decision Drivers

1. Remove the recurring authority mismatch between geometry proxy constants and env-native success.
2. Unblock offline fit evaluation without changing success metric, policy uplift gate, or held-out integrity.
3. Keep the implementation small enough to verify with focused tests before any Isaac runtime.

### Viable Options

**Option A: `v0_7a_1` env-native mask relabel. Chosen.**

Pros: directly fixes the diagnosed bug class, uses zero new geometry thresholds, preserves `v0_7a`, and keeps the same policy/trainer family.
Cons: requires strict mask hydration from runtime trace evidence because parent HDF5 metadata does not always carry `env_native_success` inline.

**Option B: Lower `seat_depth_threshold_m` from `0.03` to approximately `0.025`. Rejected.**

Pros: minimal code delta.
Cons: selects a new geometry proxy after seeing the failure, repeats the same authority mismatch pattern, and weakens claim integrity.

**Option C: Skip directly to `v0_7b` residual servo BC. Deferred.**

Pros: likely stronger expressibility if phase relabel still fails.
Cons: changes policy class before testing the diagnosed relabel bug; should remain the pre-registered fallback after v0.7a.1 produces real offline/Phase E evidence.

### ADR

**Decision:** Implement `v0_7a_1` as a new child slice using env-native success mask for `HOLD`, lateral gate for `ALIGN/DESCEND`, and trace-backed mask hydration when HDF5 metadata lacks the mask.

**Drivers:** authority consistency, artifact compatibility, held-out integrity, and cheapest useful validation.

**Alternatives considered:** depth threshold lowering and direct residual-servo fallback.

**Why chosen:** it fixes the exact root cause while keeping success criteria and trainer class unchanged.

**Consequences:** `v0_7a_1` may still fail offline MAE or Phase E; such a failure becomes valid evidence for `v0_7b`, not a reason to alter thresholds.

**Follow-ups:** if `v0_7a_1` passes offline fit and Phase E, continue to the already roadmapped calibration presignal gate. If it fails, write a narrow `v0_7b` residual-servo implementation plan.

### Architect Review Corrections Applied

Architect review returned `ITERATE`; this plan applies the required corrections before execution:

1. `v0_7a_1` mask resolution is a named artifact contract with conflict, missing trace, duplicate step, unreadable trace, and hash mismatch fail-closed reasons.
2. Baseline semantics are candidate-gate-only for this slice: candidate 3-phase coverage is required; baseline uses the same rule only where valid mask evidence exists and remains report-only when mask evidence is absent. No baseline mask is fabricated.
3. Runtime rule selection uses explicit `behavior_phase_rule_version == "env_native_hold_v0_7a_1"`, not only `FEATURE_SCHEMA_V07A`.
4. `v0_7a` helpers and artifacts remain historical compatibility paths.

### Baseline Semantics Decision

The spec contains a real tension: it asks for both baseline/candidate 3-phase coverage and baseline report-only metrics when phases are missing. Current repository evidence resolves this conservatively:

```text
candidate HDF5 rows: not assumed to contain trace fields
trace evidence source: train_generation_runtime_gate.json.generated_trace_paths
required bridge: map trace files to HDF5 rows by trajectory_id/scenario id and step, then inject runtime_trace_path + runtime_trace_sha256 before hydration
baseline rows : generated uncurated rows without env-native mask evidence
```

Therefore this implementation plan chooses:

```text
candidate gate authority:
  requires env-native mask evidence
  requires ALIGN/DESCEND/HOLD coverage
  may write candidate policy artifact and allow Phase E only if offline fit passes

baseline report-only:
  uses same env-native rule when valid mask evidence exists
  does not fabricate mask=false for generated rows
  missing mask evidence is recorded as report_only_env_native_mask_missing
  baseline artifact absence or report-only incompleteness blocks future A/B, but does not block candidate-only Phase E diagnostic
```

This means `v0_7a_1` can unblock candidate expressibility diagnosis, but it cannot by itself authorize calibration or held-out A/B unless a later step provides valid baseline env-native mask evidence or a separate baseline policy path is pre-registered.

### Spec Reconciliation: Parent Trace Evidence Location

The design spec records the root-cause measurement as "per-step env-native success mask present: 40/40", but the current repository does not guarantee that every parent HDF5 row already carries `env_native_success`, `env_native_success_mask`, `runtime_trace_path`, or `runtime_trace_sha256`.

Current source of truth for those masks is:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/train_generation_runtime_gate.json
  generated_trace_paths[]
    -> isaac_runtime_train_generation_probe/...train_success_<seed>_isaac_trace.json
```

Therefore the implementation must treat parent HDF5 rows as un-enriched until the explicit trace bridge in Task 3 adds hash-checked `runtime_trace_path` and `runtime_trace_sha256`. This is a plan-level clarification of the spec, not a change to env-native authority.

## File Structure

- Modify `scripts/run_mvp2b_isaac_proof_evaluator.py`
  - Keep `derive_v07a_behavior_state_phase_from_metrics` unchanged.
  - Add `derive_v07a1_behavior_state_phase_from_metrics`.
  - Add policy-artifact rule selection so `v0_7a_1` artifacts use env-native mask derivation at runtime.
- Modify `scripts/run_mvp2c_isaac_training_calibration.py`
  - Add `v0_7a_1` constants, schema IDs, output dir, config writer, manifest writer, CLI mode, and offline/expressibility guards.
  - Add trace-backed env-native mask resolver and parent-row validation.
  - Add `v0_7a_1` relabel, train-view, policy artifact, and offline fit gate flow.
- Modify `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
  - Add runtime parity and artifact rule-selection tests.
- Modify `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
  - Add relabel rule, mask hydration, fail-closed, config, artifact, CLI guard, and offline gate tests.
- Modify docs:
  - `docs/developer/debugging_guide.md`
  - `docs/developer/worklog.md`
  - `Handoff.md`

## Artifact Layout

Write all `v0_7a_1` child artifacts under:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7a_1_behavior_state_phase_relabel/
```

Required outputs when candidate coverage passes:

```text
v0_7a_1_relabel_config.json
v0_7a_1_relabel_manifest.json
candidate_curated_train_v0_7a_1.hdf5
candidate_policy_artifact_v0_7a_1.json
offline_train_fit_gate.json
expressibility_sanity_gate_v0_7a_1.json
```

Optional/report-only baseline artifacts may be written only if valid baseline mask evidence exists. If not, the manifest must record `baseline_report_only_status=report_only_env_native_mask_missing` and future calibration/held-out must remain blocked.

## Task 1: RED Tests For v0.7a.1 Behavior Phase Authority

**Files:**
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
- Modify: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`

- [ ] **Step 1: Add direct mask-rule tests**

Add tests proving the new rule ignores geometry depth for `HOLD` and preserves the lateral gate for non-HOLD rows.

```python
def test_v07a1_behavior_state_phase_uses_env_native_mask_as_hold_authority() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    assert script.derive_v07a1_behavior_state_phase(
        {"env_native_success": True, "lateral_error_m": 0.2, "insertion_depth_m": 0.0}
    ) == "HOLD"
    assert script.derive_v07a1_behavior_state_phase(
        {"env_native_success": False, "lateral_error_m": 0.001, "insertion_depth_m": 0.025}
    ) == "DESCEND"
    assert script.derive_v07a1_behavior_state_phase(
        {"env_native_success": False, "lateral_error_m": 0.0011, "insertion_depth_m": 0.025}
    ) == "ALIGN"
```

- [ ] **Step 2: Add fail-closed missing-mask test**

```python
def test_v07a1_behavior_state_phase_rejects_missing_env_native_mask() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="env_native_mask_missing"):
        script.derive_v07a1_behavior_state_phase(
            {"lateral_error_m": 0.0, "insertion_depth_m": 0.025}
        )
```

- [ ] **Step 3: Add config invariant test**

```python
def test_v07a1_relabel_config_removes_geometry_seat_depth_threshold(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    config = script.build_v07a1_relabel_config(
        output_dir=tmp_path,
        parent_artifact_hashes={"parent_train_generation_runtime_gate_file_sha256": "abc"},
    )

    text = json.dumps(config, sort_keys=True)
    assert "seat_depth_threshold_m" not in config
    assert "SUCCESS_METRIC.insertion_depth_m_min" not in text
    assert config["hold_authority"] == "env_native_success_mask"
```

- [ ] **Step 4: Add runtime parity test**

Add to `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`:

```python
def test_v07a1_runtime_policy_prediction_derives_same_behavior_phase_rule() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    artifact = {
        "feature_schema": script.FEATURE_SCHEMA_V07A,
        "feature_schema_version": script.FEATURE_SCHEMA_V07A_VERSION,
        "behavior_state_phase_input": True,
        "behavior_phase_rule_version": "env_native_hold_v0_7a_1",
        "weights": [[0.0] * len(script.ACTION_SCHEMA) for _ in script.FEATURE_SCHEMA_V07A],
        "bias": [0.0] * len(script.ACTION_SCHEMA),
        "selected_action_adapter_config": {"action_scale": 1.0},
    }

    _, diagnostics = script._predict_policy_action_with_diagnostics(
        artifact,
        metric_row={
            "env_native_success_mask": True,
            "phase": "APPROACH",
            "insertion_depth_m": 0.0,
            "relative_x_m": 0.2,
            "relative_y_m": 0.0,
            "lateral_error_m": 0.2,
            "orientation_error_deg": 0.0,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=1.0,
    )

    assert diagnostics["behavior_state_phase"] == "HOLD"
    assert diagnostics["behavior_state_phase_source"] == "derived_v0_7a_1_runtime_rule"
```

This test intentionally uses `env_native_success_mask` without `env_native_success`, because runtime policy prediction receives pre-step metric rows where the current native diagnostic mask may be present before the post-step `env_native_success` field is attached.

Add a no-escape-hatch guard:

```python
def test_v07a1_runtime_ignores_untrusted_provided_behavior_phase() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    artifact = {
        "feature_schema": script.FEATURE_SCHEMA_V07A,
        "feature_schema_version": script.FEATURE_SCHEMA_V07A_VERSION,
        "behavior_state_phase_input": True,
        "behavior_phase_rule_version": "env_native_hold_v0_7a_1",
        "weights": [[0.0] * len(script.ACTION_SCHEMA) for _ in script.FEATURE_SCHEMA_V07A],
        "bias": [0.0] * len(script.ACTION_SCHEMA),
        "selected_action_adapter_config": {"action_scale": 1.0},
    }

    _, diagnostics = script._predict_policy_action_with_diagnostics(
        artifact,
        metric_row={
            "behavior_state_phase": "ALIGN",
            "env_native_success": True,
            "phase": "APPROACH",
            "insertion_depth_m": 0.0,
            "relative_x_m": 0.2,
            "relative_y_m": 0.0,
            "lateral_error_m": 0.2,
            "orientation_error_deg": 0.0,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=1.0,
    )

    assert diagnostics["behavior_state_phase"] == "HOLD"
    assert diagnostics["behavior_state_phase_source"] == "derived_v0_7a_1_runtime_rule"
    assert diagnostics["provided_behavior_state_phase_ignored"] is True
```

Also add a historical compatibility guard:

```python
def test_v07a_historical_runtime_rule_still_uses_depth_proxy() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    assert script.derive_v07a_behavior_state_phase_from_metrics(
        {"env_native_success": True, "lateral_error_m": 0.2, "insertion_depth_m": 0.0}
    ) == "ALIGN"
    assert script.derive_v07a_behavior_state_phase_from_metrics(
        {"env_native_success": False, "lateral_error_m": 0.0, "insertion_depth_m": 0.03}
    ) == "HOLD"
```

- [ ] **Step 5: Run RED tests**

Run:

```bash
uv run pytest \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  -k "v07a1 or v0_7a_1 or env_native_hold" -q
```

Expected: fail because `v0_7a_1` helpers and CLI branch do not exist.

## Task 2: Add v0.7a.1 Rule Helpers Without Breaking v0.7a

**Files:**
- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Add shared constants**

Add constants while leaving all `V07A_*` constants unchanged:

```python
V07A1_POLICY_SLICE_ID = "v0_7a_1"
V07A1_SLICE_ID = "mvp2e_v07a1_env_native_hold_relabel"
V07A1_CHILD_OUTPUT_DIRNAME = "v0_7a_1_behavior_state_phase_relabel"
V07A1_RELABEL_CONFIG_SCHEMA_VERSION = "rdf_mvp2e_v07a1_relabel_config_v0.1.0"
V07A1_RELABEL_MANIFEST_SCHEMA_VERSION = "rdf_mvp2e_v07a1_relabel_manifest_v0.1.0"
V07A1_POLICY_ARTIFACT_SCHEMA_VERSION = "rdf_mvp2e_v07a1_behavior_phase_policy_artifact_v0.1.0"
V07A1_OFFLINE_FIT_GATE_SCHEMA_VERSION = "rdf_mvp2e_v07a1_offline_train_fit_gate_v0.1.0"
V07A1_BEHAVIOR_PHASE_LABEL_SOURCE = "frozen_v0_7a_1_env_native_hold_rule"
V07A1_RUNTIME_BEHAVIOR_PHASE_SOURCE = "derived_v0_7a_1_runtime_rule"
V07A1_BEHAVIOR_PHASE_RULE_VERSION = "env_native_hold_v0_7a_1"
V07A1_PARENT_PROOF_CHAIN_REQUIRED_FILES = (
    "repair_probe_gate.json",
    "train_generation_runtime_gate.json",
    "candidate_curated_train.hdf5",
    "baseline_uncurated_train.hdf5",
    "candidate_policy_artifact.json",
    "baseline_policy_artifact.json",
    "curation_manifest.json",
    "selected_action_adapter.json",
    "controller_repair_config.json",
    "v0_7a_behavior_state_phase_relabel/v0_7a_relabel_config.json",
    "v0_7a_behavior_state_phase_relabel/v0_7a_relabel_manifest.json",
    "v0_7a_behavior_state_phase_relabel/offline_train_fit_gate.json",
    "v0_7a_behavior_state_phase_relabel/expressibility_sanity_gate_v0_7a.json",
)
```

- [ ] **Step 2: Add strict env-native mask extraction**

Implement the same logic in both scripts or import from the evaluator script if local patterns allow it without circular imports:

```python
def _env_native_success_mask_from_row(row: dict[str, Any]) -> bool:
    has_success = "env_native_success" in row
    has_mask = "env_native_success_mask" in row
    if not has_success and not has_mask:
        raise ValueError("env_native_mask_missing")
    values: list[bool] = []
    for key in ("env_native_success", "env_native_success_mask"):
        if key not in row:
            continue
        value = row[key]
        if isinstance(value, bool):
            values.append(value)
        elif value in (0, 1):
            values.append(bool(value))
        else:
            raise ValueError(f"env_native_mask_invalid:{key}")
    if len(set(values)) != 1:
        raise ValueError("env_native_mask_conflict")
    return values[0]
```

The accepted direct metadata keys are only:

```text
env_native_success
env_native_success_mask
```

Conflicting direct keys fail closed. Do not infer HOLD from `runtime_trace_success`, `phase == "SEAT"`, `insertion_depth_m`, or `lateral_error_m`.

- [ ] **Step 3: Add v0.7a.1 phase derivation and preserve v0.7a**

```python
def _required_v07a1_metric(row: dict[str, Any], key: str) -> float:
    if key not in row:
        raise ValueError(f"row_missing_required_metric:{key}")
    try:
        value = float(row[key])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"relabel_config_invalid:{key}") from exc
    if not math.isfinite(value):
        raise ValueError(f"relabel_config_invalid:{key}")
    return value


def derive_v07a1_behavior_state_phase_from_metrics(metric_row: dict[str, Any]) -> str:
    env_native_success = _env_native_success_mask_from_row(metric_row)
    lateral_error_m = _required_v07a1_metric(metric_row, "lateral_error_m")
    insertion_depth_m = _required_v07a1_metric(metric_row, "insertion_depth_m")
    if insertion_depth_m < 0.0:
        raise ValueError("relabel_config_invalid:negative_insertion_depth_m")
    if env_native_success:
        return "HOLD"
    if lateral_error_m <= V07A_BEHAVIOR_PHASE_LATERAL_GATE_M:
        return "DESCEND"
    return "ALIGN"
```

Expose the test-facing wrapper and row relabel API explicitly:

```python
def derive_v07a1_behavior_state_phase(row: dict[str, Any]) -> str:
    return derive_v07a1_behavior_state_phase_from_metrics(row)


def relabel_v07a1_training_row(row: dict[str, Any]) -> dict[str, Any]:
    behavior_state_phase = derive_v07a1_behavior_state_phase(row)
    original_phase = str(row.get("phase") or "")
    return {
        **row,
        "phase": original_phase,
        "original_depth_phase": original_phase,
        "behavior_state_phase": behavior_state_phase,
        "phase_label_source": V07A1_BEHAVIOR_PHASE_LABEL_SOURCE,
        "behavior_phase_rule_version": V07A1_BEHAVIOR_PHASE_RULE_VERSION,
        "behavior_phase_lateral_gate_m": V07A_BEHAVIOR_PHASE_LATERAL_GATE_M,
        "feature_schema_version": FEATURE_SCHEMA_V07A_VERSION,
    }
```

Do not change `derive_v07a_behavior_state_phase_from_metrics`.

- [ ] **Step 4: Update runtime rule selection**

In `_predict_policy_action_with_diagnostics`, branch on the explicit policy artifact rule version:

```python
rule_version = str(policy_artifact.get("behavior_phase_rule_version") or "")
if uses_behavior_phase:
    if rule_version == V07A1_BEHAVIOR_PHASE_RULE_VERSION:
        provided_phase = metric_row.get("behavior_state_phase")
        behavior_state_phase = derive_v07a1_behavior_state_phase_from_metrics(metric_row)
        behavior_state_phase_source = V07A1_RUNTIME_BEHAVIOR_PHASE_SOURCE
        provided_phase_ignored = bool(provided_phase)
    elif metric_row.get("behavior_state_phase"):
        behavior_state_phase = str(metric_row["behavior_state_phase"]).upper()
        behavior_state_phase_source = "provided_metric_row"
    else:
        behavior_state_phase = derive_v07a_behavior_state_phase_from_metrics(metric_row)
        behavior_state_phase_source = "derived_v0_7a_runtime_rule"
```

For `v0_7a_1`, `metric_row["behavior_state_phase"]` is untrusted runtime input unless it also carries a future explicitly matching relabel rule hash. This plan does not implement that hash-trusted shortcut. Always derive from mask + lateral gate for `v0_7a_1`.

The diagnostics update must expose the local decision with this exact key:

```python
"provided_behavior_state_phase_ignored": provided_phase_ignored,
```

- [ ] **Step 5: Run focused tests**

Run the command from Task 1 Step 5. Expected: phase helper and runtime parity tests pass; artifact flow tests may still fail until later tasks.

## Task 3: Add Trace-Backed Mask Hydration For Parent HDF5 Rows

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add parent trace enrichment bridge tests**

Current parent HDF5 rows must not be assumed to contain `env_native_success`, `env_native_success_mask`, `runtime_trace_path`, or `runtime_trace_sha256`. The available runtime evidence is the external train-generation gate artifact:

```text
train_generation_runtime_gate.json.generated_trace_paths
```

Add tests that lock the bridge from gate artifact to HDF5 rows:

```python
def test_v07a1_enriches_candidate_row_from_train_generation_trace_gate(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    trace_dir = tmp_path / "isaac_runtime_train_generation_probe"
    trace_dir.mkdir()
    trace_path = trace_dir / "train_generation_probe_0017_train_success_19000_isaac_trace.json"
    script.write_json(
        trace_path,
        {
            "trace": [
                {
                    "step": 0,
                    "env_native_success": True,
                    "env_native_success_mask": True,
                    "lateral_error_m": 0.0,
                    "insertion_depth_m": 0.024,
                }
            ]
        },
    )
    train_gate = {
        "generated_trace_paths": [str(trace_path)],
        "generated_success_trace_paths": [str(trace_path)],
    }
    row = {
        "trajectory_id": "mvp2c_train_success_19000",
        "step": 0,
        "lateral_error_m": 0.0,
        "insertion_depth_m": 0.024,
    }

    enriched, report = script.enrich_v07a1_candidate_rows_with_runtime_traces(
        rows=[row],
        train_generation_runtime_gate=train_gate,
    )

    assert enriched[0]["runtime_trace_path"] == str(trace_path)
    assert enriched[0]["runtime_trace_sha256"] == script._sha256_file(trace_path)
    hydrated = script.hydrate_v07a1_env_native_mask(enriched[0])
    assert hydrated["env_native_success"] is True
    assert report["candidate_trace_enriched_rows"] == 1


def test_v07a1_missing_trace_for_candidate_row_is_excluded_not_fabricated() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    rows = [{"trajectory_id": "mvp2c_train_success_19999", "step": 0}]
    enriched, report = script.enrich_v07a1_candidate_rows_with_runtime_traces(
        rows=rows,
        train_generation_runtime_gate={"generated_trace_paths": []},
    )

    assert enriched == []
    assert report["candidate_trace_missing_rows"] == 1
    assert report["candidate_trace_excluded_reason_counts"]["runtime_trace_missing"] == 1


def test_v07a1_ambiguous_duplicate_trace_mapping_fails_closed(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    first = tmp_path / "train_generation_probe_0001_train_success_19000_isaac_trace.json"
    second = tmp_path / "train_generation_probe_9999_train_success_19000_isaac_trace.json"
    for path in (first, second):
        script.write_json(path, {"trace": [{"step": 0, "env_native_success_mask": True}]})

    with pytest.raises(ValueError, match="runtime_trace_mapping_ambiguous"):
        script.enrich_v07a1_candidate_rows_with_runtime_traces(
            rows=[{"trajectory_id": "mvp2c_train_success_19000", "step": 0}],
            train_generation_runtime_gate={"generated_trace_paths": [str(first), str(second)]},
        )
```

- [ ] **Step 2: Implement parent trace enrichment bridge**

Add:

```python
def _scenario_id_from_candidate_trajectory_id(trajectory_id: str) -> str:
    # e.g. mvp2c_train_success_19000 -> train_success_19000
    ...


def build_v07a1_runtime_trace_index(
    train_generation_runtime_gate: dict[str, Any],
) -> dict[str, Path]:
    trace_paths = train_generation_runtime_gate.get("generated_trace_paths") or []
    index: dict[str, Path] = {}
    ambiguous: set[str] = set()
    for raw_path in trace_paths:
        path = Path(str(raw_path))
        scenario_id = _scenario_id_from_trace_filename(path.name)
        if scenario_id in index:
            ambiguous.add(scenario_id)
        index[scenario_id] = path
    if ambiguous:
        raise ValueError("runtime_trace_mapping_ambiguous")
    return index


def enrich_v07a1_candidate_rows_with_runtime_traces(
    *,
    rows: list[dict[str, Any]],
    train_generation_runtime_gate: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ...
```

Bridge semantics:

```text
match key:
  trajectory_id/scenario_id -> train_success_<seed>
  trace filename -> train_generation_probe_<index>_train_success_<seed>_isaac_trace.json

for matched rows:
  inject runtime_trace_path=str(path)
  inject runtime_trace_sha256=_sha256_file(path)

for missing trace rows:
  exclude from v0_7a_1 candidate train view
  count as runtime_trace_missing

for ambiguous duplicate trace mapping:
  fail closed with runtime_trace_mapping_ambiguous
```

The bridge does not read held-out, does not run Isaac, and does not fabricate `env_native_success`. It only authenticates candidate rows against already recorded train-generation traces.

- [ ] **Step 3: Add tests for trace hydration and SHA guard**

```python
def test_v07a1_hydrates_env_native_mask_from_hash_checked_runtime_trace(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    trace_path = tmp_path / "trace.json"
    trace_payload = {
        "trace": [
            {"step": 7, "env_native_success": True, "env_native_success_mask": True},
        ]
    }
    trace_path.write_text(json.dumps(trace_payload), encoding="utf-8")
    row = {
        "runtime_trace_path": str(trace_path),
        "runtime_trace_sha256": script._sha256_file(trace_path),
        "step": 7,
        "lateral_error_m": 0.2,
        "insertion_depth_m": 0.0,
    }

    hydrated = script.hydrate_v07a1_env_native_mask(row)

    assert hydrated["env_native_success"] is True
    assert hydrated["env_native_success_mask_source"] == "runtime_trace_path"
```

```python
def test_v07a1_trace_mask_hydration_rejects_sha_mismatch(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(json.dumps({"trace": [{"step": 1, "env_native_success": False}]}), encoding="utf-8")

    with pytest.raises(ValueError, match="runtime_trace_sha256_mismatch"):
        script.hydrate_v07a1_env_native_mask(
            {
                "runtime_trace_path": str(trace_path),
                "runtime_trace_sha256": "bad",
                "step": 1,
                "lateral_error_m": 0.0,
                "insertion_depth_m": 0.0,
            }
        )
```

Also add conflict and step ambiguity tests:

```python
def test_v07a1_direct_mask_conflict_fails_closed() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="env_native_mask_conflict"):
        script.hydrate_v07a1_env_native_mask(
            {
                "env_native_success": True,
                "env_native_success_mask": False,
                "lateral_error_m": 0.0,
                "insertion_depth_m": 0.0,
            }
        )


def test_v07a1_trace_mask_hydration_rejects_duplicate_step(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        json.dumps(
            {
                "trace": [
                    {"step": 3, "env_native_success": False},
                    {"step": 3, "env_native_success": True},
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="runtime_trace_step_match_invalid"):
        script.hydrate_v07a1_env_native_mask(
            {
                "runtime_trace_path": str(trace_path),
                "runtime_trace_sha256": script._sha256_file(trace_path),
                "step": 3,
                "lateral_error_m": 0.0,
                "insertion_depth_m": 0.0,
            }
        )
```

Add named failure tests for malformed JSON and invalid step fields:

```python
def test_v07a1_trace_mask_hydration_rejects_malformed_json(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    trace_path = tmp_path / "trace.json"
    trace_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ValueError, match="runtime_trace_invalid_json"):
        script.hydrate_v07a1_env_native_mask(
            {
                "runtime_trace_path": str(trace_path),
                "runtime_trace_sha256": script._sha256_file(trace_path),
                "step": 1,
                "lateral_error_m": 0.0,
                "insertion_depth_m": 0.0,
            }
        )


def test_v07a1_trace_mask_hydration_rejects_invalid_row_step(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(json.dumps({"trace": []}), encoding="utf-8")

    with pytest.raises(ValueError, match="runtime_trace_row_step_invalid"):
        script.hydrate_v07a1_env_native_mask(
            {
                "runtime_trace_path": str(trace_path),
                "runtime_trace_sha256": script._sha256_file(trace_path),
                "step": "bad",
                "lateral_error_m": 0.0,
                "insertion_depth_m": 0.0,
            }
        )


def test_v07a1_trace_mask_hydration_rejects_invalid_trace_step(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(json.dumps({"trace": [{"step": "bad", "env_native_success": True}]}), encoding="utf-8")

    with pytest.raises(ValueError, match="runtime_trace_step_invalid"):
        script.hydrate_v07a1_env_native_mask(
            {
                "runtime_trace_path": str(trace_path),
                "runtime_trace_sha256": script._sha256_file(trace_path),
                "step": 1,
                "lateral_error_m": 0.0,
                "insertion_depth_m": 0.0,
            }
        )
```

- [ ] **Step 4: Implement hydration**

```python
def hydrate_v07a1_env_native_mask(row: dict[str, Any]) -> dict[str, Any]:
    if "env_native_success" in row or "env_native_success_mask" in row:
        mask = _env_native_success_mask_from_row(row)
        return {
            **row,
            "env_native_success": mask,
            "env_native_success_mask": mask,
            "env_native_success_mask_source": "metadata_json",
        }
    trace_path_value = row.get("runtime_trace_path")
    if not trace_path_value:
        raise ValueError("env_native_mask_missing")
    trace_path = Path(str(trace_path_value))
    if not trace_path.exists():
        raise ValueError("runtime_trace_unreadable")
    expected_sha = str(row.get("runtime_trace_sha256") or "")
    if not expected_sha:
        raise ValueError("runtime_trace_sha256_missing")
    if _sha256_file(trace_path) != expected_sha:
        raise ValueError("runtime_trace_sha256_mismatch")
    try:
        trace = read_json(trace_path)
    except json.JSONDecodeError as exc:
        raise ValueError("runtime_trace_invalid_json") from exc
    rows = trace.get("trace")
    if not isinstance(rows, list):
        raise ValueError("runtime_trace_invalid")
    try:
        target_step = int(row["step"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("runtime_trace_row_step_invalid") from exc
    matches: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            raise ValueError("runtime_trace_invalid")
        try:
            trace_step = int(item["step"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("runtime_trace_step_invalid") from exc
        if trace_step == target_step:
            matches.append(item)
    if len(matches) != 1:
        raise ValueError("runtime_trace_step_match_invalid")
    mask = _env_native_success_mask_from_row(matches[0])
    return {
        **row,
        "env_native_success": mask,
        "env_native_success_mask": mask,
        "env_native_success_mask_source": "runtime_trace_path",
    }
```

- [ ] **Step 5: Add parent-row preparation**

Add:

```python
def prepare_v07a1_training_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for row in rows:
        prepared.append(relabel_v07a1_training_row(hydrate_v07a1_env_native_mask(row)))
    return prepared
```

Use this strict function only after the candidate row set has been filtered to rows with authenticatable env-native evidence. The `v0_7a_1` candidate train view must be built from authenticated rows only:

```text
authenticated candidate row:
  inline env_native_success/env_native_success_mask with no conflict
  OR runtime_trace_path + runtime_trace_sha256 + step that hydrates exactly one trace row

unauthenticated generated candidate row:
  no inline mask and no runtime trace evidence
  excluded from v0_7a_1 candidate train view
  counted in manifest, not relabeled with fabricated mask=false

tampered/invalid evidence row:
  declares runtime evidence but fails hash/read/step/mask validation
  fail-closed input, not excluded silently
```

Add manifest counters:

```python
{
    "candidate_parent_rows_total": total_candidate_parent_rows,
    "candidate_authenticated_rows_used": len(candidate_prepared_rows),
    "candidate_unauthenticated_rows_excluded": unauthenticated_generated_count,
    "candidate_invalid_evidence_rows_failed_closed": invalid_evidence_count,
    "candidate_excluded_row_reason_counts": {
        "env_native_mask_missing_generated_row": unauthenticated_generated_count,
    },
}
```

Expose this as the candidate preparation API:

```python
def prepare_v07a1_candidate_train_rows(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ...
```

The helper must return only authenticated relabeled rows plus the manifest counters above. It may exclude unauthenticated generated rows, but it must raise or return fail-closed status for invalid declared evidence.

This deterministic provenance filter is not proof authority and must be described as a Phase E diagnostic train view. It prevents generated rows without env-native authority from poisoning the relabel while keeping the exclusion auditable. If no authenticated candidate rows remain, or if authenticated rows do not provide all required behavior phases, the slice fails closed.

For baseline rows, implement a separate report-only preparation function:

```python
def prepare_v07a1_baseline_report_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    missing_mask_count = 0
    for row in rows:
        try:
            prepared.append(relabel_v07a1_training_row(hydrate_v07a1_env_native_mask(row)))
        except ValueError as exc:
            if "env_native_mask_missing" not in str(exc):
                raise
            missing_mask_count += 1
    return prepared, {
        "baseline_report_only": True,
        "baseline_env_native_mask_missing_count": missing_mask_count,
        "baseline_report_only_status": (
            "report_only_env_native_mask_missing" if missing_mask_count else "computed"
        ),
    }
```

Do not silently set missing baseline masks to `False`. Missing baseline masks must block future calibration/held-out A/B until a valid baseline mask source or separate baseline policy path is pre-registered.

- [ ] **Step 6: Run hydration tests**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  -k "v07a1 and (hydrate or mask or missing or trace or enrich)" -q
```

Expected: pass.

## Task 4: Build v0.7a.1 Relabel Config, Artifacts, And Offline Gate

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add artifact/config tests**

Add tests that verify:

```python
assert manifest["slice_id"] == script.V07A1_SLICE_ID
assert manifest["heldout_21000_21049_accessed"] is False
assert manifest["proof_authority"] is False
assert manifest["v0_7a_1_relabel_config_sha256"]
assert "seat_depth_threshold_m" not in json.dumps(manifest["relabel_config"], sort_keys=True)
```

Add parent proof-chain validation tests:

```python
def test_v07a1_parent_proof_chain_requires_train_generation_gate_passed(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    parent_root = script._fixture_v07a1_parent_root(tmp_path)
    gate = script.read_json(parent_root / "train_generation_runtime_gate.json")
    gate["passed"] = False
    script.write_json(parent_root / "train_generation_runtime_gate.json", gate)

    with pytest.raises(ValueError, match="parent_train_generation_runtime_gate_not_passed"):
        script.validate_v07a1_parent_proof_chain(parent_root)


def test_v07a1_parent_proof_chain_requires_failed_v07a_evidence(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    parent_root = script._fixture_v07a1_parent_root(tmp_path)
    (parent_root / "v0_7a_behavior_state_phase_relabel" / "offline_train_fit_gate.json").unlink()

    with pytest.raises(ValueError, match="parent_v0_7a_fail_closed_evidence_missing"):
        script.validate_v07a1_parent_proof_chain(parent_root)
```

Add candidate-row provenance tests:

```python
def test_v07a1_excludes_unauthenticated_generated_candidate_rows_with_counts(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    rows = [
        {
            "env_native_success_mask": True,
            "lateral_error_m": 0.0,
            "insertion_depth_m": 0.024,
            "normalized_action": [0.0] * len(script.ACTION_SCHEMA),
            "trajectory_id": "runtime_trace_1",
            "step": 0,
        },
        {
            "lateral_error_m": 0.0,
            "insertion_depth_m": 0.0,
            "normalized_action": [0.0] * len(script.ACTION_SCHEMA),
            "trajectory_id": "generated_no_mask",
            "step": 0,
        },
    ]

    prepared, report = script.prepare_v07a1_candidate_train_rows(rows)

    assert len(prepared) == 1
    assert report["candidate_parent_rows_total"] == 2
    assert report["candidate_authenticated_rows_used"] == 1
    assert report["candidate_unauthenticated_rows_excluded"] == 1
    assert report["candidate_invalid_evidence_rows_failed_closed"] == 0
```

Add the three spec-required tests:

```python
def test_v07a1_synthetic_success_trace_yields_ten_hold_rows(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    rows = [
        {
            "env_native_success": i >= 5,
            "env_native_success_mask": i >= 5,
            "lateral_error_m": 0.0,
            "insertion_depth_m": 0.024,
            "phase": "SEAT" if i >= 5 else "APPROACH",
            "normalized_action": [0.0] * len(script.ACTION_SCHEMA),
            "trajectory_id": "synthetic_success_trace",
            "step": i,
        }
        for i in range(15)
    ]

    relabeled = [script.relabel_v07a1_training_row(row) for row in rows]

    assert sum(1 for row in relabeled if row["behavior_state_phase"] == "HOLD") == 10


def test_v07a1_candidate_and_baseline_report_share_same_rule_hash(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_v07a1_relabel_config(
        output_dir=tmp_path,
        parent_artifact_hashes={"parent_train_generation_runtime_gate_file_sha256": "abc"},
    )

    assert config["relabel_config_sha256"] == config["v0_7a_1_relabel_config_sha256"]
    assert config["behavior_phase_rule_version"] == script.V07A1_BEHAVIOR_PHASE_RULE_VERSION


def test_v07a1_rejects_old_v07a_relabel_config(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    old_config = {
        "schema_version": script.V07A_RELABEL_CONFIG_SCHEMA_VERSION,
        "slice_id": script.V07A_SLICE_ID,
        "seat_depth_threshold_m": 0.03,
        "relabel_config_sha256": "old",
    }

    with pytest.raises(ValueError, match="v0_7a_1_relabel_config_required"):
        script.validate_v07a1_relabel_config_contract(old_config)


def test_v07a1_rejects_stale_relabel_config_hash(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_v07a1_relabel_config(
        output_dir=tmp_path,
        parent_artifact_hashes={"parent_train_generation_runtime_gate_file_sha256": "abc"},
    )
    config["approach_lateral_gate_m"] = 999.0

    with pytest.raises(ValueError, match="v0_7a_1_relabel_config_hash_mismatch"):
        script.validate_v07a1_relabel_config_contract(config)


def test_v07a1_candidate_policy_artifact_declares_env_native_hold_rule(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    config = script.build_v07a1_relabel_config(
        output_dir=tmp_path,
        parent_artifact_hashes={"parent_train_generation_runtime_gate_file_sha256": "abc"},
    )

    artifact = script.build_v07a1_candidate_policy_artifact_payload(
        relabel_config=config,
        policy_artifact_sha256="policy",
        baseline_policy_artifact_available=False,
    )

    assert artifact["policy_slice"] == script.V07A1_POLICY_SLICE_ID
    assert artifact["behavior_phase_rule_version"] == script.V07A1_BEHAVIOR_PHASE_RULE_VERSION
    assert artifact["v0_7a_1_relabel_config_sha256"] == config["v0_7a_1_relabel_config_sha256"]
    assert artifact["relabel_config_sha256"] == config["relabel_config_sha256"]
    assert artifact["future_ab_ready"] is False
```

- [ ] **Step 2: Add config writer**

Implement `build_v07a1_relabel_config` with:

```python
config = {
    "schema_version": V07A1_RELABEL_CONFIG_SCHEMA_VERSION,
    "slice_id": V07A1_SLICE_ID,
    "parent_slice_id": V07A_SLICE_ID,
    "behavior_phase_schema": list(BEHAVIOR_STATE_PHASES),
    "behavior_phase_rule_version": V07A1_BEHAVIOR_PHASE_RULE_VERSION,
    "hold_authority": "env_native_success_mask",
    "assignment_rule_text": (
        "HOLD if env_native_success is true; DESCEND if not HOLD and "
        "lateral_error_m <= 0.001; ALIGN if not HOLD and lateral_error_m > 0.001"
    ),
    "geometry_values_are_report_only": True,
    "forbidden_config_keys": ["seat_depth_threshold_m"],
    "approach_lateral_gate_m": V07A_BEHAVIOR_PHASE_LATERAL_GATE_M,
    "invalid_row_handling": {
        "env_native_mask_missing": "fail_closed",
        "env_native_mask_conflict": "fail_closed",
        "env_native_mask_invalid": "fail_closed",
        "missing_required_metric": "fail_closed",
        "nonfinite_required_metric": "fail_closed",
        "negative_insertion_depth_m": "fail_closed",
        "runtime_trace_unreadable": "fail_closed",
        "runtime_trace_invalid_json": "fail_closed",
        "runtime_trace_invalid": "fail_closed",
        "runtime_trace_sha256_missing": "fail_closed",
        "runtime_trace_sha256_mismatch": "fail_closed",
        "runtime_trace_row_step_invalid": "fail_closed",
        "runtime_trace_step_invalid": "fail_closed",
        "runtime_trace_step_match_invalid": "fail_closed",
        "runtime_trace_mapping_ambiguous": "fail_closed",
    },
    "candidate_row_filter_handling": {
        "runtime_trace_missing": "exclude_with_manifest_count",
        "unauthenticated_generated_row": "exclude_with_manifest_count",
        "invalid_declared_runtime_evidence": "fail_closed",
    },
    "parent_proof_chain": {
        "required_files": list(V07A1_PARENT_PROOF_CHAIN_REQUIRED_FILES),
        "train_generation_runtime_gate_passed_required": True,
        "train_generation_generated_success_count_min": 20,
        "v0_7a_offline_fit_gate_required_status": "failed_closed",
        "v0_7a_expressibility_gate_required_status": "blocked_or_failed_closed",
        "selected_action_adapter_hash_required": True,
    },
    "baseline_semantics": {
        "candidate_gate_authority": True,
        "baseline_report_only": True,
        "missing_baseline_mask_handling": "report_only_env_native_mask_missing",
        "future_ab_blocked_without_baseline_policy": True,
    },
    "heldout_21000_21049_accessed": False,
    "proof_authority": False,
}
config_hash = _sha256_payload_excluding(
    config,
    "v0_7a_1_relabel_config_sha256",
    "relabel_config_sha256",
)
config["v0_7a_1_relabel_config_sha256"] = config_hash
config["relabel_config_sha256"] = config_hash
```

Both hash keys are required:

```text
v0_7a_1_relabel_config_sha256 = slice-specific artifact key
relabel_config_sha256         = compatibility key consumed by existing HDF5/policy writers
```

They must hold the same recomputed payload hash. Tests should fail if the two keys diverge or if any hashed payload field changes after the hash is written.

Add config contract validation:

```python
def validate_v07a1_relabel_config_contract(config: dict[str, Any]) -> None:
    if config.get("schema_version") != V07A1_RELABEL_CONFIG_SCHEMA_VERSION:
        raise ValueError("v0_7a_1_relabel_config_required")
    if config.get("slice_id") != V07A1_SLICE_ID:
        raise ValueError("v0_7a_1_relabel_config_required")
    if config.get("behavior_phase_rule_version") != V07A1_BEHAVIOR_PHASE_RULE_VERSION:
        raise ValueError("v0_7a_1_relabel_config_required")
    if "seat_depth_threshold_m" in config or "seat_depth_threshold_source" in config:
        raise ValueError("v0_7a_1_geometry_seat_threshold_forbidden")
    if config.get("relabel_config_sha256") != config.get("v0_7a_1_relabel_config_sha256"):
        raise ValueError("v0_7a_1_relabel_config_hash_mismatch")
    expected_hash = _sha256_payload_excluding(
        config,
        "v0_7a_1_relabel_config_sha256",
        "relabel_config_sha256",
    )
    if config.get("relabel_config_sha256") != expected_hash:
        raise ValueError("v0_7a_1_relabel_config_hash_mismatch")
```

- [ ] **Step 3: Add parent proof-chain validation and relabel flow**

Add `build_v07a1_behavior_phase_relabel_slice(output_dir: Path)`. It must:

1. Call `validate_v07a1_parent_proof_chain(parent_root)` before relabel.
2. Load parent HDF5 rows and the resolved `train_generation_runtime_gate.json`.
3. Build the runtime trace index from `train_generation_runtime_gate.generated_trace_paths`.
4. Enrich candidate parent rows with `runtime_trace_path` and `runtime_trace_sha256` by matching `trajectory_id`/scenario id to trace filename.
5. Split candidate parent rows into authenticated rows, unauthenticated generated rows, and invalid-evidence rows.
6. Exclude unauthenticated generated rows from the `v0_7a_1` candidate train view with manifest counts; fail closed on invalid-evidence rows.
7. Strictly hydrate authenticated candidate env-native masks from enriched row or trace evidence.
8. Relabel authenticated candidate rows into `behavior_state_phase`.
9. Attempt baseline report-only hydration separately; missing baseline masks are reported, not fabricated.
10. Evaluate candidate phase coverage over authenticated rows only.
11. If candidate authenticated rows are empty, candidate `HOLD=0`, or candidate mask hydration fails, write fail-closed `offline_train_fit_gate.json` and manifest.
12. If candidate coverage passes, write candidate train-view HDF5, candidate policy artifact, predictions, offline gate, and manifest.
   The candidate policy artifact contract must include:

```python
{
    "policy_slice": V07A1_POLICY_SLICE_ID,
    "slice_id": V07A1_SLICE_ID,
    "behavior_phase_rule_version": V07A1_BEHAVIOR_PHASE_RULE_VERSION,
    "behavior_state_phase_input": True,
    "phase_label_source": V07A1_BEHAVIOR_PHASE_LABEL_SOURCE,
    "v0_7a_1_relabel_config_sha256": config["v0_7a_1_relabel_config_sha256"],
    "relabel_config_sha256": config["relabel_config_sha256"],
    "phase_e_candidate_only_diagnostic": True,
    "baseline_policy_artifact_available": baseline_policy_artifact_available,
    "future_ab_ready": False,
    "future_ab_ready_source": "offline_train_fit_gate",
    "proof_authority": False,
    "heldout_21000_21049_accessed": False,
}
```

`future_ab_ready` authority belongs to `offline_train_fit_gate.json` after candidate fit and optional baseline policy availability are known. The policy artifact must not independently grant A/B readiness.

13. Write baseline train-view/policy artifact only if valid baseline mask evidence exists. Otherwise set:

```python
"baseline_report_only_status": "report_only_env_native_mask_missing",
"baseline_policy_artifact_available": False,
"future_calibration_blocked_reason": "missing_v0_7a_1_baseline_policy_artifact",
```

This keeps Phase E candidate expressibility possible while preventing later A/B progression without a valid baseline. The manifest must make clear that excluded generated candidate rows were not used for this diagnostic train view.

The parent validator must:

```python
def validate_v07a1_parent_proof_chain(parent_root: Path) -> dict[str, Any]:
    ...
```

Required checks:

```text
all V07A1_PARENT_PROOF_CHAIN_REQUIRED_FILES exist
train_generation_runtime_gate.passed == true
train_generation_runtime_gate.generated_success_count >= 20
train_generation_runtime_gate.generated_trace_paths non-empty
repair_probe_gate.passed == true
selected_action_adapter.json file and payload hashes are recorded
v0_7a offline_train_fit_gate exists and is failed-closed with failure_reason=required_phase_missing
v0_7a expressibility_sanity_gate exists and did not run Isaac because offline gate was missing/passed=false
candidate_curated_train.hdf5 and baseline_uncurated_train.hdf5 hashes are recorded
curation_manifest.json hash is recorded
heldout_21000_21049_accessed == false in all checked parent gates
```

The returned verdict must be embedded into `v0_7a_1_relabel_manifest.json` as `parent_proof_chain_verdict`.

- [ ] **Step 4: Add per-trace HOLD count reporting**

In manifest include:

```python
"candidate_per_trace_hold_counts": {
    trace_id: hold_count,
    ...
},
"candidate_min_hold_rows_per_success_trace": min_count,
"candidate_success_trace_count": success_trace_count,
```

Use `runtime_trace_path` or `trajectory_id` as the stable trace key.

- [ ] **Step 5: Preserve baseline report-only behavior**

Use the same relabel rule for baseline rows only where valid mask evidence exists. If baseline lacks mask evidence or phase coverage, keep baseline metrics report-only with null metric fields, matching the v0.7a baseline behavior. Candidate missing phase remains fail-closed.

Add explicit tests:

```python
def test_v07a1_missing_baseline_mask_is_report_only_not_fabricated() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    rows, report = script.prepare_v07a1_baseline_report_rows(
        [{"lateral_error_m": 0.0, "insertion_depth_m": 0.0}]
    )

    assert rows == []
    assert report["baseline_report_only"] is True
    assert report["baseline_report_only_status"] == "report_only_env_native_mask_missing"
    assert report["baseline_env_native_mask_missing_count"] == 1
```

- [ ] **Step 6: Define v0.7a.1 offline fit gate semantics**

Add a v0.7a.1-specific gate helper instead of reusing `derive_v07a_offline_train_fit_gate` blindly. The existing v0.7a helper expects both baseline and candidate policy artifacts; v0.7a.1 must allow candidate-only Phase E diagnostics while still blocking future calibration/A-B when baseline evidence is missing.

```python
def derive_v07a1_offline_train_fit_gate(
    *,
    candidate_rows: list[dict[str, Any]],
    candidate_predictions: list[dict[str, Any]],
    candidate_policy_artifact_sha256: str,
    relabel_config_sha256: str,
    baseline_rows: list[dict[str, Any]] | None = None,
    baseline_predictions: list[dict[str, Any]] | None = None,
    baseline_policy_artifact_sha256: str | None = None,
    baseline_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ...
```

Required semantics:

```python
{
    "schema_version": V07A1_OFFLINE_FIT_GATE_SCHEMA_VERSION,
    "policy_slice": V07A1_POLICY_SLICE_ID,
    "behavior_phase_rule_version": V07A1_BEHAVIOR_PHASE_RULE_VERSION,
    "relabel_config_sha256": relabel_config_sha256,
    "v0_7a_1_relabel_config_sha256": relabel_config_sha256,
    "candidate_gate_passed": candidate_fit_gate_passed,
    "passed": candidate_fit_gate_passed,
    "phase_e_candidate_expressibility_unblocked": candidate_fit_gate_passed,
    "baseline_policy_artifact_available": bool(baseline_policy_artifact_sha256),
    "baseline_report_only": not bool(baseline_policy_artifact_sha256),
    "baseline_same_metrics_report_only": {
        "metric_status": "report_only_baseline_policy_unavailable",
        "xy_mae_m": None,
        "z_mae_m": None,
        "phase_coverage": None,
    } if not baseline_policy_artifact_sha256 else computed_baseline_metrics,
    "future_ab_ready": bool(baseline_policy_artifact_sha256) and candidate_fit_gate_passed,
    "future_calibration_blocked_reason": (
        None
        if baseline_policy_artifact_sha256 and candidate_fit_gate_passed
        else "candidate_offline_fit_failed"
        if not candidate_fit_gate_passed
        else "missing_v0_7a_1_baseline_policy_artifact"
    ),
    "heldout_21000_21049_accessed": False,
    "proof_authority": False,
}
```

`offline_train_fit_gate.passed` means candidate offline fit passed for Phase E expressibility only. It must not mean MVP-2 A/B readiness. A missing baseline artifact must not force `passed=false` by itself; it must force `future_ab_ready=false` and set `future_calibration_blocked_reason="missing_v0_7a_1_baseline_policy_artifact"` only when candidate fit passed. If candidate fit fails, the blocked reason must be `candidate_offline_fit_failed` or a more specific candidate failure reason.

Add tests:

```python
def test_v07a1_offline_gate_allows_candidate_phase_e_when_baseline_policy_missing() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    gate = script.derive_v07a1_offline_train_fit_gate(
        candidate_rows=script._fixture_v07a1_candidate_rows_with_all_phases(),
        candidate_predictions=script._fixture_v07a1_candidate_predictions_with_low_error(),
        candidate_policy_artifact_sha256="candidate-sha",
        relabel_config_sha256="config-sha",
        baseline_rows=[],
        baseline_predictions=[],
        baseline_policy_artifact_sha256=None,
        baseline_report={"baseline_report_only_status": "report_only_env_native_mask_missing"},
    )

    assert gate["passed"] is True
    assert gate["candidate_gate_passed"] is True
    assert gate["phase_e_candidate_expressibility_unblocked"] is True
    assert gate["future_ab_ready"] is False
    assert gate["future_calibration_blocked_reason"] == "missing_v0_7a_1_baseline_policy_artifact"


def test_v07a1_offline_gate_fails_candidate_without_hold_phase() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    gate = script.derive_v07a1_offline_train_fit_gate(
        candidate_rows=script._fixture_v07a1_candidate_rows_without_hold(),
        candidate_predictions=script._fixture_v07a1_candidate_predictions_with_low_error(),
        candidate_policy_artifact_sha256="candidate-sha",
        relabel_config_sha256="config-sha",
    )

    assert gate["passed"] is False
    assert gate["candidate_gate_passed"] is False
    assert gate["phase_e_candidate_expressibility_unblocked"] is False
    assert gate["future_calibration_blocked_reason"] == "candidate_offline_fit_failed"
```

- [ ] **Step 7: Run focused tests**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  -k "v07a1 or v0_7a_1 or env_native_hold" -q
```

Expected: pass.

## Task 5: Add CLI Policy Slice Guard And Expressibility Pre-Gate

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add parser choice and guard tests**

```python
def test_v07a1_policy_slice_rejects_full_run() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="policy-slice v0_7a_1 is only valid"):
        script.main([
            "--scenario-profile", "v0_6",
            "--policy-slice", "v0_7a_1",
            "--output-dir", str(Path("/tmp/rdf-v07a1-full-run-test")),
        ])
```

- [ ] **Step 2: Update CLI choices**

```python
parser.add_argument("--policy-slice", choices=("v0_6", "v0_7a", "v0_7a_1"), default="v0_6")
```

Add guard:

```python
if args.policy_slice in {"v0_7a", "v0_7a_1"} and not (
    args.offline_relabel_only or args.expressibility_sanity_only
):
    raise ValueError(
        f"--policy-slice {args.policy_slice} is only valid with "
        "--offline-relabel-only or --expressibility-sanity-only"
    )
```

- [ ] **Step 3: Wire offline relabel mode**

In `--offline-relabel-only`, branch:

```python
if args.policy_slice == "v0_7a":
    manifest = build_v07a_behavior_phase_relabel_slice(output_dir=args.output_dir)
elif args.policy_slice == "v0_7a_1":
    manifest = build_v07a1_behavior_phase_relabel_slice(output_dir=args.output_dir)
else:
    raise ValueError("--offline-relabel-only requires --policy-slice v0_7a or v0_7a_1")
```

- [ ] **Step 4: Wire expressibility guard**

Add `run_v07a1_expressibility_sanity_if_ready` or generalize the existing `run_v07a_expressibility_sanity_if_ready` to accept slice metadata. It must refuse Isaac runtime if:

```text
offline_train_fit_gate.json missing
offline_train_fit_gate.passed != true
offline_train_fit_gate.candidate_gate_passed != true
offline_train_fit_gate.phase_e_candidate_expressibility_unblocked != true
candidate_policy_artifact_v0_7a_1.json missing
candidate_policy_artifact_v0_7a_1.behavior_phase_rule_version != env_native_hold_v0_7a_1
```

Do not require `offline_train_fit_gate.future_ab_ready=true` for Phase E. `future_ab_ready=false` is expected when baseline artifacts are unavailable; it blocks calibration/A-B, not candidate-only expressibility diagnosis.

The fail-closed output path must be:

```text
v0_7a_1_behavior_state_phase_relabel/expressibility_sanity_gate_v0_7a_1.json
```

- [ ] **Step 5: Run guard tests**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  -k "v07a1 and (policy_slice or expressibility)" -q
```

Expected: pass.

## Task 6: Execute Offline Relabel Validation

**Files:**
- Runtime artifacts under `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7a_1_behavior_state_phase_relabel/`

- [ ] **Step 1: Run focused tests before artifact generation**

```bash
uv run pytest \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  -k "v07a1 or v0_7a_1 or env_native_hold" -q
```

Expected: pass.

- [ ] **Step 2: Run offline relabel only**

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 --policy-slice v0_7a_1 \
  --offline-relabel-only --pretty
```

Expected acceptable outcomes:

```text
Outcome A:
  exit 0
  offline_train_fit_gate.passed=true
  offline_train_fit_gate.candidate_gate_passed=true
  offline_train_fit_gate.phase_e_candidate_expressibility_unblocked=true
  offline_train_fit_gate.future_ab_ready=false is allowed only when baseline is report-only
  candidate_phase_row_counts.HOLD>0
  heldout_21000_21049_accessed=false

Outcome B:
  exit 0 or expected non-zero only if explicitly designed
  offline_train_fit_gate.passed=false
  failure_reason is one of:
    env_native_mask_missing
    required_phase_missing
    offline_train_fit_failed
  heldout_21000_21049_accessed=false
```

Do not proceed to Isaac Phase E unless Outcome A occurs.

- [ ] **Step 3: Inspect artifacts**

Read and record:

```bash
python - <<'PY'
import json
from pathlib import Path
root = Path("storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7a_1_behavior_state_phase_relabel")
for name in ["v0_7a_1_relabel_manifest.json", "offline_train_fit_gate.json"]:
    p = root / name
    data = json.loads(p.read_text())
    print(name)
    for key in [
        "passed",
        "failure_reason",
        "heldout_21000_21049_accessed",
        "candidate_phase_row_counts",
        "candidate_min_hold_rows_per_success_trace",
    ]:
        if key in data:
            print(" ", key, data[key])
PY
```

Expected: artifact evidence is explicit and held-out remains sealed.

## Task 7: Run Phase E Only If Offline Gate Passes

**Files:**
- Runtime artifacts under `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7a_1_behavior_state_phase_relabel/`

- [ ] **Step 1: Check offline gate manually**

Do not run this task unless `offline_train_fit_gate.json` has `passed=true`.

- [ ] **Step 2: Run Isaac expressibility sanity**

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 --policy-slice v0_7a_1 \
  --expressibility-sanity-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 --device cuda:0 --pretty
```

Expected acceptable outcomes:

```text
Pass:
  expressibility_sanity_gate_v0_7a_1.passed=true
  success_count>=2
  required_success_count=2
  heldout_21000_21049_accessed=false

Fail:
  expressibility_sanity_gate_v0_7a_1.passed=false
  success_count<2
  heldout_21000_21049_accessed=false
  next step is v0_7b residual servo BC plan, not threshold relaxation
```

## Task 8: Documentation And Final Verification

**Files:**
- Modify: `docs/developer/debugging_guide.md`
- Modify: `docs/developer/worklog.md`
- Modify: `Handoff.md`

- [ ] **Step 1: Update debugging guide**

Add the authority invariant:

```markdown
### MVP-2E env-native seating authority

For MVP-2E v0.7a.1 and later, seated/HOLD behavior must be derived from
`env_native_success` / `env_native_success_mask` rather than geometry depth
thresholds. `insertion_depth_m`, `lateral_error_m`, and orientation metrics remain
diagnostic task-state features, not seating authority.
```

- [ ] **Step 2: Update worklog**

Record:

```text
- v0_7a_1 plan/spec path
- changed files
- offline relabel result
- Phase E result if run
- heldout/calibration status
- whether next branch is Phase F calibration or v0_7b fallback
```

- [ ] **Step 3: Update Handoff**

Record the compact next-session status:

```text
MVP-2 remains not Closed unless Phase F/G/H later pass.
v0_7a_1 offline gate status: <result>
Phase E status: <result or not run>
Held-out 21000-21049: sealed
Next valid step: <Phase F calibration presignal | v0_7b residual servo BC plan>
```

- [ ] **Step 4: Run verification suite**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  -k "v07a or v0_7a or v07a1 or v0_7a_1 or behavior_state_phase or env_native_hold" -q
```

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q
```

```bash
uv run python -m compileall -q scripts apps/api/app apps/api/tests
```

```bash
uvx ruff check scripts/run_mvp2b_isaac_proof_evaluator.py \
  scripts/run_mvp2c_isaac_training_calibration.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
```

```bash
git diff --check
```

Expected: all pass, or failures are documented with exact blocker and stop condition.

## Stop Conditions

Stop and report if:

- Parent HDF5 rows cannot be enriched from `train_generation_runtime_gate.generated_trace_paths` or hydrated from hash-checked runtime traces.
- `v0_7a_1` relabel still yields candidate `HOLD=0`.
- Offline fit gate fails on MAE/sign metrics.
- Phase E expressibility is below 2/5.
- Any path requires opening held-out `21000-21049`, running calibration before Phase E, changing env-native authority, relaxing offline fit thresholds, or mutating `v0_7a` artifacts.

## Acceptance Criteria

- `v0_7a` behavior and artifacts remain backward-compatible.
- `v0_7a_1` has its own config, manifest, policy artifacts, HDF5 train views, and gates.
- `HOLD` is derived from `env_native_success`/`env_native_success_mask`, never from `seat_depth_threshold_m`.
- Missing or unauthenticated mask evidence fails closed.
- Runtime prediction and offline relabel use identical behavior phase rules.
- Candidate offline gate is honestly evaluated with all three behavior phases present or fails closed with reason.
- Held-out `21000-21049` remains unopened.
- Calibration remains unrun.
- Docs and Handoff are updated.

## Available Agent Types / Staffing Guidance

- `executor` (medium): implement code/tasks 1-5 in a single-owner lane.
- `test-engineer` (medium): strengthen focused pytest coverage and inspect gate artifacts.
- `verifier` (high): run final verification and check claim boundaries.
- `architect` (high): review any deviation from env-native authority invariant.
- `critic` (high): review final plan or patch for proof-integrity regressions.

Recommended follow-up: `$ultragoal` for durable sequential implementation. Use `$team` only if splitting code/test/docs lanes; keep write scopes disjoint. `$ralph` is a fallback only if a single-owner persistence loop is explicitly desired.

## Team Verification Path

If implemented via `$team`, use:

1. Executor lane: scripts and CLI.
2. Test-engineer lane: tests only.
3. Writer lane: docs/Handoff only.
4. Verifier lane: no edits, final checks and artifact claim-boundary review.

No team lane may run held-out or calibration unless Phase E has passed and a later plan explicitly authorizes it.
