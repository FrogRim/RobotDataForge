# G005 MVP-3B claimed variant fix report

## Status

Implemented and verified.

## Scope

Closed the MVP-3B verifier gap where truthy `*_claimed` variants for existing
forbidden support, production, readiness, performance, and learning claims could be
added to indexed JSON after hash refresh.

## Changed behavior

- Extended the canonical MVP-3B forbidden-claim schema in verifier, producer, tests,
  generated package data, and canonical spec/plan docs.
- Added real-package tamper coverage that copies the committed MVP-3B package,
  injects these missing claimed variants into indexed JSON, refreshes
  `data/artifact_index.json` and `package_manifest.json`, and asserts only
  `forbidden_claims` fails:
  - `live_ros2_dds_runtime_support_claimed`
  - `live_ur_runtime_support_claimed`
  - `franka_hardware_support_claimed`
  - `production_certification_claimed`
  - `learning_proven_value_claimed`
- Added obvious paired variants for existing MVP-3B non-claim schema keys:
  - `deployable_policy_readiness_claimed`
  - `visual_policy_performance_claimed`
  - `hmd_openxr_collection_readiness_claimed`
- Regenerated `docs/proof/mvp3b_source_adapter_matrix_proof_package/` from
  `scripts/run_mvp3b_source_adapter_infrastructure.py --clean` so package indexes
  and manifest hashes are consistent with the new non-claim schema.

## Red/green evidence

```text
RED:
uv run pytest apps/api/tests/test_verify_mvp3b_source_adapter_package.py -q
result=failed
key failure=new real-package claimed-variant tamper test still verified before verifier update

GREEN:
uv run pytest apps/api/tests/test_verify_mvp3b_source_adapter_package.py -q
result=37 passed in 1.02s
```

## Constraints

- No frozen MVP-2 assets modified.
- No MVP-3A proof package artifacts modified.
- Verifier remains stdlib-only and independent from producer services.
- No live robot, support, production, marketplace, or learning-proven claim was introduced.

## Final verification

```text
uv run pytest apps/api/tests/test_verify_mvp3b_source_adapter_package.py -q
result=37 passed in 1.03s

uv run pytest apps/api/tests/test_mvp3b_source_adapter_infrastructure.py -q
result=9 passed in 0.15s

python3 scripts/verify_mvp3b_source_adapter_package.py docs/proof/mvp3b_source_adapter_matrix_proof_package/package_manifest.json
result=VERDICT: VERIFIED, 16 checks passed

uv run mypy scripts/run_mvp3b_source_adapter_infrastructure.py scripts/verify_mvp3b_source_adapter_package.py apps/api/tests/test_mvp3b_source_adapter_infrastructure.py apps/api/tests/test_verify_mvp3b_source_adapter_package.py
result=Success: no issues found in 4 source files

uvx ruff check scripts/run_mvp3b_source_adapter_infrastructure.py scripts/verify_mvp3b_source_adapter_package.py apps/api/tests/test_mvp3b_source_adapter_infrastructure.py apps/api/tests/test_verify_mvp3b_source_adapter_package.py apps/api/app/services/robot_embodiment_adapters.py
result=All checks passed

python3 -m py_compile scripts/run_mvp3b_source_adapter_infrastructure.py scripts/verify_mvp3b_source_adapter_package.py
result=passed

git diff --check
result=passed

git diff -- scripts/run_mvp2c_isaac_training_calibration.py scripts/run_mvp2b_isaac_proof_evaluator.py scripts/verify_mvp2_package.py docs/proof/mvp2_learning_proven_evidence_package
result=no output
```
