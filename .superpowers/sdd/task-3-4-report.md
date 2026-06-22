# MVP-3B Tasks 3-4 Report

## Status

DONE

## Scope

Implemented Task 3 RED tests and Task 4 runner/package builder for the MVP-3B source-adapter matrix proof package.

## Commits

- Implementation commit: 90193f1
- Report commit: created after this report file is written; final response records the id.

## Changed Files

```text
apps/api/tests/test_mvp3b_source_adapter_infrastructure.py
scripts/run_mvp3b_source_adapter_infrastructure.py
docs/proof/mvp3b_source_adapter_matrix_proof_package/
docs/developer/worklog.md
Handoff.md
tasks/todo.md
.superpowers/sdd/task-3-4-report.md
```

## RED Evidence

```bash
uv run pytest apps/api/tests/test_mvp3b_source_adapter_infrastructure.py -q
# RED before runner implementation: 8 failed in 0.09s
# Expected failure: FileNotFoundError for scripts/run_mvp3b_source_adapter_infrastructure.py
```

## GREEN Evidence

```bash
uv run pytest apps/api/tests/test_mvp3b_source_adapter_infrastructure.py -q
# 8 passed in 0.13s

uv run pytest apps/api/tests/test_verify_mvp3b_source_adapter_package.py -q
# 20 passed in 0.42s

uv run python scripts/run_mvp3b_source_adapter_infrastructure.py --clean
# source_adapter_infrastructure_closed

python3 scripts/verify_mvp3b_source_adapter_package.py docs/proof/mvp3b_source_adapter_matrix_proof_package/package_manifest.json
# VERDICT: VERIFIED
# PASS: hash_integrity
# PASS: data_coverage
# PASS: adapter_set_exactness
# PASS: source_log_completeness
# PASS: metadata_profile_consistency
# PASS: source_projection_hash_binding
# PASS: accepted_rejected_counts
# PASS: contract_source_fields
# PASS: contract_action_roles
# PASS: frame_action_role_coverage
# PASS: non_claims_false
# PASS: forbidden_claims
# PASS: spent_no_reuse_exact
# PASS: opened_ranges_empty
# PASS: learning_proven_addendum_absent
# PASS: summary_cache_consistency

uvx ruff check scripts/run_mvp3b_source_adapter_infrastructure.py apps/api/tests/test_mvp3b_source_adapter_infrastructure.py scripts/verify_mvp3b_source_adapter_package.py apps/api/tests/test_verify_mvp3b_source_adapter_package.py
# All checks passed

python3 -m py_compile scripts/run_mvp3b_source_adapter_infrastructure.py apps/api/tests/test_mvp3b_source_adapter_infrastructure.py
# passed

git diff --check
# passed before report commit preparation
```

## Self-Review

- Runner uses `RobotEmbodimentAdapterRegistry.create(...)` for all three required adapters and calls `project_source_evidence(...)` plus `emit_contract(...)`.
- Package contains source logs, projections, contracts, adapter_results, config, non_claims_attestation, adapter_registry_snapshot, artifact_index, source_adapter_matrix_summary, README, and package_manifest.
- `package_manifest.json` includes all `data/` files with file-byte sha256 and byte_size entries.
- `data/artifact_index.json` indexes verdict-critical `data/` files excluding itself, matching the independent verifier contract.
- Contract smoke stays explicitly non-learning-proven: `learning_results_measured=false`, `policy_uplift=false`, `learning_proven_value=false`.
- `spent_no_reuse` remains exactly `[[40000, 40049], [42000, 42049]]` and no calibration/heldout/tuning/closure range is opened.
- Runner does not import or call `scripts/verify_mvp3b_source_adapter_package.py`.
- Runner does not open Isaac or any live robot runtime.
- `--clean` refuses unsafe repo/docs/proof paths and allows only the managed default package path or safe tmp outputs.
- Frozen MVP-2 assets and MVP-3A package artifacts were not modified.

## Concerns

- The generated `.hdf5` files in `data/generated_contract_smoke/` are contract-smoke placeholders, not trainer exports. This is intentional for MVP-3B and is called out in config, summary, adapter results, trainer smoke JSON, and README.
- No external source directories were supplied in this task; the package uses repo-local generated/file-backed fixture source logs as required.

## Review Blocker Fix - Non-Learning-Proven Package Surface Binding

Status: DONE

Reviewer blocker fixed:

```text
The verifier previously enforced non-learning-proven contract-smoke fields only
under data/config.json:contract_smoke. A hash-refreshed package could set
learning_results_measured=true in generated_contract_smoke trainer smoke JSON, or
set policy_uplift / learning_proven_value on other package JSON surfaces, while
hash_integrity still passed.
```

Fix:

```text
- Added RED tests that semantically tamper indexed JSON files, refresh
  package_manifest.json and data/artifact_index.json hashes, then assert only
  non_claims_false fails.
- Covered generated_contract_smoke trainer smoke, adapter_results,
  source_adapter_matrix_summary, and normalized trajectory contract
  learning_eligibility_gates.
- Hardened scripts/verify_mvp3b_source_adapter_package.py so every package
  JSON/JSONL surface enforces:
  learning_results_measured == false
  policy_uplift == false
  learning_proven_value == false
  contract_smoke_only == true
  trainer_export_smoke == "contract_smoke_only"
- Preserved the existing data/config.json:contract_smoke.trainer_export_smoke=true
  exception.
```

Verification:

```bash
uv run pytest apps/api/tests/test_verify_mvp3b_source_adapter_package.py -q
# RED before verifier fix: 4 failed, 20 passed in 0.52s
# GREEN after verifier fix: 24 passed in 0.60s

uv run pytest apps/api/tests/test_mvp3b_source_adapter_infrastructure.py -q
# 8 passed in 0.12s

uv run python scripts/run_mvp3b_source_adapter_infrastructure.py --clean
# source_adapter_infrastructure_closed

python3 scripts/verify_mvp3b_source_adapter_package.py docs/proof/mvp3b_source_adapter_matrix_proof_package/package_manifest.json
# VERDICT: VERIFIED
# 16 verifier checks passed

uvx ruff check scripts/run_mvp3b_source_adapter_infrastructure.py apps/api/tests/test_mvp3b_source_adapter_infrastructure.py scripts/verify_mvp3b_source_adapter_package.py apps/api/tests/test_verify_mvp3b_source_adapter_package.py
# All checks passed

python3 -m py_compile scripts/run_mvp3b_source_adapter_infrastructure.py apps/api/tests/test_mvp3b_source_adapter_infrastructure.py scripts/verify_mvp3b_source_adapter_package.py
# passed
```

Notes:

```text
- Runner output did not require structural changes.
- The default generated package remains VERIFIED under the hardened verifier.
- Frozen MVP-2 assets and MVP-3A proof package artifacts were not modified.
```

## Review Blocker Fix - Modified-File Typing Cleanup

Status: DONE

Reviewer blocker fixed:

```text
The scoped mypy command failed on modified-file-related annotations:
1. verifier JSON/JSONL payload branch assignment narrowed payload to dict only.
2. runner contract-smoke artifact map returned dict[str, Path] while emit_contract
   accepts dict[str, Path | str] | None.
3. registry profile builder_class was typed as the base builder constructor even
   though concrete builder classes are no-argument factories.
```

Fix:

```text
- Added RobotEmbodimentContractBuilderFactory Protocol for no-argument builder factories.
- Updated RobotEmbodimentAdapterRegistryProfile.builder_class and _profile() to use
  that factory Protocol.
- Widened _write_contract_smoke() return type to dict[str, Path | str].
- Annotated verifier package-surface payload variables as dict/list union before
  JSON vs JSONL branch assignment.
```

Verification:

```bash
uv run mypy scripts/run_mvp3b_source_adapter_infrastructure.py scripts/verify_mvp3b_source_adapter_package.py apps/api/tests/test_mvp3b_source_adapter_infrastructure.py apps/api/tests/test_verify_mvp3b_source_adapter_package.py
# Success: no issues found in 4 source files

uv run pytest apps/api/tests/test_mvp3b_source_adapter_infrastructure.py -q
# 8 passed in 0.13s

uv run pytest apps/api/tests/test_verify_mvp3b_source_adapter_package.py -q
# 24 passed in 0.62s

python3 scripts/verify_mvp3b_source_adapter_package.py docs/proof/mvp3b_source_adapter_matrix_proof_package/package_manifest.json
# VERDICT: VERIFIED
# 16 verifier checks passed

uvx ruff check apps/api/app/services/robot_embodiment_adapters.py scripts/run_mvp3b_source_adapter_infrastructure.py scripts/verify_mvp3b_source_adapter_package.py apps/api/tests/test_mvp3b_source_adapter_infrastructure.py apps/api/tests/test_verify_mvp3b_source_adapter_package.py
# All checks passed

python3 -m py_compile apps/api/app/services/robot_embodiment_adapters.py scripts/run_mvp3b_source_adapter_infrastructure.py scripts/verify_mvp3b_source_adapter_package.py
# passed

git diff --check
# passed
```

Notes:

```text
- No proof semantics were changed.
- Verifier/package tests were not weakened.
- Frozen MVP-2 assets and MVP-3A proof package artifacts were not modified.
```
