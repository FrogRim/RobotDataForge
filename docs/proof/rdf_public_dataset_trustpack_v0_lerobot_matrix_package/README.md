# RDF Public Dataset TrustPack v0

This package supports one narrow productization claim: Robot Data Forge can
materialize the already-closed ALOHA + SO-100 public LeRobot dataset matrix
discipline into a self-contained TrustPack surface with a buyer-readable report,
existing matrix verifier compatibility, HTML claim scanning, and independent
baseline-vs-generated regeneration comparison.

Profiles:

- `lerobot_aloha_static_coffee`: `lerobot/aloha_static_coffee` robot_type=`aloha`, dims=14x14, rows=8
- `lerobot_svla_so100_pickplace`: `lerobot/svla_so100_pickplace` robot_type=`so100`, dims=6x6, rows=8

The proof source of truth is the verifier-backed package evidence, not the
top-level HTML report or this README. This package does not add a new public
dataset profile and does not rederive upstream public data as a new proof claim.

Required verification gates:

```bash
python3 scripts/verify_lerobot_public_dataset_matrix_package.py \
  docs/proof/rdf_public_dataset_trustpack_v0_lerobot_matrix_package/package_manifest.json

python3 scripts/scan_rdf_trustpack_html_claims.py \
  --package-dir docs/proof/rdf_public_dataset_trustpack_v0_lerobot_matrix_package

python3 scripts/compare_rdf_public_dataset_trustpack_regeneration.py \
  --baseline-package-dir docs/proof/lerobot_public_dataset_matrix_semantic_parity_proof_package \
  --generated-package-dir docs/proof/rdf_public_dataset_trustpack_v0_lerobot_matrix_package
```

Non-claims:

- No generic LeRobot parser support.
- No full LeRobot parser support.
- No full dataset evaluation.
- No real robot success.
- No physical robot readiness.
- No live hardware support.
- No live ALOHA support.
- No live UR RTDE support.
- No live Franka hardware support.
- No live ROS2 DDS bridge readiness.
- No visual policy performance.
- No policy uplift.
- No learning-proven value.
- No deployable policy readiness.
- No marketplace readiness.
- No production certification.
- No sim-to-real proof.
- No general robot intelligence.
