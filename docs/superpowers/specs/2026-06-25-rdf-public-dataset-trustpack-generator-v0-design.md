# Spec: RDF Public Dataset TrustPack Generator v0

Date: 2026-06-25
Status: SPEC REVIEW PATCHED; NOT IMPLEMENTED
Branch: TBD (new feature branch recommended; do not work directly on `main`)

## Objective

이번 milestone의 목적은 새 proof를 여는 것이 아니다.

이미 닫힌 public LeRobot matrix discipline을 제품 표면으로 바꾸는 것이다.

```text
RDF can generate self-contained, verifier-backed trust packages and
buyer-readable reports for explicit public robot dataset profiles.
```

v0의 첫 target은 기존 `ALOHA + SO-100` public dataset matrix다.

```text
existing LeRobot matrix proof discipline
→ public dataset profile registry
→ deterministic audited slice materialization
→ semantic conversion
→ normalized state/action contract
→ HDF5 / trainer-smoke receipts
→ buyer_report.html
→ self-contained verifier-backed TrustPack
```

중요한 범위:

```text
new proof를 열지 않는다.
새 dataset profile을 추가하지 않는다.
MVP-2/3A/3B/3C package를 통합하지 않는다.
기존 ALOHA + SO-100 matrix package를 공통 generator 계약으로 재생성한다.
```

## Current Repo Facts

현재 닫힌 public dataset evidence:

```text
docs/proof/lerobot_public_aloha_slice_semantic_parity_proof_package/
docs/proof/lerobot_public_dataset_matrix_semantic_parity_proof_package/
```

현재 matrix profile:

```text
lerobot_aloha_static_coffee
  repo_id=lerobot/aloha_static_coffee
  resolved_revision=b144896feb1f37398a862927b22cd3abdf005a6b
  robot_type=aloha
  observation_state_dim=14
  action_dim=14

lerobot_svla_so100_pickplace
  repo_id=lerobot/svla_so100_pickplace
  resolved_revision=3d6d687a25cdf1565cdf24550814f72d999a861d
  robot_type=so100
  observation_state_dim=6
  action_dim=6
```

현재 verifier:

```text
scripts/verify_lerobot_public_slice_package.py
scripts/verify_lerobot_public_dataset_matrix_package.py
```

현재 verifier evidence:

```text
matrix_verifier=VERDICT: VERIFIED
matrix_verifier_deep_hdf5=VERDICT: VERIFIED
matrix_verifier_refetch_public_source=VERDICT: VERIFIED
matrix_verifier_reextract_public_source=VERDICT: VERIFIED
```

중요한 기존 결정:

```text
summary는 source of truth가 아니다.
verifier는 included evidence에서 verdict를 재계산한다.
public dataset profile은 explicit registry 기반이다.
generic LeRobot parser claim을 하지 않는다.
verifier는 producer/generator 코드를 import하지 않는다.
```

## Decision

Use **Option A: Public Dataset TrustPack Generator v0**.

정확한 milestone 이름:

```text
MVP-4B: RDF Public Dataset TrustPack Generator v0
```

이 이름을 쓰는 이유:

```text
TrustPack Generator 전체가 아니다.
MVP-2 learning-proof generator가 아니다.
MVP-3C embodiment-source generator가 아니다.
generic robot dataset importer가 아니다.
public dataset profile TrustPack generator다.
```

Rejected alternatives:

```text
Generic TrustPack Kernel:
  MVP-2/3A/3B/3C/external/LeRobot을 한 번에 묶으면 claim 의미가 흐려진다.

Buyer Report First:
  package generation이 ad hoc이면 report만 예뻐지고 summary가 source of truth처럼 보일 수 있다.

CLI Shell First:
  내부 generator contract 안정 전 CLI부터 만들면 빈 제품 표면이 된다.

Partner File-Drop First:
  실제 provenance/attestation 문제가 필요하므로, 받는 그릇인 TrustPack contract가 먼저다.
```

## Scope

v0에서 할 것:

```text
1. ALOHA + SO-100 matrix profile registry를 productized input contract로 정리한다.
2. 기존 matrix package와 semantic-equivalent한 TrustPack output을 생성한다.
3. generated TrustPack은 기존 matrix verifier contract를 통과해야 한다.
4. buyer_report.html을 생성한다.
5. non-claim boundary를 machine-check 가능한 artifact로 유지한다.
6. generator output manifest가 verdict-critical artifact를 hash-lock한다.
7. tamper tests로 generator output의 주요 contradiction을 잡는다.
```

v0에서 하지 않을 것:

```text
generic LeRobot importer
new public dataset profile 추가
MVP-2/3A/3B/3C package generator화
Croissant full compliance
partner / external file-drop ingest
external data learning uplift
새 policy training
real robot / live ROS2 / live RTDE / HMD runtime
```

## Target Output

기존 닫힌 matrix package는 baseline으로 유지한다.

```text
baseline:
docs/proof/lerobot_public_dataset_matrix_semantic_parity_proof_package/
```

v0 generator가 만드는 새 output package:

```text
docs/proof/rdf_public_dataset_trustpack_v0_lerobot_matrix_package/
  README.md
  package_manifest.json
  buyer_report.html                  # convenience copy; not in matrix artifact_index
  data/
    config.json
    profile_registry.json
    profile_resolver_report.json
    matrix_summary.json
    artifact_index.json
    trustpack_artifact_index.json
    non_claims_attestation.json
    claim_scan_report.json
    regeneration_report.json
    reports/
      buyer_report.html              # canonical hash-locked HTML copy
    profiles/
      lerobot_aloha_static_coffee/
        source/public_source_binding.json
        source/upstream_file_hashes.json
        source/refetch_receipt.json
        source/extraction_receipt.json
        source/slice_selection_report.json
        source/lerobot_raw_rows.jsonl
        source/lerobot_feature_schema.json
        source/LICENSE.txt
        conversion/rdf_converted_rows.jsonl
        conversion/semantic_mapping_report.json
        conversion/conversion_manifest.json
        contracts/normalized_state_action_contract.json
        contracts/validator_report.json
        export/dataset.hdf5
        export/hdf5_inspection_report.json
        export/deep_hdf5_receipt.json
        export/trainer_smoke_report.json
        reports/buyer_data_evaluation_report.json
        profile_metadata.json
      lerobot_svla_so100_pickplace/
        source/public_source_binding.json
        source/upstream_file_hashes.json
        source/refetch_receipt.json
        source/extraction_receipt.json
        source/slice_selection_report.json
        source/lerobot_raw_rows.jsonl
        source/lerobot_feature_schema.json
        source/LICENSE.txt
        conversion/rdf_converted_rows.jsonl
        conversion/semantic_mapping_report.json
        conversion/conversion_manifest.json
        contracts/normalized_state_action_contract.json
        contracts/validator_report.json
        export/dataset.hdf5
        export/hdf5_inspection_report.json
        export/deep_hdf5_receipt.json
        export/trainer_smoke_report.json
        reports/buyer_data_evaluation_report.json
        profile_metadata.json
```

### Existing Verifier Contract

v0는 기존 matrix verifier를 그대로 auditor로 사용한다. 따라서 output layout은
새 product layout을 마음대로 정의하는 것이 아니라 아래 hard contract를 보존해야 한다.

```text
auditor=scripts/verify_lerobot_public_dataset_matrix_package.py
required_data_config=data/config.json
required_resolver=data/profile_resolver_report.json
required_summary=data/matrix_summary.json
required_status=external_data_evaluated
required_profiles=[
  lerobot_aloha_static_coffee,
  lerobot_svla_so100_pickplace
]
required_resolver_selected_profile_id=lerobot_svla_so100_pickplace
```

`package_manifest.json`, `data/config.json`, `data/matrix_summary.json` 모두
아래 값을 가져야 한다.

```text
package_status=external_data_evaluated
required_profiles=[
  lerobot_aloha_static_coffee,
  lerobot_svla_so100_pickplace
]
full_lerobot_parser_claimed=false
```

`data/reports/buyer_report.html`, `data/profile_registry.json`,
`data/trustpack_artifact_index.json`, `data/claim_scan_report.json`,
`data/regeneration_report.json`은 productization artifact로서 additive다.
이 파일들은 `package_manifest.json`과 `data/artifact_index.json`에 `data/` 경로로
hash-lock되어야 하지만, 기존 verifier가 요구하는 `data/config.json`,
`data/profile_resolver_report.json`, per-profile 19-file contract를 rename/drop해서는 안 된다.

Top-level `buyer_report.html`은 reviewer convenience copy다. 기존 matrix verifier의
`artifact_index` contract는 `data/` 하위 path만 허용하므로 top-level HTML을
`package_manifest.json` 또는 `data/artifact_index.json`의 `data_path`로 넣으면 안 된다.
대신 TrustPack-only scanner/comparator가 아래를 검증한다.

```text
data/reports/buyer_report.html exists
top-level buyer_report.html exists
top-level buyer_report.html bytes == data/reports/buyer_report.html bytes
data/trustpack_artifact_index.json records top-level convenience-copy sha256
HTML claim scan passes against both canonical and top-level copies
```

이 output은 기존 matrix package와 byte-identical일 필요가 없다.

필수 조건은 semantic-equivalent다.

```text
same profile ids
same repo ids
same resolved revisions
same source files
same row counts
same observation/action dims
same included raw rows semantic digest
same converted rows semantic digest
same contract validation result
same HDF5/trainer-smoke result
same non-claim boundary
same verifier PASS result
```

Semantic equivalence는 generator가 자기 선언한 summary로 닫지 않는다. 별도 comparator가
baseline package와 generated package를 모두 읽고, 양쪽 verdict-critical evidence digest를
재계산해 `data/regeneration_report.json`을 검증해야 한다.

## Profile Registry Contract

TrustPack v0는 explicit profile registry만 허용한다.

```json
{
  "schema_version": "rdf_public_dataset_profile_registry_v0.1.0",
  "profiles": [
    {
      "profile_id": "lerobot_aloha_static_coffee",
      "repo_id": "lerobot/aloha_static_coffee",
      "resolved_revision": "b144896feb1f37398a862927b22cd3abdf005a6b",
      "source_file": "data/chunk-000/file-000.parquet",
      "robot_type": "aloha",
      "observation_state_dim": 14,
      "action_dim": 14,
      "slice_rule": "first_episode_first_n_frames",
      "frame_count": 8,
      "license": "mit",
      "projection_contract": "rdf_generic_state_action_v0_1"
    }
  ]
}
```

Rules:

```text
profile이 없으면 ingest하지 않는다.
auto-detect로 통과시키지 않는다.
dimension mismatch는 fail이다.
floating revision은 fail이다.
source binding 없으면 fail이다.
profile별 conversion assumption을 명시한다.
새 public dataset은 새 profile + 새 contract review를 요구한다.
```

## TrustPack Builder Contract

새 producer entrypoint 후보:

```text
scripts/run_rdf_public_dataset_trustpack_generator.py
```

v0 builder 단계:

```text
ProfileRegistry
→ SourceBinding
→ SliceExtraction or ExistingAuditedSliceMaterialization
→ RawRows
→ SemanticConversion
→ NormalizedStateActionContract
→ HDF5Export
→ TrainerSmokeReceipt
→ BuyerReportJson
→ BuyerReportHtml
→ ArtifactIndex
→ PackageManifest
→ VerifierBackedTrustPack
```

Implementation note:

```text
v0는 이미 닫힌 ALOHA + SO-100 matrix artifacts를 productized generator contract로
재생성하는 것이 목적이다.

새 upstream fetch/reextract proof를 다시 여는 것이 목적이 아니다.
기존 receipts를 package에 self-contained하게 materialize하고, verifier가 이를 재검증한다.
즉 v0의 novel work는 registry-driven package assembly, hash-locking, buyer report,
and regeneration comparison이며, upstream Parquet에서 데이터를 새로 re-derive했다는 claim이 아니다.
```

## Verifier Independence

가장 중요한 원칙:

```text
generator는 producer다.
verifier는 auditor다.
둘은 같은 verification helper를 공유하지 않는다.
```

v0 verification strategy:

```text
1. generated TrustPack package를 scripts/verify_lerobot_public_dataset_matrix_package.py로 검증한다.
2. verifier는 generator module을 import하지 않는다.
3. generator output이 verifier PASS를 얻어야 한다.
4. 별도 trustpack wrapper verifier를 만들더라도, wrapper는 기존 independent verifier를 실행하거나
   결과를 record할 뿐, summary를 source of truth로 삼지 않는다.
```

금지:

```text
verifier가 generator code를 import
verifier가 buyer_report.html을 source of truth로 사용
verifier가 matrix_summary.json만 보고 PASS
generator가 verifier-only constants를 runtime에서 수정
```

Wrapper policy:

```text
v0 기본값은 existing matrix verifier를 그대로 재사용한다.
wrapper가 필요해도 raw verdict를 숨기거나 요약하지 않는다.
wrapper는 기존 verifier를 shell out/import 없이 process로 실행하고 stdout/stderr/exit code를 보존한다.
wrapper는 HTML claim scan 또는 regeneration comparator 같은 TrustPack-only product gates를
추가로 실행할 수 있지만, matrix verifier PASS를 대체하지 않는다.
```

TrustPack-only auditor placement:

```text
HTML scanner and regeneration comparator are auditor tools.
They must be standalone scripts or use an audit-only stdlib-compatible helper.
They must not import the TrustPack generator or `apps/api/app/services/*` producer modules.
The generator may run them as subprocesses or consume their JSON outputs, but must not make
their verdict depend on producer internals.
```

## Buyer Report HTML

`buyer_report.html`은 product surface다.

하지만 proof source of truth는 아니다.

HTML이 답해야 하는 질문:

```text
What source?
What revision?
What source files?
What audited slice?
What state/action dimensions?
What semantic conversion assumptions?
What contract passed?
What export/trainer-smoke passed?
What does this not prove?
How can a reviewer verify it?
```

HTML 필수 문구:

```text
This report is a buyer-readable view. The proof source of truth is the
self-contained package plus verifier PASS.
```

HTML 검증:

```text
file exists
canonical copy exists at data/reports/buyer_report.html
top-level convenience copy exists at buyer_report.html
top-level convenience copy bytes match canonical data/reports copy
canonical copy is hash-locked in matrix-compatible data/ indexes
top-level copy sha256 is recorded in data/trustpack_artifact_index.json
contains profile ids and revisions
contains verifier command
contains non-claim boundary
contains "not full LeRobot support"
contains "not full dataset evaluation"
contains "not real robot success"
contains "not policy uplift"
same negation-aware forbidden-claim prose scan as matrix verifier
```

HTML은 verifier가 recompute하는 raw evidence를 대체하지 않는다.

Important auditor gap:

```text
scripts/verify_lerobot_public_dataset_matrix_package.py currently scans
.json/.jsonl/.md/.txt for forbidden claims, but not .html.
```

Therefore TrustPack v0 cannot rely on matrix verifier PASS alone for
`buyer_report.html`. Acceptance must include a dedicated HTML overclaim scan
using the same negation-aware forbidden phrase semantics. A package is not
accepted as TrustPack v0 unless both are true:

```text
matrix_verifier=VERDICT: VERIFIED
buyer_report_html_claim_scan=PASS
```

HTML scan canonicalization:

```text
Scan raw HTML text.
Also scan visible text extracted with stdlib `html.parser`.
Unescape HTML entities before phrase matching.
Ignore or reject script/style content deterministically.
Tag-split forbidden phrases must still be detected in visible text.
Negation semantics must match the existing matrix verifier's clause-local behavior.
```

## Claims

Allowed claim:

```text
RDF Public Dataset TrustPack Generator v0 can generate verifier-backed,
self-contained trust packages and buyer-readable reports for explicit public
robot dataset profiles, demonstrated by materializing a semantic-equivalent
TrustPack from the already-closed ALOHA + SO-100 LeRobot matrix artifacts.
```

More concise:

```text
RDF can generate TrustPacks for explicit public robot dataset profiles.
```

Required qualifiers:

```text
public dataset profile
deterministic audited slice
self-contained verifier-backed package
buyer-readable report
semantic-equivalent regeneration of existing matrix discipline
```

Forbidden implication:

```text
Do not imply that v0 re-derived the audited slices from upstream Parquet.
Do not imply that v0 opens a new external-data proof.
Do not imply that passing the matrix verifier alone proves buyer_report.html is overclaim-free.
```

## Non-Claims

The package and report must not claim:

```text
generic LeRobot importer
full LeRobot support
full dataset evaluation
real robot success
physical robot readiness
live ALOHA/UR/Franka/ROS/RTDE support
visual policy performance
policy uplift or learning-proven value
deployable policy readiness
marketplace readiness
production certification
sim-to-real proven
general robot intelligence
Croissant full compliance
```

## Croissant Boundary

Croissant direction is valid but out of v0 scope.

v0 may include only a future hook:

```text
future_artifact=rdf_croissant_preview.jsonld
status=not_implemented_in_v0
claim=none
```

If a preview is added later, allowed wording is:

```text
Croissant-compatible metadata preview
```

Forbidden wording:

```text
full Croissant compliance
Croissant-certified dataset
standard-compliant marketplace metadata
```

## Tamper / Failure Tests

Required TDD cases:

```text
profile_registry_missing_profile -> fail
profile_registry_extra_profile -> fail
profile_dim_drift -> fail
profile_revision_not_40_char_sha -> fail
raw_rows_hash_drift -> fail
converted_rows_semantic_drift -> fail
contract_dim_mismatch -> fail
trainer_smoke_false_but_summary_true -> fail
buyer_report_overclaim_text -> fail
non_claim_true -> fail
manifest_hash_refreshed_but_semantic_drift -> fail
generator_output_passes_existing_matrix_verifier -> pass
regeneration_report_self_attested_drift -> fail
baseline_vs_generated_digest_mismatch -> fail
```

Notes:

```text
trainer_smoke_false_but_summary_true must tamper the per-profile
export/trainer_smoke_report.json that the matrix verifier actually reads, not only a top-level summary.

buyer_report_overclaim_text must tamper buyer_report.html and fail through the
TrustPack HTML claim scan, because the existing matrix verifier does not scan .html.
It must include tag-split/entity-encoded forbidden phrase cases.

regeneration_report_* tests must use an independent comparator that reads both
the baseline package and the generated package. The generator's own regeneration
summary is not sufficient.
```

## Acceptance Criteria

Required:

```text
1. TrustPack generator creates docs/proof/rdf_public_dataset_trustpack_v0_lerobot_matrix_package/
2. generated package is self-contained for ALOHA + SO-100 audited slices
3. existing matrix verifier returns VERDICT: VERIFIED on generated package
4. data/reports/buyer_report.html exists, top-level buyer_report.html exists, both copies match, and both are hash-locked through TrustPack-compatible metadata without breaking the existing matrix verifier's data/ artifact contract
5. buyer_report.html preserves required non-claims and passes a negation-aware forbidden-claim scan
6. profile_registry.json is explicit and exact
7. data/regeneration_report.json exists and an independent comparator confirms generated package is semantic-equivalent to the current matrix package
8. verifier imports no generator/producer code
9. tamper tests fail as expected
10. frozen MVP-2/MVP-3/MVP-4A/current matrix packages are not modified
```

Verification commands expected after implementation:

```bash
python scripts/run_rdf_public_dataset_trustpack_generator.py
python scripts/verify_lerobot_public_dataset_matrix_package.py \
  docs/proof/rdf_public_dataset_trustpack_v0_lerobot_matrix_package/package_manifest.json
python <trustpack_html_claim_scan_or_wrapper> \
  docs/proof/rdf_public_dataset_trustpack_v0_lerobot_matrix_package/buyer_report.html
python <trustpack_regeneration_comparator> \
  docs/proof/lerobot_public_dataset_matrix_semantic_parity_proof_package \
  docs/proof/rdf_public_dataset_trustpack_v0_lerobot_matrix_package
uv run pytest -q <focused trustpack tests>
python -m compileall scripts apps/api/app/services apps/api/tests
ruff check <touched files>
git diff --check
```

## Review Decisions Before Ralplan

1. The generated package must reuse the existing matrix verifier contract unchanged.
2. `buyer_report.html` may be generated from package evidence plus report JSON, but must be separately scanned for forbidden prose claims because the existing matrix verifier does not scan `.html`.
3. Semantic-equivalence comparison against the existing matrix package must be a required `data/regeneration_report.json` artifact, verified by an independent comparator/test that recomputes both sides.

Recommended answers:

```text
1. keep scripts/verify_lerobot_public_dataset_matrix_package.py as the matrix auditor
2. add TrustPack-only HTML claim scan acceptance gate
3. add independent baseline-vs-generated comparator and required regeneration_report.json
```

## Final Boundary

This milestone closes only this claim:

```text
RDF can materialize the already-closed ALOHA + SO-100 public dataset matrix
discipline through a public dataset TrustPack generator, producing a
verifier-backed package and buyer-readable report without opening a new proof
claim or re-deriving upstream public dataset rows.
```

It does not close external partner file-drop evaluation or external data learning uplift.
