# RDF Proof Evidence Storage

`storage/proof_evidence/` is the persistent local root for proof-run evidence
that must survive `/tmp` cleanup or machine reboot.

Policy:

- Large generated artifacts remain local and gitignored.
- Each proof slice writes `evidence_manifest.json`.
- `evidence_manifest.json` is intentionally git-trackable.
- The manifest records relative file paths, file sizes, sha256 hashes, and the
  reproducible command used to generate the run.
- The manifest excludes itself from its file list so listed hashes always refer
  to concrete proof artifacts.

Current Stage 0 runners:

- `mvp2b_isaac_proof_evaluator`
- `mvp2c_isaac_training_calibration`

Do not use `/tmp/rdf-*` as the primary evidence location for future Isaac proof
runs.

Spent held-out ranges:

| Range | Status | Rule |
| --- | --- | --- |
| `40000-40049` | `spent_for_mvp2_v0_14_closure` | Preserve for audit only. Do not use for future tuning or closure proof. |

Future MVP-2 closure attempts must use a fresh pre-registered held-out range.
