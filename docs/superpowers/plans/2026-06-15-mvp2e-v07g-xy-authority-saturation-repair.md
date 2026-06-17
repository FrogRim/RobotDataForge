# MVP-2E v0.7g XY Authority Saturation Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `v0_7g`, a shared final post-adapter xy authority repair
that addresses `v0_7f`'s classified `XY_SATURATION_CENTERING_INSTABILITY`
without weakening MVP-2 proof boundaries.

**Architecture:** `v0_7g` inherits `v0_7e` policy artifacts and adds a final
post-adapter xy authority after the existing final z authority. It must pass
offline gates before actual Isaac Phase E can run. It is not closure authority:
MVP-2 remains open until positive curated > uncurated held-out policy uplift is
proven.

**Tech Stack:** Python 3.11, NumPy, pytest, existing MVP-2B/MVP-2C proof
scripts.

---

## Source Artifacts

- Spec:
  `docs/superpowers/specs/2026-06-15-mvp2e-v07g-xy-authority-saturation-repair-design.md`
- Context:
  `.omx/context/mvp2e-v07g-xy-authority-saturation-repair-20260615T062905Z.md`
- PRD:
  `.omx/plans/prd-mvp2e-v07g-xy-authority-saturation-repair.md`
- Test spec:
  `.omx/plans/test-spec-mvp2e-v07g-xy-authority-saturation-repair.md`
- Parent evidence:
  `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7e_shared_hysteresis_parity_repair/`
- Diagnosis evidence:
  `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7f_depth_zero_xy_saturation_diagnosis/`

## RALPLAN-DR Summary

### Principles

1. Repair the diagnosed action authority failure before changing policy/trainer.
2. Keep env-native success authority and 10-consecutive window unchanged.
3. Apply xy authority symmetrically to baseline and candidate.
4. Preserve candidate/baseline attribution; do not turn the policy into a pure
   shared servo.
5. Keep calibration and held-out `21000-21049` sealed until Phase E passes.

### Decision Drivers

1. `v0_7f` classified `XY_SATURATION_CENTERING_INSTABILITY` as the primary root
   cause.
2. Policy traces show mean xy saturation near 0.992 while expert reference mean
   is near 0.044.
3. Existing z authority works as a final mutation layer, so xy authority should
   use the same architectural position after selected adapter mutation.

### Viable Options

**Option A: retrain or redesign policy/trainer. Rejected.**

The current evidence points to runtime action saturation after the selected
adapter, not a missing model class. Retraining before fixing the final authority
layer repeats the same saturation failure path.

**Option B: change selected adapter config. Rejected.**

The selected adapter is calibration-frozen. Mutating it would blur selector
integrity and re-open attribution concerns. A final shared authority layer is
the safer repair surface.

**Option C: add shared final post-adapter xy authority. Chosen.**

This matches the successful v0.7d/v0.7e z authority pattern, keeps adapter
selection frozen, and directly targets saturation-dominated centering
instability.

## ADR

**Decision:** Add `v0_7g_xy_authority_saturation_repair` as a child slice of
`v0_7e`, with a required final post-adapter xy authority gate.

**Drivers:** v0.7f root-cause classification, policy/expert saturation gap,
and need to avoid calibration/held-out access before Phase E.

**Alternatives considered:** policy/trainer redesign, selected adapter config
change, success metric relaxation, or direct rerun of Phase E.

**Why chosen:** It is the smallest repair that targets the classified failure
while preserving the existing proof boundaries and frozen adapter lineage.

**Consequences:** Offline action replay can prove the final action envelope is
less saturated, but actual lateral state regression can only be verified in
future Isaac Phase E traces.

**Follow-ups:** If Phase E passes, plan Phase F calibration freeze. If Phase E
fails, build the next artifact-only diagnosis from v0.7g traces.

---

## File Structure

### Modify

- `scripts/run_mvp2b_isaac_proof_evaluator.py`
  - Add v0.7g constants, config validation, final xy authority application, and
    diagnostics.

- `scripts/run_mvp2c_isaac_training_calibration.py`
  - Add v0.7g constants, child slice builder, offline gate, CLI dispatch, and
    Phase E runtime dispatch.

- `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
  - Add runtime authority tests.

- `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
  - Add slice/gate/CLI/claim-boundary tests.

- `docs/developer/worklog.md`
- `tasks/todo.md`
- `Handoff.md`

### Generated During Execution

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_7g_xy_authority_saturation_repair/
    v0_7g_xy_authority_config.json
    candidate_policy_artifact_v0_7g.json
    baseline_policy_artifact_v0_7g.json
    offline_xy_authority_gate_v0_7g.json
    v0_7g_xy_authority_manifest.json
    expressibility_sanity_gate_v0_7g.json
```

---

## Implementation Steps

### Task 1: RED tests for evaluator-side v0.7g xy authority

**Files:**

- Modify: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`

- [ ] Add helper that builds a `v0_7g` policy artifact inheriting v0.7e
  metadata and final z authority.
- [ ] Add `test_v07g_final_xy_authority_config_is_hash_stable`.
- [ ] Add `test_v07g_runtime_applies_xy_authority_after_adapter_and_final_z`.
- [ ] Add `test_v07g_runtime_reduces_saturated_xy_near_center`.
- [ ] Add `test_v07g_runtime_preserves_xy_sign`.
- [ ] Add `test_v07g_runtime_does_not_mutate_z_authority`.
- [ ] Add `test_v07g_runtime_keeps_env_native_stable_hold_authority`.
- [ ] Add `test_v07g_runtime_rejects_candidate_specific_xy_authority`.
- [ ] Add `test_v07g_runtime_records_pre_and_post_xy_authority_vectors`.
- [ ] Add `test_v07g_runtime_records_post_z_pre_xy_authority_vector`.
- [ ] Add `test_v07g_runtime_has_no_mutation_after_final_xy_authority`.
- [ ] Add `test_v07g_runtime_fails_if_xy_authority_changes_z_component`.

### Task 2: Implement evaluator-side final xy authority

**Files:**

- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`

- [ ] Add constants:
  - `V07G_POLICY_SLICE_ID = "v0_7g"`;
  - `V07G_SLICE_ID = "mvp2e_v07g_xy_authority_saturation_repair"`;
  - `V07G_FINAL_XY_AUTHORITY_CONFIG_SCHEMA_VERSION`;
  - `V07G_FINAL_POST_ADAPTER_XY_AUTHORITY_ID`.
- [ ] Add `_validated_v07g_final_xy_authority_config(policy_artifact)`.
- [ ] Add `_apply_v07g_final_post_adapter_xy_authority(...)`.
- [ ] Apply the xy authority after `_apply_v07d_final_post_adapter_authority`.
- [ ] Preserve final z authority diagnostics and add:
  - `final_post_adapter_xy_authority_id`;
  - `final_post_adapter_xy_authority_config_sha256`;
  - `pre_xy_authority_action_vector`;
  - `post_z_pre_xy_authority_action_vector`;
  - `post_xy_authority_action_vector`;
  - `xy_authority_applied`;
  - `xy_authority_reason`;
  - `xy_authority_preserved_sign`.
- [ ] Ensure `no_mutation_after_final_post_adapter_authority` means no mutation
  after final xy authority, not after the earlier v0.7d z authority.

### Task 3: RED tests for v0.7g child slice and offline gate

**Files:**

- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] Add `test_v07g_builds_policy_artifacts_from_v07e_parent`.
- [ ] Add `test_v07g_requires_v07f_classified_xy_saturation_parent_report`.
- [ ] Add `test_v07g_offline_gate_requires_after_authority_saturation_below_expert_bound`.
- [ ] Add `test_v07g_offline_gate_preserves_candidate_baseline_attribution`.
- [ ] Add `test_v07g_offline_gate_fails_when_xy_authority_erases_attribution`.
- [ ] Add `test_v07g_offline_gate_fails_when_pre_xy_delta_absent`.
- [ ] Add `test_v07g_offline_gate_reports_pre_post_xy_delta_and_retention_ratio`.
- [ ] Add `test_v07g_offline_gate_keeps_z_and_stable_hold_authority`.
- [ ] Add `test_v07g_offline_gate_blocks_closure_claims`.
- [ ] Add `test_v07g_cli_offline_relabel_generates_artifacts`.
- [ ] Add `test_v07g_expressibility_sanity_requires_passed_offline_gate`.
- [ ] Add `test_v07g_expressibility_sanity_rejects_failed_offline_gate`.
- [ ] Add `test_v07g_rejects_protected_heldout_seed_access`.

### Task 4: Implement v0.7g child slice and offline gate

**Files:**

- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] Add v0.7g constants and output dirname.
- [ ] Add `load_required_v07g_parent_diagnosis_report(output_dir)`.
- [ ] Add `build_v07g_xy_authority_config(...)`.
- [ ] Add `validate_v07g_xy_authority_config_contract(...)`.
- [ ] Add `build_v07g_policy_artifact_payload(...)`.
- [ ] Add `derive_v07g_offline_xy_authority_gate(...)`.
  - Report `pre_xy_authority_candidate_baseline_xy_delta_l2_mean`.
  - Report `post_xy_authority_candidate_baseline_xy_delta_l2_mean`.
  - Report `post_xy_authority_candidate_baseline_xy_delta_nonzero_fraction`.
  - Report `xy_delta_retention_ratio`.
  - Fail if `pre_delta_l2_mean <= 1.0e-6` with
    `candidate_baseline_pre_xy_delta_absent`.
  - Fail if `post_delta_l2_mean <= 1.0e-6`.
  - Fail if `post_delta_nonzero_fraction < 0.10`.
  - Fail if `xy_delta_retention_ratio < 0.10`.
- [ ] Add `build_v07g_xy_authority_saturation_repair_slice(output_dir=...)`.
- [ ] Write:
  - `v0_7g_xy_authority_config.json`;
  - `candidate_policy_artifact_v0_7g.json`;
  - `baseline_policy_artifact_v0_7g.json`;
  - `offline_xy_authority_gate_v0_7g.json`;
  - `v0_7g_xy_authority_manifest.json`.
- [ ] Ensure artifact fields include:
  - `future_ab_ready=false`;
  - `mvp2_closed=false`;
  - `policy_uplift_proven=false`;
  - `calibration_opened=false`;
  - `heldout_21000_21049_accessed=false`;
  - `proof_authority=false`.

### Task 5: CLI dispatch and Phase E gate wiring

**Files:**

- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] Include `v0_7g` in `--offline-relabel-only` policy-slice allowlist.
- [ ] Add `run_v07g_expressibility_sanity_runtime(...)`.
- [ ] Require passed `offline_xy_authority_gate_v0_7g.json` before actual
  Isaac Phase E.
- [ ] Keep Phase E output non-closure:
  - `mvp2_closed=false`;
  - `policy_uplift_proven=false`;
  - `calibration_opened=false`;
  - `heldout_21000_21049_accessed=false`.

### Task 6: Documentation and verification

**Files:**

- Modify: `docs/developer/worklog.md`
- Modify: `tasks/todo.md`
- Modify: `Handoff.md`

- [ ] Record implementation summary, evidence, verification commands, and next
  valid step.
- [ ] Run focused tests first:

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  -k "v07g or v0_7g or xy_authority or saturation" -q

uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  -k "v07g or v0_7g or xy_authority or saturation" -q
```

- [ ] Run offline artifact build:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7g \
  --offline-relabel-only \
  --pretty
```

- [ ] Run relevant regression checks:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  -k "v07d or v0_7d or v07e or v0_7e or v07f or v0_7f or v07g or v0_7g or harness or authority" -q

uv run python -m compileall -q scripts apps/api/app apps/api/tests

uvx ruff check scripts/run_mvp2b_isaac_proof_evaluator.py \
  scripts/run_mvp2c_isaac_training_calibration.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py

git diff --check
```

### Task 7: Actual Isaac Phase E only after offline gates pass

**Files:**

- Generated evidence only unless runtime trace diagnosis requires a follow-up
  plan.

- [ ] If offline gates pass and Isaac runtime is available, run:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7g \
  --expressibility-sanity-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

- [ ] If Phase E passes `>=2/5`, the next valid step is Phase F calibration
  freeze planning.
- [ ] If Phase E fails, the next valid step is artifact-only diagnosis from
  v0.7g actual Isaac traces.

---

## Stop Conditions

Stop and record a blocker if:

- env-native success authority or 10-consecutive window must be weakened;
- calibration or held-out `21000-21049` must be opened before Phase E passes;
- DB migration is required;
- baseline/candidate must receive different xy authority;
- shared authority erases candidate/baseline attribution;
- force-control, retry, withdraw, search, real robot, HMD/OpenXR, or ROS2/DDS
  runtime becomes necessary.

## Available Agent Types

- `executor`: implement code and tests.
- `test-engineer`: verify test strategy and regression coverage.
- `architect`: review authority layering and claim boundaries.
- `critic`: review plan consistency and acceptance criteria.
- `verifier`: check completion evidence.

## Execution Recommendation

Use `$ultragoal` as the durable sequential owner. Use native subagents only for
bounded review or disjoint implementation lanes. Do not use `$ralph` unless a
single-owner verification loop is explicitly needed after ultragoal evidence is
stale.
