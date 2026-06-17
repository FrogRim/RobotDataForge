# MVP-2E v0.14 Comparator Provenance / Row-Balance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `v0_14` as a provenance-checked, row-balanced uncurated comparator slice so baseline failure material cannot dominate the trainer as near-gate ALIGN tutoring data.

**Architecture:** Add `v0_14` as a narrow child slice of `v0_13`: preserve the v0.13 authority/runtime path, rebuild only the baseline training view with summary-provenance checks and row-balanced failure material, then use fresh calibration `39000-39029` and sealed held-out `40000-40049`. Candidate rows and policy remain unchanged except for v0.14 metadata wrapping.

**Tech Stack:** Python 3, HDF5 via existing `write_v07c_residual_train_view_hdf5`, pytest, Isaac runtime only through the existing evaluator script.

---

## File Structure

- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
  - Add v0.14 constants, row-balance/provenance helpers, artifact-only builder, runtime runner, CLI flags.
- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`
  - Register `v0_14` in the same hysteresis/runtime authority families as `v0_13`.
  - Preserve v0.13 policy influence authority diagnostics for v0.14.
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
  - Add artifact-only tests for provenance, row-balance, fresh split seal, and CLI guards.
- Modify: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`
  - Add v0.14 evaluator path regression.
- Update: `docs/developer/worklog.md`, `Handoff.md`, `tasks/todo.md`
  - Record v0.13 failure cause and v0.14 slice status.

---

### Task 1: Add Failing Tests For v0.14 Comparator Gate

**Files:**
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add focused tests**

Append tests near the existing v0.13 tests:

```python
def test_v14_rejects_failure_rows_from_success_summary(tmp_path: Path) -> None:
    import scripts.run_mvp2c_isaac_training_calibration as script

    success_trace = {
        "summary": {
            "success": True,
            "env_native_rollout_success": True,
            "failure_reason": "",
        },
        "trace": [],
    }
    trace_path = tmp_path / "misleading_failure_source.json"
    trace_path.write_text(json.dumps(success_trace), encoding="utf-8")
    row = {
        "accepted": False,
        "source_trace_role": "train_generation_failed_attempt",
        "runtime_trace_path": str(trace_path),
        "lateral_error_m": 0.0009,
        "behavior_state_phase": "ALIGN",
    }

    report = script.derive_v14_source_provenance_report([row], candidate_rows=[])

    assert report["passed"] is False
    assert "failure_row_source_trace_summary_success_true" in report["failure_reasons"]


def test_v14_row_balance_caps_terminal_failure_rows() -> None:
    import scripts.run_mvp2c_isaac_training_calibration as script

    success_rows = [{"accepted": True, "row_id": f"s{i}"} for i in range(100)]
    failure_rows = [
        {
            "accepted": False,
            "source_trace_role": "train_generation_failed_attempt",
            "source_trace_summary_success": False,
            "source_trace_summary_env_native_rollout_success": False,
            "source_trace_summary_failure_reason": "ENV_NATIVE_STABILITY_WINDOW_NOT_REACHED",
            "runtime_trace_path": f"trace_{trace_id}.json",
            "step": step,
            "behavior_state_phase": "ALIGN",
            "lateral_error_m": 0.0008,
        }
        for trace_id in range(12)
        for step in range(500)
    ]

    rows, report = script.build_v14_row_balanced_baseline_rows(
        success_rows=success_rows,
        failure_rows=failure_rows,
    )

    selected_failure_rows = [
        row for row in rows if row.get("uncurated_row_balance_is_failure_material") is True
    ]
    assert len(selected_failure_rows) == 100
    assert report["baseline_actual_failure_material_ratio"] == 0.5
    assert max(report["selected_failure_rows_per_trace"].values()) <= 300
    assert report["duplicate_failure_rows_allowed"] is False


def test_v14_artifact_only_builds_fresh_manifest_and_keeps_heldout_sealed(tmp_path: Path) -> None:
    import scripts.run_mvp2c_isaac_training_calibration as script

    _write_fake_v13_parent_evidence(tmp_path)

    manifest = script.build_v14_comparator_provenance_row_balance_slice(output_dir=tmp_path)

    gate = manifest["comparator_provenance_row_balance_gate"]
    assert gate["passed"] is True
    assert manifest["fresh_calibration_seed_range"] == [39000, 39029]
    assert manifest["fresh_heldout_seed_range"] == [40000, 40049]
    assert manifest["fresh_heldout_40000_40049_accessed"] is False
    assert manifest["heldout_opened"] is False
    assert manifest["mvp2_closed"] is False
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v14" -q
```

Expected: FAIL because v0.14 functions/constants do not exist yet.

---

### Task 2: Implement v0.14 Comparator Builder

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`

- [ ] **Step 1: Add constants near v0.13 constants**

```python
V14_POLICY_SLICE_ID = "v0_14"
V14_SLICE_ID = "mvp2e_v14_comparator_provenance_row_balance_slice"
V14_CHILD_OUTPUT_DIRNAME = "v0_14_comparator_provenance_row_balance"
V14_POLICY_ARTIFACT_SCHEMA_VERSION = "rdf_mvp2e_v14_policy_artifact_v0.1.0"
V14_MANIFEST_SCHEMA_VERSION = "rdf_mvp2e_v14_comparator_provenance_row_balance_manifest_v0.1.0"
V14_GATE_SCHEMA_VERSION = "rdf_mvp2e_v14_comparator_provenance_row_balance_gate_v0.1.0"
V14_CALIBRATION_PRESIGNAL_SCHEMA_VERSION = "rdf_mvp2e_v14_calibration_presignal_gate_v0.1.0"
V14_HELDOUT_CLOSURE_SCHEMA_VERSION = "rdf_mvp2e_v14_heldout_closure_gate_v0.1.0"
V14_FRESH_CALIBRATION_RANGE = range(39000, 39030)
V14_FRESH_HELDOUT_RANGE = range(40000, 40050)
V14_BASELINE_FAILURE_MATERIAL_RATIO = 0.50
V14_BASELINE_FAILURE_RATIO_MIN = 0.45
V14_BASELINE_FAILURE_RATIO_MAX = 0.55
V14_MAX_ROWS_PER_FAILURE_SOURCE_TRACE = 300
V14_MAX_FAILURE_TO_SUCCESS_ROW_RATIO = 1.10
V14_BASELINE_FLOOR_SUCCESS_MAXIMUM = 0.65
V14_CALIBRATION_SUCCESS_MINIMUM = 0.80
V14_CALIBRATION_UPLIFT_MINIMUM = 0.20
```

- [ ] **Step 2: Add source summary helper**

```python
def _v14_source_summary_from_row(row: dict[str, Any]) -> dict[str, Any]:
    path_value = row.get("runtime_trace_path") or row.get("source_trace_path")
    summary = {
        "path": str(path_value) if path_value else "",
        "success": row.get("source_trace_summary_success"),
        "env_native_rollout_success": row.get("source_trace_summary_env_native_rollout_success"),
        "failure_reason": row.get("source_trace_summary_failure_reason"),
    }
    if path_value and (summary["success"] is None or summary["env_native_rollout_success"] is None):
        path = Path(str(path_value))
        if path.exists():
            payload = read_json(path)
            payload_summary = payload.get("summary") or {}
            summary.update(
                {
                    "success": bool(payload_summary.get("success")),
                    "env_native_rollout_success": bool(
                        payload_summary.get("env_native_rollout_success", payload_summary.get("success"))
                    ),
                    "failure_reason": str(payload_summary.get("failure_reason") or ""),
                }
            )
    return summary
```

- [ ] **Step 3: Add provenance report**

```python
def derive_v14_source_provenance_report(
    baseline_rows: list[dict[str, Any]],
    *,
    candidate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    reasons: list[str] = []
    failure_rows = [row for row in baseline_rows if row.get("accepted") is False]
    for row in failure_rows:
        summary = _v14_source_summary_from_row(row)
        if summary["success"] is True or summary["env_native_rollout_success"] is True:
            reasons.append("failure_row_source_trace_summary_success_true")
            break
        if not str(summary.get("failure_reason") or ""):
            reasons.append("failure_row_missing_source_failure_reason")
            break
    if any(_v08k_any_calibration_or_heldout_training_rows(candidate_rows + baseline_rows)):
        reasons.append("calibration_or_heldout_rows_used_for_training")
    report = {
        "schema_version": "rdf_mvp2e_v14_source_provenance_report_v0.1.0",
        "policy_slice": V14_POLICY_SLICE_ID,
        "failure_row_count": len(failure_rows),
        "candidate_row_count": len(candidate_rows),
        "passed": not reasons,
        "failure_reasons": reasons,
        "failure_reason": ",".join(reasons),
    }
    report["source_provenance_report_sha256"] = _sha256_payload_excluding(
        report,
        "source_provenance_report_sha256",
    )
    return report
```

- [ ] **Step 4: Add row-balanced baseline function**

```python
def build_v14_row_balanced_baseline_rows(
    *,
    success_rows: list[dict[str, Any]],
    failure_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not success_rows:
        raise ValueError("v0_14_success_rows_missing")
    if not failure_rows:
        raise ValueError("v0_14_failure_rows_missing")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in failure_rows:
        trace_key = str(row.get("runtime_trace_path") or row.get("source_trace_path") or "")
        if not trace_key:
            raise ValueError("v0_14_failure_row_missing_source_trace")
        grouped.setdefault(trace_key, []).append(_v09_deepcopy_row(row))
    capped: list[dict[str, Any]] = []
    selected_per_trace: dict[str, int] = {}
    for trace_key, rows in sorted(grouped.items()):
        rows_sorted = sorted(rows, key=lambda item: int(item.get("step", 0)))
        selected = rows_sorted[-V14_MAX_ROWS_PER_FAILURE_SOURCE_TRACE:]
        selected_per_trace[trace_key] = len(selected)
        capped.extend(selected)
    target_failure_count = min(len(capped), len(success_rows))
    selected_failure_rows: list[dict[str, Any]] = []
    trace_order = sorted(grouped)
    per_trace_selected: Counter[str] = Counter()
    index_by_trace = {trace_key: 0 for trace_key in trace_order}
    capped_by_trace = {
        trace_key: sorted(rows, key=lambda item: int(item.get("step", 0)))[-V14_MAX_ROWS_PER_FAILURE_SOURCE_TRACE:]
        for trace_key, rows in grouped.items()
    }
    while len(selected_failure_rows) < target_failure_count:
        progressed = False
        for trace_key in trace_order:
            rows = capped_by_trace[trace_key]
            index = index_by_trace[trace_key]
            if index >= len(rows):
                continue
            row = _v09_deepcopy_row(rows[index])
            row.update(
                {
                    "proof_role": "v0_14_row_balanced_uncurated_failure_material",
                    "uncurated_row_balance_policy_slice": V14_POLICY_SLICE_ID,
                    "uncurated_row_balance_is_failure_material": True,
                    "uncurated_row_balance_duplicate_allowed": False,
                    "uncurated_row_balance_source_row_sha256": _sha256_payload(rows[index]),
                }
            )
            selected_failure_rows.append(row)
            per_trace_selected[trace_key] += 1
            index_by_trace[trace_key] += 1
            progressed = True
            if len(selected_failure_rows) >= target_failure_count:
                break
        if not progressed:
            break
    baseline_success_rows = [_v09_deepcopy_row(row) for row in success_rows]
    for row in baseline_success_rows:
        row["uncurated_row_balance_policy_slice"] = V14_POLICY_SLICE_ID
        row["uncurated_row_balance_is_failure_material"] = False
    baseline_rows = baseline_success_rows + selected_failure_rows
    ratio = len(selected_failure_rows) / len(baseline_rows)
    report = {
        "success_row_count": len(success_rows),
        "source_failure_row_count": len(failure_rows),
        "source_failure_trace_count": len(grouped),
        "selected_failure_row_count": len(selected_failure_rows),
        "baseline_actual_failure_material_ratio": round(ratio, 12),
        "baseline_failure_material_ratio_target": V14_BASELINE_FAILURE_MATERIAL_RATIO,
        "max_rows_per_failure_source_trace": V14_MAX_ROWS_PER_FAILURE_SOURCE_TRACE,
        "duplicate_failure_rows_allowed": False,
        "selected_failure_rows_per_trace": dict(sorted(per_trace_selected.items())),
        "capped_failure_rows_per_trace": dict(sorted(selected_per_trace.items())),
    }
    return baseline_rows, report
```

- [ ] **Step 5: Build v0.14 artifact slice**

Implement `build_v14_comparator_provenance_row_balance_slice(output_dir: Path) -> dict[str, Any]` that:

```python
parent_child_dir = output_dir / V13_CHILD_OUTPUT_DIRNAME
candidate_parent = read_json(parent_child_dir / "candidate_policy_artifact_v0_13.json")
baseline_parent = read_json(parent_child_dir / "baseline_policy_artifact_v0_13.json")
source_dir = output_dir / V12_CHILD_OUTPUT_DIRNAME
candidate_rows = _rows_from_hdf5_metadata(source_dir / "candidate_curated_train_v0_12.hdf5")
v12_baseline_rows = _rows_from_hdf5_metadata(
    source_dir / "baseline_uncurated_terminal_low_floor_train_v0_12.hdf5"
)
success_rows = [_v09_deepcopy_row(row) for row in candidate_rows if row.get("accepted") is not False]
failure_rows = [_v09_deepcopy_row(row) for row in v12_baseline_rows if row.get("accepted") is False]
baseline_rows, row_balance_report = build_v14_row_balanced_baseline_rows(
    success_rows=success_rows,
    failure_rows=failure_rows,
)
provenance_report = derive_v14_source_provenance_report(
    baseline_rows,
    candidate_rows=candidate_rows,
)
```

Write HDF5 views with existing `write_v07c_residual_train_view_hdf5`, fit only baseline with `fit_phase_conditioned_bc_policy`, wrap candidate policy from v13 unchanged, and write:

```text
candidate_curated_train_v0_14.hdf5
baseline_uncurated_row_balanced_train_v0_14.hdf5
candidate_policy_artifact_v0_14.json
baseline_policy_artifact_v0_14.json
v0_14_comparator_provenance_row_balance_gate.json
v0_14_comparator_provenance_row_balance_manifest.json
```

- [ ] **Step 6: Run tests**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v14" -q
```

Expected: PASS.

---

### Task 3: Register v0.14 In Evaluator Runtime Path

**Files:**
- Modify: `scripts/run_mvp2b_isaac_proof_evaluator.py`
- Modify: `apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py`

- [ ] **Step 1: Add evaluator test**

Add:

```python
def test_v14_runtime_policy_slice_uses_v13_hysteresis_and_policy_influence() -> None:
    import scripts.run_mvp2b_isaac_proof_evaluator as script

    assert "v0_14" in script.V07E_HYSTERESIS_RUNTIME_POLICY_SLICE_IDS
    assert "v0_14" not in script.V08H_DERIVED_POLICY_SLICE_IDS
```

- [ ] **Step 2: Add constants/sets**

In evaluator:

```python
V14_POLICY_SLICE_ID = "v0_14"
```

Add `V14_POLICY_SLICE_ID` to `V07E_HYSTERESIS_RUNTIME_POLICY_SLICE_IDS` and to the
same v0.13 validation branch in `_validated_v07e_hysteresis_authority_config`.

- [ ] **Step 3: Run focused evaluator tests**

```bash
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -k "v14 or v13" -q
```

Expected: PASS.

---

### Task 4: Add CLI And Runtime Runner

**Files:**
- Modify: `scripts/run_mvp2c_isaac_training_calibration.py`
- Modify: `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`

- [ ] **Step 1: Add CLI flags**

Add parser flags:

```python
parser.add_argument("--comparator-provenance-row-balance-only", action="store_true")
parser.add_argument("--comparator-provenance-row-balance-runtime", action="store_true")
```

Add `v0_14` to `--policy-slice` choices and policy-slice guard.

- [ ] **Step 2: Add runtime helper**

Implement `run_v14_comparator_provenance_row_balance_runtime(...)` by mirroring
`run_v13_policy_influence_authority_ceiling_runtime(...)` with:

```text
child_dir = output_dir / V14_CHILD_OUTPUT_DIRNAME
calibration range = 39000-39029
heldout range = 40000-40049
baseline view = baseline_uncurated_row_balanced_train_v0_14.hdf5
candidate view = candidate_curated_train_v0_14.hdf5
runtime output dirs = isaac_runtime_fresh_calibration_v0_14 / isaac_runtime_fresh_heldout_v0_14
```

Calibration gate uses v13 thresholds but writes v14 schema/version:

```python
failure_reason = ""
if runtime_gate.get("passed") is not True or runtime_metadata.get("runtime_backend") != "isaac_runtime":
    failure_reason = "calibration_runtime_gate_not_passed"
elif baseline_rate > V14_BASELINE_FLOOR_SUCCESS_MAXIMUM:
    failure_reason = "baseline_calibration_success_floor_above_v0_14_maximum"
elif candidate_rate < V14_CALIBRATION_SUCCESS_MINIMUM:
    failure_reason = "candidate_calibration_success_below_v0_14_minimum"
elif success_gap < V14_CALIBRATION_UPLIFT_MINIMUM:
    failure_reason = "candidate_baseline_success_gap_below_v0_14_minimum"
elif influence["policy_influence_preservation_passed"] is not True:
    failure_reason = "policy_influence_preservation_failed"
```

- [ ] **Step 3: Add CLI guard tests**

```python
def test_v14_cli_rejects_clean_before_isaac(tmp_path: Path) -> None:
    import scripts.run_mvp2c_isaac_training_calibration as script

    args = script.parse_args(
        [
            "--scenario-profile", "v0_6",
            "--policy-slice", "v0_14",
            "--comparator-provenance-row-balance-runtime",
            "--clean",
            "--output-dir", str(tmp_path),
        ]
    )
    with pytest.raises(SystemExit):
        script.main(args)
```

Also add fake-backend rejection tests matching v13 guards.

- [ ] **Step 4: Run focused tests**

```bash
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -k "v14" -q
```

Expected: PASS.

---

### Task 5: Verification And Runtime Proof Attempt

**Files:**
- No code changes unless verification fails.

- [ ] **Step 1: Compile and lint**

```bash
uv run python -m compileall -q scripts/run_mvp2c_isaac_training_calibration.py scripts/run_mvp2b_isaac_proof_evaluator.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py
uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py scripts/run_mvp2b_isaac_proof_evaluator.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py
```

Expected: both pass.

- [ ] **Step 2: Build artifact-only v0.14**

```bash
uv run python scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_14 \
  --comparator-provenance-row-balance-only \
  --output-dir storage/proof_evidence/mvp2c_isaac_training_calibration \
  --pretty
```

Expected:

```text
comparator_provenance_row_balance_gate_passed = true
fresh_calibration_39000_39029_accessed = false
fresh_heldout_40000_40049_accessed = false
heldout_opened = false
mvp2_closed = false
```

- [ ] **Step 3: Run actual Isaac calibration**

```bash
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --scenario-profile v0_6 \
  --policy-slice v0_14 \
  --comparator-provenance-row-balance-runtime \
  --output-dir storage/proof_evidence/mvp2c_isaac_training_calibration \
  --pretty
```

Expected if calibration passes: held-out runs automatically and closure gate is written.

Expected if calibration fails: fail-closed with `fresh_heldout_40000_40049_accessed=false`, then start next diagnosis loop.

- [ ] **Step 4: Diff hygiene**

```bash
git diff --check
```

Expected: PASS.

---

## Self-Review

- Spec coverage:
  - v0.13 failure evidence: Task 2 gate metadata and docs.
  - provenance gate: Task 2.
  - row balance: Task 2.
  - evaluator runtime support: Task 3.
  - fresh split and sealed held-out: Task 4/5.
  - runtime calibration/held-out closure: Task 4/5.
- Placeholder scan: no TBD/TODO placeholders.
- Type consistency: all new public function names use `v14` prefix and are referenced by tests before implementation.
