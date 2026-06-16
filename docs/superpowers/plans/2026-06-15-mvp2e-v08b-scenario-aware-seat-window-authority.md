# MVP-2E v0.8b Scenario-Aware Seat-Window Authority Implementation Plan

> **Execution mode:** repo-local ultragoal loop. Continue automatically until MVP-2 is Closed or a hard fail-closed blocker is proven.

**Goal:** Repair the v0.8a seat-window authority ordering and fixed-deadline weakness, then run a fresh calibration/held-out closure attempt using `25000-25029` and `26000-26049`.

**Primary evidence:** v0.8a fresh held-out failed with baseline `38/50`, candidate `45/50`, uplift `+0.14`. Candidate failures are all `ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED`; v0.8a forced z after final XY authority, so XY did not see the forced z-open state.

---

## File Map

- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`
  - Add `v0_8b` policy slice.
  - Add `scenario_aware_seat_window_authority_v0_8b`.
  - Apply seat-window z forcing before or inside final XY authority so `z_open_low_depth` XY maintenance can engage.
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
  - Add v0.8b constants, builder, manifest, CLI branch, calibration/held-out runner.
  - Fresh calibration: `25000-25029`.
  - Fresh held-out: `26000-26049`.
- Modify: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
  - Add authority ordering regression tests.
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
  - Add v0.8b manifest/config/CLI/fake-backend tests.
- Modify after execution: `docs/developer/worklog.md`, `tasks/todo.md`, `Handoff.md`, `docs/developer/debugging_guide.md`.

## Task 1: RED evaluator tests

- [ ] Add a regression test proving v0.8a ordering is not acceptable for v0.8b:
  - Given a step where seat-window z must be forced.
  - The final diagnostics must show XY authority saw the effective z-open state.
  - `seat_window_authority_preserved_xy=true` alone is insufficient.
- [ ] Add a test for off-center behavior:
  - z must not be forced when lateral is outside `z_open_centering_lateral_m`.
  - final XY may still clamp off-center saturated action.
- [ ] Add a test that candidate/baseline shared config is required for v0.8b.

Expected first run:

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -k "v08b or scenario_aware_seat_window" -q
```

Expected: fail before implementation.

## Task 2: GREEN evaluator authority

- [ ] Add constants:
  - `V08B_POLICY_SLICE_ID = "v0_8b"`
  - `V08B_SLICE_ID = "mvp2e_v08b_scenario_aware_seat_window_authority"`
  - `V08B_SEAT_WINDOW_AUTHORITY_ID = "scenario_aware_seat_window_authority_v0_8b"`
- [ ] Add `_validated_v08b_seat_window_authority_config(...)`.
- [ ] Add `_apply_v08b_scenario_aware_seat_window_authority(...)`.
- [ ] Ensure final action order is:

```text
policy/base/residual action
-> residual authority
-> selected_action_adapter
-> final z authority
-> v0.8b prospective seat-window z decision
-> final XY authority using effective z-open state
-> v0.8b final seat-window z confirmation
-> Isaac action
```

- [ ] Diagnostics must include:
  - `seat_window_authority_id`
  - `seat_window_authority_applied`
  - `seat_window_authority_reason`
  - `seat_window_xy_recomputed_with_forced_z`
  - `effective_z_open_for_xy_authority`
  - `scenario_aware_deadline_step`

## Task 3: RED v0.8b builder/CLI tests

- [ ] Add `test_v08b_requires_v08a_failed_closure_gate`.
- [ ] Add `test_v08b_builds_fresh_manifest_and_burns_v08a_heldout`.
- [ ] Add `test_v08b_policy_artifacts_are_peer_fair`.
- [ ] Add `test_v08b_cli_parses_scenario_aware_seat_window_flag`.
- [ ] Add `test_v08b_cli_runs_fresh_calibration_then_fresh_heldout_with_fake_isaac`.

Expected first run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08b or scenario_aware_seat_window" -q
```

Expected: fail before implementation.

## Task 4: GREEN v0.8b builder/CLI

- [ ] Add constants:
  - `V08B_POLICY_SLICE_ID = "v0_8b"`
  - `V08B_SLICE_ID = "mvp2e_v08b_scenario_aware_seat_window_authority"`
  - `V08B_CHILD_OUTPUT_DIRNAME = "v0_8b_scenario_aware_seat_window_authority"`
  - `V08B_FRESH_CALIBRATION_RANGE = range(25000, 25030)`
  - `V08B_FRESH_HELDOUT_RANGE = range(26000, 26050)`
- [ ] Add `load_required_v08a_failed_heldout_gate(...)`.
- [ ] Add `derive_v08b_scenario_aware_seat_window_authority_config(...)`.
- [ ] Add `build_v08b_fresh_manifest(...)`.
- [ ] Add `build_v08b_scenario_aware_seat_window_authority_slice(...)`.
- [ ] Add CLI flag `--scenario-aware-seat-window-authority-only`.
- [ ] Reject:
  - `--clean`
  - fake backend flags in actual mode
  - any profile/slice other than `--scenario-profile v0_6 --policy-slice v0_8b`
  - reuse of `21000-21049` or `24000-24049` as closure held-out

## Task 5: Focused verification

Run:

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -k "v08b or scenario_aware_seat_window" -q
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08a or v08b or fresh_seat_window or scenario_aware_seat_window" -q
uv run python -m compileall -q scripts apps/api/tests
uvx ruff check scripts/run_mvp2b_isaac_proof_evaluator.py scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
git diff --check
```

## Task 6: Actual Isaac v0.8b proof attempt

Run only after focused/static checks pass:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_8b \
  --scenario-aware-seat-window-authority-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

Expected behavior:

- fresh calibration `25000-25029` opens first.
- fresh held-out `26000-26049` opens only after calibration passes.
- final JSON may mark MVP-2 closed only if close criteria are honestly met.

## Task 7: If v0.8b fails

Do not stop for permission. Immediately:

1. Preserve v0.8b closure artifact and trace summary.
2. Classify failure root cause from artifacts.
3. Write the next diagnosis/spec.
4. Write the next implementation plan.
5. Continue the loop.
