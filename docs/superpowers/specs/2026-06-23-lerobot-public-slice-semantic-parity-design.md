# Spec: LeRobot Public Slice Semantic Parity

Date: 2026-06-23
Status: BRAINSTORMING SPEC DRAFT; NOT IMPLEMENTED
Branch: `codex/lerobot-public-slice-semantic-parity`

## Objective

이번 slice의 목적은 `external_ingest_contract_ready`에서 멈춰 있는 외부 데이터
평가 경로를 실제 public robot-learning source로 한 단계 여는 것이다.

증명하려는 것은 다음 하나다.

```text
Given a deterministic audited slice from a public LeRobot dataset, RDF can
preserve public source binding, convert source state/action rows into RDF's
normalized data trust layer without fabricating missing semantics, export the
eligible slice, run trainer smoke, and ship a verifier package that recomputes
the source -> RDF semantic parity from included evidence.
```

이번 slice는 다음을 증명하지 않는다.

```text
full LeRobot parser support
full dataset evaluation
real robot success
physical robot readiness
live hardware support
ROS2-DDS / RTDE / Franka bridge readiness
visual policy performance
policy uplift
learning-proven value
deployable policy readiness
```

## Current Repo Facts

- `docs/proof/external_robot_data_ingest_eval_v0_proof_package/` currently
  verifies as `external_ingest_contract_ready`.
- `scripts/verify_external_robot_data_ingest_package.py` intentionally rejects
  `external_data_evaluated` until semantic parity artifacts exist.
- Existing external ingest code assumes an RDF JSONL command/state drop.
- Existing `RobotEmbodimentAdapterRegistry.project_source_evidence()` path is
  industrial-arm command/state oriented and expects fields such as EEF pose,
  object pose, joint positions, and task-frame action semantics.
- LeRobot public datasets expose state/action features that may not contain
  RDF's EEF/object pose fields.
- Existing `scripts/export_rdf_to_hdf5.py` and
  `scripts/run_mvp1_trainer_smoke.py` can prove trainer-loadable data only when
  the exported HDF5 preserves the expected observation/action semantics.

Important implication:

```text
Do not force LeRobot rows through the existing UR-style external JSONL schema by
inventing EEF pose, object pose, robot family, or task semantics that the source
does not provide.
```

## External Source Facts

LeRobot v3 official documentation describes a robot-learning dataset format with
tabular state/action/timestamp data in Parquet, visual streams in MP4, and
metadata describing schema, FPS, and episode segmentation.

Public candidate datasets:

```text
Primary candidate:
  repo_id=lerobot/aloha_static_coffee
  public page reports:
    license=mit
    robot_type=aloha
    rows=55,000
    total_file_size=1.57GB
    observation.state shape=14
    action shape=14

Fallback candidate:
  repo_id=lerobot/pusht
  public page reports:
    license=mit
    robot_type=unknown
    rows=25,650
    total_file_size=7.69MB
    observation.state shape=2
    action shape=2
```

`lerobot/aloha_static_coffee` is preferred because it is a real robot learning
dataset with robot-type and high-dimensional motor state/action features. Its
size means this slice must use a deterministic audited slice, not a full dataset
verdict.

`lerobot/pusht` is useful as a tiny fallback smoke source, but its
`robot_type=unknown` and 2D PushT state/action semantics make it weaker for the
Robot Data Forge external robot data claim.

## Brainstorming Options

### Option A: ALOHA Public Audited Slice

```text
source_kind=public_lerobot_aloha_audited_slice
dataset=lerobot/aloha_static_coffee
slice=deterministic frame subset from a pinned dataset revision
```

Optimizes:

- Strongest first public-source claim without requiring live hardware.
- Public source URL, revision, license, and upstream file hashes can be recorded.
- State/action vectors are high-dimensional enough to exercise meaningful
  contract, export, and trainer-smoke paths.
- Lets RDF move past self-attested file drops into refetchable public evidence.

Tradeoff:

- Full dataset is large, so verdict must be scoped to the included audited slice.
- Requires a LeRobot/Parquet extraction producer path.
- Public dataset may not include rejected/failure examples; no rejected external
  source row may be fabricated.

### Option B: PushT Tiny Public Slice

```text
source_kind=public_lerobot_pusht_tiny_slice
dataset=lerobot/pusht
```

Optimizes:

- Very small source and likely easiest to download.
- Good for testing public-source binding and basic state/action conversion.

Tradeoff:

- Robot source credibility is weaker.
- 2D state/action semantics are less representative of robot manipulation data.
- If this path is used, the milestone must be renamed to a tiny format smoke,
  not portfolio-level external robot data evaluation.

### Option C: Full Native LeRobot Parser

```text
source_kind=native_lerobot_parser
scope=general LeRobot v2/v3 parser and arbitrary dataset support
```

Optimizes:

- Most complete product path.

Tradeoff:

- Too broad for this slice.
- Requires dependency and format support decisions across LeRobot versions,
  Parquet layouts, videos, and metadata variants.
- Risks turning the task into dataset archaeology instead of proving RDF trust
  semantics.

### Option D: Wait For Partner UR JSONL

```text
source_kind=attested_file_drop_only
```

Optimizes:

- Avoids new dependencies.
- Reuses the existing JSONL ingest shape.

Tradeoff:

- Does not solve the self-attestation ceiling.
- Delays the first independently refetchable public-source proof.

## Decision

Use **Option A: ALOHA Public Audited Slice**.

The implementation should create a new proof package rather than mutating the
contract-ready package in place:

```text
docs/proof/lerobot_public_aloha_slice_semantic_parity_proof_package/
```

Expected status:

```text
package_status=external_data_evaluated
source_kind=public_lerobot_aloha_audited_slice
external_source_included=true
provenance_trust_tier=refetchable_public_source
audited_slice_verdict_claimed=true
full_source_verdict_claimed=false
```

If ALOHA cannot be fetched, licensed, parsed, or represented without semantic
fabrication, the implementation must stop before claim unlock. It may produce a
contract/addendum artifact, but it must not claim `external_data_evaluated`.

## Claim Boundary

Allowed claim:

```text
Robot Data Forge evaluated a deterministic audited slice from a public LeRobot
dataset through source binding, semantic conversion, normalized contract,
curation/export checks, trainer smoke, and an independent verifier package.
```

Disallowed claims:

```text
RDF evaluated the full ALOHA dataset
RDF supports all LeRobot datasets
RDF proves real robot success
RDF proves physical robot readiness
RDF proves live ALOHA / UR / Franka / ROS / RTDE support
RDF proves visual policy performance
RDF proves policy uplift
RDF proves deployable policy readiness
RDF proves sim-to-real
```

The buyer-facing language must use "public dataset source binding" or
"public LeRobot audited slice", not "RDF proved this came from a real robot."

## Source Binding Contract

The package must include public-source coordinates:

```json
{
  "repo_id": "lerobot/aloha_static_coffee",
  "source_url": "https://huggingface.co/datasets/lerobot/aloha_static_coffee",
  "resolved_revision": "<pinned commit or immutable revision>",
  "license": "mit",
  "dataset_card_robot_type": "aloha",
  "dataset_card_rows": 55000,
  "dataset_card_total_file_size": "1.57GB",
  "full_dataset_verdict_claimed": false,
  "audited_slice_verdict_claimed": true
}
```

The implementation must resolve a concrete dataset revision. Floating `main` is
not sufficient for a proof package.

The package must record hashes for the upstream files used to extract the slice:

```text
meta/info.json
selected data parquet file(s)
optional meta/tasks or episode metadata files if used
```

Package generation must perform one successful public-source refetch check and
write a receipt into the package:

```text
data/source/refetch_receipt.json
```

The receipt must include:

```text
checked_at_utc
repo_id
resolved_revision
source_url
files_checked[]
declared_sha256
refetched_sha256
matched=true
```

Default verification remains offline: it validates that the receipt exists,
that every checked file points at the pinned revision, and that every
`declared_sha256` equals `refetched_sha256`. A reviewer may rerun the network
check later:

```text
--refetch-public-source
  fetch declared public files and compare sha256
```

`--refetch-public-source` is useful but not required for default CI because it
depends on network availability. The offline package claim must say:

```text
default verifier = internal semantic parity + recorded refetch receipt consistency
network origin re-check = --refetch-public-source
```

Package generation must also perform one producer-independent public-source
re-extraction check and write:

```text
data/source/extraction_receipt.json
```

This receipt binds the included raw JSONL rows to the pinned upstream Parquet
source at concrete slice coordinates. It must include:

```text
checked_at_utc
repo_id
resolved_revision
source_file
slice_rule
episode_index
frame_start
frame_count
feature_schema_sha256
extractor_implementation="independent_public_source_reextractor"
canonical_row_digest_algorithm="json.dumps(sort_keys=True,separators=(',',':'),ensure_ascii=False)+sha256"
reextract_command
dependency_versions
source_file_byte_sha256
raw_row_sha256s[]
included_raw_jsonl_sha256
reextracted_raw_jsonl_sha256
matched=true
```

Default verification remains stdlib-only and checks the receipt's internal
consistency, row digest list, coordinates, and equality between included and
re-extracted row digests. A stronger reviewer mode may rerun the re-extraction:

```text
--reextract-public-source
  fetch pinned upstream source files, re-extract the declared slice with the
  independent extraction path, and compare raw JSONL row digests
```

`external_data_evaluated` may not be claimed without this extraction receipt.

## Audited Slice Contract

The source slice must be selected by a deterministic predeclared rule:

```json
{
  "slice_rule": "first_episode_first_n_frames",
  "episode_index": 0,
  "frame_start": 0,
  "frame_count": 8,
  "reason": "small deterministic public-source slice for semantic parity proof"
}
```

If the selected episode/frame range is not available, the runner must fail
closed rather than silently choosing another range.

The verifier can prove internal slice consistency from included JSON evidence.
It cannot prove from stdlib alone that the JSON rows were extracted correctly
from Parquet. That gap is closed by:

```text
1. public source coordinates + upstream file hashes;
2. included raw LeRobot row JSON;
3. deterministic slice rule;
4. optional refetch/re-extract reviewer procedure.
```

The package must disclose:

```text
full_source_verdict_claimed=false
audited_slice_verdict_claimed=true
cherry_pick_elimination=bounded_by_slice_rule_and_public_refetch_binding
```

## Included Evidence Contract

The proof package must include enough small evidence for offline recomputation:

```text
data/source/public_source_binding.json
data/source/upstream_file_hashes.json
data/source/refetch_receipt.json
data/source/extraction_receipt.json
data/source/slice_selection_report.json
data/source/lerobot_raw_rows.jsonl
data/source/lerobot_feature_schema.json
data/source/LICENSE.txt
data/conversion/rdf_converted_rows.jsonl
data/conversion/semantic_mapping_report.json
data/conversion/conversion_manifest.json
data/contracts/normalized_state_action_contract.json
data/contracts/validator_report.json
data/export/dataset.hdf5
data/export/hdf5_inspection_report.json
data/export/deep_hdf5_receipt.json
data/export/trainer_smoke_report.json
data/reports/buyer_data_evaluation_report.json
data/non_claims_attestation.json
data/artifact_index.json
package_manifest.json
README.md
```

`lerobot_raw_rows.jsonl` is the source of truth for default semantic parity
verification. Summaries, buyer reports, and package manifests are indexes only.

## Raw Row Schema

Each included LeRobot raw row must preserve the source semantics:

```json
{
  "repo_id": "lerobot/aloha_static_coffee",
  "resolved_revision": "...",
  "source_file": "data/chunk-000/episode_000000.parquet",
  "episode_index": 0,
  "frame_index": 0,
  "timestamp": 0.0,
  "task_index": 0,
  "observation.state": [0.0],
  "action": [0.0],
  "next.done": false,
  "source_row_sha256": "..."
}
```

Required raw fields:

```text
repo_id
resolved_revision
source_file
episode_index
frame_index
timestamp
observation.state
action
```

Optional raw fields:

```text
task_index
index
next.done
next.success
observation.effort
```

The verifier must reject:

```text
missing observation.state
missing action
non-numeric state/action values
dimension drift across rows
non-monotonic timestamp within an episode
episode/frame indices that contradict the declared slice rule
```

## Semantic Mapping Contract

The conversion must not fabricate missing physical fields.

Allowed mapping:

```text
LeRobot observation.state -> RDF observation_state vector
LeRobot action            -> RDF learning_action vector
timestamp                 -> RDF frame timestamp
episode_index/frame_index -> RDF episode/frame provenance
task_index                -> RDF task provenance if present
```

Forbidden mapping:

```text
fabricated end_effector_position
fabricated end_effector_quaternion
fabricated object_position
fabricated object_quaternion
mislabeling ALOHA as UR/Franka
claiming task success from absent success labels
claiming real robot readiness from dataset provenance
```

The RDF converted row shape should be generic state/action, not UR-style
command/state:

```json
{
  "schema_version": "rdf_public_lerobot_state_action_row_v0.1.0",
  "source_kind": "public_lerobot_dataset_slice",
  "source_robot_type": "aloha",
  "episode_index": 0,
  "frame_index": 0,
  "timestamp": 0.0,
  "observation_state": [0.0],
  "learning_action": [0.0],
  "action_semantics": {
    "representation": "lerobot_action_vector",
    "coordinate_frame": "source_dataset_native_frame",
    "normalized_contract_roles": [
      "source_action",
      "learning_action"
    ]
  },
  "quality": {
    "state_action_numeric": true,
    "timestamp_monotonic": true,
    "dimension_consistent": true,
    "accepted_for_export": true,
    "rejection_reason": null
  }
}
```

## Contract / Export Boundary

Do not weaken `NormalizedTrajectoryContractValidator` to accept ambiguous data.

Preferred implementation:

```text
Create a dedicated generic state/action contract path:
  LeRobotStateActionContractValidator
  or a narrowly scoped extension of NormalizedTrajectoryContractValidator
  that has explicit state/action vector semantics.
```

The contract must say:

```text
source format = LeRobot public dataset slice
robot type = aloha
observation state dimension = 14 for ALOHA candidate
action dimension = 14 for ALOHA candidate
visual data ignored for this slice
camera/visual policy readiness = false
task success labels = not measured unless source row includes supported label
```

HDF5 export and trainer smoke must use the generic state/action arrays directly.
They must not satisfy the old trainer smoke by inserting fake EEF/object fields.

## Accepted / Rejected Evidence Policy

Many public demonstration datasets contain successful demonstrations but do not
carry RDF-style rejected examples. This slice must not fabricate rejected
external rows.

If the selected LeRobot source has no failure/rejected labels:

```text
canonical_source_rejected_examples_present=false
accepted_slice_evaluated=true
accepted_rejected_pair_claimed=false
```

The package may still include tamper tests in the test suite that produce
rejected/failed verifier cases, but those are not external rejected source
examples.

If the selected source has native failure labels later, rejected rows may be
included only when the labels are present in source evidence and hash-bound.

## Verifier Design

Create a dedicated verifier:

```text
scripts/verify_lerobot_public_slice_package.py
```

Default verifier requirements:

```text
stdlib-only
no import from producer converter
no import from RDF service modules
no pyarrow/pandas/datasets/lerobot/h5py/numpy in default mode
```

Default verifier recomputes:

- package artifact hashes;
- public source binding fields;
- upstream file hash declarations are present and sha256-shaped;
- `refetch_receipt.json` exists and records one successful pinned-revision hash
  match for every upstream file used by the audited slice;
- `extraction_receipt.json` exists and records one successful independent
  re-extraction of the declared slice from pinned upstream files into raw row
  digests matching `lerobot_raw_rows.jsonl`;
- resolved revision is not floating `main`;
- license and source URL are present;
- slice selection rule is present and deterministic;
- raw LeRobot rows match slice rule;
- raw rows have numeric, dimension-consistent `observation.state` and `action`;
- timestamps are monotonic per episode;
- converted RDF rows are deterministically derived from raw rows;
- no forbidden fabricated fields appear in converted rows;
- semantic mapping report matches recomputed mapping;
- contract report agrees with raw/conversion counts and dimensions;
- buyer report does not overclaim full dataset support or real robot readiness;
- non-claim keys are present and false;
- spent ranges `40000-40049` and `42000-42049` are not reused in any seed-like
  field;
- summary/package JSON do not become the source of truth.

Optional deep mode:

```text
--deep-hdf5
  use project dependencies h5py/numpy to inspect included HDF5 and verify
  state/action arrays match converted RDF rows.
```

Package generation should run `--deep-hdf5` once and write
`data/export/deep_hdf5_receipt.json`. Default verification checks the receipt's
presence and internal consistency; `--deep-hdf5` lets reviewers re-run the
stronger HDF5 comparison locally when dependencies are available.

Optional refetch mode:

```text
--refetch-public-source
  use network access to fetch declared upstream files and compare sha256.
```

Optional re-extraction mode:

```text
--reextract-public-source
  use network access plus optional public-source dependencies to fetch pinned
  source files, re-extract the declared rows, and compare raw row digests.
```

Deep/refetch modes are stronger reviewer aids. Default CI can remain offline and
stdlib-only. `--reextract-public-source` is the strongest provenance check for
the Parquet -> included raw JSONL boundary.

## Verifier Hard-Fail Cases

The verifier must fail if:

- `external_data_evaluated` is claimed without included raw LeRobot rows;
- only hashes to local ignored storage are present;
- `resolved_revision` is missing or floating;
- source URL/license/repo id are missing;
- `refetch_receipt.json` is missing, points at a floating revision, omits an
  upstream file, or records any hash mismatch;
- `extraction_receipt.json` is missing, points at a floating revision, has
  slice coordinates that disagree with the slice report, or records raw row
  digests that do not match included raw rows;
- raw rows do not satisfy the deterministic slice rule;
- converted rows contain fabricated EEF/object pose fields;
- converted rows relabel `aloha` as UR, Franka, ROS2, Isaac, or RTDE;
- `observation.state` or `action` dimensions drift;
- raw and converted counts differ;
- timestamp order is broken;
- hash refresh hides a raw/conversion/contract mismatch;
- buyer report claims full dataset support when only a slice is included;
- buyer report claims real robot success, physical readiness, live hardware
  support, policy uplift, deployment, marketplace, production, or sim-to-real;
- rejected source examples are claimed when no native rejected source evidence is
  included.

## Package Status

Expected final package:

```text
package_status=external_data_evaluated
source_kind=public_lerobot_aloha_audited_slice
external_source_included=true
accepted_slice_evaluated=true
canonical_source_rejected_examples_present=false
accepted_rejected_pair_claimed=false
full_source_verdict_claimed=false
audited_slice_verdict_claimed=true
```

If implementation must fallback to PushT:

```text
package_status=public_lerobot_tiny_format_smoke
source_kind=public_lerobot_pusht_tiny_slice
external_data_evaluated=false
```

The fallback name is intentionally weaker to avoid making the same claim with a
less representative source.

## Implementation Components

This spec does not authorize implementation yet. Likely components:

```text
C1 LeRobot public source resolver
   - resolve repo id, revision, license, metadata paths, selected upstream files

C2 LeRobot audited slice extractor
   - optional producer dependency path for Parquet reading
   - outputs small raw row JSONL evidence

C3 LeRobot -> RDF state/action converter
   - deterministic mapping, no fabricated fields

C4 Generic state/action contract + HDF5 export/trainer smoke
   - preserve observation.state/action semantics

C5 Proof package builder
   - self-contained small evidence, source binding, reports, non-claims

C6 Independent verifier
   - stdlib default semantic parity checks
   - optional --deep-hdf5 and --refetch-public-source

C7 Tamper tests and docs
   - hash refreshed drift, fabricated fields, overclaim text, revision drift
```

Dependency guidance:

```text
Do not add heavyweight LeRobot dependencies to the core app unless the plan
explicitly justifies it.

Prefer producer-only optional execution such as:
  uv run --with pyarrow --with huggingface_hub ...

The verifier default path must remain stdlib-only.
```

## Testing Strategy

Tests should be TDD-first.

Add tests for:

- raw LeRobot row fixture -> converted RDF rows;
- conversion rejects missing state/action;
- conversion rejects fabricated EEF/object fields;
- slice selection rule is enforced;
- ALOHA dimension metadata is preserved;
- generic state/action contract passes valid rows;
- generic state/action contract fails dimension drift;
- HDF5/trainer smoke preserves state/action arrays;
- refetch receipt is present and internally consistent;
- extraction receipt is present and internally consistent;
- deep HDF5 receipt is present and internally consistent;
- package includes raw rows, not only hashes;
- verifier recomputes raw -> converted semantic parity;
- verifier fails on hash-refreshed raw row tamper;
- verifier fails on hash-refreshed converted row tamper;
- verifier fails on fabricated EEF/object fields;
- verifier fails on floating revision;
- verifier fails on missing or mismatched refetch receipt;
- verifier fails on missing or mismatched extraction receipt;
- verifier fails on missing or mismatched deep HDF5 receipt;
- verifier fails if full dataset verdict is claimed for an audited slice;
- verifier fails if rejected examples are claimed without source labels;
- verifier fails forbidden claim leakage in JSON and README/report text;
- frozen MVP-2/MVP-3A/MVP-3B/MVP-3C verifiers still pass.

## Verification Commands

Expected commands after implementation:

```bash
uv run pytest -q apps/api/tests/test_lerobot_public_slice_semantic_parity.py
uv run pytest -q apps/api/tests/test_verify_lerobot_public_slice_package.py

python3 scripts/verify_lerobot_public_slice_package.py \
  docs/proof/lerobot_public_aloha_slice_semantic_parity_proof_package/package_manifest.json

python3 scripts/verify_lerobot_public_slice_package.py --deep-hdf5 \
  docs/proof/lerobot_public_aloha_slice_semantic_parity_proof_package/package_manifest.json

python3 scripts/verify_external_robot_data_ingest_package.py \
  docs/proof/external_robot_data_ingest_eval_v0_proof_package/package_manifest.json

python3 scripts/verify_mvp2_package.py \
  docs/proof/mvp2_learning_proven_evidence_package/package_manifest.json

python3 scripts/verify_proof_package.py \
  docs/proof/mvp3a_target_fixture_pose_variant_proof_package/package_manifest.json

python3 scripts/verify_mvp3b_source_adapter_package.py \
  docs/proof/mvp3b_source_adapter_matrix_proof_package/package_manifest.json

python3 scripts/verify_mvp3c_isaac_sim_embodiment_source_package.py \
  docs/proof/mvp3c_isaac_sim_embodiment_source_proof_package/package_manifest.json

uv run ruff check <touched files>
python3 -m compileall <touched scripts/services/tests>
git diff --check
```

## Stop Conditions

Stop before claiming `external_data_evaluated` if:

- ALOHA cannot be fetched or revision-pinned;
- license/provenance cannot be verified from the public dataset page;
- selected upstream files cannot be hash-bound;
- public-source refetch receipt cannot be produced;
- independent public-source extraction receipt cannot be produced;
- Parquet extraction would require committing large source files;
- only hashes are available and no raw row evidence is included;
- raw LeRobot rows cannot be converted without fabricating EEF/object/task
  success fields;
- HDF5/trainer smoke requires erasing source semantics;
- verifier cannot recompute raw -> converted parity from included evidence;
- source has no rejected labels and the package tries to claim rejected external
  examples;
- package/report/README leaks real robot readiness, full dataset evaluation,
  policy uplift, deployment, production, marketplace, or sim-to-real claims.

## Success Criteria

The slice is successful only if:

```text
1. a pinned public LeRobot ALOHA source binding exists;
2. a deterministic audited slice is included as raw row JSONL evidence;
3. RDF converted rows are derived without semantic fabrication;
4. a generic state/action contract is emitted and verified;
5. eligible state/action data exports to HDF5;
6. trainer smoke passes on the included slice;
7. `refetch_receipt.json` records one successful pinned-revision hash check;
8. `extraction_receipt.json` records one successful independent re-extraction
   of the declared slice into matching raw row digests;
9. `deep_hdf5_receipt.json` records one successful HDF5 state/action comparison;
10. a self-contained proof package is tracked under docs/proof/;
11. default verifier recomputes semantic parity offline;
12. optional deep HDF5 verifier passes when project dependencies are available;
13. optional re-extraction verifier passes when network/dependencies are available;
14. forbidden claims remain false;
15. older MVP proof verifiers remain green.
```

## References

- Repo-local:
  - `docs/superpowers/specs/2026-06-23-external-robot-data-ingest-evaluation-v0-design.md`
  - `scripts/verify_external_robot_data_ingest_package.py`
  - `apps/api/app/services/external_robot_data_ingest.py`
  - `apps/api/app/services/normalized_trajectory_contract.py`
  - `scripts/export_rdf_to_hdf5.py`
  - `scripts/run_mvp1_trainer_smoke.py`
- External:
  - LeRobotDataset v3.0 documentation:
    `https://huggingface.co/docs/lerobot/en/lerobot-dataset-v3`
  - LeRobot porting documentation:
    `https://huggingface.co/docs/lerobot/en/porting_datasets_v3`
  - `lerobot/aloha_static_coffee` dataset page:
    `https://huggingface.co/datasets/lerobot/aloha_static_coffee`
  - `lerobot/pusht` dataset page:
    `https://huggingface.co/datasets/lerobot/pusht`
