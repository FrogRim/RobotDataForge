# Claims And Limitations

이 문서는 v0.14 MVP-2 proof package에서 허용되는 claim과 금지되는 claim을
고정한다.

## Allowed Claims

아래 표현은 현재 evidence package와 일치한다.

- Robot Data Forge는 current Isaac held-out evaluator domain에서 MVP-2
  `learning-proven` closure를 달성했다.
- v0.14 candidate curated policy는 같은 held-out suite에서 baseline uncurated
  policy보다 높은 `policy_success_rate`를 보였다.
- Held-out closure 결과는 baseline `5 / 50`, candidate `40 / 50`,
  absolute uplift `+0.70`이다.
- Closure bootstrap CI는 `[0.56, 0.82]`이고 2,000 iterations로 기록됐다.
- Calibration pre-signal은 baseline `5 / 30`, candidate `26 / 30`이었다.
- Comparator provenance row-balance gate는 baseline training view의 failure
  material ratio를 `0.5`로 맞추고, duplicate failure rows를 허용하지 않았다.
- `40000-40049`는 v0.14 closure에 사용된 spent held-out range이며 audit-only로
  보존해야 한다.

## Forbidden Claims

아래 표현은 현재 evidence package로 주장하면 안 된다.

- real robot success가 증명됐다.
- physical robot readiness가 증명됐다.
- HMD/OpenXR readiness가 증명됐다.
- visual policy performance가 증명됐다.
- deployable real robot policy가 만들어졌다.
- universal robot support가 증명됐다.
- production certification, marketplace readiness, payment/reward flow가
  준비됐다.
- `40000-40049`를 다시 tuning, calibration, threshold tuning,
  hyperparameter selection, future closure에 사용해도 된다.

## Confidence Interval Disclosure (두 CI는 별개다)

이 closure에는 서로 다른 두 개의 bootstrap CI가 기록돼 있으며 **섞으면 안 된다**.

| 출처 | 값 | method | seed | 재현성 |
| --- | --- | --- | --- | --- |
| closure gate (`heldout_closure_gate_v0_14.json`) | `[0.56, 0.82]` | bootstrap_success_rate_difference | 미기록 | bit-단위 재현 불가 |
| learning report (`mvp2_learning_proven_report.json`) | `[0.56, 0.84]` | deterministic_bootstrap | `23` | 재현 가능 |

규칙(고정):

> Closure decision is deterministic and does not depend on bootstrap CI.
> The original closure gate CI [0.56, 0.82] is retained as historical reported
> evidence, but it is not bit-reproducible because the RNG seed was not recorded.
> The verifier recomputes a separate package-audit CI with an explicit fixed seed.
> That recomputed CI is audit evidence, not a retroactive replacement for the
> original closure gate CI.

`scripts/verify_mvp2_package.py`가 보고하는 package-audit CI는 seed `20260617`로
재계산된 **advisory** field다. closure 판정(`mvp2_closed`, uplift>=0.20)은 이 CI에
의존하지 않는다.

## Statistical Scope (n=1 held-out run)

이 closure는 단일 held-out band(`40000-40049`, 50 rollouts/policy)에 대한 **1회**
sealed 실행이다. uplift `+0.70`은 강한 existence proof지만, 복수 held-out band에
대한 분산 추정은 아니다. 통계적 견고성(robustness)을 한 단계 올리려면 새 held-out
band에서의 independent replication이 필요하다(아래 "What Would Be Needed Next").

## Non-Claim Coverage Note (hash-locked 범위)

8종 non-claim 중 hash-locked closure gate(`data/heldout_closure_gate_v0_14.json`)는
6종을 직접 기록한다(real_robot_success, physical_robot_readiness,
hmd_openxr_readiness, visual_policy_performance, deployable_real_robot_policy,
universal_robot_support). 나머지 2종(marketplace_readiness,
production_certification)은 `package_manifest.json`의 non_claims 블록에만 존재한다.
verifier는 manifest를 8종 권위로 검증하고, gate가 기록한 6종이 모순(true로 뒤집힘)
되지 않는지 함께 확인한다. 즉 marketplace/production non-claim의 무결성은 현재
manifest 레이어에 있으며, 향후 closure gate에 8종 전부를 박는 것이 더 강하다.

## Held-Out Rule

`40000-40049`는 한 번 열렸고, closure 판단에 사용됐다. 따라서 이 range의
새 역할은 audit trail이다.

- `future_tuning_allowed=false`
- `future_closure_reuse_allowed=false`
- `same_heldout_reuse_allowed_for_closure=false`

새로운 MVP-2+ 또는 public replication claim은 새 held-out range를 배정해야 한다.
기존 range를 다시 쓰면 closure evidence가 tuning evidence로 오염된다.

## What This Proof Means

이 proof는 RDF가 buyer-facing data trust layer로서 다음 질문에 답할 수 있음을
보인다.

> 같은 task/evaluator domain에서 curated dataset artifact가 uncurated artifact보다
> downstream policy success를 올렸는가?

v0.14의 답은 yes다. 하지만 이 yes는 Isaac evaluator-domain answer이며, 로봇
배포나 camera-conditioned policy answer가 아니다.

## What Would Be Needed Next

외부 신뢰도를 한 단계 올리려면 다음 package가 별도로 필요하다.

- 독립 machine에서 artifact hash 검증과 full rerun.
- 새 held-out range를 사용한 independent replication.
- Isaac runtime evaluator와 training harness를 분리한 clean-room review.
- real robot claim을 원하면 별도 physical setup, robot logs, safety boundary,
  intervention log, evaluator false-positive audit.
- visual policy claim을 원하면 camera/HMD geometry provenance, image pipeline
  readiness gate, camera-conditioned held-out evaluation.
