# MVP-2E v0.8i Calibration Uplift Compression Diagnosis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an artifact-only `v0_8i` diagnosis slice that classifies the
`v0_8h` fresh calibration failure, including candidate hard failures and
baseline success compression, without opening held-out `27000-27049`.

**Architecture:** Reuse the existing calibration diagnosis pattern in
`scripts/run_mvp2c_isaac_training_calibration.py`. Add constants, trace loading,
failure classifier, paired outcome diagnosis, CLI routing, and focused tests.

**Tech Stack:** Python 3.11, pytest, existing JSON evidence helpers, no Isaac
runtime for `v0_8i`.

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
docs/superpowers/specs/2026-06-15-mvp2e-v08i-calibration-uplift-compression-diagnosis-design.md
docs/superpowers/plans/2026-06-15-mvp2e-v08i-calibration-uplift-compression-diagnosis.md
```

## Task 1: Add v0.8i RED Tests

- [ ] Add helper `_write_fake_v08h_failed_calibration_result(script, output_dir)`.
- [ ] The helper must write:

```text
v0_8h_early_centered_z_open_safe_entry/calibration_presignal_gate_v0_8h.json
v0_8h_early_centered_z_open_safe_entry/isaac_runtime_fresh_calibration_v0_8h/isaac_runtime_heldout_rollout_traces/*.json
```

- [ ] Include 30 baseline traces and 30 candidate traces.
- [ ] Candidate result must be 25 success / 5 failure.
- [ ] Baseline result must be 23 success / 7 failure.
- [ ] Paired outcomes must include:

```text
B1_C1=23
B0_C1=2
B1_C0=0
B0_C0=5
```

- [ ] Failure classes must include:

```text
late_seat_window_shortfall: 1
under_depth_late_entry: 3
centered_no_depth_contact_miss: 1
unclassified: 0
```

- [ ] Add test `test_v08i_requires_failed_v08h_calibration_gate`.
- [ ] Add test `test_v08i_classifies_v08h_calibration_uplift_compression`.
- [ ] Add test `test_v08i_cli_runs_artifact_only_uplift_compression_diagnosis`.
- [ ] Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08i" -q
```

- [ ] Expected before implementation: fail because `v0_8i` symbols do not exist.

## Task 2: Implement v0.8i Constants and Trace Loading

- [ ] Add constants:

```python
V08I_POLICY_SLICE_ID = "v0_8i"
V08I_SLICE_ID = "mvp2e_v08i_calibration_uplift_compression_diagnosis"
V08I_CHILD_OUTPUT_DIRNAME = "v0_8i_calibration_uplift_compression_diagnosis"
V08I_CALIBRATION_UPLIFT_COMPRESSION_DIAGNOSIS_SCHEMA_VERSION = (
    "rdf_mvp2e_v08i_calibration_uplift_compression_diagnosis_v0.1.0"
)
V08I_RECOMMENDED_DOWNSTREAM_SLICE = "v0_8j_attribution_preserving_candidate_margin_repair"
```

- [ ] Add `load_required_v08h_failed_calibration_gate(output_dir)`.
- [ ] Add `_load_v08h_calibration_trace_rows(output_dir)`.
- [ ] The loader must require 60 traces and exactly calibration seeds
  `28500-28529` for both roles.

## Task 3: Implement v0.8i Classifier and Diagnosis Builder

- [ ] Add `classify_v08i_candidate_failure(summary, trace)`.
- [ ] Reuse or mirror v0.8e trace metrics.
- [ ] Add `build_v08i_calibration_uplift_compression_diagnosis(output_dir=...)`.
- [ ] The builder must fail if:

```text
v0.8h gate missing
v0.8h gate passed
heldout_opened=true
fresh_heldout_27000_27049_accessed=true
trace count is not 60
unclassified candidate failures exist
```

- [ ] It must write:

```text
v0_8i_calibration_uplift_compression_diagnosis/v0_8i_calibration_uplift_compression_diagnosis.json
v0_8i_calibration_uplift_compression_diagnosis/candidate_failure_taxonomy_v0_8i.json
calibration_uplift_compression_diagnosis_v0_8i.json
```

## Task 4: Wire CLI

- [ ] Add `v0_8i` to `--policy-slice` choices.
- [ ] Extend `--calibration-failure-diagnosis-only` to accept `--policy-slice v0_8i`.
- [ ] Route v0.8i to `build_v08i_calibration_uplift_compression_diagnosis`.
- [ ] Evidence manifest must record:

```text
runtime_backend=offline_calibration_failure_diagnosis
proof_runtime=mvp2e_v08i_calibration_uplift_compression_diagnosis
mvp2_closed=false
policy_uplift_proven=false
heldout_opened=false
fresh_heldout_27000_27049_accessed=false
recommended_downstream_slice=v0_8j_attribution_preserving_candidate_margin_repair
```

## Task 5: Verify and Run Diagnosis

- [ ] Run focused tests:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08i or v08h" -q
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
  --policy-slice v0_8i \
  --calibration-failure-diagnosis-only \
  --pretty
```

## Stop Conditions

Stop this slice only if:

```text
v0.8h calibration evidence is missing or corrupted
fresh held-out 27000-27049 was opened
candidate failures cannot be fully classified
the next repair would require changing success metric
```
