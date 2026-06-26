from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest

from app.services.mvp5a_file_drop_rehearsal import (
    PROFILE_IDS,
    build_fixture_canonical_trace,
    write_golden_profile_drop,
)


ROOT = Path(__file__).resolve().parents[3]
CLI = ROOT / "scripts" / "rdf_file_drop_evaluator.py"
ARTIFACT_ROOT = ROOT / "artifacts" / "rdf_file_drop_evaluator"


def _run_cli(*args: str | Path) -> tuple[int, dict]:
    completed = subprocess.run(
        [sys.executable, str(CLI), *[str(arg) for arg in args]],
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
            f"CLI did not emit JSON\nrc={completed.returncode}\nstdout={completed.stdout}\nstderr={completed.stderr}"
        ) from exc
    return completed.returncode, payload


def _golden_drop(tmp_path: Path, profile_id: str) -> Path:
    drop_dir = tmp_path / "drops" / profile_id
    write_golden_profile_drop(profile_id, build_fixture_canonical_trace(), drop_dir)
    return drop_dir


def _zip_dir(source_dir: Path, zip_path: Path) -> Path:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source_dir).as_posix())
    return zip_path


def _managed_run_dir(tmp_path: Path, name: str) -> Path:
    run_dir = ARTIFACT_ROOT / f"pytest-{tmp_path.name}-{name}"
    shutil.rmtree(run_dir, ignore_errors=True)
    return run_dir


def test_profiles_list_returns_exact_profile_ids() -> None:
    rc, payload = _run_cli("profiles", "list", "--json")

    assert rc == 0
    assert payload["ok"] is True
    assert payload["profile_ids"] == list(PROFILE_IDS)
    assert {profile["profile_id"] for profile in payload["profiles"]} == set(PROFILE_IDS)


def test_profiles_inspect_returns_robot_metadata() -> None:
    rc, payload = _run_cli("profiles", "inspect", "ur_rtde_csv_v0", "--json")

    assert rc == 0
    assert payload["ok"] is True
    assert payload["profile"]["profile_id"] == "ur_rtde_csv_v0"
    assert payload["profile"]["robot_family"] == "universal_robots"
    assert payload["profile"]["robot_model"] == "ur10e"
    assert payload["profile"]["dof"] == 6
    assert payload["profile"]["external_partner_data"] is False
    assert payload["profile"]["live_runtime_support"] is False


def test_profiles_inspect_unknown_profile_fails_closed() -> None:
    rc, payload = _run_cli("profiles", "inspect", "unknown_profile", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert "unsupported_profile" in payload["rejection_reasons"]


@pytest.mark.parametrize("profile_id", PROFILE_IDS)
def test_preflight_golden_folder_passes(tmp_path: Path, profile_id: str) -> None:
    drop_dir = _golden_drop(tmp_path, profile_id)

    rc, payload = _run_cli("preflight", drop_dir, "--profile", profile_id, "--json")

    assert rc == 0
    assert payload["ok"] is True
    assert payload["passed"] is True
    assert payload["profile_id"] == profile_id
    assert payload["input_kind"] == "folder"
    assert payload["frame_count"] == 12
    assert payload["source_file_hashes"]
    assert payload["export_eligible"] is True
    assert payload["trainer_smoke_eligible"] is True


@pytest.mark.parametrize("profile_id", PROFILE_IDS)
def test_preflight_golden_zip_passes(tmp_path: Path, profile_id: str) -> None:
    drop_dir = _golden_drop(tmp_path, profile_id)
    zip_path = _zip_dir(drop_dir, tmp_path / f"{profile_id}.zip")

    rc, payload = _run_cli("preflight", zip_path, "--profile", profile_id, "--json")

    assert rc == 0
    assert payload["ok"] is True
    assert payload["passed"] is True
    assert payload["profile_id"] == profile_id
    assert payload["input_kind"] == "zip"
    assert payload["frame_count"] == 12


def test_preflight_unknown_profile_fails_without_auto_detection(tmp_path: Path) -> None:
    drop_dir = _golden_drop(tmp_path, "ur_rtde_csv_v0")

    rc, payload = _run_cli("preflight", drop_dir, "--profile", "unknown_profile", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert payload["passed"] is False
    assert "unsupported_profile" in payload["rejection_reasons"]


def test_preflight_wrong_profile_declared_fails(tmp_path: Path) -> None:
    drop_dir = _golden_drop(tmp_path, "ur_rtde_csv_v0")

    rc, payload = _run_cli("preflight", drop_dir, "--profile", "franka_state_jsonl_v0", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert payload["passed"] is False
    assert "unsupported_profile" in payload["rejection_reasons"]


def test_report_summarizes_existing_run_without_creating_verdict(tmp_path: Path) -> None:
    drop_dir = _golden_drop(tmp_path, "generic_command_state_jsonl_v0")
    run_dir = _managed_run_dir(tmp_path, "report")

    rc, payload = _run_cli("evaluate", drop_dir, "--profile", "generic_command_state_jsonl_v0", "--out", run_dir, "--json")
    assert rc == 0
    assert payload["passed"] is True

    report_rc, report = _run_cli("report", run_dir, "--json")

    assert report_rc == 0
    assert report["ok"] is True
    assert report["command"] == "report"
    assert report["run_dir"] == str(run_dir)
    assert report["profile_id"] == "generic_command_state_jsonl_v0"
    assert report["passed"] is True
    assert report["proof_source_of_truth"] == "included_source_drop_and_independent_verifier"
    assert report["verifier_command"][-2:] == ["--deep-hdf5", "--json"]
    assert all(value is False for value in report["non_claims"].values())


def test_report_missing_run_fails_closed(tmp_path: Path) -> None:
    rc, payload = _run_cli("report", tmp_path / "missing", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert "run_dir_missing" in payload["rejection_reasons"]


def test_doctor_reports_local_readiness_without_external_runtime() -> None:
    rc, payload = _run_cli("doctor", "--json")

    assert rc == 0
    assert payload["ok"] is True
    assert payload["checks"]["verifier_exists"] is True
    assert payload["checks"]["profile_registry_exact"] is True
    assert payload["checks"]["no_external_runtime_required"] is True
    assert payload["external_partner_data_evaluated"] is False
    assert payload["real_robot_data_evaluated"] is False
    assert payload["hardware_readiness"] is False
