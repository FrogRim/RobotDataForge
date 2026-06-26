from __future__ import annotations

import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

import pytest

from app.services.mvp5a_file_drop_rehearsal import (
    PROFILE_IDS,
    build_fixture_canonical_trace,
    export_profile_hdf5,
    sha256_file,
    stable_json,
    write_golden_profile_drop,
)


ROOT = Path(__file__).resolve().parents[3]
CLI = ROOT / "scripts" / "rdf_file_drop_evaluator.py"
VERIFIER = ROOT / "scripts" / "verify_rdf_file_drop_evaluator_run.py"
ARTIFACT_ROOT = ROOT / "artifacts" / "rdf_file_drop_evaluator"


def _run_python(script: Path, *args: str | Path) -> tuple[int, dict[str, Any]]:
    completed = subprocess.run(
        [sys.executable, str(script), *[str(arg) for arg in args]],
        cwd=ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - failure message path
        raise AssertionError(
            f"script did not emit JSON\nscript={script}\nrc={completed.returncode}\n"
            f"stdout={completed.stdout}\nstderr={completed.stderr}"
        ) from exc
    return completed.returncode, payload


def _golden_drop(tmp_path: Path, profile_id: str) -> Path:
    drop_dir = tmp_path / "drops" / profile_id
    write_golden_profile_drop(profile_id, build_fixture_canonical_trace(), drop_dir)
    return drop_dir


def _managed_run_dir(tmp_path: Path, name: str) -> Path:
    run_dir = ARTIFACT_ROOT / f"pytest-{tmp_path.name}-{name}"
    shutil.rmtree(run_dir, ignore_errors=True)
    return run_dir


def _evaluate(tmp_path: Path, profile_id: str) -> Path:
    drop_dir = _golden_drop(tmp_path, profile_id)
    run_dir = _managed_run_dir(tmp_path, profile_id)
    rc, payload = _run_python(CLI, "evaluate", drop_dir, "--profile", profile_id, "--out", run_dir, "--json")
    assert rc == 0, payload
    assert payload["ok"] is True
    assert payload["passed"] is True
    assert payload["run_dir"] == str(run_dir)
    return run_dir


def _refresh_artifact_index(run_dir: Path) -> None:
    manifest_path = run_dir / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact_index = []
    for path in sorted(run_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(run_dir).as_posix()
        if rel in {"package_manifest.json", "verifier_result.json"}:
            continue
        artifact_index.append(
            {
                "path": rel,
                "sha256": sha256_file(path),
                "byte_size": path.stat().st_size,
                "role": next(
                    (entry["role"] for entry in manifest["artifact_index"] if entry["path"] == rel),
                    "tamper_refreshed",
                ),
            }
        )
    manifest["artifact_index"] = artifact_index
    manifest_path.write_text(stable_json(manifest) + "\n", encoding="utf-8")


def _refresh_source_hashes(run_dir: Path) -> None:
    source_root = run_dir / "source_drop"
    hashes = {}
    for path in sorted(source_root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(source_root).as_posix()
            hashes[rel] = {"sha256": sha256_file(path), "byte_size": path.stat().st_size}
    for rel in ("input_receipt.json", "preflight_result.json"):
        payload_path = run_dir / rel
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload["source_file_hashes"] = hashes
        payload_path.write_text(stable_json(payload) + "\n", encoding="utf-8")


def _write_ur_rows(csv_path: Path, rows: list[dict[str, str]]) -> None:
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "timestamp",
                "joint_names",
                "actual_q",
                "target_q",
                "actual_TCP_pose",
                "target_TCP_pose",
                "actual_TCP_speed",
                "robot_mode",
                "safety_status",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _align_ur_package_to_source_rows(run_dir: Path, rows: list[dict[str, str]]) -> None:
    normalized_rows = [
        {
            "timestamp": float(row["timestamp"]),
            "state_vector": json.loads(row["actual_q"]),
            "action_vector": json.loads(row["target_q"]),
        }
        for row in rows
    ]
    contract_path = run_dir / "normalized" / "normalized_contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["rows"] = normalized_rows
    contract["frame_count"] = len(normalized_rows)
    contract_path.write_text(stable_json(contract) + "\n", encoding="utf-8")

    for rel in ("preflight_result.json", "evaluation_result.json", "reports/buyer_report.json"):
        payload_path = run_dir / rel
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload["passed"] = True
        payload["frame_count"] = len(normalized_rows)
        payload["rejection_reasons"] = []
        payload["export_eligible"] = True
        payload["trainer_smoke_eligible"] = True
        payload_path.write_text(stable_json(payload) + "\n", encoding="utf-8")

    manifest_path = run_dir / "package_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["passed"] = True
    manifest_path.write_text(stable_json(manifest) + "\n", encoding="utf-8")

    shutil.rmtree(run_dir / "export", ignore_errors=True)
    export_profile_hdf5("ur_rtde_csv_v0", normalized_rows, run_dir / "export")
    _refresh_source_hashes(run_dir)
    _refresh_artifact_index(run_dir)


def _rejected_ur_run_with_robot_mode_stop(tmp_path: Path, name: str) -> Path:
    drop_dir = _golden_drop(tmp_path, "ur_rtde_csv_v0")
    csv_path = drop_dir / "rtde_output.csv"
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["robot_mode"] = "stopped"
    _write_ur_rows(csv_path, rows)
    run_dir = _managed_run_dir(tmp_path, name)
    rc, payload = _run_python(CLI, "evaluate", drop_dir, "--profile", "ur_rtde_csv_v0", "--out", run_dir, "--json")
    assert rc != 0
    assert payload["passed"] is False
    assert "safety_or_robot_mode_invalid" in payload["rejection_reasons"]
    return run_dir


@pytest.mark.parametrize("profile_id", PROFILE_IDS)
def test_evaluate_creates_verifier_backed_run_package(tmp_path: Path, profile_id: str) -> None:
    run_dir = _evaluate(tmp_path, profile_id)

    expected_paths = {
        "input_receipt.json",
        "preflight_result.json",
        "evaluation_result.json",
        "normalized/normalized_contract.json",
        "reports/buyer_report.html",
        "reports/buyer_report.json",
        "package_manifest.json",
    }
    assert expected_paths.issubset({path.relative_to(run_dir).as_posix() for path in run_dir.rglob("*") if path.is_file()})
    assert (run_dir / "source_drop" / "metadata.json").exists()
    assert (run_dir / "export" / "dataset.hdf5").exists()

    rc, payload = _run_python(VERIFIER, run_dir / "package_manifest.json", "--deep-hdf5", "--json")

    assert rc == 0, payload
    assert payload["ok"] is True
    assert payload["verdict"] == "VERIFIED"
    assert payload["profile_id"] == profile_id
    assert payload["passed"] is True
    assert payload["external_partner_data_evaluated"] is False
    assert payload["real_robot_data_evaluated"] is False


def test_cli_verify_runs_independent_verifier(tmp_path: Path) -> None:
    run_dir = _evaluate(tmp_path, "ur_rtde_csv_v0")

    rc, payload = _run_python(CLI, "verify", run_dir, "--deep-hdf5", "--json")

    assert rc == 0, payload
    assert payload["ok"] is True
    assert payload["verdict"] == "VERIFIED"
    assert payload["verifier"] == "verify_rdf_file_drop_evaluator_run.py"


def test_verifier_rejects_tampered_cached_evaluation_summary(tmp_path: Path) -> None:
    run_dir = _evaluate(tmp_path, "ur_rtde_csv_v0")
    result_path = run_dir / "evaluation_result.json"
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    payload["frame_count"] = 999
    result_path.write_text(stable_json(payload) + "\n", encoding="utf-8")
    _refresh_artifact_index(run_dir)

    rc, payload = _run_python(VERIFIER, run_dir / "package_manifest.json", "--deep-hdf5", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert "evaluation_summary_mismatch" in payload["failed_checks"]


def test_verifier_rejects_buyer_report_positive_forbidden_claim(tmp_path: Path) -> None:
    run_dir = _evaluate(tmp_path, "ur_rtde_csv_v0")
    report_path = run_dir / "reports" / "buyer_report.html"
    report_path.write_text(
        report_path.read_text(encoding="utf-8") + "\n<p>real robot ready and production ready</p>\n",
        encoding="utf-8",
    )
    _refresh_artifact_index(run_dir)

    rc, payload = _run_python(VERIFIER, run_dir / "package_manifest.json", "--deep-hdf5", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert "forbidden_claim_leakage" in payload["failed_checks"]


def test_verifier_rejects_positive_claim_after_negated_limitation_with_contrast(tmp_path: Path) -> None:
    run_dir = _evaluate(tmp_path, "ur_rtde_csv_v0")
    report_path = run_dir / "reports" / "buyer_report.html"
    report_path.write_text(
        report_path.read_text(encoding="utf-8")
        + "\n<p>This package does not claim production readiness, but real robot success is proven.</p>\n",
        encoding="utf-8",
    )
    _refresh_artifact_index(run_dir)

    rc, payload = _run_python(VERIFIER, run_dir / "package_manifest.json", "--deep-hdf5", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert "forbidden_claim_leakage" in payload["failed_checks"]


def test_verifier_rejects_tampered_cached_preflight_pass(tmp_path: Path) -> None:
    run_dir = _rejected_ur_run_with_robot_mode_stop(tmp_path, "preflight-pass-tamper")
    preflight_path = run_dir / "preflight_result.json"
    preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    preflight["ok"] = True
    preflight["passed"] = True
    preflight["frame_count"] = 12
    preflight["rejection_reasons"] = []
    preflight["export_eligible"] = True
    preflight["trainer_smoke_eligible"] = True
    preflight_path.write_text(stable_json(preflight) + "\n", encoding="utf-8")
    _refresh_artifact_index(run_dir)

    rc, payload = _run_python(VERIFIER, run_dir / "package_manifest.json", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert "preflight_result_mismatch" in payload["failed_checks"]


def test_verifier_rejects_duplicate_rejection_reasons_exact_parity(tmp_path: Path) -> None:
    run_dir = _rejected_ur_run_with_robot_mode_stop(tmp_path, "duplicate-reason")
    for rel in ("evaluation_result.json", "reports/buyer_report.json"):
        payload_path = run_dir / rel
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        payload["rejection_reasons"] = [*payload["rejection_reasons"], payload["rejection_reasons"][0]]
        payload_path.write_text(stable_json(payload) + "\n", encoding="utf-8")
    _refresh_artifact_index(run_dir)

    rc, payload = _run_python(VERIFIER, run_dir / "package_manifest.json", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert "evaluation_summary_mismatch" in payload["failed_checks"]


def test_verifier_rejects_rejected_run_with_training_export_attached(tmp_path: Path) -> None:
    run_dir = _rejected_ur_run_with_robot_mode_stop(tmp_path, "rejected-with-export")
    csv_path = run_dir / "source_drop" / "rtde_output.csv"
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = [
            {
                "timestamp": float(row["timestamp"]),
                "state_vector": json.loads(row["actual_q"]),
                "action_vector": json.loads(row["target_q"]),
            }
            for row in csv.DictReader(handle)
        ]
    export_profile_hdf5("ur_rtde_csv_v0", rows, run_dir / "export")
    _refresh_artifact_index(run_dir)

    rc, payload = _run_python(VERIFIER, run_dir / "package_manifest.json", "--deep-hdf5", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert "export_not_allowed_for_rejected_run" in payload["failed_checks"]


def test_verifier_rejects_hash_refreshed_buyer_report_status_drift(tmp_path: Path) -> None:
    drop_dir = _golden_drop(tmp_path, "ur_rtde_csv_v0")
    csv_path = drop_dir / "rtde_output.csv"
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["robot_mode"] = "stopped"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "timestamp",
                "joint_names",
                "actual_q",
                "target_q",
                "actual_TCP_pose",
                "target_TCP_pose",
                "actual_TCP_speed",
                "robot_mode",
                "safety_status",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    run_dir = _managed_run_dir(tmp_path, "rejected-status-drift")
    rc, payload = _run_python(CLI, "evaluate", drop_dir, "--profile", "ur_rtde_csv_v0", "--out", run_dir, "--json")
    assert rc != 0
    assert payload["passed"] is False
    report_json = json.loads((run_dir / "reports" / "buyer_report.json").read_text(encoding="utf-8"))
    report_json["passed"] = True
    report_json["frame_count"] = 999
    (run_dir / "reports" / "buyer_report.json").write_text(stable_json(report_json) + "\n", encoding="utf-8")
    html_path = run_dir / "reports" / "buyer_report.html"
    html_path.write_text(html_path.read_text(encoding="utf-8").replace("REJECTED", "PASS"), encoding="utf-8")
    _refresh_artifact_index(run_dir)

    verify_rc, verify_payload = _run_python(VERIFIER, run_dir / "package_manifest.json", "--json")

    assert verify_rc != 0
    assert verify_payload["ok"] is False
    assert "buyer_report_mismatch" in verify_payload["failed_checks"]


def test_verifier_rejects_snake_case_positive_claim_in_html(tmp_path: Path) -> None:
    run_dir = _evaluate(tmp_path, "ur_rtde_csv_v0")
    report_path = run_dir / "reports" / "buyer_report.html"
    report_path.write_text(
        report_path.read_text(encoding="utf-8") + "\n<p>external_partner_data_evaluated=true</p>\n",
        encoding="utf-8",
    )
    _refresh_artifact_index(run_dir)

    rc, payload = _run_python(VERIFIER, run_dir / "package_manifest.json", "--deep-hdf5", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert "forbidden_claim_leakage" in payload["failed_checks"]


def test_verifier_rejects_snake_case_positive_prose_claim_in_html(tmp_path: Path) -> None:
    run_dir = _evaluate(tmp_path, "ur_rtde_csv_v0")
    report_path = run_dir / "reports" / "buyer_report.html"
    report_path.write_text(
        report_path.read_text(encoding="utf-8") + "\n<p>external_partner_data_evaluated is true</p>\n",
        encoding="utf-8",
    )
    _refresh_artifact_index(run_dir)

    rc, payload = _run_python(VERIFIER, run_dir / "package_manifest.json", "--deep-hdf5", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert "forbidden_claim_leakage" in payload["failed_checks"]


def test_verifier_rejects_string_valued_positive_forbidden_claim_in_json(tmp_path: Path) -> None:
    run_dir = _evaluate(tmp_path, "ur_rtde_csv_v0")
    (run_dir / "reports" / "claim_leak.json").write_text(
        stable_json({"real_robot_success": "enabled", "production_readiness": "ready"}) + "\n",
        encoding="utf-8",
    )
    _refresh_artifact_index(run_dir)

    rc, payload = _run_python(VERIFIER, run_dir / "package_manifest.json", "--deep-hdf5", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert "forbidden_claim_leakage" in payload["failed_checks"]


def test_verifier_rejects_hash_refreshed_timestamp_gap_between_producer_and_verifier_thresholds(tmp_path: Path) -> None:
    run_dir = _evaluate(tmp_path, "ur_rtde_csv_v0")
    csv_path = run_dir / "source_drop" / "rtde_output.csv"
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for index, row in enumerate(rows):
        row["timestamp"] = f"{index * 0.02:.2f}"
    for index in range(5, len(rows)):
        rows[index]["timestamp"] = f"{0.17 + ((index - 5) * 0.02):.2f}"
    _write_ur_rows(csv_path, rows)
    _align_ur_package_to_source_rows(run_dir, rows)

    rc, payload = _run_python(VERIFIER, run_dir / "package_manifest.json", "--deep-hdf5", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert "preflight_result_mismatch" in payload["failed_checks"]


def test_verifier_rejects_extra_producer_owned_rejection_reasons(tmp_path: Path) -> None:
    drop_dir = _golden_drop(tmp_path, "ur_rtde_csv_v0")
    csv_path = drop_dir / "rtde_output.csv"
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["robot_mode"] = "stopped"
    _write_ur_rows(csv_path, rows)
    run_dir = _managed_run_dir(tmp_path, "extra-reason")
    rc, payload = _run_python(CLI, "evaluate", drop_dir, "--profile", "ur_rtde_csv_v0", "--out", run_dir, "--json")
    assert rc != 0
    assert payload["passed"] is False

    for rel in ("evaluation_result.json", "reports/buyer_report.json"):
        payload_path = run_dir / rel
        document = json.loads(payload_path.read_text(encoding="utf-8"))
        document["rejection_reasons"] = [*document["rejection_reasons"], "producer_owned_extra_reason"]
        payload_path.write_text(stable_json(document) + "\n", encoding="utf-8")
    _refresh_artifact_index(run_dir)

    verify_rc, verify_payload = _run_python(VERIFIER, run_dir / "package_manifest.json", "--json")

    assert verify_rc != 0
    assert verify_payload["ok"] is False
    assert "evaluation_summary_mismatch" in verify_payload["failed_checks"]


def test_verifier_rejects_hash_refreshed_semantic_source_tamper(tmp_path: Path) -> None:
    run_dir = _evaluate(tmp_path, "ur_rtde_csv_v0")
    csv_path = run_dir / "source_drop" / "rtde_output.csv"
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["actual_q"] = "[9,9,9,9,9,9]"
    _write_ur_rows(csv_path, rows)
    _refresh_source_hashes(run_dir)
    _refresh_artifact_index(run_dir)

    rc, payload = _run_python(VERIFIER, run_dir / "package_manifest.json", "--deep-hdf5", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert "preflight_result_mismatch" in payload["failed_checks"]


def test_verifier_import_guard_is_stdlib_plus_optional_hdf5_only() -> None:
    text = VERIFIER.read_text(encoding="utf-8")

    assert "app.services" not in text
    assert "mvp5a_file_drop_rehearsal" not in text
