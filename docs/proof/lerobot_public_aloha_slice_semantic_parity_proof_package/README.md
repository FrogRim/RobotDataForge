# LeRobot Public ALOHA Audited Slice Semantic Parity Package

This package supports one narrow claim: Robot Data Forge evaluated a
deterministic audited slice from the public LeRobot dataset
`lerobot/aloha_static_coffee` at pinned revision `b144896feb1f37398a862927b22cd3abdf005a6b`.

The default verifier recomputes source binding, included raw row validity,
raw-to-RDF semantic conversion, generic state/action contract agreement,
export/trainer-smoke evidence, receipt consistency, HDF5 float32 payload
presence for this package's fixed layout, spent-range discipline, and
non-claim boundaries from files in this repository.

This is an ALOHA audited-slice profile, not a general LeRobot importer.
The fixed repo id, pinned revision, source file, first-episode slice rule,
14-dimensional state/action contract, and HDF5 layout are part of the
verifier contract for this package. A second public LeRobot dataset should
define a new explicit slice profile instead of silently reusing these
assumptions.

```bash
python3 scripts/verify_lerobot_public_slice_package.py \
  docs/proof/lerobot_public_aloha_slice_semantic_parity_proof_package/package_manifest.json
```

Optional stronger checks:

```bash
python3 scripts/verify_lerobot_public_slice_package.py <manifest> --deep-hdf5
python3 scripts/verify_lerobot_public_slice_package.py <manifest> --refetch-public-source
uv run --with pyarrow scripts/verify_lerobot_public_slice_package.py <manifest> --reextract-public-source
```

The default verifier is offline. `--refetch-public-source` rechecks the public
Hugging Face files against the pinned hashes, and `--reextract-public-source`
rebuilds the included raw rows from the pinned Parquet source.

Non-claims:

- No full LeRobot parser support.
- No full dataset evaluation.
- No real robot success.
- No physical robot readiness.
- No live hardware support.
- No visual policy performance.
- No policy uplift.
- No deployable policy readiness.
- No marketplace readiness.
- No production certification.
- No sim-to-real proof.
