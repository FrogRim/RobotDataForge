# MVP-2E v0.7h Calibration Pre-Signal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `v0_7h`, an actual Isaac calibration pre-signal gate for the already-passing `v0_7g` policy slice.

**Architecture:** Reuse `v0_7g` baseline/candidate policy artifacts and the existing Isaac evaluator backend. Build a calibration-only runtime manifest from seeds `20000-20029`, run both policies in actual Isaac, write a non-closure calibration gate, and keep held-out `21000-21049` sealed.

**Tech Stack:** Python 3.11, NumPy, pytest, IsaacLab `Isaac-Factory-PegInsert-Direct-v0`, existing `run_mvp2c_isaac_training_calibration.py`.

---

## Source Artifacts

- Spec:
  `docs/superpowers/specs/2026-06-15-mvp2e-v07h-calibration-presignal-design.md`
- Parent evidence:
  `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_7g_xy_authority_saturation_repair/`
- Roadmap:
  `docs/superpowers/plans/2026-06-12-mvp2-closed-roadmap.md`

## File Structure

### Modify

- `scripts/run_mvp2c_isaac_training_calibration.py`
  - Add `v0_7h` constants.
  - Add calibration runtime manifest builder.
  - Add calibration pre-signal gate derivation.
  - Add actual Isaac calibration runtime function.
  - Add CLI mode `--calibration-presignal-only`.
  - Extend pre-heldout status to recognize `v0_7g` + `v0_7h`.

- `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
  - Add focused `v0_7h` tests.

- `docs/developer/worklog.md`
- `tasks/todo.md`
- `Handoff.md`

### Generated

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_7h_calibration_presignal/
    calibration_runtime_manifest_v0_7h.json
    calibration_presignal_gate_v0_7h.json
    calibration_rollout_summary_v0_7h.json
    calibration_external_rollouts/
      baseline_calibration_rollouts_v0_7h.json
      candidate_calibration_rollouts_v0_7h.json
calibration_presignal_gate.json
```

## Task 1: RED tests for v0.7h calibration manifest and gate

**Files:**

- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] Add helper `_write_v07h_parent_chain(script, output_dir)` that builds minimal `v0_7g` parent artifacts and writes a passed `expressibility_sanity_gate_v0_7g.json`.
- [ ] Add `test_v07h_builds_calibration_runtime_manifest_without_heldout_access`:
  - Build scenario manifest `v0_6`.
  - Call `build_v07h_calibration_runtime_manifest`.
  - Assert every scenario has `split == "held_out"` for backend compatibility.
  - Assert every scenario has `source_split == "calibration"`.
  - Assert seeds are `20000-20029`.
  - Assert protected held-out `21000-21049` is absent.
- [ ] Add `test_v07h_gate_passes_on_candidate_calibration_presignal`:
  - Provide baseline rollouts with 6/30 success and candidate with 10/30 success.
  - Assert `passed=true`, `heldout_allowed=true`, `mvp2_closed=false`.
- [ ] Add `test_v07h_gate_fails_when_candidate_not_above_baseline`.
- [ ] Add `test_v07h_gate_fails_when_candidate_below_minimum_success`.
- [ ] Add `test_v07h_gate_rejects_protected_heldout_seed_access`.
- [ ] Add `test_v07h_requires_passed_v07g_expressibility_gate`.
- [ ] Add `test_v07h_cli_calibration_presignal_generates_nonclosure_artifacts` with monkeypatched runtime backend.

## Task 2: Implement v0.7h manifest and gate helpers

**Files:**

- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] Add constants:
  - `V07H_POLICY_SLICE_ID = "v0_7g"`
  - `V07H_SLICE_ID = "mvp2e_v07h_calibration_presignal"`
  - `V07H_CHILD_OUTPUT_DIRNAME = "v0_7h_calibration_presignal"`
  - `V07H_CALIBRATION_PRESIGNAL_SCHEMA_VERSION`
  - `V07H_CALIBRATION_SUCCESS_MINIMUM = 0.30`
- [ ] Add `load_required_v07h_parent_expressibility_gate(output_dir)`.
  - Require `v0_7g` gate `passed=true`.
  - Require `runtime_backend=isaac_runtime`.
  - Reject held-out access.
- [ ] Add `build_v07h_calibration_runtime_manifest(output_dir, manifest)`.
  - Use original `split == "calibration"` scenarios only.
  - Reject seeds in protected held-out range.
  - Copy each row with `split="held_out"`, `source_split="calibration"`, and `semantic_eval_split="calibration"`.
  - Write `calibration_runtime_manifest_v0_7h.json`.
- [ ] Add `derive_v07h_calibration_presignal_gate(...)`.
  - Compute baseline/candidate success rates.
  - Pass only if candidate > baseline and candidate >= 0.30.
  - Always set `mvp2_closed=false`, `policy_uplift_proven=false`, `heldout_21000_21049_accessed=false`.

## Task 3: Implement actual Isaac calibration runtime

**Files:**

- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] Add `run_v07h_calibration_presignal_runtime(...)`.
  - Read parent `v0_7g` candidate/baseline policy artifacts.
  - Read and validate `offline_xy_authority_gate_v0_7g.json`.
  - Read and validate `expressibility_sanity_gate_v0_7g.json`.
  - Build calibration runtime manifest.
  - Call `IsaacConnectorInsertionEvaluatorBackend(...).run(...)` with both policies and `min_rollouts_per_policy=30`.
  - Write `baseline_calibration_rollouts_v0_7h.json` and `candidate_calibration_rollouts_v0_7h.json`.
  - Write `calibration_rollout_summary_v0_7h.json`.
  - Write `calibration_presignal_gate_v0_7h.json`.
  - Write compatibility pointer `calibration_presignal_gate.json`.

## Task 4: Add CLI dispatch and pre-heldout integration

**Files:**

- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] Add CLI flag `--calibration-presignal-only`.
- [ ] Include `--calibration-presignal-only` in policy-slice guarded modes.
- [ ] Require `--scenario-profile v0_6 --policy-slice v0_7g`.
- [ ] Reject incompatible modes (`--offline-relabel-only`, `--expressibility-sanity-only`, `--depth-zero-diagnosis-only`, `--harness-gated-closure-only`, `--train-generation-probe-only`, `--repair-probe-only`, `--capture-radius-probe-only`, `--recovery-overlay-induction-only`).
- [ ] Extend `_command_from_args`.
- [ ] Extend `resolve_v06_preheldout_gate_status(output_dir, policy_slice="v0_7g")`:
  - read `v0_7g/offline_xy_authority_gate_v0_7g.json`;
  - read `v0_7g/expressibility_sanity_gate_v0_7g.json`;
  - read top-level `calibration_presignal_gate.json`;
  - `heldout_allowed=true` only when all pass.

## Task 5: Verification

**Commands:**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  -k "v07h or v0_7h or calibration_presignal" -q

uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py \
  -k "v07g or v0_7g or xy_authority or v07h or calibration_presignal" -q

uv run python -m py_compile scripts/run_mvp2c_isaac_training_calibration.py
```

If focused tests pass and parent `v0_7g` artifacts exist, run actual Isaac:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_7g \
  --calibration-presignal-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

## Task 6: Branch after calibration

If `calibration_presignal_gate_v0_7h.passed=true`:

- Add the next ultragoal subgoal for held-out A/B `v0_7i`.
- Do not claim MVP-2 Closed yet.

If it fails:

- Add the next ultragoal subgoal for `v0_7i_calibration_failure_diagnosis`.
- Keep held-out sealed.
