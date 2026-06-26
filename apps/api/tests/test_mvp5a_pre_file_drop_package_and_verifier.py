from __future__ import annotations

import json
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import csv
from typing import Any, cast

import h5py  # type: ignore[import-untyped]
import pytest

from app.services.mvp5a_file_drop_rehearsal import (
    PACKAGE_NAME,
    PROFILE_IDS,
    RUNTIME_BACKED_SOURCE_KIND,
    RUNTIME_CAPTURE_PROVENANCE_SCHEMA_VERSION,
    RUNTIME_CAPTURE_SCHEMA_VERSION,
    RUNTIME_EVENT_HELPER_EVIDENCE_ORIGIN,
    RUNTIME_EVENT_HELPER_PRODUCER_KIND,
    RUNTIME_EVENT_HELPER_SCRIPT_ID,
    RUNTIME_EVENT_HELPER_SOURCE_FUNCTION,
    STATUS_CONTRACT_READY,
    STATUS_READY,
    _assert_managed_package_dir,
    build_fixture_canonical_trace,
    build_rehearsal_package,
    write_runtime_evidence,
)


ROOT = Path(__file__).resolve().parents[3]
VERIFIER = ROOT / "scripts" / "verify_mvp5a_pre_file_drop_chaos_rehearsal_package.py"
RUNNER = ROOT / "scripts" / "run_mvp5a_pre_file_drop_chaos_rehearsal.py"
_SPEC = importlib.util.spec_from_file_location("verify_mvp5a_pre_file_drop_chaos_rehearsal_package", VERIFIER)
assert _SPEC is not None and _SPEC.loader is not None
_VERIFIER_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_VERIFIER_MODULE)
verify_package = _VERIFIER_MODULE.verify_package
VERIFIER_FORBIDDEN_CLAIMS = cast(set[str], _VERIFIER_MODULE.FORBIDDEN_CLAIMS)
VERIFIER_FORBIDDEN_POSITIVE_PHRASES = cast(tuple[str, ...], _VERIFIER_MODULE.FORBIDDEN_POSITIVE_PHRASES)
CAPTURE_EDGE_READY_CLOSE_DISABLED_ISSUE = cast(str, _VERIFIER_MODULE.CAPTURE_EDGE_READY_CLOSE_DISABLED_ISSUE)

RAW_RUNTIME_EVENT_SCHEMA_VERSION = "rdf_mvp5a_pre_raw_runtime_event_v0.1.0"
RUNTIME_EVENT_MANIFEST_SCHEMA_VERSION = "rdf_mvp5a_pre_runtime_event_manifest_v0.1.0"
RUNTIME_RECONSTRUCTION_RECEIPT_SCHEMA_VERSION = "rdf_mvp5a_pre_runtime_reconstruction_receipt_v0.1.0"
PROCESS_PROVENANCE_RECEIPT_SCHEMA_VERSION = "rdf_mvp5a_pre_process_provenance_receipt_v0.1.0"
RUNTIME_RECONSTRUCTION_ALGORITHM = "rdf_mvp5a_pre_runtime_events_to_canonical_trace_v0.1.0"
RUNTIME_EVENT_REQUIRED_CHANNELS = (
    "phase_marker",
    "ur_joint_state",
    "ur_tcp_state",
    "franka_joint_state",
    "franka_eef_state",
    "generic_command_state",
)
UR_JOINT_NAMES = (
    "shoulder_pan_joint",
    "shoulder_lift_joint",
    "elbow_joint",
    "wrist_1_joint",
    "wrist_2_joint",
    "wrist_3_joint",
)
FRANKA_JOINT_NAMES = (
    "panda_joint1",
    "panda_joint2",
    "panda_joint3",
    "panda_joint4",
    "panda_joint5",
    "panda_joint6",
    "panda_joint7",
)


def _runtime_capture_payload(trace: dict) -> dict:
    return {
        "schema_version": RUNTIME_CAPTURE_SCHEMA_VERSION,
        "captured_at": "2026-06-25T00:00:00Z",
        "runtime_provenance": {
            "schema_version": RUNTIME_CAPTURE_PROVENANCE_SCHEMA_VERSION,
            "runtime_backend": "isaac_sim",
            "capture_script_id": "mvp5a_pre_isaac_sim_canonical_trace_capture_v0",
            "capture_command": "python scripts/capture_mvp5a_pre_isaac_sim_canonical_trace.py --frames 12",
            "isaac_sim_version": "runtime-attested-test-fixture",
            "source_process_receipt": {
                "process_kind": "isaac_sim_process",
                "capture_id": "mvp5a-pre-runtime-attested-test-fixture",
            },
        },
        "mvp5a_canonical_trace": trace,
    }


def _runtime_backed_trace() -> dict:
    trace = json.loads(json.dumps(build_fixture_canonical_trace()))
    for frame in trace["frames"]:
        index = frame["frame_index"]
        delta = round(0.0007 * (index + 1), 6)
        frame["ur"]["actual_q"][0] = round(frame["ur"]["actual_q"][0] + delta, 6)
        frame["ur"]["target_q"][0] = round(frame["ur"]["target_q"][0] + delta, 6)
        frame["ur"]["actual_TCP_pose"][0] = round(frame["ur"]["actual_TCP_pose"][0] + delta, 6)
        frame["ur"]["target_TCP_pose"][0] = round(frame["ur"]["target_TCP_pose"][0] + delta, 6)
        frame["franka"]["q"][0] = round(frame["franka"]["q"][0] + delta, 6)
        frame["franka"]["q_d"][0] = round(frame["franka"]["q_d"][0] + delta, 6)
        frame["franka"]["O_T_EE"][3] = round(frame["franka"]["O_T_EE"][3] + delta, 6)
        frame["franka"]["O_T_EE_d"][3] = round(frame["franka"]["O_T_EE_d"][3] + delta, 6)
        frame["generic"]["state"][0] = round(frame["generic"]["state"][0] + delta, 6)
        frame["generic"]["command"][0] = round(frame["generic"]["command"][0] + delta, 6)
    trace.update(
        {
            "trace_id": "mvp5a_pre_runtime_attested_test_trace_v0",
            "source_kind": RUNTIME_BACKED_SOURCE_KIND,
            "runtime_backed": True,
        }
    )
    return trace


def _runtime_labelled_fixture_trace_for_test() -> dict:
    trace = json.loads(json.dumps(build_fixture_canonical_trace()))
    trace.update(
        {
            "trace_id": "mvp5a_pre_runtime_labelled_fixture_trace_v0",
            "source_kind": RUNTIME_BACKED_SOURCE_KIND,
            "runtime_backed": True,
        }
    )
    return trace


def _runtime_events_from_canonical_for_test(trace: dict, *, capture_id: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    event_index = 0
    for frame in trace["frames"]:
        frame_index = int(frame["frame_index"])
        timestamp = float(frame["timestamp"])
        common = {
            "schema_version": RAW_RUNTIME_EVENT_SCHEMA_VERSION,
            "capture_id": capture_id,
            "frame_index": frame_index,
            "timestamp": timestamp,
            "source_backend": "isaac_sim",
            "source_process_kind": "isaac_sim_process",
        }
        channel_payloads = (
            (
                "phase_marker",
                {
                    "phase": frame["phase"],
                },
                {},
            ),
            (
                "ur_joint_state",
                {
                    "joint_names": list(UR_JOINT_NAMES),
                    "actual_q": frame["ur"]["actual_q"],
                    "target_q": frame["ur"]["target_q"],
                    "robot_mode": frame["ur"]["robot_mode"],
                    "safety_status": frame["ur"]["safety_status"],
                },
                {"joint_position": "rad"},
            ),
            (
                "ur_tcp_state",
                {
                    "actual_TCP_pose": frame["ur"]["actual_TCP_pose"],
                    "target_TCP_pose": frame["ur"]["target_TCP_pose"],
                    "actual_TCP_speed": frame["ur"]["actual_TCP_speed"],
                },
                {"tcp_position": "m", "tcp_rotation": "rotation_vector_rad", "tcp_speed": "m_per_s"},
            ),
            (
                "franka_joint_state",
                {
                    "joint_names": list(FRANKA_JOINT_NAMES),
                    "q": frame["franka"]["q"],
                    "q_d": frame["franka"]["q_d"],
                    "robot_mode": frame["franka"]["robot_mode"],
                },
                {"joint_position": "rad"},
            ),
            (
                "franka_eef_state",
                {
                    "O_T_EE": frame["franka"]["O_T_EE"],
                    "O_T_EE_d": frame["franka"]["O_T_EE_d"],
                },
                {"pose_matrix": "homogeneous_transform_row_major_m"},
            ),
            (
                "generic_command_state",
                {
                    "state": frame["generic"]["state"],
                    "command": frame["generic"]["command"],
                    "command_timestamp": frame["generic"]["command_timestamp"],
                    "state_timestamp": frame["generic"]["state_timestamp"],
                    "action_semantics": "commanded_target_state",
                    "state_semantics": "actual_robot_state",
                },
                {"state": "profile_native", "command": "profile_native"},
            ),
        )
        for channel, payload, units in channel_payloads:
            events.append({**common, "event_index": event_index, "channel": channel, "units": units, "payload": payload})
            event_index += 1
    return events


def _write_runtime_event_jsonl(path: Path, events: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for event in events
        ),
        encoding="utf-8",
    )


def _promote_package_with_l2_runtime_events_for_test(package_dir: Path, trace: dict) -> None:
    capture_id = "mvp5a-pre-l2-runtime-event-test-fixture"
    canonical = json.loads(json.dumps(trace))
    canonical.update(
        {
            "trace_id": "mvp5a_pre_l2_runtime_event_test_trace_v0",
            "source_kind": RUNTIME_BACKED_SOURCE_KIND,
            "runtime_backed": True,
        }
    )
    canonical_path = package_dir / "data" / "canonical_trace" / "canonical_trace.json"
    _write_json(canonical_path, canonical)

    runtime_dir = package_dir / "data" / "runtime_evidence"
    event_log_path = runtime_dir / "runtime_event_log.jsonl"
    events = _runtime_events_from_canonical_for_test(canonical, capture_id=capture_id)
    _write_runtime_event_jsonl(event_log_path, events)
    event_log_sha = _sha256(event_log_path)
    canonical["runtime_event_log_sha256"] = event_log_sha
    _write_json(canonical_path, canonical)
    canonical_sha = _sha256(canonical_path)

    _write_json(
        runtime_dir / "runtime_event_manifest.json",
        {
            "schema_version": RUNTIME_EVENT_MANIFEST_SCHEMA_VERSION,
            "evidence_level": "L2_verifier_owned_raw_runtime_events",
            "capture_id": capture_id,
            "source_backend": "isaac_sim",
            "capture_script_id": "mvp5a_pre_isaac_sim_raw_runtime_event_capture_v0",
            "source_process_kind": "isaac_sim_process",
            "runtime_event_log_path": "data/runtime_evidence/runtime_event_log.jsonl",
            "runtime_event_log_sha256": event_log_sha,
            "frame_count": canonical["frame_count"],
            "event_count": len(events),
            "required_channels": list(RUNTIME_EVENT_REQUIRED_CHANNELS),
            "generated_by_rdf_sim": True,
            "external_partner_data": False,
            "non_claims": dict(canonical["non_claims"]),
        },
    )
    _write_json(
        runtime_dir / "runtime_reconstruction_receipt.json",
        {
            "schema_version": RUNTIME_RECONSTRUCTION_RECEIPT_SCHEMA_VERSION,
            "reconstruction_algorithm": RUNTIME_RECONSTRUCTION_ALGORITHM,
            "runtime_event_log_sha256": event_log_sha,
            "reconstructed_canonical_trace_sha256": canonical_sha,
            "included_canonical_trace_sha256": canonical_sha,
            "matches_included_canonical_trace": True,
            "runtime_capture_sufficient": True,
            "ready_status_allowed": True,
            "frame_count": canonical["frame_count"],
            "required_channels": list(RUNTIME_EVENT_REQUIRED_CHANNELS),
        },
    )

    preflight = _json(package_dir / "data" / "canonical_trace" / "runtime_capture_preflight.json")
    preflight.update(
        {
            "runtime_capture_supplied": False,
            "runtime_capture_sufficient": True,
            "fresh_runtime_capture_required": False,
            "blocked_reason": None,
            "issues": [],
            "observed_min_source_log_rows_emitted": canonical["frame_count"],
            "runtime_event_log_sha256": event_log_sha,
        }
    )
    _write_json(package_dir / "data" / "canonical_trace" / "runtime_capture_preflight.json", preflight)

    receipt = _json(package_dir / "data" / "canonical_trace" / "runtime_capture_hash_receipt.json")
    receipt.update(
        {
            "canonical_trace_sha256": canonical_sha,
            "runtime_capture_supplied": False,
            "runtime_capture_sufficient": True,
            "runtime_capture_sha256": None,
            "ready_status_allowed": True,
            "blocked_reason": None,
            "runtime_event_log_sha256": event_log_sha,
        }
    )
    _write_json(package_dir / "data" / "canonical_trace" / "runtime_capture_hash_receipt.json", receipt)

    config = _json(package_dir / "data" / "config.json")
    config.update(
        {
            "status": STATUS_READY,
            "file_drop_rehearsal_ready": True,
            "runtime_capture_sufficient": True,
            "blocked_reason": None,
            "fresh_runtime_capture_required": False,
            "runtime_evidence_level": "L2_verifier_owned_raw_runtime_events",
            "runtime_event_log_sha256": event_log_sha,
        }
    )
    _write_json(package_dir / "data" / "config.json", config)

    manifest = _json(package_dir / "package_manifest.json")
    manifest["package_status"] = STATUS_READY
    manifest["file_drop_rehearsal_ready"] = True
    manifest["runtime_evidence_level"] = "L2_verifier_owned_raw_runtime_events"
    manifest["runtime_event_log_sha256"] = event_log_sha
    _write_json(package_dir / "package_manifest.json", manifest)
    _refresh_indexes(package_dir)


def _runtime_events_from_package_for_test(package_dir: Path) -> list[dict[str, Any]]:
    event_log_path = package_dir / "data" / "runtime_evidence" / "runtime_event_log.jsonl"
    return [json.loads(line) for line in event_log_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_runtime_events_and_refresh_for_test(package_dir: Path, events: list[dict[str, Any]]) -> None:
    event_log_path = package_dir / "data" / "runtime_evidence" / "runtime_event_log.jsonl"
    _write_runtime_event_jsonl(event_log_path, events)
    event_log_sha = _sha256(event_log_path)
    frame_count = len({event.get("frame_index") for event in events if isinstance(event.get("frame_index"), int)})
    manifest = _json(package_dir / "data" / "runtime_evidence" / "runtime_event_manifest.json")
    manifest.update(
        {
            "runtime_event_log_sha256": event_log_sha,
            "frame_count": frame_count,
            "event_count": len(events),
        }
    )
    _write_json(package_dir / "data" / "runtime_evidence" / "runtime_event_manifest.json", manifest)
    receipt = _json(package_dir / "data" / "runtime_evidence" / "runtime_reconstruction_receipt.json")
    receipt["runtime_event_log_sha256"] = event_log_sha
    _write_json(package_dir / "data" / "runtime_evidence" / "runtime_reconstruction_receipt.json", receipt)
    config = _json(package_dir / "data" / "config.json")
    config["runtime_event_log_sha256"] = event_log_sha
    _write_json(package_dir / "data" / "config.json", config)
    package_manifest = _json(package_dir / "package_manifest.json")
    package_manifest["runtime_event_log_sha256"] = event_log_sha
    _write_json(package_dir / "package_manifest.json", package_manifest)
    _refresh_indexes(package_dir)


def _refresh_canonical_hash_receipts_for_test(package_dir: Path) -> None:
    canonical_sha = _sha256(package_dir / "data" / "canonical_trace" / "canonical_trace.json")
    receipt = _json(package_dir / "data" / "canonical_trace" / "runtime_capture_hash_receipt.json")
    receipt["canonical_trace_sha256"] = canonical_sha
    _write_json(package_dir / "data" / "canonical_trace" / "runtime_capture_hash_receipt.json", receipt)
    runtime_receipt = _json(package_dir / "data" / "runtime_evidence" / "runtime_reconstruction_receipt.json")
    runtime_receipt["included_canonical_trace_sha256"] = canonical_sha
    runtime_receipt["reconstructed_canonical_trace_sha256"] = canonical_sha
    runtime_receipt["matches_included_canonical_trace"] = True
    _write_json(package_dir / "data" / "runtime_evidence" / "runtime_reconstruction_receipt.json", runtime_receipt)
    _refresh_indexes(package_dir)


def _mutate_runtime_events_for_test(package_dir: Path, mutation: str) -> None:
    events = _runtime_events_from_package_for_test(package_dir)
    if mutation == "event_index_gap":
        events[1]["event_index"] = 99
    elif mutation == "frame_index_gap":
        for event in events:
            if event["frame_index"] == 1:
                event["frame_index"] = 99
    elif mutation == "duplicate_channel":
        events[1]["channel"] = events[0]["channel"]
    elif mutation == "unknown_channel":
        events[0]["channel"] = "mystery_runtime_channel"
    elif mutation == "nan_payload":
        events[0]["payload"]["bad_value"] = float("nan")
    elif mutation == "ur_joint_order_swapped":
        event = next(event for event in events if event["channel"] == "ur_joint_state")
        event["payload"]["joint_names"] = list(reversed(event["payload"]["joint_names"]))
    elif mutation == "ur_degrees_unit":
        event = next(event for event in events if event["channel"] == "ur_joint_state")
        event["units"]["joint_position"] = "deg"
    elif mutation == "ur_tcp_mm_unit":
        event = next(event for event in events if event["channel"] == "ur_tcp_state")
        event["units"]["tcp_position"] = "mm"
    elif mutation == "ur_not_running":
        event = next(event for event in events if event["channel"] == "ur_joint_state")
        event["payload"]["robot_mode"] = "STOPPED"
    elif mutation == "ur_protective_stop":
        event = next(event for event in events if event["channel"] == "ur_joint_state")
        event["payload"]["safety_status"] = "PROTECTIVE_STOP"
    elif mutation == "franka_wrong_dof":
        event = next(event for event in events if event["channel"] == "franka_joint_state")
        event["payload"]["q"] = event["payload"]["q"][:-1]
    elif mutation == "franka_eef_wrong_length":
        event = next(event for event in events if event["channel"] == "franka_eef_state")
        event["payload"]["O_T_EE"] = event["payload"]["O_T_EE"][:-1]
    elif mutation == "generic_lag_high":
        event = next(event for event in events if event["channel"] == "generic_command_state")
        event["payload"]["command_timestamp"] = round(float(event["payload"]["state_timestamp"]) + 1.0, 6)
    elif mutation == "generic_state_only":
        event = next(event for event in events if event["channel"] == "generic_command_state")
        event["payload"].pop("action_semantics")
        event["payload"].pop("command")
    elif mutation == "phase_unknown":
        event = next(event for event in events if event["channel"] == "phase_marker")
        event["payload"]["phase"] = "teleport"
    else:
        raise AssertionError(f"unknown runtime event mutation: {mutation}")
    _write_runtime_events_and_refresh_for_test(package_dir, events)


@pytest.fixture(scope="session")
def fixture_package(tmp_path_factory: pytest.TempPathFactory) -> Path:
    package_dir = tmp_path_factory.mktemp(PACKAGE_NAME)
    build_rehearsal_package(package_dir=package_dir, fixture_only=True, clean=True)
    return package_dir


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _float32_array_hash(rows: list[list[float]]) -> str:
    import hashlib
    import struct

    return hashlib.sha256(
        b"".join(struct.pack("<f", float(value)) for row in rows for value in row)
    ).hexdigest()


def _float64_array_hash(values: list[float]) -> str:
    import hashlib
    import struct

    return hashlib.sha256(b"".join(struct.pack("<d", float(value)) for value in values)).hexdigest()


def _artifact_entry(package_dir: Path, path: Path) -> dict:
    return {
        "data_path": path.relative_to(package_dir).as_posix(),
        "file_sha256": _sha256(path),
        "byte_size": path.stat().st_size,
        "hash_convention": "file_bytes",
    }


def _refresh_indexes(package_dir: Path) -> None:
    data_dir = package_dir / "data"
    data_entries = [
        _artifact_entry(package_dir, path)
        for path in sorted(data_dir.rglob("*"))
        if path.is_file() and path.name != "artifact_index.json"
    ]
    _write_json(
        data_dir / "artifact_index.json",
        {"schema_version": "rdf_mvp5a_pre_artifact_index_v0.1.0", "artifact_index": data_entries},
    )
    manifest = _json(package_dir / "package_manifest.json")
    manifest["artifact_index"] = [
        _artifact_entry(package_dir, path)
        for path in sorted(data_dir.rglob("*"))
        if path.is_file()
    ]
    _write_json(package_dir / "package_manifest.json", manifest)


def _write_hash_consistent_forged_process_provenance_for_test(package_dir: Path) -> None:
    provenance_dir = package_dir / "data" / "process_provenance"
    provenance_dir.mkdir(parents=True, exist_ok=True)
    script_path = provenance_dir / "fake_capture_edge_emitter.py"
    config_path = provenance_dir / "fake_capture_config.json"
    stdout_path = provenance_dir / "fake_capture_stdout.log"
    stderr_path = provenance_dir / "fake_capture_stderr.log"
    script_path.write_text("# forged capture-edge emitter placeholder\n", encoding="utf-8")
    _write_json(config_path, {"profile": "forged_capture_edge", "fixture": True})
    stdout_path.write_text("forged capture completed\n", encoding="utf-8")
    stderr_path.write_text("", encoding="utf-8")
    _write_json(
        provenance_dir / "process_provenance_receipt.json",
        {
            "schema_version": PROCESS_PROVENANCE_RECEIPT_SCHEMA_VERSION,
            "capture_script_id": "mvp5a_pre_isaac_sim_raw_runtime_event_capture_v0",
            "source_backend": "isaac_sim",
            "source_process_kind": "isaac_sim_process",
            "runtime_event_log_path": "data/runtime_evidence/runtime_event_log.jsonl",
            "runtime_event_log_sha256": _sha256(package_dir / "data" / "runtime_evidence" / "runtime_event_log.jsonl"),
            "exit_code": 0,
            "git_commit": "forged-hash-consistent-test-commit",
            "command": "python data/process_provenance/fake_capture_edge_emitter.py",
            "python_version": "3.11.0",
            "os_summary": "linux-test-fixture",
            "started_at": "2026-06-26T00:00:00Z",
            "ended_at": "2026-06-26T00:00:01Z",
            "script_path": "data/process_provenance/fake_capture_edge_emitter.py",
            "script_sha256": _sha256(script_path),
            "config_path": "data/process_provenance/fake_capture_config.json",
            "config_sha256": _sha256(config_path),
            "stdout_log_path": "data/process_provenance/fake_capture_stdout.log",
            "stdout_log_sha256": _sha256(stdout_path),
            "stderr_log_path": "data/process_provenance/fake_capture_stderr.log",
            "stderr_log_sha256": _sha256(stderr_path),
        },
    )


def _copy_package(base: Path, tmp_path: Path) -> Path:
    target = tmp_path / PACKAGE_NAME
    shutil.copytree(base, target)
    return target


def _source_hashes(source_dir: Path) -> dict[str, dict[str, int | str]]:
    return {
        path.relative_to(source_dir).as_posix(): {"sha256": _sha256(path), "byte_size": path.stat().st_size}
        for path in sorted(source_dir.rglob("*"))
        if path.is_file()
    }


def _refresh_cached_golden_source_hash(package_dir: Path, profile_id: str) -> None:
    golden_path = package_dir / "data" / "ingest_results" / "golden_results.json"
    payload = _json(golden_path)
    for row in payload["results"]:
        if row["profile_id"] == profile_id:
            row["source_file_hashes"] = _source_hashes(package_dir / "data" / "source_drops" / "golden" / profile_id)
    _write_json(golden_path, payload)


def _write_generic_source_rows(package_dir: Path, rows: list[dict]) -> None:
    source_path = package_dir / "data" / "source_drops" / "golden" / "generic_command_state_jsonl_v0" / "command_state.jsonl"
    lines = []
    for row in rows:
        timestamp = float(row["timestamp"])
        lines.append(
            json.dumps(
                {
                    "timestamp": timestamp,
                    "command_timestamp": max(timestamp - 0.01, 0.0),
                    "state_timestamp": timestamp,
                    "command": row["action_vector"],
                    "state": row["state_vector"],
                    "action_semantics": "explicit_command_vector",
                    "state_semantics": "explicit_state_vector",
                    "reset_boundary": False,
                    "task_success": None,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    source_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_fixture_package_is_contract_ready_but_not_ready(fixture_package: Path) -> None:
    config = _json(fixture_package / "data" / "config.json")
    coverage = _json(fixture_package / "data" / "ingest_results" / "rejection_reason_coverage.json")
    golden = _json(fixture_package / "data" / "ingest_results" / "golden_results.json")
    corrupt = _json(fixture_package / "data" / "ingest_results" / "corruption_matrix_results.json")

    assert config["status"] == STATUS_CONTRACT_READY
    assert config["file_drop_rehearsal_contract_ready"] is True
    assert config["file_drop_rehearsal_ready"] is False
    assert config["external_partner_data"] is False
    assert config["external_data_evaluated"] is False
    assert len(golden["results"]) == len(PROFILE_IDS)
    assert all(row["passed"] is True and row["export_eligible"] is True for row in golden["results"])
    assert len(corrupt["results"]) >= 50
    assert all(row["passed"] is False and row["export_eligible"] is False for row in corrupt["results"])
    assert coverage["silent_pass_rate"] == 0.0
    assert coverage["structured_rejection_reason_coverage"] is True


def test_fixture_package_verifies_only_with_explicit_contract_ready_flag(fixture_package: Path) -> None:
    manifest = fixture_package / "package_manifest.json"

    assert verify_package(manifest, allow_contract_ready=True, deep_hdf5=True)["ok"] is True
    blocked = verify_package(manifest, allow_contract_ready=False)

    assert blocked["ok"] is False
    assert "contract-ready package requires --allow-contract-ready" in blocked["issues"]
    assert "hdf5 payload verification requires --deep-hdf5" in blocked["issues"]


def test_verifier_script_requires_deep_hdf5_for_final_verified_package(fixture_package: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(VERIFIER), str(fixture_package / "package_manifest.json"), "--allow-contract-ready"],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode != 0
    assert "VERDICT: FAILED" in result.stdout
    assert "hdf5 payload verification requires --deep-hdf5" in result.stdout


def test_verifier_script_deep_hdf5_path_verifies(fixture_package: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(VERIFIER), str(fixture_package / "package_manifest.json"), "--allow-contract-ready", "--deep-hdf5"],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "VERDICT: VERIFIED" in result.stdout


def test_runner_help_does_not_advertise_runtime_ready_promotion() -> None:
    help_result = subprocess.run(
        [sys.executable, str(RUNNER), "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    help_text = " ".join(help_result.stdout.lower().split())
    source_text = RUNNER.read_text(encoding="utf-8").lower()
    forbidden_phrases = (
        "promotes the package to ready",
        "promote the package to ready",
        "file_drop_rehearsal_ready=true",
    )
    for phrase in forbidden_phrases:
        assert phrase not in help_text
        assert phrase not in source_text
    assert "diagnostics only" in help_text
    assert "file_drop_rehearsal_ready=false" in help_text


def test_spec_forbidden_claim_list_matches_verifier_contract() -> None:
    spec_text = (
        ROOT
        / "docs"
        / "superpowers"
        / "specs"
        / "2026-06-25-mvp5a-pre-digital-twin-file-drop-chaos-rehearsal-design.md"
    ).read_text(encoding="utf-8")
    forbidden_section = spec_text.split("Forbidden claims:", 1)[1]
    fenced_block = forbidden_section.split("```text", 1)[1].split("```", 1)[0]
    spec_claims = {line.strip() for line in fenced_block.splitlines() if line.strip()}

    assert spec_claims == VERIFIER_FORBIDDEN_CLAIMS


def test_planning_docs_do_not_claim_isaac_sim_backed_rehearsal() -> None:
    checked_paths = (
        ROOT
        / "docs"
        / "superpowers"
        / "specs"
        / "2026-06-25-mvp5a-pre-digital-twin-file-drop-chaos-rehearsal-design.md",
        ROOT / "docs" / "proof" / PACKAGE_NAME / "README.md",
        RUNNER,
    )
    forbidden_phrases = (
        "isaac-sim-backed",
        "isaac sim backed",
        "isaac-backed",
        "isaac sim based",
        "isaac sim 기반",
    )
    for path in checked_paths:
        text = path.read_text(encoding="utf-8").lower()
        for phrase in forbidden_phrases:
            assert phrase not in text, f"{path}: {phrase}"
    spec_text = checked_paths[0].read_text(encoding="utf-8").lower()
    assert "future verifier-owned raw runtime contract required" in spec_text


def test_verifier_source_has_no_producer_imports_or_top_level_heavy_imports() -> None:
    source = VERIFIER.read_text(encoding="utf-8")
    before_deep_hdf5 = source.split("def _verify_deep_hdf5", maxsplit=1)[0]

    assert "from app." not in source
    assert "import app" not in source
    assert "import h5py" not in before_deep_hdf5
    assert "import numpy" not in before_deep_hdf5


def test_runtime_shaped_capture_stays_contract_ready_without_verifier_owned_runtime_evidence(tmp_path: Path) -> None:
    capture = tmp_path / "runtime_capture.json"
    _write_json(capture, _runtime_capture_payload(_runtime_backed_trace()))
    package_dir = tmp_path / f"{PACKAGE_NAME}_runtime_shaped_contract_ready"

    result = build_rehearsal_package(package_dir=package_dir, runtime_capture=capture, fixture_only=False, clean=True)
    preflight = _json(package_dir / "data" / "canonical_trace" / "runtime_capture_preflight.json")
    receipt = _json(package_dir / "data" / "canonical_trace" / "runtime_capture_hash_receipt.json")
    verification = verify_package(package_dir / "package_manifest.json", allow_contract_ready=True, deep_hdf5=True)
    strict_verification = verify_package(package_dir / "package_manifest.json", allow_contract_ready=False, deep_hdf5=True)

    assert result["status"] == STATUS_CONTRACT_READY
    assert result["file_drop_rehearsal_ready"] is False
    assert preflight["runtime_capture_structurally_valid"] is True
    assert preflight["runtime_capture_sufficient"] is False
    assert "runtime_capture_unverified_source_process" in preflight["issues"]
    assert receipt["ready_status_allowed"] is False
    assert verification["ok"] is True, verification["issues"]
    assert strict_verification["ok"] is False
    assert "contract-ready package requires --allow-contract-ready" in strict_verification["issues"]


def test_write_runtime_evidence_marks_canonical_projection_helper_non_closing(tmp_path: Path) -> None:
    package_dir = tmp_path / f"{PACKAGE_NAME}_helper_projection_non_closing"
    trace = build_fixture_canonical_trace()

    build_rehearsal_package(package_dir=package_dir, fixture_only=True, clean=True)
    result = write_runtime_evidence(package_dir, trace)
    manifest = _json(package_dir / "data" / "runtime_evidence" / "runtime_event_manifest.json")
    receipt = _json(package_dir / "data" / "runtime_evidence" / "runtime_reconstruction_receipt.json")

    assert result["event_count"] == trace["frame_count"] * len(RUNTIME_EVENT_REQUIRED_CHANNELS)
    assert manifest["capture_script_id"] == RUNTIME_EVENT_HELPER_SCRIPT_ID
    assert manifest["evidence_origin"] == RUNTIME_EVENT_HELPER_EVIDENCE_ORIGIN
    assert manifest["producer_kind"] == RUNTIME_EVENT_HELPER_PRODUCER_KIND
    assert manifest["helper_source_function"] == RUNTIME_EVENT_HELPER_SOURCE_FUNCTION
    assert manifest["closing_evidence"] is False
    assert receipt["runtime_capture_sufficient"] is False
    assert receipt["ready_status_allowed"] is False
    assert receipt["blocked_reason"] == "helper_derived_runtime_events_are_consistency_evidence_only"


def test_runtime_shaped_capture_cannot_mint_ready_after_summary_tamper(tmp_path: Path) -> None:
    trace = _runtime_backed_trace()
    capture = tmp_path / "runtime_capture.json"
    _write_json(capture, _runtime_capture_payload(trace))
    package_dir = tmp_path / f"{PACKAGE_NAME}_runtime_shaped_ready_tamper"

    build_rehearsal_package(package_dir=package_dir, runtime_capture=capture, fixture_only=False, clean=True)

    capture_sha = _sha256(package_dir / "data" / "canonical_trace" / "runtime_capture.json")
    canonical = {**trace, "runtime_capture_sha256": capture_sha}
    _write_json(package_dir / "data" / "canonical_trace" / "canonical_trace.json", canonical)
    preflight = _json(package_dir / "data" / "canonical_trace" / "runtime_capture_preflight.json")
    preflight.update(
        {
            "runtime_capture_sufficient": True,
            "runtime_capture_structurally_valid": True,
            "fresh_runtime_capture_required": False,
            "blocked_reason": None,
            "issues": [],
            "runtime_capture_sha256": capture_sha,
        }
    )
    _write_json(package_dir / "data" / "canonical_trace" / "runtime_capture_preflight.json", preflight)
    receipt = _json(package_dir / "data" / "canonical_trace" / "runtime_capture_hash_receipt.json")
    receipt.update(
        {
            "canonical_trace_sha256": _sha256(package_dir / "data" / "canonical_trace" / "canonical_trace.json"),
            "runtime_capture_supplied": True,
            "runtime_capture_sufficient": True,
            "runtime_capture_structurally_valid": True,
            "runtime_capture_sha256": capture_sha,
            "ready_status_allowed": True,
            "blocked_reason": None,
        }
    )
    _write_json(package_dir / "data" / "canonical_trace" / "runtime_capture_hash_receipt.json", receipt)
    config = _json(package_dir / "data" / "config.json")
    config.update(
        {
            "status": STATUS_READY,
            "file_drop_rehearsal_ready": True,
            "runtime_capture_sufficient": True,
            "blocked_reason": None,
            "fresh_runtime_capture_required": False,
        }
    )
    _write_json(package_dir / "data" / "config.json", config)
    manifest = _json(package_dir / "package_manifest.json")
    manifest["package_status"] = STATUS_READY
    manifest["file_drop_rehearsal_ready"] = True
    _write_json(package_dir / "package_manifest.json", manifest)
    _refresh_indexes(package_dir)

    verification = verify_package(package_dir / "package_manifest.json", allow_contract_ready=False, deep_hdf5=True)

    assert verification["ok"] is False
    assert "ready status requires data/runtime_evidence/runtime_event_log.jsonl" in verification["issues"]


def test_fixture_canonical_trace_inside_runtime_capture_stays_contract_ready(tmp_path: Path) -> None:
    capture = tmp_path / "runtime_capture.json"
    _write_json(capture, _runtime_capture_payload(build_fixture_canonical_trace()))
    package_dir = tmp_path / f"{PACKAGE_NAME}_fixture_capture"

    result = build_rehearsal_package(package_dir=package_dir, runtime_capture=capture, fixture_only=False, clean=True)
    preflight = _json(package_dir / "data" / "canonical_trace" / "runtime_capture_preflight.json")

    assert result["status"] == STATUS_CONTRACT_READY
    assert result["file_drop_rehearsal_ready"] is False
    assert preflight["runtime_capture_sufficient"] is False
    assert "runtime_capture_not_runtime_backed" in preflight["issues"]


def test_relabelled_fixture_canonical_trace_inside_runtime_capture_stays_contract_ready(tmp_path: Path) -> None:
    relabelled_fixture = build_fixture_canonical_trace()
    relabelled_fixture.update(
        {
            "trace_id": "mvp5a_pre_relabelled_fixture_as_runtime_v0",
            "source_kind": RUNTIME_BACKED_SOURCE_KIND,
            "runtime_backed": True,
        }
    )
    capture = tmp_path / "runtime_capture.json"
    _write_json(capture, _runtime_capture_payload(relabelled_fixture))
    package_dir = tmp_path / f"{PACKAGE_NAME}_relabelled_fixture_capture"

    result = build_rehearsal_package(package_dir=package_dir, runtime_capture=capture, fixture_only=False, clean=True)
    preflight = _json(package_dir / "data" / "canonical_trace" / "runtime_capture_preflight.json")
    verification = verify_package(package_dir / "package_manifest.json", allow_contract_ready=True, deep_hdf5=True)

    assert result["status"] == STATUS_CONTRACT_READY
    assert result["file_drop_rehearsal_ready"] is False
    assert preflight["runtime_capture_sufficient"] is False
    assert "runtime_capture_matches_deterministic_fixture" in preflight["issues"]
    assert verification["ok"] is True, verification["issues"]

    capture_sha = _sha256(package_dir / "data" / "canonical_trace" / "runtime_capture.json")
    canonical = {**relabelled_fixture, "runtime_capture_sha256": capture_sha}
    _write_json(package_dir / "data" / "canonical_trace" / "canonical_trace.json", canonical)
    preflight.update(
        {
            "runtime_capture_sufficient": True,
            "fresh_runtime_capture_required": False,
            "blocked_reason": None,
            "issues": [],
            "runtime_capture_sha256": capture_sha,
        }
    )
    _write_json(package_dir / "data" / "canonical_trace" / "runtime_capture_preflight.json", preflight)
    receipt = _json(package_dir / "data" / "canonical_trace" / "runtime_capture_hash_receipt.json")
    receipt.update(
        {
            "canonical_trace_sha256": _sha256(package_dir / "data" / "canonical_trace" / "canonical_trace.json"),
            "runtime_capture_supplied": True,
            "runtime_capture_sufficient": True,
            "runtime_capture_sha256": capture_sha,
            "ready_status_allowed": True,
            "blocked_reason": None,
        }
    )
    _write_json(package_dir / "data" / "canonical_trace" / "runtime_capture_hash_receipt.json", receipt)
    config = _json(package_dir / "data" / "config.json")
    config.update(
        {
            "status": STATUS_READY,
            "file_drop_rehearsal_ready": True,
            "runtime_capture_sufficient": True,
            "blocked_reason": None,
            "fresh_runtime_capture_required": False,
        }
    )
    _write_json(package_dir / "data" / "config.json", config)
    manifest = _json(package_dir / "package_manifest.json")
    manifest["package_status"] = STATUS_READY
    manifest["file_drop_rehearsal_ready"] = True
    _write_json(package_dir / "package_manifest.json", manifest)
    _refresh_indexes(package_dir)

    minted = verify_package(package_dir / "package_manifest.json", allow_contract_ready=False, deep_hdf5=True)

    assert minted["ok"] is False
    assert "ready status requires data/runtime_evidence/runtime_event_log.jsonl" in minted["issues"]


def test_relabelled_fixture_with_ignored_runtime_fields_stays_contract_ready(tmp_path: Path) -> None:
    relabelled_fixture = build_fixture_canonical_trace()
    relabelled_fixture.update(
        {
            "trace_id": "mvp5a_pre_relabelled_fixture_with_ignored_fields_v0",
            "source_kind": RUNTIME_BACKED_SOURCE_KIND,
            "runtime_backed": True,
        }
    )
    for index, frame in enumerate(relabelled_fixture["frames"]):
        frame["ignored_attestation_noise"] = f"runtime-noise-{index}"
        frame["ur"]["ignored_attestation_noise"] = index
        frame["franka"]["ignored_attestation_noise"] = index
        frame["generic"]["ignored_attestation_noise"] = index

    capture = tmp_path / "runtime_capture.json"
    _write_json(capture, _runtime_capture_payload(relabelled_fixture))
    package_dir = tmp_path / f"{PACKAGE_NAME}_relabelled_fixture_ignored_fields"

    result = build_rehearsal_package(package_dir=package_dir, runtime_capture=capture, fixture_only=False, clean=True)
    preflight = _json(package_dir / "data" / "canonical_trace" / "runtime_capture_preflight.json")
    verification = verify_package(package_dir / "package_manifest.json", allow_contract_ready=True, deep_hdf5=True)

    assert result["status"] == STATUS_CONTRACT_READY
    assert result["file_drop_rehearsal_ready"] is False
    assert preflight["runtime_capture_sufficient"] is False
    assert "runtime_capture_frame_schema_invalid" in preflight["issues"]
    assert "runtime_capture_matches_deterministic_fixture" in preflight["issues"]
    assert verification["ok"] is True, verification["issues"]

    capture_sha = _sha256(package_dir / "data" / "canonical_trace" / "runtime_capture.json")
    canonical = {**relabelled_fixture, "runtime_capture_sha256": capture_sha}
    _write_json(package_dir / "data" / "canonical_trace" / "canonical_trace.json", canonical)
    preflight.update(
        {
            "runtime_capture_sufficient": True,
            "fresh_runtime_capture_required": False,
            "blocked_reason": None,
            "issues": [],
            "runtime_capture_sha256": capture_sha,
        }
    )
    _write_json(package_dir / "data" / "canonical_trace" / "runtime_capture_preflight.json", preflight)
    receipt = _json(package_dir / "data" / "canonical_trace" / "runtime_capture_hash_receipt.json")
    receipt.update(
        {
            "canonical_trace_sha256": _sha256(package_dir / "data" / "canonical_trace" / "canonical_trace.json"),
            "runtime_capture_supplied": True,
            "runtime_capture_sufficient": True,
            "runtime_capture_sha256": capture_sha,
            "ready_status_allowed": True,
            "blocked_reason": None,
        }
    )
    _write_json(package_dir / "data" / "canonical_trace" / "runtime_capture_hash_receipt.json", receipt)
    config = _json(package_dir / "data" / "config.json")
    config.update(
        {
            "status": STATUS_READY,
            "file_drop_rehearsal_ready": True,
            "runtime_capture_sufficient": True,
            "blocked_reason": None,
            "fresh_runtime_capture_required": False,
        }
    )
    _write_json(package_dir / "data" / "config.json", config)
    manifest = _json(package_dir / "package_manifest.json")
    manifest["package_status"] = STATUS_READY
    manifest["file_drop_rehearsal_ready"] = True
    _write_json(package_dir / "package_manifest.json", manifest)
    _refresh_indexes(package_dir)

    minted = verify_package(package_dir / "package_manifest.json", allow_contract_ready=False, deep_hdf5=True)

    assert minted["ok"] is False
    assert "ready status requires data/runtime_evidence/runtime_event_log.jsonl" in minted["issues"]
    assert "canonical trace schema invalid: runtime_capture_frame_schema_invalid" in minted["issues"]


def test_runtime_capture_missing_runtime_provenance_stays_contract_ready(tmp_path: Path) -> None:
    capture = tmp_path / "runtime_capture.json"
    payload = _runtime_capture_payload(_runtime_backed_trace())
    payload.pop("runtime_provenance")
    _write_json(capture, payload)
    package_dir = tmp_path / f"{PACKAGE_NAME}_missing_runtime_provenance"

    result = build_rehearsal_package(package_dir=package_dir, runtime_capture=capture, fixture_only=False, clean=True)
    preflight = _json(package_dir / "data" / "canonical_trace" / "runtime_capture_preflight.json")

    assert result["status"] == STATUS_CONTRACT_READY
    assert result["file_drop_rehearsal_ready"] is False
    assert preflight["runtime_capture_sufficient"] is False
    assert "runtime_capture_provenance_missing" in preflight["issues"]


def test_runtime_capture_row_counts_without_canonical_trace_stays_contract_ready(tmp_path: Path) -> None:
    capture = tmp_path / "runtime_capture.json"
    _write_json(
        capture,
        {
            "captured_at": "2026-06-25T00:00:00Z",
            "embodiments": {
                "ur10e": {"preflight": {"source_log_rows_emitted": 12}},
                "franka": {"preflight": {"source_log_rows_emitted": 12}},
            },
        },
    )
    package_dir = tmp_path / f"{PACKAGE_NAME}_row_counts_only"

    result = build_rehearsal_package(package_dir=package_dir, runtime_capture=capture, fixture_only=False, clean=True)
    preflight = _json(package_dir / "data" / "canonical_trace" / "runtime_capture_preflight.json")

    assert result["status"] == STATUS_CONTRACT_READY
    assert result["file_drop_rehearsal_ready"] is False
    assert preflight["runtime_capture_sufficient"] is False
    assert "runtime_capture_canonical_trace_missing" in preflight["issues"]


def test_timestamp_only_runtime_capture_stays_contract_ready(tmp_path: Path) -> None:
    capture = tmp_path / "runtime_capture.json"
    _write_json(
        capture,
        {
            "captured_at": "2026-06-25T00:00:00Z",
            "mvp5a_canonical_trace": {
                "frames": [
                    {"timestamp": round(index * 0.04, 6)}
                    for index in range(12)
                ],
            },
        },
    )
    package_dir = tmp_path / f"{PACKAGE_NAME}_timestamp_only_capture"

    result = build_rehearsal_package(package_dir=package_dir, runtime_capture=capture, fixture_only=False, clean=True)
    preflight = _json(package_dir / "data" / "canonical_trace" / "runtime_capture_preflight.json")

    assert result["status"] == STATUS_CONTRACT_READY
    assert result["file_drop_rehearsal_ready"] is False
    assert preflight["runtime_capture_sufficient"] is False
    assert "runtime_capture_frame_schema_invalid" in preflight["issues"]


def test_helper_derived_l2_runtime_event_package_cannot_mint_ready(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / f"{PACKAGE_NAME}_helper_derived_l2_runtime_event_ready"
    trace = _runtime_labelled_fixture_trace_for_test()

    build_rehearsal_package(package_dir=package_dir, fixture_only=True, clean=True)
    _promote_package_with_l2_runtime_events_for_test(package_dir, trace)
    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=False, deep_hdf5=True)

    assert result["ok"] is False
    assert result["status"] == STATUS_READY
    assert result["file_drop_rehearsal_ready"] is True
    assert "helper-derived runtime evidence cannot open ready status" in result["issues"]


def test_hash_refreshed_helper_derived_capture_edge_relabel_requires_process_provenance(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / f"{PACKAGE_NAME}_helper_derived_capture_edge_relabel"
    trace = _runtime_labelled_fixture_trace_for_test()

    build_rehearsal_package(package_dir=package_dir, fixture_only=True, clean=True)
    _promote_package_with_l2_runtime_events_for_test(package_dir, trace)
    runtime_manifest_path = package_dir / "data" / "runtime_evidence" / "runtime_event_manifest.json"
    runtime_manifest = _json(runtime_manifest_path)
    runtime_manifest.update(
        {
            "evidence_origin": "capture_edge_runtime_event_emitter",
            "producer_kind": "capture_edge_emitter",
            "closing_evidence": True,
        }
    )
    runtime_manifest.pop("helper_source_function", None)
    _write_json(runtime_manifest_path, runtime_manifest)
    _refresh_indexes(package_dir)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=False, deep_hdf5=True)

    assert result["ok"] is False
    assert result["status"] == STATUS_READY
    assert result["file_drop_rehearsal_ready"] is True
    assert "ready status requires data/process_provenance/process_provenance_receipt.json" in result["issues"]


def test_hash_refreshed_helper_derived_capture_edge_relabel_rejects_dummy_process_provenance(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / f"{PACKAGE_NAME}_helper_derived_dummy_process_provenance"
    trace = _runtime_labelled_fixture_trace_for_test()

    build_rehearsal_package(package_dir=package_dir, fixture_only=True, clean=True)
    _promote_package_with_l2_runtime_events_for_test(package_dir, trace)
    runtime_manifest_path = package_dir / "data" / "runtime_evidence" / "runtime_event_manifest.json"
    runtime_manifest = _json(runtime_manifest_path)
    runtime_manifest.update(
        {
            "evidence_origin": "capture_edge_runtime_event_emitter",
            "producer_kind": "capture_edge_emitter",
            "closing_evidence": True,
        }
    )
    runtime_manifest.pop("helper_source_function", None)
    _write_json(runtime_manifest_path, runtime_manifest)
    process_provenance_dir = package_dir / "data" / "process_provenance"
    process_provenance_dir.mkdir(parents=True)
    _write_json(process_provenance_dir / "process_provenance_receipt.json", {"dummy": True})
    _refresh_indexes(package_dir)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=False, deep_hdf5=True)

    assert result["ok"] is False
    assert result["status"] == STATUS_READY
    assert result["file_drop_rehearsal_ready"] is True
    assert "process_provenance_receipt schema_version mismatch" in result["issues"]
    assert "process_provenance_receipt runtime_event_log_sha256 mismatch" in result["issues"]


def test_hash_refreshed_helper_derived_capture_edge_relabel_rejects_hash_consistent_process_provenance(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / f"{PACKAGE_NAME}_helper_derived_hash_consistent_process_provenance"
    trace = _runtime_labelled_fixture_trace_for_test()

    build_rehearsal_package(package_dir=package_dir, fixture_only=True, clean=True)
    _promote_package_with_l2_runtime_events_for_test(package_dir, trace)
    runtime_manifest_path = package_dir / "data" / "runtime_evidence" / "runtime_event_manifest.json"
    runtime_manifest = _json(runtime_manifest_path)
    runtime_manifest.update(
        {
            "evidence_origin": "capture_edge_runtime_event_emitter",
            "producer_kind": "capture_edge_emitter",
            "closing_evidence": True,
        }
    )
    runtime_manifest.pop("helper_source_function", None)
    _write_json(runtime_manifest_path, runtime_manifest)
    _write_hash_consistent_forged_process_provenance_for_test(package_dir)
    _refresh_indexes(package_dir)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=False, deep_hdf5=True)

    assert result["ok"] is False
    assert result["status"] == STATUS_READY
    assert result["file_drop_rehearsal_ready"] is True
    assert CAPTURE_EDGE_READY_CLOSE_DISABLED_ISSUE in result["issues"]


@pytest.mark.parametrize(
    ("mutation", "expected_issue"),
    [
        ("event_index_gap", "runtime event_index not contiguous"),
        ("frame_index_gap", "runtime frame_index not contiguous"),
        ("duplicate_channel", "duplicate runtime event for frame/channel"),
        ("unknown_channel", "unknown runtime event channel"),
        ("nan_payload", "runtime event contains non-finite number"),
    ],
)
def test_runtime_event_global_tamper_fails(tmp_path: Path, mutation: str, expected_issue: str) -> None:
    package_dir = tmp_path / f"{PACKAGE_NAME}_runtime_event_global_{mutation}"
    build_rehearsal_package(package_dir=package_dir, fixture_only=True, clean=True)
    _promote_package_with_l2_runtime_events_for_test(package_dir, _runtime_labelled_fixture_trace_for_test())
    _mutate_runtime_events_for_test(package_dir, mutation)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=False, deep_hdf5=True)

    assert result["ok"] is False
    assert expected_issue in result["issues"]


@pytest.mark.parametrize(
    ("mutation", "expected_issue"),
    [
        ("ur_joint_order_swapped", "UR joint_names mismatch"),
        ("ur_degrees_unit", "UR joint_position unit mismatch"),
        ("ur_tcp_mm_unit", "UR tcp_position unit mismatch"),
        ("ur_not_running", "UR robot_mode must be RUNNING"),
        ("ur_protective_stop", "UR safety_status must be NORMAL"),
        ("franka_wrong_dof", "Franka q/q_d dimension mismatch"),
        ("franka_eef_wrong_length", "Franka EEF matrix length mismatch"),
        ("generic_lag_high", "generic action-state lag exceeds threshold"),
        ("generic_state_only", "generic command/state semantics missing"),
        ("phase_unknown", "runtime phase unknown"),
    ],
)
def test_runtime_event_channel_tamper_fails(tmp_path: Path, mutation: str, expected_issue: str) -> None:
    package_dir = tmp_path / f"{PACKAGE_NAME}_runtime_event_channel_{mutation}"
    build_rehearsal_package(package_dir=package_dir, fixture_only=True, clean=True)
    _promote_package_with_l2_runtime_events_for_test(package_dir, _runtime_labelled_fixture_trace_for_test())
    _mutate_runtime_events_for_test(package_dir, mutation)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=False, deep_hdf5=True)

    assert result["ok"] is False
    assert expected_issue in result["issues"]


def test_runtime_event_and_canonical_hash_refresh_without_source_refresh_fails_downstream_projection(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / f"{PACKAGE_NAME}_runtime_event_canonical_drift"
    build_rehearsal_package(package_dir=package_dir, fixture_only=True, clean=True)
    _promote_package_with_l2_runtime_events_for_test(package_dir, _runtime_labelled_fixture_trace_for_test())
    events = _runtime_events_from_package_for_test(package_dir)
    generic_event = next(event for event in events if event["channel"] == "generic_command_state")
    generic_event["payload"]["state"][0] = round(float(generic_event["payload"]["state"][0]) + 0.25, 6)
    generic_event["payload"]["command"][0] = round(float(generic_event["payload"]["command"][0]) + 0.25, 6)
    _write_runtime_events_and_refresh_for_test(package_dir, events)
    canonical = _json(package_dir / "data" / "canonical_trace" / "canonical_trace.json")
    canonical["frames"][0]["generic"]["state"] = generic_event["payload"]["state"]
    canonical["frames"][0]["generic"]["command"] = generic_event["payload"]["command"]
    _write_json(package_dir / "data" / "canonical_trace" / "canonical_trace.json", canonical)
    _refresh_canonical_hash_receipts_for_test(package_dir)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=False, deep_hdf5=True)

    assert result["ok"] is False
    assert "generic_command_state_jsonl_v0 golden source rows do not match canonical projection" in result["issues"]


def test_runtime_event_canonical_and_source_hash_refresh_without_contract_refresh_fails_export_chain(
    tmp_path: Path,
) -> None:
    package_dir = tmp_path / f"{PACKAGE_NAME}_runtime_event_source_drift"
    build_rehearsal_package(package_dir=package_dir, fixture_only=True, clean=True)
    _promote_package_with_l2_runtime_events_for_test(package_dir, _runtime_labelled_fixture_trace_for_test())
    events = _runtime_events_from_package_for_test(package_dir)
    generic_event = next(event for event in events if event["channel"] == "generic_command_state")
    generic_event["payload"]["state"][0] = round(float(generic_event["payload"]["state"][0]) + 0.25, 6)
    generic_event["payload"]["command"][0] = round(float(generic_event["payload"]["command"][0]) + 0.25, 6)
    _write_runtime_events_and_refresh_for_test(package_dir, events)
    canonical = _json(package_dir / "data" / "canonical_trace" / "canonical_trace.json")
    canonical["frames"][0]["generic"]["state"] = generic_event["payload"]["state"]
    canonical["frames"][0]["generic"]["command"] = generic_event["payload"]["command"]
    _write_json(package_dir / "data" / "canonical_trace" / "canonical_trace.json", canonical)
    _write_generic_source_rows(
        package_dir,
        [
            {
                "timestamp": frame["timestamp"],
                "state_vector": frame["generic"]["state"],
                "action_vector": frame["generic"]["command"],
            }
            for frame in canonical["frames"]
        ],
    )
    _refresh_cached_golden_source_hash(package_dir, "generic_command_state_jsonl_v0")
    _refresh_canonical_hash_receipts_for_test(package_dir)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=False, deep_hdf5=True)

    assert result["ok"] is False
    assert "generic_command_state_jsonl_v0 contract rows do not match recomputed source rows" in result["issues"]


def test_runtime_capture_only_ready_package_fails_without_l2_runtime_event_log(tmp_path: Path) -> None:
    trace = _runtime_labelled_fixture_trace_for_test()
    capture = tmp_path / "runtime_capture.json"
    _write_json(capture, _runtime_capture_payload(trace))
    package_dir = tmp_path / f"{PACKAGE_NAME}_runtime_capture_only_ready"

    build_rehearsal_package(package_dir=package_dir, runtime_capture=capture, fixture_only=False, clean=True)
    capture_sha = _sha256(package_dir / "data" / "canonical_trace" / "runtime_capture.json")
    canonical = {**trace, "runtime_capture_sha256": capture_sha}
    _write_json(package_dir / "data" / "canonical_trace" / "canonical_trace.json", canonical)
    preflight = _json(package_dir / "data" / "canonical_trace" / "runtime_capture_preflight.json")
    preflight.update(
        {
            "runtime_capture_sufficient": True,
            "runtime_capture_structurally_valid": True,
            "fresh_runtime_capture_required": False,
            "blocked_reason": None,
            "issues": [],
            "runtime_capture_sha256": capture_sha,
        }
    )
    _write_json(package_dir / "data" / "canonical_trace" / "runtime_capture_preflight.json", preflight)
    receipt = _json(package_dir / "data" / "canonical_trace" / "runtime_capture_hash_receipt.json")
    receipt.update(
        {
            "canonical_trace_sha256": _sha256(package_dir / "data" / "canonical_trace" / "canonical_trace.json"),
            "runtime_capture_supplied": True,
            "runtime_capture_sufficient": True,
            "runtime_capture_structurally_valid": True,
            "runtime_capture_sha256": capture_sha,
            "ready_status_allowed": True,
            "blocked_reason": None,
        }
    )
    _write_json(package_dir / "data" / "canonical_trace" / "runtime_capture_hash_receipt.json", receipt)
    config = _json(package_dir / "data" / "config.json")
    config.update(
        {
            "status": STATUS_READY,
            "file_drop_rehearsal_ready": True,
            "runtime_capture_sufficient": True,
            "blocked_reason": None,
            "fresh_runtime_capture_required": False,
        }
    )
    _write_json(package_dir / "data" / "config.json", config)
    manifest = _json(package_dir / "package_manifest.json")
    manifest["package_status"] = STATUS_READY
    manifest["file_drop_rehearsal_ready"] = True
    _write_json(package_dir / "package_manifest.json", manifest)
    _refresh_indexes(package_dir)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=False, deep_hdf5=True)

    assert result["ok"] is False
    assert "ready status requires data/runtime_evidence/runtime_event_log.jsonl" in result["issues"]


def test_ready_status_cannot_be_minted_without_runtime_capture_file(fixture_package: Path, tmp_path: Path) -> None:
    package_dir = _copy_package(fixture_package, tmp_path)
    config = _json(package_dir / "data" / "config.json")
    config.update(
        {
            "status": STATUS_READY,
            "file_drop_rehearsal_ready": True,
            "runtime_capture_sufficient": True,
            "blocked_reason": None,
            "fresh_runtime_capture_required": False,
        }
    )
    _write_json(package_dir / "data" / "config.json", config)

    manifest = _json(package_dir / "package_manifest.json")
    manifest["package_status"] = STATUS_READY
    manifest["file_drop_rehearsal_ready"] = True
    _write_json(package_dir / "package_manifest.json", manifest)

    preflight = _json(package_dir / "data" / "canonical_trace" / "runtime_capture_preflight.json")
    preflight.update(
        {
            "runtime_capture_supplied": True,
            "runtime_capture_sufficient": True,
            "fresh_runtime_capture_required": False,
            "blocked_reason": None,
            "issues": [],
            "observed_min_source_log_rows_emitted": 12,
        }
    )
    _write_json(package_dir / "data" / "canonical_trace" / "runtime_capture_preflight.json", preflight)

    receipt = _json(package_dir / "data" / "canonical_trace" / "runtime_capture_hash_receipt.json")
    receipt.update({"runtime_capture_supplied": True, "runtime_capture_sufficient": True, "ready_status_allowed": True, "blocked_reason": None})
    _write_json(package_dir / "data" / "canonical_trace" / "runtime_capture_hash_receipt.json", receipt)

    canonical = _json(package_dir / "data" / "canonical_trace" / "canonical_trace.json")
    canonical.update({"source_kind": "isaac_sim_runtime_backed_canonical_trace", "runtime_backed": True})
    _write_json(package_dir / "data" / "canonical_trace" / "canonical_trace.json", canonical)
    receipt["canonical_trace_sha256"] = _sha256(package_dir / "data" / "canonical_trace" / "canonical_trace.json")
    _write_json(package_dir / "data" / "canonical_trace" / "runtime_capture_hash_receipt.json", receipt)
    _refresh_indexes(package_dir)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=False)

    assert result["ok"] is False
    assert "ready status requires data/runtime_evidence/runtime_event_log.jsonl" in result["issues"]


def test_manifest_only_ready_claim_fails_even_with_refreshed_hashes(fixture_package: Path, tmp_path: Path) -> None:
    package_dir = _copy_package(fixture_package, tmp_path)
    manifest = _json(package_dir / "package_manifest.json")
    manifest["file_drop_rehearsal_ready"] = True
    manifest["file_drop_rehearsal_contract_ready"] = False
    _write_json(package_dir / "package_manifest.json", manifest)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=True, deep_hdf5=True)

    assert result["ok"] is False
    assert "package_manifest file_drop_rehearsal_ready/status mismatch" in result["issues"]
    assert "package_manifest file_drop_rehearsal_ready/config mismatch" in result["issues"]
    assert "package_manifest file_drop_rehearsal_contract_ready/config mismatch" in result["issues"]


def test_ready_status_cannot_be_minted_with_timestamp_only_runtime_capture(fixture_package: Path, tmp_path: Path) -> None:
    package_dir = _copy_package(fixture_package, tmp_path)
    capture_trace = {
        "frames": [
            {"timestamp": round(index * 0.04, 6)}
            for index in range(12)
        ],
    }
    capture_path = package_dir / "data" / "canonical_trace" / "runtime_capture.json"
    _write_json(capture_path, {"captured_at": "2026-06-25T00:00:00Z", "mvp5a_canonical_trace": capture_trace})
    capture_sha = _sha256(capture_path)

    canonical = {
        **capture_trace,
        "source_kind": "isaac_sim_runtime_backed_canonical_trace",
        "runtime_backed": True,
        "runtime_capture_sha256": capture_sha,
    }
    _write_json(package_dir / "data" / "canonical_trace" / "canonical_trace.json", canonical)

    preflight = _json(package_dir / "data" / "canonical_trace" / "runtime_capture_preflight.json")
    preflight.update(
        {
            "runtime_capture_supplied": True,
            "runtime_capture_sufficient": True,
            "fresh_runtime_capture_required": False,
            "blocked_reason": None,
            "issues": [],
            "runtime_capture_sha256": capture_sha,
            "observed_min_source_log_rows_emitted": 12,
        }
    )
    _write_json(package_dir / "data" / "canonical_trace" / "runtime_capture_preflight.json", preflight)

    receipt = _json(package_dir / "data" / "canonical_trace" / "runtime_capture_hash_receipt.json")
    receipt.update(
        {
            "canonical_trace_sha256": _sha256(package_dir / "data" / "canonical_trace" / "canonical_trace.json"),
            "runtime_capture_supplied": True,
            "runtime_capture_sufficient": True,
            "runtime_capture_sha256": capture_sha,
            "ready_status_allowed": True,
            "blocked_reason": None,
        }
    )
    _write_json(package_dir / "data" / "canonical_trace" / "runtime_capture_hash_receipt.json", receipt)

    config = _json(package_dir / "data" / "config.json")
    config.update(
        {
            "status": STATUS_READY,
            "file_drop_rehearsal_ready": True,
            "runtime_capture_sufficient": True,
            "blocked_reason": None,
            "fresh_runtime_capture_required": False,
        }
    )
    _write_json(package_dir / "data" / "config.json", config)
    manifest = _json(package_dir / "package_manifest.json")
    manifest["package_status"] = STATUS_READY
    manifest["file_drop_rehearsal_ready"] = True
    _write_json(package_dir / "package_manifest.json", manifest)
    _refresh_indexes(package_dir)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=False)

    assert result["ok"] is False
    assert "ready status requires data/runtime_evidence/runtime_event_log.jsonl" in result["issues"]
    assert "canonical trace schema invalid: runtime_capture_frame_schema_invalid" in result["issues"]


def test_hash_refreshed_golden_source_semantic_drift_fails_verifier(fixture_package: Path, tmp_path: Path) -> None:
    package_dir = _copy_package(fixture_package, tmp_path)
    csv_path = package_dir / "data" / "source_drops" / "golden" / "ur_rtde_csv_v0" / "rtde_output.csv"
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = rows[0].keys()
    rows[0]["target_q"] = "[1,1,1,1,1,1]"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    _refresh_cached_golden_source_hash(package_dir, "ur_rtde_csv_v0")
    _refresh_indexes(package_dir)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=True)

    assert result["ok"] is False
    assert any("ur_rtde_csv_v0 golden recomputation failed" in issue for issue in result["issues"])


def test_hash_refreshed_ur_tcp_pose_drift_fails_canonical_projection(fixture_package: Path, tmp_path: Path) -> None:
    package_dir = _copy_package(fixture_package, tmp_path)
    profile_id = "ur_rtde_csv_v0"
    csv_path = package_dir / "data" / "source_drops" / "golden" / profile_id / "rtde_output.csv"
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = list(rows[0].keys())
    pose = json.loads(rows[0]["actual_TCP_pose"])
    pose[0] = round(float(pose[0]) + 0.02, 6)
    rows[0]["actual_TCP_pose"] = json.dumps(pose, separators=(",", ":"))
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    _refresh_cached_golden_source_hash(package_dir, profile_id)
    _refresh_indexes(package_dir)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=True, deep_hdf5=True)

    assert result["ok"] is False
    assert f"{profile_id} golden source rows do not match canonical projection" in result["issues"]


def test_hash_refreshed_franka_eef_pose_drift_fails_canonical_projection(fixture_package: Path, tmp_path: Path) -> None:
    package_dir = _copy_package(fixture_package, tmp_path)
    profile_id = "franka_state_jsonl_v0"
    state_path = package_dir / "data" / "source_drops" / "golden" / profile_id / "franka_state.jsonl"
    rows = [json.loads(line) for line in state_path.read_text(encoding="utf-8").splitlines()]
    rows[0]["O_T_EE"][3] = round(float(rows[0]["O_T_EE"][3]) + 0.02, 6)
    state_path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    _refresh_cached_golden_source_hash(package_dir, profile_id)
    _refresh_indexes(package_dir)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=True, deep_hdf5=True)

    assert result["ok"] is False
    assert f"{profile_id} golden source rows do not match canonical projection" in result["issues"]


def test_hash_refreshed_ros2_tf_translation_drift_fails_canonical_projection(fixture_package: Path, tmp_path: Path) -> None:
    package_dir = _copy_package(fixture_package, tmp_path)
    profile_id = "ros2_channel_bundle_jsonl_v0"
    tf_path = package_dir / "data" / "source_drops" / "golden" / profile_id / "topics" / "tf.jsonl"
    rows = [json.loads(line) for line in tf_path.read_text(encoding="utf-8").splitlines()]
    rows[0]["translation"][0] = round(float(rows[0]["translation"][0]) + 0.02, 6)
    tf_path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
    _refresh_cached_golden_source_hash(package_dir, profile_id)
    _refresh_indexes(package_dir)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=True, deep_hdf5=True)

    assert result["ok"] is False
    assert f"{profile_id} golden source rows do not match canonical projection" in result["issues"]


def test_hash_refreshed_contract_and_hdf5_cannot_drift_from_source(fixture_package: Path, tmp_path: Path) -> None:
    package_dir = _copy_package(fixture_package, tmp_path)
    profile_id = "generic_command_state_jsonl_v0"
    contract_path = package_dir / "data" / "normalized_contracts" / f"{profile_id}_normalized_contract.json"
    contract = _json(contract_path)
    contract["rows"][0]["state_vector"] = [value + 0.25 for value in contract["rows"][0]["state_vector"]]
    _write_json(contract_path, contract)

    export_dir = package_dir / "data" / "export" / profile_id
    hdf5_path = export_dir / "dataset.hdf5"
    with h5py.File(hdf5_path, "r+") as h5:
        h5_any = cast(Any, h5)
        h5_any["states"][0, :] = contract["rows"][0]["state_vector"]

    forged_state_hash = _float32_array_hash([row["state_vector"] for row in contract["rows"]])
    action_hash = _float32_array_hash([row["action_vector"] for row in contract["rows"]])
    timestamp_hash = _float64_array_hash([row["timestamp"] for row in contract["rows"]])

    inspection = _json(export_dir / "hdf5_inspection_report.json")
    inspection["hdf5_sha256"] = _sha256(hdf5_path)
    inspection["state_array_sha256"] = forged_state_hash
    inspection["action_array_sha256"] = action_hash
    inspection["timestamp_array_sha256"] = timestamp_hash
    _write_json(export_dir / "hdf5_inspection_report.json", inspection)

    receipt = _json(export_dir / "semantic_preservation_receipt.json")
    receipt["source_state_sha256"] = forged_state_hash
    receipt["hdf5_state_sha256"] = forged_state_hash
    receipt["source_action_sha256"] = action_hash
    receipt["hdf5_action_sha256"] = action_hash
    receipt["source_timestamp_sha256"] = timestamp_hash
    receipt["hdf5_timestamp_sha256"] = timestamp_hash
    _write_json(export_dir / "semantic_preservation_receipt.json", receipt)
    _refresh_indexes(package_dir)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=True, deep_hdf5=True)

    assert result["ok"] is False
    assert f"{profile_id} contract rows do not match recomputed source rows" in result["issues"]


def test_hash_refreshed_source_contract_hdf5_cannot_drift_from_canonical(fixture_package: Path, tmp_path: Path) -> None:
    package_dir = _copy_package(fixture_package, tmp_path)
    profile_id = "generic_command_state_jsonl_v0"
    contract_path = package_dir / "data" / "normalized_contracts" / f"{profile_id}_normalized_contract.json"
    contract = _json(contract_path)
    forged_rows = []
    for row in contract["rows"]:
        forged_rows.append(
            {
                "timestamp": row["timestamp"],
                "state_vector": [round(value + 0.125, 6) for value in row["state_vector"]],
                "action_vector": [round(value + 0.125, 6) for value in row["action_vector"]],
            }
        )
    contract["rows"] = forged_rows
    _write_json(contract_path, contract)
    _write_generic_source_rows(package_dir, forged_rows)

    export_dir = package_dir / "data" / "export" / profile_id
    hdf5_path = export_dir / "dataset.hdf5"
    with h5py.File(hdf5_path, "r+") as h5:
        h5_any = cast(Any, h5)
        h5_any["states"][:, :] = [row["state_vector"] for row in forged_rows]
        h5_any["actions"][:, :] = [row["action_vector"] for row in forged_rows]

    forged_state_hash = _float32_array_hash([row["state_vector"] for row in forged_rows])
    forged_action_hash = _float32_array_hash([row["action_vector"] for row in forged_rows])
    timestamp_hash = _float64_array_hash([row["timestamp"] for row in forged_rows])
    inspection = _json(export_dir / "hdf5_inspection_report.json")
    inspection["hdf5_sha256"] = _sha256(hdf5_path)
    inspection["state_array_sha256"] = forged_state_hash
    inspection["action_array_sha256"] = forged_action_hash
    inspection["timestamp_array_sha256"] = timestamp_hash
    _write_json(export_dir / "hdf5_inspection_report.json", inspection)
    receipt = _json(export_dir / "semantic_preservation_receipt.json")
    receipt.update(
        {
            "source_state_sha256": forged_state_hash,
            "source_action_sha256": forged_action_hash,
            "source_timestamp_sha256": timestamp_hash,
            "hdf5_state_sha256": forged_state_hash,
            "hdf5_action_sha256": forged_action_hash,
            "hdf5_timestamp_sha256": timestamp_hash,
        }
    )
    _write_json(export_dir / "semantic_preservation_receipt.json", receipt)
    _refresh_cached_golden_source_hash(package_dir, profile_id)
    _refresh_indexes(package_dir)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=True, deep_hdf5=True)

    assert result["ok"] is False
    assert f"{profile_id} golden source rows do not match canonical projection" in result["issues"]


def test_default_verifier_requires_deep_hdf5_for_hdf5_payloads(fixture_package: Path) -> None:
    result = verify_package(fixture_package / "package_manifest.json", allow_contract_ready=True)

    assert result["ok"] is False
    assert "hdf5 payload verification requires --deep-hdf5" in result["issues"]


def test_deep_hdf5_detects_timestamp_drift_after_file_hash_refresh(fixture_package: Path, tmp_path: Path) -> None:
    package_dir = _copy_package(fixture_package, tmp_path)
    profile_id = "ur_rtde_csv_v0"
    export_dir = package_dir / "data" / "export" / profile_id
    hdf5_path = export_dir / "dataset.hdf5"
    with h5py.File(hdf5_path, "r+") as h5:
        h5_any = cast(Any, h5)
        h5_any["timestamps"][0] = float(h5_any["timestamps"][0]) + 1.0
    inspection = _json(export_dir / "hdf5_inspection_report.json")
    inspection["hdf5_sha256"] = _sha256(hdf5_path)
    _write_json(export_dir / "hdf5_inspection_report.json", inspection)
    _refresh_indexes(package_dir)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=True, deep_hdf5=True)

    assert result["ok"] is False
    assert f"{profile_id} deep hdf5 timestamps mismatch" in result["issues"]


def test_deep_hdf5_detects_semantic_drift_even_after_receipt_refresh(fixture_package: Path, tmp_path: Path) -> None:
    package_dir = _copy_package(fixture_package, tmp_path)
    profile_id = "franka_state_jsonl_v0"
    export_dir = package_dir / "data" / "export" / profile_id
    hdf5_path = export_dir / "dataset.hdf5"
    with h5py.File(hdf5_path, "r+") as h5:
        h5_any = cast(Any, h5)
        h5_any["actions"][0, 0] = float(h5_any["actions"][0, 0]) + 10.0
    inspection = _json(export_dir / "hdf5_inspection_report.json")
    inspection["hdf5_sha256"] = _sha256(hdf5_path)
    _write_json(export_dir / "hdf5_inspection_report.json", inspection)
    _refresh_indexes(package_dir)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=True, deep_hdf5=True)

    assert result["ok"] is False
    assert any("franka_state_jsonl_v0 deep hdf5 actions mismatch" in issue for issue in result["issues"])


def test_deep_hdf5_detects_sub_tolerance_payload_drift_after_hash_refresh(fixture_package: Path, tmp_path: Path) -> None:
    package_dir = _copy_package(fixture_package, tmp_path)
    profile_id = "ur_rtde_csv_v0"
    export_dir = package_dir / "data" / "export" / profile_id
    hdf5_path = export_dir / "dataset.hdf5"
    with h5py.File(hdf5_path, "r+") as h5:
        h5_any = cast(Any, h5)
        h5_any["states"][0, 0] = float(h5_any["states"][0, 0]) + 1e-9
    inspection = _json(export_dir / "hdf5_inspection_report.json")
    inspection["hdf5_sha256"] = _sha256(hdf5_path)
    _write_json(export_dir / "hdf5_inspection_report.json", inspection)
    _refresh_indexes(package_dir)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=True, deep_hdf5=True)

    assert result["ok"] is False
    assert any("ur_rtde_csv_v0 deep hdf5 states mismatch" in issue for issue in result["issues"])


def test_buyer_report_positive_claim_fails_claim_scan(fixture_package: Path, tmp_path: Path) -> None:
    package_dir = _copy_package(fixture_package, tmp_path)
    report = package_dir / "buyer_report.html"
    report.write_text(report.read_text(encoding="utf-8") + "\n<p>real robot ready</p>\n", encoding="utf-8")
    data_report = package_dir / "data" / "reports" / "buyer_report.html"
    data_report.write_text(data_report.read_text(encoding="utf-8") + "\n<p>real robot ready</p>\n", encoding="utf-8")
    _refresh_indexes(package_dir)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=True)

    assert result["ok"] is False
    assert any("forbidden positive claim phrase: real robot ready" in issue for issue in result["issues"])


@pytest.mark.parametrize("phrase", VERIFIER_FORBIDDEN_POSITIVE_PHRASES)
@pytest.mark.parametrize("surface", ("readme", "html_report", "json_string_value"))
def test_every_forbidden_positive_phrase_fails_claim_scan(
    fixture_package: Path,
    tmp_path: Path,
    phrase: str,
    surface: str,
) -> None:
    package_dir = _copy_package(fixture_package, tmp_path)
    sentence = f"This package provides {phrase}."
    if surface == "readme":
        path = package_dir / "README.md"
        path.write_text(path.read_text(encoding="utf-8") + f"\n{sentence}\n", encoding="utf-8")
    elif surface == "html_report":
        path = package_dir / "data" / "reports" / "buyer_report.html"
        path.write_text(path.read_text(encoding="utf-8") + f"\n<p>{sentence}</p>\n", encoding="utf-8")
    else:
        path = package_dir / "data" / "config.json"
        config = _json(path)
        config["reviewer_summary"] = sentence
        _write_json(path, config)
    _refresh_indexes(package_dir)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=True)

    assert result["ok"] is False
    assert any(f"forbidden positive claim phrase: {phrase}" in issue for issue in result["issues"])


def test_non_claim_true_fails_even_with_refreshed_hashes(fixture_package: Path, tmp_path: Path) -> None:
    package_dir = _copy_package(fixture_package, tmp_path)
    non_claims = _json(package_dir / "data" / "non_claims_attestation.json")
    non_claims["non_claims"]["policy_uplift"] = True
    _write_json(package_dir / "data" / "non_claims_attestation.json", non_claims)
    _refresh_indexes(package_dir)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=True)

    assert result["ok"] is False
    assert "non_claims_attestation forbidden claim policy_uplift must be false" in result["issues"]


def test_profile_registry_hash_refreshed_drift_fails_verifier(fixture_package: Path, tmp_path: Path) -> None:
    package_dir = _copy_package(fixture_package, tmp_path)
    registry_path = package_dir / "data" / "profile_registry.json"
    registry = _json(registry_path)
    registry["schema_version"] = "rdf_mvp5a_pre_file_drop_profile_registry_v9.9.9"
    registry["profile_count"] = len(PROFILE_IDS) + 1
    registry["profiles"][0]["source_file_names"] = ["metadata.json"]
    registry["profiles"][0]["action_semantics"] = "actual_q_as_command"
    _write_json(registry_path, registry)
    _refresh_indexes(package_dir)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=True)

    assert result["ok"] is False
    assert "profile registry schema_version mismatch" in result["issues"]
    assert "profile registry profile_count mismatch" in result["issues"]
    assert "ur_rtde_csv_v0 profile registry contract mismatch" in result["issues"]


def test_profile_registry_duplicate_missing_profile_fails_verifier(fixture_package: Path, tmp_path: Path) -> None:
    package_dir = _copy_package(fixture_package, tmp_path)
    registry_path = package_dir / "data" / "profile_registry.json"
    registry = _json(registry_path)
    registry["profiles"][-1] = dict(registry["profiles"][0])
    _write_json(registry_path, registry)
    _refresh_indexes(package_dir)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=True, deep_hdf5=True)

    assert result["ok"] is False
    assert "profile registry profile_id order/exactness mismatch" in result["issues"]
    assert "profile registry duplicate profile_id" in result["issues"]


def test_cached_summary_mismatch_cannot_override_recomputation(fixture_package: Path, tmp_path: Path) -> None:
    package_dir = _copy_package(fixture_package, tmp_path)
    config = _json(package_dir / "data" / "config.json")
    config["corrupt_case_count"] = 0
    config["corrupt_matrix_silent_pass_rate"] = 1.0
    _write_json(package_dir / "data" / "config.json", config)
    _refresh_indexes(package_dir)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=True)

    assert result["ok"] is False
    assert "config corrupt_case_count mismatch" in result["issues"]


def test_corrupt_case_cannot_become_export_eligible_by_summary_edit(fixture_package: Path, tmp_path: Path) -> None:
    package_dir = _copy_package(fixture_package, tmp_path)
    corrupt_path = package_dir / "data" / "ingest_results" / "corruption_matrix_results.json"
    payload = _json(corrupt_path)
    payload["results"][0]["export_eligible"] = True
    payload["results"][0]["trainer_smoke_eligible"] = True
    _write_json(corrupt_path, payload)
    _refresh_indexes(package_dir)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=True)

    assert result["ok"] is False
    assert any("corrupt case export/trainer eligible" in issue for issue in result["issues"])


def test_manifest_path_traversal_and_duplicate_roles_fail(fixture_package: Path, tmp_path: Path) -> None:
    package_dir = _copy_package(fixture_package, tmp_path)
    manifest = _json(package_dir / "package_manifest.json")
    manifest["artifact_index"].append(
        {
            "data_path": "data/../package_manifest.json",
            "file_sha256": "0" * 64,
            "byte_size": 1,
            "hash_convention": "file_bytes",
        }
    )
    manifest["artifact_index"][0]["artifact_role"] = "duplicate_role"
    manifest["artifact_index"][1]["artifact_role"] = "duplicate_role"
    _write_json(package_dir / "package_manifest.json", manifest)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=True)

    assert result["ok"] is False
    assert "artifact_index unsafe data_path" in result["issues"]
    assert "duplicate_role duplicate artifact role" in result["issues"]


def test_manifest_symlink_escape_fails_even_when_data_path_is_relative(fixture_package: Path, tmp_path: Path) -> None:
    package_dir = _copy_package(fixture_package, tmp_path)
    outside = tmp_path / "outside_evidence.txt"
    outside.write_text("outside package\n", encoding="utf-8")
    symlink = package_dir / "data" / "source_drops" / "golden" / "ur_rtde_csv_v0" / "escape.txt"
    symlink.symlink_to(outside)
    _refresh_indexes(package_dir)

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=True)

    assert result["ok"] is False
    assert "data/source_drops/golden/ur_rtde_csv_v0/escape.txt symlink escapes package" in result["issues"]


def test_clean_guard_rejects_prefix_sibling_paths(tmp_path: Path) -> None:
    prefix_sibling = Path("/tmpx") / PACKAGE_NAME
    repo_prefix_sibling = ROOT / "docs" / "proof_backup" / PACKAGE_NAME

    with pytest.raises(ValueError):
        _assert_managed_package_dir(prefix_sibling)
    with pytest.raises(ValueError):
        _assert_managed_package_dir(repo_prefix_sibling)


def test_missing_artifact_fails(fixture_package: Path, tmp_path: Path) -> None:
    package_dir = _copy_package(fixture_package, tmp_path)
    (package_dir / "data" / "profile_registry.json").unlink()

    result = verify_package(package_dir / "package_manifest.json", allow_contract_ready=True)

    assert result["ok"] is False
    assert any("data/profile_registry.json missing" in issue for issue in result["issues"])
