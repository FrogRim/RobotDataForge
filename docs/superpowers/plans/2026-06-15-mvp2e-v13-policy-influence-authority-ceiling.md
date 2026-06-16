# MVP-2E v0.13 Policy Influence Authority Ceiling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` and `superpowers:executing-plans`. Implement task-by-task with focused verification after each major slice.

**Goal:** v0.12a에서 확인된 `RUNTIME_AUTHORITY_DOMINATES_LEARNED_RESIDUAL_OUTCOME`를 근거로, shared runtime authority가 baseline/candidate policy 차이를 지우지 못하게 ceiling을 걸고 fresh calibration/held-out에서 MVP-2 closure를 재시도한다.

**Architecture:** `run_mvp2c_isaac_training_calibration.py`에 v0.13 artifact-only builder와 actual Isaac runtime branch를 추가한다. `run_mvp2b_isaac_proof_evaluator.py`에는 v0.13 runtime policy slice wiring을 추가하되, v0.8h derived forced z progress injection lineage에는 넣지 않는다.

**Non-negotiable constraints:**
- held-out `38000-38049`는 v0.13 calibration gate 통과 전까지 열지 않는다.
- v0.13은 success metric을 바꾸지 않는다.
- baseline/candidate는 같은 policy class, trainer, adapter, authority ceiling을 사용한다.
- v0.13은 v0.8h style forced z progress injection을 사용하지 않는다.
- artifact-only gates는 closure authority가 아니다.

---

### Task 1: RED Tests

**Files:**
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
- Modify: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`

- [ ] Add training/calibration tests:
  - `test_v13_requires_v12a_runtime_authority_dominance_diagnosis`
  - `test_v13_builds_policy_influence_authority_ceiling_slice`
  - `test_v13_offline_policy_influence_gate_preserves_action_delta`
  - `test_v13_fresh_manifest_uses_37000_calibration_and_sealed_38000_heldout`
  - `test_v13_runtime_cli_rejects_clean_before_isaac`
  - `test_v13_runtime_cli_rejects_fake_backend_flags`

- [ ] Add evaluator tests:
  - v0.13 belongs to shared hysteresis/base-servo/final-z-authority runtime policy sets.
  - v0.13 is **not** in `V08H_DERIVED_POLICY_SLICE_IDS`.
  - v0.13 selected action adapter config uses reduced `xy_state_feedback_gain`.
  - v0.13 does not enable safe-entry progress injection diagnostics.

- [ ] Verify RED:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v13" -q
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -k "v13" -q
```

Expected: fail because v0.13 constants/builders/wiring do not exist yet.

---

### Task 2: Evaluator Runtime Wiring

**Files:**
- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`

- [ ] Add `V13_POLICY_SLICE_ID = "v0_13"`.
- [ ] Add v0.13 to `V07E_HYSTERESIS_RUNTIME_POLICY_SLICE_IDS`.
- [ ] Ensure v0.13 is transitively in:
  - `V07B_BASE_SERVO_RUNTIME_POLICY_SLICE_IDS`
  - `V07C_AUTHORITY_RUNTIME_POLICY_SLICE_IDS`
  - `V07D_FINAL_AUTHORITY_RUNTIME_POLICY_SLICE_IDS`
- [ ] Keep v0.13 out of `V08H_DERIVED_POLICY_SLICE_IDS`.
- [ ] Ensure `_apply_selected_action_adapter_with_diagnostics` records v0.13 policy influence ceiling diagnostics and does not load v0.8h safe-entry config for v0.13.

---

### Task 3: v0.13 Artifact Builder

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] Add v0.13 constants:
  - `V13_POLICY_SLICE_ID`
  - `V13_SLICE_ID`
  - `V13_CHILD_OUTPUT_DIRNAME`
  - schema versions
  - calibration range `37000-37029`
  - held-out range `38000-38049`

- [ ] Add loaders:
  - require v0.12a diagnosis with root cause `RUNTIME_AUTHORITY_DOMINATES_LEARNED_RESIDUAL_OUTCOME`
  - require recommended downstream slice `v0_13_policy_influence_authority_ceiling_slice`
  - load v0.12 policy artifacts

- [ ] Build `policy_influence_authority_ceiling_config`:
  - `state_feedback_gain_ceiling=0.5`
  - `xy_action_clip=0.05`
  - `z_action_clip=0.16`
  - `z_progress_injection_enabled=false`
  - `final_xy_state_feedback_replacement_enabled=false`
  - `min_post_adapter_delta_retention_ratio=0.35`
  - `max_post_adapter_identical_fraction=0.50`

- [ ] Build v0.13 policy artifacts:
  - preserve learned weights from v0.12
  - set policy slice metadata to `v0_13`
  - set same authority ceiling config for baseline/candidate
  - reduce selected action adapter state feedback gain to ceiling
  - remove or disable v0.8h safe-entry progress config for v0.13
  - preserve fairness equality keys

- [ ] Derive artifact-only policy influence gate:
  - simulate v0.13 post-adapter action deltas from v0.12 paired traces
  - require retention ratio `>= 0.35`
  - require identical fraction `<= 0.50`
  - require held-out unopened
  - write gate + manifest + policy artifacts

---

### Task 4: v0.13 Fresh Runtime Gate

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] Build fresh manifest:
  - calibration `37000-37029`
  - held-out `38000-38049`
  - reject reused prior calibration/held-out ranges.

- [ ] Add actual Isaac runtime runner:
  - build artifact-only v0.13 slice first
  - run calibration only first
  - write calibration rollout JSON and trace refs
  - pass calibration only if:
    - runtime backend is `isaac_runtime`
    - baseline success `<= 0.65`
    - candidate success `>= 0.80`
    - candidate > baseline
    - gap `>= 0.20`
    - policy influence preservation passes
    - held-out unopened
  - if calibration fails, fail closed and do not open held-out.

- [ ] If calibration passes, run held-out:
  - open only `38000-38049`
  - run learning validator
  - close only if candidate uplift `>= 0.20` and all MVP-2 closure gates pass.

---

### Task 5: CLI Wiring

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] Add `v0_13` to `--policy-slice` choices.
- [ ] Add flags:
  - `--policy-influence-authority-ceiling-only`
  - `--policy-influence-authority-ceiling-runtime`
- [ ] Add command serialization.
- [ ] Add special policy-slice guard support.
- [ ] Artifact-only branch:
  - rejects incompatible modes
  - writes `evidence_manifest.json`
  - marks proof authority false and held-out unopened.
- [ ] Runtime branch:
  - rejects `--clean`
  - rejects `--skip-isaac`
  - rejects fake/external rollout shortcuts
  - requires `scenario-profile=v0_6`, `policy-slice=v0_13`
  - writes evidence manifest with runtime gate paths.

---

### Task 6: Verification

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v13" -q
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -k "v13" -q
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v12a or v13" -q
uv run python -m compileall -q scripts/run_mvp2c_isaac_training_calibration.py scripts/run_mvp2b_isaac_proof_evaluator.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py
uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py scripts/run_mvp2b_isaac_proof_evaluator.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py
```

Then artifact-only evidence run:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_13 \
  --policy-influence-authority-ceiling-only \
  --output-dir storage/proof_evidence/mvp2c_isaac_training_calibration \
  --pretty
```

If artifact-only passes, run actual Isaac runtime:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_13 \
  --policy-influence-authority-ceiling-runtime \
  --output-dir storage/proof_evidence/mvp2c_isaac_training_calibration \
  --pretty
```

Stop only if MVP-2 closes or an unrecoverable blocker is hit. If v0.13 fails closed, preserve artifacts and start the next diagnosis slice automatically.
