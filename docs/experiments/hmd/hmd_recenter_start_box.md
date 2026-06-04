# HMD Robot-Space Recenter Start Box

이 문서는 Quest/OpenXR live collection에서 사용하는 recenter 계약을 고정한다. 현재 기본 UX는 operator의 첫 안정 손 위치를 시작점으로 삼지 않는다. Episode/reset마다 simulation 안에 start box를 만들고, robot EEF/fingertip이 그 box 안에 들어간 상태에서 handtracking이 안정될 때만 recenter를 완료한다.

## 목적

기존 `auto_first_valid_tracking` 방식은 operator 손이 처음 안정적으로 잡힌 위치에 workspace origin을 맞췄다. 그래서 매 episode마다 시작점이 달라지고, 사용자가 같은 task를 수행해도 trajectory 품질이 흔들렸다.

현재 방식은 시작 기준을 사람 몸/손 위치가 아니라 robot-space target으로 옮긴다.

```text
episode/reset
-> hole_target 계산
-> episode당 bounded random offset 1회 샘플링
-> start_box_center = hole_target + approach_offset + random_offset
-> /World/RDFRecenterStartBox wireframe 표시
-> setup-only control로 robot을 start box 안으로 이동
-> valid hand + robot inside box 상태를 N frame 유지
-> 현재 손 pose를 neutral pose로 calibrate
-> recording/warmup 시작
```

## Runtime Contract

권장 기본값:

```bash
RDF_RECENTER_MODE=robot_start_box
RDF_RECENTER_BOX_CENTER_SOURCE=hole_target_approach
RDF_RECENTER_BOX_APPROACH_OFFSET=0,0,0.08
RDF_RECENTER_BOX_RANDOM_OFFSET=0.02,0.02,0.01
RDF_RECENTER_BOX_HALF_EXTENTS=0.04,0.04,0.04
RDF_RECENTER_BOX_VISUAL=0
RDF_BLOCK_TELEOP_UNTIL_RECENTER=1
RDF_RECENTER_SETUP_CONTROL=1
```

Semantics:

- `RDF_RECENTER_MODE=robot_start_box`: HMD collection의 primary recenter mode다.
- `RDF_RECENTER_BOX_CENTER_SOURCE=hole_target_approach`: box center를 reset pose가 아니라 hole target approach point로 잡는다.
- `RDF_RECENTER_BOX_APPROACH_OFFSET`: hole target에서 접근 시작점을 얼마나 띄울지 정한다.
- `RDF_RECENTER_BOX_RANDOM_OFFSET`: episode/reset마다 한 번만 uniform random offset을 샘플링한다.
- `RDF_RECENTER_BOX_HALF_EXTENTS`: start box half-size다.
- `RDF_RECENTER_BOX_VISUAL=0`: 기본값. AR/HMD wireframe box를 숨긴다. 필요할 때만 `1`로 켠다.
- `RDF_BLOCK_TELEOP_UNTIL_RECENTER=1`: recenter 전 data-collection teleop를 막는다.
- `RDF_RECENTER_SETUP_CONTROL=1`: recenter 전에도 setup-only control로 robot을 box 안에 넣을 수 있게 한다. 이 구간은 recording/warmup frame으로 저장하지 않는다.

`RDF_RECENTER_BOX_CENTER=x,y,z`를 명시하면 center source보다 우선한다. 단, 기본 수집 루프에서는 직접 center override를 쓰지 않는다.

## HMD Visuals

USD prim:

```text
/World/RDFRecenterStartBox
```

Color contract:

```text
orange = valid hand 또는 robot-inside-box 조건이 아직 불충분
blue   = valid hand + robot inside box, hold 진행 가능
green  = recenter 완료
```

HMD guidance text:

```text
RECENTER: SHOW RIGHT HAND
RECENTER: MOVE TO START BOX
RECENTER: HOLD START n/N
RECENTER: OK
```

## Expected Logs

정상 시작 시:

```text
[RDF] Robot start recenter box reset: center_source=hole_target_approach center=[...] random_offset=[...] random_half_range=[...]
[RDF][RECENTER] mode=robot_start_box ... inside=True valid_hand=True ready=True ...
[RDF] Auto recenter applied after robot start-box hold ...
[RDF] Calibration/recenter requested: reason=auto_robot_start_box
[RDF] Recording frames started after dropping ... warm-up frames
```

`Recording frames started`가 recenter 완료보다 먼저 나오면 잘못된 상태다.

## Operator Workflow

1. Quest 3에서 ALVR/SteamVR 연결과 handtracking을 확인한다.
2. Isaac/AR session이 열리면 HMD 안에서 start box가 보이는지 확인한다.
3. 손을 HMD camera 시야 안에 둔다.
4. Robot을 setup-only control로 start box 안에 넣는다.
5. Box가 blue 상태로 바뀌면 움직이지 말고 hold한다.
6. Box가 green 또는 `RECENTER: OK`가 되면 실제 task를 시작한다.

Primary HMD collection에서는 terminal `P` recenter에 의존하지 않는다. `P`는 fallback/debug command다.

## Failure Interpretation

```text
start box가 보이지 않음:
  wireframe이 필요하면 RDF_RECENTER_BOX_VISUAL=1 적용 여부와 patch 적용 상태를 확인한다.

시작하자마자 바로 recenter됨:
  RDF_RECENTER_BOX_CENTER_SOURCE가 initial_robot_pose로 돌아갔거나 box가 reset pose를 포함하고 있을 가능성이 높다.
  기본값은 hole_target_approach여야 한다.

robot이 box 안으로 들어가도 recenter가 안 됨:
  right hand tracking validity, RDF_AUTO_RECENTER_VALID_FRAMES, box half extents를 확인한다.

recenter 전부터 recording frame이 저장됨:
  RDF_BLOCK_TELEOP_UNTIL_RECENTER=1, RDF_RECENTER_SETUP_CONTROL=1 계약이 깨진 것이다.

episode마다 box 위치가 조금씩 다름:
  정상이다. RDF_RECENTER_BOX_RANDOM_OFFSET이 reset마다 한 번만 샘플링된다.
```

## Current Collection Command

```bash
cd ~/robot-data-forge

RDF_ISAAC_TASK=Isaac-Forge-PegInsert-Direct-v0 \
  RDF_TASK_TYPE=peg_in_hole \
  RDF_MAX_FRAMES=600 \
  RDF_WARMUP_VALID_FRAMES=10 \
  RDF_ACTION_POS_AXIS_MAP=x,z,y \
  RDF_TELEOP_CONTROL_MODE=bounded_direct_ee_target \
  RDF_AUTO_SUCCESS_FINALIZE=1 \
  RDF_AUTO_FINALIZE_REQUIRE_LIVE_CURATION=1 \
  RDF_LIVE_CURATION_MAX_SEAT_ACTION_SATURATION_RATIO=0.30 \
  RDF_LIVE_CURATION_ON_FAIL=reset \
  RDF_RECENTER_MODE=robot_start_box \
  RDF_RECENTER_BOX_CENTER_SOURCE=hole_target_approach \
  RDF_RECENTER_BOX_APPROACH_OFFSET=0,0,0.08 \
  RDF_RECENTER_BOX_RANDOM_OFFSET=0.02,0.02,0.01 \
  RDF_RECENTER_BOX_VISUAL=0 \
  RDF_BLOCK_TELEOP_UNTIL_RECENTER=1 \
  RDF_RECENTER_SETUP_CONTROL=1 \
  RDF_EXIT_AFTER_FINALIZE=1 \
  GATE_A_TARGET=10 \
  ./scripts/run_collection_loop.sh
```

`RDF_ACTION_POS_AXIS_MAP=x,z,y` is intentional: Quest/OpenXR handtracking is
Y-up while the Isaac robot workspace is Z-up, so lowering the hand must map to
lowering robot `z`.
