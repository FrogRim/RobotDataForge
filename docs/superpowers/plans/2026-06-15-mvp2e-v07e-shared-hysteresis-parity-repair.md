# MVP-2E v0.7e Shared Hysteresis Parity Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `v0_7e`, a child MVP-2E policy slice that restores shared
stateful hysteresis parity between expert generation and policy evaluation,
then proves offline that Phase E may be rerun without opening calibration or
held-out `21000-21049`.

**Architecture:** `v0_7e` inherits the `v0_7d` final post-adapter authority,
env-native stable-hold authority, selected adapter, trainer, and feature schema.
It adds a shared, rollout-local hysteresis controller that decides whether z
motion may remain open after lateral gate entry. The same hysteresis config is
applied to baseline and candidate, and an attribution-preservation gate verifies
that shared infrastructure does not erase candidate-vs-baseline action
differences before any Isaac Phase E rerun.

**Tech Stack:** Python 3.11, NumPy, HDF5, pytest, existing MVP-2B/MVP-2C proof
scripts.

---

## Source Artifacts

- Spec:
  `docs/superpowers/specs/2026-06-15-mvp2e-v07e-shared-hysteresis-parity-repair-design.md`
- Context:
  `.omx/context/mvp2e-v07e-shared-hysteresis-parity-repair-20260615T030013Z.md`
- PRD:
  `.omx/plans/prd-mvp2e-v07e-shared-hysteresis-parity-repair.md`
- Test spec:
  `.omx/plans/test-spec-mvp2e-v07e-shared-hysteresis-parity-repair.md`
- Autoresearch result:
  `.omx/specs/autoresearch-mvp2e-v07e-hysteresis-parity/result.json`
- Parent artifacts:
  `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7d_action_authority_post_adapter_z_gate/`

## RALPLAN-DR Summary

### Principles

1. Phase E may only run after offline gates prove the runtime parity repair is
   wired and fair.
2. Shared hysteresis is infrastructure parity, not a candidate-specific policy
   advantage.
3. Final post-adapter authority remains the final action mutation boundary.
4. Attribution must be guarded: unlocking mechanics is not enough if
   candidate-vs-baseline action differences collapse.
5. Historical `v0_7d` failure evidence remains immutable.

### Decision Drivers

1. Autoresearch shows expert z-descent windows of 28-43 steps while policy
   windows are 0-4 steps on the same train-side scenarios.
2. `scripts/run_mvp2b_isaac_proof_evaluator.py:1862` only enables the existing
   v0.6 controller when adapter config has `controller_version`, while v0.7d
   runtime lacks a policy-level shared hysteresis contract.
3. Autoresearch marks A/B signal risk high because shared hysteresis may unlock
   Phase E while erasing candidate-vs-baseline differences.

### Viable Options

**Option A: rerun Phase E with current `v0_7d`. Rejected.**

Evidence already shows `v0_7d` fails `0/5`, with policy traces never reaching
positive insertion depth. Rerunning without a runtime parity change spends Isaac
time on the same known blocker.

**Option B: add `v0_7e` shared hysteresis parity with offline gates. Chosen.**

This directly targets the proven z-window parity gap, preserves `v0_7d` lineage,
keeps baseline/candidate fairness by sharing the same infrastructure, and adds
an attribution guard before any Phase E rerun.

**Option C: retune xy gain or selected adapter scale. Rejected for this slice.**

Autoresearch does show xy saturation during z-open rows, but changing adapter
or servo gains would mix a new control intervention with the hysteresis parity
repair. This belongs in a later `v0_7f` only if `v0_7e` restores z windows and
still fails.

**Option D: change policy class or trainer. Rejected.**

The current evidence points to runtime authority parity, not model capacity.
Changing model class before restoring parity would broaden scope and weaken
attribution.

## ADR

**Decision:** Create `v0_7e_shared_hysteresis_parity_repair` as a child slice
that inherits `v0_7d` and adds shared stateful hysteresis plus three offline
gates: hysteresis parity, attribution preservation, and final authority
regression.

**Drivers:** v0.7d Phase E `0/5`, expert-vs-policy z-window mismatch, missing
policy-side stateful controller, and high A/B attribution risk.

**Alternatives considered:** rerun v0.7d unchanged, retune selected adapter/xy
gain, or replace policy/trainer.

**Why chosen:** It is the narrowest repair that addresses the demonstrated
runtime parity gap while preserving the MVP-2 proof boundaries.

**Consequences:** `v0_7e` can only unlock a new Phase E attempt after offline
gates pass. Even if Phase E later passes, MVP-2 remains open until calibration
freeze and sealed held-out A/B prove positive uplift.

**Follow-ups:** If Phase E fails with z windows restored, open a new harness
report and likely plan `v0_7f` for xy saturation/contact dynamics. If Phase E
passes, write a separate calibration-freeze plan before any held-out access.

---

## File Structure

### Modify

- `scripts/run_mvp2b_isaac_proof_evaluator.py`
  - Add `v0_7e` constants and hash-stable hysteresis config validation.
  - Add a rollout-local hysteresis state helper that reuses or wraps
    `v06_phase_controller_step` at lines 1190-1227.
  - Thread hysteresis state through `_predict_policy_action_with_diagnostics`
    at lines 1440-1565 and `_apply_selected_action_adapter_with_diagnostics`
    at lines 1772-1948.
  - Preserve `_apply_v07d_final_post_adapter_authority` at lines 1744-1769 as
    the final enforcement boundary.
  - Add xy saturation / gate chatter diagnostics.

- `scripts/run_mvp2c_isaac_training_calibration.py`
  - Add `v0_7e` constants next to v0.7d constants at lines 227-237.
  - Add `build_v07e_hysteresis_authority_config` and validator next to the
    v0.7d config builder at lines 938-1003.
  - Add `build_v07e_policy_artifact_payload` beside the v0.7d payload builder
    at lines 2040-2089.
  - Add offline gates near v0.7d offline gate helpers at lines 2092-2367:
    hysteresis parity, attribution preservation, final authority regression.
  - Add `build_v07e_shared_hysteresis_parity_repair_slice` near the v0.7d
    child builder at lines 3628-3752.
  - Add `run_v07e_expressibility_sanity_runtime` near the v0.7d runtime gate at
    lines 6925-7035.
  - Add CLI `--policy-slice v0_7e` choices/guards near lines 11539-11600,
    offline manifest wiring near lines 11680-11704, and expressibility branch
    near lines 11952-11960.

- `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
  - Add v0.7e runtime tests near existing v0.7d helper/tests at lines 987-1417.

- `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
  - Add v0.7e artifact/gate tests near existing v0.7d tests at lines
    1135-1712.

- `docs/developer/worklog.md`
- `docs/developer/debugging_guide.md`
- `tasks/todo.md`
- `Handoff.md`

### Generated During Execution

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7e_shared_hysteresis_parity_repair/
  v0_7e_hysteresis_authority_config.json
  candidate_policy_artifact_v0_7e.json
  baseline_policy_artifact_v0_7e.json
  offline_hysteresis_parity_gate_v0_7e.json
  attribution_preservation_gate_v0_7e.json
  final_action_authority_regression_gate_v0_7e.json
  v0_7e_shared_hysteresis_parity_manifest.json
```

Only after offline gates pass and actual Phase E is intentionally run:

```text
  expressibility_sanity_gate_v0_7e.json
  isaac_runtime_expressibility_sanity_v0_7e/
```

---

## Implementation Steps

### Task 1: RED runtime tests for shared hysteresis parity

**Files:**

- Modify: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`

- [ ] Add `_v07e_policy_artifact` helper derived from `_v07d_policy_artifact`
  but with:
  - `policy_slice="v0_7e"`
  - `parent_policy_slice="v0_7d"`
  - `shared_hysteresis_authority_id`
  - `shared_hysteresis_authority_config`
  - `shared_hysteresis_authority_config_sha256`
  - `same_hysteresis_config_as_peer=true`

- [ ] Add `test_v07e_hysteresis_config_is_hash_stable`.

- [ ] Add `test_v07e_runtime_tracks_rollout_local_hysteresis_state`.

- [ ] Add `test_v07e_runtime_holds_descend_window_after_lateral_gate_entry`.
  This should fail RED because current runtime closes z on the next instantaneous
  `ALIGN`/lateral-gate chatter step.

- [ ] Add `test_v07e_runtime_preserves_v07d_align_block_when_hysteresis_closed`.

- [ ] Add `test_v07e_runtime_does_not_mutate_after_final_post_adapter_authority`.

- [ ] Add `test_v07e_runtime_records_xy_saturation_chatter_diagnostics`.

- [ ] Add `test_v07e_runtime_applies_same_hysteresis_config_to_baseline_and_candidate`.

### Task 2: RED artifact and offline-gate tests

**Files:**

- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] Add minimal v0.7e parent helper that starts from a v0.7d policy artifact.

- [ ] Add `test_v07e_hysteresis_authority_config_is_hash_stable`.

- [ ] Add `test_v07e_policy_artifacts_share_hysteresis_and_preserve_v07d_authority`.

- [ ] Add `test_v07e_offline_hysteresis_parity_gate_uses_existing_v07d_traces_only`.

- [ ] Add `test_v07e_offline_hysteresis_parity_gate_fails_on_heldout_access`.

- [ ] Add `test_v07e_offline_hysteresis_parity_gate_requires_3_of_5_counterfactual_windows`.

- [ ] Add `test_v07e_attribution_preservation_gate_fails_when_candidate_baseline_actions_collapse`.

- [ ] Add `test_v07e_attribution_preservation_gate_passes_when_shared_infrastructure_equal_and_actions_differ`.

- [ ] Add `test_v07e_final_authority_regression_gate_preserves_v07d_align_block_and_env_native_hold`.

- [ ] Add `test_v07e_builds_child_slice_without_mutating_v07d`.

- [ ] Add `test_v07e_cli_requires_offline_relabel_for_artifact_build`.

- [ ] Add `test_v07e_expressibility_sanity_fails_closed_without_all_offline_gates`.

### Task 3: Implement runtime hysteresis config and state

**Files:**

- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`

- [ ] Add constants:
  - `V07E_POLICY_SLICE_ID = "v0_7e"`
  - `V07E_SLICE_ID = "mvp2e_v07e_shared_hysteresis_parity_repair"`
  - `V07E_SHARED_HYSTERESIS_AUTHORITY_ID`
  - `V07E_HYSTERESIS_AUTHORITY_CONFIG_SCHEMA_VERSION`

- [ ] Add `_validated_v07e_hysteresis_authority_config(policy_artifact)`.
  It must fail if:
  - config missing;
  - hash mismatch;
  - `heldout_21000_21049_accessed` is not false;
  - candidate/baseline-specific flags are true;
  - parent final authority sha does not match v0.7d artifact metadata.

- [ ] Add a small runtime state object/dict:

```text
current_hysteresis_phase
z_window_remaining_steps
entered_descend_step
last_z_motion_allowed
hard_safety_escape_triggered
```

- [ ] Own this state in `_run_one_rollout`, reset it exactly once per rollout
  and per policy role, and explicitly pass it into and return it from the
  policy prediction/runtime path. Do not store hysteresis state in module-level
  globals, policy artifacts, or shared mutable singleton state.

- [ ] Add a deterministic update helper that:
  - enters `DESCEND` when lateral/orientation gates are satisfied;
  - keeps z open through the pre-registered hysteresis window;
  - does not treat `0.001m` chatter as a hard safety escape;
  - records diagnostic lower-bound `min_descend_window_reference_steps=28`;
  - resets only at rollout start.

- [ ] If reusing `v06_phase_controller_step`, wrap it with persistent
  `z_window_remaining_steps`. Direct single-row reuse is insufficient because
  the v0.6 helper still makes `DESCEND` z permission depend on instantaneous
  alignment, while `v0_7e` must preserve a held z window after lateral gate
  entry unless a hard safety escape fires.

- [ ] Thread the state through policy rollout diagnostics without changing
  trainer, feature schema, selected adapter, or success metric.

- [ ] Keep `_apply_v07d_final_post_adapter_authority` as final enforcement.
  No mutation may occur after it.

### Task 4: Implement v0.7e artifact builders and gates

**Files:**

- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] Add v0.7e constants and schema versions.

- [ ] Implement `build_v07e_hysteresis_authority_config`.
  It must write `v0_7e_hysteresis_authority_config.json` and include:
  - parent policy slice `v0_7d`;
  - parent final authority config sha;
  - `min_descend_window_reference_steps=28`;
  - `counterfactual_required_count=3`;
  - `counterfactual_scenario_count=5`;
  - `seed_19030_required=true`;
  - `candidate_specific=false`;
  - `baseline_specific=false`;
  - `heldout_21000_21049_accessed=false`;
  - config sha excluding the sha field.

- [ ] Implement `build_v07e_policy_artifact_payload`.
  It must inherit:
  - selected action adapter config/hash from `v0_7d`;
  - final post-adapter authority config/hash from `v0_7d`;
  - trainer family, feature schema, base servo config, authority filter config.

- [ ] Implement `derive_v07e_offline_hysteresis_parity_gate`.
  It reads existing v0.7d Phase E trace summaries and/or the persisted
  autoresearch result. It must fail closed on:
  - missing trace evidence;
  - protected held-out seed access;
  - fewer than 5 train-side scenarios;
  - fewer than 3 counterfactual windows `>=28`;
  - seed `19030` not satisfying the counterfactual window.

- [ ] Implement `derive_v07e_attribution_preservation_gate`.
  It must enforce:
  - shared infrastructure equality keys all true;
  - candidate and baseline policy artifact sha differ;
  - candidate and baseline are evaluated on the same train-side offline probe
    rows, with identical previous-action construction and identical shared
    hysteresis replay state;
  - candidate/baseline deltas are computed at the final post-authority action
    stage;
  - raw action and residual deltas are recorded as diagnostics but are not the
    primary pass/fail authority;
  - `candidate_baseline_action_delta_l2_mean > 1e-6`;
  - `candidate_baseline_action_delta_nonzero_fraction >= 0.10`;
  - no calibration/held-out/Isaac evidence read.

- [ ] Implement `derive_v07e_final_action_authority_regression_gate`.
  It must prove:
  - v0.7d final align z block still holds;
  - env-native stable hold authority still holds;
  - no post-final-authority mutation is introduced.

- [ ] Implement `build_v07e_shared_hysteresis_parity_repair_slice`.
  It writes all v0.7e artifacts and a manifest with:
  - all gate payloads;
  - all gate shas;
  - `failed_closed` from gate aggregate;
  - `phase_e_candidate_expressibility_unblocked`;
  - `future_ab_ready=false`;
  - `mvp2_closed=false`;
  - `policy_uplift_proven=false`;
  - `heldout_21000_21049_accessed=false`.

### Task 5: Add CLI wiring and fail-closed Phase E guard

**Files:**

- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] Add `v0_7e` to `--policy-slice` choices.

- [ ] Allow `--policy-slice v0_7e` only with:
  - `--offline-relabel-only`, or
  - `--expressibility-sanity-only`.

- [ ] Block `--harness-gated-closure-only --policy-slice v0_7e` unless a future
  separate harness-report spec explicitly permits it.

- [ ] Add offline relabel branch that writes v0.7e evidence manifest.

- [ ] Add `run_v07e_expressibility_sanity_runtime`.
  It must fail closed unless all three offline gates exist and pass:
  - `offline_hysteresis_parity_gate_v0_7e.json`;
  - `attribution_preservation_gate_v0_7e.json`;
  - `final_action_authority_regression_gate_v0_7e.json`.

- [ ] Preserve output fields:
  - `mvp2_closed=false`;
  - `policy_uplift_proven=false`;
  - `heldout_21000_21049_accessed=false`;
  - `calibration_opened=false`.

### Task 6: Documentation and handoff updates

**Files:**

- Modify: `docs/developer/worklog.md`
- Modify: `docs/developer/debugging_guide.md`
- Modify: `tasks/todo.md`
- Modify: `Handoff.md`

- [ ] Record implementation decisions, changed files, verification commands, and
  exact pass/fail outcomes.

- [ ] Add debugging guide section:

```text
MVP-2E v0.7e shared hysteresis parity:
  1. Build offline artifacts.
  2. Inspect three offline gates.
  3. Do not run Phase E if any gate failed.
  4. If Phase E fails with z window restored, classify next root cause.
```

- [ ] Re-state claim boundaries:
  - no MVP-2 Closed;
  - no policy uplift proof;
  - no held-out opening;
  - no real robot/HMD/visual policy claims.

---

## Verification Commands

RED:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  -k "v07e or v0_7e or hysteresis_parity or attribution_preservation" -q
```

Focused GREEN:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  -k "v07e or v0_7e or hysteresis_parity or attribution_preservation or final_action_authority" -q
```

Relevant regression:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -q
```

Offline artifact build:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --offline-relabel-only \
  --policy-slice v0_7e \
  --pretty
```

Static checks:

```bash
uv run python -m compileall -q scripts apps/api/app apps/api/tests
uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py \
  scripts/run_mvp2b_isaac_proof_evaluator.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py
git diff --check
```

Later gated Phase E command, only after offline gates pass:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7e \
  --expressibility-sanity-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

This command is not part of implementation completion and must not be run by
implementation workers unless all three offline v0.7e gates already exist and
pass.

---

## Acceptance Criteria

- [ ] v0.7e tests exist and fail before implementation.
- [ ] v0.7e runtime uses shared rollout-local hysteresis state.
- [ ] v0.7e final action authority remains after the selected adapter and after
  hysteresis permission calculation.
- [ ] v0.7e policy artifacts preserve v0.7d selected adapter, final authority,
  stable-hold authority, trainer, feature schema, and base servo lineage.
- [ ] `offline_hysteresis_parity_gate_v0_7e.passed=true`.
- [ ] `attribution_preservation_gate_v0_7e.passed=true`.
- [ ] `final_action_authority_regression_gate_v0_7e.passed=true`.
- [ ] `run_v07e_expressibility_sanity_runtime` fails closed unless all offline
  gates pass.
- [ ] Focused tests and relevant regression tests pass.
- [ ] compileall, ruff, and `git diff --check` pass.
- [ ] Docs and handoff are updated.
- [ ] `mvp2_closed=false` and `policy_uplift_proven=false` remain true
  boundaries in all generated v0.7e artifacts.

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Shared hysteresis makes baseline and candidate both behave identically | Attribution preservation gate blocks Phase E if action deltas collapse |
| Hysteresis hides off-center descent | Hard safety escape remains fail-closed; xy saturation diagnostics are recorded |
| Implementation regresses v0.7d final authority | Final authority regression gate and existing v0.7d tests remain in regression suite |
| Evidence lineage becomes ambiguous | v0.7e is a child slice and never mutates v0.7d artifacts |
| Isaac Phase E is run too early | CLI guard fails closed unless all v0.7e offline gates pass |
| Plan drifts into policy/trainer retuning | Explicit non-goals and tests preserve selected adapter/trainer/schema equality |
| Legacy path labels mention `heldout` for train-side expressibility probes | Keep protected held-out authority seed-based: `21000-21049` access remains false, and legacy path labels are diagnostics only |

## Available-Agent-Types Roster

- `executor` (`gpt-5.5`, medium): implementation in proof scripts and tests.
- `test-engineer` (`gpt-5.5`, medium): TDD coverage and regression command
  validation.
- `debugger` (`gpt-5.5`, high): only if offline gates fail unexpectedly.
- `verifier` (`gpt-5.5`, high): final claim-boundary and artifact review.
- `code-reviewer` (`gpt-5.5`, high): post-implementation review.
- `architect` (`gpt-5.5`, high): use only for scope expansion or next-slice
  design review.

## Follow-Up Staffing Guidance

Recommended default: `$ultragoal` with one executor lane.

Suggested lanes:

- Executor, medium reasoning:
  - owns `scripts/run_mvp2b_isaac_proof_evaluator.py`;
  - owns `scripts/run_mvp2c_isaac_training_calibration.py`;
  - owns focused tests.
- Verifier, high reasoning:
  - checks generated artifacts;
  - confirms no held-out/calibration access;
  - confirms claim boundary fields.

Use `$team` only if implementation needs parallel lanes:

- Lane A: runtime evaluator/hysteresis state.
- Lane B: training calibration artifact/gate builder.
- Lane C: tests/docs/verification.

Avoid `$ralph` unless the user explicitly asks for a legacy persistent
single-owner loop.

## Goal-Mode Follow-Up Suggestions

- `$ultragoal` is the default follow-up for implementing this plan with durable
  checkpoints.
- `$team` can be combined with `$ultragoal` if parallel execution is desired;
  Team returns checkpoint-ready evidence while Ultragoal owns the durable ledger.
- `$autoresearch-goal` is not the default because the research question has
  already been answered by the v0.7e autoresearch artifact.
- `$performance-goal` is not applicable; this is correctness/authority repair,
  not performance optimization.

## Team Launch Hints

Sequential default:

```bash
$ultragoal implement docs/superpowers/plans/2026-06-15-mvp2e-v07e-shared-hysteresis-parity-repair.md
```

Parallel option:

```bash
$team implement docs/superpowers/plans/2026-06-15-mvp2e-v07e-shared-hysteresis-parity-repair.md
```

Team verification path:

```text
1. Team reports changed files by lane.
2. Leader runs focused v0.7e pytest.
3. Leader runs relevant regression pytest.
4. Leader builds offline v0.7e artifacts.
5. Leader checks all three offline gates.
6. Leader runs compileall, ruff, git diff --check.
7. Ultragoal checkpoints only after evidence paths and command outputs are recorded.
```

## Review Changelog

Initial plan written from the approved v0.7e spec and autoresearch result. No
Architect/Critic changes applied yet.

Iteration 1 Architect changes applied:

- Made hysteresis state ownership explicit in `_run_one_rollout`.
- Required explicit state input/output through policy runtime paths.
- Clarified that direct single-row `v06_phase_controller_step` reuse is not
  enough without persistent `z_window_remaining_steps`.
- Tightened attribution gate to compare candidate/baseline on the same
  train-side rows with identical previous-action and hysteresis replay state,
  using final post-authority action deltas as the primary measurement.
- Clarified that the later Phase E command is not implementation-completion
  work and remains blocked until all offline v0.7e gates pass.
- Added a risk note distinguishing legacy `heldout` path labels from protected
  held-out seed access.
