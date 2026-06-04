# ForgeXR Input Signal State And Action Eligibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separate input validity from control safety, and separate recorded robot commands from learning-eligible labels.

**Architecture:** Add `InputSignalState` beside `WristPoseSample` in `scripts/rdf_input_sources.py`. Recorder action payloads consume control/input state metadata and mark `learning_action` eligibility explicitly. IsaacLab raw-wrist metadata mirrors the same state vocabulary without importing repo-local modules.

**Tech Stack:** Python standard library, existing pytest tests, no new dependencies.

**Repository Constraint:** Do not run physical HMD, Quest/OpenXR, Isaac collection, or collection-loop commands. Do not commit without explicit user approval.

---

### Task 1: PR2 InputSignalState

**Files:**
- Modify: `scripts/rdf_input_sources.py`
- Modify: `apps/api/tests/test_teleop_diagnostics_scripts.py`

- [x] Add failing tests proving a valid/tracked held sample is not `control_safe`.
- [x] Add failing tests proving missing timestamp/confidence are represented as explicit provenance rather than implied stability.
- [x] Implement `InputSignalState`.
- [x] Add `WristPoseSample.input_signal_state()` helper.

### Task 2: PR2 Recorder Learning Eligibility

**Files:**
- Modify: `scripts/rdf_isaac_runtime_recorder.py`
- Modify: `apps/api/tests/test_teleop_diagnostics_scripts.py`

- [x] Add failing tests proving accepted raw-wrist direct actions are `learning_action.eligible == True`.
- [x] Add failing tests proving held/tracking-gated actions are `learning_action.eligible == False`.
- [x] Implement `_learning_action_eligibility()`.
- [x] Store eligibility fields inside `action.learning_action`.

### Task 3: PR3 Live Raw-Wrist Provenance Alignment

**Files:**
- Modify: `/home/kangrim/IsaacLab/scripts/environments/teleoperation/teleop_se3_agent.py`
- Modify: `apps/api/tests/test_teleop_diagnostics_scripts.py`

- [x] Add static failing tests that live raw-wrist metadata contains `input_signal_state`, `control_safe`, and `learning_label_eligible`.
- [x] Implement small local signal-state metadata helper in IsaacLab teleop script.
- [x] Attach state to accepted, warn, held, tracking-gate, and reacquire metadata.

### Task 4: Verification

- [x] Run targeted HMD-free tests.
- [x] Run `uv run pytest apps/api/tests/test_teleop_diagnostics_scripts.py -q`.
- [x] Run `python3 -m py_compile scripts/rdf_input_sources.py scripts/rdf_isaac_runtime_recorder.py scripts/analyze_hmd_motion_mapping.py /home/kangrim/IsaacLab/scripts/environments/teleoperation/teleop_se3_agent.py`.
- [x] Run `uvx ruff check` on changed repo Python files.
- [x] Run `git diff --check` on changed repo files.
