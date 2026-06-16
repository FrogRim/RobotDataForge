# MVP-2 Learning-Proven Evidence Package

이 패키지는 `v0_14_comparator_provenance_row_balance` closure를 외부 기술 검토자가
읽고 추적할 수 있도록 고정한 문서 세트다. 현재 주장은 좁다. Robot Data Forge는
현재 Isaac held-out evaluator domain에서 curated training material이 uncurated
baseline보다 downstream policy success를 높였다는 MVP-2 `learning-proven`
증거를 만들었다.

이 패키지는 real robot 성공, HMD/OpenXR readiness, visual policy 성능,
deployable policy, universal robot support, marketplace 또는 production
certification을 주장하지 않는다.

## Frozen Claim

| 항목 | 값 |
| --- | --- |
| Proof slice | `v0_14_comparator_provenance_row_balance` |
| Runtime backend | `isaac_runtime` |
| Proof domain | Isaac held-out evaluator domain |
| Calibration pre-signal | baseline `5 / 30`, candidate `26 / 30` |
| Held-out closure | baseline `5 / 50`, candidate `40 / 50` |
| Absolute uplift | `+0.70` |
| Bootstrap CI | `[0.56, 0.82]`, 2,000 iterations |
| MVP-2 status | `mvp2_closed=true`, `policy_uplift_proven=true` |
| Spent held-out | `40000-40049` |

`40000-40049`는 v0.14 closure에 사용된 audit-only held-out range다. 앞으로
tuning, calibration, threshold selection, hyperparameter search, future closure
re-use에 쓰면 안 된다.

## Source Of Truth

주장 판단의 source of truth는 아래 artifact다.

- Root evidence manifest:
  `storage/proof_evidence/mvp2c_isaac_training_calibration/evidence_manifest.json`
- Closure gate:
  `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_14_comparator_provenance_row_balance/heldout_closure_gate_v0_14.json`
- Learning-proven report:
  `storage/proof_evidence/mvp2c_isaac_training_calibration/v0_14_comparator_provenance_row_balance/mvp2_learning_proven_policy_eval/mvp2_learning_proven_report.json`

이 문서 패키지는 사람이 읽는 freeze layer다. 실제 검토자는 `evidence_index.md`의
경로와 SHA-256을 기준으로 원본 artifact를 확인해야 한다.

## Package Contents

- `README.md`: 외부 검토용 요약.
- `evidence_index.md`: 주요 artifact 경로, 역할, SHA-256.
- `claims_and_limitations.md`: 허용 claim과 non-claim boundary.
- `reproducibility_and_review_notes.md`: 재현 명령, 검증 절차, 리뷰 관점.
- `v0_14_comparator_provenance_row_balance_appendix.md`: comparator provenance와
  row-balance 세부 설명.
- `package_manifest.json`: machine-readable package manifest.

## Codex Use Disclosure

이 패키지의 문서화와 self-review 정리는 Codex가 보조했다. Codex는 source
artifact를 읽고, claim boundary를 문서화하고, 반복 검증 명령을 실행하는 데
사용됐다. Proof 자체의 source of truth는 Codex 응답이 아니라 위 JSON artifact,
검증 스크립트, commit history다.
