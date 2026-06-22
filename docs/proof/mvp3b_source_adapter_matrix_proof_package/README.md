# MVP-3B Source-Adapter Matrix Proof Package

This package is the `MVP-3B Infrastructure Closed` evidence package for Robot
Data Forge source-adapter expansion.

## Claim

MVP-3B proves that three generated/file-backed recorded-log source profiles can
be projected through the common RDF adapter infrastructure into self-contained,
hash-locked source logs, projections, normalized trajectory contracts, adapter
results, and contract-smoke artifacts.

The three source profiles are:

```text
franka_research_arm
robotis_sh5_ros2_dds
universal_robots_ur_industrial_arm
```

These names describe recorded-log fixture profiles used to exercise the shared
adapter path. They are not live hardware integrations.

## Source Of Truth

The verifier treats these files as source evidence:

```text
data/config.json
data/adapter_registry_snapshot.json
data/non_claims_attestation.json
data/source_logs/<adapter_id>/*.json*
data/projections/<adapter_id>/*.json
data/contracts/*_normalized_trajectory_contract.json
data/adapter_results/*_adapter_result.json
data/generated_contract_smoke/<adapter_id>/*.json
data/artifact_index.json
package_manifest.json
```

`data/source_adapter_matrix_summary.json` is a cached summary only. The verifier
recomputes adapter membership, accepted/rejected counts, action-role coverage,
spent-range discipline, non-claims, and summary consistency from the package
contents.

## Verify

Run from the repository root:

```bash
python3 scripts/verify_mvp3b_source_adapter_package.py \
  docs/proof/mvp3b_source_adapter_matrix_proof_package/package_manifest.json
```

Expected result:

```text
VERDICT: VERIFIED
status=source_adapter_infrastructure_closed
accepted_count=3
rejected_count=3
```

The verifier is stdlib-only and does not import producer adapter services.

## Non-Claims

This package does not claim real robot success.
This package does not claim physical robot readiness.
This package does not claim live UR runtime support.
This package does not claim live ROS2-DDS runtime support.
This package does not claim Franka hardware support.
This package does not claim deployable policy readiness.
This package does not claim visual policy performance.
This package does not claim HMD/OpenXR collection readiness.
This package does not claim universal robot support.
This package does not claim marketplace readiness.
This package does not claim production certification.
This package does not claim public sample evidence.
This package does not claim database migration.
This package does not claim production auth.
This package does not claim policy uplift.
This package does not claim learning-proven value.

Trainer/export smoke is contract smoke only. The package JSON records all
learning-result, uplift, and downstream-value fields as false, and the
addendum marker remains absent.

## Range Discipline

MVP-3B opens no calibration, held-out, tuning, or closure range. The spent ranges
remain audit-only/no-reuse:

```text
40000-40049
42000-42049
```

This package is an infrastructure proof, not a learning-proven addendum.
