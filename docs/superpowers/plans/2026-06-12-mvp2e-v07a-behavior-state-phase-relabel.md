# MVP-2E v0.7a Behavior-State Phase Relabel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 `v0_6` actual Isaac train-generation evidence를 보존한 채 `behavior_state_phase` 기반 policy training view를 만들고, offline train-fit gate를 통과한 경우에만 Isaac expressibility sanity를 허용한다.

**Architecture:** `v0_7a`는 parent `v0_6` artifact를 덮어쓰지 않는 child slice다. `phase`는 audit field로 보존하고 `behavior_state_phase`를 새 model input으로 사용한다. Baseline/candidate는 동일 relabel config, feature schema, trainer, hyperparameters, selected action adapter를 공유하며, offline fit gate가 expensive Isaac 실행 앞단을 막는다.

**Tech Stack:** Python 3.11+, NumPy, h5py, pytest, IsaacLab lazy runtime, existing `scripts/run_mvp2b_isaac_proof_evaluator.py`, `scripts/run_mvp2c_isaac_training_calibration.py`.

---

## File Structure

- Modify `scripts/run_mvp2b_isaac_proof_evaluator.py`
  - Add `BEHAVIOR_STATE_PHASES`, `FEATURE_SCHEMA_V07A`, and schema-aware feature construction.
  - Keep existing `FEATURE_SCHEMA` and `PHASES` backward-compatible.
  - Make policy prediction select feature schema from policy artifact metadata.
- Modify `scripts/run_mvp2c_isaac_training_calibration.py`
  - Add v0.7a parent hash validation.
  - Add relabel config writer and immutable config hash.
  - Add deterministic relabeler preserving `phase`.
  - Add v0.7a child HDF5 / policy artifact writers.
  - Add offline train-fit gate and expressibility pre-gate.
  - Add `--policy-slice v0_7a` and `--offline-relabel-only`.
- Modify `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
  - Add schema-aware feature and prediction tests.
- Modify `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
  - Add v0.7a relabel, parent hash, HDF5, policy artifact, offline fit, and expressibility gate tests.
- Modify docs:
  - `docs/developer/worklog.md`
  - `docs/developer/debugging_guide.md`
  - `Handoff.md`

## Artifact Layout

Write all v0.7a child artifacts under:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7a_behavior_state_phase_relabel/
```

Required outputs:

```text
v0_7a_relabel_config.json
v0_7a_relabel_manifest.json
baseline_uncurated_train_v0_7a.hdf5
candidate_curated_train_v0_7a.hdf5
baseline_policy_artifact_v0_7a.json
candidate_policy_artifact_v0_7a.json
offline_train_fit_gate.json
expressibility_sanity_gate_v0_7a.json
```

## Architect Review Corrections Required Before Implementation

The first Architect review returned `CHANGES_REQUESTED`. Implementation must include
these corrections before considering this plan executable:

- Runtime prediction must derive `behavior_state_phase` from the same frozen rule
  when a v0.7a policy artifact is evaluated against Isaac metric rows that only
  contain `lateral_error_m` and `insertion_depth_m`.
- `V07A_PARENT_ARTIFACT_HASHES` must be defined and must validate the full parent
  proof chain: `repair_probe_gate.json`, `train_generation_runtime_gate.json`,
  `expressibility_sanity_gate.json`, both parent HDF5 files, both policy file
  hashes, both policy payload hashes, and `curation_manifest.json`.
- `v0_7a_relabel_config.json` must serialize the full pre-registered contract:
  invalid row handling, reset-tail handling or parent-cleanliness validation,
  baseline noise mix, offline fit metric definitions, thresholds, and aggregation.
- `offline_train_fit_gate.json` must include baseline report-only metrics via
  `baseline_same_metrics_report_only`.
- Relabel must fail closed if parent traces show reset-tail contamination that was
  not already excluded before parent HDF5 creation.

## Task 1: Add RED Tests For Behavior Phase Contract

**Files:**
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
- Modify: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`

- [ ] **Step 1: Add phase assignment and relabel RED tests**

Add to `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`:

```python
def test_v07a_behavior_state_phase_assignment_uses_lateral_gate_and_depth() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    assert script.derive_v07a_behavior_state_phase(
        {"lateral_error_m": 0.0011, "insertion_depth_m": 0.040}
    ) == "ALIGN"
    assert script.derive_v07a_behavior_state_phase(
        {"lateral_error_m": 0.001, "insertion_depth_m": 0.029}
    ) == "DESCEND"
    assert script.derive_v07a_behavior_state_phase(
        {"lateral_error_m": 0.001, "insertion_depth_m": 0.03}
    ) == "HOLD"


def test_v07a_relabel_preserves_original_depth_phase() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    row = script.relabel_v07a_training_row(
        {
            "phase": "APPROACH",
            "lateral_error_m": 0.0008,
            "insertion_depth_m": 0.012,
            "normalized_action": [0.0] * len(script.ACTION_SCHEMA),
        }
    )

    assert row["phase"] == "APPROACH"
    assert row["original_depth_phase"] == "APPROACH"
    assert row["behavior_state_phase"] == "DESCEND"
    assert row["phase_label_source"] == "frozen_v0_7a_behavior_state_rule"


def test_v07a_relabel_rejects_missing_required_metrics() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="row_missing_required_metric"):
        script.relabel_v07a_training_row({"phase": "APPROACH", "insertion_depth_m": 0.0})

    with pytest.raises(ValueError, match="relabel_config_invalid"):
        script.relabel_v07a_training_row(
            {"phase": "APPROACH", "lateral_error_m": float("nan"), "insertion_depth_m": 0.0}
        )
```

- [ ] **Step 2: Add schema-aware feature RED test**

Add to `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`:

```python
def test_v07a_feature_schema_uses_behavior_state_phase_without_mutating_phase() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    feature, _ = script.featurize_step(
        {
            "phase": "APPROACH",
            "behavior_state_phase": "DESCEND",
            "insertion_depth_m": 0.012,
            "relative_x_m": 0.0,
            "relative_y_m": 0.0,
            "lateral_error_m": 0.0008,
            "orientation_error_deg": 0.0,
            "normalized_action": [0.0] * len(script.ACTION_SCHEMA),
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        feature_schema=script.FEATURE_SCHEMA_V07A,
    )

    assert len(feature) == len(script.FEATURE_SCHEMA_V07A)
    assert feature[0:3].tolist() == [0.0, 1.0, 0.0]
```

- [ ] **Step 3: Add runtime prediction RED test**

Add to `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`:

```python
def test_v07a_runtime_prediction_derives_behavior_state_phase_from_metric_row() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    weights = [[0.0] * len(script.ACTION_SCHEMA) for _ in script.FEATURE_SCHEMA_V07A]
    weights[1][2] = -0.16
    policy = {
        "policy_id": "candidate_curated_mvp2e_v07a_behavior_phase_numpy_bc",
        "policy_class": script.POLICY_CLASS,
        "feature_schema": list(script.FEATURE_SCHEMA_V07A),
        "phase_schema": list(script.BEHAVIOR_STATE_PHASES),
        "behavior_state_phase_input": True,
        "selected_action_adapter_id": "isaac_delta_pose_direct_v0",
        "selected_action_adapter_config": {"adapter_mode": "global_action_scale"},
        "weights": weights,
        "bias": [0.0] * len(script.ACTION_SCHEMA),
    }

    action, diagnostics = script._predict_policy_action_with_diagnostics(
        policy,
        metric_row={
            "phase": "APPROACH",
            "lateral_error_m": 0.0008,
            "insertion_depth_m": 0.012,
            "relative_x_m": 0.0,
            "relative_y_m": 0.0,
            "orientation_error_deg": 0.0,
        },
        previous_action=[0.0] * len(script.ACTION_SCHEMA),
        action_scale=1.0,
    )

    assert diagnostics["behavior_state_phase"] == "DESCEND"
    assert diagnostics["behavior_state_phase_source"] == "derived_v0_7a_runtime_rule"
    assert action[2] == -0.16
```

- [ ] **Step 4: Run RED tests**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  -k "v07a or v0_7a or behavior_state_phase" -q
```

Expected: FAIL because v0.7a helpers, runtime derivation, and `FEATURE_SCHEMA_V07A`
do not exist.

## Task 2: Add Schema-Aware Feature Construction

**Files:**
- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`
- Test: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`

- [ ] **Step 1: Add v0.7a constants**

Add near existing `PHASES` / `FEATURE_SCHEMA` constants:

```python
BEHAVIOR_STATE_PHASES = ("ALIGN", "DESCEND", "HOLD")
FEATURE_SCHEMA_V07A = [
    "behavior_phase_ALIGN",
    "behavior_phase_DESCEND",
    "behavior_phase_HOLD",
    "insertion_depth_m",
    "relative_x_m",
    "relative_y_m",
    "lateral_error_m",
    "orientation_error_deg",
    "previous_action_dx",
    "previous_action_dy",
    "previous_action_dz",
    "previous_action_rx",
    "previous_action_ry",
    "previous_action_rz",
    "previous_action_gripper",
]
FEATURE_SCHEMA_V07A_VERSION = "rdf_mvp2e_v07a_behavior_phase_feature_schema_v0.1.0"
```

- [ ] **Step 2: Replace `featurize_step` with schema-aware version**

Keep default behavior unchanged:

```python
def _phase_vector_for_schema(step: dict[str, Any], feature_schema: Sequence[str]) -> list[float]:
    if list(feature_schema[:3]) == ["behavior_phase_ALIGN", "behavior_phase_DESCEND", "behavior_phase_HOLD"]:
        behavior_phase = str(step.get("behavior_state_phase") or "").upper()
        return [1.0 if behavior_phase == item else 0.0 for item in BEHAVIOR_STATE_PHASES]
    phase = str(step.get("phase") or "").upper()
    return [1.0 if phase == item else 0.0 for item in PHASES]


def featurize_step(
    step: dict[str, Any],
    *,
    previous_action: list[float],
    feature_schema: Sequence[str] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    schema = list(feature_schema or FEATURE_SCHEMA)
    phase_width = 3 if schema == FEATURE_SCHEMA_V07A else 4
    phase_vector = _phase_vector_for_schema(step, schema)
    if len(phase_vector) != phase_width:
        raise ValueError("feature_schema_phase_width_mismatch")
    previous = [float(value) for value in previous_action[: len(ACTION_SCHEMA)]]
    if len(previous) < len(ACTION_SCHEMA):
        previous.extend([0.0] * (len(ACTION_SCHEMA) - len(previous)))
    feature_values = phase_vector + [
        float(step.get("insertion_depth_m", 0.0)),
        float(step.get("relative_x_m", 0.0)),
        float(step.get("relative_y_m", 0.0)),
        float(step.get("lateral_error_m", 0.0)),
        float(step.get("orientation_error_deg", 0.0)),
    ] + previous
    if len(feature_values) != len(schema):
        raise ValueError("feature_schema_length_mismatch")
    target = [float(value) for value in step.get("normalized_action", [0.0] * len(ACTION_SCHEMA))]
    return np.asarray(feature_values, dtype=np.float64), np.asarray(target, dtype=np.float64)
```

- [ ] **Step 3: Update `_features_targets` and `fit_phase_conditioned_bc_policy`**

```python
def _features_targets(
    rows: list[dict[str, Any]],
    *,
    feature_schema: Sequence[str] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    features: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    previous_by_trajectory: dict[str, list[float]] = {}
    for row in rows:
        trajectory_id = str(row.get("trajectory_id"))
        previous = previous_by_trajectory.get(trajectory_id, [0.0] * len(ACTION_SCHEMA))
        feature, target = featurize_step(row, previous_action=previous, feature_schema=feature_schema)
        features.append(feature)
        targets.append(target)
        previous_by_trajectory[trajectory_id] = [float(value) for value in row["normalized_action"]]
    if not features:
        raise ValueError("cannot train MVP-2B policy without rows")
    return np.vstack(features), np.vstack(targets)


def fit_phase_conditioned_bc_policy(
    *,
    policy_id: str,
    train_rows: list[dict[str, Any]],
    hyperparameters: dict[str, Any],
    feature_schema: Sequence[str] | None = None,
    phase_schema: Sequence[str] | None = None,
) -> dict[str, Any]:
    schema = list(feature_schema or FEATURE_SCHEMA)
    phases = list(phase_schema or PHASES)
    features, targets = _features_targets(train_rows, feature_schema=schema)
    ridge_lambda = float(hyperparameters.get("ridge_lambda", 1e-3))
    augmented = np.hstack([features, np.ones((features.shape[0], 1), dtype=np.float64)])
    lhs = augmented.T @ augmented
    lhs += ridge_lambda * np.eye(lhs.shape[0], dtype=np.float64)
    rhs = augmented.T @ targets
    weights = np.linalg.solve(lhs, rhs)
    payload = {
        "policy_id": policy_id,
        "policy_class": POLICY_CLASS,
        "trainer": TRAINER,
        "feature_schema": schema,
        "phase_schema": phases,
        "action_schema": list(ACTION_SCHEMA),
        "hyperparameters": dict(hyperparameters),
        "train_sample_count": int(features.shape[0]),
        "weights": weights[:-1].round(10).tolist(),
        "bias": weights[-1].round(10).tolist(),
    }
    payload["policy_artifact_sha256"] = _sha256_payload(payload)
    return payload
```

- [ ] **Step 4: Update policy prediction to use artifact schema**

In `_predict_policy_action`, pass `feature_schema=policy_artifact.get("feature_schema")` to `featurize_step`.
Preserve existing behavior when the field is absent.

- [ ] **Step 5: Run GREEN tests**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  -k "v07a or feature_schema or policy_features" -q
```

Expected: PASS.

## Task 3: Add v0.7a Config, Parent Hash Validation, And Relabeler

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Test: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Import new feature constants**

Extend the import from `run_mvp2b_isaac_proof_evaluator`:

```python
    BEHAVIOR_STATE_PHASES,
    FEATURE_SCHEMA_V07A,
    FEATURE_SCHEMA_V07A_VERSION,
```

- [ ] **Step 2: Add v0.7a constants**

```python
V07A_SLICE_ID = "v0_7a"
V07A_CHILD_DIR_NAME = "v0_7a_behavior_state_phase_relabel"
V07A_RELABEL_CONFIG_SCHEMA_VERSION = "rdf_mvp2e_v07a_behavior_phase_relabel_config_v0.1.0"
V07A_RELABEL_MANIFEST_SCHEMA_VERSION = "rdf_mvp2e_v07a_behavior_phase_relabel_manifest_v0.1.0"
V07A_HDF5_SCHEMA_VERSION = "rdf_mvp2e_v07a_behavior_phase_train_view_hdf5_v0.1.0"
V07A_POLICY_ARTIFACT_SCHEMA_VERSION = "rdf_mvp2e_v07a_behavior_phase_policy_artifact_v0.1.0"
V07A_OFFLINE_FIT_GATE_SCHEMA_VERSION = "rdf_mvp2e_v07a_offline_train_fit_gate_v0.1.0"
V07A_APPROACH_LATERAL_GATE_M = 0.001
V07A_SEAT_DEPTH_THRESHOLD_M = 0.03
V07A_ORIENTATION_GATE_RAD = 0.25
V07A_PHASE_LABEL_SOURCE = "frozen_v0_7a_behavior_state_rule"
V07A_OFFLINE_FIT_THRESHOLDS = {
    "candidate_xy_mae_max": 0.01,
    "candidate_z_mae_max": 0.02,
    "candidate_action_rmse_max": 0.03,
    "candidate_align_predicted_negative_z_rate": 0.10,
    "candidate_descend_predicted_negative_z_rate": 0.80,
    "candidate_descend_z_sign_agreement": 0.90,
    "candidate_hold_abs_z_mean": 0.04,
}
```

- [ ] **Step 3: Add parent hash validator**

```python
def validate_v07a_parent_artifact_hashes(
    artifact_paths: dict[str, Path],
    expected_hashes: dict[str, str],
) -> dict[str, Any]:
    mismatched: list[str] = []
    observed: dict[str, str | None] = {}
    for name, path in artifact_paths.items():
        file_key = f"parent_{name}_file_sha256"
        payload_key = f"parent_{name}_payload_sha256"
        if not path.exists():
            observed[file_key] = None
            mismatched.append(file_key)
            continue
        observed[file_key] = _sha256_file(path)
        if expected_hashes.get(file_key) and observed[file_key] != expected_hashes[file_key]:
            mismatched.append(file_key)
        if payload_key in expected_hashes:
            payload = read_json(path)
            observed[payload_key] = str(payload.get("policy_artifact_sha256") or "")
            if observed[payload_key] != expected_hashes[payload_key]:
                mismatched.append(payload_key)
    return {
        "passed": not mismatched,
        "mismatched_hashes": sorted(set(mismatched)),
        "observed_hashes": observed,
    }
```

- [ ] **Step 4: Add relabel config builder**

```python
def build_v07a_relabel_config(
    *,
    output_dir: Path,
    parent_artifact_hashes: dict[str, str],
) -> dict[str, Any]:
    config = {
        "schema_version": V07A_RELABEL_CONFIG_SCHEMA_VERSION,
        "slice_id": V07A_SLICE_ID,
        "scenario_profile": "v0_6",
        "parent_artifact_hashes": dict(parent_artifact_hashes),
        "behavior_phase_schema": list(BEHAVIOR_STATE_PHASES),
        "approach_lateral_gate_m": V07A_APPROACH_LATERAL_GATE_M,
        "approach_lateral_gate_source": "parent_v0_6i_controller_repair_config.approach_lateral_gate_m",
        "seat_depth_threshold_m": V07A_SEAT_DEPTH_THRESHOLD_M,
        "seat_depth_threshold_source": "SUCCESS_METRIC.insertion_depth_m_min",
        "orientation_gate_rad": V07A_ORIENTATION_GATE_RAD,
        "orientation_gate_source": "parent_v0_6i_controller_repair_config.align_orientation_gate_rad",
        "assignment_rule_text": (
            "ALIGN if lateral_error_m > 0.001; DESCEND if lateral_error_m <= 0.001 "
            "and insertion_depth_m < 0.03; HOLD if lateral_error_m <= 0.001 "
            "and insertion_depth_m >= 0.03"
        ),
        "equality_handling": {
            "lateral_error_m == approach_lateral_gate_m": "DESCEND_or_HOLD_branch",
            "insertion_depth_m == seat_depth_threshold_m": "HOLD_branch",
        },
        "feature_schema_v0_7a": list(FEATURE_SCHEMA_V07A),
        "feature_schema_version": FEATURE_SCHEMA_V07A_VERSION,
        "trainer": TRAINER,
        "policy_class": POLICY_CLASS,
        "ridge_lambda": 1e-3,
        "offline_fit_thresholds": dict(V07A_OFFLINE_FIT_THRESHOLDS),
        "heldout_21000_21049_accessed": False,
        "proof_authority": False,
    }
    config["relabel_config_sha256"] = _sha256_payload_excluding(config, "relabel_config_sha256")
    write_json(output_dir / "v0_7a_relabel_config.json", config)
    return config
```

- [ ] **Step 5: Add relabel helpers**

```python
def _required_float_metric(row: dict[str, Any], key: str) -> float:
    if key not in row:
        raise ValueError(f"row_missing_required_metric:{key}")
    value = float(row[key])
    if not math.isfinite(value):
        raise ValueError(f"relabel_config_invalid:{key}")
    return value


def derive_v07a_behavior_state_phase(row: dict[str, Any]) -> str:
    lateral = _required_float_metric(row, "lateral_error_m")
    depth = _required_float_metric(row, "insertion_depth_m")
    if depth < 0.0:
        raise ValueError("relabel_config_invalid:negative_insertion_depth_m")
    if lateral > V07A_APPROACH_LATERAL_GATE_M:
        return "ALIGN"
    if depth < V07A_SEAT_DEPTH_THRESHOLD_M:
        return "DESCEND"
    return "HOLD"


def relabel_v07a_training_row(row: dict[str, Any]) -> dict[str, Any]:
    phase = str(row.get("phase") or "")
    return {
        **row,
        "phase": phase,
        "original_depth_phase": phase,
        "behavior_state_phase": derive_v07a_behavior_state_phase(row),
        "phase_label_source": V07A_PHASE_LABEL_SOURCE,
    }
```

- [ ] **Step 6: Add phase coverage evaluator**

```python
def _behavior_phase_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        phase: sum(1 for row in rows if row.get("behavior_state_phase") == phase)
        for phase in BEHAVIOR_STATE_PHASES
    }


def evaluate_v07a_required_phase_coverage(
    *,
    candidate_rows: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    candidate_counts = _behavior_phase_counts(candidate_rows)
    baseline_counts = _behavior_phase_counts(baseline_rows)
    missing = [phase for phase, count in candidate_counts.items() if count <= 0]
    return {
        "passed": not missing,
        "failure_reason": "" if not missing else "required_phase_missing",
        "candidate_phase_row_counts": candidate_counts,
        "baseline_phase_row_counts": baseline_counts,
        "missing_candidate_phases": missing,
    }
```

- [ ] **Step 7: Run GREEN tests**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  -k "v07a_behavior_state_phase or v07a_relabel or v07a_parent_hash or v07a_candidate_requires" -q
```

Expected: PASS.

## Task 4: Write v0.7a HDF5 And Policy Artifacts

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Test: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add HDF5 artifact test**

```python
def test_v07a_train_view_hdf5_uses_behavior_feature_schema(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    rows = [
        script.relabel_v07a_training_row(
            {
                "trajectory_id": "t0",
                "step": 0,
                "phase": "APPROACH",
                "lateral_error_m": 0.002,
                "insertion_depth_m": 0.0,
                "relative_x_m": 0.002,
                "relative_y_m": 0.0,
                "orientation_error_deg": 0.0,
                "normalized_action": [0.0] * len(script.ACTION_SCHEMA),
                "accepted": True,
            }
        )
    ]
    config = script.build_v07a_relabel_config(output_dir=tmp_path, parent_artifact_hashes={})

    view = script.write_v07a_train_view_hdf5(
        path=tmp_path / "candidate_curated_train_v0_7a.hdf5",
        rows=rows,
        view_id="candidate_curated_v0_7a",
        relabel_config=config,
    )

    assert view["schema_version"] == script.V07A_HDF5_SCHEMA_VERSION
    assert view["feature_schema"] == script.FEATURE_SCHEMA_V07A
    assert view["phase_schema"] == list(script.BEHAVIOR_STATE_PHASES)
```

- [ ] **Step 2: Add v0.7a HDF5 writer**

```python
def write_v07a_train_view_hdf5(
    *,
    path: Path,
    rows: list[dict[str, Any]],
    view_id: str,
    relabel_config: dict[str, Any],
) -> dict[str, Any]:
    features, targets = _features_targets(rows, feature_schema=FEATURE_SCHEMA_V07A)
    string_dtype = h5py.string_dtype(encoding="utf-8")
    metadata = np.asarray([stable_json(row) for row in rows], dtype=object)
    path.parent.mkdir(parents=True, exist_ok=True)
    with h5py.File(path, "w") as h5:
        h5.attrs["schema_version"] = V07A_HDF5_SCHEMA_VERSION
        h5.attrs["view_id"] = view_id
        h5.attrs["feature_schema"] = stable_json(FEATURE_SCHEMA_V07A)
        h5.attrs["feature_schema_version"] = FEATURE_SCHEMA_V07A_VERSION
        h5.attrs["phase_schema"] = stable_json(list(BEHAVIOR_STATE_PHASES))
        h5.attrs["action_schema"] = stable_json(ACTION_SCHEMA)
        h5.attrs["relabel_config_sha256"] = relabel_config["relabel_config_sha256"]
        h5.create_dataset("features", data=features)
        h5.create_dataset("actions", data=targets)
        h5.create_dataset("metadata_json", data=metadata, dtype=string_dtype)
    return {
        "schema_version": V07A_HDF5_SCHEMA_VERSION,
        "view_id": view_id,
        "path": str(path),
        "sha256": _sha256_file(path),
        "trajectory_count": len({str(row.get("trajectory_id")) for row in rows}),
        "transition_count": len(rows),
        "feature_schema": list(FEATURE_SCHEMA_V07A),
        "phase_schema": list(BEHAVIOR_STATE_PHASES),
        "relabel_config_sha256": relabel_config["relabel_config_sha256"],
        "includes_rejected_material": any(row.get("accepted") is False for row in rows),
    }
```

- [ ] **Step 3: Add policy artifact writer**

```python
def write_v07a_policy_artifacts(
    *,
    output_dir: Path,
    baseline_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    selected_adapter_id: str,
    selected_adapter_config: dict[str, Any],
    relabel_config: dict[str, Any],
) -> dict[str, Any]:
    hyperparameters = {
        "ridge_lambda": 1e-3,
        "phase_input_shared": True,
        "feature_standardization": "none_deterministic_domain_units",
        "selected_action_adapter_id": selected_adapter_id,
        "selected_action_adapter_config_sha256": _sha256_payload(selected_adapter_config),
        "trainer_family": "phase_conditioned_bc",
        "relabel_config_sha256": relabel_config["relabel_config_sha256"],
    }
    baseline = fit_phase_conditioned_bc_policy(
        policy_id="baseline_uncurated_mvp2e_v07a_behavior_phase_numpy_bc",
        train_rows=baseline_rows,
        hyperparameters=hyperparameters,
        feature_schema=FEATURE_SCHEMA_V07A,
        phase_schema=BEHAVIOR_STATE_PHASES,
    )
    candidate = fit_phase_conditioned_bc_policy(
        policy_id="candidate_curated_mvp2e_v07a_behavior_phase_numpy_bc",
        train_rows=candidate_rows,
        hyperparameters=hyperparameters,
        feature_schema=FEATURE_SCHEMA_V07A,
        phase_schema=BEHAVIOR_STATE_PHASES,
    )
    for payload in (baseline, candidate):
        payload["policy_artifact_schema_version"] = V07A_POLICY_ARTIFACT_SCHEMA_VERSION
        payload["feature_schema_version"] = FEATURE_SCHEMA_V07A_VERSION
        payload["behavior_state_phase_input"] = True
        payload["relabel_config_sha256"] = relabel_config["relabel_config_sha256"]
        payload["selected_action_adapter_id"] = selected_adapter_id
        payload["selected_action_adapter_config"] = dict(selected_adapter_config)
        payload["selected_action_adapter_config_sha256"] = _sha256_payload(selected_adapter_config)
        payload["same_feature_schema_as_peer"] = True
        payload["same_trainer_hyperparameters_as_peer"] = True
        payload["heldout_21000_21049_accessed"] = False
        payload["proof_authority"] = False
        payload["policy_artifact_sha256"] = _sha256_payload_excluding(payload, "policy_artifact_sha256")
    baseline_path = output_dir / "baseline_policy_artifact_v0_7a.json"
    candidate_path = output_dir / "candidate_policy_artifact_v0_7a.json"
    write_json(baseline_path, baseline)
    write_json(candidate_path, candidate)
    return {
        "baseline": {**baseline, "path": str(baseline_path)},
        "candidate": {**candidate, "path": str(candidate_path)},
    }
```

- [ ] **Step 4: Run artifact tests**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  -k "v07a_train_view or v07a_policy_artifact" -q
```

Expected: PASS.

## Task 5: Add Offline Train Fit Gate

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Test: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add prediction helper for rows**

```python
def predict_actions_for_rows(policy_artifact: dict[str, Any], rows: list[dict[str, Any]]) -> list[list[float]]:
    predictions: list[list[float]] = []
    previous_by_trajectory: dict[str, list[float]] = {}
    weights = np.asarray(policy_artifact["weights"], dtype=np.float64)
    bias = np.asarray(policy_artifact["bias"], dtype=np.float64)
    feature_schema = policy_artifact.get("feature_schema") or FEATURE_SCHEMA
    for row in rows:
        trajectory_id = str(row.get("trajectory_id"))
        previous = previous_by_trajectory.get(trajectory_id, [0.0] * len(ACTION_SCHEMA))
        feature, _ = featurize_step(row, previous_action=previous, feature_schema=feature_schema)
        predictions.append((feature @ weights + bias).round(10).tolist())
        previous_by_trajectory[trajectory_id] = [float(value) for value in row["normalized_action"]]
    return predictions
```

- [ ] **Step 2: Add offline metric helpers**

```python
def _sign_bucket(z: float) -> str:
    if z <= -0.08:
        return "negative"
    if z >= 0.02:
        return "positive"
    return "zero"


def _phase_rows_with_predictions(
    rows: list[dict[str, Any]],
    predictions: list[list[float]],
    phase: str,
) -> list[tuple[dict[str, Any], list[float]]]:
    return [
        (row, pred)
        for row, pred in zip(rows, predictions, strict=True)
        if row.get("behavior_state_phase") == phase
    ]
```

- [ ] **Step 3: Add `derive_v07a_offline_train_fit_gate`**

```python
def derive_v07a_offline_train_fit_gate(
    *,
    candidate_rows: list[dict[str, Any]],
    candidate_predictions: list[list[float]],
    baseline_rows: list[dict[str, Any]],
    baseline_predictions: list[list[float]],
    relabel_config_sha256: str,
    baseline_policy_artifact_sha256: str,
    candidate_policy_artifact_sha256: str,
) -> dict[str, Any]:
    coverage = evaluate_v07a_required_phase_coverage(
        candidate_rows=candidate_rows,
        baseline_rows=baseline_rows,
    )
    metrics: dict[str, Any] = {
        "schema_version": V07A_OFFLINE_FIT_GATE_SCHEMA_VERSION,
        "candidate_gate_passed": False,
        "baseline_report_only": True,
        "candidate_phase_row_counts": coverage["candidate_phase_row_counts"],
        "baseline_phase_row_counts": coverage["baseline_phase_row_counts"],
        "relabel_config_sha256": relabel_config_sha256,
        "baseline_policy_artifact_sha256": baseline_policy_artifact_sha256,
        "candidate_policy_artifact_sha256": candidate_policy_artifact_sha256,
        "heldout_21000_21049_accessed": False,
        "proof_authority": False,
    }
    if coverage["passed"] is not True:
        metrics.update({"passed": False, "failure_reason": "required_phase_missing"})
        metrics["offline_train_fit_gate_sha256"] = _sha256_payload_excluding(
            metrics,
            "offline_train_fit_gate_sha256",
        )
        return metrics

    xy_mae_values: list[float] = []
    z_mae_values: list[float] = []
    rmse_values: list[float] = []
    for phase in BEHAVIOR_STATE_PHASES:
        pairs = _phase_rows_with_predictions(candidate_rows, candidate_predictions, phase)
        expert = np.asarray([row["normalized_action"] for row, _ in pairs], dtype=np.float64)
        pred = np.asarray([prediction for _, prediction in pairs], dtype=np.float64)
        xy_mae_values.append(float(np.mean(np.abs(pred[:, :2] - expert[:, :2]))))
        z_mae_values.append(float(np.mean(np.abs(pred[:, 2] - expert[:, 2]))))
        rmse_values.append(float(np.sqrt(np.mean((pred - expert) ** 2))))

    align_pairs = _phase_rows_with_predictions(candidate_rows, candidate_predictions, "ALIGN")
    descend_pairs = _phase_rows_with_predictions(candidate_rows, candidate_predictions, "DESCEND")
    hold_pairs = _phase_rows_with_predictions(candidate_rows, candidate_predictions, "HOLD")
    align_negative_rate = sum(1 for _, pred in align_pairs if float(pred[2]) <= -0.08) / len(align_pairs)
    descend_negative_rate = sum(1 for _, pred in descend_pairs if float(pred[2]) <= -0.08) / len(descend_pairs)
    descend_sign_agreement = sum(
        1
        for row, pred in descend_pairs
        if _sign_bucket(float(pred[2])) == _sign_bucket(float(row["normalized_action"][2]))
    ) / len(descend_pairs)
    hold_abs_z_mean = statistics.mean(abs(float(pred[2])) for _, pred in hold_pairs)
    metrics.update(
        {
            "candidate_xy_mae_max": round(max(xy_mae_values), 6),
            "candidate_z_mae_max": round(max(z_mae_values), 6),
            "candidate_action_rmse_max": round(max(rmse_values), 6),
            "candidate_align_predicted_negative_z_rate": round(align_negative_rate, 6),
            "candidate_descend_predicted_negative_z_rate": round(descend_negative_rate, 6),
            "candidate_descend_z_sign_agreement": round(descend_sign_agreement, 6),
            "candidate_hold_abs_z_mean": round(float(hold_abs_z_mean), 6),
        }
    )
    passed = (
        metrics["candidate_xy_mae_max"] <= V07A_OFFLINE_FIT_THRESHOLDS["candidate_xy_mae_max"]
        and metrics["candidate_z_mae_max"] <= V07A_OFFLINE_FIT_THRESHOLDS["candidate_z_mae_max"]
        and metrics["candidate_action_rmse_max"] <= V07A_OFFLINE_FIT_THRESHOLDS["candidate_action_rmse_max"]
        and metrics["candidate_align_predicted_negative_z_rate"]
        <= V07A_OFFLINE_FIT_THRESHOLDS["candidate_align_predicted_negative_z_rate"]
        and metrics["candidate_descend_predicted_negative_z_rate"]
        >= V07A_OFFLINE_FIT_THRESHOLDS["candidate_descend_predicted_negative_z_rate"]
        and metrics["candidate_descend_z_sign_agreement"]
        >= V07A_OFFLINE_FIT_THRESHOLDS["candidate_descend_z_sign_agreement"]
        and metrics["candidate_hold_abs_z_mean"] <= V07A_OFFLINE_FIT_THRESHOLDS["candidate_hold_abs_z_mean"]
    )
    metrics["candidate_gate_passed"] = passed
    metrics["passed"] = passed
    metrics["failure_reason"] = "" if passed else "offline_train_fit_failed"
    metrics["offline_train_fit_gate_sha256"] = _sha256_payload_excluding(
        metrics,
        "offline_train_fit_gate_sha256",
    )
    return metrics
```

- [ ] **Step 4: Run offline gate tests**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  -k "v07a_offline_train_fit or required_phase_missing" -q
```

Expected: PASS.

## Task 6: Add v0.7a Offline Build Command

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Test: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add command-line flags**

In `parse_args`:

```python
parser.add_argument(
    "--policy-slice",
    choices=("v0_6", "v0_7a"),
    default="v0_6",
)
parser.add_argument("--offline-relabel-only", action="store_true")
```

- [ ] **Step 2: Add `build_v07a_behavior_phase_relabel_slice`**

```python
def build_v07a_behavior_phase_relabel_slice(*, output_dir: Path) -> dict[str, Any]:
    parent_dir = output_dir
    child_dir = output_dir / V07A_CHILD_DIR_NAME
    child_dir.mkdir(parents=True, exist_ok=True)
    parent_hashes = V07A_PARENT_ARTIFACT_HASHES
    parent_paths = {
        "baseline_uncurated_train_hdf5": parent_dir / "baseline_uncurated_train.hdf5",
        "candidate_curated_train_hdf5": parent_dir / "candidate_curated_train.hdf5",
        "baseline_policy_artifact": parent_dir / "baseline_policy_artifact.json",
        "candidate_policy_artifact": parent_dir / "candidate_policy_artifact.json",
        "curation_manifest": parent_dir / "curation_manifest.json",
    }
    parent_verdict = validate_v07a_parent_artifact_hashes(parent_paths, parent_hashes)
    if parent_verdict["passed"] is not True:
        raise ValueError("parent_artifact_hash_mismatch")

    bundle = load_existing_v06_training_rows(parent_dir=parent_dir)
    relabel_config = build_v07a_relabel_config(
        output_dir=child_dir,
        parent_artifact_hashes=parent_hashes,
    )
    baseline_rows = [relabel_v07a_training_row(row) for row in bundle["baseline_train_rows"]]
    candidate_rows = [relabel_v07a_training_row(row) for row in bundle["candidate_train_rows"]]
    coverage = evaluate_v07a_required_phase_coverage(
        candidate_rows=candidate_rows,
        baseline_rows=baseline_rows,
    )
    if coverage["passed"] is not True:
        raise ValueError("required_phase_missing")

    baseline_view = write_v07a_train_view_hdf5(
        path=child_dir / "baseline_uncurated_train_v0_7a.hdf5",
        rows=baseline_rows,
        view_id="baseline_uncurated_v0_7a",
        relabel_config=relabel_config,
    )
    candidate_view = write_v07a_train_view_hdf5(
        path=child_dir / "candidate_curated_train_v0_7a.hdf5",
        rows=candidate_rows,
        view_id="candidate_curated_v0_7a",
        relabel_config=relabel_config,
    )
    selection = read_json(parent_dir / "selected_action_adapter.json")
    policies = write_v07a_policy_artifacts(
        output_dir=child_dir,
        baseline_rows=baseline_rows,
        candidate_rows=candidate_rows,
        selected_adapter_id=selection["selected_adapter_id"],
        selected_adapter_config=selection["selected_adapter_config"],
        relabel_config=relabel_config,
    )
    baseline_predictions = predict_actions_for_rows(policies["baseline"], baseline_rows)
    candidate_predictions = predict_actions_for_rows(policies["candidate"], candidate_rows)
    offline_gate = derive_v07a_offline_train_fit_gate(
        candidate_rows=candidate_rows,
        candidate_predictions=candidate_predictions,
        baseline_rows=baseline_rows,
        baseline_predictions=baseline_predictions,
        relabel_config_sha256=relabel_config["relabel_config_sha256"],
        baseline_policy_artifact_sha256=policies["baseline"]["policy_artifact_sha256"],
        candidate_policy_artifact_sha256=policies["candidate"]["policy_artifact_sha256"],
    )
    write_json(child_dir / "offline_train_fit_gate.json", offline_gate)
    manifest = {
        "schema_version": V07A_RELABEL_MANIFEST_SCHEMA_VERSION,
        "slice_id": V07A_SLICE_ID,
        "parent_artifact_hash_verdict": parent_verdict,
        "phase_coverage": coverage,
        "training_views": {"baseline": baseline_view, "candidate": candidate_view},
        "policy_artifacts": policies,
        "offline_train_fit_gate": offline_gate,
        "heldout_21000_21049_accessed": False,
        "proof_authority": False,
    }
    manifest["v0_7a_relabel_manifest_sha256"] = _sha256_payload_excluding(
        manifest,
        "v0_7a_relabel_manifest_sha256",
    )
    write_json(child_dir / "v0_7a_relabel_manifest.json", manifest)
    return manifest
```

Implementation note: if `load_existing_v06_training_rows` cannot recover rows from current artifacts, make it read the stored parent HDF5 `metadata_json` datasets. Do not regenerate Isaac rows.

- [ ] **Step 3: Wire `main` offline path**

Before `expressibility_sanity_only` branch:

```python
if args.offline_relabel_only:
    if args.clean:
        raise ValueError("--offline-relabel-only must reuse existing v0_6 artifacts; do not pass --clean")
    if args.scenario_profile != "v0_6" or args.policy_slice != "v0_7a":
        raise ValueError("--offline-relabel-only requires --scenario-profile v0_6 --policy-slice v0_7a")
    manifest = build_v07a_behavior_phase_relabel_slice(output_dir=args.output_dir)
    _write_mvp2c_evidence_manifest(
        output_dir=args.output_dir,
        reproducible_command=_command_from_args(args),
        scenario_profile=args.scenario_profile,
        metadata={
            "runtime_backend": "offline_relabel",
            "proof_runtime": "mvp2e_v07a_behavior_state_phase_relabel",
            "mvp2_closed": False,
            "heldout_opened": False,
        },
    )
    print(stable_json(manifest))
    return 0
```

- [ ] **Step 4: Run command-path tests**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  -k "v07a_offline_relabel or policy_slice" -q
```

Expected: PASS.

## Task 7: Gate Expressibility On v0.7a Offline Fit

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Test: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add `run_v07a_expressibility_sanity_runtime`**

```python
def run_v07a_expressibility_sanity_runtime(
    *,
    output_dir: Path,
    manifest: dict[str, Any],
    device: str,
    headless: bool,
    isaac_task: str,
    max_steps: int,
    action_scale: float,
) -> dict[str, Any]:
    child_dir = output_dir / V07A_CHILD_DIR_NAME
    gate_path = child_dir / "offline_train_fit_gate.json"
    if not gate_path.exists() or read_json(gate_path).get("passed") is not True:
        gate = {
            "schema_version": "rdf_mvp2e_v07a_expressibility_sanity_gate_v0.1.0",
            "passed": False,
            "runtime_backend": "isaac_runtime_not_started",
            "proof_runtime": "isaac_candidate_policy_train_split_expressibility_sanity",
            "reason": "missing_passed_v0_7a_offline_train_fit_gate",
            "heldout_opened": False,
            "heldout_21000_21049_accessed": False,
            "proof_authority": False,
        }
        write_json(child_dir / "expressibility_sanity_gate_v0_7a.json", gate)
        return gate
    policy_path = child_dir / "candidate_policy_artifact_v0_7a.json"
    if not policy_path.exists():
        raise ValueError("missing_v0_7a_candidate_policy_artifact")
    train_gate_status = resolve_existing_v06_train_generation_runtime_gate(output_dir=output_dir)
    probe_manifest = build_v06_expressibility_sanity_manifest(
        manifest=manifest,
        train_generation_runtime_gate=train_gate_status["gate"],
    )
    write_json(child_dir / "expressibility_sanity_manifest_v0_7a.json", probe_manifest)
    probe_result = IsaacConnectorInsertionEvaluatorBackend(
        task=isaac_task,
        device=device,
        headless=headless,
        action_scale=action_scale,
        max_steps=max_steps,
    ).run_single_policy_probe(
        manifest=probe_manifest,
        output_dir=child_dir / "isaac_runtime_expressibility_sanity_v0_7a",
        policy_artifact=read_json(policy_path),
        role="v0_7a_expressibility_sanity",
        max_rollouts=V06_EXPRESSIBILITY_SANITY_SEED_COUNT,
        stop_after_first_success=False,
    )
    gate = derive_v06_expressibility_sanity_gate_from_probe_result(probe_result)
    gate["schema_version"] = "rdf_mvp2e_v07a_expressibility_sanity_gate_v0.1.0"
    gate["policy_slice"] = V07A_SLICE_ID
    gate["offline_train_fit_gate_sha256"] = read_json(gate_path)["offline_train_fit_gate_sha256"]
    gate["manifest_sha256"] = probe_manifest["manifest_sha256"]
    gate["heldout_21000_21049_accessed"] = False
    gate["proof_authority"] = False
    write_json(child_dir / "expressibility_sanity_gate_v0_7a.json", gate)
    return gate
```

- [ ] **Step 2: Route `--expressibility-sanity-only --policy-slice v0_7a`**

In `main`, inside the expressibility branch:

```python
if args.policy_slice == "v0_7a":
    gate = run_v07a_expressibility_sanity_runtime(
        output_dir=args.output_dir,
        manifest=read_json(manifest_path),
        device=args.device,
        headless=args.headless,
        isaac_task=args.isaac_task,
        max_steps=args.max_steps,
        action_scale=args.action_scale,
    )
else:
    gate = run_v06_expressibility_sanity_runtime(...)
```

- [ ] **Step 3: Update preheldout status**

Make `resolve_v06_preheldout_gate_status(output_dir=..., policy_slice="v0_7a")` require:

```text
offline_train_fit_gate.passed=true
expressibility_sanity_gate_v0_7a.passed=true
calibration_presignal_gate.passed=true
```

Keep default `policy_slice="v0_6"` behavior compatible.

- [ ] **Step 4: Run gate tests**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  -k "v07a_expressibility or preheldout" -q
```

Expected: PASS.

## Task 8: Reports, Evidence Manifest, And Documentation

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Modify: `docs/developer/worklog.md`
- Modify: `docs/developer/debugging_guide.md`
- Modify: `Handoff.md`
- Test: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Include v0.7a artifacts in evidence manifest metadata**

Ensure `_write_mvp2c_evidence_manifest` receives metadata with:

```python
{
    "policy_slice": "v0_7a",
    "offline_train_fit_gate": "v0_7a_behavior_state_phase_relabel/offline_train_fit_gate.json",
    "v0_7a_relabel_manifest": "v0_7a_behavior_state_phase_relabel/v0_7a_relabel_manifest.json",
    "heldout_opened": False,
    "heldout_21000_21049_accessed": False,
    "mvp2_closed": False,
}
```

- [ ] **Step 2: Add buyer-facing limitation string to v0.7a report payloads**

Use exactly:

```text
This is an Isaac evaluator-domain learning proof using privileged task-state and behavior-state phase features derived from frozen controller geometry gates. It does not claim deployable real-world visual policy performance, real robot success, physical robot readiness, HMD readiness, or universal robot support.
```

- [ ] **Step 3: Update docs**

Append to `docs/developer/worklog.md`:

```markdown
### 2026-06-12 - MVP-2E v0.7a behavior-state phase relabel plan/implementation

- 작업: `v0_7a` behavior-state phase relabel slice 구현.
- 판단 이유: Phase E expressibility `0/5` 원인이 depth-derived `phase`와 controller behavior state mismatch로 확인됨.
- 변경 파일: `scripts/run_mvp2b_isaac_proof_evaluator.py`, `scripts/run_mvp2c_isaac_training_calibration.py`, 관련 tests.
- 검증: targeted pytest, full MVP-2B/MVP-2C non-Isaac pytest, compileall, ruff, `git diff --check`.
- 남은 gap: offline gate 통과 후 actual Isaac expressibility sanity `>=2/5` 필요. Held-out은 계속 봉인.
```

Update `docs/developer/debugging_guide.md` with:

```markdown
### MVP-2E v0.7a

`v0_7a`는 새 Isaac train-generation을 만들지 않는다. 먼저:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 --policy-slice v0_7a --offline-relabel-only --pretty
```

`offline_train_fit_gate.passed=true`일 때만:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 --policy-slice v0_7a --expressibility-sanity-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 --device cuda:0 --pretty
```
```

Update `Handoff.md` with current status and next gate:

```text
MVP-2E v0.7a: behavior-state phase relabel slice implemented.
Next gate: offline_train_fit_gate -> expressibility sanity >=2/5.
Held-out 21000-21049 remains sealed.
```

- [ ] **Step 4: Run final non-Isaac verification**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q

uv run python -m compileall -q scripts apps/api/app apps/api/tests

uvx ruff check scripts/run_mvp2b_isaac_proof_evaluator.py \
  scripts/run_mvp2c_isaac_training_calibration.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py

git diff --check
```

Expected: all pass.

## Final Runtime Sequence

After implementation and non-Isaac verification:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7a \
  --offline-relabel-only \
  --pretty
```

Then, only if `offline_train_fit_gate.passed=true`:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7a \
  --expressibility-sanity-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

Do not run calibration or held-out in this implementation slice.

## ADR

Decision: implement `v0_7a` as a child offline relabel/training slice using `behavior_state_phase` rather than rewriting old `phase`.

Drivers:

1. Current expressibility failure is caused by behavior-state/action mismatch.
2. Existing v0.6 train-generation evidence is valid and must not be overwritten.
3. Offline fit gate can prevent wasteful Isaac runs.

Alternatives considered:

- Overwrite `phase`: rejected because it breaks audit semantics and old artifact compatibility.
- Move straight to residual servo BC: rejected because it confounds the diagnosed single-variable fix.
- Re-run train-generation: rejected because v0.7a is a policy feature slice and the 40-run expert gate already passed.

Consequences:

- Old and new policy artifacts must carry their own feature schema.
- Expressibility must become policy-slice aware.
- v0.7a can still fail closed; if so, v0.7b needs a separate spec.

## Available Agent Types

- `executor`: implement code/test tasks.
- `test-engineer`: strengthen offline fit and artifact tests.
- `architect`: review schema and artifact boundary.
- `critic`: verify proof integrity and anti-leakage constraints.
- `verifier`: run final checks and summarize evidence.

## Recommended Execution Handoff

Default:

```bash
$ultragoal implement docs/superpowers/plans/2026-06-12-mvp2e-v07a-behavior-state-phase-relabel.md
```

Parallel option:

```text
$ultragoal + $team
  lane 1 executor: `run_mvp2b` schema-aware feature path
  lane 2 executor: `run_mvp2c` relabel/config/HDF5/policy artifacts
  lane 3 test-engineer: offline gate and preheldout tests
```

`$ralph` fallback is not recommended as the default because durable checkpointed goal tracking is more important than single-owner persistence for this slice. Use `$ralph` only if `ultragoal` state is unavailable.

## Goal-Mode Follow-up Suggestions

- `$ultragoal`: recommended next step for implementation.
- `$team`: useful if parallel lanes are desired after the plan is approved.
- `$autoresearch-goal`: not needed unless v0.7a fails and the next blocker becomes research-shaped.
- `$performance-goal`: not relevant; this is proof integrity and behavior correctness, not optimization.
