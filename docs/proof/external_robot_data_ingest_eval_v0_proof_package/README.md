# External Robot Data Ingest / Evaluation v0 Proof Package

This package is an RDF external recorded-log ingest contract package.

## Status

`package_status=external_ingest_contract_ready`
`external_source_included=false`

When `external_source_included=false`, this package does not claim that external robot data was evaluated.
It only proves that the contract, package shape, non-claim boundary, and verifier surface are ready.
Until semantic parity checks are implemented, the verifier intentionally rejects `external_data_evaluated` packages.

## Provenance Trust Boundary

RDF recomputes ingest/evaluation consistency from included rows and hashes. Offline verification does not cryptographically prove physical external origin.

## Non-Claims

No real robot success, physical robot readiness, live UR/RTDE support, live Franka hardware support,
live ROS2-DDS bridge readiness, HMD/OpenXR readiness, deployable policy readiness, visual policy
performance, marketplace readiness, production certification, sim-to-real proof, general robot
intelligence, policy uplift, or learning-proven value is claimed.

## Verify

```bash
python3 scripts/verify_external_robot_data_ingest_package.py \
  docs/proof/external_robot_data_ingest_eval_v0_proof_package/package_manifest.json
```
