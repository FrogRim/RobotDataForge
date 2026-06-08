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

## MVP-1+ Robot Embodiment Adapter Proof - 2026-06-08

Goal: prove that multiple recorded/log-backed robot embodiment adapters can emit
the same normalized trajectory contract and pass the same data trust layer
without claiming real robot runtime support or policy uplift.

- [x] Restore Ultragoal plan in `.omx/ultragoal/`.
- [x] Add `AdapterContractEmitter`, `ContractBuilder`, and
  `NormalizedTrajectoryContractValidator` service boundaries.
- [x] Add static robot embodiment adapter registry.
- [x] Represent `Franka`, `ROBOTIS SH5 / ROS2-DDS`, `Universal Robots UR`, and
  generated external-style UR.
- [x] Generate adapter source evidence as `JSONL + metadata JSON`.
- [x] Project source logs into RDF-compatible trajectory/evaluation/curation
  inputs.
- [x] Emit normalized trajectory contracts through adapter + builder path.
- [x] Require preprojected inputs for contract emission; no internal
  re-projection fallback is allowed after export/trainer artifacts exist.
- [x] Keep default robot embodiment adapter contract identity aligned with the
  MVP-1+ proof id and contract name.
- [x] Reject cross-adapter projected artifact mixes by validating accepted and
  rejected trajectory/evaluation/curation/split/projection links.
- [x] Preserve projected recorded-log `source_profile`; keep builder static
  source profile under adapter evidence only.
- [x] Generate accepted and rejected artifacts with complete rejection reasons.
- [x] Export per-adapter and integrated HDF5 artifacts.
- [x] Pass trainer smoke for per-adapter and integrated exports.
- [x] Add buyer-readable `mvp1plus_buyer_summary.json`.
- [x] Add safe `--clean` guard and regression test for unsafe output paths.
- [x] Preserve original MVP-1 proof script compatibility.
- [x] Run final cleanup scan and independent code-review/architect gate.
- [x] Checkpoint Ultragoal final story.

Verification so far:

```text
uv run pytest apps/api/tests/test_mvp1plus_embodiment_proof_script.py -q
  16 passed

uv run pytest apps/api/tests/test_data_trust_layer_proof_script.py -q
  9 passed

uv run pytest apps/api/tests/test_mvp1_proof_audit_script.py apps/api/tests/test_mvp1c_real_policy_eval_script.py -q
  8 passed

uv run python scripts/run_mvp1plus_embodiment_proof.py --clean --pretty
  passed=true, adapter_count=4, accepted_count=4, rejected_count=4
  rejection_reason_coverage_passed=true
  integrated hdf5/export/trainer gates pass
  normalized contract proof_id is rdf_mvp1plus_cross_embodiment_recorded_log_adapter_proof_v0
  all adapter emissions use preprojected inputs

uv run python scripts/run_data_trust_layer_proof.py --clean --pretty
  passed=true, accepted_count=4, rejected_count=4

uv run python -m compileall -q scripts apps/api/app apps/api/tests
  PASS

uvx ruff check scripts/run_mvp1plus_embodiment_proof.py scripts/run_data_trust_layer_proof.py apps/api/app apps/api/tests
  All checks passed

git diff --check
  PASS
```

Final review gate:

```text
code-reviewer: APPROVE
architect: CLEAR
prior blockers: closed
ultragoal: G001 complete, artifactComplete=true
```

## MVP-1+ UR File-Backed Lineage Hardening - 2026-06-08

Goal: strengthen MVP-1+ confidence by proving the UR industrial-arm adapter can
start from a repo-local file-backed recorded-log fixture, not only in-script
generated rows, and preserve hash lineage into buyer/proof artifacts.

- [x] Add claim-safe UR recorded-log fixture under
  `fixtures/mvp1plus/universal_robots_ur_recorded_log_fixture/`.
- [x] Make `universal_robots_ur_industrial_arm` use the repo-local fixture by
  default.
- [x] Add `--ur-recorded-log-dir` and `ur_recorded_log_dir` build parameter for
  custom UR recorded/log source directories.
- [x] Preserve the same normalized trajectory contract and validator gates.
- [x] Add source file SHA-256 and projected artifact SHA-256 lineage evidence.
- [x] Attach lineage evidence to adapter proof, normalized contract evidence,
  summary, and buyer summary.
- [x] Keep claims bounded: no live UR/RTDE runtime, no physical UR readiness, no
  real robot success, no policy uplift.
- [x] Update data schema, debugging guide, worklog, tasks, and Handoff.

Verification:

```text
uv run pytest apps/api/tests/test_mvp1plus_embodiment_proof_script.py -q
  19 passed

uv run pytest apps/api/tests/test_data_trust_layer_proof_script.py -q
  9 passed

uv run pytest apps/api/tests/test_mvp1_proof_audit_script.py apps/api/tests/test_mvp1c_real_policy_eval_script.py -q
  8 passed

uv run python scripts/run_mvp1plus_embodiment_proof.py --clean --pretty
  passed=true, adapter_count=4, accepted_count=4, rejected_count=4
  UR lineage source_evidence_type=file_backed_recorded_log_fixture

uv run python scripts/run_data_trust_layer_proof.py --clean --pretty
  passed=true, accepted_count=4, rejected_count=4

uv run python -m compileall -q scripts apps/api/app apps/api/tests
  PASS

uvx ruff check scripts/run_mvp1plus_embodiment_proof.py scripts/run_data_trust_layer_proof.py apps/api/app apps/api/tests
  All checks passed

uvx ruff check --select F401,F841,PLR0912,PLR0915,C901 scripts/run_mvp1plus_embodiment_proof.py apps/api/app/services/robot_embodiment_adapters.py apps/api/tests/test_mvp1plus_embodiment_proof_script.py
  All checks passed

git diff --check
  PASS
```

Next confidence step:

- [ ] Feed a captured or externally converted UR recorded/log directory through
  `--ur-recorded-log-dir` without adding live UR runtime control.
- [ ] Extend the same file-backed lineage pattern to Franka and ROBOTIS if
  stronger cross-embodiment buyer evidence is needed before MVP-2.

## MVP-2 Rebase UR Policy A/B Harness Spec - 2026-06-08

Goal: rebase MVP-2 from legacy `MVP-1C` / HUD-first policy-uplift execution
into the new MVP-1/MVP-1+ adapter-emitted contract lineage.

- [x] Select first MVP-2 proof source:
  `universal_robots_ur_industrial_arm` file-backed recorded log.
- [x] Select first slice scope:
  Rebase spec + offline policy A/B harness.
- [x] Preserve legacy `mvp1c_*` scripts as compatibility surfaces.
- [x] Define new `mvp2_*` primary artifact/entrypoint direction.
- [x] Use schema-only rollout ingest fixture for contract validation, not policy
  evidence.
- [x] Define primary `mvp2_policy_ab_harness_report.json` plus proof audit
  summary integration.
- [x] Write design spec:
  `docs/superpowers/specs/2026-06-08-mvp2-rebase-ur-policy-ab-harness-design.md`
- [x] User review of the written spec and approval to continue.
- [x] Write implementation plan:
  `docs/superpowers/plans/2026-06-08-mvp2-rebase-ur-policy-ab-harness.md`
- [x] `$ultragoal` implementation execution from the written plan.
- [x] Add `scripts/run_mvp2_ur_policy_ab_harness.py`.
- [x] Add MVP-2 UR harness TDD coverage.
- [x] Add MVP-2 UR harness safe-clean guard regression coverage.
- [x] Resolve final architect WATCH items:
  non-comparative schema fixture, UR file-backed lineage gate, no-clean stale reset.
- [x] Resolve final code-review findings:
  exact lineage key/hash/path binding and gate-derived harness readiness.
- [x] Add proof audit `mvp2_policy_ab_harness` readiness summary.
- [x] Generate MVP-2 harness artifacts under `storage/mvp2_policy_ab_harness/`.
- [x] Preserve boundary:
  `learning_results_measured=false`, `learning_proven=false`,
  `proof_eligible=false`, no policy uplift claim.
- [x] Update data schema, debugging guide, worklog, tasks, and Handoff.

Verification:

```text
uv run pytest apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py -q
  9 passed

uv run pytest apps/api/tests/test_mvp1plus_embodiment_proof_script.py -q
  19 passed

uv run pytest apps/api/tests/test_mvp1_proof_audit_script.py apps/api/tests/test_mvp1c_real_policy_eval_script.py -q
  9 passed

uv run pytest apps/api/tests/test_mvp1c_headless_eval_bundle_script.py apps/api/tests/test_mvp1c_rollout_result_adapter_script.py -q
  5 passed

uv run pytest apps/api/tests/test_data_trust_layer_proof_script.py -q
  9 passed

uv run python scripts/run_mvp2_ur_policy_ab_harness.py --clean --refresh-mvp1plus --pretty
  passed=true, harness_ready=true, rollout_ingest_contract_ready=true

uv run python scripts/run_mvp1plus_embodiment_proof.py --clean --pretty
  passed=true, adapter_count=4, accepted_count=4, rejected_count=4

uv run python scripts/run_data_trust_layer_proof.py --clean --pretty
  passed=true, accepted_count=4, rejected_count=4

uv run python -m compileall -q scripts apps/api/app apps/api/tests
  PASS

uvx ruff check scripts/run_mvp2_ur_policy_ab_harness.py scripts/run_mvp1_proof_audit.py apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py apps/api/tests/test_mvp1_proof_audit_script.py
  All checks passed!

git diff --check
  PASS
```

Next MVP-2 gap:

- [ ] Ingest real held-out rollout results.
- [ ] Select actual trainer/policy class for baseline and candidate.
- [ ] Run real curated-vs-uncurated policy A/B.
- [ ] Record positive or negative learning-proven result report.
