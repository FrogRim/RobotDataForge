# MVP-2E v0.8a Fresh Seat-Window Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a fresh-split v0.8a MVP-2 closure attempt that uses train-derived seat-window progress authority, fresh calibration `23000-23029`, and fresh held-out `24000-24049`.

**Architecture:** v0.8a is a child of v0.7o. It reuses peer-fair v0.7o policy artifacts, appends a shared seat-window progress authority config, runs fresh calibration first, and opens fresh held-out only after calibration passes. The opened v0.7p held-out `21000-21049` is permanently marked burned and cannot be reused for closure.

**Tech Stack:** Python 3.11, pytest, existing Isaac evaluator backend, JSON proof artifacts, existing MVP-2 learning validator.

---

## File Map

- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`
  - Recognize `policy_slice == "v0_8a"`.
  - Apply final post-adapter seat-window progress authority after existing z/xy authority.
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
  - Add v0.8a constants.
  - Build v0.8a fresh manifest.
  - Derive train-side seat-window authority config.
  - Build v0.8a policy artifacts.
  - Add `--fresh-seat-window-authority-only`.
  - Run fresh calibration and, only after pass, fresh held-out closure.
- Modify: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
  - Add authority unit tests.
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
  - Add v0.8a config/fresh split/CLI tests.
- Modify: `docs/developer/worklog.md`, `tasks/todo.md`, `Handoff.md`, `docs/developer/debugging_guide.md`
  - Record command, artifacts, and MVP-2 non-closed/closed state.

## Task 1: RED tests for evaluator authority

- [ ] Add test `test_v08a_seat_window_authority_forces_z_after_train_derived_deadline`.

Expected behavior:

```python
raw = np.asarray([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0])
metric = {
    "step": 82,
    "lateral_error_m": 0.0005,
    "insertion_depth_m": 0.010,
    "env_native_success": False,
}
config = {
    "seat_window_authority_id": "seat_window_progress_authority_v0_8a",
    "latest_z_open_step": 81,
    "z_open_centering_lateral_m": 0.006,
    "seat_region_depth_m": 0.024,
    "z_progress_action": -0.16,
}
action, diagnostics = script._apply_v08a_seat_window_progress_authority(
    action=raw,
    metric_row=metric,
    config=config,
)
assert action[2] == -0.16
assert diagnostics["seat_window_authority_applied"] is True
```

- [ ] Add test `test_v08a_seat_window_authority_does_not_change_z_before_deadline_or_off_center`.

Expected behavior: step 80 or lateral 0.02 leaves z unchanged.

- [ ] Run:

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -k "v08a or seat_window" -q
```

Expected: FAIL because helper is missing.

## Task 2: GREEN evaluator authority

- [ ] Add evaluator constants:

```python
V08A_POLICY_SLICE_ID = "v0_8a"
V08A_SEAT_WINDOW_AUTHORITY_ID = "seat_window_progress_authority_v0_8a"
```

- [ ] Add `_validated_v08a_seat_window_authority_config(policy_artifact)`.
- [ ] Add `_apply_v08a_seat_window_progress_authority(...)`.
- [ ] Include `V08A_POLICY_SLICE_ID` in the same final z, hysteresis, and xy authority sets as v0.7o.
- [ ] Apply v0.8a seat-window authority after final xy authority and update diagnostics.
- [ ] Run evaluator focused tests again and expect PASS.

## Task 3: RED tests for v0.8a fresh split and config

- [ ] Add test `test_v08a_requires_v07q_post_heldout_marker`.

Expected: `build_v08a_fresh_seat_window_authority_slice(output_dir=tmp_path)` raises `ValueError("missing_v0_7q_post_heldout_marker")`.

- [ ] Add test `test_v08a_builds_fresh_manifest_and_peer_fair_policy_artifacts`.

Fixture requirements:

- fake v0.7o policy artifacts
- fake v0.7q marker with `fresh_slice_required=true`
- fake train-generation success traces with first z steps `[63, 81]` and first env-native success steps `[115, 136]`

Expected:

- calibration range is `[23000, 23029]`
- held-out range is `[24000, 24049]`
- policy slice is `v0_8a`
- candidate/baseline `seat_window_authority_config_sha256` match
- `latest_z_open_step == 81`
- `heldout_21000_21049_accessed is False`

- [ ] Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08a or fresh_seat_window" -q
```

Expected: FAIL because v0.8a functions/CLI are missing.

## Task 4: GREEN v0.8a builder and CLI

- [ ] Add constants:

```python
V08A_POLICY_SLICE_ID = "v0_8a"
V08A_SLICE_ID = "mvp2e_v08a_fresh_seat_window_authority"
V08A_CHILD_OUTPUT_DIRNAME = "v0_8a_fresh_seat_window_authority"
V08A_FRESH_CALIBRATION_RANGE = range(23000, 23030)
V08A_FRESH_HELDOUT_RANGE = range(24000, 24050)
```

- [ ] Add `load_required_v07q_post_heldout_marker(...)`.
- [ ] Add `derive_v08a_seat_window_authority_config(...)`.
- [ ] Add `build_v08a_fresh_manifest(...)`.
- [ ] Add `build_v08a_fresh_seat_window_authority_slice(...)`.
- [ ] Add CLI flag `--fresh-seat-window-authority-only`.
- [ ] For CLI:
  - reject `--clean`
  - require `--scenario-profile v0_6 --policy-slice v0_8a`
  - require existing v0.7q marker
  - run fresh calibration first
  - if calibration fails, write gate and return 0 with `mvp2_closed=false`
  - if calibration passes, run fresh held-out and write closure gate
- [ ] Run v0.8a focused tests and expect PASS.

## Task 5: Verification and actual runtime attempt

- [ ] Run:

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -k "v08a or seat_window" -q
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v07q or heldout_shortfall or v08a or fresh_seat_window" -q
uv run python -m compileall -q scripts apps/api/tests
uvx ruff check scripts/run_mvp2b_isaac_proof_evaluator.py scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
git diff --check
```

- [ ] Run actual Isaac only after focused/static checks pass:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py --scenario-profile v0_6 --policy-slice v0_8a --fresh-seat-window-authority-only --isaac-task Isaac-Factory-PegInsert-Direct-v0 --device cuda:0 --pretty
```

- [ ] If `mvp2_closed=true`, update docs and report MVP-2 Closed.
- [ ] If `mvp2_closed=false`, immediately write the next diagnosis spec and continue the loop.
