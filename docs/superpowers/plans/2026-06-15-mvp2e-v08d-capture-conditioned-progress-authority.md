# MVP-2E v0.8d Capture-Conditioned Progress Authority Implementation Plan

## Target

Implement a v0.8d repair slice that builds on v0.8c diagnosis and introduces
capture-conditioned progress authority before the next fresh held-out closure
attempt. This plan must not open held-out `27000-27049` until calibration passes.

Spec:

```text
docs/superpowers/specs/2026-06-15-mvp2e-v08d-capture-conditioned-progress-authority-design.md
```

## Files

Modify:

```text
scripts/run_mvp2b_isaac_proof_evaluator.py
scripts/run_mvp2c_isaac_training_calibration.py
apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py
apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
docs/developer/worklog.md
docs/developer/debugging_guide.md
tasks/todo.md
Handoff.md
```

## Implementation Steps

1. Add v0.8d constants and config builder.

```text
V08D_POLICY_SLICE_ID="v0_8d"
V08D_SLICE_ID="mvp2e_v08d_capture_conditioned_progress_authority"
V08D_CHILD_OUTPUT_DIRNAME="v0_8d_capture_conditioned_progress_authority"
V08D_FRESH_CALIBRATION_RANGE=26500-26529
V08D_FRESH_HELDOUT_RANGE=27000-27049
early_z_deadline_step=68
capture_prepare_start_step=56
capture_lateral_gate_m=0.0035
depth_progress_window_steps=12
minimum_depth_progress_m=0.001
```

2. Build v0.8d artifacts from v0.8c diagnosis.

Required inputs:

```text
v0_8c_heldout_shortfall_diagnosis/v0_8c_shortfall_diagnosis.json
v0_8b_scenario_aware_seat_window_authority/candidate_policy_artifact_v0_8b.json
v0_8b_scenario_aware_seat_window_authority/baseline_policy_artifact_v0_8b.json
```

Outputs:

```text
v0_8d_capture_conditioned_progress_authority_config.json
candidate_policy_artifact_v0_8d.json
baseline_policy_artifact_v0_8d.json
v0_8d_fresh_manifest.json
```

3. Evaluator action authority changes.

In `run_mvp2b_isaac_proof_evaluator.py`:

```text
load v0.8d authority config from policy artifact
apply capture conditioning before z opens
apply earlier z deadline
record depth progress watch diagnostics
preserve final env-native z and xy authority ordering
```

Required diagnostics:

```text
capture_conditioned_progress_authority_id
capture_conditioning_applied
capture_conditioning_reason
early_z_deadline_step
capture_prepare_start_step
capture_lateral_gate_m
z_open_step
z_open_depth_reference_m
depth_progress_window_steps
depth_progress_delta_m
under_depth_progress_watch
```

4. Calibration runtime branch.

Add CLI mode:

```text
--capture-conditioned-progress-authority-only
```

Requirements:

```text
--scenario-profile v0_6
--policy-slice v0_8d
actual Isaac runtime required
--clean forbidden
burned held-out ranges rejected
held-out 27000-27049 not opened unless calibration passes
```

5. Calibration gate.

Use fresh calibration `26500-26529` first. Fail closed unless:

```text
candidate_success_rate > baseline_success_rate
candidate_minus_baseline_success_rate >= 0.10
candidate_failures_total <= 3
attribution_preservation_gate_passed=true
fresh_heldout_27000_27049_accessed=false
```

If calibration passes, the implementation may open fresh held-out
`27000-27049` in the same command, following the v0.8b pattern.

6. Tests.

Add focused tests proving:

```text
v0.8d config is derived from v0.8c diagnosis
burned held-out ranges include 21000/24000/26000
fresh manifest uses calibration 26500-26529 and heldout 27000-27049
evaluator blocks z during capture_conditioning_wait
evaluator uses early_z_deadline_step=68
depth progress watch diagnostics are emitted
same authority config is used for baseline and candidate
CLI runs fake calibration before fake held-out
```

## Verification Commands

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -k "v08d or capture_conditioned" -q

uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08c or v08d or capture_conditioned" -q

uv run python -m compileall -q scripts apps/api/tests

uvx ruff check \
  scripts/run_mvp2b_isaac_proof_evaluator.py \
  scripts/run_mvp2c_isaac_training_calibration.py \
  apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py

git diff --check
```

Actual Isaac command after focused verification:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_8d \
  --capture-conditioned-progress-authority-only \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

## Stop Conditions

Stop only if:

```text
v0.8c diagnosis is missing or inconsistent
v0.8d would need to reuse burned held-out ranges
success metric must be changed
validator rules must be weakened
implementation requires retry/withdraw/search/force-control
actual Isaac runtime is unavailable for the required calibration/held-out run
```
