# MVP-2E Harness-Gated Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:test-driven-development` and `superpowers:executing-plans`.
> This is a planning artifact only; do not implement from this file until the
> user invokes an execution workflow such as `$ultragoal`.

Date: 2026-06-12

## Goal

Implement the MVP-2E harness-gated closure layer defined in:

```text
docs/superpowers/specs/2026-06-12-mvp2e-harness-gated-closure-design.md
```

The implementation must generate a root-cause harness report against current
`v0_7c` evidence before any `v0_7d` downstream slice is created.

## Scope

In scope:

- Offline harness config/report generation.
- Close-critical H0-H3 and H15 implemented first.
- H4-H7/H9/H11/H12/H14 represented and progressively implemented where current
  artifacts support them.
- H8/H10/H13/H16 represented as credibility/statistical tiers but not required
  for the first downstream-slice gate.
- Report artifacts under persistent `storage/proof_evidence`.
- Tests and documentation updates.

Out of scope:

- `v0_7d` implementation.
- Actual Isaac execution.
- Calibration.
- Held-out `21000-21049`.
- New policy architecture or training.
- Real robot/HMD/force-control/VLA/world model work.

## Current Code Anchors

- `scripts/run_mvp2c_isaac_training_calibration.py:218` defines `v0_7c`
  constants.
- `scripts/run_mvp2c_isaac_training_calibration.py:795` builds the current
  `v0_7c_action_authority_config`.
- `scripts/run_mvp2c_isaac_training_calibration.py:869` applies the current
  residual authority filter.
- `scripts/run_mvp2c_isaac_training_calibration.py:999` derives the current
  offline action-authority gate.
- `scripts/run_mvp2c_isaac_training_calibration.py:2184` builds the `v0_7c`
  child slice artifacts.
- `scripts/run_mvp2b_isaac_proof_evaluator.py:1480` starts the runtime action
  prediction/diagnostic path.
- `scripts/run_mvp2b_isaac_proof_evaluator.py:1707` records
  `post_adapter_action_vector`.

## ADR

Decision:

```text
Implement a staged harness report builder before any v0_7d slice.
```

Drivers:

- Phase E has been used as a debugger too many times.
- `v0_7c` revealed a concrete final-action authority gap.
- Harnesses should classify root causes before repair slices are created.

Alternatives considered:

- Implement `v0_7d` immediately: rejected because it repeats the blind-slice
  loop.
- Implement all H0-H17 fully in one pass: rejected because it is too broad and
  delays the close-critical root-cause report.
- Implement only post-adapter z gate tests: rejected because it ignores schema,
  base-servo, source authenticity, and normalization failure classes.

Why chosen:

- Staged harnessing catches the known blocker while creating the evidence
  structure needed to stop future Phase E loops.

Consequences:

- MVP-2 remains Not Closed after this plan.
- `v0_7d` becomes a follow-up generated from `mvp2e_harness_report.json`.
- Some harnesses may initially be `not_evaluated`, but all must be explicit.

Architect review addendum:

- Harness-only mode must reject `--clean`; it must not delete or regenerate the
  existing v0.7c evidence it is supposed to diagnose.
- Root-cause recommendation is evidence-gated. Missing H1/H2/H3/H15 evidence
  yields `root_cause_status="missing_evidence"` and
  `recommended_downstream_slice=null`.
- H0/H14 held-out leakage means protected seed access in `21000-21049`, not a
  legacy diagnostic path or trace label containing `heldout`.
- Root-cause classification must expose one deterministic
  `primary_root_cause_class`, optional `secondary_root_cause_candidates`, and
  `missing_required_evidence`.

Follow-ups:

- If root cause is `ACTION_AUTHORITY_POST_ADAPTER_Z_LEAK`, write a separate
  `v0_7d_action_authority_post_adapter_z_gate` spec.
- If root cause is schema/adapter mismatch, repair schema before any policy
  slice.

## Implementation Steps

- [ ] Step 1: RED tests for harness config/report shape
  - Add tests for hash-stable `mvp2e_harness_config`.
  - Add tests that H0-H17 keys are always present.
  - Add tests that held-out/calibration access flags fail closed.
  - Expected files:
    - `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] Step 2: Add constants and artifact helpers
  - Add schema constants:
    - `rdf_mvp2e_harness_config_v0.1.0`
    - `rdf_mvp2e_harness_report_v0.1.0`
    - `rdf_mvp2e_harness_gate_manifest_v0.1.0`
  - Add output directory:
    - `harness_gated_closure`
  - Add helpers:
    - `build_mvp2e_harness_config`
    - `validate_mvp2e_harness_config`
    - `build_empty_harness_record`
    - `write_mvp2e_harness_artifacts`

- [ ] Step 3: Implement H0 scenario/evaluator immutability
  - Validate `scenario_profile=v0_6`.
  - Validate held-out and calibration flags are false.
  - Validate success authority fields remain unchanged.
  - Record scenario/evaluator hashes where available.
  - Fail closed on mutation.

- [ ] Step 4: Implement trace index and H1/H2/H3
  - Build `harness_trace_index.json` from current `v0_7c` artifacts and runtime
    traces if present.
  - Do not rely only on `expressibility_sanity_gate_v0_7c.json`; current gate
    metadata may have `trace_dir=null` and `rollouts=0` while real v0.7c traces
    exist in adjacent runtime trace directories.
  - Discover adjacent v0.7c runtime trace JSON files under the existing
    `isaac_runtime_expressibility_sanity_v0_7c` evidence tree, while preserving
    H0/H14 protected-seed leakage semantics.
  - Read per-step diagnostics from `trace[].controller_action_diagnostics`,
    which is the current runtime trace artifact shape.
  - Required real-evidence fields:
    - `controller_action_diagnostics`
    - `raw_action_after_authority`
    - `residual_z_after_authority`
    - `post_adapter_action_vector`
    - real v0.7c trace path and sha256
  - H1 checks:
    - `residual_z_after_authority == 0.0` in `ALIGN`.
    - `post_adapter_action_vector[2] == 0.0` in `ALIGN`.
  - H2 checks adapter final-action invariant:
    - if post-authority z is zero, post-adapter z must stay zero.
  - H3 checks base servo premature descent:
    - base-only or base-derived `ALIGN` z must not create post-adapter descent
      before centering.
  - Current `v0_7c` should classify as `ACTION_AUTHORITY_POST_ADAPTER_Z_LEAK`
    or `BASE_SERVO_PREMATURE_DESCENT`, not as success.
  - Missing real-evidence fields must mark H1/H2/H3 as `missing_evidence` and
    must block downstream slice recommendation.

- [ ] Step 5: Implement H15 normalization/action schema fairness
  - Verify candidate/baseline share:
    - adapter id
    - authority filter config hash
    - base servo config hash
    - trainer family
    - feature schema
    - hyperparameters
    - normalization/scaling metadata where present
  - Fail closed on mismatches.

- [ ] Step 6: Represent remaining harnesses with evidence-aware records
  - H4 reads `train_generation_runtime_gate.json` and records scripted expert
    viability.
  - H5 reads phase/action metadata and records phase/mode consistency.
  - H6 checks train/runtime schema fields.
  - H7 records action divergence metrics where trace rows and predictions exist.
  - H9/H11/H12/H14 record current evidence or `not_evaluated` with reason.
  - H8/H10/H13/H16 are included as credibility/statistical tiers.

- [ ] Step 7: Build root-cause classifier
  - Input: H0-H15 records.
  - Output:
    - `primary_root_cause_class`
    - `root_cause_class` as a backward-compatible alias for the primary class
    - `root_cause_status`
    - `secondary_root_cause_candidates`
    - `missing_required_evidence`
    - `classifier_precedence`
    - `recommended_downstream_slice`
    - `downstream_slice_created=false`
    - `close_critical_passed=false` for current `v0_7c`.
  - Root cause must be one of the pre-registered classes in the spec.
  - Deterministic precedence:
    1. `EVALUATOR_OR_SCENARIO_MUTATION`
    2. `EXPERT_SOURCE_INVALID`
    3. `NORMALIZATION_OR_ADAPTER_SCHEMA_MISMATCH`
    4. `ACTION_AUTHORITY_POST_ADAPTER_Z_LEAK`
    5. `BASE_SERVO_PREMATURE_DESCENT`
    6. `PHASE_LABEL_RUNTIME_MISMATCH`
    7. `TRAIN_RUNTIME_SCHEMA_MISMATCH`
    8. `SATURATION_DOMINATED_CONTROL`
    9. `ACTION_DIVERGENCE_UNDER_COVARIATE_SHIFT`
    10. `TRAIN_SUPPORT_OOD_ROLLOUT`
  - If required H1/H2/H3/H15 evidence is missing, set
    `root_cause_status="missing_evidence"`,
    `primary_root_cause_class=null`, and
    `recommended_downstream_slice=null`.

- [ ] Step 8: Add CLI guard
  - Add mode:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7c \
  --harness-gated-closure-only \
  --pretty
```

  - This mode must never start Isaac.
  - It must write persistent evidence artifacts and `evidence_manifest.json`.
  - It must reject `--clean` before any output deletion.
  - It must reject incompatible modes such as full run, expressibility,
    calibration, or held-out execution.
  - It must not call `_prepare_output_dir(..., clean=True)` or the full proof
    builder path.

- [ ] Step 8a: Encode H0/H14 held-out leakage semantics
  - Treat protected seed range `21000-21049` as held-out leakage.
  - Treat legacy trace/path labels such as `isaac_runtime_heldout_rollout_traces`
    as diagnostic labels only when the scenario seed is outside the protected
    range.
  - Preserve the existing interpretation:
    `directory_name_only_not_protected_seed_split`.

- [ ] Step 9: Integration and regression verification
  - Run focused tests:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  -k "harness_gated or mvp2e_harness or v07c or v0_7c or action_authority" -q
```

  - Run full relevant tests:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -q
```

  - Run static checks:

```bash
uv run python -m compileall -q scripts apps/api/app apps/api/tests
uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py \
  scripts/run_mvp2b_isaac_proof_evaluator.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py
git diff --check
```

- [ ] Step 10: Documentation update
  - Update:
    - `docs/developer/worklog.md`
    - `docs/developer/debugging_guide.md`
    - `tasks/todo.md`
    - `Handoff.md`
  - State that MVP-2 remains Not Closed.
  - State that `v0_7d` is still not created until harness report classification.

## Acceptance Criteria

- `mvp2e_harness_report.json` exists and is hash-stable.
- H0-H3/H15 are executable and covered by focused tests.
- H0-H17 keys are present in the report.
- Current `v0_7c` is classified without opening calibration or held-out.
- Missing required real evidence fails closed with no downstream slice
  recommendation.
- `downstream_slice_created=false`.
- `mvp2_closed=false`.
- `--harness-gated-closure-only --clean` is rejected before output deletion.
- No actual Isaac command is run by the harness-only mode.
- Existing v0.7c regression tests continue to pass.

## Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Harness builder becomes another large monolith | Keep helper functions small and artifact-only in the first pass |
| H1/H2/H3 classification overlaps | Allow multiple candidate root causes but require one primary class plus evidence |
| Missing runtime traces cause fake certainty | Use `missing_evidence` status and do not recommend downstream slice unless required evidence exists |
| Harness-only mode deletes evidence with `--clean` | Reject `--clean` before any output preparation |
| Legacy held-out path labels trigger false leakage | Leakage is protected seed `21000-21049`; path labels are diagnostic unless seed is protected |
| Harness weakens MVP-2 gate | Mark harness as diagnosis only; env-native/Phase E/held-out authority unchanged |
| Scope expands into new policy | Stop rule: no `v0_7d`, no training, no Isaac in this plan |

## Available-Agent-Types Roster

- `executor`: implement small harness helpers and CLI mode.
- `test-engineer`: write focused tests and fixture traces.
- `architect`: review authority hierarchy and slice boundaries.
- `critic`: verify no hidden policy uplift or held-out leakage.
- `verifier`: run final evidence checks.

## Follow-up Staffing Guidance

Recommended execution path:

```text
$ultragoal implement docs/superpowers/plans/2026-06-12-mvp2e-harness-gated-closure.md
```

Reasoning by lane:

- executor: medium, code/test implementation.
- test-engineer: medium, focused tests and regression commands.
- verifier: high, final claim-boundary and evidence review.

Team path if parallelizing:

```text
$team implement docs/superpowers/plans/2026-06-12-mvp2e-harness-gated-closure.md
```

Parallel split:

- Lane A: H0/H15 schema and fairness gates.
- Lane B: H1/H2/H3 action authority and trace index.
- Lane C: CLI/artifact writer and documentation.

Team verification path:

- Team must return changed files, focused test output, generated harness artifact
  paths, and held-out seal proof.
- Ultragoal should checkpoint only after the leader verifies those outputs.

Goal-mode follow-up suggestions:

- `$ultragoal`: default durable implementation follow-up.
- `$team`: useful if H0/H15 and H1/H2/H3 are split in parallel.
- `$ralph`: fallback only if a single-owner persistent verify/fix loop is
  explicitly desired.
- `$autoresearch-goal`: not recommended; research is already synthesized into
  the spec.
- `$performance-goal`: not applicable.
