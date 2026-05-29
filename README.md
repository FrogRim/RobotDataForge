# Robot Data Forge

XR teleoperation trajectory를 replay-verified, action-labelled, task-validated, trainer-loadable dataset artifact로 변환하는 로봇 데이터 인프라 프로젝트입니다.

> Portfolio position: robotics data pipeline, evaluator/curation system, dataset artifact engineering.

## Problem

로봇 학습에서 raw teleoperation trajectory만 저장하면 “학습에 쓸 수 있는 데이터인가?”를 판단하기 어렵습니다. Robot Data Forge는 task outcome, data quality, replay/action contract, curation reason, HDF5 export, trainer loader smoke check를 한 파이프라인에서 남겨 학습 준비 상태를 검증합니다.

## What I Built

- Quest/OpenXR/Isaac Lab teleoperation trajectory recording path
- FastAPI 기반 backend와 trajectory/task schema
- task state extraction, evaluator, curation manifest
- accepted/rejected trajectory reason tracking
- HDF5 dataset export and dataset card generation
- trainer loader smoke check
- MVP-1 proof reports and MVP-2 learning-proof strategy docs

## My Role

FastAPI backend, trajectory schema, evaluator, curation/export pipeline, dataset proof reports를 설계했습니다. 정책 성능 향상 자체를 과장하지 않고, MVP-1에서는 “학습 가능한 dataset artifact를 만들 수 있는가”를 검증 범위로 분리했습니다.

## Stack

| Area | Stack |
| --- | --- |
| Backend | FastAPI, SQLAlchemy, Pydantic, Alembic |
| Robotics runtime | Quest 3, OpenXR, ALVR, SteamVR, Isaac Lab |
| Dataset artifact | HDF5, curation manifest, dataset card |
| Validation | pytest, compileall, proof audit scripts |
| Reporting | HTML proof reports, MVP task specs |

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

## Run

```bash
uv sync --group dev
uv run pytest -q apps/api/tests
uv run python -m compileall -q apps/api/app apps/api/tests scripts
```

Start the local SQLite-backed API:

```bash
DATABASE_URL=sqlite:///./storage/local_api.sqlite \
STORAGE_ROOT=storage \
uv run uvicorn app.main:app --app-dir apps/api --reload
```

Run proof checks:

```bash
uv run python scripts/run_mvp1_proof_audit.py --pretty
uv run python scripts/run_mvp2_learning_sanity.py --pretty
```

## Validation Evidence

| Evidence | Result |
| --- | --- |
| MVP-1 pipeline proof | Complete |
| Curation | accepted/rejected reasons written to manifests |
| Export | HDF5 artifacts generated |
| Trainer smoke | loader smoke check passes |
| Dataset card | generated with proof reports |
| Scope discipline | policy uplift moved to MVP-2, not claimed in MVP-1 |

## Reports

- [Detailed MVP-1/MVP-2 report](docs/RDF_MVP1_MVP2_DETAILED_REPORT_KO.html)
- [MVP-1 one-screen proof result](docs/MVP1_VALIDATED_DATASET_PIPELINE_RESULT.html)
- [MVP-2 learning-proven strategy](docs/MVP2_LEARNING_PROVEN_PROOF_STRATEGY_KO.html)
- [MVP-1 task spec](docs/MVP1_TASK_SPEC.md)
- [API spec](docs/API_SPEC.md)
- [Data schema](docs/DATA_SCHEMA.md)

## Status

MVP-1 is complete as a learning-ready dataset pipeline proof. MVP-2 is reserved for transition-rich data, stronger trainer/policy capacity, and curated vs uncurated held-out A/B evidence.

## Public Release Notes

Raw trajectory logs, SQLite databases, HDF5 files, and local live artifacts are intentionally excluded from git. Publish only sanitized example artifacts when a public demo dataset is ready.
