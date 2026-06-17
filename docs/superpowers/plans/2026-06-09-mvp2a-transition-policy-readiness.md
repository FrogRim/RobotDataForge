# MVP-2A Transition / Policy Readiness Plan

## Goal

Before trying to close MVP-2, make the current UR MVP-2 harness report whether
its curated candidate train set is ready for proof-grade held-out policy A/B.

MVP-2 Closed still requires positive curated > uncurated held-out policy uplift.
This plan does not claim uplift.

## Scope

Add an MVP-2A readiness layer to the existing UR policy A/B harness:

```text
UR file-backed recorded-log candidate train HDF5
-> view curation manifest
-> view split manifest
-> run_mvp2_learning_sanity
-> mvp2a transition/policy readiness report
```

The readiness report must show:

- transition-rich train data readiness
- train-set overfit sanity
- next blocker before proof-grade external held-out rollout evaluation
- unchanged claim boundary: no policy uplift, no physical UR readiness, no HMD readiness

## Non-Goals

- Do not implement live UR/RTDE runtime.
- Do not implement physical robot control.
- Do not claim policy uplift.
- Do not weaken MVP-2 external proof rules.
- Do not turn schema-only rollout fixtures into proof evidence.
- Do not close MVP-2 unless positive held-out uplift evidence exists.

## Implementation Steps

1. Extend MVP-2 learning sanity phase extraction to read command-state
   metadata such as `command_state_row.task_phase`.
2. Add UR harness view manifests for the candidate train view:
   `candidate_curated/curation_manifest.json` and
   `candidate_curated/split_manifest.json`.
3. Run `run_mvp2_learning_sanity` from the UR harness against
   `candidate_curated_train.hdf5`.
4. Write `mvp2a_transition_policy_readiness_report.json` and include the same
   readiness summary in `mvp2_policy_ab_harness_report.json`.
5. Keep `harness_ready` scoped to the existing harness gates, while
   `mvp2a_policy_ab_ready` remains false until transition-rich and stronger
   trainer/policy prerequisites pass.

## Test Plan

Add focused tests before implementation:

- `command_state_row.task_phase` is recognized as a phase source.
- UR harness writes candidate curation/split manifests.
- UR harness writes MVP-2A readiness report.
- Current UR candidate train set is blocked on transition coverage and does not
  claim learning-proven value.

Verification commands:

```text
uv run pytest apps/api/tests/test_mvp2_learning_sanity_script.py apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py -q
uv run pytest apps/api/tests/test_mvp2_learning_proven_policy_eval_script.py apps/api/tests/test_mvp1_proof_audit_script.py apps/api/tests/test_mvp1c_real_policy_eval_script.py -q
uv run python scripts/run_mvp2_ur_policy_ab_harness.py --clean --refresh-mvp1plus --pretty
uv run python -m compileall -q scripts apps/api/app apps/api/tests
uvx ruff check scripts/run_mvp2_learning_sanity.py scripts/run_mvp2_ur_policy_ab_harness.py apps/api/tests/test_mvp2_learning_sanity_script.py apps/api/tests/test_mvp2_ur_policy_ab_harness_script.py
git diff --check
```
