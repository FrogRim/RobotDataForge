# MVP-2 External Proof Package Freeze Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 현재 `v0_14_comparator_provenance_row_balance` MVP-2 closure를 외부 기술 검토자가 읽고 재현 경로를 추적할 수 있는 frozen evidence package로 고정한다.

**Architecture:** `docs/proof/mvp2_learning_proven_evidence_package/` 아래에 사람이 읽는 summary, evidence index, claims/limitations, reproducibility/review notes, comparator appendix, package manifest를 둔다. 모든 문서는 `heldout_closure_gate_v0_14.json`, root `evidence_manifest.json`, Handoff의 spent held-out registry를 source of truth로 삼고, real robot / HMD / visual policy / deployment claim은 명시적으로 제외한다.

**Tech Stack:** Markdown documentation, JSON package manifest, shell/Python validation, existing proof artifacts under `storage/proof_evidence/`.

---

### Task 1: Package File Skeleton

**Files:**
- Create: `docs/proof/mvp2_learning_proven_evidence_package/README.md`
- Create: `docs/proof/mvp2_learning_proven_evidence_package/evidence_index.md`
- Create: `docs/proof/mvp2_learning_proven_evidence_package/claims_and_limitations.md`
- Create: `docs/proof/mvp2_learning_proven_evidence_package/reproducibility_and_review_notes.md`
- Create: `docs/proof/mvp2_learning_proven_evidence_package/v0_14_comparator_provenance_row_balance_appendix.md`
- Create: `docs/proof/mvp2_learning_proven_evidence_package/package_manifest.json`

- [x] **Step 1: Create the package directory**

Run:

```bash
mkdir -p docs/proof/mvp2_learning_proven_evidence_package
```

Expected: directory exists.

- [x] **Step 2: Create each package file with complete content**

Use `apply_patch` to add all six files. Keep docs Korean by default and preserve code identifiers / paths / schema keys in English.

Expected: six new files exist under `docs/proof/mvp2_learning_proven_evidence_package/`.

### Task 2: Evidence Values and Claim Boundaries

**Files:**
- Modify: files created in Task 1

- [x] **Step 1: Verify source artifact values**

Run:

```bash
python - <<'PY'
import json
from pathlib import Path
gate = json.loads(Path("storage/proof_evidence/mvp2c_isaac_training_calibration/v0_14_comparator_provenance_row_balance/heldout_closure_gate_v0_14.json").read_text())
manifest = json.loads(Path("storage/proof_evidence/mvp2c_isaac_training_calibration/evidence_manifest.json").read_text())
print(gate["baseline_success_rate"], gate["candidate_success_rate"], gate["curated_vs_uncurated_uplift"])
print(gate["confidence_interval_report"])
print(gate["non_claims"])
print(manifest["evidence_manifest_sha256"])
PY
```

Expected output includes baseline `0.1`, candidate `0.8`, uplift approximately `0.7`, CI lower `0.56`, CI upper `0.82`, all non-claims false, and root evidence manifest hash.

- [x] **Step 2: Check package text for required public claims**

Run:

```bash
rg -n "5 / 30|26 / 30|5 / 50|40 / 50|\\+0\\.70|\\[0\\.56, 0\\.82\\]|40000-40049|Isaac held-out evaluator domain|real robot|HMD/OpenXR|visual policy|deployable" docs/proof/mvp2_learning_proven_evidence_package
```

Expected: required metrics and non-claim terms appear.

### Task 3: Developer Handoff and Worklog

**Files:**
- Modify: `docs/developer/worklog.md`
- Modify: `Handoff.md`

- [x] **Step 1: Append worklog entry**

Add a Korean worklog section covering package purpose, changed files, source-of-truth artifacts, validation commands, and remaining gaps.

- [x] **Step 2: Append Handoff note**

Add a compact package note listing package path and frozen claim.

### Task 4: Final Verification and Commit

**Files:**
- All files touched in Tasks 1-3

- [x] **Step 1: Run markdown/package self-review**

Run:

```bash
rg -n "TBD|TODO|real robot success=true|hmd_openxr_readiness=true|visual_policy_performance=true|deployable_real_robot_policy=true|future_tuning_allowed=true|future_closure_reuse_allowed=true" docs/proof/mvp2_learning_proven_evidence_package docs/developer/worklog.md Handoff.md
```

Expected: no matches.

- [x] **Step 2: Validate package manifest JSON**

Run:

```bash
python -m json.tool docs/proof/mvp2_learning_proven_evidence_package/package_manifest.json >/tmp/rdf_mvp2_package_manifest.validated.json
```

Expected: exit code 0.

- [x] **Step 3: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: no output, exit code 0.

- [x] **Step 4: Commit**

Run:

```bash
git add docs/proof/mvp2_learning_proven_evidence_package docs/developer/worklog.md
git commit -m "Freeze the MVP-2 external proof package" \
  -m "Package the v0.14 Isaac evaluator-domain closure into externally reviewable summary, evidence index, claims, reproducibility notes, comparator appendix, and manifest." \
  -m "Constraint: The package must preserve non-claims for real robot, HMD/OpenXR, visual policy, deployable policy, universal robot, marketplace, and production readiness." \
  -m "Rejected: Reopening or retuning held-out 40000-40049 | it is spent audit-only closure evidence." \
  -m "Confidence: high" \
  -m "Scope-risk: narrow" \
  -m "Directive: Future external references should cite this package path and keep 40000-40049 audit-only." \
  -m "Tested: rg package self-review; python -m json.tool package_manifest.json; git diff --check." \
  -m "Not-tested: third-party reproduction on a separate machine; live Isaac rerun; legal/commercial due diligence."
```

Expected: commit succeeds.
