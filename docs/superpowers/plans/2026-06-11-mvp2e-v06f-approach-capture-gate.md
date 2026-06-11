# MVP-2E v0.6f Approach Capture Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the pre-registered v0.6f approach capture gate so repair-probe-only execution can test controller-assisted descent without opening the fixed 40-run train gate or held-out `21000-21049`.

**Architecture:** Preserve `capture_radius_m` as straight-down geometry evidence, add a separate controller-assisted `approach_lateral_gate_m`, and keep env-native 10-consecutive success as the only seed pass authority. The change stays inside the existing MVP-2B/MVP-2C scripts and tests; v0.6e artifacts remain historical fail-closed evidence.

**Tech Stack:** Python 3.11, pytest, Isaac Lab runtime through `/home/kangrim/IsaacLab/_isaac_sim/python.sh`, JSON artifacts, existing scripts under `scripts/`, existing tests under `apps/api/tests/`.

---

## Source Spec

Implement exactly this spec:

```text
docs/superpowers/specs/2026-06-11-mvp2e-v06f-approach-capture-gate-design.md
```

Do not implement broader MVP-2 closure. The only allowed runtime proof in this plan is capture-radius preflight reuse/execution and repair-probe-only execution.

## File Structure

- Modify `scripts/run_mvp2c_isaac_training_calibration.py`
  - Add v0.6f constants.
  - Add `build_v06f_controller_repair_config`.
  - Add v0.6f non-seated convergence evaluation using `approach_lateral_gate_m`.
  - Add v0.6f repair probe gate evaluation.
  - Add a CLI selector `--repair-probe-controller-version` with allowed values `v0_6e` and `v0_6f`.
  - Wire v0.6f config into repair-probe runtime only when explicitly selected.
  - Emit both `straight_down_capture_radius_m` and `approach_lateral_gate_m`.
- Modify `scripts/run_mvp2b_isaac_proof_evaluator.py`
  - Keep existing action adapter behavior; it already gates z by `align_lateral_gate_m`.
  - Ensure diagnostics can expose `approach_lateral_gate_m` when present.
- Modify `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
  - Add unit tests for v0.6f config derivation, gate evaluation, CLI version validation, and no held-out scheduling.
- Modify `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
  - Add a unit test proving the action adapter permits z descent at `approach_lateral_gate_m` while retaining z suppression outside it.
- Modify docs after implementation:
  - `docs/developer/worklog.md`
  - `docs/developer/debugging_guide.md`
  - `tasks/todo.md`
  - `Handoff.md`

## Stop Conditions

Stop and report if any condition is hit.

```text
capture_radius_m is not numeric
approach_lateral_gate_m cannot be computed before repair probe
repair probe requires held-out 21000-21049
repair probe requires fixed 40-run train gate
controller repair requires horizon increase
controller repair requires retry/search/withdraw/force-control
controller repair requires per-seed grid search over 16023/16042/16096
16023 loses env-native pass
all lateral seeds fail env-native
all probe seeds remain max_insertion_depth_m=0
```

## Task 1: Add RED Tests For v0.6f Config Derivation

**Files:**
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
- Later modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Add test after `test_v06e_controller_repair_config_derives_z_gate_from_capture_radius`**

```python
def test_v06f_controller_repair_config_uses_approach_gate_not_raw_capture_radius() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    config = script.build_v06f_controller_repair_config(capture_radius_m=0.0001)

    assert config["schema_version"] == "rdf_mvp2e_v06f_controller_repair_config_v0.1.0"
    assert config["straight_down_capture_radius_m"] == 0.0001
    assert config["approach_lateral_gate_m"] == 0.001
    assert config["align_lateral_gate_m"] == 0.001
    assert config["z_push_gate"] == "lateral_error_m <= approach_lateral_gate_m"
    assert config["success_authority"] == "env_native_10_consecutive"
    assert config["proof_authority"] is False
    assert config["horizon_increase"] is False
    assert config["retry_enabled"] is False
    assert config["search_enabled"] is False
    assert config["force_control_enabled"] is False
```

- [ ] **Step 2: Add multiplier/floor test**

```python
def test_v06f_approach_gate_uses_capture_multiplier_above_floor() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    config = script.build_v06f_controller_repair_config(capture_radius_m=0.0004)

    assert config["straight_down_capture_radius_m"] == 0.0004
    assert config["approach_lateral_gate_m"] == 0.004
    assert config["approach_gate_floor_m"] == 0.001
    assert config["approach_gate_capture_multiplier"] == 10.0
```

- [ ] **Step 3: Run RED tests**

Run:

```bash
uv run pytest \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06f_controller_repair_config_uses_approach_gate_not_raw_capture_radius \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06f_approach_gate_uses_capture_multiplier_above_floor \
  -q
```

Expected:

```text
FAILED ... AttributeError: module 'run_mvp2c_isaac_training_calibration' has no attribute 'build_v06f_controller_repair_config'
```

## Task 2: Implement v0.6f Config Helper

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Test: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add constants near existing v0.6e constants**

```python
V06F_APPROACH_GATE_FLOOR_M = 0.001
V06F_APPROACH_GATE_CAPTURE_MULTIPLIER = 10.0
V06F_REGRESSION_TOL_FLOOR_M = 0.0005
V06F_REGRESSION_TOL_APPROACH_RATIO = 0.5
```

- [ ] **Step 2: Add approach gate helper after `_numeric_capture_radius_m`**

```python
def _v06f_approach_lateral_gate_m(capture_radius_m: float) -> float:
    numeric_capture_radius = _numeric_capture_radius_m(capture_radius_m)
    if numeric_capture_radius is None:
        raise ValueError("v0_6f approach gate requires numeric capture_radius_m")
    return max(
        V06F_APPROACH_GATE_FLOOR_M,
        V06F_APPROACH_GATE_CAPTURE_MULTIPLIER * numeric_capture_radius,
    )
```

- [ ] **Step 3: Add config builder after `build_v06e_controller_repair_config`**

```python
def build_v06f_controller_repair_config(*, capture_radius_m: float) -> dict[str, Any]:
    numeric_capture_radius = _numeric_capture_radius_m(capture_radius_m)
    if numeric_capture_radius is None:
        raise ValueError("v0_6f controller repair config requires numeric capture_radius_m")
    approach_gate = _v06f_approach_lateral_gate_m(numeric_capture_radius)
    config = {
        "schema_version": "rdf_mvp2e_v06f_controller_repair_config_v0.1.0",
        "controller_repair_version": "v0_6f",
        "straight_down_capture_radius_m": round(float(numeric_capture_radius), 6),
        "capture_radius_m": round(float(numeric_capture_radius), 6),
        "approach_lateral_gate_m": round(float(approach_gate), 6),
        "align_lateral_gate_m": round(float(approach_gate), 6),
        "approach_gate_floor_m": V06F_APPROACH_GATE_FLOOR_M,
        "approach_gate_capture_multiplier": V06F_APPROACH_GATE_CAPTURE_MULTIPLIER,
        "approach_lateral_gate_source": "pre_registered_controller_assisted_approach_gate_v0_6f",
        "z_push_gate": "lateral_error_m <= approach_lateral_gate_m",
        "success_authority": "env_native_10_consecutive",
        "proof_authority": False,
        "straight_down_capture_radius_is_lower_bound": True,
        "horizon_increase": False,
        "retry_enabled": False,
        "search_enabled": False,
        "withdraw_enabled": False,
        "force_control_enabled": False,
        "per_seed_tuning": False,
        "non_claims": dict(V06A_NON_CLAIMS),
    }
    config["controller_repair_config_sha256"] = _sha256_payload_excluding(config, "controller_repair_config_sha256")
    return config
```

- [ ] **Step 4: Run GREEN tests**

Run:

```bash
uv run pytest \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06f_controller_repair_config_uses_approach_gate_not_raw_capture_radius \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06f_approach_gate_uses_capture_multiplier_above_floor \
  -q
```

Expected:

```text
2 passed
```

## Task 3: Add RED Tests For v0.6f Non-seated Convergence And Gate

**Files:**
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
- Later modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Add convergence test after v0.6e convergence tests**

```python
def test_v06f_non_seated_convergence_uses_approach_gate_not_straight_down_capture() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    converged = script.evaluate_v06f_non_seated_lateral_convergence(
        lateral_errors_m=[0.016, 0.009, 0.003, 0.0012, 0.0009, 0.0008, 0.0009, 0.0009, 0.0008, 0.0009],
        capture_radius_m=0.0001,
        last_k=5,
    )

    assert converged["non_seated_lateral_converged"] is True
    assert converged["straight_down_capture_radius_m"] == 0.0001
    assert converged["near_band_m"] == 0.001
    assert converged["last_k_median_lateral_m"] <= 0.001
    assert converged["regression_detected"] is False

    regressed = script.evaluate_v06f_non_seated_lateral_convergence(
        lateral_errors_m=[0.023, 0.006, 0.0008, 0.002, 0.004, 0.006, 0.0065, 0.0063, 0.0064, 0.0062],
        capture_radius_m=0.0001,
        last_k=5,
    )

    assert regressed["non_seated_lateral_converged"] is False
    assert regressed["regression_detected"] is True
```

- [ ] **Step 2: Add gate test**

```python
def test_v06f_repair_probe_gate_keeps_env_native_authority_and_uses_approach_convergence() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    gate = script.evaluate_v06f_repair_probe_gate(
        {
            16023: {
                "env_native_rollout_success": True,
                "env_native_max_consecutive_success_steps": 10,
                "max_insertion_depth_m": 0.03,
            },
            16042: {
                "env_native_rollout_success": True,
                "env_native_max_consecutive_success_steps": 10,
                "lateral_divergence_stopped": False,
                "max_insertion_depth_m": 0.03,
            },
            16096: {
                "env_native_rollout_success": False,
                "env_native_max_consecutive_success_steps": 0,
                "lateral_errors_m": [0.023, 0.009, 0.003, 0.0012, 0.0009, 0.0008, 0.0009, 0.0009, 0.0008, 0.0009],
                "max_insertion_depth_m": 0.0,
            },
        },
        capture_radius_m=0.0001,
    )

    assert gate["green_light_for_40_run_gate"] is True
    assert gate["hard_stop"] is False
    assert gate["straight_down_capture_radius_m"] == 0.0001
    assert gate["approach_lateral_gate_m"] == 0.001
    assert gate["seed_results"]["16042"]["divergence_diagnostic_authority"] == "report_only"
    assert gate["seed_results"]["16096"]["convergence"]["non_seated_lateral_converged"] is True
```

- [ ] **Step 3: Add all-depth-zero hard-stop test**

```python
def test_v06f_repair_probe_gate_blocks_when_all_probe_seeds_never_descend() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    gate = script.evaluate_v06f_repair_probe_gate(
        {
            16023: {
                "env_native_rollout_success": False,
                "env_native_max_consecutive_success_steps": 0,
                "lateral_errors_m": [0.0003, 0.0002, 0.0002],
                "max_insertion_depth_m": 0.0,
            },
            16042: {
                "env_native_rollout_success": False,
                "env_native_max_consecutive_success_steps": 0,
                "lateral_errors_m": [0.0011, 0.0009, 0.0009],
                "max_insertion_depth_m": 0.0,
            },
            16096: {
                "env_native_rollout_success": False,
                "env_native_max_consecutive_success_steps": 0,
                "lateral_errors_m": [0.0012, 0.0008, 0.0008],
                "max_insertion_depth_m": 0.0,
            },
        },
        capture_radius_m=0.0001,
    )

    assert gate["green_light_for_40_run_gate"] is False
    assert gate["hard_stop"] is True
    assert gate["failure_mode"] == "all_probe_seeds_never_descended"
```

- [ ] **Step 4: Run RED tests**

Run:

```bash
uv run pytest \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06f_non_seated_convergence_uses_approach_gate_not_straight_down_capture \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06f_repair_probe_gate_keeps_env_native_authority_and_uses_approach_convergence \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06f_repair_probe_gate_blocks_when_all_probe_seeds_never_descend \
  -q
```

Expected:

```text
FAILED ... AttributeError: module 'run_mvp2c_isaac_training_calibration' has no attribute 'evaluate_v06f_non_seated_lateral_convergence'
FAILED ... AttributeError: module 'run_mvp2c_isaac_training_calibration' has no attribute 'evaluate_v06f_repair_probe_gate'
```

## Task 4: Implement v0.6f Convergence And Gate Helpers

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Test: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add convergence evaluator after `evaluate_v06e_non_seated_lateral_convergence`**

```python
def evaluate_v06f_non_seated_lateral_convergence(
    *,
    lateral_errors_m: Sequence[float],
    capture_radius_m: float,
    last_k: int = V06E_CONVERGENCE_LAST_K,
    regression_tol_floor_m: float = V06F_REGRESSION_TOL_FLOOR_M,
    regression_tol_approach_ratio: float = V06F_REGRESSION_TOL_APPROACH_RATIO,
) -> dict[str, Any]:
    numeric_capture_radius = _numeric_capture_radius_m(capture_radius_m)
    if numeric_capture_radius is None:
        return {
            "non_seated_lateral_converged": False,
            "reason": "capture_radius_not_numeric",
            "capture_radius_m": capture_radius_m,
        }
    approach_gate = _v06f_approach_lateral_gate_m(numeric_capture_radius)
    if not lateral_errors_m:
        return {
            "non_seated_lateral_converged": False,
            "reason": "missing_lateral_diagnostics",
            "straight_down_capture_radius_m": numeric_capture_radius,
            "near_band_m": approach_gate,
        }
    values = [float(value) for value in lateral_errors_m]
    window = values[-max(1, int(last_k)) :]
    min_lateral = min(values)
    tail_median = statistics.median(window)
    regression_tol = max(float(regression_tol_floor_m), float(regression_tol_approach_ratio) * approach_gate)
    inside_near_band = tail_median <= approach_gate
    no_regression = tail_median <= min_lateral + regression_tol
    return {
        "non_seated_lateral_converged": bool(inside_near_band and no_regression),
        "reason": "converged_to_approach_gate_no_regression"
        if inside_near_band and no_regression
        else "not_converged_or_regressed",
        "straight_down_capture_radius_m": round(float(numeric_capture_radius), 6),
        "capture_radius_m": round(float(numeric_capture_radius), 6),
        "near_band_m": round(float(approach_gate), 6),
        "approach_lateral_gate_m": round(float(approach_gate), 6),
        "last_k": int(last_k),
        "regression_tol_m": round(float(regression_tol), 6),
        "min_lateral_achieved_m": round(float(min_lateral), 6),
        "last_k_median_lateral_m": round(float(tail_median), 6),
        "inside_near_band": bool(inside_near_band),
        "regression_detected": not bool(no_regression),
    }
```

- [ ] **Step 2: Add max-depth helper after `_v06e_lateral_errors_from_probe_result`**

```python
def _v06_max_insertion_depth_m(result: dict[str, Any]) -> float:
    value = result.get("max_insertion_depth_m", result.get("max_depth_m", result.get("max_insertion_depth_observed_m", 0.0)))
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
```

- [ ] **Step 3: Add v0.6f repair gate after `evaluate_v06e_repair_probe_gate`**

```python
def evaluate_v06f_repair_probe_gate(
    probe_results: dict[Any, Any],
    *,
    capture_radius_m: float,
) -> dict[str, Any]:
    numeric_capture_radius = _numeric_capture_radius_m(capture_radius_m)
    approach_gate = _v06f_approach_lateral_gate_m(capture_radius_m) if numeric_capture_radius is not None else None
    normalized = _normalize_v06_repair_probe_results(probe_results)
    seed_results: dict[str, dict[str, Any]] = {}
    non_seated_lateral_converged = True
    lateral_env_native_pass_count = 0
    all_depths = []

    for seed, result in normalized.items():
        env_native_pass = bool(result.get("env_native_rollout_success")) or int(
            result.get("env_native_max_consecutive_success_steps", 0)
        ) >= V06_ENV_NATIVE_STABLE_STEPS_REQUIRED
        max_depth = _v06_max_insertion_depth_m(result)
        all_depths.append(max_depth)
        is_lateral_seed = seed in {16042, 16096}
        seed_payload = {
            **result,
            "env_native_seed_pass": env_native_pass,
            "seed_pass": env_native_pass,
            "max_insertion_depth_m": max_depth,
            "divergence_diagnostic_authority": "report_only" if env_native_pass else "non_seated_lateral_gate",
        }
        if env_native_pass and is_lateral_seed:
            lateral_env_native_pass_count += 1
        if (not env_native_pass) and is_lateral_seed:
            convergence = evaluate_v06f_non_seated_lateral_convergence(
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
    all_never_descended = all(depth <= 0.0 for depth in all_depths)
    green = (
        numeric_capture_radius is not None
        and hold_passed
        and lateral_env_native_pass_count >= 1
        and non_seated_lateral_converged
        and not all_never_descended
        and all(bool(payload["seed_pass"]) for payload in seed_results.values())
    )
    result = {
        "schema_version": "rdf_mvp2e_v06f_repair_probe_gate_v0.1.0",
        "proof_authority": False,
        "success_authority": "env_native_10_consecutive",
        "straight_down_capture_radius_m": numeric_capture_radius if numeric_capture_radius is not None else capture_radius_m,
        "capture_radius_m": numeric_capture_radius if numeric_capture_radius is not None else capture_radius_m,
        "approach_lateral_gate_m": approach_gate,
        "probe_seeds": list(V06_REPAIR_PROBE_SEEDS),
        "hold_mode_passed": hold_passed,
        "lateral_success_mode_passed": lateral_env_native_pass_count >= 1,
        "non_seated_lateral_converged": non_seated_lateral_converged,
        "all_probe_seeds_never_descended": all_never_descended,
        "green_light_for_40_run_gate": bool(green),
        "hard_stop": not bool(green),
        "failure_mode": None if green else (
            "all_probe_seeds_never_descended" if all_never_descended else "repair_probe_not_green"
        ),
        "seed_results": seed_results,
        "fixed_40_run_gate_opened": False,
        "heldout_opened": False,
    }
    result["repair_probe_gate_sha256"] = _sha256_payload_excluding(result, "repair_probe_gate_sha256")
    return result
```

- [ ] **Step 4: Run GREEN tests**

Run:

```bash
uv run pytest \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06f_non_seated_convergence_uses_approach_gate_not_straight_down_capture \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06f_repair_probe_gate_keeps_env_native_authority_and_uses_approach_convergence \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06f_repair_probe_gate_blocks_when_all_probe_seeds_never_descend \
  -q
```

Expected:

```text
3 passed
```

## Task 5: Wire Controller Version Selection Into Repair Probe Runtime

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Test: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add CLI parser option near `--repair-probe-only`**

```python
parser.add_argument(
    "--repair-probe-controller-version",
    choices=("v0_6e", "v0_6f"),
    default="v0_6e",
    help="Controller repair config version for repair-probe-only execution.",
)
```

- [ ] **Step 2: Change `run_v06_repair_probe_runtime` signature**

```python
def run_v06_repair_probe_runtime(
    *,
    output_dir: Path,
    manifest: dict[str, Any],
    isaac_task: str,
    device: str,
    headless: bool,
    repair_probe_controller_version: str = "v0_6e",
) -> dict[str, Any]:
```

- [ ] **Step 3: Select config and gate by version after `capture_radius_m = float(preflight["capture_radius_m"])`**

```python
if repair_probe_controller_version == "v0_6f":
    controller_repair_config = build_v06f_controller_repair_config(capture_radius_m=capture_radius_m)
else:
    controller_repair_config = build_v06e_controller_repair_config(capture_radius_m=capture_radius_m)
```

- [ ] **Step 4: Select final gate after Isaac probe result**

```python
if repair_probe_controller_version == "v0_6f":
    gate = evaluate_v06f_repair_probe_gate(probe_results, capture_radius_m=capture_radius_m)
else:
    gate = derive_v06_repair_probe_gate_from_probe_result(
        probe_result=probe_result,
        preflight=preflight,
        capture_radius_m=capture_radius_m,
    )
```

- [ ] **Step 5: Preserve required shared fields**

After gate selection and before writing `repair_probe_gate.json`, ensure:

```python
gate["controller_repair_version"] = repair_probe_controller_version
gate["controller_repair_config"] = controller_repair_config
gate["chamfer_preflight"] = preflight
gate["fixed_40_run_gate_opened"] = False
gate["heldout_opened"] = False
gate["repair_probe_gate_sha256"] = _sha256_payload_excluding(gate, "repair_probe_gate_sha256")
```

- [ ] **Step 6: Pass CLI value from `main`**

```python
gate = run_v06_repair_probe_runtime(
    output_dir=output_dir,
    manifest=manifest,
    isaac_task=args.isaac_task,
    device=args.device,
    headless=not args.no_headless,
    repair_probe_controller_version=args.repair_probe_controller_version,
)
```

- [ ] **Step 7: Add focused runtime-selection unit test**

```python
def test_v06f_repair_probe_config_can_be_selected_without_opening_train_or_heldout() -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    config = script.build_v06f_controller_repair_config(capture_radius_m=0.0001)

    assert config["controller_repair_version"] == "v0_6f"
    assert config["align_lateral_gate_m"] == 0.001
    assert config["proof_authority"] is False
    assert config["non_claims"]["real_robot_success"] is False
```

- [ ] **Step 8: Run focused tests**

Run:

```bash
uv run pytest \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06f_repair_probe_config_can_be_selected_without_opening_train_or_heldout \
  -q
```

Expected:

```text
1 passed
```

## Task 6: Add Action Adapter Diagnostic Test For Approach Gate

**Files:**
- Modify: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
- Test existing implementation in `scripts/run_mvp2b_isaac_proof_evaluator.py`

- [ ] **Step 1: Add test after `test_v06e_capture_radius_gate_allows_z_inside_capture_radius`**

```python
def test_v06f_approach_gate_allows_z_inside_approach_gate_without_claiming_success() -> None:
    script = load_script("run_mvp2b_isaac_proof_evaluator")

    adapter = script.ScriptedPegInsertExpertAdapter(
        {
            "controller_repair_version": "v0_6f",
            "straight_down_capture_radius_m": 0.0001,
            "approach_lateral_gate_m": 0.001,
            "align_lateral_gate_m": 0.001,
            "z_push_gate": "lateral_error_m <= approach_lateral_gate_m",
        }
    )

    outside = adapter.action_for_state(
        {
            "phase": "APPROACH",
            "relative_x_m": 0.0012,
            "relative_y_m": 0.0,
            "insertion_depth_m": 0.0,
            "orientation_error_deg": 0.0,
        }
    )
    inside = adapter.action_for_state(
        {
            "phase": "APPROACH",
            "relative_x_m": 0.0009,
            "relative_y_m": 0.0,
            "insertion_depth_m": 0.0,
            "orientation_error_deg": 0.0,
        }
    )

    assert outside["diagnostics"]["z_motion_suppressed"] is True
    assert outside["diagnostics"]["block_reason"] == "alignment_gate_not_satisfied"
    assert inside["diagnostics"]["z_motion_suppressed"] is False
    assert inside["diagnostics"]["align_lateral_gate_m"] == 0.001
```

- [ ] **Step 2: Run focused test**

Run:

```bash
uv run pytest \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py::test_v06f_approach_gate_allows_z_inside_approach_gate_without_claiming_success \
  -q
```

Expected:

```text
1 passed
```

## Task 7: Run Local Verification Before Runtime

**Files:**
- No file edits.

- [ ] **Step 1: Run focused MVP-2B/MVP-2C tests**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q
```

Expected:

```text
All tests pass.
```

- [ ] **Step 2: Run compile and lint**

Run:

```bash
uv run python -m compileall -q scripts apps/api/app apps/api/tests
uvx ruff check scripts/run_mvp2b_isaac_proof_evaluator.py scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
git diff --check
```

Expected:

```text
No output from compileall.
All checks passed!
No whitespace errors.
```

## Task 8: Run v0.6f Runtime Probe Only

**Files:**
- Runtime artifacts under `/tmp/rdf-mvp2e-v06f-approach-capture-gate`.

- [ ] **Step 1: Run capture-radius preflight into a new output directory**

Run:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2e-v06f-approach-capture-gate \
  --scenario-profile v0_6 \
  --capture-radius-probe-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

Expected:

```text
capture_radius_preflight_result.json exists.
capture_radius_m is a positive JSON number.
heldout_schedule.scheduled=false.
```

- [ ] **Step 2: Run repair-probe-only with v0.6f controller**

Run:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2e-v06f-approach-capture-gate \
  --scenario-profile v0_6 \
  --train-generation-probe-only \
  --repair-probe-only \
  --repair-probe-controller-version v0_6f \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

Expected:

```text
repair_probe_gate.json exists.
fixed_40_run_gate_opened=false.
heldout_opened=false.
```

- [ ] **Step 3: Summarize runtime evidence**

Run:

```bash
uv run python - <<'PY'
import json
from pathlib import Path
root = Path("/tmp/rdf-mvp2e-v06f-approach-capture-gate")
gate = json.loads((root / "repair_probe_gate.json").read_text())
print("green_light_for_40_run_gate=", gate.get("green_light_for_40_run_gate"))
print("hard_stop=", gate.get("hard_stop"))
print("fixed_40_run_gate_opened=", gate.get("fixed_40_run_gate_opened"))
print("heldout_opened=", gate.get("heldout_opened"))
print("approach_lateral_gate_m=", gate.get("approach_lateral_gate_m"))
for seed, result in gate.get("seed_results", {}).items():
    print(seed, result.get("env_native_seed_pass"), result.get("seed_pass"), result.get("env_native_max_consecutive_success_steps"), result.get("max_insertion_depth_m"), result.get("failure_reason"))
PY
```

Expected:

```text
The output is copied into docs/developer/worklog.md and Handoff.md.
```

- [ ] **Step 4: Apply stop condition**

If `green_light_for_40_run_gate=false`, stop without running fixed 40-run gate.

If `green_light_for_40_run_gate=true`, stop and report that the next separate valid milestone is fixed 40-run train-generation gate. Do not run it inside this plan unless a new explicit plan covers it.

## Task 9: Update Documentation

**Files:**
- Modify: `docs/developer/worklog.md`
- Modify: `docs/developer/debugging_guide.md`
- Modify: `tasks/todo.md`
- Modify: `Handoff.md`

- [ ] **Step 1: Append worklog entry**

Add a dated `2026-06-11` entry containing:

```text
작업:
  MVP-2E v0.6f approach capture gate implemented and runtime probe executed.

판단:
  v0.6e capture_radius_m=0.0001 is preserved as straight-down lower bound.
  v0.6f uses separately pre-registered approach_lateral_gate_m for controller-assisted z descent.
  env-native 10-consecutive remains the only seed pass authority.

검증:
  <copy exact commands and results from Tasks 7 and 8>

남은 gap:
  If green=false: fixed 40-run gate remains closed and next work is controller diagnosis.
  If green=true: next work is separate fixed 40-run train-generation gate plan.
```

- [ ] **Step 2: Update debugging guide**

Add a section:

```markdown
### MVP-2E v0.6f repair probe 해석

- `straight_down_capture_radius_m`은 geometry-only lower bound다.
- `approach_lateral_gate_m`은 controller-assisted z descent gate다.
- `env_native_max_consecutive_success_steps >= 10`만 seed pass authority다.
- `green_light_for_40_run_gate=false`이면 held-out을 열지 않는다.
```

- [ ] **Step 3: Update tasks/todo**

Record:

```text
MVP-2E v0.6f:
  [x] spec/plan
  [x] implementation
  [x] repair-probe-only runtime evidence
  [ ] fixed 40-run train gate (blocked until green)
  [ ] held-out 21000-21049 (sealed)
```

- [ ] **Step 4: Update Handoff**

Record:

```text
v0.6f result:
  path: /tmp/rdf-mvp2e-v06f-approach-capture-gate/repair_probe_gate.json
  green_light_for_40_run_gate=<actual>
  hard_stop=<actual>
  fixed_40_run_gate_opened=false
  heldout_opened=false
  next valid milestone=<actual based on green>
```

## Task 10: Final Verification And Commit

**Files:**
- All changed files.

- [ ] **Step 1: Run final verification**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q
uv run python -m compileall -q scripts apps/api/app apps/api/tests
uvx ruff check scripts/run_mvp2b_isaac_proof_evaluator.py scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
git diff --check
```

Expected:

```text
All commands pass.
```

- [ ] **Step 2: Inspect worktree**

Run:

```bash
git status --short
```

Expected:

```text
Only intended tracked changes are present.
```

- [ ] **Step 3: Commit**

Use a Lore commit message:

```bash
git add \
  scripts/run_mvp2c_isaac_training_calibration.py \
  scripts/run_mvp2b_isaac_proof_evaluator.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  docs/developer/worklog.md \
  docs/developer/debugging_guide.md \
  tasks/todo.md

git commit -m "Separate approach gating from straight-down capture evidence" \
  -m "Constraint: Held-out 21000-21049 and fixed 40-run gate remain closed until repair probe is green." \
  -m "Rejected: direct straight-down capture radius as controller z gate | v0.6e showed it suppresses descent for all repair probe seeds." \
  -m "Confidence: medium" \
  -m "Scope-risk: moderate" \
  -m "Directive: Do not treat v0.6f repair probe evidence as MVP-2 Closed evidence; it only gates the later fixed 40-run train-generation run." \
  -m "Tested: <exact final verification commands and runtime result>" \
  -m "Not-tested: Fixed 40-run train gate and held-out policy A/B remain intentionally unopened."
```

`Handoff.md` is gitignored; keep it updated locally but do not force-add it.

## Self-Review

Spec coverage:

```text
Authority layer: Tasks 3, 4, 8
Capture radius lower-bound semantics: Tasks 1, 2, 9
Approach gate derivation: Tasks 1, 2
Controller runtime wiring: Task 5
Action adapter gate behavior: Task 6
Runtime fail-closed evidence: Task 8
Docs/handoff: Task 9
Verification: Task 10
```

Placeholder scan:

```text
No incomplete-marker tokens. Every task has concrete files, code, commands, and expected outcomes.
```

Execution boundary:

```text
This plan stops after repair-probe-only runtime evidence.
It does not run fixed 40-run train gate or held-out evaluation.
```
