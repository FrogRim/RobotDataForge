# LeRobot Public Dataset Matrix Semantic Parity Package

This package supports one narrow claim: Robot Data Forge combines a frozen
verified ALOHA audited slice with a newly generated SO-100 audited slice, then
independently reverifies both pinned public LeRobot profiles through the same
semantic parity matrix verifier.

Profiles:

- `lerobot_aloha_static_coffee`: `lerobot/aloha_static_coffee` robot_type=`aloha`, dims=14x14
- `lerobot_svla_so100_pickplace`: `lerobot/svla_so100_pickplace` robot_type=`so100`, dims=6x6

The matrix verifier recomputes each profile from included source rows and
receipts. Its provenance tier is refetchable public bytes plus audited profile
metadata. The profile registry is explicit; this is not a generic LeRobot
parser and not a full dataset evaluation.

```bash
python3 scripts/verify_lerobot_public_dataset_matrix_package.py \
  docs/proof/lerobot_public_dataset_matrix_semantic_parity_proof_package/package_manifest.json
```

Non-claims:

- No generic LeRobot parser support.
- No full dataset evaluation.
- No real robot success.
- No physical robot readiness.
- No live hardware support.
- No visual policy performance.
- No policy uplift.
- No learning-proven value.
- No deployable policy readiness.
- No marketplace readiness.
- No production certification.
- No sim-to-real proof.
