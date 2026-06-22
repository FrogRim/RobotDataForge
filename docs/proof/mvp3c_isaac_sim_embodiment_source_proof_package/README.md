# MVP-3C Isaac Sim Embodiment Source Proof Package

## Status

- package_status: `isaac_sim_embodiment_source_closed`
- runtime_evidence_captured: `True`
- closure_assertion: `True`
- evidence_kind: `isaac_sim_runtime_backed_command_state_log`
- note: This package is the runtime-backed MVP-3C source/embodiment infrastructure closure package.

## Claim

The package verifies that Franka Panda and UR10e Isaac Sim command/state source logs can be recorded, projected through RDF adapter infrastructure, packaged as self-contained evidence, and independently audited from tracked package data.

The verifier recomputes artifact hashes, required embodiment exactness, source-log completeness, runtime metadata binding, per-row `runtime_capture_id` binding, projection hash binding, accepted/rejected counts, normalized contract action roles, spent range discipline, opened-range emptiness, and forbidden claim boundaries.

## Verify

```bash
python3 scripts/verify_mvp3c_isaac_sim_embodiment_source_package.py docs/proof/mvp3c_isaac_sim_embodiment_source_proof_package/package_manifest.json
```

Expected result:

```text
VERDICT: VERIFIED
status=isaac_sim_embodiment_source_closed
```

The verifier is stdlib-only and does not import the package builder, the proof spine, Isaac Sim, numpy, or scipy.

## Evidence Boundary

- `data/` is the self-contained audit bundle.
- `data/runtime_capture.json` is copied into the package for runtime-backed closure and hash-bound by the manifest.
- `package_manifest.json` and `data/artifact_index.json` hash-lock the data artifacts.
- A local provenance source outside this tracked package was used to build the package, but the verifier audits the copied runtime-capture source in `data/runtime_capture.json` after generation.
- The package opens no calibration, held-out, tuning, or closure seed range.
- The package records spent/no-reuse ranges `40000-40049` and `42000-42049` as audit-only ranges.
- `learning_proven_addendum` is absent.

## Non-Claims

- Does not claim real robot success.
- Does not claim real robot readiness.
- Does not claim physical robot readiness.
- Does not claim deployable policy readiness.
- Does not claim visual policy performance.
- Does not claim HMD OpenXR collection readiness.
- Does not claim HMD readiness.
- Does not claim live runtime support.
- Does not claim live UR runtime support.
- Does not claim live UR hardware support.
- Does not claim live Franka hardware support.
- Does not claim live ROS2 DDS runtime support.
- Does not claim ROS2 bridge support.
- Does not claim Franka hardware support.
- Does not claim UR hardware support.
- Does not claim policy uplift.
- Does not claim learning proven value.
- Does not claim marketplace readiness.
- Does not claim production certification.
- Does not claim production auth.
- Does not claim production robot support.
- Does not claim universal robot support.
- Does not claim public sample import.
- Does not claim public sample evidence.
- Does not claim DB migration.

## Tamper Discipline

G006/G009 verifies hash-refreshed semantic tamper cases against a copied real package: runtime capture source drift, preflight boolean drift, runtime capture ID drift, source-row embodiment drift, runtime metadata removal, source-row/runtime-metadata mismatch, forbidden claim injection, opened range injection, spent range weakening, count drift, projection binding drift, and required action-role removal.
