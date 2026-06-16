# MVP-2E v0.8c Held-Out Shortfall Diagnosis Implementation Plan

## Target

Implement an artifact-only diagnostic slice that consumes the completed
`v0_8b` actual Isaac held-out run and emits a fail-closed shortfall diagnosis.
This plan must not open calibration, held-out, Isaac, HMD, ROS, or robot
runtime paths.

Spec:

```text
docs/superpowers/specs/2026-06-15-mvp2e-v08c-heldout-shortfall-diagnosis-design.md
```

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

Create output artifact:

```text
storage/proof_evidence/mvp2c_isaac_training_calibration/
  v0_8c_heldout_shortfall_diagnosis/
    v0_8c_shortfall_diagnosis.json
```

## Implementation Steps

1. Add v0.8c constants.

```text
V08C_POLICY_SLICE_ID="v0_8c"
V08C_SLICE_ID="mvp2e_v08c_heldout_shortfall_diagnosis"
V08C_CHILD_OUTPUT_DIRNAME="v0_8c_heldout_shortfall_diagnosis"
V08C_SHORTFALL_DIAGNOSIS_SCHEMA_VERSION="rdf_mvp2e_v08c_heldout_shortfall_diagnosis_v0.1.0"
```

2. Add loader for required v0.8b artifacts.

Required source files:

```text
v0_8b_scenario_aware_seat_window_authority/heldout_closure_gate_v0_8b.json
v0_8b_scenario_aware_seat_window_authority/v0_8b_seat_window_authority_config.json
v0_8b_scenario_aware_seat_window_authority/isaac_runtime_fresh_heldout_v0_8b/isaac_runtime_heldout_rollout_traces/*.json
```

Fail closed if:

```text
heldout gate missing
policy_slice != v0_8b
fresh_heldout_26000_26049_accessed != true
runtime_backend != isaac_runtime
actual_rollouts_per_policy != 50
candidate traces count != 50
baseline traces count != 50
mvp2_closed != false
```

3. Add classifier.

Classifier precedence:

```text
late_seat_window_shortfall:
  first_success_step exists
  max_consecutive < 10
  max_depth >= 0.0248

centered_under_depth_progress:
  min_lateral <= 0.0006
  max_depth < 0.024
  z_count >= 60

off_center_no_capture:
  max_depth <= 0.001
  min_lateral >= 0.002
  z_count >= 60

unclassified:
  everything else
```

The diagnostic passes only when `unclassified` is empty and all six candidate
failures are assigned exactly once.

4. Emit diagnosis artifact.

Required top-level fields:

```text
schema_version
slice_id
policy_slice
proof_authority=false
mvp2_closed=false
policy_uplift_proven=false
proof_eligible=false
source_v08b_gate_path
source_v08b_gate_sha256
source_v08b_config_path
source_v08b_config_sha256
baseline_success_rate
candidate_success_rate
curated_vs_uncurated_uplift
candidate_failures_total
failure_taxonomy
burned_heldout_seed_ranges
recommended_downstream_slice
recommended_downstream_constraints
heldout_opened=false
fresh_heldout_27000_27049_accessed=false
```

5. Add CLI flag.

```text
--heldout-shortfall-diagnosis-only
```

The flag must reject:

```text
--clean
--skip-isaac
--expressibility-sanity-only
--calibration-presignal-only
--heldout-closure-only
--fresh-seat-window-authority-only
--scenario-aware-seat-window-authority-only
```

It must require:

```text
--scenario-profile v0_6
--policy-slice v0_8c
```

6. Tests.

Add focused tests that prove:

```text
1. missing v0_8b gate fails closed
2. incomplete candidate traces fail closed
3. all six real v0_8b failure modes classify into 2/2/2 taxonomy
4. CLI parses and runs artifact-only without opening Isaac
5. output records burned held-out 21000/24000/26000 and recommends v0_8d
```

Use synthetic minimal traces for tests. Do not depend on storage artifacts in
unit tests.

## Verification Commands

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08c or heldout_shortfall" -q

uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_8c \
  --heldout-shortfall-diagnosis-only \
  --pretty

uv run python -m compileall -q scripts apps/api/tests

uvx ruff check \
  scripts/run_mvp2c_isaac_training_calibration.py \
  apps/api/tests/test_mvp2c_isaac_training_calibration_script.py

git diff --check
```

## Stop Conditions

Stop and report only if:

```text
v0_8b evidence is missing or internally inconsistent
classification has unclassified failures
the script would need to open Isaac or held-out runtime
existing v0.8b artifacts must be modified
validator or close criteria would need weakening
```

Otherwise continue automatically to the next valid repair slice after the
diagnostic artifact is emitted.
