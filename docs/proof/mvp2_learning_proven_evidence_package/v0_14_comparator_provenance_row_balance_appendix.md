# v0.14 Comparator Provenance Row-Balance Details

이 appendix는 v0.14 closure가 왜 이전 v0.13 proof보다 외부 리뷰에 더 견딜 수
있는지 설명한다. 핵심은 candidate만 좋은 조건을 받은 것이 아니라 baseline
comparator도 provenance와 row-balance를 명시적으로 맞췄다는 점이다.

## Problem Addressed

이전 proof에서 외부 리뷰어가 물을 수 있는 질문은 세 가지였다.

- baseline uncurated view가 너무 약하게 구성된 것은 아닌가?
- candidate curated view가 더 좋은 source provenance를 가진 것은 아닌가?
- failure material이 baseline에 충분히 들어가지 않아 비교가 불공정한 것은
  아닌가?

v0.14는 이 질문을 closure 전에 별도 gate로 분리했다.

## Comparator Provenance Controls

`v0_14_comparator_provenance_row_balance_gate.json`는 held-out을 열기 전에 아래
조건을 확인한다.

- `parent_policy_slice`: `v0_13`
- `same_policy_influence_authority_ceiling_config_as_peer=true`
- `peer_fairness_mismatch_keys=[]`
- `fresh_calibration_39000_39029_accessed=false`
- `fresh_heldout_40000_40049_accessed=false`
- `proof_authority=false`

즉 comparator gate 자체는 proof authority가 아니며, held-out closure를 열기 전
비교 조건을 점검하는 precondition이다.

## Row-Balance Controls

`v0_14_row_balance_report.json`는 baseline training view에 near-miss terminal
failure rows를 명시적으로 포함한다.

| 항목 | 값 |
| --- | --- |
| Failure material selection | `row_balanced_near_miss_terminal_failure_rows` |
| Baseline actual failure material ratio | `0.5` |
| Baseline failure material ratio target | `0.5` |
| Failure ratio accepted range | `0.45` to `0.55` |
| Selected success row count | `288` |
| Selected failure row count | `288` |
| Failure-to-success row ratio | `1.0` |
| Duplicate failure rows allowed | `false` |
| Max rows per failure source trace | `300` |

이 구조는 baseline이 failure material을 못 봐서 실패했다는 단순 반론을 줄인다.
동시에 baseline을 artificially improve하는 것이 아니라, 같은 trainer/policy
class 아래에서 uncurated comparator가 fair하게 실패 사례를 볼 수 있도록 만든다.

## Calibration Then Closure

v0.14는 calibration과 closure를 분리했다.

1. Comparator provenance row-balance gate 통과.
2. Calibration pre-signal range `39000-39029` open.
3. Calibration 결과 baseline `5 / 30`, candidate `26 / 30`.
4. Calibration signal이 충분할 때만 held-out `40000-40049` open.
5. Closure 결과 baseline `5 / 50`, candidate `40 / 50`.

이 순서는 held-out을 tuning loop에 노출하지 않는 구조다. `40000-40049`는
closure 후 spent가 되었고, 앞으로 audit-only로 보존해야 한다.

## Why This Is Still Narrow

이 appendix가 강화하는 것은 comparator fairness다. 이것은 아래를 증명하지 않는다.

- real robot success
- HMD/OpenXR readiness
- visual policy performance
- deployable real robot policy
- universal robot support

따라서 public-facing 문장은 "Isaac held-out evaluator domain에서
learning-proven uplift가 있었다"로 제한해야 한다.

## Reviewer Interpretation

외부 리뷰어가 볼 때 v0.14의 의미는 다음과 같다.

- Candidate curated artifact가 같은 evaluator-domain에서 downstream value를
  만든 것은 확인됐다.
- Baseline comparator가 failure material을 완전히 배제한 unfair baseline이라는
  반론은 row-balance gate로 약해졌다.
- 그러나 이 결과는 deployment readiness가 아니라 data trust layer의 learning
  value proof다.
