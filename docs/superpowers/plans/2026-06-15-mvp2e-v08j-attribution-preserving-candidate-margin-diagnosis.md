# MVP-2E v0.8j Attribution-Preserving Candidate Margin Diagnosis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an artifact-only `v0_8j` diagnosis slice that decides whether the `v0_8h` calibration shortfall can be repaired with attribution-preserving learned residual margin, without opening held-out.

**Architecture:** Reuse the existing `v0_8i` trace loader and paired outcome model. Add residual-intent feature extraction, candidate-only margin signature detection, failure recoverability classification, CLI routing, and evidence manifest writing.

**Tech Stack:** Python 3.11, pytest, existing JSON proof evidence helpers, no Isaac runtime.

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

Created by this plan:

```text
docs/superpowers/specs/2026-06-15-mvp2e-v08j-attribution-preserving-candidate-margin-diagnosis-design.md
docs/superpowers/plans/2026-06-15-mvp2e-v08j-attribution-preserving-candidate-margin-diagnosis.md
```

## Task 1: Add v0.8j RED Tests

- [ ] Add test `test_v08j_requires_v08i_diagnosis`.
- [ ] Add test `test_v08j_extracts_residual_margin_table_from_v08h_traces`.
- [ ] Add test `test_v08j_recommends_rebalance_when_no_candidate_specific_recoverability`.
- [ ] Add test `test_v08j_cli_runs_artifact_only_candidate_margin_diagnosis`.
- [ ] Use `_write_fake_v08h_failed_calibration_result(script, tmp_path)` to seed v0.8h evidence.
- [ ] Build v0.8i evidence in the fixture with:

```python
script.build_v08i_calibration_uplift_compression_diagnosis(output_dir=tmp_path)
```

- [ ] The fixture must include two candidate-only wins and five both-fail failures.
- [ ] Expected v0.8j diagnosis:

```python
assert diagnosis["policy_slice"] == "v0_8j"
assert diagnosis["source_policy_slice"] == "v0_8h"
assert diagnosis["parent_diagnosis_policy_slice"] == "v0_8i"
assert diagnosis["mvp2_closed"] is False
assert diagnosis["proof_authority"] is False
assert diagnosis["heldout_opened"] is False
assert diagnosis["fresh_heldout_27000_27049_accessed"] is False
assert diagnosis["paired_outcome_counts"] == {"B1_C1": 23, "B0_C1": 2, "B1_C0": 0, "B0_C0": 5}
assert diagnosis["candidate_failures_total"] == 5
assert diagnosis["candidate_failures_to_recover_for_calibration_gate"] == 2
assert diagnosis["unclassified_recoverability_count"] == 0
```

- [ ] Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08j" -q
```

- [ ] Expected before implementation: fail because `v0_8j` symbols do not exist.

## Task 2: Add Constants and Parent Evidence Loader

- [ ] Add constants:

```python
V08J_POLICY_SLICE_ID = "v0_8j"
V08J_SLICE_ID = "mvp2e_v08j_attribution_preserving_candidate_margin_diagnosis"
V08J_CHILD_OUTPUT_DIRNAME = "v0_8j_attribution_preserving_candidate_margin_diagnosis"
V08J_DIAGNOSIS_SCHEMA_VERSION = (
    "rdf_mvp2e_v08j_attribution_preserving_candidate_margin_diagnosis_v0.1.0"
)
V08J_REPAIR_SLICE_IF_MARGIN_PRESENT = "v0_8k_residual_intent_margin_repair"
V08J_REBALANCE_SLICE_IF_MARGIN_ABSENT = "v0_8k_candidate_training_signal_rebalance"
```

- [ ] Add `load_required_v08i_uplift_compression_diagnosis(output_dir)`.
- [ ] Validate:

```python
diagnosis["policy_slice"] == V08I_POLICY_SLICE_ID
diagnosis["source_policy_slice"] == V08H_POLICY_SLICE_ID
diagnosis["mvp2_closed"] is False
diagnosis["policy_uplift_proven"] is False
diagnosis["heldout_opened"] is False
diagnosis["fresh_heldout_27000_27049_accessed"] is False
diagnosis["baseline_success_compression"] is True
diagnosis["candidate_failures_total"] > 0
```

## Task 3: Extract Residual Margin Rows

- [ ] Add helper `_v08j_trace_residual_margin_metrics(trace)`.
- [ ] It must inspect `row["controller_action_diagnostics"]`.
- [ ] It must return:

```python
{
    "first_z_open_step": int | None,
    "first_depth_positive_step": int | None,
    "first_env_native_success_step": int | None,
    "env_native_max_consecutive_success_steps": int,
    "z_open_row_count": int,
    "max_insertion_depth_m": float,
    "min_lateral_error_m": float,
    "z_open_lateral_median": float | None,
    "z_open_residual_z_median": float | None,
    "z_open_residual_z_min": float | None,
    "z_open_residual_xy_median": float | None,
}
```

- [ ] Add `build_v08j_residual_margin_table(output_dir)`.
- [ ] Use `_load_v08h_calibration_trace_rows(output_dir)`.
- [ ] Pair baseline/candidate rows by seed.
- [ ] Store per seed:

```python
{
    "seed": seed,
    "paired_outcome": "B0_C1",
    "baseline": {...metrics...},
    "candidate": {...metrics...},
    "candidate_minus_baseline": {
        "first_z_open_step_delta": candidate_first_z - baseline_first_z,
        "first_depth_positive_step_delta": candidate_first_depth - baseline_first_depth,
        "z_open_residual_z_median_delta": candidate_median - baseline_median,
        "z_open_lateral_median_delta": candidate_lateral - baseline_lateral,
    },
}
```

## Task 4: Classify Recoverability

- [ ] Add `classify_v08j_candidate_failure_recoverability(pair_row, v08i_failure_row)`.
- [ ] Rules:

```text
recoverability_class="candidate_margin_present"
  if paired_outcome == "B0_C0"
  and candidate z_open_residual_z_median is at least 0.03 more negative than baseline
  and candidate z_open_lateral_median <= baseline z_open_lateral_median - 0.0005

recoverability_class="shared_failure_no_candidate_margin"
  if paired_outcome == "B0_C0"
  and candidate/baseline residual and lateral medians are effectively tied

recoverability_class="insufficient_margin_signal"
  if paired_outcome == "B0_C0"
  and candidate is better than baseline but below both thresholds
```

- [ ] Never classify `B0_C1` candidate-only wins as failures.
- [ ] Never classify `B1_C1` as repair targets.
- [ ] Return `unclassified` only for malformed evidence; builder must fail if any remain.

## Task 5: Build Diagnosis and Wire CLI

- [ ] Add `build_v08j_attribution_preserving_candidate_margin_diagnosis(output_dir)`.
- [ ] It must write:

```text
v0_8j_attribution_preserving_candidate_margin_diagnosis/residual_margin_table_v0_8j.json
v0_8j_attribution_preserving_candidate_margin_diagnosis/candidate_failure_recoverability_v0_8j.json
v0_8j_attribution_preserving_candidate_margin_diagnosis/v0_8j_attribution_preserving_candidate_margin_diagnosis.json
attribution_preserving_candidate_margin_diagnosis_v0_8j.json
```

- [ ] Add `v0_8j` to `--policy-slice` choices.
- [ ] Extend `--calibration-failure-diagnosis-only` to accept `--policy-slice v0_8j`.
- [ ] Evidence manifest metadata:

```python
{
    "policy_slice": "v0_8j",
    "runtime_backend": "offline_calibration_failure_diagnosis",
    "proof_runtime": V08J_SLICE_ID,
    "mvp2_closed": False,
    "policy_uplift_proven": False,
    "calibration_opened": True,
    "heldout_opened": False,
    "fresh_heldout_27000_27049_accessed": False,
    "recommended_downstream_slice": diagnosis["recommended_downstream_slice"],
}
```

## Task 6: Verify and Run Actual Diagnosis

- [ ] Run focused tests:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08j" -q
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08i or v08j" -q
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
  --policy-slice v0_8j \
  --calibration-failure-diagnosis-only \
  --pretty
```

- [ ] Continue automatically:
  - if `recommended_downstream_slice == "v0_8k_residual_intent_margin_repair"`, write the repair spec/plan next.
  - if `recommended_downstream_slice == "v0_8k_candidate_training_signal_rebalance"`, write the data/trainer rebalance spec/plan next.

## Stop Conditions

Stop this slice only if:

```text
v0.8h calibration evidence is missing or corrupted
v0.8i diagnosis is missing or contradicts v0.8h traces
held-out 27000-27049 was opened
candidate/baseline paired outcomes cannot be reconstructed
recoverability classification has unclassified evidence
```
