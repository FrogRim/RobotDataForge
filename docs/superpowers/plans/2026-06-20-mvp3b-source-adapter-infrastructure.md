# MVP-3B Source-Adapter Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:test-driven-development` for implementation tasks and
> `superpowers:verification-before-completion` before claiming completion.
> This plan passed ralplan Architect and Critic review on 2026-06-20. Implement from
> Task 1 using TDD; do not skip the verifier tamper tests.

**Goal:** Build MVP-3B Source-Adapter Infrastructure Closed: a self-contained,
externally verifiable proof package showing that Franka, ROS2-DDS-style, and UR-style
recorded-log source profiles can be projected through the common RDF adapter
infrastructure into normalized trajectory contracts without claiming live robot support,
independent robot integrations, or learning uplift.

**Chosen Option:** Source-Adapter Matrix Slice.

**Architecture:** Producer code uses existing `RobotEmbodimentAdapterRegistry` and
`NormalizedTrajectoryContractValidator` to generate per-adapter source projections and
contracts. A new stdlib-only verifier independently audits the package from serialized
data and does not import producer services.

**Tech Stack:** Python 3.11, stdlib-only verifier, pytest, existing
`app.services.robot_embodiment_adapters`, existing `app.services.normalized_trajectory_contract`,
local filesystem package artifacts.

## RALPLAN-DR Summary

Principles:

```text
1. One changed variable: source_adapter_matrix.
2. No support claim from fixture compatibility.
3. Self-contained evidence beats storage-local provenance.
4. Producer and auditor code remain independent.
5. Learning-proven remains separate from infrastructure closed.
```

Decision drivers:

```text
1. MVP-3B must be meaningfully different from MVP-3A.
2. UR/ROS2-DDS/Franka names must not become live support claims.
3. External reviewers must be able to recompute the package without local storage.
```

Viable options considered:

```text
A. Single UR adapter deep slice
   pro: smallest scope
   con: weaker source-expansion story, higher chance of being misread as UR support

B. Source-adapter matrix slice
   pro: strongest MVP-3B source expansion proof
   con: larger package/verifier contract

C. Real/public log import
   pro: strongest external credibility
   con: provenance/license/schema risk too high for this immediate slice

D. Another Isaac robustness slice
   pro: easiest to verify
   con: not a source-adapter step
```

Decision: Option B.

Ralplan consensus:

```text
architect_iteration_1=REQUEST_CHANGES
architect_iteration_2=APPROVE
critic_iteration_1=APPROVE
implementation_status=not_started
```

Pre-mortem:

```text
1. Self-attestation returns: package summary says closed but source logs/contracts are
   missing or local-only.
   Mitigation: manifest covers every data file; verifier recomputes from source logs,
   projections, contracts, and non-claims.

2. Adapter names overclaim support: UR/ROS2-DDS/Franka names are interpreted as live
   runtime readiness.
   Mitigation: non-claims hash-locked; verifier rejects truthy support/readiness claims;
   docs use source-profile projection wording instead of robot integration wording.

3. Matrix scope sprawls: implementation tries to solve learning-proven or real-log import.
   Mitigation: no held-out policy A/B, no learning addendum, no live runtime, no DB migration.
```

Expanded test plan:

```text
unit:
  - adapter fixture builder source log shape
  - verifier source log parser
  - verifier normalized contract role checks
  - non-claim truthy rejection

integration:
  - runner builds full matrix package
  - verifier accepts generated package
  - tamper matrix fails

e2e:
  - python3 scripts/verify_mvp3b_source_adapter_package.py <manifest> => VERIFIED
  - existing MVP-3A verifier remains VERIFIED
  - existing MVP-2 verifier remains VERIFIED

observability:
  - package README has exact claim/non-claim boundary
  - worklog and Handoff record no-reuse/no-support boundaries
```

## Global Constraints

- Do not modify frozen MVP-2 assets:
  - `scripts/run_mvp2c_isaac_training_calibration.py`
  - `scripts/run_mvp2b_isaac_proof_evaluator.py`
  - `scripts/verify_mvp2_package.py`
  - `docs/proof/mvp2_learning_proven_evidence_package/`
- Do not modify MVP-3A proof package artifacts except documentation references if needed.
- Do not reuse `40000-40049` or `42000-42049` for tuning, threshold selection, or closure proof.
- MVP-3B verifier must hard-code exact `spent_no_reuse == [[40000, 40049], [42000, 42049]]`.
- MVP-3B verifier must hard-fail if any calibration, held-out, tuning, or closure range is opened.
- Do not claim real robot success, physical robot readiness, live UR runtime support,
  live ROS2-DDS runtime support, Franka hardware support, policy uplift, marketplace
  readiness, or production certification.
- Treat trainer/export smoke as contract smoke only. Keep
  `learning_results_measured=false`, `policy_uplift=false`, and
  `learning_proven_value=false`.
- `scripts/verify_mvp3b_source_adapter_package.py` must be stdlib-only.
- Verifier must not import `app.services.robot_embodiment_adapters` or
  `app.services.normalized_trajectory_contract`.
- `source_adapter_matrix_summary.json` is cached summary only, not source of truth.
- No commits, pushes, tags, or PRs unless explicitly requested after verification.

## File Structure

Create:

```text
scripts/run_mvp3b_source_adapter_infrastructure.py
scripts/verify_mvp3b_source_adapter_package.py
apps/api/tests/test_mvp3b_source_adapter_infrastructure.py
apps/api/tests/test_verify_mvp3b_source_adapter_package.py
docs/proof/mvp3b_source_adapter_matrix_proof_package/
```

Modify:

```text
docs/developer/worklog.md
Handoff.md
tasks/todo.md
```

No code task modifies frozen MVP-2 files.

## Package Contract

The runner writes:

```text
docs/proof/mvp3b_source_adapter_matrix_proof_package/
  README.md
  package_manifest.json
  data/
    config.json
    adapter_registry_snapshot.json
    source_adapter_matrix_summary.json
    non_claims_attestation.json
    artifact_index.json
    source_logs/<adapter_id>/{metadata.json,accepted_command_state.jsonl,rejected_command_state.jsonl}
    projections/<adapter_id>/{projection_manifest.json,curation_manifest.json,trajectories/,evaluations/}
    contracts/<adapter_id>_normalized_trajectory_contract.json
    adapter_results/<adapter_id>_adapter_result.json
```

Required adapters:

```text
franka_research_arm
robotis_sh5_ros2_dds
universal_robots_ur_industrial_arm
```

Canonical MVP-3B forbidden claim keys:

```text
real_robot_success
real_robot_success_claimed
physical_robot_readiness
physical_robot_readiness_claimed
deployable_policy_readiness
visual_policy_performance
hmd_openxr_collection_readiness
hmd_readiness
hmd_readiness_claimed
marketplace_readiness
marketplace_readiness_claimed
production_certification
universal_robot_support
universal_robot_support_claimed
policy_uplift
policy_uplift_claimed
learning_proven_value
live_runtime_support
live_runtime_support_claimed
live_ur_runtime_support
live_ros2_dds_runtime_support
franka_hardware_support
public_sample_import
public_sample_import_claimed
public_sample_evidence_claimed
db_migration
db_migration_claimed
production_auth
production_auth_claimed
real_robot_readiness_claimed
production_robot_support_claimed
```

The verifier owns this canonical list, not the producer services. It must reject truthy
values or unsupported support wording across config, metadata, registry snapshot, adapter
results, summary, non-claim attestation, and README text.

Source-of-truth hierarchy:

```text
source_logs/      -> source metadata and accepted/rejected command-state rows
projections/      -> projected trajectory/evaluation/curation artifacts
contracts/        -> normalized trajectory contract evidence
adapter_results/  -> producer-side per-adapter result, checked as cached result
config.json       -> expected adapter set and non-claim policy
summary.json      -> cached summary only
```

## Task 1: RED tests for source-adapter verifier package contract

Files:

```text
apps/api/tests/test_verify_mvp3b_source_adapter_package.py
scripts/verify_mvp3b_source_adapter_package.py
```

Acceptance:

- Tests create a temp package with three adapters and no `app.services` imports.
- Initial tests fail because verifier does not exist yet.
- Tests cover:
  - green package returns `status=source_adapter_infrastructure_closed`
  - missing adapter fails
  - extra adapter fails
  - source log hash tamper fails
  - unindexed data file fails
  - truthy `real_robot_success`, `live_ur_runtime_support`, or
    `live_runtime_support_claimed` fails
  - truthy producer claim keys `physical_robot_readiness_claimed`,
    `real_robot_success_claimed`, `public_sample_evidence_claimed`, and
    `live_runtime_support` fail inside recursive package surfaces
  - missing/altered exact `spent_no_reuse` fails
  - any non-empty opened calibration/heldout/tuning/closure range fails
  - learning_proven_addendum present without separate fresh-range addendum evidence fails
  - missing contract action role fails
  - summary count override fails

Verification:

```bash
uv run pytest apps/api/tests/test_verify_mvp3b_source_adapter_package.py -q
```

Expected first run: RED.

## Task 2: Implement stdlib-only source-adapter verifier

Files:

```text
scripts/verify_mvp3b_source_adapter_package.py
apps/api/tests/test_verify_mvp3b_source_adapter_package.py
```

Implementation requirements:

- No non-stdlib imports.
- Expose `verify_package(manifest_path: Path) -> Report`.
- CLI exits `0` only when all hard checks pass.
- Detect imports of producer-side modules via test guard.
- Recompute:
  - manifest hash integrity
  - data coverage
  - adapter set exactness
  - source log completeness
  - metadata/profile consistency
  - source/projection hash binding
  - accepted/rejected counts
  - normalized contract source fields
  - normalized contract required action roles
  - frame action role coverage
  - non-claims false
  - canonical forbidden claim keys recursively across package surfaces
  - exact spent_no_reuse equals `[[40000, 40049], [42000, 42049]]`
  - opened calibration/heldout/tuning/closure ranges are all empty
  - no learning-proven addendum unless separately fresh-range-verifiable
  - summary/cache consistency

Verification:

```bash
uv run pytest apps/api/tests/test_verify_mvp3b_source_adapter_package.py -q
python3 scripts/verify_mvp3b_source_adapter_package.py --help
```

## Task 3: RED tests for MVP-3B source-adapter package runner

Files:

```text
apps/api/tests/test_mvp3b_source_adapter_infrastructure.py
scripts/run_mvp3b_source_adapter_infrastructure.py
```

Acceptance:

- Tests fail before runner exists.
- Tests assert runner:
  - builds required source log fixtures
  - calls the existing adapter registry path
  - writes package layout
  - writes hash-indexed manifest
  - refuses learning-proven addendum
  - writes all non-claims false
  - writes exact spent_no_reuse and empty opened range contract
  - labels trainer/export smoke as contract smoke only
  - refuses unsafe output cleanup paths

Verification:

```bash
uv run pytest apps/api/tests/test_mvp3b_source_adapter_infrastructure.py -q
```

Expected first run: RED.

## Task 4: Implement MVP-3B package runner

Files:

```text
scripts/run_mvp3b_source_adapter_infrastructure.py
apps/api/tests/test_mvp3b_source_adapter_infrastructure.py
```

Implementation requirements:

- Use existing `RobotEmbodimentAdapterRegistry`.
- Create repo-local generated/file-backed fixture source logs when external source dirs
  are not provided.
- Project each adapter to trajectories/evaluations/curation artifacts.
- Build normalized trajectory contracts.
- Copy all verdict-critical source/projection/contract/result data into `docs/proof/`.
- Generate `package_manifest.json` and `data/artifact_index.json`.
- Do not call the verifier from producer code.
- Do not open Isaac or any live robot runtime.
- Do not emit wording or flags that imply live UR, live ROS2-DDS, Franka hardware,
  real robot readiness, or learning-proven value.

Verification:

```bash
uv run pytest apps/api/tests/test_mvp3b_source_adapter_infrastructure.py -q
uv run python scripts/run_mvp3b_source_adapter_infrastructure.py --clean
```

## Task 5: Full package verification and tamper matrix

Files:

```text
apps/api/tests/test_verify_mvp3b_source_adapter_package.py
scripts/verify_mvp3b_source_adapter_package.py
docs/proof/mvp3b_source_adapter_matrix_proof_package/
```

Acceptance:

- Real generated package verifies:

```bash
python3 scripts/verify_mvp3b_source_adapter_package.py \
  docs/proof/mvp3b_source_adapter_matrix_proof_package/package_manifest.json
```

- Tamper tests fail for:
  - source row changed
  - metadata truthy support claim
  - generic producer claim key set truthy
  - `physical_robot_readiness_claimed`, `real_robot_success_claimed`,
    `public_sample_evidence_claimed`, or `live_runtime_support` set truthy
  - spent_no_reuse missing or altered
  - opened held-out/calibration/tuning/closure range non-empty
  - learning_proven_addendum present without fresh-range addendum evidence
  - contract role removed
  - adapter result count override
  - package summary override
  - data file removed from manifest

## Task 6: Documentation and handoff updates

Files:

```text
docs/proof/mvp3b_source_adapter_matrix_proof_package/README.md
docs/developer/worklog.md
tasks/todo.md
Handoff.md
```

Acceptance:

- README says exactly what is claimed and not claimed.
- README says MVP-3B proves generated/file-backed source-profile projection through RDF
  infrastructure, not live UR, ROS2-DDS, Franka, or real robot integration.
- `Handoff.md` records:
  - MVP-3B Infrastructure Closed status if verified
  - no learning-proven addendum
  - no held-out range opened
  - `40000-40049` and `42000-42049` remain spent
- Worklog records commands and results.

## Task 7: Regression and frozen-asset verification

Commands:

```bash
python3 scripts/verify_mvp3b_source_adapter_package.py \
  docs/proof/mvp3b_source_adapter_matrix_proof_package/package_manifest.json

python3 scripts/verify_proof_package.py \
  docs/proof/mvp3a_target_fixture_pose_variant_proof_package/package_manifest.json

python3 scripts/verify_mvp2_package.py \
  docs/proof/mvp2_learning_proven_evidence_package/package_manifest.json

uv run pytest apps/api/tests/test_mvp3b_source_adapter_infrastructure.py \
  apps/api/tests/test_verify_mvp3b_source_adapter_package.py -q

uv run pytest -q
uvx ruff check scripts apps/api
python3 -m compileall -q scripts apps/api
git diff --check
git diff -- \
  scripts/run_mvp2c_isaac_training_calibration.py \
  scripts/run_mvp2b_isaac_proof_evaluator.py \
  scripts/verify_mvp2_package.py \
  docs/proof/mvp2_learning_proven_evidence_package
```

Expected:

```text
MVP-3B verifier: VERDICT: VERIFIED
MVP-3A verifier: VERDICT: VERIFIED
MVP-2 verifier: VERDICT: VERIFIED
pytest: pass
ruff: pass
compileall: pass
frozen MVP-2 diff: no output
```

## Ralplan Consensus Gate Requirements

Before execution, an Architect review must approve:

```text
- source-adapter matrix is the correct MVP-3B variable
- package source-of-truth hierarchy prevents self-attestation
- non-claims are enforceable by verifier
- no learning-proven or support claim leaks into the package
```

Then a Critic review must approve:

```text
- acceptance criteria are testable
- hard-fail criteria cover self-attestation and overclaiming
- task sequence is small enough for TDD
- verification commands are sufficient
```

If either review requests changes, revise this plan before implementation.

## Execution Handoff Recommendation

Default follow-up:

```text
$ultragoal using this plan
```

Parallel option:

```text
$team
  lane 1: verifier RED/GREEN + tamper tests
  lane 2: runner/package builder
  lane 3: docs/handoff and frozen-regression verification
```

Ralph fallback:

```text
$ralph only if a single-owner persistent verification loop is explicitly desired.
```
