# MVP-3A Target / Fixture Pose Variant Proof Package

This package is the MVP-3A actual Isaac proof package for the
`target_fixture_pose_variant` slice.

It is self-contained for verdict-critical evidence. A reviewer can clone the
repo and recompute the verdict from git-tracked JSON without access to the
local `storage/` directory or an Isaac runtime:

```bash
python3 scripts/verify_proof_package.py \
  docs/proof/mvp3a_target_fixture_pose_variant_proof_package/package_manifest.json
```

Expected verifier result:

```text
VERDICT: VERIFIED
package_status=proof_infrastructure_closed
learning_result=positive_uplift
learning_proven_addendum=present
```

Actual Isaac evidence summary:

```text
calibration: baseline 5/30, candidate 30/30
held-out: baseline 8/50, candidate 48/50
held-out uplift: +0.80
fresh calibration range: 41000-41029
fresh held-out range: 42000-42049
spent inherited held-out range: 40000-40049
proof_runtime=dedicated_isaac_connector_insertion_evaluator
```

The verifier recomputes rollout counts, success counts, success rates, uplift,
seed disjointness, spent-range no-reuse, gate consistency, policy artifact
binding, per-rollout C-lite mask consistency, non-claims, cached summary
consistency, and learning addendum consistency.

Non-claims are part of the package. This does not prove real robot success,
physical robot readiness, deployable policy readiness, visual policy
performance, HMD/OpenXR readiness, UR adapter support, ROS2-DDS adapter support,
Franka hardware support, marketplace readiness, production certification, or
universal robot support.
