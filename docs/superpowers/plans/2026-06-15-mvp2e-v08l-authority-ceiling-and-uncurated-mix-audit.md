# MVP-2E v0.8l Authority Ceiling / Uncurated Mix Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** v0.8k calibration failure를 artifact-only로 audit해, held-out을 열지 않고 authority ceiling / weak uncurated comparator 여부를 JSON evidence로 고정한다.

**Architecture:** `scripts/run_mvp2c_isaac_training_calibration.py`에 v0.8l audit builder와 CLI flag를 추가한다. HDF5 train views와 calibration trace JSON만 읽고, 새 Isaac runtime이나 policy training은 실행하지 않는다.

**Tech Stack:** Python 3.11, h5py, pytest, existing proof evidence helpers.

---

### Task 1: v0.8l audit tests

**Files:**
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add fake v0.8k evidence writer**

Create a helper that writes:

```python
def _write_fake_v08l_v08k_evidence(script: Any, output_dir: Path) -> None:
    child_dir = output_dir / script.V08K_CHILD_OUTPUT_DIRNAME
    trace_dir = child_dir / "isaac_runtime_fresh_calibration_v0_8k" / "isaac_runtime_heldout_rollout_traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    child_dir.mkdir(parents=True, exist_ok=True)
    gate = {
        "schema_version": script.V08K_CALIBRATION_PRESIGNAL_SCHEMA_VERSION,
        "policy_slice": "v0_8k",
        "slice_id": script.V08K_SLICE_ID,
        "passed": False,
        "failure_reason": "candidate_baseline_success_gap_below_minimum",
        "baseline_calibration_success_count": 26,
        "candidate_calibration_success_count": 27,
        "baseline_calibration_success_rate": 26 / 30,
        "candidate_calibration_success_rate": 27 / 30,
        "candidate_baseline_success_gap": 1 / 30,
        "heldout_opened": False,
        "fresh_heldout_27000_27049_accessed": False,
        "trace_paths": {"baseline": [], "candidate": []},
    }
    gate["calibration_presignal_gate_sha256"] = script._sha256_payload_excluding(
        gate,
        "calibration_presignal_gate_sha256",
    )
    script.write_json(child_dir / "calibration_presignal_gate_v0_8k.json", gate)
```

- [ ] **Step 2: Add focused test**

Add:

```python
def test_v08l_detects_authority_ceiling_and_recommends_rebase(tmp_path: Path) -> None:
    script = load_script("run_mvp2c_isaac_training_calibration")
    _write_fake_v08l_v08k_evidence(script, tmp_path)
    _write_fake_v08k_source_train_views(script, tmp_path)
    report = script.build_v08l_authority_ceiling_uncurated_mix_audit(output_dir=tmp_path)
    assert report["policy_slice"] == "v0_8l"
    assert report["authority_ceiling_detected"] is True
    assert report["uncurated_comparator_weak"] is True
    assert report["recommended_downstream_slice"] == "v0_9_fresh_attribution_preserving_uncurated_mix_rebase"
    assert report["heldout_opened"] is False
    assert report["fresh_heldout_27000_27049_accessed"] is False
```

- [ ] **Step 3: Run RED**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08l" -q
```

Expected: fail because builder is missing.

### Task 2: v0.8l audit implementation

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Add constants**

Add `V08L_POLICY_SLICE_ID`, `V08L_SLICE_ID`, `V08L_CHILD_OUTPUT_DIRNAME`, and `V08L_AUDIT_SCHEMA_VERSION` near v0.8k constants.

- [ ] **Step 2: Add HDF5 and trace summary helpers**

Implement helpers that:

- read `actions`, `features`, `metadata_json`
- count accepted/rejected rows
- compute rejected DESCEND negative-z fraction
- compute calibration trace success rates and mean residual z by role

- [ ] **Step 3: Add builder**

Implement:

```python
def build_v08l_authority_ceiling_uncurated_mix_audit(*, output_dir: Path) -> dict[str, Any]:
    ...
```

The builder must write:

```text
v0_8l_authority_ceiling_uncurated_mix_audit/v0_8l_authority_ceiling_audit_report.json
```

and return the report.

- [ ] **Step 4: Add CLI flag**

Add `--authority-ceiling-audit-only` and route it in `main()`.

- [ ] **Step 5: Run GREEN**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v08l or v08k" -q
```

Expected: pass.

### Task 3: verification and execution

**Files:**
- Modify: `docs/developer/worklog.md`
- Modify: `Handoff.md`
- Modify: `tasks/todo.md`

- [ ] **Step 1: Run static checks**

Run:

```bash
uv run python -m compileall -q scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
```

- [ ] **Step 2: Build actual audit artifact**

Run:

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py --scenario-profile v0_6 --policy-slice v0_8l --authority-ceiling-audit-only --output-dir storage/proof_evidence/mvp2c_isaac_training_calibration --pretty
```

- [ ] **Step 3: Record result**

Update worklog/Handoff/todo with:

- v0.8k lineage fix evidence
- v0.8k calibration result: baseline 26/30, candidate 27/30, gap 0.033, held-out sealed
- v0.8l audit result and recommended downstream slice

## Self-review

- Spec coverage: covers artifact-only diagnosis, held-out guard, and downstream recommendation.
- Placeholder scan: no `TBD` or open-ended implementation steps.
- Type consistency: function and flag names match planned tests and CLI command.
