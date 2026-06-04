# Teleoperation 입력스트림 정확도 딥 리서치

Date: 2026-05-28
Status: RDF raw-wrist / Quest 3 / ALVR / SteamVR OpenXR 입력 품질 개선을 위한 연구 메모
Scope: MVP-1 Gate A 재개 전, 손 입력 신호 튐과 tracking loss를 줄이기 위한 논문/공식 문서 기반 의사결정

---

## 1. 한 줄 결론

현재 RDF의 문제는 단순히 “Wi-Fi가 느려서”가 아니라, **OpenXR hand joint pose의 validity, tracking loss, valid-to-valid pose spike, 재획득(reacquire) 정책, smoothing 순서, task-level 보조장치가 모두 얽힌 입력스트림 품질 문제**다.

따라서 red flag를 완화해서 데이터를 받아들이면 안 된다. 먼저 아래 순서로 막아야 한다.

```text
1) invalid / untracked sample 제거
2) 비현실적인 wrist jump / velocity outlier hold
3) 안정 재획득 후 rebase
4) 그 다음 adaptive smoothing
5) 마지막으로 motion scaling / virtual fixture를 assist metadata로 별도 기록
```

---

## 2. 현재 RDF 증거

최근 `raw-wrist-direct` physical run은 schema/action contract 자체는 통과했지만, 학습 후보로는 아직 위험하다.

| 항목 | 값 |
|---|---:|
| trajectory | `traj_b804823e845a` |
| episode | `episode_0fbcc5f783b4` |
| evaluation | `eval_88c6e66f9dff` |
| task | `Isaac-Forge-PegInsert-Direct-v0` |
| frame count | `180` |
| failure_reason | `TRACKING_LOSS` |
| tracking_loss_rate | `0.4444444444` |
| right_hand_tracked_rate | `0.5777777778` |
| xr_frame_valid_rate | `0.5555555556` |
| gate accepted / warn / held | `54 / 10 / 116` |
| valid-to-valid raw wrist jumps > 10cm | `27` |
| max valid-to-valid jump | `0.9097165936 m` |
| H14 target accumulation | `PASS` |
| H15 scene-state discontinuity | `PASS` |

해석:

- 로봇이 전혀 안 움직이는 것은 아니다. H7은 방향 응답을 통과했다.
- target accumulation 가설은 최신 run에서 지지되지 않는다.
- 최신 핵심 blocker는 H9/H13: **tracking loss와 raw wrist spike**다.
- 90cm급 valid-to-valid wrist jump는 사람 손 움직임으로 보기 어렵다. smoothing으로 “부드럽게” 만들 대상이 아니라, 먼저 outlier로 hold/reject해야 한다.

---

## 3. 공식 API/런타임 근거

### 3.1 OpenXR hand joint는 `valid` flag가 먼저다

OpenXR `XR_EXT_hand_tracking`의 `xrLocateHandJointsEXT`는 특정 시간의 hand joint 배열을 base space 기준으로 반환한다. `XrHandJointLocationEXT`에는 `locationFlags`, `pose`, `radius`가 있고, `locationFlags`는 어떤 데이터가 valid인지 나타낸다. spec은 flag bit가 하나도 없으면 다른 필드를 valid/meaningful로 보면 안 된다고 설명한다.

RDF implication:

- `pose` 숫자가 finite라고 바로 control에 쓰면 안 된다.
- 가능하면 Isaac/OpenXR layer에서 `XR_SPACE_LOCATION_POSITION_VALID_BIT`, `XR_SPACE_LOCATION_POSITION_TRACKED_BIT` 계열 정보를 frame metadata로 저장해야 한다.
- 현재처럼 `pose=[0,0,0]`, anchor fallback, invalid hand가 섞이면 `raw`는 저장하되 `training_eligible=false`가 맞다.

Source:

- Khronos OpenXR `xrLocateHandJointsEXT`: https://registry.khronos.org/OpenXR/specs/1.0/man/html/xrLocateHandJointsEXT.html
- Khronos OpenXR `XrHandJointLocationEXT`: https://registry.khronos.org/OpenXR/specs/1.0/man/html/XrHandJointLocationEXT.html

### 3.2 Unity XR Hands도 `isTracked` / `trackingState`를 분리한다

Unity XR Hands 문서는 손 데이터가 root pose, joint pose, joint velocity 등을 제공하고, provider가 매 update마다 모든 데이터를 항상 제공하지 않을 수 있으므로 `trackingState`로 유효성을 확인해야 한다고 설명한다. `XRHand.isTracked`는 마지막 hand data update 기준으로 root pose와 joints가 추적 중인지 알려준다.

RDF implication:

- `right_hand_tracked`, `xr_frame_valid` 같은 현재 metadata 방향은 맞다.
- 다음 단계는 단일 boolean이 아니라 joint별/pose별 validity와 sample timestamp를 최대한 보존하는 것이다.

Source:

- Unity XR Hands `XRHand.isTracked`: https://docs.unity.cn/Packages/com.unity.xr.hands%401.4/api/UnityEngine.XR.Hands.XRHand.isTracked.html
- Unity XR Hands data model: https://docs.unity.cn/Packages/com.unity.xr.hands%401.4/manual/hand-data/xr-hand-data-model.html

### 3.3 ALVR/Wi-Fi는 latency와 frame 문제를 만들 수 있지만, 단독 원인으로 확정하면 안 된다

ALVR 문서는 streaming path가 control socket과 stream socket을 쓰며, tracking/button data를 SteamVR에 push한다고 설명한다. 또한 VR streaming은 tracking poll time, prediction offset, compositor latency까지 얽히며, overloaded decoder/network에서는 laggy/frozen controller, erroneous head tracking, stream freeze 같은 증상이 생길 수 있다.

RDF implication:

- Wi-Fi/ALVR는 **latency, frame freeze, stale pose, prediction mismatch**의 원인이 될 수 있다.
- 하지만 최신 RDF 증상은 `invalid_right_hand`, `anchor_fallback`, `valid-to-valid 0.9m wrist jump`까지 포함한다.
- 따라서 “Wi-Fi 때문”이라고 단정하려면 ALVR latency graph, packet loss, OpenXR sample timestamp, RDF `input_latency_ms`를 동시에 기록해야 한다.

Source:

- ALVR troubleshooting: https://github.com/alvr-org/ALVR/wiki/Troubleshooting
- ALVR architecture/timing: https://github.com/alvr-org/ALVR/wiki/How-ALVR-works

---

## 4. Quest handtracking 정확도 논문

### 4.1 Quest Pro / Quest 3 markerless hand-tracking robotic characterization

Godden et al.은 robot manipulator를 사용해 Meta Quest Pro와 Quest 3 hand-tracking의 positional accuracy, jitter, latency를 측정했다. PubMed abstract 기준, Quest 3는 조건이 좋을 때 평균 positional error가 약 `1.73 cm`, jitter가 약 `1.11 cm`였고, latency는 `14.4–220.5 ms`로 매우 가변적이었다. 또한 hand proximity, hand rotation, tracking feature로 선택한 joint가 성능에 영향을 준다고 보고했다.

RDF implication:

- 정상 환경에서도 cm급 error와 variable latency가 있다.
- RDF에서 `RDF_DIRECT_EE_DEADZONE_M=0.003` 같은 mm급 deadzone은 Quest markerless handtracking의 실제 jitter보다 작을 수 있다.
- 단, 논문의 cm급 jitter와 최신 RDF의 90cm spike는 다른 문제다. cm급 jitter는 filter 대상이고, 90cm spike는 validity/outlier gate 대상이다.

Source:

- Godden, Steedman, Pan, “Robotic Characterization of Markerless Hand-Tracking on Meta Quest Pro and Quest 3 Virtual Reality Headsets”, IEEE TVCG 2025 / PubMed: https://pubmed.ncbi.nlm.nih.gov/40053653/

### 4.2 Quest 2 hand-tracking accuracy framework

Quest 2를 대상으로 한 methodological framework 연구는 VR markerless hand-tracking 데이터를 신뢰하려면 lens/space correction과 측정 framework가 필요하다는 점을 강조한다.

RDF implication:

- operator별/방별 calibration과 tracking quality preflight는 선택이 아니다.
- raw data를 보존하고 derived alignment를 따로 기록하는 RDF 원칙은 문헌과 맞다.

Source:

- “A methodological framework to assess the accuracy of virtual reality hand-tracking systems: A case study with the Meta Quest 2”, PubMed: https://pubmed.ncbi.nlm.nih.gov/36781700/

---

## 5. 필터링/스무딩 계열 논문

### 5.1 One Euro Filter

Casiez, Roussel, Vogel의 One Euro Filter는 interactive system의 noisy input에서 jitter와 lag를 함께 줄이기 위한 adaptive low-pass filter다. 낮은 속도에서는 cutoff를 낮춰 jitter를 줄이고, 빠른 움직임에서는 cutoff를 높여 lag를 줄인다.

RDF implication:

- RDF raw wrist에는 moving average보다 One Euro 계열이 적합하다.
- 그러나 적용 순서가 중요하다.

```text
잘못된 순서: spike 포함 raw pose -> smoothing -> robot command
올바른 순서: validity/jump/velocity gate -> stable pose -> One Euro smoothing -> bounded servo
```

- 0.9m spike를 One Euro로 “부드럽게” 만들면 잘못된 target이 몇 frame 동안 남을 수 있다.

Source:

- Casiez et al., “1€ Filter: A Simple Speed-based Low-pass Filter for Noisy Input in Interactive Systems”, CHI 2012: https://gery.casiez.net/publications/CHI2012-casiez.pdf

### 5.2 Tremor suppression / Kalman / adaptive filtering

Teleoperation 분야에서는 손 떨림을 줄이기 위해 weighted-frequency filter, Kalman filter, adaptive filter, broad-learning filter 등이 오래전부터 연구되었다. 예를 들어 Riviere and Thakor는 glove-based dexterous teleoperation에서 tremor model을 빼는 방식으로 RMS error를 줄였다고 보고했다. 최근 teleoperation tremor attenuation 연구들도 filtering이 precision task에서 중요하다고 본다.

RDF implication:

- 작은 고주파 tremor에는 filter가 효과적이다.
- 하지만 RDF의 큰 jump는 tremor가 아니다.
- Kalman/EKF도 measurement outlier가 들어오면 state가 오염될 수 있으므로 innovation gate / residual gate가 먼저 필요하다.

Source:

- Riviere and Thakor, “Suppressing pathological tremor during dextrous teleoperation”, CMU RI: https://publications.ri.cmu.edu/suppressing-pathological-tremor-during-dextrous-teleoperation
- “An Incremental Broad-Learning-System-Based Approach for Tremor Attenuation for Robot Tele-Operation”, PMC: https://pmc.ncbi.nlm.nih.gov/articles/PMC10378126/
- “IMU Motion Capture Method with Adaptive Tremor Attenuation in Teleoperation Robot System”, PMC: https://pmc.ncbi.nlm.nih.gov/articles/PMC9100553/

---

## 6. Motion scaling / virtual fixture / shared control

### 6.1 Motion scaling

High-delay surgical teleoperation 연구에서는 latency가 precision과 error를 악화시키며, motion scaling이 operator accuracy와 error rate를 개선할 수 있다고 보고한다.

RDF implication:

- peg insertion에서는 `position_gain`을 낮추는 것이 단순 감도 조절이 아니라 data quality 전략이다.
- 단, motion scaling 값은 반드시 frame/session metadata로 남겨야 한다.
- scaling이 들어간 action은 `raw_operator_motion`과 `assisted_control`을 분리해야 한다.

Source:

- Richter, Orosco, Yip, “Motion Scaling Solutions for Improved Performance in High Delay Surgical Teleoperation”, ICRA 2019: https://arxiv.org/abs/1902.03290

### 6.2 Virtual fixture

Virtual fixture 연구는 목표와 제약이 알려져 있을 때 operator motion을 task geometry에 맞춰 제한/보조하면 precision이 좋아질 수 있음을 보여준다. Handheld micromanipulation 논문은 tremor compensation과 motion scaling, position-based virtual fixture를 함께 다룬다.

RDF implication:

- peg-in-hole task에는 `approach cone`, `hole axis guide`, `insertion axis clamp`, `lateral clamp` 같은 virtual fixture가 적합하다.
- 하지만 이것은 raw action label을 덮어쓰는 것이 아니라 `assist_policy`, `fixture_id`, `assist_ratio`로 따로 기록해야 한다.
- MVP-1에서는 “assist 없음 raw dataset”과 “assist 있음 curated dataset”을 분리해야 한다.

Source:

- “Handheld Micromanipulation with Vision-Based Virtual Fixtures”, PMC: https://pmc.ncbi.nlm.nih.gov/articles/PMC3531243/

### 6.3 VR shared-control interface

VR-based shared-control manipulation 연구는 operator가 task-space waypoint를 선택하고 robot feasibility를 UI로 feedback하는 방식을 제안한다.

RDF implication:

- HMD panel에 `RECENTER`, `TRACKING_OK`, `SPIKE_HOLD`, `RECORDING_ON`, `TRAINING_ELIGIBLE_SO_FAR`를 보여주는 방향은 맞다.
- operator가 terminal 로그가 아니라 HMD에서 현재 red flag를 봐야 한다.

Source:

- Xu, Moore, Cosgun, “Shared-Control Robotic Manipulation in Virtual Reality”: https://arxiv.org/abs/2205.10564

---

## 7. Robot learning teleoperation 시스템 논문

### 7.1 RoboTurk

RoboTurk는 consumer-grade VR headset과 hand tracking hardware로 robot을 자연스럽게 teleoperate하고, imitation learning을 위한 pixel-to-action demonstrations를 수집했다.

RDF implication:

- “VR teleop → dataset → policy” 방향은 검증된 연구 흐름이다.
- RDF는 단순 수집보다 replay/action/curation manifest를 더 강하게 가져가야 차별화된다.

Source:

- Zhang et al., “Deep Imitation Learning for Complex Manipulation Tasks from Virtual Reality Teleoperation”: https://arxiv.org/abs/1710.04615

### 7.2 DexPilot

DexPilot은 bare human hand 관찰만으로 23 DoF hand-arm system을 teleoperate하고, state-action data를 수집하는 low-cost vision-based teleoperation system이다.

RDF implication:

- glove 없이 hand pose를 robot action으로 바꾸는 접근은 가능하다.
- 그러나 high-DoF retargeting은 RDF MVP peg-in-hole에는 과하다. 현재는 wrist translation 안정화가 우선이다.

Source:

- Handa et al., “DexPilot: Vision Based Teleoperation of Dexterous Robotic Hand-Arm System”: https://arxiv.org/abs/1910.03135

### 7.3 Holo-Dex

Holo-Dex는 commodity VR headset의 hand pose estimator로 dexterous robot을 teleoperate하고 demonstrations를 수집한다.

RDF implication:

- Quest/VR hand pose를 first-class teleop input으로 쓰는 방향은 타당하다.
- 단, Holo-Dex류 시스템처럼 data collection과 learning을 주장하려면 input quality gate가 필요하다.

Source:

- Arunachalam et al., “Holo-Dex: Teaching Dexterity with Immersive Mixed Reality”: https://arxiv.org/abs/2210.06463

### 7.4 OPEN TEACH

OPEN TEACH는 Meta Quest 3 기반 teleoperation system으로, multiple robot morphologies와 data collection을 지원한다. abstract 기준 Quest 3 app, real-time robot control, 90Hz visual feedback, data compatibility with policy learning을 강조한다.

RDF implication:

- `Quest app / teleop server / robot adapter / data collection` 분리는 RDF에도 맞다.
- RDF의 최종 제품도 웹/앱 배포가 필요하지만, MVP에서는 Isaac Lab primary path를 web mock으로 대체하면 안 된다.

Source:

- OPEN TEACH paper: https://arxiv.org/abs/2403.07870
- Existing RDF note: `2024_open_teach.md`

### 7.5 Open-TeleVision

Open-TeleVision은 immersive active visual feedback으로 operator가 robot surroundings를 stereoscopic하게 보고, arm/hand movement를 robot에 mirror하여 imitation learning data를 수집한다.

RDF implication:

- operator visual feedback은 input accuracy의 일부다. 손 입력만 좋아도 operator가 target mapping을 못 보면 데이터 품질은 낮아진다.
- RDF HMD panel과 replay viewer는 “예쁜 UI”가 아니라 data quality 장치다.

Source:

- Open-TeleVision paper: https://arxiv.org/abs/2407.01512
- Existing RDF note: `2024_open_television.md`

### 7.6 Industrial VR teleoperation filtering

Industrial robot manipulator를 VR interface로 teleoperate한 연구는 industrial platform에서 standard VR control이 어렵고, command signal filtering이 필요하다고 보고한다.

RDF implication:

- Franka/Isaac task에서도 command filter와 bounded servo는 정당하다.
- 단, filter는 raw evidence를 삭제하지 말고 `applied_action`, `learning_action`, `raw_xr`, `control_filter` provenance로 분리해야 한다.

Source:

- Rosen and Jha, “A Virtual Reality Teleoperation Interface for Industrial Robot Manipulators”: https://arxiv.org/abs/2305.10960

---

## 8. RDF용 결론: red flag 조절 원칙

### 8.1 지금 red flag를 풀면 안 되는 것

현재 `raw_wrist_jump_reject_m=0.15`를 더 크게 키워서 0.9m jump를 받아들이면 안 된다.

이유:

- 사람이 손목을 1 frame 간격으로 90cm 이동한 것이 아니라 tracking artifact일 가능성이 높다.
- 그 값을 smoothing해서 control에 쓰면 action label이 오염된다.
- raw는 저장할 수 있지만, training candidate로는 막아야 한다.

### 8.2 권장 gate 정책

| 상황 | live robot control | raw 저장 | training eligibility |
|---|---|---|---|
| `position_valid=false` 또는 `isTracked=false` | hold | 저장 | 불가 |
| anchor fallback pose | hold | 저장 | 불가 |
| valid-to-valid jump `>0.10m` | warning/hold | 저장 | 불가 또는 review |
| valid-to-valid jump `>0.15m` | hard hold + reacquire | 저장 | 불가 |
| stable reacquire `N` frames | current EEF 기준 rebase | 저장 | 이후 frame만 후보 |
| cm급 jitter | One Euro / low-pass | raw+filtered 저장 | 가능 |
| precision 부족 | motion scaling / fixture | assist metadata 저장 | 별도 split |

### 8.3 추천 threshold 방향

현재 debugging threshold 자체는 나쁘지 않다.

```text
warn:   0.10 m
reject: 0.15 m
stable reacquire: 0.03 m
valid frames: 3
```

하지만 Gate A 학습 후보 기준은 더 엄격해야 한다.

```text
preflight_stable_valid_duration: 1.0~2.0 sec
preflight_max_valid_to_valid_jump: <= 0.05~0.10 m
episode_tracking_loss_rate: <= 0.05
episode_valid_to_valid_jump_gt_10cm_count: 0
held_ratio: low enough for continuous task phases
```

정리하면:

- **debug run**: warn/reject를 관찰하며 raw 저장 가능.
- **collection run**: HMD panel에서 `TRACKING_OK`가 충분히 안정되기 전 recording 금지.
- **training candidate**: valid-to-valid 10cm 초과 jump가 있으면 기본 reject.

---

## 9. Wi-Fi/ALVR 원인 여부 판단법

Wi-Fi일 수 있는 증상:

- ALVR latency graph에서 network latency spike.
- stream freeze / video glitch.
- controller/head pose가 동시에 lag/freeze.
- RDF frame interval jitter 증가.
- `input_latency_ms` 증가.

Wi-Fi만으로 설명하기 어려운 증상:

- OpenXR hand joint가 invalid인데 pose 숫자가 anchor fallback처럼 남는다.
- valid-to-valid wrist position이 0.9m jump한다.
- hand proximity/rotation/occlusion과 함께 tracking이 깨진다.

필요한 추가 계측:

```text
metadata.raw_xr.sample_time_ns
metadata.raw_xr.location_flags
metadata.raw_xr.position_valid
metadata.raw_xr.position_tracked
metadata.raw_xr.joint_source
metadata.raw_xr.openxr_predicted_display_time
metadata.runtime.alvr_network_latency_ms
metadata.runtime.alvr_packet_loss
metadata.runtime.steamvr_frame_timing
metadata.control.input_to_action_latency_ms
```

판단 규칙:

```text
ALVR network spike + RDF input latency spike + pose freeze
  => Wi-Fi/streaming 원인 가능성 높음

OpenXR invalid/tracked false + anchor fallback + hand occlusion/rotation
  => optical handtracking 원인 가능성 높음

flags valid인데 물리적으로 불가능한 jump 반복
  => runtime/provider pose artifact 또는 coordinate-frame/reacquire bug 의심
```

---

## 10. MVP-safe 실행 제안

### P0: Gate A 재개 전 필수

1. Recording preflight 강화
   - `TRACKING_OK`가 1~2초 지속되기 전 저장 금지.
   - HMD panel에 “손 추적 안정 전에는 recording 아님” 표시.
2. OpenXR/Unity validity provenance 추가
   - 가능하면 `locationFlags` 또는 equivalent `trackingState` 저장.
3. Raw wrist outlier gate 강화
   - valid-to-valid jump, velocity, acceleration 기록.
   - reject spike는 즉시 hold, stable reacquire 후 rebase.
4. Training eligibility gate 추가
   - `valid_to_valid_jump_gt_10cm_count > 0`이면 기본 reject.

### P1: 안정화 후 A/B

1. One Euro Filter A/B
   - `min_cutoff`, `beta`, `d_cutoff` metadata 저장.
2. Multi-joint robust wrist point
   - wrist 단독 vs `wrist+palm+index_mcp+pinky_mcp` robust centroid 비교.
3. Motion scaling A/B
   - `position_gain=0.10/0.15/0.18` 비교.
   - accepted trajectory rate와 task progress 비교.

### P2: task-level assist

1. Insertion-axis virtual fixture
2. Approach cone / lateral clamp
3. Assisted dataset split

주의:

- assist는 MVP-safe일 수 있지만, `raw_action_label`을 덮어쓰면 안 된다.
- `assist_policy`, `assist_strength`, `fixture_geometry`, `raw_operator_motion`, `assisted_control`을 분리해야 한다.

---

## 11. RDF 최종 제품 목표와의 연결

최종적으로 RDF는 HMD 사용자에게 배포 가능한 app/web/launcher가 필요하다. 그러나 “많이 배포”보다 먼저 필요한 것은 **입력 품질을 자동으로 판별하고, 나쁜 run을 학습 데이터에서 제외하는 데이터 공장 gate**다.

최종 제품 구조:

```text
HMD Operator App
  - task instruction
  - tracking quality panel
  - recenter / recording / red flag 표시

PC Collector Launcher
  - ALVR/SteamVR/OpenXR/Isaac launch
  - network/runtime preflight
  - local recorder

RDF Backend
  - trajectory ingest
  - ForgeEval
  - ForgeCurate
  - export

Web Dashboard
  - progress/KPI
  - episode replay
  - accepted/rejected reason
  - dataset card
```

이번 리서치의 핵심은 HMD app이 단순 조작 UI가 아니라 **quality-gated data collection instrument**가 되어야 한다는 점이다.

---

## 12. 최종 추천

현재 red flag 조절의 정답은 “threshold를 풀기”가 아니라 다음이다.

```text
1. debug mode와 collection mode를 분리한다.
2. collection mode에서는 preflight를 길게 잡는다.
3. valid flag와 timestamp를 저장한다.
4. 10cm 이상 valid-to-valid jump는 training gate에서 막는다.
5. 15cm 이상 jump는 live control에서도 hold/reacquire한다.
6. spike 제거 후에 One Euro Filter를 적용한다.
7. 그래도 precision이 부족하면 motion scaling과 virtual fixture를 assist metadata로 추가한다.
```

Gate A를 다시 시작하기 위한 최소 조건:

```text
tracking_loss_rate <= 0.05
right_hand_tracked_rate >= 0.95
xr_frame_valid_rate >= 0.95
valid_to_valid_jump_gt_10cm_count == 0
raw_wrist_spike_reacquire_pending_count == 0 or explainable
H14 PASS
H15 PASS
episode training_eligible candidate evidence present
```
