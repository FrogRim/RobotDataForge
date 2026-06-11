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

## 2026-06-09 - MVP-2A transition / policy readiness

Status: closed for MVP-2 learning-proven uplift. This does not claim real robot
success, physical UR readiness, Isaac runtime success, or HMD/OpenXR readiness.

- [x] Add plan:
  `docs/superpowers/plans/2026-06-09-mvp2a-transition-policy-readiness.md`.
- [x] Extend phase extraction to support `command_state_row.task_phase`.
- [x] Generate candidate view `curation_manifest.json` and `split_manifest.json`
  from the UR harness.
- [x] Run `run_mvp2_learning_sanity.py` from
  `run_mvp2_ur_policy_ab_harness.py`.
- [x] Generate
  `storage/mvp2_policy_ab_harness/mvp2a_transition_policy_readiness_report.json`.
- [x] Include MVP-2A readiness summary in
  `storage/mvp2_policy_ab_harness/mvp2_policy_ab_harness_report.json`.
- [x] Surface MVP-2A blocker in `run_mvp1_proof_audit.py`.
- [x] Build or ingest transition-rich UR train material with
  `APPROACH`, `CONTACT`, `INSERT`, `SEAT`.
- [x] Select stronger policy/trainer class after transition coverage passes.
- [ ] Re-run proof-grade independent external held-out policy eval with positive
  curated > uncurated uplift.
- [x] Add phase-conditioned local proxy evaluator:
  `scripts/run_mvp2_phase_conditioned_external_eval.py`.
- [x] Generate phase-conditioned proxy artifacts under
  `storage/mvp2_phase_conditioned_local_eval_proxy/`.
- [x] Block phase-conditioned local proxy evidence from MVP-2 Closed promotion.
- [x] Merge explicit MVP-2 learning-proven report into proof audit
  `mvp2_policy_uplift_proof` summary.

Current generated readiness:

```text
harness_ready=true
mvp2a_policy_ab_ready=true
stronger_policy_trainer_selected=true
selected_policy_class=phase_conditioned_sequence_bc_policy_v0
selected_trainer=rdf_phase_conditioned_sequence_bc_trainer_contract_v0
next_recommended_gate=external_heldout_policy_rollout_generation
candidate dataset_present_required_phases=["APPROACH", "CONTACT", "INSERT", "SEAT"]
candidate dataset_missing_required_phases=[]
candidate transition_rich_episode_count=1
candidate sample_count=4
candidate train_set_overfit_passed=true
learning_proven=false
```

Phase-conditioned proxy result:

```text
uv run python scripts/run_mvp2_phase_conditioned_external_eval.py --clean --refresh-harness --refresh-mvp1plus --pretty
  passed=true
  mvp2_closed=false
  proxy_results_measured=true
  learning_results_measured=true
  learning_proven=false
  proof_eligible=false
  evidence_tier=local_phase_conditioned_policy_eval_proxy
  validator_evidence_tier=null
  baseline_success_rate=0.4
  candidate_success_rate=0.9
  curated_vs_uncurated_uplift=0.5

uv run python scripts/run_mvp1_proof_audit.py --mvp2-policy-ab-harness-report storage/mvp2_policy_ab_harness/mvp2_policy_ab_harness_report.json --mvp2-learning-proven-report storage/mvp2_phase_conditioned_local_eval_proxy/mvp2_learning_proven_policy_eval/mvp2_learning_proven_report.json --output storage/mvp1_proof/proof_audit.json --pretty
  status=partial
  staged_current=offline_readiness
  learning_proven_policy_uplift_achieved=false
  mvp2_learning_proven_policy_eval.learning_proven=false
  mvp2_policy_uplift_proof.learning_proven=false
```

The audit remains `partial` for legacy MVP-1 live/XR gates in the default
`storage/mvp1_readiness` path. The explicit phase-conditioned proxy verdict is
not promoted to MVP-2 Closed.

Latest verification:

```text
uv run pytest apps/api/tests/test_mvp2_learning_sanity_script.py apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py apps/api/tests/test_mvp1_proof_audit_script.py -q
  22 passed

uv run pytest apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py apps/api/tests/test_mvp1_proof_audit_script.py apps/api/tests/test_mvp1c_real_policy_eval_script.py -q
  24 passed

uv run python scripts/run_mvp2_ur_policy_ab_harness.py --clean --refresh-mvp1plus --pretty
  harness_ready=true,
  mvp2a_policy_ab_ready=true,
  stronger_policy_trainer_selected=true,
  selected_policy_class=phase_conditioned_sequence_bc_policy_v0,
  selected_trainer=rdf_phase_conditioned_sequence_bc_trainer_contract_v0,
  next_recommended_gate=external_heldout_policy_rollout_generation

uv run python scripts/run_mvp1_proof_audit.py --mvp2-policy-ab-harness-report storage/mvp2_policy_ab_harness/mvp2_policy_ab_harness_report.json --pretty
  mvp2a_policy_ab_ready=true,
  stronger_policy_trainer_selected=true,
  mvp2a_next_recommended_gate=external_heldout_policy_rollout_generation,
  candidate_transition_coverage_passed=true,
  candidate_train_set_overfit_passed=true,
  legacy_stronger_gate=true,
  learning_proven_policy_uplift_achieved=false

uv run python scripts/run_mvp2_learning_proven_policy_eval.py --clean --refresh-harness --refresh-mvp1plus --pretty
  learning_proven=false,
  proof_eligible=false,
  evidence_tier=local_offline_policy_eval_proxy

uv run python -m compileall -q scripts apps/api/app apps/api/tests
  PASS

uvx ruff check scripts/run_mvp2_learning_sanity.py scripts/run_mvp2_ur_policy_ab_harness.py scripts/run_mvp1_proof_audit.py apps/api/tests/test_mvp2_learning_sanity_script.py apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py apps/api/tests/test_mvp1_proof_audit_script.py scripts/run_mvp2_learning_proven_policy_eval.py apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py
  All checks passed

git diff --check
  PASS
```

Transition-rich ingest verification:

```text
uv run python scripts/run_mvp1plus_embodiment_proof.py --clean --pretty
  passed=true,
  UR accepted trajectory frames=4,
  phases=["APPROACH", "CONTACT", "INSERT", "SEAT"]

uv run pytest apps/api/tests/test_mvp1plus_embodiment_proof_script.py apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py apps/api/tests/test_mvp2_learning_sanity_script.py apps/api/tests/test_mvp1_proof_audit_script.py -q
  41 passed

uv run pytest apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py apps/api/tests/test_mvp1c_real_policy_eval_script.py apps/api/tests/test_data_trust_layer_proof_script.py -q
  24 passed
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

## MVP-2 Closed Positive Uplift Ralplan - 2026-06-08

Goal: implement MVP-2 Closed as a bounded local offline held-out policy A/B
wrapper where curated UR data beats uncurated UR data and the existing policy
eval validator reports `proof_eligible=true`.

- [x] Write PRD:
  `.omx/plans/prd-mvp2-learning-proven-policy-uplift.md`
- [x] Write test spec:
  `.omx/plans/test-spec-mvp2-learning-proven-policy-uplift.md`
- [x] Write implementation plan:
  `docs/superpowers/plans/2026-06-08-mvp2-learning-proven-policy-uplift.md`
- [x] Fix Architect/Critic blocker: local offline proof must overwrite
  `policy_eval_payload["eval_suite"]` before `run_real_policy_eval()`.
- [x] Add planned regression assertions that both policy eval input and policy
  eval report reference `mvp2_local_offline_heldout_suite_manifest.json`, not
  the harness schema-only suite.
- [x] Complete Architect review: `APPROVE`.
- [x] Complete Critic review: `APPROVE`.
- [x] Persist consensus handoff:
  `.omx/plans/ralplan-consensus-mvp2-learning-proven-policy-uplift.md`
- [x] Execute with `$ultragoal`.

Required implementation boundaries:

- [x] Do not weaken `run_mvp1c_real_policy_eval.py`.
- [x] Do not promote schema-only rollout fixtures into proof-grade policy
  evidence.
- [x] Preserve MVP-1 `policy_uplift_required_for_mvp1=false`.
- [x] Do not introduce live UR/RTDE runtime, physical robot readiness, HMD
  readiness, DB migration, marketplace, VLA, or World Model scope.

Required verification after implementation:

```text
uv run pytest apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py -q
uv run pytest apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py -q
uv run pytest apps/api/tests/test_mvp1plus_embodiment_proof_script.py -q
uv run pytest apps/api/tests/test_mvp1_proof_audit_script.py apps/api/tests/test_mvp1c_real_policy_eval_script.py -q
uv run pytest apps/api/tests/test_data_trust_layer_proof_script.py -q
uv run python scripts/run_mvp2_learning_proven_policy_eval.py --clean --refresh-harness --pretty
uv run python scripts/run_mvp2_ur_policy_ab_harness.py --clean --refresh-mvp1plus --pretty
uv run python scripts/run_mvp1plus_embodiment_proof.py --clean --pretty
uv run python scripts/run_data_trust_layer_proof.py --clean --pretty
uv run python -m compileall -q scripts apps/api/app apps/api/tests
uvx ruff check scripts apps/api/app apps/api/tests
git diff --check
```

Implementation result after review correction:

- [x] Add `scripts/run_mvp2_learning_proven_policy_eval.py`.
- [x] Add local offline proxy rollout generation.
- [x] Keep local offline deterministic proxy from closing MVP-2.
- [x] Add schema-only, schema-like, local proxy, and missing provenance
  pre-validator blockers.
- [x] Preserve external rollout ingest path, metadata passthrough, and external
  held-out suite provenance.
- [x] Call the held-out policy validator only for
  `evidence_tier=external_heldout_policy_eval`.
- [x] Generate `mvp2_learning_proven_report.json`.
- [x] Add proof audit `mvp2_learning_proven_policy_eval` summary.
- [x] Require explicit `--mvp2-learning-proven-report` before proof audit reads
  MVP-2 learning-proven evidence.
- [x] Preserve MVP-1/MVP-2 boundary:
  `policy_uplift_required_for_mvp1=false`.
- [x] Add external proof package template generation for real held-out rollout
  JSON handoff.
- [x] Keep unfilled external proof templates from closing MVP-2 or reaching the
  held-out policy validator.

Current generated default artifact:

```text
storage/mvp2_learning_proven_policy_eval/mvp2_learning_proven_report.json
learning_results_measured=true
learning_proven=false
proof_eligible=false
evidence_tier=local_offline_policy_eval_proxy
validator_evidence_tier=null
baseline_success_rate=0.7
candidate_success_rate=1.0
curated_vs_uncurated_uplift=0.30000000000000004
blocker=Local offline deterministic proxy cannot close MVP-2.
```

MVP-2 Closed status:

- [ ] Pending external proof-grade held-out policy eval rollout results.
- [x] External proof template package is ready at
  `storage/mvp2_learning_proven_policy_eval/external_policy_eval_template/`.
- [x] Schema-only external held-out `scenario_ids` are blocked before validator.
- [x] Actual Isaac headless smoke was attempted against the current MVP-2 harness
  HDF5 and did not produce positive uplift:
  baseline_success_rate=0.0, candidate_success_rate=0.0.
- [x] Wrapper and proof audit are ready to close MVP-2 only when those results
  pass the existing held-out policy validator with positive curated >
  uncurated uplift.

Final verification:

```text
uv run pytest apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py -q
  12 passed

uv run pytest apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py -q
  9 passed

uv run pytest apps/api/tests/test_mvp1plus_embodiment_proof_script.py -q
  19 passed

uv run pytest apps/api/tests/test_mvp1_proof_audit_script.py apps/api/tests/test_mvp1c_real_policy_eval_script.py -q
  11 passed

uv run pytest apps/api/tests/test_data_trust_layer_proof_script.py -q
  9 passed

uv run python scripts/run_mvp2_learning_proven_policy_eval.py --clean --refresh-harness --refresh-mvp1plus --pretty
  passed=true, learning_results_measured=true, learning_proven=false,
  proof_eligible=false, evidence_tier=local_offline_policy_eval_proxy

uv run python scripts/run_mvp2_ur_policy_ab_harness.py --clean --refresh-mvp1plus --pretty
  passed=true, harness_ready=true, learning_proven=false

uv run python scripts/run_mvp1plus_embodiment_proof.py --clean --pretty
  passed=true, issues=[]

uv run python scripts/run_data_trust_layer_proof.py --clean --pretty
  passed=true, accepted_count=4, rejected_count=4

uv run python -m compileall -q scripts apps/api/app apps/api/tests
  PASS

uvx ruff check scripts apps/api/app apps/api/tests
  All checks passed

git diff --check
  PASS
```

Fresh verification for external proof template package:

```text
uv run python scripts/run_mvp2_learning_proven_policy_eval.py --write-external-proof-template --clean --refresh-harness --refresh-mvp1plus --pretty
  passed=true, proof_ready=false, mvp2_closed=false,
  template_is_not_evidence=true,
  heldout_suite.scenario_ids=["TODO_external_heldout_scenario_00"]

/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp1c_isaac_policy_ab_smoke.py --baseline-hdf5 storage/mvp2_policy_ab_harness/baseline_uncurated/baseline_uncurated_train.hdf5 --candidate-hdf5 storage/mvp2_policy_ab_harness/candidate_curated/candidate_curated_train.hdf5 --template storage/mvp2_policy_ab_harness/mvp2_policy_eval_input_template.json --output-dir /tmp/rdf-mvp2-isaac-rollout-check --rollouts-per-policy 10 --max-steps 150 --seed-start 9100 --action-scale 1.0 --evidence-tier isaac_headless_policy_eval_smoke --pretty
  passed=true, evidence_tier=isaac_headless_policy_eval_smoke,
  proof_eligible=false, baseline_success_rate=0.0,
  candidate_success_rate=0.0

/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp1c_isaac_policy_ab_smoke.py --baseline-hdf5 storage/mvp2_policy_ab_harness/baseline_uncurated/baseline_uncurated_train.hdf5 --candidate-hdf5 storage/mvp2_policy_ab_harness/candidate_curated/candidate_curated_train.hdf5 --template storage/mvp2_policy_ab_harness/mvp2_policy_eval_input_template.json --output-dir /tmp/rdf-mvp2-isaac-rollout-action-scale20-check --rollouts-per-policy 2 --max-steps 150 --seed-start 9300 --action-scale 20 --evidence-tier isaac_headless_policy_eval_smoke --pretty
  passed=true, evidence_tier=isaac_headless_policy_eval_smoke,
  proof_eligible=false, baseline_success_rate=0.0,
  candidate_success_rate=0.0

uv run python scripts/run_mvp2_learning_proven_policy_eval.py --output-dir /tmp/rdf-mvp2-template-reject --clean --baseline-results storage/mvp2_learning_proven_policy_eval/external_policy_eval_template/baseline_external_rollouts.template.json --candidate-results storage/mvp2_learning_proven_policy_eval/external_policy_eval_template/candidate_external_rollouts.template.json --pretty
  passed=true, learning_results_measured=false, learning_proven=false,
  proof_eligible=false, validator_evidence_tier=null,
  artifact_paths.policy_eval_report=null

uv run pytest apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py apps/api/tests/test_mvp1_proof_audit_script.py apps/api/tests/test_mvp1c_real_policy_eval_script.py -q
  24 passed

uv run pytest apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py -q
  9 passed

uv run python -m compileall -q scripts apps/api/app apps/api/tests
  PASS

uvx ruff check scripts/run_mvp2_learning_proven_policy_eval.py apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py scripts/run_mvp1_proof_audit.py apps/api/tests/test_mvp1_proof_audit_script.py
  All checks passed

git diff --check
  PASS
```

Fresh verification for phase-conditioned local proxy blocker:

```text
uv run python scripts/run_mvp2_phase_conditioned_external_eval.py --clean --refresh-harness --refresh-mvp1plus --pretty
  passed=true, mvp2_closed=false, learning_proven=false,
  proof_eligible=false, evidence_tier=local_phase_conditioned_policy_eval_proxy,
  validator_evidence_tier=null

uv run python scripts/run_mvp1_proof_audit.py --mvp2-policy-ab-harness-report storage/mvp2_policy_ab_harness/mvp2_policy_ab_harness_report.json --mvp2-learning-proven-report storage/mvp2_phase_conditioned_local_eval_proxy/mvp2_learning_proven_policy_eval/mvp2_learning_proven_report.json --output storage/mvp1_proof/proof_audit.json --pretty
  learning_proven_policy_uplift_achieved=false,
  mvp2_learning_proven_policy_eval.learning_proven=false,
  mvp2_policy_uplift_proof.learning_proven=false

uv run pytest apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py -q
  14 passed

uv run pytest apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py apps/api/tests/test_mvp1_proof_audit_script.py -q
  19 passed

uv run pytest apps/api/tests/test_mvp1c_real_policy_eval_script.py apps/api/tests/test_data_trust_layer_proof_script.py -q
  12 passed

uv run pytest apps/api/tests/test_mvp1plus_embodiment_proof_script.py apps/api/tests/test_mvp2_learning_sanity_script.py -q
  22 passed

uv run python -m compileall -q scripts apps/api/app apps/api/tests
  PASS

uvx ruff check scripts/run_mvp2_phase_conditioned_external_eval.py scripts/run_mvp2_learning_proven_policy_eval.py scripts/run_mvp2_ur_policy_ab_harness.py scripts/run_mvp1_proof_audit.py scripts/run_mvp2_learning_sanity.py apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py apps/api/tests/test_mvp1_proof_audit_script.py apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py apps/api/tests/test_mvp2_learning_sanity_script.py
  All checks passed

git diff --check
  PASS
```

Current MVP-2 Closed status:

- [x] MVP-2A transition-rich UR train material exists.
- [x] Stronger phase-conditioned policy/trainer contract is selected.
- [x] Phase-conditioned local proxy uplift is measured and buyer-readable.
- [x] Phase-conditioned local proxy is blocked from proof promotion.
- [ ] Proof-grade independent external held-out baseline/candidate rollout JSON
  with positive curated > uncurated `policy_success_rate` uplift is still
  missing.

## 2026-06-10 Resume: Next Valid MVP-2B Slice

Current evidence after resume:

- [x] Handoff/worklog/todo were re-read.
- [x] Isaac headless smoke artifacts are present under
  `/tmp/rdf-mvp2-isaac-preflight-headless`.
- [x] Headless smoke report has `passed=true` and `proof_eligible=false`.
- [x] Headless smoke rollout adapter has baseline/candidate success rate `0`.
- [x] Current Isaac smoke policy class is `linear_bc_numpy_isaac_smoke`.
- [x] MVP-2A selected policy contract is
  `phase_conditioned_sequence_bc_policy_v0`.
- [x] MVP-2A selected trainer contract is
  `rdf_phase_conditioned_sequence_bc_trainer_contract_v0`.
- [ ] MVP-2 Closed remains blocked.

Next valid slice:

- [x] Plan `MVP-2B dedicated Isaac proof evaluator`.
- [x] Use a dedicated Isaac connector insertion evaluator rather than promoting
  the existing smoke task or local proxy.
- [x] Implement the consensus-approved MVP-2B deterministic foundation with
  `$ultragoal` artifact-backed execution.
- [x] Keep `isaac_headless_policy_eval_smoke`, deterministic backend, local
  proxy, schema fixture, template artifacts, HMD/OpenXR, and visual-only
  artifacts out of MVP-2 proof promotion.
- [ ] Implement actual `IsaacConnectorInsertionEvaluatorBackend.run()` for
  dedicated connector insertion held-out rollouts.

## 2026-06-10 MVP-2B Brainstorming: Isaac Proof Evaluator

Current design decisions:

- [x] Use `A3 Hybrid staged path`.
- [x] Keep existing Isaac task as smoke/sanity only.
- [x] Use a dedicated Isaac physics-based connector insertion evaluator scene
  for MVP-2 proof attempts.
- [x] Fix success metric as geometry + stability:
  insertion depth, lateral error, orientation error, and consecutive stable
  steps.
- [x] Pre-register `scenario_manifest.json` before training or evaluation.
- [x] Split scenarios by seed, initial offset, and noise level.
- [x] Keep held-out scenarios completely excluded from training and curation
  tuning.
- [x] Generate primary training data in the Isaac evaluator domain.
- [x] Use `scripted expert + controlled noise/failure` as primary trajectory
  generation.
- [x] Keep operator demo as auxiliary visual/UX validation evidence only.
- [x] Use NumPy phase-conditioned BC for policy/trainer.
- [x] Give baseline and candidate identical phase inputs, trainer,
  hyperparameters, features, and held-out scenarios.
- [x] Close MVP-2 only with practical effect size:
  candidate > baseline, uplift >= 20 percentage points, and at least 20
  held-out rollouts per policy.
- [x] Treat bootstrap CI lower bound > 0 as a later strengthening gate, not the
  initial MVP-2 Closed blocker.
- [x] Save design spec at
  `docs/superpowers/specs/2026-06-10-mvp2b-isaac-proof-evaluator-design.md`.

Next step:

- [x] User approved the MVP-2B design direction.
- [x] Write the dedicated Isaac evaluator implementation plan that supersedes
  preliminary `docs/superpowers/plans/2026-06-10-mvp2b-proof-grade-evaluator-bridge.md`.
- [x] Complete ralplan consensus gate.
  - Architect: APPROVE
  - Critic: APPROVE
  - Consensus handoff:
    `.omx/plans/ralplan-consensus-mvp2b-isaac-proof-evaluator.md`
- [x] Run `$ultragoal` from the approved MVP-2B plan.
  - Implementation and verification completed.
  - Final Ultragoal checkpoint is terminal `failed` because the existing Codex
    goal snapshot is already `complete` from a prior aggregate run and the
    final independent code-review gate could not be reconciled in this thread.

MVP-2B execution invariants:

- [x] Deterministic/skipped/proxy/smoke/HMD/visual-only evidence must never set
  top-level `mvp2_closed=true` or `proof_eligible=true`.
- [x] MVP-2B closure requires `runtime_backend=isaac_runtime`,
  `proof_runtime=dedicated_isaac_connector_insertion_evaluator`, existing proof
  evaluator pass, candidate > baseline, and uplift >= 0.20.
- [x] Held-out results must not drive threshold changes in the same manifest
  version.

## 2026-06-10 MVP-2B Ultragoal Implementation Checkpoint

- [x] Ultragoal artifact regenerated from approved MVP-2B plan.
- [x] Completed Codex goal blocker recorded in `.omx/ultragoal/ledger.jsonl`.
- [x] Added red tests for scenario manifest, leak guard, metric, trajectory
  contract, HDF5 train views, policy parity, rollout JSON, runtime gate, HMD
  boundary, and visual evidence.
- [x] Added `scripts/run_mvp2b_isaac_proof_evaluator.py`.
- [x] Pre-registered scenario manifest writes deterministic train/calibration/
  held-out split and `manifest_sha256`.
- [x] Held-out leakage and threshold-freeze guards implemented.
- [x] Generated scripted expert and controlled failure train trajectories.
- [x] Generated contracts pass `NormalizedTrajectoryContractValidator`.
- [x] Baseline uncurated / candidate curated HDF5 train views generated.
- [x] Shared NumPy phase-conditioned BC policy artifacts generated.
- [x] Deterministic backend writes proof-grade rollout JSON shape and visual
  evidence, then existing MVP-2 validator ingests it.
- [x] Top-level report keeps deterministic positive uplift non-closing:
  `mvp2_closed=false`, `proof_eligible=false`.
- [x] `--skip-isaac` path remains non-closing.
- [x] Focused tests pass: `19 passed`.
- [x] Existing MVP-2 evaluator compatibility pass: combined `33 passed`.
- [x] Final relevant MVP checks pass: `52 passed`.
- [x] `compileall`, `ruff`, and `git diff --check` pass.
- [x] Ultragoal ledger records final-gate orchestration failure separately from
  implementation/verification success.
- [x] Actual Isaac runtime backend implemented for
  `Isaac-Factory-PegInsert-Direct-v0`.
- [x] Actual Isaac runtime proof attempt generated 40/40 held-out rollout traces.
- [x] Actual Isaac runtime gate passed with
  `runtime_backend=isaac_runtime` and
  `proof_runtime=dedicated_isaac_connector_insertion_evaluator`.
- [ ] MVP-2 Closed still needs positive curated > uncurated held-out uplift.

## 2026-06-10 MVP-2B Actual Isaac Runtime Attempt

- [x] Implemented actual `IsaacConnectorInsertionEvaluatorBackend.run()`.
- [x] Added runtime trace extraction for insertion depth, signed relative offset,
  lateral error, orientation error, phase, and normalized action.
- [x] Added `relative_x_m` and `relative_y_m` to the shared baseline/candidate
  phase-conditioned feature schema.
- [x] Fixed closure accounting to use actual rollout count, not only requested
  `--rollouts-per-policy`.
- [x] Marked actual Isaac visual evidence as
  `visual_evidence_source=isaac_runtime_capture`.
- [x] Ran actual Isaac proof attempt:

```text
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2b_isaac_proof_evaluator.py \
  --output-dir /tmp/rdf-mvp2b-isaac-runtime-signed-offset-step150-scale20 \
  --clean \
  --rollouts-per-policy 20 \
  --max-steps 150 \
  --action-scale 20 \
  --bootstrap-iterations 200 \
  --pretty
```

Actual result:

```text
runtime_backend=isaac_runtime
proof_runtime=dedicated_isaac_connector_insertion_evaluator
runtime_gate.passed=true
actual_rollouts_per_policy=20
baseline_success_rate=0.0
candidate_success_rate=0.0
curated_vs_uncurated_uplift=0.0
mvp2_closed=false
proof_eligible=false
```

Trace diagnosis:

```text
baseline:
  20 rollouts, 0 success
  failure_reason=UNDER_INSERTION_FAILURE for all

candidate:
  20 rollouts, 0 success
  LATERAL_OFFSET_FAILURE=10
  ORIENTATION_MISALIGNMENT_FAILURE=7
  STABILITY_WINDOW_NOT_REACHED=3
  max insertion depth can reach 0.034m, but no stable seating window is achieved
```

Current blocker:

- MVP-2 Closed is blocked by actual non-positive held-out uplift.
- Do not lower thresholds or retune against the same held-out manifest.
- Next valid technical milestone is a new pre-registered training/calibration
  slice: Isaac-runtime scripted expert train data plus calibration-only action
  adapter selection, then a fresh held-out run.

## 2026-06-11 MVP-2C Training / Calibration Slice Spec

- [x] Wrote MVP-2C spec:
  `docs/superpowers/specs/2026-06-11-mvp2c-isaac-training-calibration-slice-design.md`
- [x] Fixed new manifest boundary:
  `rdf_mvp2c_scenario_manifest_v0.1.0`
- [x] Fixed new split:
  - `train_success`: seeds `4000-4079`
  - `train_failure`: seeds `4100-4179`
  - `calibration`: seeds `5000-5019`
  - `held_out`: seeds `6000-6019`
- [x] Explicitly banned reusing MVP-2B held-out seeds `3000-3019` for MVP-2C
  training, calibration, tuning, or closure proof.
- [x] Specified `IsaacRuntimeScriptedExpertDataGenerator`.
- [x] Specified `ActionAdapterCandidateRegistry`.
- [x] Specified `CalibrationOnlyActionAdapterSelector`.
- [x] Specified closure rule requiring actual Isaac runtime gate plus existing
  MVP-2 learning-proven validator.
- [x] Added baseline uncurated mix pre-registration:
  `baseline_noise_mix_ratio`, `accepted_failure_ratio`,
  `failure_type_distribution`, and `noise_profile_config_sha256`.
- [x] Added hash-stable generator config evidence:
  `scripted_expert_config_sha256`, `controlled_failure_config_sha256`, and
  `train_generation_config_sha256`.
- [x] Added calibration selector anti-p-hacking guard:
  `selector_score_pre_registered=true`,
  `same_adapter_used_for_baseline_and_candidate=true`, `heldout_excluded=true`,
  and `selected_adapter_frozen_before_heldout=true`.
- [x] Separated `mvp2c_close_minimum_passed` from
  `stronger_public_evidence_target_passed`.
- [x] Added privileged Isaac task-state feature non-claims:
  `deployable_real_robot_policy=false`, `visual_policy_performance=false`,
  `real_robot_success=false`, `physical_robot_readiness=false`, and
  `universal_robot_support=false`.
- [x] User review / approval of hardened MVP-2C spec.
- [x] After approval, run `$ralplan` for implementation plan.
- [x] Wrote PRD:
  `.omx/plans/prd-mvp2c-isaac-training-calibration.md`
- [x] Wrote test spec:
  `.omx/plans/test-spec-mvp2c-isaac-training-calibration.md`
- [x] Wrote implementation plan:
  `docs/superpowers/plans/2026-06-11-mvp2c-isaac-training-calibration.md`
- [x] Architect reviewed and approved after one iteration.
- [x] Critic reviewed and approved.
- [x] Consensus handoff written:
  `.omx/plans/ralplan-consensus-mvp2c-isaac-training-calibration.md`
- [x] After approved plan, run `$ultragoal` for implementation.
- [x] Added MVP-2C focused tests:
  `apps/api/tests/test_mvp2c_isaac_training_calibration_script.py`
- [x] Added MVP-2C runner:
  `scripts/run_mvp2c_isaac_training_calibration.py`
- [x] Implemented fresh MVP-2C scenario manifest:
  - `train_success`: seeds `4000-4079`
  - `train_failure`: seeds `4100-4179`
  - `calibration`: seeds `5000-5019`
  - `held_out`: seeds `6000-6019`
- [x] Implemented baseline uncurated mix pre-registration and hash evidence.
- [x] Implemented generator config hashes and immutability guard.
- [x] Implemented calibration-only action adapter registry/selector.
- [x] Implemented HDF5 baseline/candidate train views.
- [x] Implemented shared phase-conditioned NumPy BC baseline/candidate policy artifacts.
- [x] Implemented MVP-2C learning-proven validator bridge and external rollout JSON.
- [x] Implemented separate:
  - `mvp2c_close_minimum_passed`
  - `stronger_public_evidence_target_passed`
- [x] Implemented privileged task-state non-claims.
- [x] Verified deterministic positive uplift remains non-closing.
- [x] Ran actual Isaac MVP-2C attempt:

```text
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2c-isaac-runtime-final \
  --clean \
  --rollouts-per-policy 20 \
  --max-steps 150 \
  --bootstrap-iterations 200 \
  --action-scale 20
```

Actual MVP-2C result:

```text
runtime_backend=isaac_runtime
proof_runtime=dedicated_isaac_connector_insertion_evaluator
train_generation_runtime_backend=deterministic_test_backend
train_generation_runtime_gate.runtime_backend=isaac_runtime_import_probe_only
train_generation_runtime_gate.passed=false
train_generation_runtime_gate.actual_train_generation_evidence=false
runtime_gate.passed=true
actual_rollouts_per_policy=20
baseline_success_rate=0.0
candidate_success_rate=0.0
curated_vs_uncurated_uplift=0.0
mvp2_closed=false
mvp2c_close_minimum_passed=false
```

- [x] Focused tests pass: `13 passed`.
- [x] Regression tests pass: `50 passed`.
- [x] `compileall`, `ruff`, and `git diff --check` pass.
- [x] Post-review fail-closed hardening:
  - Isaac import probe alone cannot pass train-generation runtime gate.
  - Closure now requires actual Isaac train-generation evidence.
  - Closure now requires calibration-only selection and held-out leakage guards.
  - Deterministic positive uplift remains nested-validator non-proof evidence.
- [x] Added selected actual Isaac action adapter runtime config:
  - `xy_source=state_feedback`
  - `xy_state_feedback_gain=4.0`
  - `xy_action_clip=0.035`
  - `z_action_scale=24.0`
  - `z_action_clip=0.12`
  - `rotation_action_scale=1.0`
  - `stable_hold_action=[0.0, 0.0, -0.02, 0.0, 0.0, 0.0, 1.0]`
- [x] Verified latest actual Isaac adapter attempt remains non-closing:

```text
/home/kangrim/IsaacLab/_isaac_sim/python.sh scripts/run_mvp2c_isaac_training_calibration.py \
  --output-dir /tmp/rdf-mvp2c-isaac-adapter-v6 \
  --clean \
  --rollouts-per-policy 20 \
  --max-steps 150 \
  --bootstrap-iterations 200

baseline_success_rate=0.15
candidate_success_rate=0.15
curated_vs_uncurated_uplift=0.0
train_generation_runtime_backend=deterministic_test_backend
mvp2_closed=false
```

- [ ] MVP-2 Closed still needs positive curated > uncurated held-out uplift.
- [ ] MVP-2 Closed still needs actual Isaac runtime scripted expert train
  trajectory generation evidence.
- [ ] Do not use `held_out=6000-6019` for further tuning; next valid attempt
  needs a fresh pre-registered slice.

### 2026-06-11 follow-up: MVP-2C v0.2 train-generation blocker

- [x] Added fresh `v0_2` scenario profile:
  - `train_success=7000-7079`
  - `train_failure=7100-7179`
  - `calibration=8000-8019`
  - `held_out=9000-9019`
  - prior held-out ranges `3000-3019` and `6000-6019` are excluded.
- [x] Added hybrid `policy_plus_state_feedback` selected action adapter mode.
- [x] Split actual train-generation probe into a child process so parent can run
  held-out Isaac evaluation without opening two Isaac apps in one process.
- [x] Added single-policy Isaac probe path for train-generation evidence.
- [x] Verified focused tests:

```text
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -q
  47 passed
```

- [x] Verified actual Isaac train-generation probe still fails closed:

```text
/tmp/rdf-mvp2c-train-probe-v02b
generated_rollout_count=20
generated_success_count=0
passed=false

/tmp/rdf-mvp2c-train-probe-v02c
easy train-success attempts inspected=10
observed_success_count=0
```

- [ ] MVP-2 Closed remains blocked by actual Isaac scripted expert controller
  failure.
- [ ] Next valid step: build/debug a task-specific Isaac scripted expert
  controller until it can create at least one accepted train-generation rollout
  before re-running held-out policy A/B.

### 2026-06-11 follow-up: actual Isaac viability split

- [x] Verified Factory task viability:

```text
/tmp/rdf-mvp2c-factory-viability.json
evaluator_success_state_passed=true
accepted_replay_viability=true
scripted_oracle_passed=false
policy_loop_viability=false
```

- [x] Verified Forge task viability:

```text
/tmp/rdf-mvp2c-forge-viability.json
evaluator_success_state_passed=true
accepted_replay_viability=true
scripted_oracle_passed=false
policy_loop_viability=false
```

- [x] Verified accepted-readiness seed-family diagnostic still fails scripted
  oracle:

```text
/tmp/rdf-mvp2c-forge-viability-seed202506.json
evaluator_success_state_passed=true
accepted_replay_viability=true
scripted_oracle_passed=false
policy_loop_viability=false
```

- [ ] MVP-2 Closed remains blocked.
- [ ] Do not close from accepted replay alone; that would prove replay
  viability, not learning-proven curated > uncurated policy uplift.
- [ ] Next valid step is fresh pre-registered evaluator/controller rebase:
  align MVP-2C success metric with the existing RDF peg-in-hole evaluator and
  build a controller that can generate actual Isaac train-success rollouts
  before held-out policy A/B.

### 2026-06-11 follow-up: MVP-2D oracle repair and non-closing held-out proof

- [x] Repaired actual Isaac scripted oracle:
  - live target recompute each step
  - horizon-limited execution before env timeout reset
  - RDF `peg_in_hole` success metric
  - target/reset/fixed-asset jump instrumentation
- [x] Verified Phase 4 oracle evidence:

```text
/tmp/rdf-mvp2d-factory-oracle-repair.json
scripted_oracle_passed=true
policy_loop_viability=true
selected_success_evaluator=rdf_peg_in_hole
effective_steps=145
horizon_limited=true
success_step=4
```

- [x] Added fresh diagnostic scenario profiles:
  - `v0_3`: `train_success=10000-10079`,
    `train_failure=10100-10179`, `calibration=11000-11019`,
    `held_out=12000-12019`
  - `v0_4`: `train_success=13000-13079`,
    `train_failure=13100-13179`, `calibration=14000-14019`,
    `held_out=15000-15019`
- [x] Added actual Isaac success trace ingestion into candidate train rows only.
- [x] Verified `v0_3` full actual Isaac run remains non-closing:

```text
train_generation_success=3
baseline_success_rate=0.15
candidate_success_rate=0.15
curated_vs_uncurated_uplift=0.0
mvp2_closed=false
```

- [x] Verified `v0_4` full actual Isaac run remains non-closing:

```text
train_generation_success=5
baseline_success_rate=0.15
candidate_success_rate=0.15
curated_vs_uncurated_uplift=0.0
mvp2_closed=false
```

- [x] Recorded `G006-mvp-2d-oracle-repair-and-proof-close` as failed because
  MVP-2 Closed criteria are still unmet.
- [ ] MVP-2 Closed still needs positive curated > uncurated held-out uplift.
- [ ] Do not reuse `v0_3` or `v0_4` held-out seeds for proof closure.
- [ ] Next valid step: pre-register `v0_5`, improve candidate policy/trainer or
  calibration-only adapter selection before held-out, then run fresh held-out
  A/B once.

### 2026-06-11 follow-up: MVP-2D v0.5 residual servo BC

- [x] Added `v0_5` scenario profile:
  - `train_success=16000-16159`
  - `train_failure=16200-16359`
  - `calibration=17000-17029`
  - `held_out=18000-18019`
- [x] Added burned held-out exclusions through `15000-15019`.
- [x] Added v0.5 baseline/candidate train-view contract:
  - candidate: accepted actual Isaac success traces only when proof-eligible
  - baseline: equal trace count, fixed `60/40` accepted/rejected-noisy mix
  - failure bucket cycle: `lateral_offset`,
    `stability_window_loss`, `under_insertion`
- [x] Added phase-conditioned residual servo BC:
  - weak base servo + learned residual
  - residual target =
    `actual_trace_action_minus_weak_base_servo_action`
  - same feature schema, phase input, hyperparameters, selected adapter config
    for baseline/candidate
- [x] Added residual policy support in the Isaac proof evaluator.
- [x] Added self-contained `--train-generation-probe-only --clean` setup for
  `v0_5`.
- [x] Added fail-closed held-out scheduling:
  - if actual train-generation success traces `<20`, do not run held-out.
- [x] Verified tests/static checks:

```text
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -q
58 passed

uv run python -m compileall -q scripts apps/api/app apps/api/tests
PASS

uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py scripts/run_mvp2b_isaac_proof_evaluator.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py
PASS

git diff --check
PASS
```

- [x] Ran actual Isaac `v0_5` train-generation gate:

```text
/tmp/rdf-mvp2d-v05-train-gate/train_generation_runtime_gate.json
passed=false
generated_rollout_count=40
generated_success_count=5
required_success_count=20
actual_train_generation_evidence=false
```

- [x] Stopped before held-out A/B because train-generation gate failed.
- [ ] MVP-2 Closed remains blocked.
- [ ] Do not run or tune against `v0_5` held-out `18000-18019` until
  train-generation gate passes.
- [ ] Next valid step: improve the train-generation expert/adapter enough to
  produce `>=20` actual Isaac success traces before opening held-out A/B.

### 2026-06-11 follow-up: MVP-2E v0.6 env-native train-generation recovery design

- [x] Agreed to stop patching `v0_5` and open fresh profile `v0_6`.
- [x] Froze env-native `_get_curr_successes` as MVP-2E primary success
  authority.
- [x] Froze rollout success as `>=10` consecutive env-native success control
  steps.
- [x] Kept RDF `peg_in_hole` geometry metrics as buyer-facing diagnostics only.
- [x] Split repair probe seeds from proof gate seeds:
  - probe-only seeds: `16023`, `16042`, `16096`
  - fresh proof train range: `19000-19159`
  - fresh calibration range: `20000-20029`
  - sealed held-out range: `21000-21049`
- [x] Defined build-time config-difficulty selection for the fixed 40 train gate
  seeds.
- [x] Defined probe green-light/hard-stop logic with lateral divergence stopped
  diagnostics.
- [x] Defined chamfer/lead-in preflight as a mandatory INSERT parameter freeze
  gate.
- [x] Wrote design spec:
  `docs/superpowers/specs/2026-06-11-mvp2e-v06-env-native-train-generation-recovery-design.md`
- [x] Wrote `$ralplan` implementation artifacts:
  - `.omx/plans/prd-mvp2e-v06-env-native-train-generation-recovery.md`
  - `.omx/plans/test-spec-mvp2e-v06-env-native-train-generation-recovery.md`
  - `docs/superpowers/plans/2026-06-11-mvp2e-v06-env-native-train-generation-recovery.md`
- [x] Implemented `v0_6` manifest/profile, env-native success authority,
  deterministic 40-seed selection, repair probe gate, chamfer preflight gate,
  active phase z-gate, CLI wiring, and fail-closed held-out scheduling.
- [x] Verified focused MVP-2B/C tests:

```text
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -q
69 passed
```

- [x] Verified static checks:

```text
uv run python -m compileall -q scripts apps/api/app apps/api/tests
PASS

uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py scripts/run_mvp2b_isaac_proof_evaluator.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py
PASS

git diff --check
PASS
```

- [x] Verified `v0_6 --skip-isaac` smoke:

```text
manifest_version=rdf_mvp2e_scenario_manifest_v0.6.0
actual_isaac_success_trace_minimum=20
actual_isaac_success_trace_cap=40
heldout_schedule.scheduled=false
```

- [x] Ran actual repair probe and train gate entrypoints; both fail-closed before
  Isaac rollout because chamfer preflight Branch C blocked INSERT parameter freeze.
- [ ] MVP-2 Closed remains blocked.
- [ ] Next valid step: make Factory USD mesh geometry inspectable and resolve
  chamfer preflight Branch A/B before running repair probe or the fixed 40 gate.

### 2026-06-11 follow-up: MVP-2E v0.6a runtime capture-radius preflight

- [x] Reframed `v0_6` Branch C as a static-local inspection limitation, not proof
  that Factory assets are runtime-inaccessible.
- [x] Wrote design spec:
  `docs/superpowers/specs/2026-06-11-mvp2e-v06a-runtime-capture-radius-preflight-design.md`
- [x] Froze empirical capture-radius probe as the primary Branch C resolution path.
- [x] Reserved geometry-only probe seed namespace `18500-18509`.
- [x] Preserved held-out `21000-21049` seal.
- [x] Preserved train gate `19000-19159`, calibration `20000-20029`, and repair
  probe seeds `16023`, `16042`, `16096`.
- [x] Defined `capture_radius_probe.json` and updated `chamfer_preflight.json`
  artifact requirements.
- [x] Next valid step completed: wrote `$ralplan` implementation plan for the
  v0.6a runtime capture-radius preflight.
- [ ] Do not run repair probe, fixed 40-run gate, or held-out A/B until Branch A/B
  is produced by the preflight and recorded.

### 2026-06-11 follow-up: MVP-2E v0.6a ralplan implementation plan

- [x] Cleared stale OMX `ultragoal` state that blocked `$ralplan`.
- [x] Wrote context snapshot:
  `.omx/context/mvp2e-v06a-runtime-capture-radius-preflight-20260611T101043Z.md`
- [x] Wrote PRD:
  `.omx/plans/prd-mvp2e-v06a-runtime-capture-radius-preflight.md`
- [x] Wrote test spec:
  `.omx/plans/test-spec-mvp2e-v06a-runtime-capture-radius-preflight.md`
- [x] Wrote implementation plan:
  `docs/superpowers/plans/2026-06-11-mvp2e-v06a-runtime-capture-radius-preflight.md`
- [x] Ran Architect review iteration 1: `ITERATE`.
- [x] Applied Architect blockers:
  - exact INSERT envelope `24/4/145/0`
  - verified v0.6a preflight artifact consumption
  - repair-probe-dependent `train_generation_gate_allowed`
  - artifact-shape tests
- [x] Ran final Architect review: `APPROVE`.
- [x] Ran Critic review: `APPROVE`.
- [x] Wrote consensus handoff:
  `.omx/plans/ralplan-consensus-mvp2e-v06a-runtime-capture-radius-preflight.md`
- [x] Ran `$ultragoal implement docs/superpowers/plans/2026-06-11-mvp2e-v06a-runtime-capture-radius-preflight.md`.
- [x] Added RED/GREEN tests for v0.6a seed namespace, Branch A/B/C, artifact
  authority, verified preflight validation, Branch B align-then-jam, and static
  skip compatibility.
- [x] Added `--capture-radius-probe-only`.
- [x] Produced runtime capture-radius artifacts:
  - `/tmp/rdf-mvp2e-v06a-capture-radius/capture_radius_probe.json`
  - `/tmp/rdf-mvp2e-v06a-capture-radius/chamfer_preflight.json`
  - `/tmp/rdf-mvp2e-v06a-capture-radius/capture_radius_preflight_result.json`
- [x] Result: Branch C fail-closed.
  - `runtime_loaded=true`
  - `runtime_error=TimeoutError: v0_6a capture-radius trial exceeded runtime deadline`
  - `repair_probe_allowed=false`
  - `train_generation_gate_allowed=false`
  - `heldout_schedule.scheduled=false`
- [x] Review-fix rerun result: Branch B partial runtime evidence.
  - `runtime_loaded=true`
  - `capture_radius_m=approximate`
  - `runtime_error=v0_6a capture-radius trial exceeded runtime deadline`
  - `repair_probe_allowed=true`
  - `train_generation_gate_allowed=false`
  - `train_generation_gate_status=pending_repair_probe`
  - `heldout_schedule.scheduled=false`
- [x] Verified train-generation gate still blocks without repair green light.
  - reason: `missing_v0_6_repair_probe_green_light`
- [x] Applied final review hardening for v0.6a:
  - Branch A now requires full pre-registered offset sweep coverage and
    direction-wise non-zero success count evidence.
  - A green `repair_probe_gate.json` is validated structurally before it can
    open the fixed 40-run train gate.
  - Full `v0_6` build preserves an existing runtime Branch A/B
    `chamfer_preflight.json` instead of overwriting it with static Branch C.
  - `--capture-radius-probe-only --clean` rejects wrong profiles before
    touching the output directory.
- [x] Re-verified after hardening:

```text
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q
51 passed

uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py -q
84 passed

uv run python -m compileall -q scripts apps/api/app apps/api/tests
PASS

uvx ruff check scripts/run_mvp2c_isaac_training_calibration.py scripts/run_mvp2b_isaac_proof_evaluator.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py
PASS

git diff --check
PASS
```
- [x] Fixed code-reviewer HIGH finding: the train-generation gate no longer
  accepts a semantically fake `repair_probe_gate.json`.
  - `probe_results` are normalized by seed.
  - `evaluate_v06_repair_probe_gate()` is recomputed during validation.
  - top-level gate booleans must match recomputed semantics.
  - regression added for green top-level flags with empty per-seed probe results.
- [x] Ran actual Isaac repair probe `16023/16042/16096` with verified Branch B
  preflight.
  - command exited 0
  - `runtime_backend=isaac_runtime`
  - `runtime_gate.passed=true`
  - artifact:
    `/tmp/rdf-mvp2e-v06a-capture-radius/repair_probe_gate.json`
- [x] Repair probe failed closed as intended.
  - `green_light_for_40_run_gate=false`
  - `hard_stop=true`
  - `hold_mode_passed=false`
  - `lateral_success_mode_passed=false`
  - `lateral_divergence_stopped=false`
  - resolver result: `train_generation_gate_allowed=false`,
    `reason=v0_6_repair_probe_not_green`
- [ ] MVP-2 Closed remains blocked.
- [ ] Do not run fixed 40-run train gate or held-out A/B until a future repair
  probe green light is recorded and semantically validated.
- [ ] Next valid step: instrument env-native `_get_curr_successes` inputs and
  keypoint distances for repair probe seeds, then explain why RDF secondary
  geometry succeeds while env-native success mask remains false.

### 2026-06-11 follow-up: MVP-2E v0.6b RDF/native metric repair

- [x] Wrote implementation plan:
  `docs/superpowers/plans/2026-06-11-mvp2e-v06b-rdf-native-metric-repair.md`
- [x] Ran Architect review iteration 1/2 and resolved blockers.
- [x] Ran final Architect review: `APPROVE`.
- [x] Ran Critic review: `APPROVE`.
- [x] Wrote consensus handoff:
  `.omx/plans/ralplan-consensus-mvp2e-v06b-rdf-native-metric-repair.md`
- [x] Created artifact-backed `$ultragoal` goals in `.omx/ultragoal/goals.json`.
  - Codex goal state was already `complete`, so intermediate OMX checkpointing
    could not mark `in_progress -> complete`; implementation continued from
    the approved artifacts.
- [x] Added Factory native base/target diagnostic helpers.
- [x] Added native-aligned runtime metric row builder.
- [x] Preserved legacy deterministic RDF metric behavior for fixtures.
- [x] Added v0.6b native metric trace semantic validator.
- [x] Made repair gate fail closed when native metric trace validation is missing
  or semantically invalid.
- [x] Ran actual Isaac repair probe with v0.6b native-aligned trace semantics.
  - command exited 0
  - artifact:
    `/tmp/rdf-mvp2e-v06b-native-metric-repair/repair_probe_gate.json`
  - `runtime_backend=isaac_runtime`
  - `runtime_gate.passed=true`
  - `v0_6b_native_metric_trace_validation.valid=true`
  - `validated_trace_count=450`
- [x] Repair probe failed closed as intended.
  - `green_light_for_40_run_gate=false`
  - `hard_stop=true`
  - `hold_mode_passed=false`
  - `lateral_success_mode_passed=false`
  - `lateral_divergence_stopped=false`
  - resolver result: `train_generation_gate_allowed=false`,
    `reason=v0_6_repair_probe_not_green`
- [x] Confirmed the v0.6a semantic mismatch is resolved.
  - RDF secondary metric now reports `UNDER_INSERTION_FAILURE` instead of false
    success when native seating progress is zero.
- [ ] MVP-2 Closed remains blocked.
- [ ] Do not run fixed 40-run train gate or held-out A/B until a future repair
  probe green light is recorded and v0.6b semantic validation passes.
- [ ] Next valid step: diagnose active phase / z-gate / action adapter behavior.
  Current v0.6b traces remain in `APPROACH` with `runtime_depth_feature_m=0.0`
  and `env_native_z_disp_m` still tens of millimeters above the native target.

### 2026-06-11 follow-up: MVP-2E v0.6c controller/action diagnosis

- [x] Confirmed a new Codex goal context cannot be created in this thread until the
  previous completed aggregate goal is manually cleared with `/goal clear`.
- [x] Continued artifact-backed because the v0.6c diagnostic scope is
  repair-probe-only and does not open held-out or the fixed 40-run gate.
- [x] Added action adapter diagnostics:
  - raw policy action vector
  - pre-controller action vector
  - final post-adapter action vector
  - phase controller verdict
  - z suppression flag
  - z motion block reason
- [x] Added `summarize_v06c_controller_action_diagnosis()`.
- [x] Ran actual Isaac repair probe with copied verified Branch B preflight:
  `/tmp/rdf-mvp2e-v06c-controller-action-diagnosis`.
- [x] Generated:
  `/tmp/rdf-mvp2e-v06c-controller-action-diagnosis/controller_action_diagnosis.json`
- [x] Diagnosis result:
  - `root_cause_hypothesis=controller_phase_vocabulary_mismatch_blocks_z_motion`
  - `trace_rows=450`
  - `rows_with_diagnostics=450`
  - `raw_negative_z_action_steps=450`
  - `pre_controller_negative_z_action_steps=450`
  - `final_negative_z_action_steps=0`
  - `z_motion_suppressed_steps=450`
  - `phase_vocabulary_mismatch_steps=450`
  - `z_motion_block_reason_counts.controller_phase_vocabulary_mismatch=450`
- [x] Verified:

```text
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q
96 passed

uv run python -m compileall -q scripts apps/api/app apps/api/tests
PASS

uvx ruff check scripts/run_mvp2b_isaac_proof_evaluator.py scripts/run_mvp2c_isaac_training_calibration.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py
PASS

git diff --check
PASS
```

- [ ] MVP-2 Closed remains blocked.
- [ ] Do not run fixed 40-run train gate or held-out A/B yet.
- [ ] Next valid step: minimal v0.6d fix for controller phase vocabulary/state
  persistence, then rerun only repair probe `16023/16042/16096`.

### 2026-06-11 follow-up: MVP-2E v0.6d controller phase vocabulary fix

- [x] Added RED tests for trace-to-controller phase normalization.
- [x] Implemented `normalize_v06_controller_phase()`.
  - `APPROACH -> ALIGN`
  - `CONTACT -> DESCEND`
  - `INSERT -> INSERT`
  - `SEAT -> HOLD`
- [x] Updated action adapter diagnostics with `controller_input_phase` and
  `phase_normalized`.
- [x] Confirmed focused RED -> GREEN:

```text
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py::test_v06d_trace_phase_normalization_maps_runtime_phase_to_controller_phase apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py::test_v06d_action_diagnostics_allow_approach_phase_z_motion_when_aligned -q
RED: 2 failed before implementation
GREEN: 2 passed after implementation
```

- [x] Ran relevant regression:

```text
uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q
97 passed

uv run pytest apps/api/tests/test_mvp1_proof_audit_script.py apps/api/tests/test_mvp1plus_embodiment_proof_script.py apps/api/tests/test_mvp2_learning_sanity_script.py apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py apps/api/tests/test_peg_insert_viability_script.py -q
156 passed
```

- [x] Ran actual Isaac repair probe:
  `/tmp/rdf-mvp2e-v06d-controller-phase-fix/repair_probe_gate.json`
- [x] Confirmed v0.6c blocker is resolved:
  - `phase_vocabulary_mismatch_steps=0`
  - `final_negative_z_action_steps=269`
  - `z_motion_block_reason_counts.z_motion_allowed=269`
- [x] Repair probe still failed closed:
  - `green_light_for_40_run_gate=false`
  - `hard_stop=true`
  - `16023` env-native success: true
  - `16042` env-native success: true, but diagnostic divergence false because
    initial lateral is already above the 8mm cap
  - `16096` env-native success: false
- [ ] MVP-2 Closed remains blocked.
- [ ] Do not run fixed 40-run train gate or held-out `21000-21049`.
- [ ] Next valid step: v0.6e pre-registered diagnostic/repair slice.
  - Separate high-initial-lateral diagnostic gate semantics from closure.
  - Diagnose/fix severe seed `16096` align time / horizon exhaustion.

### 2026-06-11 follow-up: MVP-2E v0.6e repair probe green spec

- [x] Chose v0.6e as one combined slice:
  - diagnostic divergence rule repair
  - `16096` controller repair
  - repair probe green light only
- [x] Locked authority hierarchy:
  - env-native 10-consec pass cannot be vetoed by secondary diagnostics
  - RDF geometry remains report-only
- [x] Locked capture-radius hardening:
  - `capture_radius_m` must be numeric
  - source must be empirical runtime probe
  - probe must disable xy/yaw correction and use straight-down push only
- [x] Locked convergence rule:
  - `last_k_median_lateral_m <= capture_radius_m`
  - `last_k_median_lateral_m <= min_lateral_achieved_m + regression_tol_m`
  - no initial-improvement clause
- [x] Locked controller envelope:
  - z push is forbidden while `lateral_error_m > capture_radius_m`
  - no horizon increase
  - no retry/search/withdraw/force-control
  - no per-seed grid search on the three repair probe seeds
- [x] Wrote spec:
  `docs/superpowers/specs/2026-06-11-mvp2e-v06e-repair-probe-green-design.md`
- [x] User approved moving to implementation plan.
- [x] Wrote implementation plan:
  `docs/superpowers/plans/2026-06-11-mvp2e-v06e-repair-probe-green.md`
- [x] Executed implementation plan with `$ultragoal` until runtime stop condition.
- [x] Added v0.6e helper/tests:
  - env-native authority cannot be vetoed by secondary divergence diagnostics.
  - non-seated lateral convergence uses numeric capture radius + no-regression.
  - strict numeric geometry-isolated capture-radius preflight gates repair probe.
  - controller repair config derives z-push gate from `capture_radius_m`.
  - capture-radius runtime trial schedule is delta-major.
- [x] Ran focused and relevant regression tests:

```text
uv run pytest apps/api/tests/test_mvp2c_isaac_training_calibration_script.py::test_v06a_capture_radius_trial_schedule_samples_all_directions_before_next_delta -q
1 passed

uv run pytest apps/api/tests/test_mvp2b_isaac_proof_evaluator_script.py apps/api/tests/test_mvp2c_isaac_training_calibration_script.py -q
107 passed
```

- [x] Ran capture-radius runtime probe:

```text
/tmp/rdf-mvp2e-v06e-repair-probe-green/capture_radius_preflight_result.json
capture_radius_m=0.0001
preflight_branch=B
direction max successful deltas: +x=0.0002, -x=0.0002, +y=0.0001, -y=0.0001
heldout_schedule.scheduled=false
```

- [x] Ran repair-probe-only runtime:

```text
/tmp/rdf-mvp2e-v06e-repair-probe-green/repair_probe_gate.json
green_light_for_40_run_gate=false
hard_stop=true
fixed_40_run_gate_opened=false
heldout_opened=false
16023 env_native_rollout_success=false, max_consecutive=0, max_insertion_depth_m=0
16042 env_native_rollout_success=false, max_consecutive=0, max_insertion_depth_m=0
16096 env_native_rollout_success=false, max_consecutive=0, max_insertion_depth_m=0
```

- [x] Stop condition hit:
  - `16023 loses env-native pass after global repair config`
  - `all lateral seeds lose env-native pass after global repair config`
- [x] Fixed 40-run train gate remained closed.
- [x] Held-out `21000-21049` remained sealed.
- [ ] MVP-2 Closed remains blocked.
- [ ] Next valid step: write a new spec/plan for the v0.6f design question:
  whether `straight_down capture_radius_m=0.0001` should be used directly as
  the z descent gate, or whether the z-gate must be derived from a different
  pre-registered approach/capture envelope without weakening env-native success.
