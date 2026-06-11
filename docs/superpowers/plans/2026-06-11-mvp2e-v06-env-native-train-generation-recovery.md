# MVP-2E v0.6 Env-native Train-generation Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fresh `v0_6` MVP-2E profile that proves env-native Isaac train-generation readiness through chamfer preflight, repair probe, and a fixed 40-seed train gate before any held-out A/B is opened.

**Architecture:** Keep `v0_5` as a historical fail-closed profile and add `v0_6` beside it. The implementation adds explicit success-authority helpers, seed selection helpers, preflight/probe gates, and state-based scripted expert behavior while preserving existing report compatibility.

**Tech Stack:** Python 3.11, pytest, Isaac Lab runtime via `/home/kangrim/IsaacLab/_isaac_sim/python.sh`, JSON proof artifacts, existing RDF scripts under `scripts/`.

---

## RALPLAN-DR Summary

### Principles

1. `v0_5` history is immutable; `v0_6` is a fresh profile.
2. Closure authority must be exogenous and pre-registered: Isaac env-native consecutive success.
3. Held-out seeds remain sealed until train-generation gate and calibration freeze.
4. Expert repair remains single-pass and BC-friendly; no retry/search/force-control.
5. Every gate fails closed with buyer-readable reasons and reproducible artifacts.

### Decision Drivers

1. Avoid p-hacking after observing `v0_5` fail-closed results.
2. Recover actual Isaac train-generation material before any policy uplift claim.
3. Preserve MVP-2 boundary: positive held-out uplift is required for MVP-2 Closed.

### Viable Options

#### Option A — Adopted: Fresh `v0_6` env-native profile with preflight + probe + fixed 40 gate

Pros:
- Cleanly separates `v0_5` failure from `v0_6` proof.
- Uses Isaac env-native `_get_curr_successes()` as an external success authority.
- Prevents held-out leakage with fresh ranges and programmatic disjointness.
- Cheap repair probe blocks costly 40-run gate when the repair is not ready.

Cons:
- Requires new manifest fields, trace fields, tests, and runtime wiring.
- Env-native success may be harder than the prior geometry proxy.

#### Option B — Rejected: Reinterpret `v0_5` with RDF `0.015` geometry metric

Invalidation rationale:
- The `0.015` threshold was inspected after seeing `v0_5` results; using it as primary
  closure authority would look like metric shopping.
- It would blur historical failure evidence and future proof evidence.

#### Option C — Rejected: Add force/retry/search controller to increase success rate

Invalidation rationale:
- Retry/search trajectories are multimodal and hostile to phase-conditioned BC.
- Force-reactive control and richer contact search are outside this slice.
- The product proof is curated data value, not a new controller benchmark.

## ADR

### Decision

Implement `v0_6` as a new profile with:

- env-native consecutive success primary authority
- `stable_steps_required=10`
- fresh seed ranges `19000+`, `20000+`, `21000+`
- repair probe seeds `16023`, `16042`, `16096`
- static chamfer preflight before INSERT parameter freeze
- deterministic config-difficulty 40-seed selection

### Drivers

- `v0_5` actual Isaac train-generation gate stopped at `5/40`.
- The old metric was a project-owned geometry proxy, not the strongest closure authority.
- `v0_6` must not open held-out until train-generation material exists.

### Alternatives Considered

- Patch `v0_5`: rejected because it would rewrite fail-closed history.
- Use RDF `0.015` metric as closure: rejected because the count implication was already known.
- Use retry/search/force-control: rejected as scope and BC-learnability risk.

### Consequences

- Implementation work is larger than a threshold patch.
- Proof integrity is stronger because the new profile is fresh and fail-closed.
- Runtime Isaac gate may still fail; that is an acceptable honest blocker.

### Follow-ups

- If `v0_6` train gate passes, run calibration freeze and held-out A/B under the same env-native success authority.
- If chamfer Branch C or repair probe hard-stop occurs, stop and redesign insertion feasibility before further Isaac spend.

## File Structure

### Modify

- `scripts/run_mvp2c_isaac_training_calibration.py`
  - Add `v0_6` profile constants, seed ranges, disjointness validation, selected 40 train seed selection, preflight/probe gates, held-out scheduling guard.
- `scripts/run_mvp2b_isaac_proof_evaluator.py`
  - Add env-native stable-window summarizer, trace fields, active phase expert envelope, secondary RDF diagnostic preservation.
- `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
  - Add manifest, seed selection, preflight, repair probe, held-out guard tests.
- `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
  - Add env-native window and runtime trace summary tests.
- `docs/developer/worklog.md`
  - Record implementation decisions and verification.
- `tasks/todo.md`
  - Track `v0_6` execution tasks.
- `Handoff.md`
  - Add compact next-session state and blockers.

### Create

- `chamfer_preflight.json` at runtime output directory.
- `repair_probe_gate.json` at runtime output directory.
- Optional helper functions inside existing scripts unless extraction becomes necessary.

## Implementation Tasks

### Task 1: Add RED tests for `v0_6` manifest identity and seed isolation

**Files:**
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
- Modify later: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Add manifest identity test**

Add this test:

```python
def test_v06_scenario_manifest_uses_fresh_env_native_seed_ranges(tmp_path):
    manifest = script.build_mvp2c_scenario_manifest(
        output_dir=tmp_path / "mvp2e",
        scenario_profile="v0_6",
    )

    assert manifest["scenario_profile"] == "v0_6"
    assert manifest["manifest_version"] == "rdf_mvp2e_scenario_manifest_v0.6.0"
    assert manifest["success_authority"]["primary"] == "isaac_env_native_consecutive_success_v0"
    assert manifest["success_authority"]["stable_steps_required"] == 10
    assert manifest["success_authority"]["check_rot"] is False

    split_to_seeds = {
        split: {row["seed"] for row in manifest["scenarios"] if row["split"] == split}
        for split in ("train_success", "train_failure", "calibration", "held_out")
    }
    assert split_to_seeds["train_success"] == set(range(19000, 19160))
    assert split_to_seeds["train_failure"] == set(range(19200, 19360))
    assert split_to_seeds["calibration"] == set(range(20000, 20030))
    assert split_to_seeds["held_out"] == set(range(21000, 21050))
```

- [ ] **Step 2: Add disjointness test**

Add this test:

```python
def test_v06_manifest_excludes_prior_heldout_v05_train_and_probe_seeds(tmp_path):
    manifest = script.build_mvp2c_scenario_manifest(
        output_dir=tmp_path / "mvp2e",
        scenario_profile="v0_6",
    )

    all_scenario_seeds = {row["seed"] for row in manifest["scenarios"]}
    excluded = set()
    for item in manifest["excluded_prior_heldout_seed_ranges"]:
        start, end = item
        excluded.update(range(start, end + 1))

    assert {16023, 16042, 16096}.issubset(excluded)
    assert all_scenario_seeds.isdisjoint(excluded)
    assert all_scenario_seeds.isdisjoint(set(range(16000, 16160)))
    assert all_scenario_seeds.isdisjoint(set(range(18000, 18020)))
```

- [ ] **Step 3: Run RED test**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06_scenario_manifest_uses_fresh_env_native_seed_ranges apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06_manifest_excludes_prior_heldout_v05_train_and_probe_seeds -q
```

Expected:

```text
FAILED ... ValueError: unknown MVP-2C scenario_profile: v0_6
```

### Task 2: Implement `v0_6` manifest profile

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Add constants**

Add near existing scenario constants:

```python
V06_MANIFEST_VERSION = "rdf_mvp2e_scenario_manifest_v0.6.0"
V06_REPAIR_PROBE_SEEDS = (16023, 16042, 16096)
V06_ENV_NATIVE_STABLE_STEPS_REQUIRED = 10
V06_TRAIN_GATE_SUCCESS_MINIMUM = 20
V06_TRAIN_GATE_ATTEMPT_COUNT = 40
V06_ENV_NATIVE_SUCCESS_AUTHORITY = {
    "primary": "isaac_env_native_consecutive_success_v0",
    "isaac_function": "_get_curr_successes",
    "success_threshold_source": "env.cfg_task.success_threshold",
    "success_threshold": 0.04,
    "fixed_asset_height_m": 0.025,
    "height_threshold_m": 0.001,
    "xy_dist_threshold_m": 0.0025,
    "check_rot": False,
    "stable_steps_required": V06_ENV_NATIVE_STABLE_STEPS_REQUIRED,
}
```

- [ ] **Step 2: Extend `_scenario_seed_ranges`**

Add:

```python
    if scenario_profile == "v0_6":
        return {
            "train_success": range(19000, 19160),
            "train_failure": range(19200, 19360),
            "calibration": range(20000, 20030),
            "held_out": range(21000, 21050),
        }
```

- [ ] **Step 3: Extend manifest version**

Add:

```python
    if scenario_profile == "v0_6":
        return V06_MANIFEST_VERSION
```

- [ ] **Step 4: Extend excluded ranges**

For `v0_6`, return:

```python
    if scenario_profile == "v0_6":
        return [
            [3000, 3019],
            [6000, 6019],
            [9000, 9019],
            [12000, 12019],
            [15000, 15019],
            [16000, 16159],
            [18000, 18019],
            [16023, 16023],
            [16042, 16042],
            [16096, 16096],
        ]
```

- [ ] **Step 5: Add seed disjointness helper**

Add:

```python
def _validate_manifest_seed_disjointness(manifest: dict[str, Any]) -> None:
    scenario_seeds = {int(row["seed"]) for row in manifest.get("scenarios", [])}
    excluded = set()
    for start, end in manifest.get("excluded_prior_heldout_seed_ranges", []):
        excluded.update(range(int(start), int(end) + 1))
    overlap = sorted(scenario_seeds & excluded)
    if overlap:
        raise ValueError(f"scenario seeds overlap excluded seeds: {overlap[:10]}")
```

- [ ] **Step 6: Add `success_authority` to manifest for `v0_6`**

Inside `build_mvp2c_scenario_manifest()`, after manifest creation:

```python
    if scenario_profile == "v0_6":
        manifest["success_authority"] = dict(V06_ENV_NATIVE_SUCCESS_AUTHORITY)
        manifest["secondary_diagnostics"] = {
            "rdf_peg_in_hole_metric": dict(SUCCESS_METRIC),
            "closure_authority": False,
        }
        manifest["repair_probe_seeds"] = list(V06_REPAIR_PROBE_SEEDS)
        _validate_manifest_seed_disjointness(manifest)
```

- [ ] **Step 7: Run tests**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06_scenario_manifest_uses_fresh_env_native_seed_ranges apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06_manifest_excludes_prior_heldout_v05_train_and_probe_seeds -q
```

Expected:

```text
2 passed
```

### Task 3: Add deterministic fixed 40 seed selection

**Files:**
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Add RED test**

Use the test from `.omx/plans/test-spec-mvp2e-v06-env-native-train-generation-recovery.md`
named `test_v06_train_gate_seed_selection_is_deterministic_config_only`.

- [ ] **Step 2: Add difficulty helper**

```python
def _v06_difficulty_cell(seed: int) -> tuple[int, int]:
    return (abs((int(seed) % 9) - 4), abs(((int(seed) // 5) % 11) - 5))
```

- [ ] **Step 3: Add selector**

```python
def build_v06_train_gate_seed_selection(source_range: range) -> dict[str, Any]:
    cells: dict[tuple[int, int], list[int]] = {}
    for seed in source_range:
        cells.setdefault(_v06_difficulty_cell(seed), []).append(seed)
    for seeds in cells.values():
        seeds.sort()

    ordered_cells = sorted(cells)
    selected: list[int] = []
    cell_index = 0
    while len(selected) < V06_TRAIN_GATE_ATTEMPT_COUNT:
        cell = ordered_cells[cell_index % len(ordered_cells)]
        seeds = cells[cell]
        if seeds:
            selected.append(seeds.pop(0))
        cell_index += 1
        if cell_index > len(ordered_cells) * V06_TRAIN_GATE_ATTEMPT_COUNT * 2:
            raise ValueError("unable to select v0_6 train gate seeds")

    config = {
        "source_range": [source_range.start, source_range.stop - 1],
        "difficulty_cell_formula": {
            "offset_class": "abs((seed % 9) - 4)",
            "orient_class": "abs(((seed // 5) % 11) - 5)",
        },
        "allocation_rule": "round_robin_across_sorted_difficulty_cells",
        "tie_break_rule": "lowest_seed_id_in_cell",
        "uses_isaac_results": False,
        "uses_rng": False,
    }
    return {
        **config,
        "selected_40_seed_ids": selected,
        "selection_config_sha256": _sha256_payload(config),
        "selected_seed_list_sha256": _sha256_payload(selected),
    }
```

- [ ] **Step 4: Attach to manifest**

Inside `build_mvp2c_scenario_manifest()` for `v0_6`:

```python
        manifest["v0_6_train_gate_seed_selection"] = build_v06_train_gate_seed_selection(
            seed_ranges["train_success"]
        )
```

- [ ] **Step 5: Run focused test**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06_train_gate_seed_selection_is_deterministic_config_only -q
```

Expected:

```text
1 passed
```

### Task 4: Add env-native stable-window evaluator

**Files:**
- Modify: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`

- [ ] **Step 1: Add RED test**

Use the test named `test_env_native_success_requires_ten_consecutive_steps` from the
test spec.

- [ ] **Step 2: Implement evaluator helper**

```python
def evaluate_env_native_success_window(
    mask: Sequence[bool],
    *,
    stable_steps_required: int = 10,
) -> dict[str, Any]:
    first_success_step: int | None = None
    current = 0
    max_consecutive = 0
    for index, value in enumerate(mask):
        if bool(value):
            if first_success_step is None:
                first_success_step = index
            current += 1
            max_consecutive = max(max_consecutive, current)
        else:
            current = 0
    return {
        "first_success_step": first_success_step,
        "max_consecutive_success_steps": max_consecutive,
        "stable_steps_required": stable_steps_required,
        "rollout_success": max_consecutive >= stable_steps_required,
    }
```

- [ ] **Step 3: Run focused test**

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py::test_env_native_success_requires_ten_consecutive_steps -q
```

Expected:

```text
1 passed
```

### Task 5: Record env-native mask in runtime traces

**Files:**
- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`
- Modify: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`

- [ ] **Step 1: Add trace summary test with synthetic trace**

Add a test that builds rows with `env_native_success` values and asserts:

```python
assert summary["env_native_rollout_success"] is True
assert summary["env_native_max_consecutive_success_steps"] == 10
assert summary["rdf_peg_in_hole_metric"]["closure_authority"] is False
```

- [ ] **Step 2: In `_run_one_rollout`, read env-native mask when available**

Add guarded extraction inside the step loop:

```python
env_native_success = None
if hasattr(self.env.unwrapped, "_get_curr_successes"):
    env_native_tensor = self.env.unwrapped._get_curr_successes(
        success_threshold=self.env.unwrapped.cfg_task.success_threshold,
        check_rot=False,
    )
    env_native_success = bool(env_native_tensor[0].item())
```

If wrapper structure differs, keep this guarded and report `env_native_success_available=false`
rather than crashing.

- [ ] **Step 3: Add row fields**

Each trace row should include:

```python
"env_native_success": env_native_success,
"success_authority": "isaac_env_native_consecutive_success_v0" if env_native_success is not None else None,
```

- [ ] **Step 4: Add summary fields**

After trace collection:

```python
env_native_mask = [bool(row["env_native_success"]) for row in trace if row.get("env_native_success") is not None]
env_native_summary = evaluate_env_native_success_window(env_native_mask, stable_steps_required=10)
summary["env_native_first_success_step"] = env_native_summary["first_success_step"]
summary["env_native_max_consecutive_success_steps"] = env_native_summary["max_consecutive_success_steps"]
summary["env_native_rollout_success"] = env_native_summary["rollout_success"]
summary["env_native_success_available"] = bool(env_native_mask)
summary["rdf_peg_in_hole_metric"] = {"closure_authority": False, "summary": geometry_summary}
```

- [ ] **Step 5: Run evaluator tests**

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -q
```

Expected:

```text
all tests passed
```

### Task 6: Add chamfer preflight gate

**Files:**
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Add RED test**

Use `test_chamfer_preflight_branch_c_blocks_insert_probe_and_train_gate` from the test spec.

- [ ] **Step 2: Implement preflight evaluator**

```python
def evaluate_chamfer_preflight_gate(
    *,
    source_asset_paths: list[str],
    inspection_result: dict[str, Any],
) -> dict[str, Any]:
    chamfer_present = inspection_result.get("chamfer_present")
    capture_radius_m = inspection_result.get("capture_radius_m")
    if chamfer_present is True and isinstance(capture_radius_m, int | float):
        branch = "A"
    elif chamfer_present is True:
        branch = "B"
    else:
        branch = "C"
    allowed = branch in {"A", "B"}
    result = {
        "chamfer_present": chamfer_present,
        "capture_radius_m": capture_radius_m if capture_radius_m is not None else "unknown",
        "inspection_method": inspection_result.get("inspection_method", "static_usd"),
        "source_asset_paths": source_asset_paths,
        "preflight_branch": branch,
        "insert_parameter_freeze_allowed": allowed,
        "repair_probe_allowed": allowed,
        "train_generation_gate_allowed": allowed,
        "derivation_rationale": inspection_result.get("derivation_rationale", "chamfer preflight gate"),
    }
    result["chamfer_preflight_sha256"] = _sha256_payload(result)
    return result
```

- [ ] **Step 3: Persist artifact in v0_6 runs**

Write to:

```python
write_json(output_dir / "chamfer_preflight.json", chamfer_preflight)
```

- [ ] **Step 4: Fail closed before probe/gate**

Before executing repair probe or train gate:

```python
if scenario_profile == "v0_6" and not chamfer_preflight["train_generation_gate_allowed"]:
    return fail_closed_result_with_reason("chamfer preflight Branch C blocked INSERT parameter freeze")
```

- [ ] **Step 5: Run focused test**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_chamfer_preflight_branch_c_blocks_insert_probe_and_train_gate -q
```

Expected:

```text
1 passed
```

### Task 7: Add repair probe gate and lateral divergence diagnostic

**Files:**
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Add RED tests**

Add tests named:

```python
test_lateral_divergence_stopped_uses_gap_derived_cap_and_last10_median
test_v06_repair_probe_green_light_requires_hold_and_lateral_modes
```

- [ ] **Step 2: Implement diagnostic helper**

```python
def evaluate_lateral_divergence_stopped(
    *,
    lateral_errors_m: Sequence[float],
    divergence_cap_m: float = 0.008,
    final_drift_margin_m: float = 0.002,
    last_k: int = 10,
) -> dict[str, Any]:
    if not lateral_errors_m:
        return {
            "lateral_divergence_stopped": False,
            "reason": "missing lateral diagnostics",
        }
    initial = float(lateral_errors_m[0])
    max_lateral = max(float(value) for value in lateral_errors_m)
    tail = [float(value) for value in lateral_errors_m[-last_k:]]
    tail_median = statistics.median(tail)
    stopped = max_lateral < divergence_cap_m and tail_median <= initial + final_drift_margin_m
    return {
        "lateral_divergence_stopped": stopped,
        "initial_lateral_error_m": initial,
        "max_lateral_error_m": max_lateral,
        "last_10_median_lateral_error_m": tail_median,
        "divergence_cap_m": divergence_cap_m,
        "final_drift_margin_m": final_drift_margin_m,
    }
```

- [ ] **Step 3: Implement probe gate helper**

```python
def evaluate_v06_repair_probe_gate(probe_results: dict[int, dict[str, Any]]) -> dict[str, Any]:
    hold = probe_results.get(16023, {})
    lateral_a = probe_results.get(16042, {})
    lateral_b = probe_results.get(16096, {})
    hold_pass = bool(hold.get("env_native_rollout_success"))
    lateral_success_pass = bool(lateral_a.get("env_native_rollout_success")) or bool(
        lateral_b.get("env_native_rollout_success")
    )
    lateral_divergence_stopped = bool(lateral_a.get("lateral_divergence_stopped")) and bool(
        lateral_b.get("lateral_divergence_stopped")
    )
    green = hold_pass and lateral_success_pass and lateral_divergence_stopped
    hard_stop = (not hold_pass) or (
        not bool(lateral_a.get("lateral_divergence_stopped"))
        and not bool(lateral_b.get("lateral_divergence_stopped"))
    )
    return {
        "proof_authority": False,
        "probe_seeds": list(V06_REPAIR_PROBE_SEEDS),
        "hold_mode_passed": hold_pass,
        "lateral_success_mode_passed": lateral_success_pass,
        "lateral_divergence_stopped": lateral_divergence_stopped,
        "green_light_for_40_run_gate": green,
        "hard_stop": hard_stop,
    }
```

- [ ] **Step 4: Persist artifact**

Write to:

```python
write_json(output_dir / "repair_probe_gate.json", repair_probe_gate)
```

- [ ] **Step 5: Run focused tests**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_lateral_divergence_stopped_uses_gap_derived_cap_and_last10_median apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06_repair_probe_green_light_requires_hold_and_lateral_modes -q
```

Expected:

```text
2 passed
```

### Task 8: Implement active state-based expert repair envelope

**Files:**
- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`
- Modify: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`

- [ ] **Step 1: Add tests for phase transitions**

Add synthetic tests for a helper that chooses phase/action intent:

```python
def test_v06_phase_controller_holds_z_until_lateral_and_orientation_are_aligned():
    phase = script.v06_phase_controller_step(
        current_phase="ALIGN",
        lateral_error_m=0.009,
        orientation_error_rad=0.01,
        insertion_depth_m=0.0,
        env_native_success=False,
        stable_steps=0,
    )
    assert phase["next_phase"] == "ALIGN"
    assert phase["z_motion_allowed"] is False

def test_v06_phase_controller_descends_only_while_alignment_gate_holds():
    phase = script.v06_phase_controller_step(
        current_phase="DESCEND",
        lateral_error_m=0.009,
        orientation_error_rad=0.01,
        insertion_depth_m=0.010,
        env_native_success=False,
        stable_steps=0,
    )
    assert phase["next_phase"] == "DESCEND"
    assert phase["z_motion_allowed"] is False
```

- [ ] **Step 2: Implement helper with fixed gates**

```python
def v06_phase_controller_step(
    *,
    current_phase: str,
    lateral_error_m: float,
    orientation_error_rad: float,
    insertion_depth_m: float,
    env_native_success: bool,
    stable_steps: int,
    align_lateral_gate_m: float = 0.008,
    align_orientation_gate_rad: float = 0.25,
) -> dict[str, Any]:
    aligned = lateral_error_m <= align_lateral_gate_m and orientation_error_rad <= align_orientation_gate_rad
    phase = current_phase
    z_motion_allowed = False
    if phase == "ALIGN" and aligned:
        phase = "DESCEND"
    if phase == "DESCEND":
        z_motion_allowed = aligned
        if insertion_depth_m >= 0.025:
            phase = "INSERT"
    if phase == "INSERT":
        z_motion_allowed = aligned
        if env_native_success:
            phase = "HOLD"
    if phase == "HOLD":
        z_motion_allowed = False
    return {
        "next_phase": phase,
        "alignment_gate_satisfied": aligned,
        "z_motion_allowed": z_motion_allowed,
        "stable_steps": stable_steps,
    }
```

- [ ] **Step 3: Wire helper into the scripted expert action path**

Use the helper in the runtime policy path that currently uses `_phase_from_depth()` and
servo action logic. Keep:

```text
NO retry
NO withdraw
NO search
NO force reactive control
```

- [ ] **Step 4: Preserve secondary phase labels**

Trace rows should record:

```python
"phase": controller_state["next_phase"],
"phase_source": "v0_6_active_state_controller",
"z_motion_allowed": controller_state["z_motion_allowed"],
"alignment_gate_satisfied": controller_state["alignment_gate_satisfied"],
```

- [ ] **Step 5: Run evaluator tests**

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -q
```

Expected:

```text
all tests passed
```

### Task 9: Wire `v0_6` train gate and held-out fail-closed behavior

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add held-out guard RED test**

Use `test_v06_train_generation_failure_blocks_heldout` from the test spec.

- [ ] **Step 2: Extend `probe_isaac_train_generation_runtime()`**

For `scenario_profile == "v0_6"`:

```python
min_success_count = V06_TRAIN_GATE_SUCCESS_MINIMUM
success_trace_cap = V06_TRAIN_GATE_ATTEMPT_COUNT
selected_seeds = manifest["v0_6_train_gate_seed_selection"]["selected_40_seed_ids"]
```

Require env-native success:

```python
rollout_success = bool(summary.get("env_native_rollout_success"))
```

If `env_native_success_available` is false, fail closed:

```python
"passed": False,
"reason": "env-native success mask unavailable"
```

- [ ] **Step 3: Add held-out schedule gate**

For `v0_6`, held-out scheduled only when:

```python
train_generation_runtime_gate["passed"] is True
repair_probe_gate["green_light_for_40_run_gate"] is True
chamfer_preflight["train_generation_gate_allowed"] is True
```

- [ ] **Step 4: Run held-out guard test**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06_train_generation_failure_blocks_heldout -q
```

Expected:

```text
1 passed
```

### Task 10: Add CLI and report compatibility

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Extend CLI choices**

Change:

```python
parser.add_argument("--scenario-profile", choices=("v0_1", "v0_2", "v0_3", "v0_4", "v0_5"), default="v0_1")
```

to:

```python
parser.add_argument("--scenario-profile", choices=("v0_1", "v0_2", "v0_3", "v0_4", "v0_5", "v0_6"), default="v0_1")
```

- [ ] **Step 2: Add `--repair-probe-only`**

```python
parser.add_argument("--repair-probe-only", action="store_true")
```

When true, run only the `16023/16042/16096` repair probe and write
`repair_probe_gate.json`.

- [ ] **Step 3: Include artifact paths in output**

For `v0_6`, top-level result should include:

```python
"v0_6_artifacts": {
    "chamfer_preflight": str(output_dir / "chamfer_preflight.json"),
    "repair_probe_gate": str(output_dir / "repair_probe_gate.json"),
    "train_generation_runtime_gate": str(output_dir / "train_generation_runtime_gate.json"),
}
```

- [ ] **Step 4: Run skip-isaac smoke**

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py --output-dir /tmp/rdf-mvp2e-v06-skip --clean --scenario-profile v0_6 --skip-isaac --pretty
```

Expected:

```text
exit code 0
scenario_manifest.json exists
scenario_profile == "v0_6"
heldout_schedule_gate.heldout_scheduled == false
```

### Task 11: Run actual Isaac repair probe

**Files:**
- Runtime artifacts only under `/tmp/rdf-mvp2e-v06-repair-probe`

- [ ] **Step 1: Run repair probe**

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2e-v06-repair-probe \
  --clean \
  --scenario-profile v0_6 \
  --train-generation-probe-only \
  --repair-probe-only \
  --max-steps 145 \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

- [ ] **Step 2: Inspect result**

Run:

```bash
python -m json.tool /tmp/rdf-mvp2e-v06-repair-probe/repair_probe_gate.json | sed -n '1,220p'
```

Expected green:

```text
green_light_for_40_run_gate: true
hard_stop: false
```

Expected fail-closed:

```text
hard_stop: true
explicit reason present
do not run 40 gate
```

### Task 12: Run actual Isaac fixed 40 train-generation gate

**Files:**
- Runtime artifacts only under `/tmp/rdf-mvp2e-v06-train-gate`

- [ ] **Step 1: Run 40 gate only if repair probe green-lights**

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2e-v06-train-gate \
  --clean \
  --scenario-profile v0_6 \
  --train-generation-probe-only \
  --max-steps 145 \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

- [ ] **Step 2: Inspect result**

Run:

```bash
python -m json.tool /tmp/rdf-mvp2e-v06-train-gate/train_generation_runtime_gate.json | sed -n '1,260p'
```

Expected pass:

```text
generated_rollout_count: 40
generated_success_count >= 20
passed: true
```

Expected fail-closed:

```text
generated_success_count < 20
passed: false
held-out not scheduled
```

### Task 13: Documentation and handoff

**Files:**
- Modify: `docs/developer/worklog.md`
- Modify: `tasks/todo.md`
- Modify: `Handoff.md`

- [ ] **Step 1: Record implementation**

Append to `docs/developer/worklog.md`:

```markdown
## 2026-06-11 - MVP-2E v0.6 env-native train-generation recovery implementation

- 작업 내용:
  - ...
- 판단 이유:
  - ...
- 변경 파일:
  - ...
- 검증:
  - ...
- 남은 gap:
  - ...
```

- [ ] **Step 2: Update `tasks/todo.md`**

Record status:

```markdown
## MVP-2E v0.6 env-native train-generation recovery

- [ ] chamfer preflight passed
- [ ] repair probe green-lit
- [ ] fixed 40 train-generation gate >=20/40
- [ ] held-out remains sealed until calibration freeze
```

- [ ] **Step 3: Update `Handoff.md`**

Record compact state:

```markdown
## 2026-06-11 - MVP-2E v0.6 env-native train-generation recovery

Current status:
- ...

Next step:
- ...

Blockers:
- ...
```

### Task 14: Final verification

**Files:**
- All changed files

- [ ] **Step 1: Run focused tests**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -q
```

- [ ] **Step 2: Run skip-isaac smoke**

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py --output-dir /tmp/rdf-mvp2e-v06-skip --clean --scenario-profile v0_6 --skip-isaac --pretty
```

- [ ] **Step 3: Compile**

```bash
uv run python -m compileall -q scripts apps/api/app apps/api/tests
```

- [ ] **Step 4: Lint**

```bash
uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py scripts/run_mvp2b_isaac_proof_evaluator.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py
```

- [ ] **Step 5: Diff check**

```bash
git diff --check
```

Expected:

```text
all commands pass, or runtime Isaac gate fails closed with explicit artifact evidence
```

## Available Agent Types Roster

- `executor`: main implementation lane for script and test changes.
- `test-engineer`: focused TDD and failure-mode coverage.
- `debugger`: Isaac runtime diagnosis if repair probe or 40 gate fails.
- `architect`: boundary review if implementation threatens proof integrity.
- `critic`: final verification and claim-boundary review.
- `writer`: docs/worklog/handoff update after evidence is collected.

## Staffing Guidance

### Default: `$ultragoal`

Use `$ultragoal` with this plan as the durable implementation ledger. Recommended
goal checkpoints:

1. Red tests and v0_6 manifest.
2. Env-native evaluator and trace fields.
3. Seed selection, preflight, repair probe gates.
4. Active phase repair and skip-isaac smoke.
5. Actual Isaac repair probe.
6. Actual Isaac fixed 40 train gate.
7. Documentation and handoff.

### Parallel option: `$ultragoal` + `$team`

Use Team only after the red tests and manifest boundaries are clear. Suggested lanes:

- Lane A: manifest/seed selection/preflight tests.
- Lane B: env-native evaluator/runtime trace tests.
- Lane C: docs and artifact schema review.

Do not parallelize changes to the same script sections without a leader integration pass.

### `$ralph` fallback

Use `$ralph` only if a single-owner persistent loop is needed after Isaac runtime failures.
Do not use Ralph as the default durable goal mode; `$ultragoal` is the default.

## Goal-Mode Follow-up Suggestions

- `$ultragoal`: recommended next step for implementation.
- `$team`: optional inside Ultragoal for disjoint test/helper lanes.
- `$autoresearch-goal`: not recommended now; the design questions are resolved enough for implementation.
- `$performance-goal`: not applicable; this is proof correctness, not performance optimization.

