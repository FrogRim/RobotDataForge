# Spec: LeRobot Public Dataset Matrix Semantic Parity

Date: 2026-06-24
Status: BRAINSTORMING SPEC DRAFT; NOT IMPLEMENTED
Branch: TBD (new feature branch; do not work on `main`)

## Objective

mvp4a-v0.1은 단일 public dataset(`lerobot/aloha_static_coffee`)의 8-row audited
slice가 RDF external public dataset ingest 경로를 통과함을 증명했다. 그 한 번이
**ALOHA 특수 케이스인가, 아니면 RDF의 external public dataset ingest 패턴이 반복
가능한가**가 다음 질문이다.

이번 slice는 그 반복성을 증명한다.

```text
Given two distinct public LeRobot real-robot datasets — the existing bimanual
ALOHA profile and a new single-arm profile with a different robot_type and
different state/action dimensions — RDF can ingest each as a deterministic
audited slice with refetchable public binding, convert source state/action rows
without fabricating missing semantics, emit a generic state/action contract,
export and trainer-smoke the eligible slice, and ship one self-contained matrix
proof package that a single independent stdlib verifier recomputes profile by
profile. This proves the external public dataset ingest pattern repeats across
different embodiments, not just one dataset family.
```

이번 slice는 다음을 증명하지 않는다.

```text
all LeRobot datasets 지원 (오직 pinned 2 프로파일)
generic LeRobot parser
full dataset evaluation
real robot success / physical robot readiness
live hardware / RTDE / ROS2-DDS / Franka bridge readiness
visual policy performance / policy uplift / learning-proven value
deployable policy readiness / sim-to-real / marketplace / production
```

## Current Repo Facts

- `docs/proof/lerobot_public_aloha_slice_semantic_parity_proof_package/` verifies as
  `external_data_evaluated` and is tagged `mvp4a-v0.1-lerobot-public-aloha-slice-semantic-parity`.
- `scripts/verify_lerobot_public_slice_package.py` hardcodes ALOHA constants at
  module level and its own comment says a second dataset must add an **explicit
  slice profile**, not weaken the constants into implicit generic support.
- The aloha v0.1 default verifier already enforces, offline and stdlib-only:
  pinned 40-char revision, `refetch_receipt`, `extraction_receipt`, and a
  `deep_hdf5_receipt` plus a float32 byte-search that confirms the HDF5 contains
  the converted observation/action payload exactly once.
- MVP-3B (`scripts/verify_mvp3b_source_adapter_package.py`) is the established
  "matrix" precedent: a `REQUIRED_ADAPTERS` set verified for exactness with a
  per-item loop that keeps each item's checks exact.

## Decision

Use **A1: Matrix package + profile-registry verifier**.

```text
- frozen mvp4a-v0.1 aloha package/verifier are NOT modified.
- a NEW matrix package verifies the ALOHA profile + one new single-arm profile.
- each profile keeps exact pinned constants (no generic-parser weakening).
- one independent stdlib verifier iterates a profile registry.
- the default verifier enforces refetch/extraction/deep-hdf5 receipts per profile
  (preserves the v0.1 audit bar).
- the two profiles must differ in robot_type AND state/action dims, so this proves
  external public dataset pattern repeatability, not same-family constant repetition.
```

Rejected alternatives: A2 (shared verifier re-verifying the frozen aloha package —
couples to or mutates a tagged asset); A3 (standalone second package — two
independent one-offs do not prove a parameterized repeatable pattern).

If the second dataset cannot meet the selection criteria (below), the slice must
**stop and not claim the matrix**. It may ship a contract/addendum artifact, but it
must not claim `external_data_evaluated` for the matrix.

## Profile Registry

Each dataset is one frozen profile of exact constants. The verifier hardcodes the
**structural** expectations per profile; the immutable revision is package-declared
and only required to be a pinned 40-char sha that matches across binding/receipts.

```python
# verifier module-level registry (stdlib only)
Profile = {
    "profile_id": str,            # e.g. "lerobot_aloha_static_coffee"
    "repo_id": str,               # e.g. "lerobot/aloha_static_coffee"
    "source_file": str,           # e.g. "data/chunk-000/file-000.parquet"
    "robot_type": str,            # e.g. "aloha" | "<single_arm_type>"
    "episode_index": int,
    "frame_start": int,
    "frame_count": int,
    "observation_state_dim": int, # 14 for ALOHA; != 14 for the single-arm profile
    "action_dim": int,
    "license": str,               # "mit" or other redistributable license
    "required_upstream_files": tuple[str, ...],  # source_file + meta/info.json + README.md
}

PROFILES = (ALOHA_PROFILE, SINGLE_ARM_PROFILE)
```

Adding a future third dataset = append one Profile dict. The verifier never accepts
an unlisted repo_id or weakens a dimension to "any".

## Matrix Package Layout

New, separate package (frozen aloha package untouched):

```text
docs/proof/lerobot_public_dataset_matrix_semantic_parity_proof_package/
  README.md
  package_manifest.json
  data/
    config.json                  # required_profiles, package_status, non_claims
    matrix_summary.json          # cached/index summary only (not source of truth)
    non_claims_attestation.json
    artifact_index.json
    profiles/
      lerobot_aloha_static_coffee/
        source/{public_source_binding.json, upstream_file_hashes.json,
                refetch_receipt.json, extraction_receipt.json,
                slice_selection_report.json, lerobot_raw_rows.jsonl,
                lerobot_feature_schema.json, LICENSE.txt}
        conversion/{rdf_converted_rows.jsonl, semantic_mapping_report.json,
                    conversion_manifest.json}
        contracts/{normalized_state_action_contract.json, validator_report.json}
        export/{dataset.hdf5, hdf5_inspection_report.json,
                deep_hdf5_receipt.json, trainer_smoke_report.json}
        reports/{buyer_data_evaluation_report.json}
      lerobot_<single_arm_profile_id>/
        ... identical shape ...
```

Each profile directory mirrors the v0.1 aloha package `data/` shape exactly. The
per-profile `lerobot_raw_rows.jsonl` is the source of truth for that profile's
semantic parity. `matrix_summary.json`, buyer reports, and manifests are
cached/index artifacts only.

The matrix package includes its **own self-contained copy** of the ALOHA profile's
audited-slice evidence (pinned to the same revision as v0.1). The matrix verifier
must not read or depend on the frozen v0.1 package at verification time — the matrix
package verifies standalone. The frozen v0.1 package remains a separate, untouched
artifact verified by its own frozen verifier.

## Verifier Contract

New file: `scripts/verify_lerobot_public_dataset_matrix_package.py`.

```text
- stdlib-only default; no import from producer/RDF service modules; no
  pyarrow/pandas/datasets/lerobot/h5py/numpy in default mode.
- iterate PROFILES; for EACH profile, recompute the v0.1 per-profile checks:
  - package + data artifact-index hash integrity (path-traversal blocked);
  - public_source_binding: repo_id == profile.repo_id, source_file == profile.source_file,
    license present, dataset_card_robot_type == profile.robot_type,
    provenance_trust_tier == "refetchable_public_source",
    resolved_revision is a pinned 40-char lowercase sha consistent across
    binding/config/manifest/upstream/receipts;
  - upstream_file_hashes cover profile.required_upstream_files, sha256-shaped,
    source_url bound to resolved_revision;
  - refetch_receipt: matched true, files_checked == upstream files,
    declared==refetched==upstream sha per file (DEFAULT-enforced);
  - raw rows satisfy the profile slice rule, numeric/dimension-consistent
    observation.state and action with profile dims, monotonic timestamps,
    per-row source_row_sha256, bound to repo_id/resolved_revision/source_file;
  - extraction_receipt: independent re-extractor reproduced identical raw-row
    digests; included == reextracted jsonl sha (DEFAULT-enforced);
  - conversion parity: verifier RE-DERIVES converted rows from raw rows and
    compares; fabricated EEF/object/task_success fields hard-fail;
  - contract/validator/buyer/trainer-smoke counts and dims agree; visual ignored;
  - deep_hdf5_receipt + float32 byte-search: HDF5 bytes contain the converted
    observation/action payload exactly once (DEFAULT-enforced, no h5py needed).
- MATRIX-level checks:
  - config.required_profiles == exactly the registry profile_ids (missing/extra fail);
  - the two profiles have DIFFERENT robot_type AND different
    (observation_state_dim, action_dim) — same-shape profiles fail
    (this is what proves repeatability across embodiments, not constant repetition);
  - shared non_claims keys exact + all false across manifest/config/buyer/attestation;
  - negation-aware forbidden prose scan over README/reports/text (ported from MVP-3C);
  - spent ranges 40000-40049 / 42000-42049 not reused in any seed-like field.
- optional modes, per profile: --deep-hdf5 (h5py/numpy), --refetch-public-source
  (network sha compare), --reextract-public-source (pyarrow re-extract).
```

Independence/duplication note: the matrix verifier intentionally **re-implements**
the per-profile checks rather than importing the frozen aloha verifier. Code
duplication is the accepted cost of (a) producer/auditor independence and (b) not
mutating the tagged v0.1 verifier. The matrix verifier is the sole authority for
the matrix package.

Frozen: the matrix verifier and package must not modify
`scripts/verify_lerobot_public_slice_package.py` or the aloha v0.1 package.

## Second Dataset Selection Criteria + Stop Conditions

The single-arm profile dataset must satisfy ALL of:

```text
- public LeRobot dataset on Hugging Face;
- robot_type != "aloha" and a single-arm embodiment;
- observation.state / action dims != 14 (different shape from ALOHA);
- redistributable license (mit or compatible) for the small audited slice;
- an immutable, pinnable 40-char commit revision (floating main is rejected);
- tabular state/action parquet readable into the raw-row JSONL shape;
- a small deterministic audited slice (first episode, first N frames) is sufficient.
```

Candidate single-arm LeRobot dataset families to evaluate in priority order, each
subject to license/revision/format verification at implementation (the
implementation pins the concrete repo_id + revision, exactly as v0.1 did):

```text
- a SO-100 / SO-101 single-arm recording;
- a Koch low-cost single-arm recording;
- an xArm single-arm recording.
```

Stop conditions (inherited from v0.1; do not claim the matrix if any holds):

```text
- no single-arm dataset meeting the criteria can be fetched or revision-pinned;
- license/provenance cannot be verified from the public dataset page;
- selected upstream files cannot be hash-bound;
- parquet extraction would require committing large source files;
- rows cannot be converted without fabricating EEF/object/task-success fields;
- HDF5/trainer smoke would require erasing source semantics;
- the verifier cannot recompute raw -> converted parity from included evidence;
- the only available second dataset shares ALOHA's robot_type or dims (no variety);
- any report/README leaks real robot readiness, full dataset, policy uplift, etc.
```

The conversion must never force the single-arm rows into ALOHA's dims/schema and
must never fabricate EEF pose, object pose, robot family, or task success.

## Claim / Non-Claims

```text
package_status=external_data_evaluated
source_kind=public_lerobot_dataset_matrix_audited_slice
external_source_included=true
profiles_count=2
provenance_trust_tier=refetchable_public_source   # per profile
full_dataset_verdict_claimed=false                # per profile
audited_slice_verdict_claimed=true                # per profile
```

Allowed claim: "RDF evaluated deterministic audited slices from two distinct public
LeRobot real-robot datasets (bimanual ALOHA + a single-arm embodiment) through the
same parameterized ingest pattern, each refetchable-public-source bound and
recomputed by one independent verifier."

Disallowed: full dataset evaluation, all-LeRobot support, generic parser, real
robot success/readiness, live hardware/RTDE/ROS2/Franka, visual policy, policy
uplift, deployment, marketplace, production, sim-to-real. The canonical non-claim
key set from v0.1 is preserved and extended with `full_lerobot_parser_support` and
an explicit "only two pinned profiles" statement.

Honest residual (disclosed, not a defect): the default offline verifier enforces
internal parity + receipt consistency; the ground-truth that upstream hashes match
Hugging Face is re-checkable by anyone via `--refetch-public-source`. The producer
runs refetch/reextract once and records the receipts. This is the same
publicly-re-checkable posture as v0.1.

## Testing Strategy

Tests are TDD-first.

Per-profile (parameterized over both profiles):

```text
- raw LeRobot row fixture -> converted RDF rows (deterministic parity);
- conversion rejects missing state/action;
- conversion rejects fabricated EEF/object/task-success fields;
- slice selection rule enforced; declared dims preserved;
- generic state/action contract passes valid rows, fails dimension drift;
- HDF5/trainer smoke preserves state/action arrays (float32 byte-search);
- package includes raw rows, not only hashes;
- verifier fails hash-refreshed raw/converted/HDF5 tamper;
- verifier fails floating (non-40-char) revision;
- verifier fails refetch/extraction receipt mismatch.
```

Matrix-level:

```text
- required_profiles exactness: missing or extra profile fails;
- DIFFERENT robot_type AND dims asserted: a second profile equal to ALOHA's shape fails
  (proves embodiment variety, not constant repetition);
- shared non-claims exact + false; forbidden prose/claim scan; spent ranges.
```

Regression:

```text
- frozen aloha v0.1 verifier still VERIFIED, zero diff to its package/script;
- MVP-2 / MVP-3A / MVP-3B / MVP-3C / external-ingest verifiers still VERIFIED;
- git diff --check clean.
```

## Verification Commands (expected after implementation)

```bash
uv run pytest -q apps/api/tests/test_lerobot_public_dataset_matrix.py
uv run pytest -q apps/api/tests/test_verify_lerobot_public_dataset_matrix_package.py
python3 scripts/verify_lerobot_public_dataset_matrix_package.py \
  docs/proof/lerobot_public_dataset_matrix_semantic_parity_proof_package/package_manifest.json
python3 scripts/verify_lerobot_public_dataset_matrix_package.py --deep-hdf5 \
  docs/proof/lerobot_public_dataset_matrix_semantic_parity_proof_package/package_manifest.json
python3 scripts/verify_lerobot_public_slice_package.py \
  docs/proof/lerobot_public_aloha_slice_semantic_parity_proof_package/package_manifest.json
python3 scripts/verify_external_robot_data_ingest_package.py \
  docs/proof/external_robot_data_ingest_eval_v0_proof_package/package_manifest.json
python3 scripts/verify_mvp2_package.py docs/proof/mvp2_learning_proven_evidence_package/package_manifest.json
python3 scripts/verify_proof_package.py docs/proof/mvp3a_target_fixture_pose_variant_proof_package/package_manifest.json
python3 scripts/verify_mvp3b_source_adapter_package.py docs/proof/mvp3b_source_adapter_matrix_proof_package/package_manifest.json
python3 scripts/verify_mvp3c_isaac_sim_embodiment_source_package.py docs/proof/mvp3c_isaac_sim_embodiment_source_proof_package/package_manifest.json
uvx ruff check <touched files>
python3 -m compileall <touched scripts/services/tests>
git diff --check
```

## Success Criteria

```text
1. a new matrix package exists under docs/proof/ with exactly two profiles;
2. one profile is the ALOHA bimanual dataset, one is a single-arm dataset with a
   different robot_type and different state/action dims;
3. each profile carries a pinned-revision refetchable public binding plus
   refetch/extraction/deep-hdf5 receipts;
4. converted rows are derived without semantic fabrication;
5. a generic state/action contract is emitted and verified per profile;
6. the default stdlib verifier recomputes both profiles offline and enforces the
   v0.1 receipt bar;
7. the verifier rejects a same-shape (non-varied) second profile;
8. forbidden claims remain false; non-claims include "no generic parser / only two
   pinned profiles";
9. frozen aloha v0.1 + all older MVP verifiers remain green with zero diff.
```

## Implementation Components

This spec does not authorize implementation. Likely components:

```text
C1 profile registry + single-arm dataset resolver (pin repo_id/revision/license)
C2 single-arm audited slice extractor (producer-only optional pyarrow path)
C3 LeRobot -> RDF generic state/action converter reused across profiles
C4 generic state/action contract + HDF5 export/trainer smoke per profile
C5 matrix proof package builder (two profile dirs + matrix summary + non-claims)
C6 independent stdlib matrix verifier (profile loop + matrix-level checks)
C7 tamper tests, matrix variety tests, regression, docs/handoff
```

Dependency guidance: heavyweight LeRobot/parquet deps stay producer-only and
optional (`uv run --with pyarrow --with huggingface_hub ...`). The verifier default
path is stdlib-only.

## Stop / Boundary Summary

```text
Never: modify the frozen aloha v0.1 package or scripts/verify_lerobot_public_slice_package.py;
       work on main; fabricate EEF/object/task-success; force single-arm into ALOHA dims;
       claim generic LeRobot parser or full dataset evaluation;
       claim the matrix if the second dataset fails the selection criteria.
Always: new feature branch; new separate matrix package; stdlib-only default verifier;
        per-profile exact constants; explicit refetch/reextract options;
        receipts enforced by default; two profiles differ in robot_type and dims.
```

## References

- `docs/superpowers/specs/2026-06-23-lerobot-public-slice-semantic-parity-design.md`
- `scripts/verify_lerobot_public_slice_package.py`
- `scripts/verify_mvp3b_source_adapter_package.py`
- `apps/api/app/services/lerobot_public_slice.py`
- `apps/api/app/services/lerobot_state_action_contract.py`
- LeRobotDataset v3.0: `https://huggingface.co/docs/lerobot/en/lerobot-dataset-v3`
