# IsaacLab Runtime Patches

This directory stores reviewable patches for local IsaacLab runtime changes that
Robot Data Forge depends on during live XR/HMD collection.

The RDF repository owns the dataset API, evaluator, export, diagnostics, and
proof documents. Some live collection behavior is implemented in the external
IsaacLab checkout at `/home/kangrim/IsaacLab`; those changes are captured here
so the live runtime contract can be reviewed and replayed from the RDF repo.

Current patch:

- `2026-05-19-rdf-live-hmd-curation.patch`
  - RDF handtracking recorder integration
  - HMD task guidance panel support
  - robot-space start-box recenter gate for HMD collection
  - HMD/AR-visible recenter start-box wireframe at `/World/RDFRecenterStartBox`
  - setup-only pre-recenter control into the start box before recording begins
  - per-episode/reset bounded random recenter box offset
  - phase-conditional live curation saturation gate
  - trailing-window `RETARGETING_JUMP` live gate
  - Isaac Sim Stop-button guard for the teleop loop

The current HMD recenter UX is documented in
`docs/HMD_RECENTER_START_BOX.md`. The default live collection contract is:

```text
RDF_RECENTER_MODE=robot_start_box
RDF_RECENTER_BOX_CENTER_SOURCE=hole_target_approach
RDF_RECENTER_BOX_APPROACH_OFFSET=0,0,0.08
RDF_RECENTER_BOX_RANDOM_OFFSET=0.02,0.02,0.01
RDF_RECENTER_BOX_VISUAL=1
RDF_BLOCK_TELEOP_UNTIL_RECENTER=1
RDF_RECENTER_SETUP_CONTROL=1
```

Apply from the IsaacLab repository root. The patch is stored as a zero-context
diff so RDF repo whitespace checks do not flag unified-diff context lines:

```bash
git apply --unidiff-zero /home/kangrim/robot-data-forge/patches/isaaclab/2026-05-19-rdf-live-hmd-curation.patch
```

This patch is a versioned artifact for review/reproduction. It does not replace
an eventual dedicated IsaacLab-side commit.
