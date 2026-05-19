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
  - phase-conditional live curation saturation gate
  - trailing-window `RETARGETING_JUMP` live gate
  - Isaac Sim Stop-button guard for the teleop loop

Apply from the IsaacLab repository root:

```bash
git apply /home/kangrim/robot-data-forge/patches/isaaclab/2026-05-19-rdf-live-hmd-curation.patch
```

This patch is a versioned artifact for review/reproduction. It does not replace
an eventual dedicated IsaacLab-side commit.
