# ForgeXR / RDF Data Trust Layer Reset - 2026-06-04

## Plan

Goal: implement the approved ralplan consensus in
`.omx/plans/ralplan-forgexr-data-trust-layer-reset-consensus.md`.

Primary product reset:

- RDF / ForgeXR is a buyer-trustable robot data trust layer first.
- The first reset proof is HMD-free.
- Quest/OpenXR/HMD remains preserved as an experimental input adapter.
- This task must not claim HMD readiness, Gate A readiness, physical collection
  readiness, or policy uplift.

## Ultragoal Stories

- [x] G001: Map existing HMD-free proof/export/trainer surfaces and set the
  active checklist.
- [x] G002: Implement `scripts/run_data_trust_layer_proof.py` with HMD-free
  accepted/rejected fixtures and generated buyer-trust artifacts.
- [x] G003: Add acceptance and guard tests for trust record, action semantics,
  no-HMD claims, export, trainer smoke, and governance docs.
- [x] G004: Reposition README, AGENTS.md, project instructions, Handoff, and
  WORKLOG around the data trust layer reset.
- [x] G005: Run final acceptance, cleanup, and independent review gate.

## G001 Findings

- Existing reusable proof surface:
  `scripts/run_mvp1_offline_readiness.py`.
- Existing trainer-loader smoke:
  `scripts/run_mvp1_trainer_smoke.py`.
- Existing export/inspection helpers:
  `scripts/export_rdf_to_hdf5.py` and `scripts/inspect_rdf_hdf5.py`.
- Existing service surfaces:
  `app.services.evaluator`, `app.services.curator`,
  `app.services.dataset_card`.
- Current risk to fix in the new proof lane:
  `run_mvp1_offline_readiness.py` still uses Quest/OpenXR-like source metadata
  and action representations even though the fixtures are synthetic/offline.
  The reset proof must normalize primary source and buyer-visible action
  semantics separately rather than reusing those labels directly.

## Verification Plan

Targeted:

```text
uv run pytest apps/api/tests/test_data_trust_layer_proof_script.py -q
uv run pytest apps/api/tests/test_mvp1_trainer_smoke_script.py apps/api/tests/test_mvp1_proof_audit_script.py -q
uv run python scripts/run_data_trust_layer_proof.py --clean --pretty
```

Static:

```text
uv run python -m compileall -q scripts apps/api/app apps/api/tests
uvx ruff check scripts/run_data_trust_layer_proof.py apps/api/tests/test_data_trust_layer_proof_script.py
git diff -- scripts/run_hmd_axis_debug.sh scripts/run_live_rdf_smoke_test.sh scripts/run_gate0_xr_input_viability.py
```

Expected HMD runtime default guard: no diff in live/HMD runtime scripts unless
only documentation comments changed.

## Review

Implemented:

- Added `scripts/run_data_trust_layer_proof.py`.
- Added `apps/api/tests/test_data_trust_layer_proof_script.py`.
- Updated README, AGENTS.md, project instructions, Handoff, and WORKLOG to make
  data trust layer the primary proof path and keep Quest/OpenXR/HMD as an
  experimental input adapter.
- Generated proof artifacts in `storage/data_trust_layer_proof`.
- Addressed final review blockers:
  - Removed inherited `Isaac/Quest synthetic teleoperation` wording from the
    generated data trust dataset card.
  - Switched default generated artifact paths to repo-relative paths.
  - Added `legacy_schema_field_mapping` so `raw_xr_*` HDF5/trainer field names
    are explicitly compatibility observation fields, not HMD/Gate A evidence.

Current verification:

```text
uv run python scripts/run_data_trust_layer_proof.py --clean --pretty
  passed=true, accepted_count=4, rejected_count=4

uv run pytest apps/api/tests/test_data_trust_layer_proof_script.py -q
  9 passed

uv run pytest apps/api/tests/test_mvp1_trainer_smoke_script.py apps/api/tests/test_mvp1_proof_audit_script.py -q
  7 passed

uv run python -m compileall -q scripts apps/api/app apps/api/tests
  PASS

uvx ruff check scripts/run_data_trust_layer_proof.py apps/api/tests/test_data_trust_layer_proof_script.py
  All checks passed

claim inspection
  data_trust_claim_inspection_ok

git diff --check on task-owned files
  PASS

independent code review
  code-reviewer: APPROVE
  architect: CLEAR
```

Known verification gap:

- HMD runtime default diff guard is not empty because the worktree already had
  live/HMD script modifications before this reset task. This task did not edit
  those scripts.
- `.omx/ultragoal` CLI checkpoint state remains stale at G001 because the
  Codex goal tool still exposes a previous completed aggregate goal and cannot
  clear it from this session. Implementation evidence is preserved in repo
  files, generated artifacts, tests, review results, and ultragoal ledger notes.

## Documentation Addendum - LinkedIn/docs reset summary

Goal: create a buyer-facing HTML document explaining how the LinkedIn MVP-1 and
Gate 0 lessons changed the repo narrative and proof path.

- [x] Use `docs/buyer/social_narrative.md`, README, project instructions,
  WORKLOG, and Handoff as evidence.
- [x] Add `docs/buyer/data_trust_layer_reset.html`.
- [x] Link the new reset summary from `docs/index.html`.
- [x] Validate HTML links/content and update the final verification record.

Verification:

```text
python3 HTML parser/link/content validation
  docs/buyer/data_trust_layer_reset.html: ok, links=15
  docs/index.html: ok, links=14

git diff --check -- docs/buyer/data_trust_layer_reset.html docs/index.html docs/developer/worklog.md Handoff.md tasks/todo.md
  PASS
```

## Documentation Reorganization - portal and physical file move

Goal: make root `index.html` the public portal and physically classify docs into
buyer, developer, HMD experiment, and archive sections.

- [x] Write design spec at
  `docs/superpowers/specs/2026-06-04-docs-portal-reorganization-design.md`.
- [x] Write implementation plan at
  `docs/superpowers/plans/2026-06-04-docs-portal-reorganization.md`.
- [x] Add root `index.html`.
- [x] Replace `docs/index.html` with an audience-routed docs hub.
- [x] Move buyer-facing docs to `docs/buyer/`.
- [x] Move developer contracts, worklog, and papers to `docs/developer/`.
- [x] Move HMD/Gate 0 adapter history to `docs/experiments/hmd/`.
- [x] Move older MVP/planning/release material to `docs/archive/`.
- [x] Validate all HTML repo-local links and stale references.
- [x] Record final verification in worklog and Handoff.

Verification:

```text
HTML local link validation
  validated_html_files=18

Markdown link validation for README/tasks/Handoff/current docs
  validated_markdown_files=6

Papers relocation check
  docs/papers absent
  docs/developer/papers/README.md present

Stale current-facing reference scan
  no stale reset/social/project/papers paths in current-facing docs

git diff --check -- index.html docs Handoff.md README.md tasks/todo.md
  PASS
```

## Documentation Addendum - HMD-free test execution guide

Goal: explain to the user how tests should be run now that the default proof no
longer depends on OpenXR, ALVR, SteamVR, Quest handtracking, or Isaac Sim GUI.

- [x] Add `docs/developer/hmd_free_test_execution_guide.html`.
- [x] Explain when to use HMD-free proof tests, API tests, web tests, and HMD
  adapter physical validation.
- [x] State that Isaac/HMD is not the default proof path and Gate A collection
  remains blocked until physical HMD Gate 0 passes.
- [x] Link the guide from `docs/index.html` and `docs/developer/index.html`.
- [x] Validate HTML/Markdown links and whitespace after this addendum.

Verification:

```text
HTML local link validation
  validated_html_files=19

Markdown link validation for README/tasks/Handoff/current docs/HMD experiment docs
  validated_markdown_files=20

Stale moved-path scan
  no stale docs-link script placeholder, old buyer storage href, or old recenter local-link references

git diff --check -- index.html docs Handoff.md README.md tasks/todo.md
  PASS

uv run python scripts/run_data_trust_layer_proof.py --clean --pretty
  passed=true, accepted_count=4, rejected_count=4
  trainer_smoke_passed=true, hdf5_inspection_clean=true
```
