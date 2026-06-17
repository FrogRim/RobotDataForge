# MVP-2E v0.6a Runtime Capture-radius Preflight Design

Date: 2026-06-11

## 목적

`v0_6` implementation slice는 의도대로 fail-closed했다.

```text
chamfer_preflight.preflight_branch=Branch C
inspection_method=static_config_only_geometry_uninspectable
repair_probe_allowed=false
train_generation_gate_allowed=false
```

하지만 이 결과는 "Factory asset 자체를 접근할 수 없다"는 뜻이 아니다. 현재
preflight 구현이 local static USD/mesh inspection만 시도했기 때문에 멈춘 것이다.
직전 `v0_5` actual Isaac train-generation probe는
`Isaac-Factory-PegInsert-Direct-v0`를 로드하고 trace를 생성했다. 따라서 Isaac
runtime은 cloud/Nucleus asset을 resolve할 수 있다.

`v0_6a`의 목적은 `v0_6`의 Branch C를 runtime 기반 capture-radius preflight로
해소할 수 있는지 확인하는 것이다.

이 slice의 목표는 MVP-2 Closed가 아니다.

```text
goal:
  resolve chamfer_preflight Branch C -> Branch A or Branch B, if justified
  then allow repair probe to run

not goal:
  prove policy uplift
  run held-out A/B
  claim MVP-2 Closed
```

## 현재 문제 정의

`v0_6` preflight의 Branch C reason:

```text
static_config_only_geometry_uninspectable
```

이는 다음을 의미한다.

```text
known:
  IsaacLab task config exposes peg/hole USD paths and diameters
  local static mesh geometry was not inspectable through the current code path

not proven:
  cloud/Nucleus USD asset is unavailable
  chamfer/lead-in is absent
  capture radius cannot be measured
```

따라서 다음 valid step은 static-local inspection을 반복하는 것이 아니라, Isaac
runtime이 이미 resolve하는 asset을 이용해 capture radius를 측정하는 것이다.

## 비목표

`v0_6a`는 다음을 하지 않는다.

- held-out `21000-21049`를 열지 않는다.
- train gate seed `19000-19159`를 사용하지 않는다.
- calibration seed `20000-20029`를 사용하지 않는다.
- repair probe seed `16023`, `16042`, `16096`을 capture-radius tuning에 사용하지
  않는다.
- success metric, env-native stable window, seed range, policy/trainer,
  selected action adapter를 바꾸지 않는다.
- capture-radius probe 결과로 policy uplift를 주장하지 않는다.
- capture-radius probe rollout을 training material, accepted dataset, curation
  evidence로 사용하지 않는다.
- force-reactive control, retry/recover, withdraw/reinsert, search pattern을
  도입하지 않는다.
- asset geometry를 보고 success threshold를 완화하지 않는다.

## 결정

`v0_6a`는 **empirical capture-radius probe**를 primary Branch C 해소 수단으로
사용한다.

대안인 runtime USD stage inspection은 secondary fallback이다.

선택 이유:

- runtime Isaac env는 이미 Factory asset을 resolve한다.
- chamfer/lead-in의 실질적 의미는 "USD에 chamfer mesh가 보이는가"보다
  "어느 lateral offset까지 수직 삽입이 capture되는가"에 가깝다.
- empirical probe는 실제 physics/runtime 조건에서 capture 가능 반경을 직접
  측정한다.
- held-out, train gate, calibration, repair probe seed를 쓰지 않는다면
  p-hacking 경로가 아니다.

## Pre-registration Boundary

`capture_radius_probe`는 geometry-only preflight다.

```text
artifact:
  capture_radius_probe.json

scope:
  Factory peg/hole capture behavior measurement

authority:
  may resolve chamfer_preflight Branch C
  may derive INSERT parameter envelope

no authority:
  no train-generation pass
  no repair probe green light
  no 40-run gate pass
  no held-out access
  no MVP-2 Closed claim
```

Dedicated probe seed namespace:

```text
geometry_probe_seed_range=18500-18509
primary_geometry_probe_seed=18500
```

Rationale:

- disjoint from `v0_5` train `16000-16159`
- disjoint from `v0_5` held-out `18000-18019`
- disjoint from `v0_6` train `19000-19159`
- disjoint from `v0_6` calibration `20000-20029`
- disjoint from `v0_6` held-out `21000-21049`
- disjoint from repair probe seeds `16023`, `16042`, `16096`

The probe seed is for deterministic scene initialization only. It is not a
training, calibration, held-out, or repair-evidence seed.

## Empirical Capture-radius Probe Design

The empirical probe loads `Isaac-Factory-PegInsert-Direct-v0`, lets the runtime
resolve the Factory assets, and measures lateral capture behavior by controlled
offset sweeps.

Procedure:

```text
1. reset env with geometry_probe_seed=18500
2. read target hole pose from task-state / fixed asset state
3. place or command held peg above the hole with lateral offset delta
4. disable lateral/yaw correction for this measurement
5. apply bounded vertical push only
6. record env-native success mask per step
7. success(delta)=max_consecutive(env_native_success_mask) >= 10
8. sweep delta values in ascending order
9. capture_radius_m=max delta where success(delta)=true
```

The measurement must not use the `v0_6_active_state_controller` correction path.
Otherwise the probe would measure controller correction ability, not passive
capture radius.

Required offset sweep:

```text
delta_m = [
  0.0000,
  0.0001,
  0.0002,
  0.0004,
  0.0006,
  0.0008,
  0.0010,
  0.0015,
  0.0020,
  0.0030,
  0.0040,
  0.0060,
  0.0080,
]
```

Direction set:

```text
directions = [
  +x,
  -x,
  +y,
  -y,
]
```

The conservative capture radius is the minimum across directions:

```text
capture_radius_m = min(max_success_delta_by_direction)
```

This avoids over-claiming if the chamfer or contact behavior is asymmetric.

## Branch Resolution Rules

The runtime probe updates `chamfer_preflight` only through these rules.

Branch A:

```text
conditions:
  capture_radius_m is numeric
  capture_radius_m >= 0.0004
  at least two non-zero delta levels pass in every direction
  zero-offset control passes

meaning:
  capture behavior is measurable and non-trivial

result:
  preflight_branch=Branch A
  chamfer_present=true
  capture_radius_m=<numeric>
  inspection_method=runtime_empirical_capture_radius_probe
  repair_probe_allowed=true
  train_generation_gate_allowed=true only after repair probe green light
```

Branch B:

```text
conditions:
  zero-offset control passes
  capture_radius_m is numeric but < 0.0004
  OR direction asymmetry makes capture radius approximate
  OR only one non-zero delta level passes in any direction

meaning:
  some capture behavior exists, but the radius is approximate or weak

result:
  preflight_branch=Branch B
  chamfer_present=true
  capture_radius_m=<numeric or approximate>
  inspection_method=runtime_empirical_capture_radius_probe
  repair_probe_allowed=true
  train_generation_gate_allowed=true only after repair probe green light
  if repair probe shows align-then-jam, escalate back to Branch C/blocker
```

Branch C:

```text
conditions:
  runtime env cannot load
  env-native success mask unavailable
  zero-offset control cannot seat
  all non-zero delta levels fail
  probe cannot produce trustworthy trace/artifact

meaning:
  capture radius is unavailable or effectively absent

result:
  preflight_branch=Branch C
  repair_probe_allowed=false
  train_generation_gate_allowed=false
  heldout_schedule.scheduled=false
```

## Derived INSERT Parameter Envelope

The empirical preflight may derive only INSERT envelope parameters.

Allowed derived fields:

```text
derived_insert_params.capture_radius_m
derived_insert_params.align_lateral_gate_m
derived_insert_params.insert_lateral_guard_m
derived_insert_params.vertical_push_scale
derived_insert_params.correction_gain_limit
derived_insert_params.max_insert_steps
```

Initial derivation rules:

```text
align_lateral_gate_m = min(0.008, 0.5 * capture_radius_m)
insert_lateral_guard_m = min(0.008, capture_radius_m)
vertical_push_scale = conservative_fixed_value
correction_gain_limit = conservative_fixed_value
max_insert_steps = existing horizon-aware v0_6 limit
```

If `capture_radius_m` is smaller than the previously assumed alignment gate, the
INSERT envelope must become stricter. It must not relax the env-native success
authority.

The exact `vertical_push_scale` and `correction_gain_limit` values must be
pre-registered in the implementation plan before running repair probe. They may
not be chosen after observing repair probe results.

## Required Artifacts

`capture_radius_probe.json`:

```text
schema_version
scenario_profile=v0_6a
probe_type=runtime_empirical_capture_radius
isaac_task
geometry_probe_seed
asset_paths_from_task_config
runtime_asset_resolution_status
offset_sweep_m
directions
per_delta_direction_results
env_native_success_authority
stable_steps_required
capture_radius_m
branch_recommendation
non_claims
probe_sha256
```

Updated `chamfer_preflight.json`:

```text
preflight_branch
chamfer_present
capture_radius_m
inspection_method
source_asset_paths
runtime_resolution_evidence
derived_insert_params
derivation_rationale
repair_probe_allowed
train_generation_gate_allowed
heldout_allowed=false
chamfer_preflight_sha256
```

The probe must preserve the old static preflight result as prior evidence:

```text
prior_static_preflight_branch=Branch C
prior_static_inspection_method=static_config_only_geometry_uninspectable
```

## Runtime USD Stage Inspection Fallback

If empirical capture-radius probing cannot produce trustworthy output, runtime
USD stage inspection may be attempted as a secondary diagnostic.

It may read resolved prims or meshes from the Isaac runtime stage and report:

```text
runtime_stage_asset_paths
mesh_or_prim_presence
top_hole_edge_geometry
chamfer_or_lead_in_presence
estimated_capture_radius_m
inspection_confidence
```

Runtime USD stage inspection may resolve Branch A only if it produces a numeric
capture radius with clear geometry evidence. Otherwise it may only support Branch
B or keep Branch C.

## Integrity Guards

- Held-out `21000-21049` remains sealed.
- The probe may not read held-out trace paths, held-out metrics, or held-out
  scenario IDs beyond disjointness checks.
- Capture-radius output may not change env-native success authority.
- Capture-radius output may not change `stable_steps_required=10`.
- Capture-radius output may not change the fixed 40 train-gate seed list.
- Capture-radius output may not alter baseline/candidate policy/trainer
  selection.
- Capture-radius output may not be treated as training data.
- Branch A/B only permits the repair probe to run. It does not pass the repair
  probe or 40-run gate by itself.

## Test Requirements

Focused tests should prove:

```text
runtime capture-radius probe uses geometry-only seed namespace
runtime capture-radius probe excludes train/calibration/held-out/probe seeds
zero-offset failure keeps Branch C
numeric non-zero capture radius can produce Branch A
weak/asymmetric capture behavior produces Branch B
capture-radius probe artifact cannot mark train gate passed
updated chamfer_preflight preserves prior static Branch C evidence
heldout_schedule remains blocked until repair probe and 40-run gate pass
```

No test should require live Isaac unless explicitly marked runtime/integration.

## Execution Order

Implementation should proceed in this order:

```text
1. Add pure branch-resolution tests and artifact-shape tests.
2. Add capture-radius probe config and manifest fields.
3. Add runtime empirical capture-radius probe entrypoint.
4. Wire updated chamfer_preflight Branch A/B/C output.
5. Verify skip/static path still fail-closes.
6. Run runtime capture-radius probe.
7. If Branch A/B, run repair probe.
8. If repair probe green-lights, run fixed 40-run train gate.
9. Only after train gate >=20/40 and calibration freeze, open held-out A/B.
```

## Stop Conditions

Stop and report if:

```text
Factory env cannot load through Isaac runtime
env-native success mask cannot be observed
zero-offset vertical insertion fails under the empirical probe
runtime probe requires held-out seed access
runtime probe requires success metric changes
runtime probe requires force/retry/search controller behavior
capture-radius result would require weakening v0_6 integrity guards
```

## Self-review

- Placeholder scan: no unresolved placeholder markers remain.
- Scope check: this spec covers only Branch C resolution through runtime
  capture-radius preflight.
- Integrity check: held-out, train gate, calibration, repair probe, policy, and
  success authority boundaries remain unchanged.
- Ambiguity check: Branch A/B/C rules and artifact authority are explicit.
