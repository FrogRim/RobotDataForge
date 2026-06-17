# MVP-2E v0.11 Attribution-Preserving Low-Floor Comparator Implementation Plan

> **For agentic workers:** execute task-by-task. Keep held-out `34000-34049` sealed until calibration passes. Do not weaken env-native success authority.

**Goal:** Build and run `v0_11_attribution_preserving_low_floor_comparator_slice`, a fresh actual-Isaac proof attempt that lowers baseline comparator floor without changing policy/trainer/runtime authority parity.

**Architecture:** Extend `scripts/run_mvp2c_isaac_training_calibration.py` with a v0.11 child slice sourced from v0.10c diagnosis. v0.11 builds new train views and policies, runs fresh calibration `33000-33029`, and opens fresh held-out `34000-34049` only when calibration passes.

---

## Task 1: RED tests

Files:

- `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

Steps:

- [ ] Add helper `_write_fake_v11_parent_evidence(script, output_dir)`:
  - create v0.10 parent evidence
  - create fake v0.10 calibration gap failure evidence
  - build v0.10c diagnosis
- [ ] Add test `test_v11_requires_v10c_gap_compression_diagnosis`.
- [ ] Add test `test_v11_builds_low_floor_comparator_views`.
- [ ] Add test `test_v11_cli_builds_artifact_only_low_floor_comparator`.
- [ ] Add runtime gate unit test for `derive_v11_calibration_presignal_gate`:
  - rejects baseline success rate above `0.65`
  - rejects `B1_C0 > 0`
  - passes when candidate >=0.80, gap >=0.20, baseline <=0.65, attribution pass.

Expected RED:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v11" -q
```

## Task 2: Constants and parent validation

Files:

- `scripts/run_mvp2c_isaac_training_calibration.py`

Add:

```python
V11_POLICY_SLICE_ID = "v0_11"
V11_SLICE_ID = "mvp2e_v11_attribution_preserving_low_floor_comparator_slice"
V11_CHILD_OUTPUT_DIRNAME = "v0_11_low_floor_comparator_slice"
V11_POLICY_ARTIFACT_SCHEMA_VERSION = "rdf_mvp2e_v11_policy_artifact_v0.1.0"
V11_MANIFEST_SCHEMA_VERSION = "rdf_mvp2e_v11_low_floor_comparator_manifest_v0.1.0"
V11_COMPARATOR_GATE_SCHEMA_VERSION = "rdf_mvp2e_v11_low_floor_comparator_gate_v0.1.0"
V11_CALIBRATION_PRESIGNAL_SCHEMA_VERSION = "rdf_mvp2e_v11_calibration_presignal_gate_v0.1.0"
V11_HELDOUT_CLOSURE_SCHEMA_VERSION = "rdf_mvp2e_v11_heldout_closure_gate_v0.1.0"
V11_FRESH_CALIBRATION_RANGE = range(33000, 33030)
V11_FRESH_HELDOUT_RANGE = range(34000, 34050)
V11_BASELINE_FAILURE_MATERIAL_RATIO = 0.90
V11_BASELINE_FLOOR_SUCCESS_MAXIMUM = 0.65
V11_CALIBRATION_SUCCESS_MINIMUM = 0.80
V11_CALIBRATION_UPLIFT_MINIMUM = 0.20
```

Add `load_required_v10c_calibration_gap_compression_diagnosis(output_dir)` requiring:

```text
policy_slice == v0_10c
source_policy_slice == v0_10
primary_root_cause_class == CALIBRATION_GAP_COMPRESSED_BY_BASELINE_SUCCESS_FLOOR
recommended_downstream_slice == v0_11_attribution_preserving_low_floor_comparator_slice
heldout_opened == false
fresh_heldout_32000_32049_accessed == false
mvp2_closed == false
policy_uplift_proven == false
```

## Task 3: Build v0.11 train views and policies

Files:

- `scripts/run_mvp2c_isaac_training_calibration.py`

Steps:

- [ ] Load v0.10 policy artifacts.
- [ ] Load v0.10 candidate rows.
- [ ] Candidate rows remain unchanged from v0.10.
- [ ] Build baseline rows:
  - accepted/success rows plus deterministic duplicated train-generation failure rows
  - target failure material ratio `0.90`
  - allowed ratio `[0.85, 0.95]`
- [ ] Train both policies with existing `fit_phase_conditioned_bc_policy`.
- [ ] Preserve policy/trainer/feature/action adapter/runtime authority equality keys.
- [ ] Write artifacts:
  - `v0_11_low_floor_comparator_config.json`
  - `candidate_curated_train_v0_11.hdf5`
  - `baseline_uncurated_low_floor_train_v0_11.hdf5`
  - `candidate_policy_artifact_v0_11.json`
  - `baseline_policy_artifact_v0_11.json`
  - `low_floor_comparator_gate_v0_11.json`
  - `v0_11_low_floor_comparator_manifest.json`

## Task 4: Fresh runtime path

Files:

- `scripts/run_mvp2c_isaac_training_calibration.py`

Steps:

- [ ] Add `build_v11_fresh_manifest(output_dir, low_floor_manifest)`.
- [ ] Add `_v11_runtime_manifest_for_split(fresh_manifest, split)`.
- [ ] Add `_load_v11_policy_artifacts(output_dir)` with peer fairness checks.
- [ ] Add `derive_v11_calibration_presignal_gate(...)` requiring:
  - candidate >= `0.80`
  - candidate-baseline gap >= `0.20`
  - baseline <= `0.65`
  - attribution preservation pass
- [ ] Add `run_v11_low_floor_comparator_runtime(...)`.
- [ ] Calibration uses `33000-33029`.
- [ ] Held-out uses `34000-34049`.
- [ ] If calibration fails, return calibration gate and do not open held-out.

## Task 5: CLI wiring

Files:

- `scripts/run_mvp2c_isaac_training_calibration.py`

Add:

- [ ] `--policy-slice v0_11`
- [ ] `--low-floor-comparator-only`
- [ ] `--low-floor-comparator-runtime`
- [ ] `_command_from_args` support.
- [ ] main artifact-only branch.
- [ ] main runtime branch.
- [ ] evidence manifest metadata.
- [ ] `--clean` rejected for both v0.11 modes.
- [ ] runtime branch rejects fake backend flags.

## Task 6: Verification

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v11" -q
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v10c or v11" -q
uv run python -m compileall -q scripts/run_mvp2c_isaac_training_calibration.py scripts/run_mvp2b_isaac_proof_evaluator.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py scripts/run_mvp2b_isaac_proof_evaluator.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
```

Then artifact-only build:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_11 \
  --low-floor-comparator-only \
  --output-dir storage/proof_evidence/mvp2c_isaac_training_calibration \
  --pretty
```

Then actual Isaac runtime:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_11 \
  --low-floor-comparator-runtime \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --output-dir storage/proof_evidence/mvp2c_isaac_training_calibration \
  --pretty
```

## Task 7: Next loop

- If calibration fails because baseline floor remains high, write `v0_11a_low_floor_failure_diagnosis`.
- If calibration passes but held-out uplift fails, write `v0_11b_heldout_shortfall_diagnosis`.
- If held-out closes, freeze MVP-2 Closed proof package.
