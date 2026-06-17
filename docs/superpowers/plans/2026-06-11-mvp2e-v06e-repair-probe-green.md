# MVP-2E v0.6e Repair Probe Green Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the pre-registered v0.6e repair-probe-green slice without opening the fixed 40-run train gate or held-out `21000-21049`.

**Architecture:** Keep Isaac env-native 10-consecutive success as the primary authority, make secondary divergence diagnostics non-veto for env-native-passed seeds, require numeric geometry-isolated capture radius before repair probe execution, and derive the controller z-push gate from that capture radius. The implementation stays inside the existing MVP-2B/MVP-2C scripts and tests; no new runtime dependency or dynamic plugin system is introduced.

**Tech Stack:** Python 3.11, pytest, Isaac Lab runtime through `/home/kangrim/IsaacLab/_isaac_sim/python.sh`, JSON artifacts, existing scripts under `scripts/`, existing tests under `apps/api/tests/`.

---

## Source Spec

Implement exactly this spec:

```text
docs/superpowers/specs/2026-06-11-mvp2e-v06e-repair-probe-green-design.md
```

Do not implement broader MVP-2 closure. The only allowed runtime proof in this plan is capture-radius probe and repair-probe-only execution.

## File Structure

- Modify `scripts/run_mvp2c_isaac_training_calibration.py`
  - Add v0.6e convergence constants.
  - Add numeric capture-radius preflight validation.
  - Add v0.6e non-seated lateral convergence evaluation.
  - Add v0.6e repair probe gate evaluation.
  - Derive controller repair config from numeric `capture_radius_m`.
  - Pass capture-radius-derived config into repair probe expert policy.
  - Emit `controller_repair_config.json`.
- Modify `scripts/run_mvp2b_isaac_proof_evaluator.py`
  - Preserve v0.6d phase normalization.
  - Ensure action adapter diagnostics expose capture-radius-gated z suppression.
  - Keep z motion blocked while `lateral_error_m > align_lateral_gate_m`.
- Modify `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
  - Add unit tests for v0.6e convergence, authority, strict numeric capture preflight, and controller repair config.
- Modify `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
  - Add unit tests for capture-radius-derived z gating.
- Modify docs after implementation:
  - `docs/developer/worklog.md`
  - `docs/developer/debugging_guide.md`
  - `tasks/todo.md`
  - `Handoff.md`

## Stop Conditions

Stop and report if any condition is hit.

```text
capture_radius_m cannot be made numeric through geometry-isolated runtime probe
capture-radius probe requires xy/yaw correction
repair probe requires held-out 21000-21049
repair probe requires fixed 40-run train gate
controller repair requires horizon increase
controller repair requires retry/search/withdraw/force-control
controller repair requires per-seed grid search over 16023/16042/16096
16023 loses env-native pass after global repair config
all lateral seeds lose env-native pass after global repair config
```

## Task 1: Add RED Tests For v0.6e Authority And Convergence

**Files:**
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
- Later modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Add tests after `test_lateral_divergence_stopped_uses_gap_derived_cap_and_last10_median`**

```python
def test_v06e_non_seated_convergence_uses_capture_radius_and_no_regression() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    converged = script.evaluate_v06e_non_seated_lateral_convergence(
        lateral_errors_m=[0.023, 0.018, 0.011, 0.004, 0.0028, 0.0027, 0.0028, 0.0029, 0.0028, 0.0029],
        capture_radius_m=0.003,
        last_k=5,
    )

    assert converged["non_seated_lateral_converged"] is True
    assert converged["near_band_m"] == 0.003
    assert converged["last_k_median_lateral_m"] <= 0.003
    assert converged["regression_detected"] is False

    regressed = script.evaluate_v06e_non_seated_lateral_convergence(
        lateral_errors_m=[0.0234, 0.012, 0.00276, 0.006, 0.010, 0.0143, 0.0142, 0.0144, 0.0143, 0.0141],
        capture_radius_m=0.003,
        last_k=5,
    )

    assert regressed["non_seated_lateral_converged"] is False
    assert regressed["regression_detected"] is True
    assert regressed["min_lateral_achieved_m"] == 0.00276
```

- [ ] **Step 2: Add env-native authority test**

```python
def test_v06e_repair_probe_gate_does_not_let_divergence_veto_env_native_pass() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    gate = script.evaluate_v06e_repair_probe_gate(
        {
            16023: {
                "env_native_rollout_success": True,
                "env_native_max_consecutive_success_steps": 10,
                "lateral_divergence_stopped": True,
            },
            16042: {
                "env_native_rollout_success": True,
                "env_native_max_consecutive_success_steps": 10,
                "lateral_divergence_stopped": False,
                "initial_lateral_error_m": 0.016754,
                "last_10_median_lateral_error_m": 0.000365,
            },
            16096: {
                "env_native_rollout_success": False,
                "env_native_max_consecutive_success_steps": 0,
                "lateral_errors_m": [0.023, 0.018, 0.011, 0.004, 0.0028, 0.0027, 0.0028, 0.0029, 0.0028, 0.0029],
            },
        },
        capture_radius_m=0.003,
    )

    assert gate["green_light_for_40_run_gate"] is True
    assert gate["hard_stop"] is False
    assert gate["seed_results"]["16042"]["seed_pass"] is True
    assert gate["seed_results"]["16042"]["divergence_diagnostic_authority"] == "report_only"
```

- [ ] **Step 3: Add non-seated regression blocker test**

```python
def test_v06e_repair_probe_gate_blocks_non_seated_lateral_regression() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    gate = script.evaluate_v06e_repair_probe_gate(
        {
            16023: {
                "env_native_rollout_success": True,
                "env_native_max_consecutive_success_steps": 10,
            },
            16042: {
                "env_native_rollout_success": True,
                "env_native_max_consecutive_success_steps": 10,
            },
            16096: {
                "env_native_rollout_success": False,
                "env_native_max_consecutive_success_steps": 0,
                "lateral_errors_m": [0.0234, 0.012, 0.00276, 0.006, 0.010, 0.0143, 0.0142, 0.0144, 0.0143, 0.0141],
            },
        },
        capture_radius_m=0.003,
    )

    assert gate["green_light_for_40_run_gate"] is False
    assert gate["hard_stop"] is True
    assert gate["seed_results"]["16096"]["seed_pass"] is False
    assert gate["seed_results"]["16096"]["convergence"]["regression_detected"] is True
```

- [ ] **Step 4: Run RED tests**

Run:

```bash
uv run pytest \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06e_non_seated_convergence_uses_capture_radius_and_no_regression \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06e_repair_probe_gate_does_not_let_divergence_veto_env_native_pass \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06e_repair_probe_gate_blocks_non_seated_lateral_regression \
  -q
```

Expected:

```text
FAILED ... AttributeError: module 'run_mvp2c_isaac_training_calibration' has no attribute 'evaluate_v06e_non_seated_lateral_convergence'
FAILED ... AttributeError: module 'run_mvp2c_isaac_training_calibration' has no attribute 'evaluate_v06e_repair_probe_gate'
```

## Task 2: Implement v0.6e Convergence And Gate Helpers

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Test: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add v0.6e constants near existing v0.6 constants**

```python
V06E_CONVERGENCE_LAST_K = 10
V06E_REGRESSION_TOL_FLOOR_M = 0.0005
V06E_REGRESSION_TOL_CAPTURE_RATIO = 0.5
```

- [ ] **Step 2: Add numeric helper after `evaluate_lateral_divergence_stopped`**

```python
def _numeric_capture_radius_m(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if not isinstance(value, int | float):
        return None
    numeric = float(value)
    if numeric <= 0.0:
        return None
    return numeric
```

- [ ] **Step 3: Add v0.6e convergence evaluator**

```python
def evaluate_v06e_non_seated_lateral_convergence(
    *,
    lateral_errors_m: Sequence[float],
    capture_radius_m: float,
    last_k: int = V06E_CONVERGENCE_LAST_K,
    regression_tol_floor_m: float = V06E_REGRESSION_TOL_FLOOR_M,
    regression_tol_capture_ratio: float = V06E_REGRESSION_TOL_CAPTURE_RATIO,
) -> dict[str, Any]:
    numeric_capture_radius = _numeric_capture_radius_m(capture_radius_m)
    if numeric_capture_radius is None:
        return {
            "non_seated_lateral_converged": False,
            "reason": "capture_radius_not_numeric",
            "capture_radius_m": capture_radius_m,
        }
    if not lateral_errors_m:
        return {
            "non_seated_lateral_converged": False,
            "reason": "missing_lateral_diagnostics",
            "capture_radius_m": numeric_capture_radius,
            "near_band_m": numeric_capture_radius,
        }
    values = [float(value) for value in lateral_errors_m]
    window = values[-max(1, int(last_k)) :]
    min_lateral = min(values)
    tail_median = statistics.median(window)
    regression_tol = max(float(regression_tol_floor_m), float(regression_tol_capture_ratio) * numeric_capture_radius)
    inside_near_band = tail_median <= numeric_capture_radius
    no_regression = tail_median <= min_lateral + regression_tol
    return {
        "non_seated_lateral_converged": bool(inside_near_band and no_regression),
        "reason": "converged_no_regression" if inside_near_band and no_regression else "not_converged_or_regressed",
        "capture_radius_m": numeric_capture_radius,
        "near_band_m": numeric_capture_radius,
        "last_k": int(last_k),
        "regression_tol_m": round(float(regression_tol), 6),
        "min_lateral_achieved_m": round(float(min_lateral), 6),
        "last_k_median_lateral_m": round(float(tail_median), 6),
        "inside_near_band": bool(inside_near_band),
        "regression_detected": not bool(no_regression),
    }
```

- [ ] **Step 4: Add lateral error extraction helper**

```python
def _v06e_lateral_errors_from_probe_result(result: dict[str, Any]) -> list[float]:
    values = result.get("lateral_errors_m")
    if isinstance(values, list):
        return [float(value) for value in values]
    initial = result.get("initial_lateral_error_m")
    last_median = result.get("last_10_median_lateral_error_m")
    min_lateral = result.get("min_lateral_achieved_m")
    if initial is not None and last_median is not None and min_lateral is not None:
        return [float(initial), float(min_lateral), float(last_median)]
    return []
```

- [ ] **Step 5: Add v0.6e repair probe gate evaluator**

```python
def evaluate_v06e_repair_probe_gate(
    probe_results: dict[Any, Any],
    *,
    capture_radius_m: float,
) -> dict[str, Any]:
    numeric_capture_radius = _numeric_capture_radius_m(capture_radius_m)
    normalized = _normalize_v06_repair_probe_results(probe_results)
    seed_results: dict[str, dict[str, Any]] = {}
    non_seated_lateral_converged = True
    lateral_env_native_pass_count = 0
    for seed, result in normalized.items():
        env_native_pass = bool(result.get("env_native_rollout_success")) or int(
            result.get("env_native_max_consecutive_success_steps", 0)
        ) >= V06_ENV_NATIVE_STABLE_STEPS_REQUIRED
        is_lateral_seed = seed in {16042, 16096}
        seed_payload = {
            **result,
            "env_native_seed_pass": env_native_pass,
            "seed_pass": env_native_pass,
            "divergence_diagnostic_authority": "report_only" if env_native_pass else "non_seated_lateral_gate",
        }
        if env_native_pass and is_lateral_seed:
            lateral_env_native_pass_count += 1
        if (not env_native_pass) and is_lateral_seed:
            convergence = evaluate_v06e_non_seated_lateral_convergence(
                lateral_errors_m=_v06e_lateral_errors_from_probe_result(result),
                capture_radius_m=capture_radius_m,
            )
            seed_payload["convergence"] = convergence
            seed_payload["seed_pass"] = bool(convergence["non_seated_lateral_converged"])
            non_seated_lateral_converged = non_seated_lateral_converged and bool(
                convergence["non_seated_lateral_converged"]
            )
        elif (not env_native_pass) and seed == 16023:
            seed_payload["seed_pass"] = False
        seed_results[str(seed)] = seed_payload

    hold_passed = bool(seed_results["16023"]["env_native_seed_pass"])
    green = (
        numeric_capture_radius is not None
        and hold_passed
        and lateral_env_native_pass_count >= 1
        and non_seated_lateral_converged
        and all(bool(payload["seed_pass"]) for payload in seed_results.values())
    )
    result = {
        "schema_version": "rdf_mvp2e_v06e_repair_probe_gate_v0.1.0",
        "proof_authority": False,
        "capture_radius_m": numeric_capture_radius if numeric_capture_radius is not None else capture_radius_m,
        "capture_radius_numeric": numeric_capture_radius is not None,
        "probe_seeds": list(V06_REPAIR_PROBE_SEEDS),
        "hold_mode_passed": hold_passed,
        "lateral_success_mode_passed": lateral_env_native_pass_count >= 1,
        "non_seated_lateral_converged": non_seated_lateral_converged,
        "green_light_for_40_run_gate": bool(green),
        "hard_stop": not bool(green),
        "seed_results": seed_results,
        "fixed_40_run_gate_opened": False,
        "heldout_opened": False,
    }
    result["repair_probe_gate_sha256"] = _sha256_payload_excluding(result, "repair_probe_gate_sha256")
    return result
```

- [ ] **Step 6: Run GREEN tests**

Run:

```bash
uv run pytest \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06e_non_seated_convergence_uses_capture_radius_and_no_regression \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06e_repair_probe_gate_does_not_let_divergence_veto_env_native_pass \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06e_repair_probe_gate_blocks_non_seated_lateral_regression \
  -q
```

Expected:

```text
3 passed
```

- [ ] **Step 7: Commit Task 2**

```bash
git add scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
git commit -m "Make MVP-2E repair probe authority env-native first" \
  -m "Add v0.6e convergence and repair-probe gate helpers so secondary lateral diagnostics cannot veto env-native pass." \
  -m "Constraint: Held-out and fixed 40-run remain unopened." \
  -m "Rejected: absolute max-lateral cap | high-initial-lateral seeds made it a false veto." \
  -m "Confidence: high" \
  -m "Scope-risk: narrow" \
  -m "Tested: uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06e_non_seated_convergence_uses_capture_radius_and_no_regression apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06e_repair_probe_gate_does_not_let_divergence_veto_env_native_pass apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06e_repair_probe_gate_blocks_non_seated_lateral_regression -q"
```

## Task 3: Enforce Numeric Geometry-Isolated Capture Radius Before Repair Probe

**Files:**
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Add strict preflight tests after existing v0.6a preflight tests**

```python
def test_v06e_numeric_capture_preflight_rejects_approximate_branch_b(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    preflight = {
        "preflight_branch": "B",
        "inspection_method": "runtime_empirical_capture_radius_probe",
        "capture_radius_m": "approximate",
        "repair_probe_allowed": True,
        "capture_radius_probe_sha256": "abc",
    }
    probe = {
        "preflight_branch": "B",
        "inspection_method": "runtime_empirical_capture_radius_probe",
        "capture_radius_m": "approximate",
        "capture_radius_probe_sha256": "abc",
        "geometry_probe_seed": script.V06A_CAPTURE_RADIUS_PRIMARY_SEED,
        "directions": list(script.V06A_CAPTURE_RADIUS_DIRECTIONS),
        "offset_sweep_m": list(script.V06A_CAPTURE_RADIUS_OFFSET_SWEEP_M),
        "measurement": {"capture_radius_m": "approximate"},
    }

    resolved = script.validate_v06e_numeric_capture_radius_preflight(
        preflight=preflight,
        capture_radius_probe=probe,
    )

    assert resolved["repair_probe_allowed"] is False
    assert resolved["insert_parameter_freeze_allowed"] is False
    assert resolved["reason"] == "capture_radius_not_numeric"
```

- [ ] **Step 2: Add numeric pass test**

```python
def test_v06e_numeric_capture_preflight_accepts_geometry_isolated_numeric_probe() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    preflight = {
        "preflight_branch": "B",
        "inspection_method": "runtime_empirical_capture_radius_probe",
        "capture_radius_m": 0.0002,
        "repair_probe_allowed": True,
        "insert_parameter_freeze_allowed": True,
        "capture_radius_probe_sha256": "abc",
    }
    probe = {
        "preflight_branch": "B",
        "inspection_method": "runtime_empirical_capture_radius_probe",
        "capture_radius_m": 0.0002,
        "capture_radius_probe_sha256": "abc",
        "geometry_probe_seed": script.V06A_CAPTURE_RADIUS_PRIMARY_SEED,
        "geometry_isolated": True,
        "xy_correction_enabled": False,
        "yaw_correction_enabled": False,
        "z_push_mode": "straight_down_bounded",
        "directions": list(script.V06A_CAPTURE_RADIUS_DIRECTIONS),
        "offset_sweep_m": list(script.V06A_CAPTURE_RADIUS_OFFSET_SWEEP_M),
        "measurement": {"capture_radius_m": 0.0002},
    }

    resolved = script.validate_v06e_numeric_capture_radius_preflight(
        preflight=preflight,
        capture_radius_probe=probe,
    )

    assert resolved["repair_probe_allowed"] is True
    assert resolved["insert_parameter_freeze_allowed"] is True
    assert resolved["capture_radius_m"] == 0.0002
    assert resolved["capture_radius_probe_geometry_isolated"] is True
```

- [ ] **Step 3: Run RED tests**

Run:

```bash
uv run pytest \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06e_numeric_capture_preflight_rejects_approximate_branch_b \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06e_numeric_capture_preflight_accepts_geometry_isolated_numeric_probe \
  -q
```

Expected:

```text
FAILED ... AttributeError: module 'run_mvp2c_isaac_training_calibration' has no attribute 'validate_v06e_numeric_capture_radius_preflight'
```

- [ ] **Step 4: Update capture probe artifact to mark geometry isolation**

Modify `build_v06a_capture_radius_probe_artifact()` to include:

```python
"geometry_isolated": True,
"xy_correction_enabled": False,
"yaw_correction_enabled": False,
"z_push_mode": "straight_down_bounded",
```

- [ ] **Step 5: Add strict v0.6e preflight validator after `validate_v06a_verified_chamfer_preflight`**

```python
def validate_v06e_numeric_capture_radius_preflight(
    *,
    preflight: dict[str, Any],
    capture_radius_probe: dict[str, Any],
) -> dict[str, Any]:
    capture_radius = _numeric_capture_radius_m(preflight.get("capture_radius_m"))
    probe_capture_radius = _numeric_capture_radius_m(capture_radius_probe.get("capture_radius_m"))
    required_probe_fields = {
        "geometry_isolated": True,
        "xy_correction_enabled": False,
        "yaw_correction_enabled": False,
        "z_push_mode": "straight_down_bounded",
        "geometry_probe_seed": V06A_CAPTURE_RADIUS_PRIMARY_SEED,
    }
    reasons: list[str] = []
    if capture_radius is None or probe_capture_radius is None:
        reasons.append("capture_radius_not_numeric")
    elif abs(capture_radius - probe_capture_radius) > 1.0e-12:
        reasons.append("capture_radius_probe_mismatch")
    if preflight.get("inspection_method") != "runtime_empirical_capture_radius_probe":
        reasons.append("inspection_method_not_runtime_empirical_capture_radius_probe")
    for key, expected in required_probe_fields.items():
        if capture_radius_probe.get(key) != expected:
            reasons.append(f"capture_radius_probe_{key}")
    if capture_radius_probe.get("directions") != list(V06A_CAPTURE_RADIUS_DIRECTIONS):
        reasons.append("capture_radius_probe_directions")
    if capture_radius_probe.get("offset_sweep_m") != list(V06A_CAPTURE_RADIUS_OFFSET_SWEEP_M):
        reasons.append("capture_radius_probe_offset_sweep")

    if reasons:
        reason = "capture_radius_not_numeric" if "capture_radius_not_numeric" in reasons else ";".join(reasons)
        return {
            **preflight,
            "repair_probe_allowed": False,
            "insert_parameter_freeze_allowed": False,
            "train_generation_gate_allowed": False,
            "capture_radius_probe_geometry_isolated": False,
            "reason": reason,
            "v0_6e_numeric_capture_radius_preflight_valid": False,
            "v0_6e_numeric_capture_radius_preflight_reasons": reasons,
        }
    return {
        **preflight,
        "capture_radius_m": capture_radius,
        "capture_radius_source": "empirical_runtime_probe",
        "capture_radius_probe_geometry_isolated": True,
        "repair_probe_allowed": True,
        "insert_parameter_freeze_allowed": True,
        "v0_6e_numeric_capture_radius_preflight_valid": True,
        "v0_6e_numeric_capture_radius_preflight_reasons": [],
    }
```

- [ ] **Step 6: Run GREEN tests**

Run:

```bash
uv run pytest \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06e_numeric_capture_preflight_rejects_approximate_branch_b \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06e_numeric_capture_preflight_accepts_geometry_isolated_numeric_probe \
  -q
```

Expected:

```text
2 passed
```

- [ ] **Step 7: Commit Task 3**

```bash
git add scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
git commit -m "Require numeric capture radius before MVP-2E repair probe" \
  -m "Validate that v0.6e repair-probe parameters are grounded in a geometry-isolated empirical runtime capture-radius measurement." \
  -m "Constraint: Approximate Branch B no longer unlocks repair probe for v0.6e." \
  -m "Rejected: frozen v0.6 adapter envelope | reused failed parameters without geometry grounding." \
  -m "Confidence: high" \
  -m "Scope-risk: narrow" \
  -m "Tested: uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06e_numeric_capture_preflight_rejects_approximate_branch_b apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06e_numeric_capture_preflight_accepts_geometry_isolated_numeric_probe -q"
```

## Task 4: Derive Controller Repair Config From Numeric Capture Radius

**Files:**
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
- Modify: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`

- [ ] **Step 1: Add controller repair config test**

Add to `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`:

```python
def test_v06e_controller_repair_config_derives_z_gate_from_capture_radius() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    config = script.build_v06e_controller_repair_config(capture_radius_m=0.003)

    assert config["controller_version"] == "v0_6_active_state_controller"
    assert config["capture_radius_m"] == 0.003
    assert config["align_lateral_gate_m"] == 0.003
    assert config["tol_align_source"] == "empirical_capture_radius_m"
    assert config["z_push_gate"] == "lateral_error_m <= capture_radius_m"
    assert config["retry_recover_withdraw_search"] is False
    assert config["force_reactive_control"] is False
```

- [ ] **Step 2: Add action adapter z-gate tests**

Add to `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py` after v0.6d action diagnostics tests:

```python
def test_v06e_capture_radius_gate_suppresses_z_until_inside_capture_radius() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy_artifact = {
        "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
        "selected_action_adapter_config": {
            "controller_version": "v0_6_active_state_controller",
            "capture_radius_m": 0.003,
            "align_lateral_gate_m": 0.003,
            "align_orientation_gate_rad": 0.25,
            "xy_source": "state_feedback",
            "xy_state_feedback_gain": 4.0,
            "xy_action_clip": 0.035,
            "z_action_scale": 24.0,
            "z_action_clip": 0.12,
            "rotation_action_scale": 0.0,
        },
    }
    metric_row = {
        "phase": "APPROACH",
        "lateral_error_m": 0.004,
        "orientation_error_deg": 0.01,
        "insertion_depth_m": 0.0,
        "relative_x_m": 0.004,
        "relative_y_m": 0.0,
        "env_native_success": False,
        "env_native_current_consecutive_success_steps": 0,
    }

    action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy_artifact,
        raw_action=script.np.asarray([0.0, 0.0, -0.005, 0.0, 0.0, 0.0, 1.0]),
        action_scale=1.0,
        metric_row=metric_row,
    )

    assert diagnostics["pre_controller_action_vector"][2] < 0.0
    assert action[2] == 0.0
    assert diagnostics["z_motion_suppressed"] is True
    assert diagnostics["z_motion_block_reason"] == "alignment_gate_not_satisfied"
    assert diagnostics["align_lateral_gate_m"] == 0.003
```

- [ ] **Step 3: Add inside-capture z-allow test**

```python
def test_v06e_capture_radius_gate_allows_z_inside_capture_radius() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")
    policy_artifact = {
        "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
        "selected_action_adapter_config": {
            "controller_version": "v0_6_active_state_controller",
            "capture_radius_m": 0.003,
            "align_lateral_gate_m": 0.003,
            "align_orientation_gate_rad": 0.25,
            "xy_source": "state_feedback",
            "xy_state_feedback_gain": 4.0,
            "xy_action_clip": 0.035,
            "z_action_scale": 24.0,
            "z_action_clip": 0.12,
            "rotation_action_scale": 0.0,
        },
    }
    metric_row = {
        "phase": "APPROACH",
        "lateral_error_m": 0.0025,
        "orientation_error_deg": 0.01,
        "insertion_depth_m": 0.0,
        "relative_x_m": 0.0025,
        "relative_y_m": 0.0,
        "env_native_success": False,
        "env_native_current_consecutive_success_steps": 0,
    }

    action, diagnostics = script._apply_selected_action_adapter_with_diagnostics(
        policy_artifact=policy_artifact,
        raw_action=script.np.asarray([0.0, 0.0, -0.005, 0.0, 0.0, 0.0, 1.0]),
        action_scale=1.0,
        metric_row=metric_row,
    )

    assert action[2] < 0.0
    assert diagnostics["z_motion_suppressed"] is False
    assert diagnostics["z_motion_block_reason"] == "z_motion_allowed"
    assert diagnostics["align_lateral_gate_m"] == 0.003
```

- [ ] **Step 4: Run RED tests**

Run:

```bash
uv run pytest \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06e_controller_repair_config_derives_z_gate_from_capture_radius \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py::test_v06e_capture_radius_gate_suppresses_z_until_inside_capture_radius \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py::test_v06e_capture_radius_gate_allows_z_inside_capture_radius \
  -q
```

Expected:

```text
FAILED ... AttributeError: module 'run_mvp2c_isaac_training_calibration' has no attribute 'build_v06e_controller_repair_config'
```

The two `test_mvp2b` tests may already pass because the v0.6d controller honors `align_lateral_gate_m`; keep them as regression coverage.

- [ ] **Step 5: Add controller repair config builder**

Add to `scripts/run_mvp2c_isaac_training_calibration.py` near `_scripted_expert_probe_policy_artifact()`:

```python
def build_v06e_controller_repair_config(*, capture_radius_m: float) -> dict[str, Any]:
    numeric_capture_radius = _numeric_capture_radius_m(capture_radius_m)
    if numeric_capture_radius is None:
        raise ValueError("v0_6e controller repair config requires numeric capture_radius_m")
    config = {
        "controller_version": "v0_6_active_state_controller",
        "success_authority": "isaac_env_native_consecutive_success_v0",
        "capture_radius_m": numeric_capture_radius,
        "align_lateral_gate_m": numeric_capture_radius,
        "tol_align_source": "empirical_capture_radius_m",
        "z_push_gate": "lateral_error_m <= capture_radius_m",
        "align_orientation_gate_rad": 0.25,
        "continued_xy_yaw_correction": True,
        "bounded_monotonic_downward_push": True,
        "retry_recover_withdraw_search": False,
        "force_reactive_control": False,
        "per_seed_tuning": False,
        "horizon_increase": False,
    }
    config["controller_repair_config_sha256"] = _sha256_payload_excluding(config, "controller_repair_config_sha256")
    return config
```

- [ ] **Step 6: Update expert policy artifact to accept repair config**

Change `_scripted_expert_probe_policy_artifact()` signature:

```python
def _scripted_expert_probe_policy_artifact(
    *,
    selected_adapter_id: str,
    selected_adapter_config: dict[str, Any],
    scenario_profile: str = "v0_1",
    controller_repair_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
```

Inside the `if scenario_profile == "v0_6":` block, after the existing `update(...)`, add:

```python
        if isinstance(controller_repair_config, dict):
            train_generation_controller_config.update(controller_repair_config)
```

- [ ] **Step 7: Run GREEN tests**

Run:

```bash
uv run pytest \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06e_controller_repair_config_derives_z_gate_from_capture_radius \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py::test_v06e_capture_radius_gate_suppresses_z_until_inside_capture_radius \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py::test_v06e_capture_radius_gate_allows_z_inside_capture_radius \
  -q
```

Expected:

```text
3 passed
```

- [ ] **Step 8: Commit Task 4**

```bash
git add scripts/run_mvp2c_isaac_training_calibration.py scripts/run_mvp2b_isaac_proof_evaluator.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py
git commit -m "Gate MVP-2E z push on measured capture radius" \
  -m "Derive the v0.6e controller repair config from numeric capture_radius_m so off-center seeds cannot descend before entering the measured capture band." \
  -m "Constraint: No horizon increase, retry, search, withdraw, force control, or per-seed tuning." \
  -m "Rejected: generic damping as primary repair | evidence points to off-center early z push causing rim eject." \
  -m "Confidence: high" \
  -m "Scope-risk: narrow" \
  -m "Tested: uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06e_controller_repair_config_derives_z_gate_from_capture_radius apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py::test_v06e_capture_radius_gate_suppresses_z_until_inside_capture_radius apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py::test_v06e_capture_radius_gate_allows_z_inside_capture_radius -q"
```

## Task 5: Wire v0.6e Strict Preflight And Gate Into Repair Probe Runtime

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Test: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add derive gate test with capture radius**

Add this test to `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`:

```python
def test_v06e_repair_probe_gate_from_probe_result_uses_capture_radius(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    trace_dir = tmp_path / "traces"
    trace_dir.mkdir()
    paths = []
    scenarios = [
        (16023, True, [0.002, 0.001, 0.0005]),
        (16042, True, [0.016, 0.004, 0.0004]),
        (16096, False, [0.023, 0.010, 0.0028, 0.0029, 0.0028, 0.0029, 0.0028, 0.0029, 0.0028, 0.0029]),
    ]
    for seed, success, lateral_values in scenarios:
        rows = [
            {
                "step": index,
                "phase": "APPROACH",
                "lateral_error_m": lateral,
                "env_native_success": success,
                "env_native_success_mask": success,
                "env_native_diagnostics_source": "factory_utils_base_target",
                "env_native_xy_dist_m": lateral,
                "env_native_z_disp_m": 0.0 if success else 0.02,
                "env_native_height_threshold_m": 0.001,
                "held_asset_pose_w": {},
                "fixed_asset_pose_w": {},
                "held_base_pose_w": {},
                "target_held_base_pose_w": {},
                "legacy_positive_z_disp_m": 0.0,
                "runtime_depth_feature_m": 0.0,
                "insertion_depth_m": 0.0,
            }
            for index, lateral in enumerate(lateral_values)
        ]
        path = trace_dir / f"seed_{seed}.json"
        script.write_json(
            path,
            {
                "scenario": {"seed": seed},
                "summary": {
                    "env_native_rollout_success": success,
                    "env_native_max_consecutive_success_steps": 10 if success else 0,
                },
                "trace": rows,
            },
        )
        paths.append(str(path))
    probe_result = script.BackendResult(
        runtime_gate={"passed": True},
        rollouts=[],
        baseline_trace_paths=paths,
        candidate_trace_paths=[],
        runtime_backend="isaac_runtime",
        proof_runtime="isaac_scripted_expert_repair_probe",
        runtime_metadata={},
    )

    gate = script.derive_v06_repair_probe_gate_from_probe_result(
        probe_result,
        capture_radius_m=0.003,
    )

    assert gate["schema_version"] == "rdf_mvp2e_v06e_repair_probe_gate_v0.1.0"
    assert gate["green_light_for_40_run_gate"] is True
    assert gate["seed_results"]["16042"]["seed_pass"] is True
    assert gate["seed_results"]["16096"]["seed_pass"] is True
```

- [ ] **Step 2: Run RED test**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06e_repair_probe_gate_from_probe_result_uses_capture_radius -q
```

Expected:

```text
FAILED ... TypeError: derive_v06_repair_probe_gate_from_probe_result() got an unexpected keyword argument 'capture_radius_m'
```

- [ ] **Step 3: Change derive function signature and lateral extraction**

Change function signature:

```python
def derive_v06_repair_probe_gate_from_probe_result(
    probe_result: BackendResult,
    *,
    capture_radius_m: float | None = None,
) -> dict[str, Any]:
```

Inside the loop, preserve raw lateral series in each seed payload:

```python
        probe_results[seed] = {**summary, **divergence, "lateral_errors_m": lateral_errors}
```

After the loop, replace:

```python
    gate = evaluate_v06_repair_probe_gate(probe_results)
```

with:

```python
    if _numeric_capture_radius_m(capture_radius_m) is not None:
        gate = evaluate_v06e_repair_probe_gate(probe_results, capture_radius_m=float(capture_radius_m))
    else:
        gate = evaluate_v06_repair_probe_gate(probe_results)
        gate["v0_6e_numeric_capture_radius_missing"] = True
```

- [ ] **Step 4: Wire strict preflight into runtime**

In `run_v06_repair_probe_runtime()`, after resolving `preflight`, load the probe artifact and validate v0.6e strict numeric preflight:

```python
    capture_probe_path = output_dir / "capture_radius_probe.json"
    if capture_probe_path.exists():
        preflight = validate_v06e_numeric_capture_radius_preflight(
            preflight=preflight,
            capture_radius_probe=read_json(capture_probe_path),
        )
```

Before building `expert_policy`, derive and write controller config:

```python
    capture_radius_m = float(preflight["capture_radius_m"])
    controller_repair_config = build_v06e_controller_repair_config(capture_radius_m=capture_radius_m)
    write_json(output_dir / "controller_repair_config.json", controller_repair_config)
```

Pass config into expert policy:

```python
    expert_policy = _scripted_expert_probe_policy_artifact(
        selected_adapter_id=selected_adapter_id,
        selected_adapter_config=selected_adapter_config,
        scenario_profile="v0_6",
        controller_repair_config=controller_repair_config,
    )
```

Change gate derive call:

```python
    gate = derive_v06_repair_probe_gate_from_probe_result(
        probe_result,
        capture_radius_m=capture_radius_m,
    )
```

Add fields after `gate["chamfer_preflight"] = preflight`:

```python
    gate["controller_repair_config"] = controller_repair_config
    gate["controller_repair_config_sha256"] = controller_repair_config["controller_repair_config_sha256"]
    gate["fixed_40_run_gate_opened"] = False
    gate["heldout_opened"] = False
```

- [ ] **Step 5: Run GREEN test**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06e_repair_probe_gate_from_probe_result_uses_capture_radius -q
```

Expected:

```text
1 passed
```

- [ ] **Step 6: Run focused MVP-2C tests**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 7: Commit Task 5**

```bash
git add scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
git commit -m "Wire MVP-2E repair probe to numeric capture radius" \
  -m "Use v0.6e strict preflight and convergence gate when deriving repair_probe_gate.json, and emit controller_repair_config.json as proof evidence." \
  -m "Constraint: Repair probe remains proof_authority=false and cannot open held-out." \
  -m "Rejected: fallback to approximate capture radius | v0.6e requires numeric geometry grounding." \
  -m "Confidence: high" \
  -m "Scope-risk: moderate" \
  -m "Tested: uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q"
```

## Task 6: Run Verification And Repair-Probe-Only Runtime Evidence

**Files:**
- Runtime artifacts under `/tmp/rdf-mvp2e-v06e-repair-probe-green`
- Modify docs after run in Task 7.

- [ ] **Step 1: Run relevant Python tests**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 2: Run broader MVP proof tests**

Run:

```bash
uv run pytest apps/api/tests/test_mvp1_proof_audit_script.py apps/api/tests/test_mvp1plus_embodiment_proof_script.py apps/api/tests/test_mvp2_learning_sanity_script.py apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py apps/api/tests/test_peg_insert_viability_script.py -q
```

Expected:

```text
all tests passed
```

- [ ] **Step 3: Run compile and lint**

Run:

```bash
uv run python -m compileall -q scripts apps/api/app apps/api/tests
uvx ruff check scripts/run_mvp2b_isaac_proof_evaluator.py scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
git diff --check
```

Expected:

```text
compileall exits 0
ruff exits 0
git diff --check exits 0
```

- [ ] **Step 4: Run capture-radius probe only**

Run:

```bash
rm -rf /tmp/rdf-mvp2e-v06e-repair-probe-green
mkdir -p /tmp/rdf-mvp2e-v06e-repair-probe-green

/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2e-v06e-repair-probe-green \
  --scenario-profile v0_6 \
  --capture-radius-probe-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

Expected:

```text
command exits 0
/tmp/rdf-mvp2e-v06e-repair-probe-green/capture_radius_probe.json exists
/tmp/rdf-mvp2e-v06e-repair-probe-green/capture_radius_preflight_result.json exists
capture_radius_m is numeric
capture_radius_probe_geometry_isolated=true
```

- [ ] **Step 5: Stop if capture radius is not numeric**

Run:

```bash
python - <<'PY'
import json
from pathlib import Path
p = Path("/tmp/rdf-mvp2e-v06e-repair-probe-green/capture_radius_preflight_result.json")
d = json.loads(p.read_text())
preflight = d["chamfer_preflight"]
cap = preflight.get("capture_radius_m")
print("capture_radius_m", cap)
print("repair_probe_allowed", preflight.get("repair_probe_allowed"))
if isinstance(cap, bool) or not isinstance(cap, (int, float)) or cap <= 0:
    raise SystemExit("capture_radius_not_numeric")
PY
```

Expected:

```text
capture_radius_m 0.0002
repair_probe_allowed True
```

The printed numeric value may differ from `0.0002`; the acceptance condition is that it is a positive JSON number. If this command exits nonzero, stop and report `capture_radius_not_numeric`; do not run repair probe.

- [ ] **Step 6: Run repair-probe-only**

Run:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2e-v06e-repair-probe-green \
  --scenario-profile v0_6 \
  --train-generation-probe-only \
  --repair-probe-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

Expected:

```text
command exits 0
/tmp/rdf-mvp2e-v06e-repair-probe-green/repair_probe_gate.json exists
/tmp/rdf-mvp2e-v06e-repair-probe-green/controller_repair_config.json exists
fixed_40_run_gate_opened=false
heldout_opened=false
```

- [ ] **Step 7: Summarize runtime evidence**

Run:

```bash
python - <<'PY'
import json
from pathlib import Path
p = Path("/tmp/rdf-mvp2e-v06e-repair-probe-green/repair_probe_gate.json")
d = json.loads(p.read_text())
print("green_light_for_40_run_gate", d.get("green_light_for_40_run_gate"))
print("hard_stop", d.get("hard_stop"))
print("fixed_40_run_gate_opened", d.get("fixed_40_run_gate_opened"))
print("heldout_opened", d.get("heldout_opened"))
print("capture_radius_m", d.get("capture_radius_m") or (d.get("chamfer_preflight") or {}).get("capture_radius_m"))
for seed, result in sorted((d.get("seed_results") or d.get("probe_results") or {}).items()):
    print(seed, result.get("env_native_seed_pass"), result.get("seed_pass"), result.get("env_native_max_consecutive_success_steps"), result.get("failure_reason"))
PY
```

Expected:

```text
fixed_40_run_gate_opened False
heldout_opened False
```

`green_light_for_40_run_gate` may be true or false. If false, report the seed-level blocker and stop. Do not run 40-run gate.

## Task 7: Update Documentation And Handoff

**Files:**
- Modify: `docs/developer/worklog.md`
- Modify: `docs/developer/debugging_guide.md`
- Modify: `tasks/todo.md`
- Modify: `Handoff.md`

- [ ] **Step 1: Append worklog entry**

Append this structure to `docs/developer/worklog.md` with the actual command outputs from Task 6:

````markdown
## 2026-06-11 - MVP-2E v0.6e repair probe green implementation

### 작업 내용

- v0.6e numeric capture-radius preflight validation을 구현했다.
- env-native pass를 secondary diagnostic이 veto하지 못하도록 repair probe gate를 재정의했다.
- non-seated lateral convergence를 near-band + no-regression rule로 재정의했다.
- capture-radius-derived z-push gate를 controller config에 연결했다.

### 판단 이유

- v0.6d에서 16042는 env-native success를 달성했지만 secondary divergence diagnostic 때문에 false fail이었다.
- 16096은 off-center early z push로 rim-eject drift-back-out이 발생했다.

### 변경 파일

```text
scripts/run_mvp2c_isaac_training_calibration.py
scripts/run_mvp2b_isaac_proof_evaluator.py
apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py
docs/developer/worklog.md
docs/developer/debugging_guide.md
tasks/todo.md
Handoff.md
```

### 검증 결과

- Task 6 Step 1의 pytest 명령과 실제 pass/fail 요약을 그대로 기록한다.
- Task 6 Step 2의 broader MVP proof pytest 명령과 실제 pass/fail 요약을 그대로 기록한다.
- Task 6 Step 3의 compileall, ruff, `git diff --check` 결과를 그대로 기록한다.
- Task 6 Step 5의 `capture_radius_m`과 `repair_probe_allowed` 출력값을 그대로 기록한다.
- Task 6 Step 7의 `green_light_for_40_run_gate`, `hard_stop`, `fixed_40_run_gate_opened`, `heldout_opened`, seed별 출력값을 그대로 기록한다.

### 남은 gap 또는 다음 작업

- If repair_probe_green_light=true: next valid step is fixed 40-run train-generation gate.
- If repair_probe_green_light=false: next valid step is the reported seed-level blocker.
- held-out 21000-21049 remains sealed.
```
````

- [ ] **Step 2: Update debugging guide**

Add a section named:

```markdown
## MVP-2E v0.6e repair probe green
```

Include:

```text
capture-radius command
repair-probe-only command
artifact paths
green/fail interpretation
explicit ban on fixed 40-run and held-out before green
```

- [ ] **Step 3: Update tasks/todo**

Add checklist:

```markdown
### 2026-06-11 follow-up: MVP-2E v0.6e repair probe green implementation

- [x] Numeric capture-radius preflight validation implemented.
- [x] Env-native authority cannot be vetoed by secondary diagnostics.
- [x] Non-seated lateral convergence uses near-band + no-regression.
- [x] Controller z-push gate is derived from capture_radius_m.
- [x] Repair-probe-only runtime executed.
- [ ] Fixed 40-run train gate remains closed until green.
- [ ] Held-out 21000-21049 remains sealed.
```

- [ ] **Step 4: Update Handoff**

Add:

````markdown
## 2026-06-11 - Session Update: MVP-2E v0.6e implementation

Current truth:
- MVP-2 is still not Closed.
- v0.6e repair probe result: set to the actual `green_light_for_40_run_gate` and `hard_stop` values from `/tmp/rdf-mvp2e-v06e-repair-probe-green/repair_probe_gate.json`.
- Fixed 40-run gate opened: false.
- Held-out 21000-21049 opened: false.

Artifacts:
- /tmp/rdf-mvp2e-v06e-repair-probe-green/capture_radius_probe.json
- /tmp/rdf-mvp2e-v06e-repair-probe-green/capture_radius_preflight_result.json
- /tmp/rdf-mvp2e-v06e-repair-probe-green/controller_repair_config.json
- /tmp/rdf-mvp2e-v06e-repair-probe-green/repair_probe_gate.json
```
````

- [ ] **Step 5: Commit docs**

```bash
git add docs/developer/worklog.md docs/developer/debugging_guide.md tasks/todo.md
git commit -m "Record MVP-2E repair probe green evidence" \
  -m "Document the v0.6e repair-probe-only result and preserve the remaining MVP-2 gate boundary." \
  -m "Constraint: Handoff.md is gitignored and updated locally." \
  -m "Confidence: high" \
  -m "Scope-risk: narrow" \
  -m "Tested: documentation updated from fresh verification output."
```

## Task 8: Final Verification

**Files:**
- Verify entire changed set.

- [ ] **Step 1: Run final tests**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q
uv run pytest apps/api/tests/test_mvp1_proof_audit_script.py apps/api/tests/test_mvp1plus_embodiment_proof_script.py apps/api/tests/test_mvp2_learning_sanity_script.py apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py apps/api/tests/test_peg_insert_viability_script.py -q
uv run python -m compileall -q scripts apps/api/app apps/api/tests
uvx ruff check scripts/run_mvp2b_isaac_proof_evaluator.py scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
git diff --check
```

Expected:

```text
all commands exit 0
```

- [ ] **Step 2: Check worktree**

Run:

```bash
git status --short
git status --ignored --short Handoff.md AGENTS.md
```

Expected:

```text
tracked worktree clean after commits
Handoff.md may show as ignored
AGENTS.md may be clean or runtime-dirtied; stash runtime-only AGENTS.md before final if needed
```

## Self-Review

Spec coverage:

```text
Authority layer: Task 1, Task 2, Task 5
Capture-radius numeric preflight: Task 3, Task 6
Geometry-isolated capture probe evidence: Task 3, Task 6
Convergence/no-regression rule: Task 1, Task 2, Task 5
Capture-radius z-push gate: Task 4, Task 5
Overfit guard: Task 4, Task 6 stop conditions
Green rule: Task 1, Task 2, Task 5, Task 6
Docs/handoff: Task 7
Final verification: Task 8
```

Self-review red-flag scan:

```text
Checked for unresolved plan tokens and angle-bracket fields after writing the plan.
The final scan should return no unresolved execution tokens outside this self-review note.
```
