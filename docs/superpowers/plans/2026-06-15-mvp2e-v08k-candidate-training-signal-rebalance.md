# MVP-2E v0.8k Candidate Training Signal Rebalance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `v0_8k_candidate_training_signal_rebalance`, a fail-closed slice that retrains the candidate residual policy from a deterministically rebalanced curated train view while preserving the same shared runtime authority as v0.8h.

**Architecture:** Add one child slice to `scripts/run_mvp2c_isaac_training_calibration.py`. The slice requires v0.8h/v0.8i/v0.8j evidence, reads v0.7d train HDF5 metadata rows, creates v0.8k train views, retrains baseline/candidate with the same trainer, wraps the artifacts with v0.8h authority metadata, and exposes an actual Isaac calibration/held-out runtime path guarded by fresh calibration `29000-29029` and sealed held-out `27000-27049`.

**Tech Stack:** Python, NumPy ridge regression via existing `fit_phase_conditioned_bc_policy`, HDF5 via existing train-view writer, pytest, Isaac runtime only for final proof attempt.

---

## Files

- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
  - Add v0.8k constants, parent gates, row rebalance helpers, HDF5 view writer calls, policy artifact builder, offline gates, runtime runner, and CLI mode.
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
  - Add focused RED/GREEN tests for parent gating, deterministic candidate-only rebalance, peer fairness, CLI artifact build, and held-out seal.
- Modify: `Handoff.md`
  - Record v0.8k result after implementation/proof attempt.
- Modify: `tasks/todo.md`
  - Update v0.8k checklist.
- Modify: `docs/developer/worklog.md`
  - Record implementation, commands, result, and next gap.
- Modify: `docs/developer/debugging_guide.md`
  - Add v0.8k command and failure interpretation if runtime is reached.

## Task 1: RED Tests for v0.8k Parent Gating and Rebalance

**Files:**
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add test helpers**

Add helpers near the existing v0.8j helpers:

```python
def _write_fake_v08k_parent_chain(script: Any, output_dir: Path) -> None:
    _write_fake_v08h_failed_calibration_result_with_v08j_residuals(script, output_dir)
    script.build_v08i_calibration_uplift_compression_diagnosis(output_dir=output_dir)
    script.build_v08j_attribution_preserving_candidate_margin_diagnosis(output_dir=output_dir)


def _write_fake_v08k_source_train_views(script: Any, output_dir: Path) -> None:
    child_dir = output_dir / script.V07D_CHILD_OUTPUT_DIRNAME
    child_dir.mkdir(parents=True, exist_ok=True)
    authority_config = {
        "authority_filter_config_sha256": "fake_authority_sha",
        "authority_filter_id": script.V07C_AUTHORITY_FILTER_ID,
        "selected_action_adapter_id": "isaac_signed_xy_downward_servo_v0",
    }
    rows = [
        {
            "trajectory_id": "traj_success",
            "step": index,
            "accepted": True,
            "proof_role": "trace_native_residual_train",
            "behavior_state_phase": phase,
            "env_native_success_mask": phase == "HOLD",
            "insertion_depth_m": 0.025 if phase == "HOLD" else 0.012,
            "relative_x_m": 0.0,
            "relative_y_m": 0.0,
            "lateral_error_m": 0.001,
            "orientation_error_deg": 0.0,
            "previous_action_dx": 0.0,
            "previous_action_dy": 0.0,
            "previous_action_dz": 0.0,
            "previous_action_rx": 0.0,
            "previous_action_ry": 0.0,
            "previous_action_rz": 0.0,
            "previous_action_gripper": 1.0,
            "normalized_action": [0.0, 0.0, -0.12 if phase == "DESCEND" else 0.0, 0.0, 0.0, 0.0, 1.0],
        }
        for index, phase in enumerate(["ALIGN", "DESCEND", "DESCEND", "HOLD", "HOLD"])
    ]
    baseline_rows = rows + [
        {
            **rows[0],
            "trajectory_id": "traj_rejected",
            "accepted": False,
            "proof_role": "trace_native_residual_train",
            "behavior_state_phase": "ALIGN",
        }
    ]
    script.write_v07c_residual_train_view_hdf5(
        path=child_dir / "candidate_curated_train_v0_7d.hdf5",
        rows=rows,
        view_id="candidate_curated_v0_7d_action_authority_post_adapter_z_gate",
        authority_config=authority_config,
    )
    script.write_v07c_residual_train_view_hdf5(
        path=child_dir / "baseline_uncurated_train_v0_7d.hdf5",
        rows=baseline_rows,
        view_id="baseline_uncurated_v0_7d_action_authority_post_adapter_z_gate",
        authority_config=authority_config,
    )
```

- [ ] **Step 2: Add failing parent-gate test**

```python
def test_v08k_requires_v08j_rebalance_recommendation(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="missing_v0_8j_candidate_margin_diagnosis"):
        script.build_v08k_candidate_training_signal_rebalance_slice(output_dir=tmp_path)
```

- [ ] **Step 3: Add failing rebalance test**

```python
def test_v08k_rebalances_candidate_rows_without_changing_baseline(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v08k_parent_chain(script, tmp_path)
    _write_fake_v08k_source_train_views(script, tmp_path)
    script.write_json(
        tmp_path / script.V08H_CHILD_OUTPUT_DIRNAME / "candidate_policy_artifact_v0_8h.json",
        _fake_v08k_parent_policy(script, role="candidate"),
    )
    script.write_json(
        tmp_path / script.V08H_CHILD_OUTPUT_DIRNAME / "baseline_policy_artifact_v0_8h.json",
        _fake_v08k_parent_policy(script, role="baseline"),
    )

    manifest = script.build_v08k_candidate_training_signal_rebalance_slice(output_dir=tmp_path)

    gate = manifest["training_signal_rebalance_gate"]
    assert manifest["policy_slice"] == "v0_8k"
    assert manifest["mvp2_closed"] is False
    assert manifest["heldout_opened"] is False
    assert manifest["fresh_heldout_27000_27049_accessed"] is False
    assert gate["passed"] is True
    assert gate["candidate_duplicate_rows"] > 0
    assert gate["candidate_rebalanced_rows"] > gate["candidate_source_rows"]
    assert gate["baseline_rebalanced_rows"] == gate["baseline_source_rows"]
    assert gate["candidate_duplicate_rows_by_reason"]["seat_hold_rows"] > 0
    assert gate["candidate_duplicate_rows_by_reason"]["centered_descent_rows"] > 0
```

- [ ] **Step 4: Add failing CLI test**

```python
def test_v08k_cli_builds_artifact_only_rebalance_slice(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v08k_parent_chain(script, tmp_path)
    _write_fake_v08k_source_train_views(script, tmp_path)
    script.write_json(
        tmp_path / script.V08H_CHILD_OUTPUT_DIRNAME / "candidate_policy_artifact_v0_8h.json",
        _fake_v08k_parent_policy(script, role="candidate"),
    )
    script.write_json(
        tmp_path / script.V08H_CHILD_OUTPUT_DIRNAME / "baseline_policy_artifact_v0_8h.json",
        _fake_v08k_parent_policy(script, role="baseline"),
    )

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_8k",
            "--candidate-training-signal-rebalance-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    manifest = script.read_json(
        tmp_path / script.V08K_CHILD_OUTPUT_DIRNAME / "v0_8k_candidate_training_signal_rebalance_manifest.json"
    )
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert manifest["proof_authority"] is False
    assert evidence_manifest["proof_runtime"] == script.V08K_SLICE_ID
    assert evidence_manifest["fresh_heldout_27000_27049_accessed"] is False
```

- [ ] **Step 5: Run RED tests**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08k" -q
```

Expected: FAIL because `V08K_*`, `_fake_v08k_parent_policy`, and build/CLI functions do not exist yet.

## Task 2: Implement v0.8k Artifact Build

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add constants**

Add near v0.8h/v0.8i/v0.8j constants:

```python
V08K_POLICY_SLICE_ID = "v0_8k"
V08K_SLICE_ID = "mvp2e_v08k_candidate_training_signal_rebalance"
V08K_CHILD_OUTPUT_DIRNAME = "v0_8k_candidate_training_signal_rebalance"
V08K_POLICY_ARTIFACT_SCHEMA_VERSION = "rdf_mvp2e_v08k_policy_artifact_v0.1.0"
V08K_MANIFEST_SCHEMA_VERSION = "rdf_mvp2e_v08k_candidate_training_signal_rebalance_manifest_v0.1.0"
V08K_REBALANCE_GATE_SCHEMA_VERSION = "rdf_mvp2e_v08k_training_signal_rebalance_gate_v0.1.0"
V08K_CALIBRATION_PRESIGNAL_SCHEMA_VERSION = "rdf_mvp2e_v08k_calibration_presignal_gate_v0.1.0"
V08K_HELDOUT_CLOSURE_SCHEMA_VERSION = "rdf_mvp2e_v08k_heldout_closure_gate_v0.1.0"
V08K_FRESH_CALIBRATION_RANGE = range(29000, 29030)
V08K_FRESH_HELDOUT_RANGE = range(27000, 27050)
```

- [ ] **Step 2: Add parent loaders**

Implement:

```python
def load_required_v08j_candidate_margin_diagnosis(output_dir: Path) -> dict[str, Any]:
    path = output_dir / V08J_CHILD_OUTPUT_DIRNAME / "v0_8j_attribution_preserving_candidate_margin_diagnosis.json"
    if not path.exists():
        raise ValueError("missing_v0_8j_candidate_margin_diagnosis")
    diagnosis = read_json(path)
    if (
        diagnosis.get("policy_slice") != V08J_POLICY_SLICE_ID
        or diagnosis.get("source_policy_slice") != V08H_POLICY_SLICE_ID
        or diagnosis.get("recommended_downstream_slice") != "v0_8k_candidate_training_signal_rebalance"
        or diagnosis.get("candidate_margin_repair_feasible") is not False
        or diagnosis.get("heldout_opened") is not False
        or diagnosis.get("fresh_heldout_27000_27049_accessed") is not False
    ):
        raise ValueError("invalid_v0_8j_candidate_margin_diagnosis")
    diagnosis["path"] = str(path)
    diagnosis["sha256"] = _sha256_file(path)
    return diagnosis
```

- [ ] **Step 3: Add deterministic row rebalance**

Implement `rebalance_v08k_candidate_rows(rows)`:

```python
def _v08k_row_sha256(row: dict[str, Any]) -> str:
    return _sha256_payload(row)


def _v08k_rebalance_reasons(row: dict[str, Any]) -> list[str]:
    action = row.get("normalized_action")
    action_z = float(action[2]) if isinstance(action, list) and len(action) > 2 else 0.0
    phase = row.get("behavior_state_phase")
    lateral = float(row.get("lateral_error_m") or 0.0)
    depth = float(row.get("insertion_depth_m") or 0.0)
    reasons = []
    if phase == "HOLD" or row.get("env_native_success_mask") is True:
        reasons.extend(["seat_hold_rows", "seat_hold_rows", "seat_hold_rows"])
    if phase == "DESCEND" and lateral <= 0.006 and action_z <= -0.08:
        reasons.append("centered_descent_rows")
        if depth < 0.024:
            reasons.append("under_depth_progress_rows")
    return reasons[:4]


def rebalance_v08k_candidate_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rebalanced = []
    counts: dict[str, int] = {"seat_hold_rows": 0, "centered_descent_rows": 0, "under_depth_progress_rows": 0}
    for row in rows:
        source_hash = _v08k_row_sha256(row)
        base = dict(row)
        base.update(
            {
                "rebalance_policy_slice": V08K_POLICY_SLICE_ID,
                "rebalance_is_duplicate": False,
                "rebalance_reason": "base_source_row",
                "rebalance_source_row_sha256": source_hash,
                "rebalance_copy_index": 0,
            }
        )
        rebalanced.append(base)
        for index, reason in enumerate(_v08k_rebalance_reasons(row), start=1):
            duplicate = dict(row)
            duplicate.update(
                {
                    "rebalance_policy_slice": V08K_POLICY_SLICE_ID,
                    "rebalance_is_duplicate": True,
                    "rebalance_reason": reason,
                    "rebalance_source_row_sha256": source_hash,
                    "rebalance_copy_index": index,
                }
            )
            counts[reason] = counts.get(reason, 0) + 1
            rebalanced.append(duplicate)
    return rebalanced, counts
```

- [ ] **Step 4: Add v0.8k policy artifact wrapper**

Implement `build_v08k_policy_artifact_payload(...)` by copying parent v0.8h policy metadata, replacing weights/bias/train fields from the new base fit, and updating:

```python
schema_version=V08K_POLICY_ARTIFACT_SCHEMA_VERSION
policy_slice=V08K_POLICY_SLICE_ID
slice_id=V08K_SLICE_ID
parent_policy_slice=V08H_POLICY_SLICE_ID
source_policy_slice=V08H_POLICY_SLICE_ID
candidate_training_signal_rebalance_enabled=(role == "candidate")
same_shared_authority_as_peer=True
fresh_calibration_29000_29029_accessed=False
fresh_heldout_27000_27049_accessed=False
mvp2_closed=False
policy_uplift_proven=False
```

- [ ] **Step 5: Add offline gate**

Implement `derive_v08k_training_signal_rebalance_gate(...)` with the G1-G4 fields from the spec. Use `predict_actions_for_rows` to compare v0.8h parent candidate predictions vs v0.8k candidate predictions on original candidate rows. Fail when candidate delta is absent or peer fairness fields diverge.

- [ ] **Step 6: Add build function**

Implement:

```python
def build_v08k_candidate_training_signal_rebalance_slice(*, output_dir: Path) -> dict[str, Any]:
    diagnosis = load_required_v08j_candidate_margin_diagnosis(output_dir)
    parent_policies = _load_v08h_policy_artifacts(output_dir)
    source_dir = output_dir / V07D_CHILD_OUTPUT_DIRNAME
    candidate_source_rows = _rows_from_hdf5_metadata(source_dir / "candidate_curated_train_v0_7d.hdf5")
    baseline_source_rows = _rows_from_hdf5_metadata(source_dir / "baseline_uncurated_train_v0_7d.hdf5")
    candidate_rows, duplicate_counts = rebalance_v08k_candidate_rows(candidate_source_rows)
    baseline_rows = [{**row, "rebalance_policy_slice": V08K_POLICY_SLICE_ID, "rebalance_is_duplicate": False} for row in baseline_source_rows]
    ...
```

Write:

```text
v0_8k_candidate_training_signal_rebalance_config.json
candidate_curated_train_v0_8k.hdf5
baseline_uncurated_train_v0_8k.hdf5
candidate_policy_artifact_v0_8k.json
baseline_policy_artifact_v0_8k.json
training_signal_rebalance_gate_v0_8k.json
v0_8k_candidate_training_signal_rebalance_manifest.json
```

- [ ] **Step 7: Add test helper `_fake_v08k_parent_policy`**

In the test file, add a compact fake parent policy with equality fields needed by `_load_v08h_policy_artifacts`. Use the same fake metadata for baseline and candidate except dataset role / policy id / weights.

- [ ] **Step 8: Run GREEN tests**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08k" -q
```

Expected: PASS.

## Task 3: Add v0.8k CLI and Runtime Calibration Path

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add CLI argument**

Add:

```python
parser.add_argument(
    "--candidate-training-signal-rebalance-only",
    action="store_true",
    help="Build v0.8k candidate training signal rebalance artifacts without running Isaac.",
)
```

Add `v0_8k` to `--policy-slice` choices.

- [ ] **Step 2: Add artifact-only CLI branch**

Branch rules:

```text
requires --scenario-profile v0_6 --policy-slice v0_8k
rejects --clean
rejects Isaac/fake runtime mode combinations
returns 0 after artifact build
writes evidence_manifest with proof_runtime=V08K_SLICE_ID
```

- [ ] **Step 3: Add runtime-only CLI branch**

Add a second mode:

```text
--candidate-training-signal-rebalance-runtime
```

It must:

```text
require actual Isaac runtime
build/reuse v0.8k artifacts
run calibration 29000-29029
if calibration fails, return the failed gate with heldout_opened=false
if calibration passes, run held-out 27000-27049 and write closure gate
```

The runtime structure can mirror `run_v08h_early_centered_z_open_safe_entry_runtime`, replacing constants, manifest paths, and policy artifact loader.

- [ ] **Step 4: Add focused CLI tests**

Test artifact-only branch with fake parents. Add a guard test that `--candidate-training-signal-rebalance-only --clean` raises.

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08k" -q
```

Expected: PASS.

## Task 4: Verification and Actual Proof Attempt

**Files:**
- Modify docs after results.

- [ ] **Step 1: Static verification**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08h or v08i or v08j or v08k" -q
uv run python -m compileall -q scripts apps/api/tests
uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
git diff --check
```

- [ ] **Step 2: Artifact-only v0.8k build on real evidence**

Run:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_8k \
  --candidate-training-signal-rebalance-only \
  --pretty
```

Expected:

```text
training_signal_rebalance_gate.passed=true
heldout_opened=false
fresh_heldout_27000_27049_accessed=false
mvp2_closed=false
```

- [ ] **Step 3: Actual Isaac v0.8k calibration / closure attempt**

Run:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_8k \
  --candidate-training-signal-rebalance-runtime \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --pretty
```

Expected if calibration fails:

```text
calibration_opened=true
heldout_opened=false
mvp2_closed=false
```

Then immediately create next diagnostic slice.

Expected if calibration passes and held-out closes:

```text
heldout_opened=true
fresh_heldout_27000_27049_accessed=true
MVP-2 closure flag is true
policy-uplift proof flag is true
```

- [ ] **Step 4: Update docs**

Update:

```text
Handoff.md
tasks/todo.md
docs/developer/worklog.md
docs/developer/debugging_guide.md
```

Record exact commands and outcomes.

## Self-Review

Spec coverage:

- Parent evidence gate: Task 1 and Task 2.
- Candidate-only deterministic train-view rebalance: Task 2.
- Peer fairness and candidate signal delta gate: Task 2.
- Fresh calibration / held-out seal: Task 3 and Task 4.
- Non-claims and fail-closed loop: Task 4 docs.

Completion-text scan:

- No unresolved-marker text or unspecified implementation step is intended.

Execution:

- The current user contract removes the normal “which execution option?” pause.
  Execute inline with TDD and continue automatically until MVP-2 closes or the
  next fail-closed diagnosis is required.
