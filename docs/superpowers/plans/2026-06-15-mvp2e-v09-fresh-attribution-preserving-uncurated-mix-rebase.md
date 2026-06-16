# MVP-2E v0.9 Fresh Attribution-Preserving Uncurated Mix Rebase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `v0_9_fresh_attribution_preserving_uncurated_mix_rebase`, a fail-closed slice that rebases the baseline uncurated comparator with a pre-registered controlled-failure mix, then runs fresh calibration before opening sealed held-out `27000-27049`.

**Architecture:** Extend `scripts/run_mvp2c_isaac_training_calibration.py` with one child slice. The artifact builder requires the v0.8l audit, reads v0.8k train views and `train_generation_runtime_gate`, creates v0.9 train views and policy artifacts with the same shared authority, then exposes an actual Isaac runtime path guarded by calibration `30000-30029` and sealed held-out `27000-27049`.

**Tech Stack:** Python 3.11, NumPy ridge regression through existing `fit_phase_conditioned_bc_policy`, HDF5 through existing view writer, pytest, Isaac runtime only for final proof attempt.

---

### Task 1: RED Tests for v0.9 Parent Gate and Dataset Mix

**Files:**
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add a fake v0.9 parent evidence helper**

Add a helper near v0.8l helpers:

```python
def _write_fake_v09_parent_evidence(script: Any, output_dir: Path) -> None:
    _write_fake_v08l_v08k_evidence(script, output_dir)
    script.build_v08l_authority_ceiling_uncurated_mix_audit(output_dir=output_dir)
    child_dir = output_dir / script.V08K_CHILD_OUTPUT_DIRNAME
    policy = _fake_v08k_parent_policy(script, role="candidate")
    policy.update(
        {
            "schema_version": script.V08K_POLICY_ARTIFACT_SCHEMA_VERSION,
            "policy_artifact_schema_version": script.V08K_POLICY_ARTIFACT_SCHEMA_VERSION,
            "policy_slice": "v0_8k",
            "slice_id": script.V08K_SLICE_ID,
            "parent_policy_slice": script.V08H_POLICY_SLICE_ID,
            "source_policy_slice": script.V08H_POLICY_SLICE_ID,
            "fresh_calibration_29000_29029_accessed": True,
            "fresh_heldout_27000_27049_accessed": False,
            "heldout_opened": False,
            "mvp2_closed": False,
            "policy_uplift_proven": False,
        }
    )
    baseline = dict(policy)
    candidate = dict(policy)
    baseline["dataset_view_role"] = "baseline_uncurated"
    baseline["policy_id"] = "baseline_fake_v08k_policy"
    candidate["dataset_view_role"] = "candidate_curated"
    candidate["policy_id"] = "candidate_fake_v08k_policy"
    for payload in (baseline, candidate):
        payload["policy_artifact_sha256"] = script._sha256_payload_excluding(
            payload,
            "policy_artifact_sha256",
        )
    script.write_json(child_dir / "baseline_policy_artifact_v0_8k.json", baseline)
    script.write_json(child_dir / "candidate_policy_artifact_v0_8k.json", candidate)
```

- [ ] **Step 2: Add failing parent-gate test**

```python
def test_v09_requires_v08l_authority_ceiling_audit(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="missing_v0_8l_authority_ceiling_audit"):
        script.build_v09_fresh_uncurated_mix_rebase_slice(output_dir=tmp_path)
```

- [ ] **Step 3: Add failing dataset mix test**

```python
def test_v09_builds_preregistered_uncurated_mix_and_keeps_candidate_unchanged(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v09_parent_evidence(script, tmp_path)

    manifest = script.build_v09_fresh_uncurated_mix_rebase_slice(output_dir=tmp_path)

    gate = manifest["uncurated_mix_rebase_gate"]
    assert manifest["policy_slice"] == "v0_9"
    assert manifest["heldout_opened"] is False
    assert manifest["fresh_heldout_27000_27049_accessed"] is False
    assert manifest["fresh_calibration_seed_range"] == [30000, 30029]
    assert gate["passed"] is True
    assert gate["baseline_noise_mix_ratio"] == pytest.approx(0.40)
    assert gate["accepted_failure_ratio"] == pytest.approx(0.40)
    assert gate["baseline_failure_material_row_count"] > 0
    assert 0.35 <= gate["baseline_actual_failure_material_ratio"] <= 0.45
    assert gate["candidate_rows_unchanged_from_v08k"] is True
    assert gate["peer_fairness_mismatch_keys"] == []
```

- [ ] **Step 4: Add failing CLI build test**

```python
def test_v09_cli_builds_artifact_only_uncurated_mix_rebase(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v09_parent_evidence(script, tmp_path)

    result = script.main(
        [
            "--scenario-profile",
            "v0_6",
            "--policy-slice",
            "v0_9",
            "--fresh-uncurated-mix-rebase-only",
            "--output-dir",
            str(tmp_path),
        ]
    )

    manifest = script.read_json(tmp_path / script.V09_CHILD_OUTPUT_DIRNAME / "v0_9_uncurated_mix_rebase_manifest.json")
    evidence_manifest = script.read_json(tmp_path / "evidence_manifest.json")
    assert result == 0
    assert manifest["proof_authority"] is False
    assert evidence_manifest["proof_runtime"] == script.V09_SLICE_ID
    assert evidence_manifest["fresh_heldout_27000_27049_accessed"] is False
```

- [ ] **Step 5: Run RED**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v09" -q
```

Expected: fail because `build_v09_fresh_uncurated_mix_rebase_slice`, `V09_*`, and CLI flag do not exist.

### Task 2: Implement v0.9 Artifact Builder

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Add constants**

Add near v0.8l constants:

```python
V09_POLICY_SLICE_ID = "v0_9"
V09_SLICE_ID = "mvp2e_v09_fresh_attribution_preserving_uncurated_mix_rebase"
V09_CHILD_OUTPUT_DIRNAME = "v0_9_fresh_uncurated_mix_rebase"
V09_POLICY_ARTIFACT_SCHEMA_VERSION = "rdf_mvp2e_v09_policy_artifact_v0.1.0"
V09_MANIFEST_SCHEMA_VERSION = "rdf_mvp2e_v09_fresh_uncurated_mix_rebase_manifest_v0.1.0"
V09_REBASE_GATE_SCHEMA_VERSION = "rdf_mvp2e_v09_uncurated_mix_rebase_gate_v0.1.0"
V09_CALIBRATION_PRESIGNAL_SCHEMA_VERSION = "rdf_mvp2e_v09_calibration_presignal_gate_v0.1.0"
V09_HELDOUT_CLOSURE_SCHEMA_VERSION = "rdf_mvp2e_v09_heldout_closure_gate_v0.1.0"
V09_FRESH_CALIBRATION_RANGE = range(30000, 30030)
V09_FRESH_HELDOUT_RANGE = range(27000, 27050)
V09_BASELINE_NOISE_MIX_RATIO = 0.40
```

- [ ] **Step 2: Add parent loader**

Implement:

```python
def load_required_v08l_authority_ceiling_audit(output_dir: Path) -> dict[str, Any]:
    path = output_dir / V08L_CHILD_OUTPUT_DIRNAME / "v0_8l_authority_ceiling_audit_report.json"
    if not path.exists():
        raise ValueError("missing_v0_8l_authority_ceiling_audit")
    report = read_json(path)
    if (
        report.get("policy_slice") != V08L_POLICY_SLICE_ID
        or report.get("source_policy_slice") != V08K_POLICY_SLICE_ID
        or report.get("authority_ceiling_detected") is not True
        or report.get("uncurated_comparator_weak") is not True
        or report.get("recommended_downstream_slice") != V08L_RECOMMENDED_DOWNSTREAM_SLICE
        or report.get("heldout_opened") is not False
        or report.get("fresh_heldout_27000_27049_accessed") is not False
    ):
        raise ValueError("invalid_v0_8l_authority_ceiling_audit")
    report["path"] = str(path)
    report["sha256"] = _sha256_file(path)
    return report
```

- [ ] **Step 3: Add controlled-failure material extractor**

Implement helpers that load `train_generation_runtime_gate.json`, read its `generated_trace_paths`, classify summary success, and convert failed trace rows into HDF5 metadata rows using existing trace-row feature fields. Each failure row must set:

```python
row["accepted"] = False
row["uncurated_mix_policy_slice"] = V09_POLICY_SLICE_ID
row["uncurated_mix_is_failure_material"] = True
row["uncurated_mix_failure_type"] = "env_native_stability_window_not_reached"
row["uncurated_mix_source_trace_path"] = str(path)
row["uncurated_mix_source_trace_sha256"] = _sha256_file(path)
row["uncurated_mix_ratio_target"] = V09_BASELINE_NOISE_MIX_RATIO
```

- [ ] **Step 4: Add baseline mix builder**

Build:

```python
candidate_rows = _rows_from_hdf5_metadata(v0_8k_candidate_path)
success_rows = [row for row in candidate_rows if row.get("accepted") is not False]
failure_rows = extracted failed train-generation rows
baseline_rows = success_rows + deterministic duplicated failure_rows
```

Duplicate failure rows round-robin until:

```python
failure_count / len(baseline_rows) >= 0.40
```

Stop if the ratio would exceed `0.45`.

- [ ] **Step 5: Add policy artifacts and rebase gate**

Use `fit_phase_conditioned_bc_policy` for both views and wrap payloads by copying v0.8k policy authority fields. The gate must include:

```text
baseline_noise_mix_ratio
accepted_failure_ratio
failure_type_distribution
noise_profile_config_sha256
scripted_expert_config_sha256
controlled_failure_config_sha256
train_generation_config_sha256
baseline_actual_failure_material_ratio
candidate_rows_unchanged_from_v08k
peer_fairness_mismatch_keys
passed
heldout_opened=false
fresh_heldout_27000_27049_accessed=false
mvp2_closed=false
policy_uplift_proven=false
```

- [ ] **Step 6: Add CLI flag**

Add:

```text
--fresh-uncurated-mix-rebase-only
```

Require:

```text
--scenario-profile v0_6 --policy-slice v0_9
```

Reject `--clean`, Isaac flags, calibration/heldout modes, and all other artifact modes when combined.

- [ ] **Step 7: Run GREEN**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v09 or v08l or v08k" -q
```

Expected: pass.

### Task 3: Add v0.9 Fresh Runtime Path

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add fake-backend CLI test**

Add a test modelled on v0.8k runtime tests but using `V09_FRESH_CALIBRATION_RANGE`. Assert calibration runs before held-out and held-out opens only if calibration passes.

- [ ] **Step 2: Implement fresh manifest and runtime runner**

Implement:

```python
def build_v09_fresh_manifest(...)
def _v09_runtime_manifest_for_split(...)
def run_v09_fresh_uncurated_mix_rebase_runtime(...)
```

Use calibration `30000-30029`, held-out `27000-27049`, and burn previous calibration ranges including `29000-29029`.

- [ ] **Step 3: Add runtime CLI flag**

Add:

```text
--fresh-uncurated-mix-rebase-runtime
```

Reject fake backend flags for actual proof execution, following v0.8k runtime policy.

- [ ] **Step 4: Run focused runtime tests**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v09" -q
```

Expected: pass.

### Task 4: Verification and Actual Attempt

**Files:**
- Modify: `docs/developer/worklog.md`
- Modify: `Handoff.md`
- Modify: `tasks/todo.md`

- [ ] **Step 1: Run static verification**

Run:

```bash
uv run python -m compileall -q scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
```

- [ ] **Step 2: Build actual v0.9 artifact-only slice**

Run:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_9 \
  --fresh-uncurated-mix-rebase-only \
  --output-dir storage/proof_evidence/mvp2c_isaac_training_calibration \
  --pretty
```

- [ ] **Step 3: Run actual v0.9 calibration/held-out attempt**

Run:

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_9 \
  --fresh-uncurated-mix-rebase-runtime \
  --isaac-task Isaac-Factory-PegInsert-Direct-v0 \
  --device cuda:0 \
  --output-dir storage/proof_evidence/mvp2c_isaac_training_calibration \
  --pretty
```

- [ ] **Step 4: Continue loop based on result**

If calibration fails:

```text
preserve evidence
write next artifact-only diagnosis spec/plan
do not open held-out
do not claim MVP-2 Closed
```

If calibration passes and held-out closure passes:

```text
write closure report
mark MVP-2 Closed in Handoff/worklog/todo
report exact held-out baseline/candidate rates and limitations
```

## Self-review

- Spec coverage: parent audit gate, pre-registered baseline mix, peer fairness, fresh calibration/held-out seal, non-claims, and automatic fail-closed continuation are covered.
- Placeholder scan: no TBD/FIXME/open-ended steps.
- Type consistency: public functions and CLI flags use `v09`/`v0_9` consistently.
