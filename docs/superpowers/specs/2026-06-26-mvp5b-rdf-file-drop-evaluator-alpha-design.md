# MVP-5B RDF File-Drop Evaluator Alpha Design

Date: 2026-06-26 KST

Status: Specify

Milestone name:

```text
MVP-5B: RDF File-Drop Evaluator Alpha
```

Working product name:

```text
RDF File-Drop Evaluator
```

Branch context:

```text
base requirement: MVP-5A L2/L3 capture-edge close must be merged or used as the verified backend baseline.
preferred branch: codex/mvp5b-file-drop-evaluator-alpha
```

## Problem

Robot Data Forge now has a strong verifier-backed backend boundary for
digital-twin recorded-log file-drop rehearsal:

```text
capture-edge runtime event evidence
-> process provenance receipt
-> verifier-owned reconstruction
-> file-drop profile projections
-> normalized contracts
-> HDF5 / trainer smoke
-> TrustPack verifier
```

The proof core is strong, but the user-facing product surface is still weak.
Today a reviewer or operator must know which scripts to run, where packages are
written, which verifier mode is required, and how to read rejection reasons.

That is not yet a practical local evaluator.

The next milestone should not create a new proof claim. It should productize
the existing proof discipline into a local tool that can accept a folder or zip
file-drop, run the existing trust path, and show the result without weakening
the verifier boundary.

## Goal

Build a local file-drop evaluator alpha that lets a user evaluate recorded-log
folders or zips through the RDF trust layer.

Target flow:

```text
folder-or-zip file-drop
-> explicit profile selection
-> preflight scan
-> RDF CLI evaluation
-> TrustPack generation or structured rejection
-> verifier run
-> buyer_report.html
-> local web UI display
-> Pake desktop shell wraps the UI
```

Primary claim:

```text
RDF can run a local file-drop evaluation workflow through an explicit profile,
the CLI/verifier backend, and a user-facing desktop alpha shell.
```

More precise internal status:

```text
file_drop_evaluator_alpha_ready=true
```

This is a product-surface readiness claim, not a new data-origin claim.

## Non-Goals

Do not implement in this milestone:

```text
real robot control
live UR/RTDE connection
live Franka hardware connection
live ROS2/DDS bridge
HMD/OpenXR/SteamVR/Quest runtime
policy training
policy uplift
marketplace
worker/operator payment flow
production auth
cloud service deployment
generic LeRobot importer
generic robot-log auto-detection
full MCAP binary parser unless already lightweight and locally available
full Croissant compliance
```

The alpha may evaluate digital-twin rehearsal logs and local test corpus drops.
It must not claim that real external partner robot data has been evaluated
unless such data is explicitly supplied in a future milestone with its own
provenance boundary.

## Forbidden Claims

The CLI, package, buyer report, local web UI, Pake shell, docs, and logs must not
claim:

```text
external_partner_data_evaluated
real_robot_data_evaluated
real_robot_success
physical_robot_readiness
hardware_readiness
live_ur_rtde_support
live_franka_hardware_support
live_ros2_dds_bridge_readiness
visual_policy_performance
policy_uplift
sim_to_real_proven
production_readiness
marketplace_readiness
universal_robot_support
```

Allowed language:

```text
local file-drop evaluation alpha
digital-twin rehearsal package
recorded-log profile validation
TrustPack verifier-backed result
pre-real-log readiness
```

Disallowed language:

```text
real robot ready
hardware validated
external data evaluated
production ready
works with any robot log
universal ROS2 support
live UR support
```

## Brainstorming

### Option A — CLI-first + local web UI + Pake shell

Shape:

```text
RDF CLI owns evaluation and verifier invocation.
Local web UI displays CLI JSON output.
Pake wraps the local web UI into a desktop app.
```

Optimizes:

```text
trust boundary
testability
future desktop stability
small implementation risk
clean separation between verdict engine and UI
```

Tradeoff:

```text
More plumbing before a polished desktop app exists.
```

Risk:

```text
Local server/process lifecycle must be designed carefully.
```

Verdict:

```text
Chosen.
```

### Option B — Web API first, desktop later

Shape:

```text
FastAPI endpoint wraps evaluation scripts.
Existing Next.js app calls backend endpoints.
Pake comes later.
```

Optimizes:

```text
reuse of existing apps/api and apps/web boundaries.
```

Tradeoff:

```text
Risk of making the API server the hidden verdict source rather than the CLI/verifier.
Desktop alpha gets delayed.
```

Verdict:

```text
Use as an implementation detail only if the API endpoint shells out to the CLI
and surfaces raw verifier results. Do not make backend API logic a parallel
trust engine.
```

### Option C — Desktop-first Pake demo

Shape:

```text
Create a nice web page and package it with Pake before the CLI contract exists.
```

Optimizes:

```text
visual demo speed.
```

Tradeoff:

```text
High risk of UI inventing PASS/FAIL semantics, stale summaries, or overclaims.
```

Verdict:

```text
Rejected.
```

### Option D — Native Tauri app from scratch

Shape:

```text
Build a custom Tauri shell instead of Pake.
```

Optimizes:

```text
long-term desktop control, filesystem dialogs, local command invocation.
```

Tradeoff:

```text
Scope explodes into Rust/Tauri product engineering before the evaluator UX is
settled.
```

Verdict:

```text
Defer. If Pake cannot support the needed local workflow safely, graduate to a
custom Tauri shell in a later milestone.
```

### Option E — Report-only productization

Shape:

```text
Generate buyer_report.html and tell users to run scripts manually.
```

Optimizes:

```text
smallest code change.
```

Tradeoff:

```text
Does not solve the product interaction problem. A buyer still needs script
knowledge.
```

Verdict:

```text
Rejected as incomplete for MVP-5B.
```

## Decision

Use Option A:

```text
CLI-first evaluator
-> local web UI
-> Pake desktop shell
```

Pake is treated as a wrapper for the user-facing web surface, not as the trust
engine. Pake must never calculate verdicts, rewrite packages, or override CLI
and verifier results.

If Pake cannot directly provide safe folder selection or process invocation, the
fallback architecture is:

```text
local RDF backend process
-> serves the web UI
-> executes rdf CLI subprocesses
-> Pake wraps the localhost URL
```

That fallback still preserves the core rule:

```text
CLI/verifier is source of truth.
UI displays evidence.
```

## Product Boundary

### What this alpha should feel like

The user should be able to:

```text
1. Open RDF File-Drop Evaluator.
2. Choose or drag a folder/zip.
3. Select a profile explicitly.
4. Run preflight.
5. Run evaluation.
6. See PASS/FAIL and rejection reasons.
7. Open buyer_report.html.
8. Copy the exact verifier command.
9. Inspect generated TrustPack path.
```

### What this alpha must not do

The app must not:

```text
auto-trust unknown profiles
infer robot type silently
turn missing fields into warnings when the profile requires them
mark rejected data training eligible
allow cached buyer_report.json to override verifier output
hide verifier failure behind a UI success banner
rename digital-twin logs as external partner logs
```

## System Architecture

### Layering

```text
Desktop shell layer:
  Pake wrapper around local web UI.
  No trust logic.

Web UI layer:
  Human workflow, file selection, progress display, result display.
  No verdict computation.

Local evaluator API or command bridge:
  Runs RDF CLI subprocesses.
  Streams logs and returns structured JSON.
  Does not independently decide PASS/FAIL.

CLI layer:
  Owns profile selection, preflight, evaluation orchestration,
  TrustPack output, verifier invocation, report command.

Verifier layer:
  Owns package truth and PASS/FAIL.
  Recomputes from included evidence.
```

### Data flow

```text
input_path
  -> safe_input_resolver
  -> explicit profile_id
  -> preflight_result.json
  -> evaluation_result.json
  -> package_dir/
  -> verifier_result.json
  -> buyer_report.html
  -> UI session summary
```

### Trust source hierarchy

```text
1. Included evidence files
2. Verifier recomputation
3. Verifier exit code and structured report
4. CLI evaluation_result.json
5. UI display
```

The hierarchy is strict. Lower layers cannot override higher layers.

## CLI Contract

The implementation may start as:

```bash
uv run python scripts/rdf_file_drop_evaluator.py <subcommand>
```

It may later expose:

```bash
rdf <subcommand>
```

The spec uses `rdf` as the product command name, but the first implementation
may use the script path if packaging is not ready.

### Commands

#### `rdf profiles list`

Purpose:

```text
List supported explicit file-drop profiles.
```

Output JSON:

```json
{
  "schema_version": "rdf_file_drop_profiles_list_v0.1.0",
  "profiles": [
    {
      "profile_id": "ur_rtde_csv_v0",
      "robot_family": "universal_robots",
      "robot_model": "ur10e",
      "source_kind": "digital_twin_rehearsal_or_declared_file_drop",
      "requires_action_semantics": true
    }
  ]
}
```

#### `rdf profiles inspect <profile_id>`

Purpose:

```text
Show exact required files, fields, units, dimensions, action semantics, and
non-claims for one profile.
```

Hard rules:

```text
unknown profile -> non-zero exit
missing profile_id -> non-zero exit
```

#### `rdf preflight <folder-or-zip> --profile <profile_id> --json`

Purpose:

```text
Check file-drop shape before evaluation.
```

Checks:

```text
safe path
zip extraction safety
required files present
profile metadata present
source file hashes computable
required fields detectable
obvious forbidden claims absent
not in frozen proof package path unless explicitly allowed for corpus tests
```

Preflight does not certify training eligibility. It only decides whether the
input is well-formed enough to evaluate.

#### `rdf evaluate <folder-or-zip> --profile <profile_id> --out <dir> --json`

Purpose:

```text
Run the full file-drop evaluation path.
```

Expected behavior:

```text
valid golden input -> package generated, verifier run, buyer report generated
corrupt input -> structured rejection, no training-eligible export
```

The command must preserve rejected raw evidence when safe, but it must not
promote rejected data into training export.

#### `rdf verify <trustpack-dir> --deep-hdf5 --json`

Purpose:

```text
Run the relevant package verifier and return structured result.
```

For MVP-5A-ready packages, `--deep-hdf5` is required to open the ready claim.
The CLI must surface that requirement plainly.

#### `rdf report <trustpack-dir> --json`

Purpose:

```text
Locate or generate buyer-readable report artifacts.
```

Report generation must not change verifier verdict.

#### `rdf doctor --json`

Purpose:

```text
Check local prerequisites and supported commands.
```

Checks:

```text
Python version
repo root detected
required scripts available
MVP-5A verifier import-free/stdlib boundary preserved
write permission to output directory
optional Pake/web build availability
```

## CLI Result Schemas

### `preflight_result.json`

Required fields:

```json
{
  "schema_version": "rdf_file_drop_preflight_result_v0.1.0",
  "status": "preflight_passed",
  "profile_id": "ur_rtde_csv_v0",
  "input_path": "<user-supplied path redacted or normalized>",
  "input_kind": "folder",
  "source_file_hashes": [],
  "required_files_present": true,
  "issues": [],
  "warnings": [],
  "non_claims": {
    "external_partner_data_evaluated": false,
    "real_robot_data_evaluated": false,
    "hardware_readiness": false
  }
}
```

Allowed statuses:

```text
preflight_passed
preflight_failed
```

### `evaluation_result.json`

Required fields:

```json
{
  "schema_version": "rdf_file_drop_evaluation_result_v0.1.0",
  "status": "evaluation_passed",
  "profile_id": "ur_rtde_csv_v0",
  "input_kind": "folder",
  "package_dir": "artifacts/rdf_evaluator/<run_id>/package",
  "buyer_report_path": "artifacts/rdf_evaluator/<run_id>/package/buyer_report.html",
  "verifier": {
    "command": [
      "uv",
      "run",
      "python",
      "scripts/verify_mvp5a_pre_file_drop_chaos_rehearsal_package.py",
      "...",
      "--deep-hdf5"
    ],
    "exit_code": 0,
    "status": "VERIFIED"
  },
  "curation": {
    "accepted_count": 1,
    "rejected_count": 0,
    "rejection_reasons": []
  },
  "training_eligible": true,
  "non_claims": {
    "external_partner_data_evaluated": false,
    "real_robot_data_evaluated": false,
    "policy_uplift": false
  }
}
```

Allowed statuses:

```text
evaluation_passed
evaluation_failed
rejected_not_training_eligible
verifier_failed
```

### UI session log

Each UI-triggered run must persist:

```text
run_id
started_at
finished_at
input_path_display
profile_id
commands_executed
exit_codes
result_paths
```

The session log is audit convenience only. It is not a proof artifact.

## Supported Profiles for Alpha

The alpha must expose exactly the current MVP-5A-pre supported profiles unless
a later plan extends the profile registry:

```text
ur_rtde_csv_v0
franka_state_jsonl_v0
ros2_channel_bundle_jsonl_v0
generic_command_state_jsonl_v0
```

Profile rules:

```text
profile selection is explicit
unknown profile fails
missing profile fails
wrong profile declared for data fails
robot family/model mismatch fails
units missing fail
timestamp field missing fails
action semantics missing fails unless the profile explicitly supports state-only evaluation
```

## Input Safety Contract

### Folder input

The evaluator may read only under the selected folder root.

Reject:

```text
symlink escape
path traversal
absolute manifest paths
duplicate source IDs
duplicate artifact roles
profile_id used directly as unsafe path
```

### Zip input

Zip handling must:

```text
extract into a managed temp directory
reject ../ entries
reject absolute paths
reject symlinks or unsafe file types unless explicitly allowed
reject overwrite collisions
limit total extracted size for alpha
clean only managed temp/output directories
```

Zip handling must not:

```text
extract into repo root
overwrite proof packages
follow symlinks outside extraction root
```

## UI Design Requirements

### First screen

The first screen is the actual evaluator, not a landing page.

Must include:

```text
file/folder or zip input control
profile selector
preflight button
evaluate button disabled until preflight passes
short non-claim boundary
backend status
```

Avoid marketing hero layout. This is an operator/reviewer tool.

### Profile selector

For each profile show:

```text
profile_id
robot family/model
required files
state/action dimension
required units
action semantics
```

Do not show UR/Franka/ROS2 labels as live hardware support.

### Preflight view

Show:

```text
required file checklist
detected source hashes
profile metadata match/mismatch
issues
warnings
```

Preflight pass should use language like:

```text
Ready to evaluate
```

not:

```text
Verified
```

because verification happens later.

### Evaluation progress view

Show:

```text
current command
step status
stdout/stderr tail
elapsed time
cancel button if safe
```

Command output is diagnostic. The UI must not parse stdout as proof if a JSON
result and exit code are available.

### Result view

Show:

```text
verifier verdict
verifier exit code
package status
file_drop_rehearsal_ready or contract-ready status
accepted/rejected counts
top rejection reasons
TrustPack path
buyer report path
copy verifier command
open buyer report
open package folder
```

PASS language:

```text
Verifier PASS
```

FAIL language:

```text
Verifier FAILED
Rejected: <reason>
```

Do not use:

```text
Robot data valid
Robot ready
Hardware verified
Production ready
```

### Buyer report viewer

The UI may link to `buyer_report.html` or display it in a constrained iframe.

If displayed inline, still show:

```text
Report is explanatory.
Verifier output is source of truth.
```

### Non-claim display

Every result view must show:

```text
This alpha does not claim real robot success, external partner data evaluation,
hardware readiness, live UR/Franka/ROS2 support, policy uplift, or production
readiness.
```

This sentence must be covered by the negation-aware claim scanner.

## Pake Desktop Shell Boundary

Pake is suitable here only because the target shell is a web UI. Based on the
public Pake project positioning, it wraps webpages into lightweight desktop apps
with Rust/Tauri.

RDF-specific Pake constraints:

```text
Pake is not the evaluator.
Pake is not the verifier.
Pake does not compute PASS/FAIL.
Pake does not edit TrustPacks.
Pake wraps the local evaluator web surface.
```

Implementation may choose one of two safe launch models:

### Model 1 — User starts local backend, Pake wraps URL

```text
uv run python scripts/rdf_file_drop_evaluator_server.py
pake wraps http://127.0.0.1:<port>
```

Pros:

```text
lowest Pake integration risk
clear process boundary
easy browser-first development
```

Cons:

```text
less app-like at first
```

### Model 2 — Pake app starts or expects bundled local backend

```text
desktop app launches local backend or checks backend health
```

Pros:

```text
better user experience
```

Cons:

```text
requires more desktop packaging work
```

Alpha recommendation:

```text
Start with Model 1. Move to Model 2 only after CLI and browser UI are green.
```

## Local Web/API Boundary

If a local API is added for the UI, it must be a command bridge, not a second
verifier.

Allowed API endpoints:

```text
GET  /api/file-drop/profiles
GET  /api/file-drop/profiles/{profile_id}
POST /api/file-drop/preflight
POST /api/file-drop/evaluate
POST /api/file-drop/verify
GET  /api/file-drop/runs/{run_id}
GET  /api/file-drop/runs/{run_id}/logs
```

Endpoint rules:

```text
endpoints shell out to CLI or call the same narrow CLI orchestration module
endpoints return command, exit_code, stdout/stderr summary, and JSON result
endpoints do not recompute verifier verdict
endpoints do not edit packages after verifier pass/fail
```

## Output Directory Contract

Default output root:

```text
artifacts/rdf_file_drop_evaluator/
```

Run directory:

```text
artifacts/rdf_file_drop_evaluator/<timestamp_or_run_id>/
  input_receipt.json
  preflight_result.json
  evaluation_result.json
  verifier_result.json
  ui_session_log.jsonl
  package/
  logs/
```

The output root may be gitignored. Generated proof packages intended for review
must be copied deliberately into `docs/proof/...` in a separate step, not
silently.

## Package Boundary

The evaluator may generate two kinds of output:

### Diagnostic run artifact

Purpose:

```text
local debugging and UI display
```

Status:

```text
not necessarily externally reviewable
```

### TrustPack package

Purpose:

```text
self-contained verifier-backed review artifact
```

Status:

```text
externally reviewable if it includes verdict-critical evidence
```

The UI must label the difference. A diagnostic run artifact is not a proof
package unless the verifier package contract is satisfied.

## Rejection Reason Taxonomy

The CLI and UI should preserve structured reasons, not only generic failure.

Initial categories:

```text
profile_missing
profile_unknown
profile_mismatch
path_unsafe
source_hash_missing
required_file_missing
required_field_missing
timestamp_missing
timestamp_non_monotonic
timestamp_duplicate
timestamp_gap_large
unit_mismatch
dimension_mismatch
joint_order_mismatch
robot_metadata_missing
robot_model_mismatch
action_semantics_missing
state_only_not_allowed
target_actual_semantic_confusion
frame_id_missing
tf_static_missing
base_frame_drift
command_state_lag_high
safety_status_protective_stop
robot_mode_not_running
reset_boundary_inside_episode
nan_or_inf_value
fabricated_task_success_field
hdf5_export_ineligible
trainer_smoke_ineligible
verifier_failed
forbidden_claim_detected
```

The UI should show the category and the human explanation.

## Buyer-Facing Copy Contract

Required copy in app and generated reports:

```text
RDF File-Drop Evaluator Alpha evaluates recorded-log file drops through explicit
profiles and verifier-backed TrustPack checks.

This alpha does not prove real robot success, external partner data evaluation,
hardware readiness, live runtime support, policy uplift, or production
readiness.

Verifier output is the source of truth. UI summaries and buyer reports are
explanatory.
```

The claim scanner must allow negated non-claim text and reject positive
overclaim text.

## Test Strategy

### T1 — CLI profile tests

```text
profiles list returns exactly supported profiles
profiles inspect returns required fields and units
missing profile fails
unknown profile fails
profile path traversal fails
```

### T2 — Preflight tests

```text
golden folder preflight passes
golden zip preflight passes
missing required file fails
unsafe zip path fails
symlink escape fails
missing metadata fails
wrong profile declared fails
```

### T3 — Evaluation tests

```text
golden UR RTDE-style drop evaluates and verifies
golden Franka-style drop evaluates and verifies
golden ROS2 channel bundle drop evaluates and verifies
golden generic command-state drop evaluates and verifies
corrupt drops fail with expected rejection reason
rejected drops do not become training eligible
```

### T4 — Verifier source-of-truth tests

```text
tampered buyer report cannot make failed package pass
tampered evaluation_result cannot override verifier failure
tampered package manifest cannot override included evidence
UI-facing JSON preserves verifier exit code
ready package requires --deep-hdf5 where applicable
```

### T5 — Claim scanner tests

```text
positive forbidden claim in UI copy fails
positive forbidden claim in buyer_report.html fails
negated non-claim text does not fail
non_claims true fails
```

### T6 — Local web UI tests

```text
profile selector renders all supported profiles
evaluate button disabled until preflight passes
result view displays verifier exit code
result view displays non-claims
failure view displays rejection reason
UI does not display PASS unless verifier_result says VERIFIED and exit_code==0
```

### T7 — Pake shell smoke

```text
web UI can run in browser mode
Pake build or packaging command is documented
desktop shell opens local UI
desktop shell does not bypass CLI/verifier
```

If Pake packaging cannot run in CI, keep the Pake test as a documented local
smoke with a deterministic command and artifact path.

### T8 — Regression tests

```text
MVP-5A verifier still verifies checked package with --deep-hdf5
frozen MVP-2/MVP-3/MVP-4 verifier regressions remain green when lightweight
RDF TrustPack public dataset verifier remains green
git diff --check passes
```

## Acceptance Criteria

### A1 — CLI alpha

```text
User can run profile list/inspect/preflight/evaluate/verify/report commands.
```

### A2 — Four profile path

```text
All four MVP-5A-pre profiles have at least one golden local file-drop sample
that evaluates through the CLI and reaches verifier PASS.
```

### A3 — Corrupt path

```text
Defined corrupt samples fail closed with structured rejection reasons.
No corrupt sample becomes training eligible.
```

### A4 — Trust boundary

```text
Verifier exit code and structured verifier output are the only source of PASS.
UI and buyer report cannot override verifier result.
```

### A5 — Web UI alpha

```text
Browser UI can select input/profile, run preflight/evaluation, display result,
open buyer report, and copy verifier command.
```

### A6 — Pake shell alpha

```text
Pake-wrapped desktop shell can open the local evaluator UI or documented
localhost workflow.
```

### A7 — Claim boundary

```text
All UI/report/docs non-claims are present and machine-scanned.
Positive forbidden claims fail tests.
```

### A8 — No heavy runtime requirement

```text
Alpha tests do not require live Isaac, live ROS2/DDS, real robot hardware,
HMD/OpenXR, network, or long training.
```

### A9 — Documentation

```text
docs/developer/worklog.md, Handoff.md, debugging guide, and user runbook explain
the CLI/UI flow and claim boundary.
```

### A10 — Clean verification

```text
focused tests pass
web lint/build passes if touched
compileall passes for touched Python
ruff passes for touched Python
git diff --check passes
```

## Implementation Phases

### Phase 0 — Baseline confirmation

Required before implementation:

```text
PR #13 merged or current branch contains verified MVP-5A ready package.
MVP-5A verifier passes with --deep-hdf5.
Current supported profile registry is confirmed.
```

### Phase 1 — CLI evaluator v0

Deliver:

```text
scripts/rdf_file_drop_evaluator.py or equivalent
profile list/inspect/preflight/evaluate/verify/report/doctor subcommands
structured JSON outputs
```

### Phase 2 — File-drop corpus v0

Deliver:

```text
tiny golden samples for four profiles
tiny corrupt samples for representative failures
corpus manifest with expected pass/fail and rejection reason
```

The corpus may live under a test fixture directory if not intended as a proof
artifact.

### Phase 3 — Local web UI

Deliver:

```text
apps/web file-drop evaluator page
local command bridge/API
profile selector
preflight/evaluate/result views
claim boundary copy
```

### Phase 4 — Pake desktop shell

Deliver:

```text
documented Pake packaging command or script
desktop smoke instructions
manifest of app role and non-claims
```

### Phase 5 — Partner intake kit

Deliver:

```text
docs/partner_intake/README.md
docs/partner_intake/ur_rtde_file_drop_request.md
docs/partner_intake/franka_file_drop_request.md
docs/partner_intake/ros2_channel_bundle_file_drop_request.md
docs/partner_intake/generic_command_state_file_drop_request.md
docs/partner_intake/file_drop_triage_runbook.md
```

These docs must match the actual supported profile contracts.

### Phase 6 — Blind local dry run

Deliver:

```text
clean checkout or fresh output-dir run
golden pass
corrupt fail
buyer report opens
verifier command reproducible
```

## Stop Conditions

Stop and re-plan if:

```text
Pake requires weakening file/path safety
Pake cannot support a local-only alpha without unsafe shortcuts
UI needs to compute PASS/FAIL independently to work
CLI cannot expose structured verifier output
profile validation would need to be weakened
zip/folder handling cannot be made path-safe
corrupt samples silently pass
buyer report or UI needs positive forbidden claims
implementation would call generated digital-twin logs external partner data
implementation requires live robot, live ROS2, live Isaac, or HMD runtime
```

## Pre-Mortem

### Failure 1 — UI becomes a second verifier

Symptom:

```text
React/Next code computes PASS from report fields or inferred counts.
```

Mitigation:

```text
UI displays only CLI/verifier JSON and exit code. Add tests that a failed
verifier cannot show a green PASS.
```

### Failure 2 — Desktop app overclaims because it looks polished

Symptom:

```text
User reads desktop UI as production-ready robot data certification.
```

Mitigation:

```text
Alpha label, non-claim footer, claim scanner, and buyer report boundary.
```

### Failure 3 — Pake integration drives architecture

Symptom:

```text
Code is shaped around desktop packaging before CLI contract is stable.
```

Mitigation:

```text
Browser-first web UI. Pake only after CLI and local web UI pass.
```

### Failure 4 — Path handling becomes dangerous

Symptom:

```text
Zip extraction or folder selection can escape roots or overwrite artifacts.
```

Mitigation:

```text
Temp extraction root, safe path resolver, path traversal tests, symlink tests.
```

### Failure 5 — Diagnostic artifact mistaken for proof artifact

Symptom:

```text
Local run folder is treated as externally reviewable TrustPack without
self-contained evidence.
```

Mitigation:

```text
Separate diagnostic run artifact from verifier-backed package. Label both in UI.
```

## Required Verification Commands

Minimum expected final verification:

```bash
uv run pytest -q apps/api/tests/test_mvp5a_pre_file_drop_profiles.py \
  apps/api/tests/test_mvp5a_pre_file_drop_package_and_verifier.py \
  apps/api/tests/test_mvp5a_pre_frozen_verifier_regressions.py

uv run python scripts/verify_mvp5a_pre_file_drop_chaos_rehearsal_package.py \
  docs/proof/mvp5a_pre_digital_twin_file_drop_chaos_rehearsal_package/package_manifest.json \
  --deep-hdf5

uv run pytest -q <new file-drop evaluator tests>

uv run python -m compileall <touched Python files>
uvx ruff check <touched Python files>

cd apps/web && npm run lint
cd apps/web && npm run build

git diff --check
```

If `npm run build` is too slow for normal iteration, it is still required before
claiming the web/desktop alpha complete.

## Open Questions for RALPLAN

### Q1 — CLI location

Options:

```text
A. scripts/rdf_file_drop_evaluator.py first, package entrypoint later.
B. Add installable `rdf` console script now.
```

Recommendation:

```text
A for first slice. It matches the repo's current script-heavy proof pattern and
avoids packaging churn.
```

### Q2 — Local web bridge

Options:

```text
A. FastAPI local endpoint shells out to CLI.
B. Next.js server action shells out.
C. Separate tiny Python local server for evaluator commands.
```

Recommendation:

```text
A if existing apps/api startup is lightweight enough. C if API server scope
would pull unrelated backend concerns. Avoid B unless process execution security
is explicitly contained.
```

### Q3 — Pake implementation depth

Options:

```text
A. Documented Pake wrapper command for localhost UI.
B. Checked-in packaging script that builds a desktop shell.
C. Custom Tauri app.
```

Recommendation:

```text
A for first alpha, B after browser UI is stable, C only if Pake blocks core UX.
```

### Q4 — Partner intake kit in same milestone

Options:

```text
A. Include as Phase 5 of MVP-5B.
B. Split into MVP-5C docs milestone.
```

Recommendation:

```text
Include minimal kit in MVP-5B because the stated goal is pre-real-log product
readiness. Keep it strictly aligned to current profiles.
```

### Q5 — Test corpus location

Options:

```text
A. apps/api/tests/fixtures/file_drop_corpus/
B. docs/proof/.../test_corpus/
C. artifacts/ generated only
```

Recommendation:

```text
A for tiny deterministic test fixtures. Generated heavy outputs stay under
artifacts/ and are not committed.
```

## Final Claim Boundary

When complete, the milestone may claim:

```text
RDF has a local file-drop evaluator alpha that routes explicit recorded-log
profiles through the CLI/verifier trust boundary and displays verifier-backed
results in a web/desktop shell.
```

It may not claim:

```text
RDF has evaluated real external partner robot data.
RDF is hardware ready.
RDF supports live UR/Franka/ROS2 runtime.
RDF proves policy uplift on these file drops.
RDF is production-certified.
```

## References

```text
Pake: https://github.com/tw93/Pake
MVP-5A L2/L3 close spec:
docs/superpowers/specs/2026-06-26-mvp5a-l2-l3-capture-edge-evidence-close-design.md
Current MVP-5A verifier:
scripts/verify_mvp5a_pre_file_drop_chaos_rehearsal_package.py
Current MVP-5A service:
apps/api/app/services/mvp5a_file_drop_rehearsal.py
```
