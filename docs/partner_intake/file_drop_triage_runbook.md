# File-drop triage runbook

This runbook is for the first hour after receiving a recorded robot log folder or zip.

## 1. Preserve original files

```bash
mkdir -p /tmp/rdf_partner_drop/original
cp -a /path/from/partner/. /tmp/rdf_partner_drop/original/
```

Do not rename source files until the original hash is recorded.

## 2. Choose the profile explicitly

Use the supported profile list.

```bash
uv run python scripts/rdf_file_drop_evaluator.py profiles list --json
```

If no profile fits, stop. Do not auto-detect a trusted profile.

## 3. Preflight

```bash
uv run python scripts/rdf_file_drop_evaluator.py preflight \
  /tmp/rdf_partner_drop/original \
  --profile <profile_id> \
  --json
```

If preflight fails, keep the result and rejection reasons. Do not edit source files to make them pass unless the partner confirms the correction.

## 4. Evaluate

```bash
uv run python scripts/rdf_file_drop_evaluator.py evaluate \
  /tmp/rdf_partner_drop/original \
  --profile <profile_id> \
  --out artifacts/rdf_file_drop_evaluator/<run_id> \
  --json
```

Rejected runs are still useful. They should preserve raw evidence and structured rejection reasons, but must not become training eligible.

## 5. Verify

```bash
uv run python scripts/rdf_file_drop_evaluator.py verify \
  artifacts/rdf_file_drop_evaluator/<run_id> \
  --deep-hdf5 \
  --json
```

The verifier result is the local source of truth. Do not override it from a buyer report, UI state, or cached summary.

## 6. Inspect buyer report

Open:

```text
artifacts/rdf_file_drop_evaluator/<run_id>/reports/buyer_report.html
```

The report must include non-claims and rejection reasons when applicable.

## 7. Escalate only with evidence

If the file-drop fails, send the partner:

```text
profile_id used
command run
exit code
rejection reasons
missing files or fields
unit/dimension/timestamp mismatch evidence
privacy/license blockers if present
```

Do not send a broad "data bad" message without the structured evidence.

## 8. Stop conditions

Stop if:

```text
profile is unknown
source license is unclear
privacy status is unclear
metadata claims external origin but owner/permission is absent
data requires live robot control to interpret
data requires live ROS2/DDS runtime to parse
source rows cannot support action/state semantics
HDF5 export would erase embodiment-specific semantics
```
