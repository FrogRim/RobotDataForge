# MVP-5A-pre Digital Twin File-Drop Chaos Rehearsal

Status: `file_drop_rehearsal_ready`

This package rehearses RDF recorded-log file-drop ingestion with deterministic
digital-twin UR/Franka/ROS2-style/generic logs.

The default verifier recomputes package consistency from included evidence:

```bash
uv run python scripts/verify_mvp5a_pre_file_drop_chaos_rehearsal_package.py docs/proof/mvp5a_pre_digital_twin_file_drop_chaos_rehearsal_package/package_manifest.json --deep-hdf5
```

`file_drop_rehearsal_ready=true` is opened only for the L2/L3
capture-edge path: raw runtime events, process provenance receipt, L2 runtime
manifest, reconstruction receipt, and verifier recomputation all agree.
Runtime-shaped summary JSON or helper-derived event logs are not closing
evidence.

This package keeps `runtime_capture_*` false because no
`data/canonical_trace/runtime_capture.json` artifact is included. The closing
evidence is `runtime_event_capture_*`: the hash-bound raw runtime event log and
process provenance receipt that the verifier recomputes from.

For a ready package, process provenance binds the declared command, script,
config, stdout/stderr logs, and runtime event hash. It does not prove the
runtime was a genuine physics run rather than replay or fabrication.

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
