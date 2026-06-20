# Robot Data Forge Project Instructions

## Validated Robot Learning Data Infrastructure

---

## 0. 문서 목적

이 문서는 Robot Data Forge 프로젝트의 제품 방향, MVP 범위, 개발 원칙, 경쟁 차별화, 구현 지침을 하나로 정리한 프로젝트 지침 문서다.

이 문서는 처음 보는 사람도 다음을 바로 이해할 수 있도록 작성되었다.

- Robot Data Forge가 무엇인지
- 무엇을 만들고 있는지
- 무엇을 만들지 않는지
- 왜 단순 trajectory recorder가 아닌지
- OpenGraphLabs, Assured Robot Intelligence 같은 회사와 어떻게 다른지
- MVP-0와 MVP-1에서 각각 무엇을 증명해야 하는지
- 코딩 에이전트가 어떤 기준으로 작업해야 하는지

---

## 1. 한 줄 정의

Robot Data Forge는 raw robot-action trajectory를 자동 검증, 큐레이션, export하여 로봇 학습 시스템과 데이터 구매자가 신뢰할 수 있는 replay-verified, action-labelled, task-validated, trainer-loadable dataset artifact와 재현 가능한 data trust layer record로 만드는 Physical AI 데이터 인프라다.

쉽게 말하면:

> Robot Data Forge는 로봇이 배울 수 있는 “좋은 조작 경험 데이터”를 만들고, 검수하고, 신뢰 증거와 함께 상품화하는 시스템이다.

---

## 2. 제품 정체성

Robot Data Forge는 다음이 아니다.

- 일반 행동 영상을 모으는 보상형 앱
- 단순 VR 게임형 데이터 수집 플랫폼
- 일반 크라우드소싱 앱
- 자율주행 데이터 플랫폼
- 범용 휴머노이드 foundation model 회사
- VLA 또는 World Foundation Model을 직접 만드는 회사
- 실제 로봇 원격 관제 플랫폼
- 단순 trajectory recorder

Robot Data Forge는 다음이다.

- robot-action-labelled trajectory 검증 시스템
- replay-verified action contract 검증 시스템
- task-validated robot learning dataset 인프라
- provenance, schema version, audit trail, reproducible command, limitations를 포함한 data trust layer
- 학습 가능한 데이터만 선별하는 큐레이션 시스템
- 로봇 학습용 dataset export 인프라
- task-specific validated robot learning data infrastructure

Quest/OpenXR/HMD 수집 경로는 삭제하지 않는다. 다만 현재 reset proof에서는
experimental input adapter로 격하하며, data trust layer primary proof나
buyer-facing readiness claim의 근거로 사용하지 않는다.

핵심 제품 방향은 다음이다.

> 데이터를 많이 모으는 것이 아니라, 로봇 학습에 실제로 쓸 수 있는 데이터를 선별하고 상품화한다.

---

## 2.1 RDF 데이터 파이프라인 원칙

RDF의 구현과 proof 판단은 아래 9개 원칙을 따른다.

1. Raw trajectory는 관대하게 저장한다. Raw evidence는 training eligible 여부와 별개로 보존한다.
2. Task success와 data quality를 분리한다. 성공한 task라도 tracking/action/replay 품질이 낮으면 training candidate가 아닐 수 있다.
3. Replay/action contract를 통과해야 training eligible이 된다. 저장된 action이 replay와 export에서 같은 의미를 가져야 한다.
4. Accepted/rejected reason을 curation manifest에 남긴다. 탈락 데이터도 왜 탈락했는지 증거가 남아야 한다.
5. BEHAVIOR식 task spec으로 goal, progress, efficiency를 정의한다. 최종 성공 flag만으로 task를 설명하지 않는다.
6. Episode outcome뿐 아니라 transition coverage를 기록한다. APPROACH, CONTACT, INSERT, SEAT 같은 phase 분포가 학습 가능성을 좌우한다.
7. HDF5/export와 trainer smoke를 통과한 dataset artifact를 만든다. 파일이 존재하는 것만으로 learning-ready라고 주장하지 않는다.
8. Policy uplift는 MVP-2로 넘긴다. MVP-1 완료 조건은 learning-ready dataset artifact이고, downstream learning performance는 MVP-2에서 검증한다.
9. Camera/HMD geometry는 버리지 않는다. HMD pose, operator view frame, camera intrinsics/extrinsics, task/robot/object visibility, world↔robot↔EEF↔task↔camera transform provenance를 raw evidence와 함께 저장하고, 시점 기반 보정은 raw action label을 덮어쓰지 않는 derived conditioning metadata로 분리한다.

---

## 3. 현재 Primary Proof Path

현재 MVP reset의 primary proof path는 HMD-free data trust layer 흐름을 기준으로 한다.

```text
scripted / synthetic replay fixture
→ trajectory + source provenance
→ action semantics normalization
→ ForgeSync
→ ForgeEval
→ ForgeCurate
→ Validated Dataset Export
→ trainer smoke
→ trust_record.json / buyer_dataset_card.json / proof_report.json
```

중요한 원칙:

- 첫 reset proof는 HMD-free여야 한다.
- Quest/OpenXR/HMD readiness, Gate A collection readiness, physical collection
  readiness, policy uplift를 이 proof에서 주장하지 않는다.
- 웹 mock task는 primary path가 아니다.
- 웹 mock task는 fallback, debug, test, demo 보조 경로다.
- MockSimAdapter가 data trust layer proof를 대체하는 primary path처럼 보이면 안 된다.
- Quest 3 + SteamVR/OpenXR + Isaac Lab 기반 수집은 experimental input adapter다.

### 3.1 Experimental Input Adapters

아래 경로는 보존하지만 현재 primary proof나 구매자 readiness claim의 기준으로
삼지 않는다.

```text
Quest 3 handtracking
→ ALVR + SteamVR/OpenXR
→ Isaac Lab teleoperation
→ Trajectory Recorder
→ Gate 0 / Gate A validation
```

이 adapter에서 생성된 trajectory는 Gate 0과 replay/action/data-quality gate를
통과하기 전까지 raw evidence로만 보존한다.

---

## 4. 초기 아이디어와 피벗

### 4.1 초기 아이디어

초기 아이디어는 다음과 같았다.

> 전 세계 VR 유저의 플레이를 로봇의 지능으로 바꾸는 데이터 크라우드소싱 플랫폼

초기 흐름:

```text
VR 유저
→ 로봇 조작 task 수행
→ trajectory 데이터 수집
→ 성공 데이터 선별
→ 로봇 회사 / AI 연구소에 데이터 판매
```

이 아이디어의 장점은 명확했다.

- 로봇 학습용 데이터 부족 문제를 겨냥한다.
- 실제 로봇 없이 시뮬레이션에서 데이터를 수집할 수 있다.
- Quest 같은 VR 기기 보급을 활용할 수 있다.
- Physical AI와 robot foundation model 시장 성장과 연결된다.

하지만 초기 아이디어는 투자자 관점에서 너무 넓었다.

- 고객이 불명확했다.
- 처음부터 양면 마켓플레이스를 전제했다.
- VR 유저 공급을 과대평가하기 쉬웠다.
- Sim-to-Real 가능성을 과장할 위험이 있었다.
- 데이터 품질 증명이 부족했다.
- “데이터를 모았다”와 “학습에 유용하다”는 완전히 다른 문제였다.

### 4.2 피벗 후 방향

기존 포지션:

> VR 유저가 로봇 데이터를 생산하는 크라우드소싱 플랫폼

피벗 후 포지션:

> 특정 로봇 조작 task를 위한 validated robot learning data infrastructure

즉, Robot Data Forge는 단순히 데이터를 많이 모으는 서비스가 아니다.

Robot Data Forge는 특정 조작 task에서 수집된 robot-action-labelled trajectory를 자동 검증하고, 큐레이션하여, policy 학습에 사용할 수 있는 validated dataset으로 만드는 데이터 인프라다.

---

## 5. MVP 단계 구분

### 5.1 MVP-0: Technical Pipeline Proof

MVP-0의 목적은 기술 파이프라인이 실제로 동작하는지 증명하는 것이다.

MVP-0에서 증명할 것:

- 안정적인 입력 소스(scripted fixture, synthetic replay fixture, operator
  control 등)가 Isaac Lab task 또는 동등한 검증 경로에 전달된다.
- episode start/stop lifecycle이 동작한다.
- end-effector pose, gripper/action, object state, timestamp가 frame 단위로 저장된다.
- source metadata와 runtime metadata가 trajectory에 포함된다.
- trajectory가 replay 가능하다.
- ForgeEval이 기본 success/failure와 score를 생성한다.
- JSON dataset export가 가능하다.
- Quest/OpenXR/HMD 입력은 이 목록의 primary proof 조건이 아니라 보존된
  experimental adapter 검증 조건이다.

MVP-0에서 사용할 수 있는 task:

- `Isaac-Stack-Cube-Franka-IK-Rel-v0`

주의:

- 이 task는 engineering smoke test다.
- customer wedge로 광고하면 안 된다.
- Stack cube 결과를 industrial insertion validation처럼 과장하면 안 된다.

### 5.2 MVP-1: Learning-Ready Dataset Pipeline Proof

MVP-1의 목적은 raw robot-action trajectory가 검증 가능한 학습 후보 dataset artifact와 buyer-facing trust record로 승격되는지 증명하는 것이다. 현재 reset proof는 HMD-free data trust layer 경로를 기준으로 하며, XR/HMD teleoperation은 별도 experimental adapter evidence로만 다룬다.

MVP-1은 아래 evidence chain을 닫으면 완료된다.

| Gate | 증명해야 할 것 |
|---|---|
| Raw trajectory saved | HMD-free scripted/synthetic replay fixture 또는 안정 입력 경로의 raw trajectory와 source metadata를 보존한다. Quest/SteamVR/OpenXR 경로는 experimental adapter 사용 시 별도 source metadata로 보존한다. |
| Task state extracted | peg-in-hole 또는 connector insertion의 task_state를 frame metadata로 기록한다. |
| Task outcome recorded | operator outcome, evaluator task success, finalize reason을 저장한다. |
| Data quality recorded | tracking loss, action saturation, retargeting jump, frame quality 같은 data quality를 별도로 저장한다. |
| Operator/evaluator separated | 사람이 성공했다고 본 사실과 evaluator가 성공으로 판정한 사실을 하나의 flag로 합치지 않는다. |
| Replay/action gate recorded | action contract와 replay 가능성을 training eligibility 전에 확인한다. |
| Camera conditioning recorded | HMD/operator camera geometry, view frame, transforms, visibility, projection smoke 결과를 저장하고, camera-conditioned downstream 학습에 쓸 수 있는지 별도 readiness로 판정한다. |
| Curation manifest generated | accepted/rejected reason을 manifest에 남긴다. |
| Transition coverage recorded | episode 결과뿐 아니라 APPROACH/CONTACT/INSERT/SEAT 같은 transition coverage를 기록한다. |
| HDF5/export generated | trainer가 읽을 수 있는 dataset artifact를 만든다. |
| Trainer smoke passed | dataset loader 또는 trainer smoke가 통과한다. |
| Dataset card generated | artifact의 claim, limitation, source, split, gate 결과를 사람이 읽을 수 있게 만든다. |

MVP-1의 claim은 다음 문장으로 제한한다.

> raw robot-action trajectory를 replay-verified, action-labelled, task-validated, trainer-loadable learning-candidate dataset artifact와 재현 가능한 trust record로 만드는 파이프라인을 완성했다.

2026-05-27 추가 결정: 기존 MVP-1 learning-ready proof는 robot/action/replay/export evidence로 보존한다. `camera-conditioning-ready`는 ForgeXR dataset claim의 신규 readiness gate이며, 실제 recorder/export/loader 구현과 projection smoke가 완료되기 전까지 current artifact를 camera-conditioned visual-policy material로 주장하지 않는다.

### 5.3 MVP-2: Learning-Proven Value Proof

MVP-2의 목적은 MVP-1 artifact가 downstream learning performance로 이어지는지 검증하는 것이다.

MVP-2에서 다룰 것:

- transition-rich accepted dataset
- stronger policy/trainer
- held-out policy A/B
- curated vs uncurated policy uplift
- world-model utility
- positive/negative result report

MVP-2 결과가 음성이어도 MVP-1 실패가 아니다. 음성 결과는 현재 데이터 규모, transition coverage, action contract, trainer, evaluator 중 어디가 병목인지 판단하는 evidence로 남긴다.

### 5.4 Spent Held-Out Discipline

Closed 또는 attempted closure에 사용된 held-out seed range는 이후 tuning,
threshold 조정, adapter 조정, comparator 조정, policy/trainer 조정, metric 조정,
curation rule 조정, future closure proof에 재사용하지 않는다.

현재 spent/audit-only/no-reuse range:

- `40000-40049`: MVP-2 v0.14 actual Isaac closure에 사용됨.
- `42000-42049`: MVP-3A `target_fixture_pose_variant` actual Isaac closure
  attempt에 사용됨.

허용되는 사용:

- audit
- provenance 확인
- buyer-facing limitation 설명
- regression fixture 설계 참고

금지되는 사용:

- 결과를 보고 policy, comparator, adapter, threshold, metric, trainer, curation
  rule을 조정하는 것
- 같은 range를 future closure proof나 fresh held-out으로 재사용하는 것
- 같은 range를 새 task/source expansion의 tuning evidence로 사용하는 것

MVP-3B 이후 proof attempt는 fresh pre-registered calibration/held-out range를
새로 잡고, 이전 spent range와 seed disjointness를 verifier 또는 package
manifest에서 명시해야 한다.

MVP-1에서 추천하는 task:

- Peg-in-hole
- Connector insertion

MVP-1에서 증명해야 할 것:

- task success criteria가 명확하다.
- ForgeEval이 자동으로 성공/실패와 조작 품질을 판정할 수 있다.
- ForgeCurate가 학습 가능한 trajectory를 선별할 수 있다.
- transition coverage와 replay/action contract가 training eligibility 전에 기록된다.
- dataset export가 고객 학습 파이프라인에 연결될 수 있다.
- 고객 또는 design partner가 이 task를 실제 산업용 manipulation 문제와 연결해서 이해할 수 있다.

핵심 문장:

> MVP-1은 “데이터를 저장할 수 있다”가 아니라 “우리가 저장한 raw teleop trajectory가 검증, 큐레이션, replay/action gate, export, trainer smoke를 통과한 learning-ready dataset artifact가 된다”를 증명해야 한다.

---

## 6. 최종 제품 구조

현재 기준 핵심 모듈은 다음과 같다.

| 모듈 | 역할 |
|---|---|
| ForgeTask | task 정의, 성공 조건, 환경 파라미터 관리 |
| ForgeXR | Quest 3 handtracking, SteamVR/OpenXR 입력 수집용 experimental adapter |
| ForgeIsaac | Isaac Lab task 실행, episode lifecycle 관리 |
| ForgeRecord | pose, action, object state, metadata를 trajectory로 저장 |
| ForgeSync | timestamp, frame drop, latency, handtracking loss 등 sync 품질 측정 |
| ForgeEval | success/failure뿐 아니라 조작 품질, 물리 타당성, 실패 원인 평가 |
| ForgeCurate | 학습에 쓸 가치가 있는 trajectory만 선별 |
| ForgePlay | replay, QA, mock fallback 화면 |
| ForgeOps | admin dashboard, KPI, dataset export 관리 |

---

## 7. 제품 변화의 핵심

기존 MVP는 다음에 가까웠다.

```text
trajectory 저장
→ success/failure 평가
→ dataset export
```

개선된 MVP는 다음을 목표로 한다.

```text
trajectory 저장
→ timestamp/sync 품질 검증
→ action phase segmentation
→ manipulation-aware validation
→ data usability scoring
→ curation reason tracking
→ LeRobot-compatible export readiness
→ curated vs uncurated policy uplift 추적 가능성 확보
```

가장 중요한 변화:

> Robot Data Forge는 데이터를 “모으는 회사”가 아니라, 로봇이 배울 수 있는 데이터인지 “검수해서 상품화하는 회사”가 된다.

---

## 8. 핵심 KPI 변화

### 8.1 약한 KPI

다음 지표만으로는 부족하다.

- recorded episodes
- trajectory count
- success count
- exported dataset count

이 지표는 활동량을 보여줄 뿐, 데이터 품질을 보장하지 않는다.

### 8.2 강한 KPI

앞으로 중요한 지표는 다음이다.

| KPI | 의미 |
|---|---|
| usable trajectory count | 실제 학습에 쓸 수 있는 trajectory 수 |
| accepted trajectory rate | 수집된 데이터 중 dataset에 들어간 비율 |
| data usability score | 학습 데이터로 쓸 수 있는 정도 |
| sync quality score | timestamp, frame, runtime 정렬 품질 |
| replayable trajectory rate | replay 가능한 trajectory 비율 |
| evaluator agreement rate | 사람 판정과 evaluator 판정 일치율 |
| curated vs uncurated uplift | 큐레이션된 데이터가 성능을 얼마나 올리는지 |
| cost per accepted trajectory | 학습 가능한 데이터 1개당 비용 |
| failure mode distribution | 실패 유형 분포 |
| average quality score | accepted trajectory 평균 품질 |

핵심 질문은 다음으로 바뀐다.

| 기존 질문 | 개선 후 질문 |
|---|---|
| 몇 개 찍었나? | 그중 몇 개가 학습에 쓸 수 있나? |
| 성공했나? | 성공 과정이 물리적으로 타당한가? |
| 저장됐나? | replay 가능하고 timestamp가 정렬됐나? |
| export됐나? | 고객 학습 파이프라인에 들어갈 수 있나? |
| 데이터가 많나? | policy 성능을 실제로 올렸나? |

---

## 9. ForgeSync 지침

ForgeSync는 데이터의 시간 정렬 품질을 평가하는 모듈이다.

로봇 데이터는 단순히 값이 있는 것이 중요하지 않다.

중요한 것은 다음이 같은 시점의 데이터인지다.

- action
- robot state
- object state
- timestamp
- XR input
- Isaac simulation state
- recorder timestamp

ForgeSync가 측정해야 할 것:

- sync_error_ms_mean
- sync_error_ms_p95
- clock_drift_ms_per_min
- xr_to_isaac_timestamp_offset_ms
- action_to_sim_state_offset_ms
- dropped_sensor_samples
- modality_alignment_status
- frame_drop_rate
- hand_tracking_loss_rate
- input_latency_ms

해야 할 것:

- session 단위 sync 품질 기록
- episode 단위 sync 품질 기록
- sync 품질이 낮은 trajectory를 low-usability로 분류
- sync 관련 KPI를 admin API 또는 dashboard에서 확인 가능하게 함

하지 말아야 할 것:

- timestamp가 불명확한 trajectory를 고품질 데이터로 취급하지 않는다.
- sync 품질을 측정하지 않고 정상이라고 가정하지 않는다.
- 누락된 timestamp를 임의로 채워 신뢰 가능한 값처럼 표시하지 않는다.

---

## 10. Data Usability Score 지침

Data Usability Score는 episode가 실제 학습 데이터로 쓸 수 있는지 평가하는 점수다.

예시 계산식:

```text
data_usability_score =
  0.25 * replayability_score
+ 0.25 * sync_quality_score
+ 0.20 * modality_completeness_score
+ 0.20 * evaluator_confidence
+ 0.10 * physical_plausibility_score
```

반영해야 할 요소:

- replay 가능 여부
- sync 품질
- 필수 modality 존재 여부
- evaluator confidence
- physical plausibility
- runtime metadata 존재 여부
- source metadata 존재 여부

해야 할 것:

- episode별 data usability score 산출
- usable / not usable 상태 구분
- not usable이면 rejection reason 기록
- admin KPI에 average_data_usability_score 노출

하지 말아야 할 것:

- 단순히 저장된 episode 수를 제품 성과로 과장하지 않는다.
- 필수 필드가 빠진 trajectory를 usable로 취급하지 않는다.
- replay 불가능한 trajectory를 학습용 dataset에 포함하지 않는다.

---

## 11. ForgeEval 지침

ForgeEval은 단순 success/failure 판정기가 아니라 manipulation-aware evaluator가 되어야 한다.

기존 수준:

- success = true / false
- score
- failure_reason

개선 후 평가해야 할 것:

- task_completion_score
- interaction_quality_score
- contact_sequence_score
- physical_plausibility_score
- stability_score
- efficiency_score
- smoothness_score
- data_usability_score
- evaluator_confidence
- failure_mode

Failure taxonomy에 포함할 수 있는 항목:

- TIMEOUT
- TARGET_MISSED
- UNSTABLE_FINAL_STATE
- NO_TRAJECTORY
- INVALID_TRAJECTORY
- OUT_OF_BOUNDS
- PHYSICALLY_IMPLAUSIBLE
- TRACKING_LOSS
- EXCESSIVE_COLLISION
- BAD_CONTACT_SEQUENCE
- GRIPPER_FAILURE
- OBJECT_DROPPED
- SIM_RUNTIME_ERROR
- SYNC_FAILURE
- INCOMPLETE_MODALITY
- LOW_REPLAYABILITY
- UNKNOWN

해야 할 것:

- task completion 평가
- interaction quality 평가
- contact sequence 평가
- physical plausibility 평가
- 실패 원인 기록
- evaluator confidence 기록
- human review와 비교 가능한 구조 유지

하지 말아야 할 것:

- 최종 위치만 맞았다고 좋은 trajectory로 간주하지 않는다.
- 물리적으로 부자연스러운 trajectory를 고품질 데이터로 분류하지 않는다.
- 실패 trajectory를 이유 없이 버리지 않는다.
- 실패 이유 없이 failure만 기록하지 않는다.

---

## 12. Action Phase Segmentation 지침

로봇 조작은 하나의 긴 좌표 로그가 아니라 여러 조작 phase로 구성된다.

지원해야 할 phase:

- APPROACH
- ALIGN
- CONTACT
- INSERT
- STABILIZE
- RELEASE
- RECOVER
- UNKNOWN

각 segment는 다음 정보를 가져야 한다.

- phase
- start_frame
- end_frame
- confidence
- source

해야 할 것:

- trajectory 또는 episode에 action segment 연결
- replay 또는 QA에서 phase 단위 확인 가능
- evaluator와 curator가 phase 정보를 활용할 수 있는 구조 제공

하지 말아야 할 것:

- 모든 trajectory를 phase 없는 frame sequence로만 취급하지 않는다.
- 실패 원인을 episode 전체 단위로만 기록하지 않는다.
- phase confidence 없이 확정적 라벨처럼 표시하지 않는다.

---

## 13. ForgeCurate 지침

ForgeCurate는 성공 trajectory만 모으는 기능이 아니다.
학습에 쓸 가치가 있는 trajectory를 선별하는 제품 핵심 레이어다.

Dataset 포함 기준 예시:

```text
success == true
AND quality_score >= min_quality_score
AND data_usability_score >= min_data_usability_score
AND is_duplicate == false
AND fraud_risk_score < threshold
AND sync_quality_score >= min_sync_quality_score
AND replayable == true
```

Rejection reason 예시:

- LOW_QUALITY_SCORE
- LOW_DATA_USABILITY
- DUPLICATE_TRAJECTORY
- HIGH_FRAUD_RISK
- SYNC_FAILURE
- NOT_REPLAYABLE
- TASK_FAILURE
- MISSING_REQUIRED_MODALITY

해야 할 것:

- dataset 포함 여부 판단
- 제외된 trajectory의 rejection reason 기록
- 중복 trajectory 제거
- low-quality trajectory 제외
- low-usability trajectory 제외
- not replayable trajectory 제외
- curation rule을 dataset metadata에 저장

하지 말아야 할 것:

- 성공했다는 이유만으로 dataset에 포함하지 않는다.
- 제외된 trajectory를 rejection reason 없이 버리지 않는다.
- 중복 trajectory를 고품질 데이터처럼 취급하지 않는다.
- curation 기준을 metadata에 남기지 않는 방식으로 구현하지 않는다.

---

## 14. Export 지침

Export는 단순 파일 저장이 아니라 고객 학습 파이프라인에 연결되는 제품화 단계다.

지원 방향:

- json
- hdf5_placeholder
- lerobot_v3_placeholder

JSON export는 유지한다.
HDF5와 LeRobot-compatible export는 MVP에서 완전 구현하지 않아도 되지만, metadata 구조와 service interface는 준비해야 한다.

LeRobot-compatible export readiness에 필요한 정보:

- robot_type
- fps
- total_episodes
- total_frames
- observation.state
- action
- timestamp
- frame_index
- episode_index
- task_index
- train/validation/test split
- evaluator_version
- curation_rules
- limitations

해야 할 것:

- dataset card 생성에 필요한 metadata 포함
- 지원하지 않는 export format은 명확히 거부
- export 결과가 재현 가능해야 함
- simulation-only dataset은 limitations에 명시

하지 말아야 할 것:

- 독자 JSON 파일만 만들고 고객 학습 파이프라인 연결성을 무시하지 않는다.
- 지원하지 않는 export format을 조용히 성공 처리하지 않는다.
- dataset limitations를 숨기지 않는다.
- simulation-only dataset을 real robot validated dataset처럼 표현하지 않는다.

---

## 15. Admin Dashboard / QA 지침

Admin dashboard는 단순 상태 표시가 아니라 데이터 품질을 검토하는 QA 도구여야 한다.

보여줘야 할 정보:

- end-effector path
- object path
- gripper state timeline
- timestamp timeline
- action phase overlay
- evaluator score overlay
- failure frame marker
- accepted/rejected reason
- sync quality summary
- data usability score

KPI 범주:

- Collection KPI
- XR / Isaac Runtime KPI
- Sync KPI
- Evaluation KPI
- Curation KPI
- Data Usability KPI
- Learning KPI

하지 말아야 할 것:

- 측정되지 않은 KPI를 측정된 것처럼 표시하지 않는다.
- 실제 학습 실험 없이 policy uplift를 가짜로 만들지 않는다.
- placeholder 값은 반드시 placeholder임을 명시한다.
- dashboard 시각적 완성도를 데이터 품질보다 우선하지 않는다.

---

## 16. Public Artifact 지침

공개 가능한 demo dataset 또는 dataset card를 만들 수 있어야 한다.

Dataset card에 포함할 정보:

- dataset_name
- task_description
- robot
- simulator
- input_device
- num_episodes
- num_accepted
- num_rejected
- success_criteria
- evaluator_version
- curation_rules
- train/validation/test split
- limitations

해야 할 것:

- 공개 가능한 demo/synthetic/Isaac task dataset 중심으로 준비
- limitations 명시
- accepted/rejected ratio 명시
- evaluator version 명시
- curation rules 명시

하지 말아야 할 것:

- 고객 private data를 공개하지 않는다.
- private task spec을 공개하지 않는다.
- demo dataset을 실제 고객 데이터처럼 표현하지 않는다.
- limitations 없이 dataset을 공개하지 않는다.

---

## 17. Required Existing Models

기존 모델은 유지한다.

- Task
- Episode
- Trajectory
- Evaluation
- Dataset
- CollectionSession
- HumanReview
- LearningExperiment

기존 모델과 가능한 한 backward-compatible해야 한다.

---

## 18. Required New or Extended Models

필요한 경우 다음 모델 또는 필드를 추가한다.

- AcquisitionConfig
- SyncMetrics
- ActionSegment
- DataUsabilityScore
- LeRobotExportMetadata
- DatasetCard metadata
- Curator rejection reason
- Unit economics placeholder fields

모든 모델 원칙:

- schema_version 유지
- source metadata 유지
- runtime metadata 유지
- task_id, episode_id, trajectory_id 연결성 유지
- JSON export와 DB 저장 모두 가능
- 향후 LeRobot-compatible export와 충돌하지 않음
- 기존 API와 가능한 한 backward-compatible

---

## 19. Required Source Metadata

Trajectory에는 다음 source 필드가 누락되면 안 된다.

- input_device
- runtime
- simulator
- robot
- task_name

예시:

- input_device: quest3_handtracking
- runtime: steamvr_openxr
- simulator: isaac_lab
- robot: franka
- task_name: Isaac-Stack-Cube-Franka-IK-Rel-v0 또는 peg_in_hole

하지 말아야 할 것:

- source metadata 없이 trajectory를 저장하지 않는다.
- task_name이 없는 trajectory를 export하지 않는다.
- simulator와 runtime을 혼동하지 않는다.

---

## 20. Required Runtime Metadata

Session 또는 trajectory frame에는 가능한 범위에서 runtime metadata를 기록해야 한다.

권장 metadata:

- right_hand_tracked
- left_hand_tracked
- tracking_confidence
- pinch_strength
- xr_frame_valid
- input_latency_ms
- sim_fps
- frame_drop_rate
- hand_tracking_loss_rate
- session_crashed
- sync_error_ms
- timestamp_source

하지 말아야 할 것:

- handtracking loss를 무시하지 않는다.
- frame drop을 무시하지 않는다.
- runtime metadata가 없는데 있는 것처럼 표시하지 않는다.

---

## 21. Unit Economics Tracking

실제 결제와 보상은 구현하지 않는다.

하지만 future unit economics 추정을 위해 다음 필드는 기록 가능해야 한다.

- human_time_sec
- compute_time_sec
- cost_per_recorded_episode
- cost_per_accepted_trajectory
- evaluation_runtime_ms
- storage_bytes
- export_runtime_ms

하지 말아야 할 것:

- 실제 결제를 구현하지 않는다.
- 보상 지급을 구현하지 않는다.
- 정산 시스템을 구현하지 않는다.
- KYC를 구현하지 않는다.
- 비용 추정 필드를 실제 지급 내역처럼 표현하지 않는다.

---

## 22. API Expectations

기존 API는 가능한 한 유지한다.

필요하면 다음 기능을 API로 제공한다.

- acquisition config 생성/조회
- sync metrics 생성/조회
- action segment 생성/조회
- episode usability 조회
- admin KPI 조회
- dataset export 요청
- dataset card 조회
- human review 생성/조회
- learning experiment 생성/조회

API 원칙:

- request/response schema가 명확해야 한다.
- OpenAPI에 표시되어야 한다.
- 오류 응답이 명확해야 한다.
- unsupported export format은 명확히 거부해야 한다.
- MVP 범위 밖 기능을 암묵적으로 추가하면 안 된다.

---

## 23. Migration Expectations

새 모델이나 필드가 추가되면 Alembic migration을 포함한다.

Migration 대상 예시:

- acquisition_configs
- sync_metrics
- action_segments
- data_usability_scores
- lerobot_export_metadata

기존 테이블 확장 예시:

- episodes.replayable
- episodes.human_time_sec
- episodes.compute_time_sec
- episodes.cost_per_recorded_episode
- episodes.cost_per_accepted_trajectory
- evaluations.task_completion_score
- evaluations.interaction_quality_score
- evaluations.contact_sequence_score
- evaluations.physical_plausibility_score
- evaluations.data_usability_score
- evaluations.evaluator_confidence
- evaluations.failure_mode
- datasets.export_format
- datasets.dataset_card_path
- datasets.lerobot_metadata_path

---

## 24. Testing Expectations

테스트는 데이터 품질과 제품 핵심 로직을 검증해야 한다.

필수 테스트 범주:

- sync metrics computation
- data usability score
- action segmentation
- manipulation-aware evaluator
- curator rejection reasons
- dataset card generation
- export format validation
- unsupported export format handling
- KPI aggregation
- required source metadata validation

테스트는 pytest로 실행 가능해야 한다.

---

## 25. Validation Expectations

작업 결과는 다음 방식으로 검증 가능해야 한다.

- pytest 실행
- API curl 호출
- dataset export 요청
- admin KPI 조회
- trajectory evaluation 실행
- curation rule 적용 결과 확인
- dataset card 생성 확인

검증 결과는 응답에 포함해야 한다.

---

## 26. Competitive Positioning

### 26.1 OpenGraphLabs 대비

OpenGraphLabs는 일반 참여자 기반 현실 세계 멀티모달 행동 데이터 수집에 가깝다.

Robot Data Forge는 특정 로봇 조작 task의 action-labelled trajectory를 검증해 학습 데이터로 만든다.

정리:

```text
OpenGraphLabs:
real-world multimodal human behavior data

Robot Data Forge:
task-specific robot-action trajectory validation pipeline
```

Robot Data Forge는 OpenGraphLabs와 같은 일반 행동 영상 수집 앱으로 포지셔닝하지 않는다.

### 26.2 Assured Robot Intelligence / Meta 대비

Assured Robot Intelligence는 Meta에 인수된 robot foundation model / humanoid intelligence 쪽 회사다.

공동창업자 Lerrel Pinto와 Xiaolong Wang의 연구 방향은 다음과 강하게 연결된다.

- robot learning
- generalization
- adaptation
- teleoperation
- dexterous manipulation
- world models
- humanoid control
- high-quality demonstrations

하지만 Robot Data Forge는 이들과 모델 레이어에서 경쟁하지 않는다.

차별화 문장:

```text
ARI builds robot intelligence.
Robot Data Forge builds the validated task data that robot intelligence needs.
```

한국어:

```text
ARI가 로봇의 두뇌를 만든다면,
Robot Data Forge는 그 두뇌가 학습할 수 있는 검증된 경험 데이터를 만든다.
```

하지 말아야 할 것:

- robot foundation model 직접 개발
- humanoid general intelligence 주장
- whole-body humanoid control 구현
- ARI / Meta와 모델 레이어에서 정면 경쟁

집중해야 할 것:

- Quest/Isaac 기반 teleoperation trajectory 수집
- high-quality demonstration 선별
- noisy human trajectory의 usability 평가
- action phase segmentation
- manipulation-aware validation
- curated vs uncurated policy uplift 추적
- robot model team이 바로 사용할 수 있는 learning-ready dataset export

---

## 27. ARI 기반 전략 반영

Assured Robot Intelligence 사례는 Robot Data Forge의 방향을 더 명확하게 만든다.

### 27.1 ARI에서 배울 점

ARI와 창업자들의 연구 흐름에서 가져올 핵심은 다음이다.

- 좋은 로봇 지능은 좋은 trajectory data에서 나온다.
- 좋은 trajectory data는 단순 수집이 아니라 품질 검증이 필요하다.
- VR/Quest 기반 teleoperation은 데이터 수집 인터페이스로 유효하다.
- noisy human trajectory를 task-centric learning data로 구조화해야 한다.
- 적은 수의 고품질 demonstration이 더 큰 가치를 만들 수 있다.
- 데이터가 실제 policy 성능을 개선하는지 추적해야 한다.
- cross-robot / LeRobot-compatible 데이터 표준화가 중요하다.
- tactile, humanoid whole-body control, generative task generation은 post-MVP로 보류해야 한다.

### 27.2 ARI 기반으로 강화할 제품 요소

반드시 강화해야 할 요소:

- Quest/VR teleoperation diagnostics
- raw_action / applied_action logging
- calibration analyzer
- data usability score
- manipulation-aware ForgeEval
- action phase segmentation
- curated vs uncurated policy uplift tracking
- LearningExperiment model
- LeRobot-compatible export readiness
- DatasetCard
- reusable evaluator library

### 27.3 ARI 기반으로 하지 말아야 할 것

ARI를 보고 다음 방향으로 가면 안 된다.

- foundation model 직접 개발
- humanoid general intelligence 주장
- whole-body humanoid control 구현
- full RL pipeline 구현
- Meta/ARI와 모델 레이어 경쟁
- 너무 넓은 robotics intelligence 회사로 포지셔닝

Robot Data Forge의 정확한 위치는 다음이다.

> Robot foundation model 팀이 필요로 하는 validated task trajectory data layer.

---

## 28. 연구 방향에서 가져올 제품 철학

### 28.1 OPEN TEACH / Holo-Dex에서 가져올 점

Quest/VR 기반 teleoperation은 단순 gimmick이 아니라 로봇 demonstration 수집 인터페이스가 될 수 있다.

반영할 것:

- teleop quality metric
- raw_action / applied_action logging
- workspace alignment metadata
- calibration preset
- handtracking confidence
- tracking loss
- input latency

### 28.2 From Play to Policy / C-BeT에서 가져올 점

비전문가가 만든 데이터는 noisy하고 inconsistent할 수 있다.
중요한 것은 이 데이터를 버리는 것이 아니라 task-centric behavior로 구조화하는 것이다.

반영할 것:

- ForgeCurate
- ActionSegment
- DataUsabilityScore
- accepted/rejected reason
- noisy trajectory filtering

### 28.3 FISH / BAKU에서 가져올 점

적은 수의 고품질 demonstration으로도 policy 성능을 올릴 수 있다.

반영할 것:

- demos_per_task
- success_rate_by_demo_count
- curated_vs_uncurated_uplift
- data_efficiency_gain

### 28.4 Robot Utility Models에서 가져올 점

핵심은 diverse yet high-quality demonstrations다.

반영할 것:

- data quality
- diversity
- usability
- task-specific validation
- failure mode analysis

### 28.5 Open X-Embodiment에서 가져올 점

데이터는 향후 cross-robot, cross-embodiment 확장이 가능해야 한다.

반영할 것:

- robot
- embodiment
- gripper
- action_space
- observation_space
- task_name
- source
- dataset format
- LeRobot-compatible export readiness

### 28.6 Dex1B / GenSim에서 가져올 점

Synthetic/generative demonstration과 task generation은 미래 확장 가능성이 있다.

하지만 지금은 구현하지 않는다.

Post-MVP로 보류할 것:

- generated trajectory source
- geometric constraint score
- diversity score
- simulation task generator

### 28.7 Tactile 계열에서 가져올 점

Contact-rich manipulation에서는 tactile이 중요하다.
하지만 지금 구현하면 MVP 범위가 터진다.

Post-MVP placeholder만 남긴다.

예시:

- contact_event
- pressure_map
- slip_event
- grip_force_estimate
- tactile_source

---

## 29. Quest 착용 전 디버깅 우선순위

Quest 착용 전에는 실제 좌표계 감각을 확정할 수 없다.

따라서 지금 해야 할 일은:

> 한 번 착용했을 때 바로 원인을 좁힐 수 있는 계측과 도구를 준비하는 것.

가장 효율적인 조합:

```text
3 + 2 + 1
```

즉:

### 29.1 XR/SteamVR/ALVR preflight checker

착용 전 환경 문제를 제거한다.

체크할 것:

- SteamVR OpenXR runtime
- ALVR dashboard
- NVIDIA offload
- CPU powersave 여부
- API server 상태
- Isaac script 존재 여부
- recording directory
- storage path writable 여부

### 29.2 Latest recording validator

실기기 테스트 직후 데이터가 제대로 찍혔는지 확인한다.

체크할 것:

- action.raw
- action.applied
- control_filter
- workspace_alignment_v2
- calibration offset
- frame count
- source metadata
- runtime metadata

### 29.3 Teleop calibration analyzer

좌표계/감각 문제를 수치로 분석한다.

체크할 것:

- raw_action range
- applied_action range
- jump count
- jitter score
- smoothing effect
- per-axis min/max/std
- workspace alignment
- calibration preset

### 29.4 Calibration preset

가볍게 추가한다.

예시:

- default
- low_gain
- axis_x_negz_y
- axis_x_z_negy

### 29.5 HDF5/export 확인은 보류

HDF5/export raw/applied action 반영 확인은 지금은 후순위다.

이유:

- 먼저 실기기 trajectory가 안정적으로 쌓이는지 확인해야 한다.
- export/training sanity check는 그 다음 단계가 더 효율적이다.

---

## 30. MVP 범위에서 하지 말아야 할 것

다음은 MVP에서 구현하지 않는다.

- 실제 결제
- 실제 보상 지급
- KYC
- 정산 시스템
- 마켓플레이스
- 실제 로봇 제어
- CloudXR
- tactile hardware integration
- production authentication
- full reinforcement learning pipeline
- 자율주행 데이터
- 범용 휴머노이드 task
- 대규모 real-world data collection operation
- 고객 private data 공개
- 보안상 민감한 credential 저장
- 가짜 학습 결과 생성
- 측정하지 않은 KPI를 측정된 것처럼 표시

---

## 31. Post-MVP로 보류할 것

다음은 roadmap에만 기록한다.

- reward/bounty system
- tactile extension 실제 구현
- real robot replay
- customer workspace
- Hugging Face publish automation
- production authentication
- paid pilot billing
- marketplace
- full reinforcement learning pipeline
- real-world hardware fleet
- multi-user real-time collaboration
- generated demonstration pipeline
- task generator

---

## 32. Output Requirements

코딩 에이전트는 매 작업마다 다음 순서로 보고해야 한다.

1. 작업 요약
2. 변경/생성 파일 트리
3. 핵심 변경 내용
4. DB migration 요약
5. API contract 변경 요약
6. 테스트 및 검증 방법
7. 충족한 목표 항목
8. 남은 TODO
9. MVP 범위 밖으로 보류한 항목

코드를 제시해야 하는 경우:

- 각 파일별로 분리해서 제시한다.
- 언어 태그를 명시한다.
- 상대경로를 명확히 표시한다.
- 기존 파일 수정인지 신규 파일인지 표시한다.

---

## 33. Continuous Execution Rules

Ralph loop처럼 목표 달성까지 반복적으로 작업한다.

각 반복에서 다음을 수행한다.

1. 현재 상태 파악
2. 이번 반복에서 달성할 목표 선택
3. MVP 범위 검증
4. 필요한 변경 수행
5. 테스트 또는 검증 수행
6. 완료된 항목과 남은 항목 보고
7. 다음 반복에서 해야 할 일 명시

구체적인 구현 방법을 사용자에게 장황하게 설명하지 않는다.
결과, 변경사항, 검증 결과, 다음 목표 중심으로 보고한다.

---

## 34. Stop Rules

다음 상황에서는 구현을 중단하고 보고한다.

- 기존 명세와 충돌
- task 정의 불명확
- success criteria 불명확
- export format 요구 모호
- repo 구조와 목표 구조가 크게 충돌
- IsaacLabAdapter 구현 불가능
- MVP 범위 밖 기능 요구
- handtracking loss 과다
- evaluator false positive 과다
- curated dataset uplift 확인 불가
- accepted trajectory당 비용 과다
- insertion success 정의 불가
- 고객 private data 공개 위험
- credential 또는 민감 정보 노출 위험

중단 시 보고할 것:

1. 무엇 때문에 중단했는가
2. 어떤 목표 또는 제약과 충돌하는가
3. 가능한 선택지는 무엇인가
4. 추천하는 다음 행동은 무엇인가

---

## 35. Fallback Rules

IsaacLabAdapter가 실패하면 MockSimAdapter로 fallback할 수 있다.

하지만 반드시 다음을 지킨다.

- fallback 사실을 명확히 표시한다.
- fallback을 primary path처럼 표현하지 않는다.
- fallback 결과와 Isaac 기반 결과를 구분한다.
- fallback은 debug/test/demo 보조 경로로만 사용한다.

---

## 36. Quality Bar

완료된 작업은 다음 기준을 만족해야 한다.

- schema가 명확하다.
- API contract가 명확하다.
- migration이 포함된다.
- 테스트 가능하다.
- 실패 이유가 기록된다.
- KPI가 집계 가능하다.
- dataset export가 재현 가능하다.
- MVP 범위를 넘지 않는다.
- 향후 LeRobot-compatible export와 충돌하지 않는다.
- 데이터 품질을 설명할 수 있다.
- 투자자와 고객에게 보여줄 수 있는 evidence artifact로 이어진다.

---

## 37. CEO 관점 한 문장

Robot Data Forge는 데이터를 “모으는 회사”가 아니라, 로봇이 배울 수 있는 데이터인지 “검수해서 상품화하는 회사”가 된다.

---

## 38. 투자자 관점 한 문장

Robot Data Forge is a task-validated robot trajectory data infrastructure that turns teleoperated manipulation attempts into learning-ready datasets with measurable quality, usability, and policy improvement potential.

한국어:

Robot Data Forge는 사람이 조작한 로봇 trajectory를 검증·큐레이션하여, 학습 가능한 데이터셋으로 바꾸는 task-validated 로봇 데이터 인프라다.

---

## 39. 최종 결론

Robot Data Forge의 방향은 다음으로 확정된다.

모델을 만들지 않는다.
휴머노이드 범용 지능을 주장하지 않는다.
일반 행동 영상 앱으로 가지 않는다.
보상형 crowd app을 전면에 내세우지 않는다.

대신:

특정 조작 task의 robot-action trajectory를 검증하고,
학습 가능한 dataset으로 만들어,
모델 팀과 산업용 로봇 팀이 바로 쓸 수 있게 한다.

가장 중요한 제품 철학은 다음이다.

> 좋은 로봇 지능은 좋은 trajectory data에서 나오고, 좋은 trajectory data는 단순 수집이 아니라 teleoperation quality, sync, usability, phase, validation, curation, export까지 갖춘 제품이어야 한다.

이것이 Robot Data Forge의 현재 전략, MVP 방향, 경쟁 차별화, 개발 지침의 전체 결과다.
