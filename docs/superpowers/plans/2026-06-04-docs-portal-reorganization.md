# Docs Portal Reorganization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize Robot Data Forge docs into a root `index.html` portal with buyer, developer, HMD experiment, and archive sections, then physically move docs into those sections.

**Architecture:** Keep `index.html` at the repository root as the public landing portal and `docs/index.html` as the detailed documentation hub. Move existing docs into audience-based folders while preserving historical content and repairing repo-local links.

**Tech Stack:** Static HTML, Markdown, POSIX shell file moves, Python stdlib `html.parser` link validation.

---

### Task 1: Create Target Directories and Move Files

**Files:**
- Create directories: `docs/buyer`, `docs/developer`, `docs/developer/papers`, `docs/experiments/hmd`, `docs/archive`
- Move existing docs from `docs/` into those directories.

- [ ] **Step 1: Create directories**

Run:

```bash
mkdir -p docs/buyer docs/developer docs/developer/papers docs/experiments/hmd docs/archive
```

Expected: command exits with status 0.

- [ ] **Step 2: Move buyer-facing docs**

Run:

```bash
mv docs/FORGEXR_DATA_TRUST_LAYER_RESET_SUMMARY_2026_06_04.html docs/buyer/data_trust_layer_reset.html
mv docs/MVP1_VALIDATED_DATASET_PIPELINE_RESULT.html docs/buyer/mvp1_validated_dataset_pipeline_result.html
mv docs/MVP2_LEARNING_PROVEN_PROOF_STRATEGY_KO.html docs/buyer/mvp2_learning_proven_strategy_ko.html
mv docs/RDF_MVP1_MVP2_DETAILED_REPORT_KO.html docs/buyer/rdf_mvp1_mvp2_detailed_report_ko.html
mv docs/social/linkedin_posts.md docs/buyer/social_narrative.md
rmdir docs/social
```

Expected: files exist under `docs/buyer`; `docs/social` is removed.

- [ ] **Step 3: Move developer docs**

Run:

```bash
mv docs/API_SPEC.md docs/developer/api_spec.md
mv docs/DATA_SCHEMA.md docs/developer/data_schema.md
mv docs/DEBUGGING_GUIDE.md docs/developer/debugging_guide.md
mv docs/DEMO_SCRIPT.md docs/developer/demo_script.md
mv docs/EXPORT_FORMAT.md docs/developer/export_format.md
mv docs/LIVE_VALIDATION_CHECKLIST.md docs/developer/live_validation_checklist.md
mv docs/MVP1_REFERENCE_MAPPING.md docs/developer/reference_mapping.md
mv docs/MVP1_TASK_SPEC.md docs/developer/task_spec.md
mv docs/ROADMAP.md docs/developer/roadmap.md
mv docs/ROBOT_DATA_FORGE_PROJECT_INSTRUCTIONS.md docs/developer/project_instructions.md
mv docs/WORKLOG.md docs/developer/worklog.md
mv docs/papers/* docs/developer/papers/
rmdir docs/papers
```

Expected: developer docs and papers exist under `docs/developer`.

- [ ] **Step 4: Move HMD experiment docs**

Run:

```bash
mv docs/GATE0_INPUT_TRUTH_WORK_SUMMARY_2026_06_03.html docs/experiments/hmd/gate0_input_truth_work_summary_2026_06_03.html
mv docs/HMD_INPUT_STRUCTURAL_ANALYSIS_2026_06_03.html docs/experiments/hmd/hmd_input_structural_analysis_2026_06_03.html
mv docs/HMD_RECENTER_START_BOX.md docs/experiments/hmd/hmd_recenter_start_box.md
mv docs/HMD_YAW_OFFSET_AB_LIVE_DEBUG.md docs/experiments/hmd/hmd_yaw_offset_ab_live_debug.md
mv docs/MVP1_NEXT_ACTIONS_HMD_GUIDE.html docs/experiments/hmd/mvp1_next_actions_hmd_guide.html
mv docs/MVP_PRE_HMD_STEP1_INPUT_GATES.html docs/experiments/hmd/mvp_pre_hmd_step1_input_gates.html
mv docs/MVP_TELEOP_INPUT_STREAM_RESEARCH.html docs/experiments/hmd/mvp_teleop_input_stream_research.html
mv docs/RAW_WRIST_DIRECT_CONTROL_RESEARCH.md docs/experiments/hmd/raw_wrist_direct_control_research.md
mv docs/UX_CALIBRATION_PROBLEM_STATEMENT.md docs/experiments/hmd/ux_calibration_problem_statement.md
```

Expected: HMD and Gate 0 experiment docs exist under `docs/experiments/hmd`.

- [ ] **Step 5: Move archive docs**

Run:

```bash
mv docs/DATA_COLLECTION_LOG.md docs/archive/data_collection_log.md
mv docs/FRONTEND_PLAN.md docs/archive/frontend_plan.md
mv docs/GITHUB_RELEASE_CHECKLIST.md docs/archive/github_release_checklist.md
mv docs/MVP0_SMOKE_VALIDATION_REPORT.md docs/archive/mvp0_smoke_validation_report.md
mv docs/MVP1C_FULL_PROOF_EXECUTION_GUIDE.html docs/archive/mvp1c_full_proof_execution_guide.html
mv docs/MVP1C_FULL_PROOF_EXECUTION_GUIDE.md docs/archive/mvp1c_full_proof_execution_guide.md
mv docs/MVP1_STATUS_DASHBOARD.html docs/archive/mvp1_status_dashboard.html
mv docs/MVP_COMPLETION_PLAN.md docs/archive/mvp_completion_plan.md
mv docs/MVP_PROGRESS_OVERVIEW.html docs/archive/mvp_progress_overview.html
mv docs/NEXT_ISSUES.md docs/archive/next_issues.md
mv docs/ROBOT_DATA_FORGE_MVP.md docs/archive/robot_data_forge_mvp.md
```

Expected: older MVP, frontend, release, and planning docs exist under `docs/archive`.

### Task 2: Create Root and Section Portals

**Files:**
- Create: `index.html`
- Replace: `docs/index.html`
- Create: `docs/buyer/index.html`
- Create: `docs/developer/index.html`
- Create: `docs/experiments/hmd/index.html`
- Create: `docs/archive/index.html`

- [ ] **Step 1: Create `index.html`**

Create a root portal with four links:

```text
docs/buyer/index.html
docs/developer/index.html
docs/experiments/hmd/index.html
docs/archive/index.html
```

The page must say RDF is a data trust layer, not an HMD demo, and must link to `docs/buyer/data_trust_layer_reset.html` as the recommended first read.

- [ ] **Step 2: Replace `docs/index.html`**

Create a detailed docs hub with the same four audience sections and a short explanation:

```text
Buyer docs: trust, proof, limitations.
Developer docs: contracts, validation, research.
HMD experiments: adapter history and Gate 0 evidence.
Archive: old MVP and planning material.
```

- [ ] **Step 3: Create section index pages**

Create each section index with a complete list of files in that section:

```text
docs/buyer/index.html
docs/developer/index.html
docs/experiments/hmd/index.html
docs/archive/index.html
```

Expected: every moved file is reachable from one section index.

### Task 3: Repair Relocated Links and Durable References

**Files:**
- Modify: `docs/buyer/data_trust_layer_reset.html`
- Modify: `docs/developer/worklog.md`
- Modify: `Handoff.md`
- Modify: `tasks/todo.md`
- Modify any moved HTML page that has broken repo-local links.

- [ ] **Step 1: Update reset summary links**

In `docs/buyer/data_trust_layer_reset.html`, update relocated links:

```text
social/linkedin_posts.md -> social_narrative.md
../README.md -> ../../README.md
ROBOT_DATA_FORGE_PROJECT_INSTRUCTIONS.md -> ../developer/project_instructions.md
WORKLOG.md -> ../developer/worklog.md
../Handoff.md -> ../../Handoff.md
../scripts/run_data_trust_layer_proof.py -> ../../scripts/run_data_trust_layer_proof.py
../apps/api/tests/test_data_trust_layer_proof_script.py -> ../../apps/api/tests/test_data_trust_layer_proof_script.py
../storage/data_trust_layer_proof/... -> ../../storage/data_trust_layer_proof/...
```

Expected: local links resolve from `docs/buyer/`.

- [ ] **Step 2: Update durable references**

Update `Handoff.md`, `docs/developer/worklog.md`, and `tasks/todo.md` references from old paths to new paths:

```text
docs/FORGEXR_DATA_TRUST_LAYER_RESET_SUMMARY_2026_06_04.html -> docs/buyer/data_trust_layer_reset.html
docs/social/linkedin_posts.md -> docs/buyer/social_narrative.md
docs/WORKLOG.md -> docs/developer/worklog.md
docs/ROBOT_DATA_FORGE_PROJECT_INSTRUCTIONS.md -> docs/developer/project_instructions.md
```

Expected: stale references to the old reset summary path and old social path are gone except inside the design/plan history.

### Task 4: Validate and Fix Links

**Files:**
- Read all `*.html` under `docs/` and root `index.html`.
- Modify only files with broken local links.

- [ ] **Step 1: Run HTML local link validation**

Run:

```bash
python3 - <<'PY'
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

root = Path.cwd()
html_files = [root / "index.html", *sorted((root / "docs").rglob("*.html"))]
allow_missing_prefixes = ("../../storage/", "../storage/", "storage/")

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

failures = []
for path in html_files:
    parser = LinkParser()
    parser.feed(path.read_text(encoding="utf-8"))
    for href in parser.links:
        parsed = urlparse(href)
        if parsed.scheme or href.startswith("#") or href.startswith("mailto:"):
            continue
        if href.startswith(allow_missing_prefixes):
            continue
        target = (path.parent / href).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            failures.append((path, href, "escapes repo"))
            continue
        if not target.exists():
            failures.append((path, href, "missing"))

if failures:
    for path, href, reason in failures:
        print(f"{path.relative_to(root)} -> {href}: {reason}")
    raise SystemExit(1)
print(f"validated_html_files={len(html_files)}")
PY
```

Expected: prints `validated_html_files=<count>` and exits 0.

- [ ] **Step 2: Search for stale references**

Run:

```bash
rg -n "FORGEXR_DATA_TRUST_LAYER_RESET_SUMMARY_2026_06_04|docs/social/linkedin_posts.md|docs/WORKLOG.md|docs/ROBOT_DATA_FORGE_PROJECT_INSTRUCTIONS.md" README.md Handoff.md docs tasks || true
```

Expected: no stale references in current-facing docs; references inside design/plan history are acceptable if they describe migration history.

- [ ] **Step 3: Confirm papers moved**

Run:

```bash
test ! -d docs/papers
test -f docs/developer/papers/README.md
find docs/developer/papers -maxdepth 1 -type f | sort
```

Expected: `docs/papers` is absent and paper files are listed under `docs/developer/papers`.

- [ ] **Step 4: Run diff whitespace check**

Run:

```bash
git diff --check -- index.html docs Handoff.md tasks/todo.md
```

Expected: no output and exit 0.

### Task 5: Update Task Notes and Report

**Files:**
- Modify: `tasks/todo.md`
- Modify: `Handoff.md`
- Modify: `docs/developer/worklog.md`

- [ ] **Step 1: Record final structure and validation**

Add a short docs reorganization review to `tasks/todo.md`, `Handoff.md`, and `docs/developer/worklog.md`:

```text
Root portal: index.html
Docs hub: docs/index.html
Buyer docs: docs/buyer/
Developer docs: docs/developer/
HMD experiment docs: docs/experiments/hmd/
Archive docs: docs/archive/
Validation: HTML local link validation, stale reference scan, papers moved check, git diff --check
```

Expected: future sessions know where to find the reorganized docs and which command proved links are valid.
