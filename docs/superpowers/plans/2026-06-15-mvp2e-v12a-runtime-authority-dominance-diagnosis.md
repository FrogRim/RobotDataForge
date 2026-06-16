# MVP-2E v0.12a Runtime Authority Dominance Diagnosis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** v0.12 actual Isaac calibration failure를 artifact-only로 분석해 shared runtime authority가 learned residual 차이를 압축했는지 증명한다.

**Architecture:** 기존 `run_mvp2c_isaac_training_calibration.py`에 v0.12a diagnosis-only slice를 추가한다. 입력은 v0.12 calibration gate, paired rollout JSON, runtime trace JSON이며, held-out에는 접근하지 않는다.

**Tech Stack:** Python, pytest, JSON proof artifacts, existing MVP-2C script conventions.

---

### Task 1: RED Tests

**Files:**
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add failing tests**

Add tests near the v0.12 tests:

```python
def test_v12a_requires_v12_actual_calibration_evidence(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")

    with pytest.raises(ValueError, match="missing_v0_12_calibration_presignal_gate"):
        script.build_v12a_runtime_authority_dominance_diagnosis(output_dir=tmp_path)


def test_v12a_classifies_runtime_authority_dominance(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v12_failed_calibration_evidence(script, tmp_path)

    report = script.build_v12a_runtime_authority_dominance_diagnosis(output_dir=tmp_path)

    assert report["policy_slice"] == "v0_12a"
    assert report["source_policy_slice"] == "v0_12"
    assert report["primary_root_cause_class"] == "RUNTIME_AUTHORITY_DOMINATES_LEARNED_RESIDUAL_OUTCOME"
    assert report["paired_outcome_counts"] == {"B1_C1": 25, "B1_C0": 0, "B0_C1": 0, "B0_C0": 5}
    assert report["action_compression_report"]["post_adapter_delta_smaller_than_raw_delta"] is True
    assert report["recommended_downstream_slice"] == "v0_13_policy_influence_authority_ceiling_slice"
    assert report["fresh_heldout_36000_36049_accessed"] is False
    assert report["mvp2_closed"] is False
    assert report["policy_uplift_proven"] is False
```

- [ ] **Step 2: Verify RED**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v12a" -q
```

Expected: fail because `build_v12a_runtime_authority_dominance_diagnosis` does not exist.

### Task 2: Diagnosis Implementation

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Add v0.12a constants**

Add constants after v0.12 constants:

```python
V12A_POLICY_SLICE_ID = "v0_12a"
V12A_SLICE_ID = "mvp2e_v12a_runtime_authority_dominance_diagnosis"
V12A_CHILD_OUTPUT_DIRNAME = "v0_12a_runtime_authority_dominance_diagnosis"
V12A_DIAGNOSIS_SCHEMA_VERSION = "rdf_mvp2e_v12a_runtime_authority_dominance_diagnosis_v0.1.0"
V12A_RECOMMENDED_DOWNSTREAM_SLICE = "v0_13_policy_influence_authority_ceiling_slice"
```

- [ ] **Step 2: Add artifact loaders and paired outcome helpers**

Implement:

```python
def _v12a_calibration_gate_path(output_dir: Path) -> Path: ...
def _v12a_rollout_path(output_dir: Path, role: str) -> Path: ...
def _v12a_paired_outcomes(...) -> tuple[dict[str, int], dict[str, list[int]], list[dict[str, Any]]]: ...
```

- [ ] **Step 3: Add action compression report**

Implement `build_v12a_action_compression_report(...)` to compare:

- `raw_action_before_authority`
- `raw_action_after_authority`
- `pre_controller_action_vector`
- `post_adapter_action_vector`

The report must include:

- mean raw delta
- mean post-adapter delta
- post-adapter identical fraction
- shared XY authority active fraction
- final post-adapter z-block active fraction
- `post_adapter_delta_smaller_than_raw_delta`

- [ ] **Step 4: Add main diagnosis builder**

Implement `build_v12a_runtime_authority_dominance_diagnosis(output_dir: Path)`.

It must:

- require actual Isaac v0.12 calibration evidence
- require held-out unopened
- write paired outcome table
- write action compression report
- classify `RUNTIME_AUTHORITY_DOMINATES_LEARNED_RESIDUAL_OUTCOME`
- recommend `v0_13_policy_influence_authority_ceiling_slice`
- mark `proof_authority=false`, `mvp2_closed=false`, `policy_uplift_proven=false`

### Task 3: CLI Wiring

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Add parser choice and flag**

Add `v0_12a` to `--policy-slice` choices and add:

```python
parser.add_argument("--baseline-floor-suppression-diagnosis-only", action="store_true")
```

- [ ] **Step 2: Add command serialization and guard**

Add flag support in `_command_from_args` and special policy-slice guard.

- [ ] **Step 3: Add CLI branch**

The branch must reject:

- `--clean`
- non `--scenario-profile v0_6`
- non `--policy-slice v0_12a`
- any other special mode

It must write `evidence_manifest.json` with:

- `proof_runtime=V12A_SLICE_ID`
- `runtime_backend=offline_artifact_diagnosis`
- `calibration_opened=true`
- `heldout_opened=false`
- `fresh_heldout_36000_36049_accessed=false`

### Task 4: GREEN Verification

**Files:**
- Modify: tests and script above

- [ ] **Step 1: Run focused tests**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v12a" -q
```

Expected: pass.

- [ ] **Step 2: Run adjacent regression**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v12 or v12a" -q
```

Expected: pass.

- [ ] **Step 3: Run static checks**

```bash
uv run python -m compileall -q scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
```

Expected: pass.

### Task 5: Evidence Run

**Files:**
- Generated: `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_12a_runtime_authority_dominance_diagnosis/*.json`

- [ ] **Step 1: Run artifact-only diagnosis**

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_12a \
  --baseline-floor-suppression-diagnosis-only \
  --output-dir storage/proof_evidence/mvp2c_isaac_training_calibration \
  --pretty
```

Expected: `primary_root_cause_class=RUNTIME_AUTHORITY_DOMINATES_LEARNED_RESIDUAL_OUTCOME`.
