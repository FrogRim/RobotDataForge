# Implementation Plan: MVP-2E v0.6a Runtime Capture-radius Preflight

Date: 2026-06-11

## ADR

Decision:

- Implement a runtime empirical capture-radius preflight for `v0_6a`.
- Use it to resolve `v0_6` static-local Branch C into Branch A/B/C.
- Keep runtime USD stage inspection as a fallback diagnostic, not the primary
  route.

Drivers:

- `v0_6` Branch C came from static-local inspection limits.
- Isaac runtime has already loaded the Factory task in prior actual traces.
- Passive capture radius is the INSERT parameter dependency that matters.
- Geometry preflight must not contaminate held-out, train, calibration, or repair
  probe seeds.

Alternatives considered:

- Runtime USD stage inspection first: rejected as less directly tied to physical
  capture behavior.
- Manual asset export before any runtime probe: rejected as slower and not
  necessary before trying the runtime path.
- Treat static Branch C as final blocker: rejected because runtime evidence
  indicates the asset path can be resolved by Isaac.

Consequences:

- Adds a small runtime-only preflight lane before repair probe.
- Adds a new artifact, `capture_radius_probe.json`.
- Requires tests to prevent the preflight from passing downstream proof gates.
- Freezes INSERT envelope values before repair probe to prevent Branch B from
  becoming a hidden tuning loop.

Follow-ups:

- If Branch A/B: run repair probe `16023/16042/16096`.
- If repair probe green-lights: run fixed 40-run gate.
- If Branch C: keep MVP-2 blocked and inspect runtime asset/stage manually.

## RALPLAN-DR Summary

Principles:

1. Geometry-only evidence must stay separate from learning proof.
2. Branch A/B unlocks repair probe only.
3. Held-out seeds remain sealed.
4. Prior static Branch C evidence remains auditable.
5. Runtime failure must fail closed.

Decision drivers:

1. The blocker is inspection path limitation, not proven asset absence.
2. Passive capture radius is best measured empirically in runtime.
3. Seed and gate authority boundaries are the highest-risk failure mode.

Viable options:

- A: empirical runtime probe first. Chosen.
- B: runtime USD inspection first. Kept as fallback.
- C: manual export/static-only path. Deferred.

## Available Agent Types

- `executor`: implementation and focused refactor.
- `test-engineer`: test coverage and fixture/gate validation.
- `architect`: review boundary and artifact authority.
- `critic`: final plan/quality gate.
- `verifier`: runtime evidence and completion checks.

Suggested reasoning:

- executor: medium
- test-engineer: medium
- architect: high
- critic: high
- verifier: high

## Work Items

### G001 - Add RED Tests For v0.6a Preflight Contract

Files:

- `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

Add focused failing tests for:

- geometry seed namespace `18500-18509` disjointness;
- Branch A classification from measurable capture radius;
- Branch B classification from weak/asymmetric capture;
- Branch C classification from runtime/mask/zero-offset failure;
- updated preflight preserving prior static Branch C evidence;
- explicit `capture_radius_probe.json` artifact shape;
- verified v0.6a preflight validator rejection cases;
- `repair_probe_green_light=false` in both capture and preflight artifacts;
- Branch B align-then-jam escalation before any 40-run gate;
- capture-radius probe cannot pass repair probe/train gate/held-out/MVP-2;
- exact pre-registered INSERT envelope values;
- repair probe requires a verified `v0_6a` preflight artifact instead of
  rebuilding static Branch C;
- Branch A/B leaves `train_generation_gate_allowed=false` with
  `train_generation_gate_status=pending_repair_probe`;
- static `v0_6 --skip-isaac` behavior remains fail-closed.

Verification:

```text
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q
```

Expected first result:

```text
RED: missing v0_6a constants/helpers/artifact builders
```

### G002 - Implement Pure v0.6a Constants And Branch Resolution

Files:

- `scripts/run_mvp2c_isaac_training_calibration.py`

Add:

- `V06A_CAPTURE_RADIUS_GEOMETRY_PROBE_SEEDS = tuple(range(18500, 18510))`
- `V06A_CAPTURE_RADIUS_PRIMARY_SEED = 18500`
- `V06A_CAPTURE_RADIUS_OFFSET_SWEEP_M`
- `V06A_CAPTURE_RADIUS_DIRECTIONS`
- `V06A_PRE_REGISTERED_INSERT_ENVELOPE`
- `evaluate_runtime_capture_radius_probe(...)`
- `build_v06a_capture_radius_probe_artifact(...)`
- `build_v06a_runtime_chamfer_preflight_from_probe(...)`
- `validate_v06a_verified_chamfer_preflight(...)`
- `resolve_v06_repair_probe_preflight(...)`

Pre-registered INSERT envelope:

```python
V06A_PRE_REGISTERED_INSERT_ENVELOPE = {
    "vertical_push_scale": 24.0,
    "correction_gain_limit": 4.0,
    "max_insert_steps": 145,
    "rotation_action_scale": 0.0,
    "value_source": "frozen_v0_6_adapter_and_horizon_not_probe_results",
}
```

Rationale:

- `vertical_push_scale=24.0` follows the frozen `v0_6` active-state
  train-generation controller `z_action_scale`.
- `correction_gain_limit=4.0` follows the frozen `v0_6` active-state
  train-generation controller `xy_action_scale`.
- `max_insert_steps=145` follows the horizon-aware `v0_6` runtime limit used by
  the prior repair/train gate commands.
- `rotation_action_scale=0.0` preserves the existing no-yaw-correction runtime
  envelope.
- None of these values may be selected from capture-radius or repair-probe
  results.
- These values do not come from older calibration-selected adapter registry
  values.

Rules:

- Branch A requires zero-offset pass, env-native availability, runtime load, and
  non-trivial capture in every direction.
- Branch B requires zero-offset pass and some weak/approximate capture.
- Branch C covers runtime load failure, mask failure, zero-offset failure, all
  non-zero failure, or untrustworthy artifact.
- `proof_authority=false` always.
- `heldout_allowed=false` always.
- `train_generation_gate_passed=false` always.
- Branch A/B must set `train_generation_gate_allowed=false` and
  `train_generation_gate_status=pending_repair_probe`.
- Branch C must set `train_generation_gate_allowed=false` and
  `train_generation_gate_status=blocked_by_preflight`.

Verification:

```text
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q
```

### G003 - Add Artifact Writers And CLI Surface

Files:

- `scripts/run_mvp2c_isaac_training_calibration.py`

Add CLI:

```text
--capture-radius-probe-only
```

Add artifact output:

- `capture_radius_probe.json`
- updated `chamfer_preflight.json`

Preserve:

- existing `--repair-probe-only`
- existing `v0_6 --skip-isaac` fail-closed behavior when runtime probe is not
  requested.

Guard:

- `--capture-radius-probe-only` must not run repair probe or 40-run train gate.
- `--capture-radius-probe-only` must not open held-out.
- `chamfer_preflight.json` from capture-radius probe must include:
  - `scenario_profile=v0_6a`
  - `source_scenario_profile=v0_6`
  - `prior_static_preflight_branch`
  - `prior_static_inspection_method`
  - `non_claims`
  - `derived_insert_params`
  - `repair_probe_green_light=false`
  - `train_generation_gate_allowed=false`
  - `train_generation_gate_status=pending_repair_probe` for Branch A/B.

Verified preflight predicate:

```text
scenario_profile=v0_6a
source_scenario_profile=v0_6
inspection_method=runtime_empirical_capture_radius_probe
preflight_branch in {A, B}
repair_probe_allowed=true
train_generation_gate_allowed=false
train_generation_gate_status=pending_repair_probe
heldout_allowed=false
non_claims present and all downstream claims false
chamfer_preflight_sha256 matches canonical payload hash
prior_static_preflight_branch=C
```

Verification:

```text
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2e-v06a-skip \
  --clean \
  --scenario-profile v0_6 \
  --skip-isaac \
  --pretty
```

Expected:

```text
static Branch C remains fail-closed
heldout_schedule.scheduled=false
```

### G004 - Implement Runtime Empirical Capture-radius Probe

Files:

- `scripts/run_mvp2c_isaac_training_calibration.py`
- optionally reuse helpers from `scripts/run_mvp2b_isaac_proof_evaluator.py`

Runtime behavior:

1. Load `Isaac-Factory-PegInsert-Direct-v0`.
2. Reset with geometry seed `18500`.
3. Resolve task-state/fixed asset target pose.
4. For each direction and delta:
   - initialize or command held peg above target with lateral offset;
   - disable lateral/yaw correction;
   - apply bounded vertical push;
   - record per-step env-native success mask;
   - summarize consecutive success window.
5. Compute per-direction max successful delta.
6. Compute conservative `capture_radius_m = min(max_success_delta_by_direction)`.
7. Emit `capture_radius_probe.json`.
8. Build updated `chamfer_preflight.json`.
9. Do not run repair probe from this command.

Implementation notes:

- Prefer minimal reuse of existing Isaac evaluator setup to avoid a second runtime
  stack.
- If direct state placement is not reliable, stop and report before replacing it
  with controller correction. The probe must measure passive capture, not active
  alignment.
- Runtime USD stage inspection may be added only as fallback diagnostic if the
  empirical probe cannot produce trustworthy output.

Verification:

```text
/home/kangrim/IsaacLab/_isaac_sim/python.sh \
  scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2e-v06a-capture-radius \
  --clean \
  --scenario-profile v0_6 \
  --capture-radius-probe-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

Acceptable result:

- Branch A/B/C artifact is produced.
- Branch C is a valid fail-closed result if runtime probing cannot verify capture.

### G005 - Wire Branch A/B Into Existing Repair-probe Gate Without Passing Downstream Gates

Files:

- `scripts/run_mvp2c_isaac_training_calibration.py`
- tests as needed.

Behavior:

- Branch A/B sets `repair_probe_allowed=true`.
- Branch A/B sets `train_generation_gate_allowed=false` and
  `train_generation_gate_status=pending_repair_probe`.
- Branch A/B does not mark `train_generation_runtime_gate.passed=true`.
- Branch A/B does not mark `green_light_for_40_run_gate=true`.
- Branch A/B does not schedule held-out.
- `run_v06_repair_probe_runtime()` must consume a verified v0.6a
  `chamfer_preflight.json` artifact or an explicitly supplied verified preflight
  object.
- If no verified v0.6a preflight exists, repair probe must fail closed with
  `reason=missing_verified_v0_6a_chamfer_preflight`.
- If Branch B preflight proceeds to repair probe and the repair probe reports
  `failure_mode=align_then_jam`, the fixed 40-run gate must remain blocked with
  `reason=branch_b_align_then_jam_escalated_to_blocker`.
- Existing static `build_v06_chamfer_preflight()` remains the default only when
  runtime capture-radius preflight has not been requested.
- The fixed 40-run gate can open only when:

```text
preflight.preflight_branch in {"A", "B"}
preflight.repair_probe_allowed=true
repair_probe_gate.green_light_for_40_run_gate=true
```

Verification:

```text
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q
```

### G006 - Documentation And Final Verification

Files:

- `docs/developer/worklog.md`
- `tasks/todo.md`
- `Handoff.md`

Update:

- what Branch result occurred;
- artifact paths;
- validation commands;
- next gate:
  - Branch A/B -> repair probe;
  - Branch C -> blocker remains.

Final verification:

```text
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -q

uv run python -m compileall -q scripts apps/api/app apps/api/tests

uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py scripts/run_mvp2b_isaac_proof_evaluator.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py

git diff --check
```

## Team Verification Path

Solo execution is acceptable because the code surface is narrow. If using
`$team`, split lanes as:

- test-engineer: RED tests and pure branch assertions;
- executor: helper/CLI/runtime implementation;
- verifier: runtime probe evidence and docs.

`$ultragoal` remains the recommended owner for durable sequential execution.

## Stop Rules

Stop and report if:

- runtime probe cannot load Isaac Factory env;
- env-native mask is unavailable;
- zero-offset insertion fails;
- direct state placement is impossible without controller correction;
- probe needs held-out/train/calibration/repair seeds;
- success authority or stable window would need to change;
- force/retry/search behavior becomes necessary;
- downstream gate pass would depend on capture-radius artifact alone.

## Recommended Next Command

```text
$ultragoal implement docs/superpowers/plans/2026-06-11-mvp2e-v06a-runtime-capture-radius-preflight.md
```
