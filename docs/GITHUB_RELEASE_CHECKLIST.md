# GitHub Release Checklist

이 문서는 Robot Data Forge를 GitHub에 처음 공개하기 전 확인할 항목이다.

## Public Positioning

Use this primary description:

```text
Robot Data Forge turns XR teleoperation trajectories into replay-verified,
action-labelled, task-validated, trainer-loadable dataset artifacts for
downstream robotics learning systems.
```

Allowed claims:

- MVP-1 is a learning-ready dataset pipeline proof.
- RDF stores raw XR teleoperation trajectories and preserves source/runtime metadata.
- RDF separates task outcome, data quality, replay/action validity, and curation eligibility.
- RDF generates accepted/rejected curation manifests.
- RDF exports HDF5 dataset artifacts and runs trainer loader smoke checks.
- RDF preserves a negative policy A/B result as MVP-2 evidence.

Blocked claims:

- RDF has proven curated data improves downstream policy success.
- RDF is a VLA, WFM, RL framework, or production robot policy.
- Current artifacts are customer-grade policy uplift proof.
- A zero-uplift policy result means MVP-1 failed.

## Files To Keep Public

Recommended first public commit:

```text
README.md
.env.example
.gitignore
pyproject.toml
uv.lock
docker-compose.yml
apps/
packages/
scripts/
docs/API_SPEC.md
docs/DATA_SCHEMA.md
docs/DEBUGGING_GUIDE.md
docs/DEMO_SCRIPT.md
docs/EXPORT_FORMAT.md
docs/LIVE_VALIDATION_CHECKLIST.md
docs/MVP1_TASK_SPEC.md
docs/MVP1_VALIDATED_DATASET_PIPELINE_RESULT.html
docs/MVP2_LEARNING_PROVEN_PROOF_STRATEGY_KO.html
docs/RDF_MVP1_MVP2_DETAILED_REPORT_KO.html
docs/ROBOT_DATA_FORGE_PROJECT_INSTRUCTIONS.md
docs/GITHUB_RELEASE_CHECKLIST.md
```

Optional later:

```text
docs/papers/
docs/MVP1_STATUS_DASHBOARD.html
docs/MVP1_NEXT_ACTIONS_HMD_GUIDE.html
docs/MVP1C_FULL_PROOF_EXECUTION_GUIDE.*
```

## Files To Keep Local

Do not publish these in the first GitHub release:

```text
storage/
.venv/
.omc/
Handoff.md
docs/WORKLOG.md
output.txt
*.sqlite
*.hdf5
*.h5
*.log
__pycache__/
.pytest_cache/
```

Reasons:

- `storage/` contains live logs, SQLite databases, trajectory artifacts, HDF5 exports, and local proof outputs.
- `Handoff.md` and `docs/WORKLOG.md` contain internal session context and machine-specific paths.
- `output.txt` is terminal capture/debug material.

## Preflight Commands

Run these before creating the first commit:

```bash
cd ~/robot-data-forge

uv run pytest -q apps/api/tests
uv run python -m compileall -q apps/api/app apps/api/tests scripts

python3 - <<'PY'
from html.parser import HTMLParser
from pathlib import Path
for path in [
    Path("docs/RDF_MVP1_MVP2_DETAILED_REPORT_KO.html"),
    Path("docs/MVP1_VALIDATED_DATASET_PIPELINE_RESULT.html"),
    Path("docs/MVP2_LEARNING_PROVEN_PROOF_STRATEGY_KO.html"),
]:
    HTMLParser().feed(path.read_text())
    print(f"HTML_PARSE_OK {path}")
PY

git status --short
```

## First GitHub Commands

After creating an empty GitHub repository:

```bash
cd ~/robot-data-forge
git init
git add .
git status --short
git commit -m "Prepare Robot Data Forge MVP-1 public release"
git branch -M main
git remote add origin git@github.com:<YOUR_USER_OR_ORG>/robot-data-forge.git
git push -u origin main
```

Before `git commit`, inspect `git status --short` carefully. The first commit should not include `storage/`, `.venv/`, `Handoff.md`, `docs/WORKLOG.md`, `output.txt`, SQLite files, HDF5 files, logs, caches, or local machine paths beyond documented examples.

## Suggested GitHub Description

```text
Replay-verified XR teleoperation dataset infrastructure for downstream robotics learning.
```

## Suggested Topics

```text
robotics
teleoperation
dataset
xr
isaac-lab
imitation-learning
robot-learning
data-curation
```

## Release Boundary

The first GitHub release should be positioned as:

```text
Portfolio-grade MVP-1 technical release.
```

Do not position it yet as:

```text
Production open-source platform.
Customer-ready dataset marketplace.
Proven policy-uplift benchmark.
VLA or World Foundation Model project.
```
