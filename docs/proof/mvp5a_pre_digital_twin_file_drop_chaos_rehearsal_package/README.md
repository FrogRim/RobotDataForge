# MVP-5A-pre Digital Twin File-Drop Chaos Rehearsal

Status: `file_drop_rehearsal_contract_ready`

This package rehearses RDF recorded-log file-drop ingestion with deterministic
digital-twin UR/Franka/ROS2-style/generic logs.

The default verifier recomputes package consistency from included evidence:

```bash
python3 scripts/verify_mvp5a_pre_file_drop_chaos_rehearsal_package.py /home/kangrim/robot-data-forge/docs/proof/mvp5a_pre_digital_twin_file_drop_chaos_rehearsal_package/package_manifest.json --allow-contract-ready --deep-hdf5
```

`file_drop_rehearsal_ready=true` is allowed only for packages that include
`data/runtime_evidence/runtime_event_log.jsonl` plus the L2 runtime manifest and
reconstruction receipt. Runtime-shaped summary JSON alone is not closing
evidence. This checked-in fixture package remains contract-ready.

## Claim Boundary

No external partner data evaluation.
No real robot success.
No hardware readiness.
No live UR RTDE support.
No live Franka hardware support.
No live ROS2 DDS bridge readiness.
No native MCAP parser support.
No policy uplift.
No production certification.
No marketplace readiness.
No sim-to-real performance claim.
