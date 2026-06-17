# MVP-2E v0.8e Calibration Shortfall Diagnosis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an artifact-only v0.8e diagnosis slice that classifies v0.8d fresh calibration failures and recommends the next repair without opening held-out `27000-27049`.

**Architecture:** Reuse the existing calibration diagnosis pattern in `scripts/run_mvp2c_isaac_training_calibration.py`. Add constants, trace metric extraction, failure classifier, diagnosis builder, CLI routing, and focused tests.

**Tech Stack:** Python 3.11, pytest, existing JSON evidence helpers, no Isaac runtime for v0.8e.

---

## Files

Modify:

```text
scripts/run_mvp2c_isaac_training_calibration.py
apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
docs/developer/worklog.md
docs/developer/debugging_guide.md
tasks/todo.md
Handoff.md
```

Create:

```text
docs/superpowers/specs/2026-06-15-mvp2e-v08e-calibration-shortfall-diagnosis-design.md
docs/superpowers/plans/2026-06-15-mvp2e-v08e-calibration-shortfall-diagnosis.md
```

## Task 1: Add v0.8e RED Tests

- [ ] Add helper `_write_fake_v08d_failed_calibration_result(script, output_dir)`.
- [ ] The helper must write:

```text
v0_8d_capture_conditioned_progress_authority/calibration_presignal_gate_v0_8d.json
v0_8d_capture_conditioned_progress_authority/isaac_runtime_fresh_calibration_v0_8d/isaac_runtime_heldout_rollout_traces/*.json
```

- [ ] Include 30 baseline traces and 30 candidate traces.
- [ ] Candidate result must be 21 success / 9 failure.
- [ ] Failure classes must include:

```text
late_z_open_depth_shortfall: 5
late_seat_window_shortfall: 3
off_center_no_capture: 1
unclassified: 0
```

- [ ] Add test `test_v08e_requires_failed_v08d_calibration_gate`.
- [ ] Add test `test_v08e_classifies_v08d_calibration_shortfall`.
- [ ] Add test `test_v08e_cli_runs_artifact_only_calibration_diagnosis`.
- [ ] Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08e" -q
```

- [ ] Expected before implementation: fail because v0.8e symbols do not exist.

## Task 2: Implement v0.8e Constants and Metrics

- [ ] Add constants:

```python
V08E_POLICY_SLICE_ID = "v0_8e"
V08E_SLICE_ID = "mvp2e_v08e_calibration_shortfall_diagnosis"
V08E_CHILD_OUTPUT_DIRNAME = "v0_8e_calibration_shortfall_diagnosis"
V08E_CALIBRATION_SHORTFALL_DIAGNOSIS_SCHEMA_VERSION = (
    "rdf_mvp2e_v08e_calibration_shortfall_diagnosis_v0.1.0"
)
V08E_RECOMMENDED_DOWNSTREAM_SLICE = "v0_8f_horizon_reserved_capture_authority"
```

- [ ] Add `_v08e_trace_metrics(summary, trace)` returning:

```text
env_native_first_success_step
env_native_max_consecutive_success_steps
z_open_step
z_open_row_count
z_longest_consecutive_steps
first_depth_positive_step
max_insertion_depth_m
min_lateral_error_m
final_lateral_error_m
forced_capture_conditioning_count
capture_conditioning_wait_count
```

## Task 3: Implement v0.8e Classifier and Diagnosis Builder

- [ ] Add `classify_v08e_candidate_failure(summary, trace)`.
- [ ] Add `load_required_v08d_failed_calibration_gate(output_dir)`.
- [ ] Add `build_v08e_calibration_shortfall_diagnosis(output_dir=...)`.
- [ ] The builder must fail if:

```text
v0.8d gate missing
v0.8d gate passed
heldout_opened=true
fresh_heldout_27000_27049_accessed=true
trace count is not 60
unclassified candidate failures exist
```

- [ ] It must write:

```text
v0_8e_calibration_shortfall_diagnosis/v0_8e_calibration_shortfall_diagnosis.json
v0_8e_calibration_shortfall_diagnosis/candidate_failure_taxonomy_v0_8e.json
calibration_shortfall_diagnosis_v0_8e.json
```

## Task 4: Wire CLI

- [ ] Add `v0_8e` to `--policy-slice` choices.
- [ ] Extend `--calibration-failure-diagnosis-only` to accept `--policy-slice v0_8e`.
- [ ] Route v0.8e to `build_v08e_calibration_shortfall_diagnosis`.
- [ ] Evidence manifest must record:

```text
runtime_backend=offline_calibration_failure_diagnosis
proof_runtime=mvp2e_v08e_calibration_shortfall_diagnosis
mvp2_closed=false
policy_uplift_proven=false
heldout_opened=false
fresh_heldout_27000_27049_accessed=false
recommended_downstream_slice=v0_8f_horizon_reserved_capture_authority
```

## Task 5: Verify and Run Diagnosis

- [ ] Run focused tests:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08e or v08d" -q
```

- [ ] Run static checks:

```bash
uv run python -m compileall -q scripts apps/api/tests
uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
git diff --check
```

- [ ] Run actual artifact-only diagnosis:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_8e \
  --calibration-failure-diagnosis-only \
  --pretty
```

## Stop Conditions

Stop this slice only if:

```text
v0.8d calibration evidence is missing or corrupted
fresh held-out 27000-27049 was opened
candidate failures cannot be fully classified
the next repair would require changing success metric
```
