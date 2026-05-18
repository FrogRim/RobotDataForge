# Robot Data Forge

Robot Data Forge turns XR teleoperation trajectories into replay-verified, action-labelled, task-validated, trainer-loadable dataset artifacts for downstream robotics learning systems.

It is not a VLA, World Foundation Model, RL framework, or robot policy benchmark. RDF is data infrastructure: it records raw XR/HMD teleoperation, validates task state and data quality, gates replay/action contracts, curates accepted/rejected trajectories, exports HDF5 datasets, and checks that a trainer can load the result.

## MVP-1 Status

MVP-1 is complete as a **learning-ready dataset pipeline proof**.

What MVP-1 proves:

- raw Quest/OpenXR/Isaac teleoperation trajectories can be stored with source/runtime metadata
- peg-in-hole task state can be extracted from recorded frames
- task outcome is recorded separately from data quality
- operator success is separated from evaluator task success
- replay/action contract evidence is recorded before training eligibility
- accepted/rejected curation reasons are written to manifests
- transition coverage is tracked in addition to episode-level outcome
- HDF5/export artifacts are generated
- trainer loader smoke checks pass
- dataset cards and proof reports are generated

What MVP-1 does **not** claim:

- curated data improves held-out policy success rate
- RDF has trained a production robot policy
- RDF is a VLA/WFM system
- current artifacts are customer-grade policy-uplift proof

Policy uplift and downstream learning performance are MVP-2 work.

## Pipeline

```text
Quest 3 handtracking
  -> ALVR + SteamVR/OpenXR
  -> Isaac Lab teleoperation
  -> trajectory recorder
  -> task_state extraction
  -> task outcome + data quality evaluation
  -> replay/action contract gate
  -> accepted/rejected curation manifest
  -> HDF5 export + dataset card
  -> trainer loader smoke
```

## Data Pipeline Principles

1. Store raw trajectories generously.
2. Keep task success separate from data quality.
3. Require replay/action contract evidence before marking data as training-eligible.
4. Record accepted and rejected reasons in curation manifests.
5. Define task goal, progress, and efficiency with a BEHAVIOR-style task spec.
6. Record transition coverage as well as episode-level outcome.
7. Produce dataset artifacts that pass HDF5/export and trainer smoke checks.
8. Move policy uplift claims to MVP-2.

## Repository Layout

```text
apps/api/       FastAPI backend, models, evaluator, curator, export services
apps/web/       Minimal dashboard/prototype frontend
packages/       Shared dataset and trajectory schemas
scripts/        Offline proof scripts, live smoke scripts, export/trainer checks
docs/           Specs, reports, task definitions, debugging guides
```

Generated runtime data is intentionally not committed:

```text
storage/
*.sqlite
*.hdf5
*.log
output.txt
```

## Reports

Key project reports:

- [Detailed MVP-1/MVP-2 report](docs/RDF_MVP1_MVP2_DETAILED_REPORT_KO.html)
- [MVP-1 one-screen proof result](docs/MVP1_VALIDATED_DATASET_PIPELINE_RESULT.html)
- [MVP-2 learning-proven strategy](docs/MVP2_LEARNING_PROVEN_PROOF_STRATEGY_KO.html)
- [MVP-1 task spec](docs/MVP1_TASK_SPEC.md)
- [Project instructions](docs/ROBOT_DATA_FORGE_PROJECT_INSTRUCTIONS.md)
- [API spec](docs/API_SPEC.md)
- [Data schema](docs/DATA_SCHEMA.md)

The HTML reports are self-contained local reports. If hosted on GitHub Pages, they can be used as the portfolio-facing visual summary.

## Quickstart

Install dependencies:

```bash
uv sync --group dev
```

Run focused tests:

```bash
uv run pytest -q apps/api/tests
```

Run a lightweight compile check:

```bash
uv run python -m compileall -q apps/api/app apps/api/tests scripts
```

Start the local SQLite-backed API:

```bash
DATABASE_URL=sqlite:///./storage/local_api.sqlite \
STORAGE_ROOT=storage \
uv run uvicorn app.main:app --app-dir apps/api --reload
```

## Proof Commands

MVP-1 dataset pipeline proof audit:

```bash
uv run python scripts/run_mvp1_proof_audit.py --pretty
```

MVP-2 pre-A/B learning sanity:

```bash
uv run python scripts/run_mvp2_learning_sanity.py --pretty
```

Current interpretation:

- MVP-1 learning-ready proof is complete.
- MVP-2 learning-proven proof is pending.
- The latest live artifact passes trainer overfit sanity but is not policy-A/B-ready because accepted transition coverage is currently SEAT-heavy and lacks APPROACH/CONTACT/INSERT coverage.

## Live XR Smoke Test

The live path expects Quest 3, ALVR, SteamVR/OpenXR, Isaac Lab, and the local RDF API.

```bash
RDF_RECORD=1 \
RDF_ISAAC_TASK=Isaac-Forge-PegInsert-Direct-v0 \
RDF_TASK_TYPE=peg_in_hole \
./scripts/run_live_rdf_smoke_test.sh --no-start-xr
```

Use `--no-start-xr` only when ALVR, SteamVR, and the Quest connection are already prepared manually.

## MVP-2 Direction

MVP-2 is a staged learning-proven proof, not a blind policy A/B rerun.

Before claiming policy uplift, RDF should prove:

- transition-rich accepted data
- train-set overfit sanity
- replay/action contract sanity
- stronger policy/trainer capacity
- dataset size and coverage ablations
- curated vs uncurated held-out A/B
- positive or negative result report

The current zero-uplift A/B result is preserved as MVP-2 negative evidence, not treated as an MVP-1 failure.

## Public Release Notes

This repository is prepared as a portfolio-grade technical release. Local live logs, HDF5 files, SQLite databases, and raw trajectory artifacts are excluded by `.gitignore`.

Before turning this into a production open-source project, choose a license, add contribution guidelines, and publish sanitized example artifacts.

## License

License is not selected yet.
