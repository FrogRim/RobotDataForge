# ForgeXR Offline Provenance Analyzer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an offline trajectory provenance timeline that identifies where HMD-to-robot discontinuities first appear.

**Architecture:** Extend the existing `scripts/analyze_hmd_motion_mapping.py` analyzer instead of creating a parallel tool. The new section computes transition-level deltas across raw wrist, aligned wrist, raw-wrist origin, wrist offset, desired target, command, EEF, and scene-state fields, then records the first stage whose delta crosses a diagnostic threshold.

**Tech Stack:** Python standard library, existing pytest tests in `apps/api/tests/test_teleop_diagnostics_scripts.py`, no new dependencies.

**Repository Constraint:** Do not run physical HMD, Quest/OpenXR, Isaac collection, or collection-loop commands. Do not commit without explicit user approval.

---

### Task 1: Add Red Tests For Provenance Classification

**Files:**
- Modify: `apps/api/tests/test_teleop_diagnostics_scripts.py`
- Modify later: `scripts/analyze_hmd_motion_mapping.py`

- [ ] **Step 1: Write failing tests**

Add synthetic tests near the existing `test_motion_mapping_reports_scene_state_discontinuity` tests:

```python
def test_motion_mapping_provenance_timeline_classifies_raw_wrist_first_jump(tmp_path: Path) -> None:
    path = tmp_path / "traj_raw_first.json"
    write_json(
        path,
        raw_wrist_trajectory_payload(
            [
                raw_wrist_motion_frame(0, hand_delta=[0.0, 0.0, 0.0], target=[1.0, 0.0, 0.0], current=[1.0, 0.0, 0.0], raw_wrist_pose=[0.0, 0.0, 0.0], aligned_wrist_pose=[0.0, 0.0, 0.0]),
                raw_wrist_motion_frame(1, hand_delta=[0.0, 0.0, 0.0], target=[1.0, 0.0, 0.0], current=[1.0, 0.0, 0.0], raw_wrist_pose=[0.25, 0.0, 0.0], aligned_wrist_pose=[0.0, 0.0, 0.0]),
            ]
        ),
    )

    report = motion_mapping.analyze_trajectory(path)
    event = report["provenance_timeline"]["events"][0]

    assert event["first_discontinuity_stage"] == "raw_wrist"
    assert report["provenance_timeline"]["first_stage_counts"] == {"raw_wrist": 1}
```

Add matching tests for `aligned_wrist`, `desired_target`, and `actual_eef` first-stage events.

- [ ] **Step 2: Run red tests**

Run:

```bash
uv run pytest apps/api/tests/test_teleop_diagnostics_scripts.py::test_motion_mapping_provenance_timeline_classifies_raw_wrist_first_jump -q
```

Expected: FAIL because `provenance_timeline` is not implemented yet.

### Task 2: Implement Provenance Timeline

**Files:**
- Modify: `scripts/analyze_hmd_motion_mapping.py`

- [ ] **Step 1: Add field getter helpers**

Add helpers for aligned wrist, raw wrist origin, wrist offset, desired target, applied command, and scene static vectors.

- [ ] **Step 2: Add `provenance_timeline_stats(frames)`**

Implement a transition scanner that emits:

```python
{
    "schema_version": "rdf_hmd_provenance_timeline_v0.1.0",
    "event_count": 1,
    "first_stage_counts": {"raw_wrist": 1},
    "stage_counts": {"raw_wrist": 1},
    "events": [
        {
            "from_index": 0,
            "to_index": 1,
            "first_discontinuity_stage": "raw_wrist",
            "stages": {
                "raw_wrist": {"available": True, "delta_m": 0.25, "threshold_m": 0.10, "over_threshold": True}
            }
        }
    ],
}
```

- [ ] **Step 3: Wire report output**

Add `report["provenance_timeline"] = provenance_timeline_stats(frames)` inside `analyze_trajectory()`.

### Task 3: Verify And Document

**Files:**
- Modify: `/home/kangrim/tasks/todo.md`
- Modify: `Handoff.md`

- [ ] **Step 1: Run targeted tests**

Run:

```bash
uv run pytest apps/api/tests/test_teleop_diagnostics_scripts.py::test_motion_mapping_provenance_timeline_classifies_raw_wrist_first_jump apps/api/tests/test_teleop_diagnostics_scripts.py::test_motion_mapping_provenance_timeline_classifies_aligned_wrist_first_jump apps/api/tests/test_teleop_diagnostics_scripts.py::test_motion_mapping_provenance_timeline_classifies_target_first_jump apps/api/tests/test_teleop_diagnostics_scripts.py::test_motion_mapping_provenance_timeline_classifies_eef_first_jump apps/api/tests/test_teleop_diagnostics_scripts.py::test_motion_mapping_reports_target_accumulation_when_target_exceeds_current_hand_delta apps/api/tests/test_teleop_diagnostics_scripts.py::test_motion_mapping_reports_scene_state_discontinuity -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run saved trajectory offline**

Run:

```bash
uv run python scripts/analyze_hmd_motion_mapping.py storage/trajectories/traj_7f78c4bbd77e.json --pretty --output storage/hmd_motion_mapping/provenance_timeline_traj_7f78c4bbd77e.json
```

Expected: command succeeds and writes a report containing `provenance_timeline`.

- [ ] **Step 3: Run static checks**

Run:

```bash
python3 -m py_compile scripts/analyze_hmd_motion_mapping.py
git diff --check -- scripts/analyze_hmd_motion_mapping.py apps/api/tests/test_teleop_diagnostics_scripts.py docs/superpowers/plans/2026-06-03-forgexr-offline-provenance-analyzer.md
```

Expected: both checks pass.
