# MVP-1+ UR File-Backed Lineage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add file-backed UR recorded-log fixture import and lineage hashes to the MVP-1+ proof.

**Architecture:** Keep the existing MVP-1+ proof path intact. Add a source-log selection boundary in `run_mvp1plus_embodiment_proof.py` so only the UR industrial adapter can use a file-backed source directory, then add hash lineage evidence after projection/export without weakening validators.

**Tech Stack:** Python 3.11+, pytest, JSON/JSONL, SHA-256, existing RDF proof/export/trainer scripts.

---

### Task 1: RED Tests

**Files:**
- Modify: `apps/api/tests/test_mvp1plus_embodiment_proof_script.py`

- [ ] Add a failing test that proves the default UR industrial source is repo-local file-backed.
- [ ] Add a failing test that proves `--ur-recorded-log-dir`/builder parameter overrides the UR source directory.
- [ ] Add a failing test that proves source and projected artifact SHA-256 lineage appears in buyer/proof artifacts.

### Task 2: Source Fixture

**Files:**
- Create: `fixtures/mvp1plus/universal_robots_ur_recorded_log_fixture/metadata.json`
- Create: `fixtures/mvp1plus/universal_robots_ur_recorded_log_fixture/accepted_command_state.jsonl`
- Create: `fixtures/mvp1plus/universal_robots_ur_recorded_log_fixture/rejected_command_state.jsonl`

- [ ] Add a claim-safe UR recorded-log fixture with `source_type=file_backed_recorded_log_fixture`.
- [ ] Keep all non-claim fields false.

### Task 3: Script Implementation

**Files:**
- Modify: `scripts/run_mvp1plus_embodiment_proof.py`

- [ ] Add `DEFAULT_UR_RECORDED_LOG_DIR`.
- [ ] Add `_copy_source_logs()` and source selection for `universal_robots_ur_industrial_arm`.
- [ ] Add `ur_recorded_log_dir` parameter to `build_mvp1plus_embodiment_proof()`.
- [ ] Add `--ur-recorded-log-dir` CLI option.
- [ ] Add source/projected SHA-256 lineage helpers.
- [ ] Attach lineage to contract evidence, proof, adapter summary, and buyer summary.

### Task 4: Verification And Docs

**Files:**
- Modify: `docs/developer/data_schema.md`
- Modify: `docs/developer/debugging_guide.md`
- Modify: `docs/developer/worklog.md`
- Modify: `tasks/todo.md`
- Modify: `Handoff.md`

- [ ] Run targeted tests and proof scripts.
- [ ] Run compileall, ruff, focused ruff, and `git diff --check`.
- [ ] Update developer docs and handoff with the new UR file-backed lineage path.
