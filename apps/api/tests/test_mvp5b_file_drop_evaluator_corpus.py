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
    generate_corrupt_drop,
    mutation_specs,
    write_golden_profile_drop,
)


ROOT = Path(__file__).resolve().parents[3]
CLI = ROOT / "scripts" / "rdf_file_drop_evaluator.py"
VERIFIER = ROOT / "scripts" / "verify_rdf_file_drop_evaluator_run.py"
ARTIFACT_ROOT = ROOT / "artifacts" / "rdf_file_drop_evaluator"


def _run(script: Path, *args: str | Path) -> tuple[int, dict]:
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
    drop_dir = tmp_path / "golden" / profile_id
    write_golden_profile_drop(profile_id, build_fixture_canonical_trace(), drop_dir)
    return drop_dir


def _zip_dir(source_dir: Path, zip_path: Path) -> Path:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source_dir).as_posix())
    return zip_path


def _managed_run_dir(tmp_path: Path, name: str) -> Path:
    safe_name = name.replace("/", "-").replace(":", "-")
    run_dir = ARTIFACT_ROOT / f"pytest-{tmp_path.name}-{safe_name}"
    shutil.rmtree(run_dir, ignore_errors=True)
    return run_dir


@pytest.mark.parametrize("profile_id", PROFILE_IDS)
def test_golden_corpus_profiles_evaluate_export_and_verify(tmp_path: Path, profile_id: str) -> None:
    drop_dir = _golden_drop(tmp_path, profile_id)
    run_dir = _managed_run_dir(tmp_path, f"{profile_id}_golden")

    rc, payload = _run(CLI, "evaluate", drop_dir, "--profile", profile_id, "--out", run_dir, "--json")

    assert rc == 0
    assert payload["passed"] is True
    assert (run_dir / "export" / "dataset.hdf5").exists()
    verifier_rc, verifier_payload = _run(VERIFIER, run_dir / "package_manifest.json", "--deep-hdf5", "--json")
    assert verifier_rc == 0, verifier_payload
    assert verifier_payload["verdict"] == "VERIFIED"
    assert verifier_payload["passed"] is True


@pytest.mark.parametrize("mutation", mutation_specs(), ids=lambda item: f"{item.profile_id}:{item.mutation_id}")
def test_corrupt_corpus_rejects_with_expected_reason_and_no_training_export(tmp_path: Path, mutation) -> None:
    golden_dir = _golden_drop(tmp_path, mutation.profile_id)
    corrupt_dir = tmp_path / "corrupt" / mutation.profile_id / mutation.mutation_id
    generate_corrupt_drop(mutation.profile_id, mutation, golden_dir, corrupt_dir)
    run_dir = _managed_run_dir(tmp_path, f"{mutation.profile_id}-{mutation.mutation_id}")

    rc, payload = _run(CLI, "evaluate", corrupt_dir, "--profile", mutation.profile_id, "--out", run_dir, "--json")

    assert rc != 0
    assert payload["passed"] is False
    assert mutation.expected_rejection_reason in payload["rejection_reasons"]
    evaluation = json.loads((run_dir / "evaluation_result.json").read_text(encoding="utf-8"))
    contract = json.loads((run_dir / "normalized" / "normalized_contract.json").read_text(encoding="utf-8"))
    assert evaluation["passed"] is False
    assert evaluation["export_eligible"] is False
    assert evaluation["trainer_smoke_eligible"] is False
    assert mutation.expected_rejection_reason in evaluation["rejection_reasons"]
    assert contract["export_eligible"] is False
    assert contract["trainer_smoke_eligible"] is False
    assert contract["rows"] == []
    assert not (run_dir / "export" / "dataset.hdf5").exists()

    verifier_rc, verifier_payload = _run(VERIFIER, run_dir / "package_manifest.json", "--json")
    if mutation.mutation_id == "fabricated_task_success" and mutation.profile_id == "ur_rtde_csv_v0":
        assert verifier_rc != 0
        assert "forbidden_claim_leakage" in verifier_payload["failed_checks"]
    else:
        assert verifier_rc == 0, verifier_payload
        assert verifier_payload["verdict"] == "VERIFIED"
        assert verifier_payload["passed"] is False


def test_corrupt_zip_fails_with_structured_reason_and_no_export(tmp_path: Path) -> None:
    mutation = next(item for item in mutation_specs() if item.profile_id == "generic_command_state_jsonl_v0" and item.mutation_id == "missing_command")
    golden_dir = _golden_drop(tmp_path, mutation.profile_id)
    corrupt_dir = tmp_path / "corrupt_zip_source"
    generate_corrupt_drop(mutation.profile_id, mutation, golden_dir, corrupt_dir)
    zip_path = _zip_dir(corrupt_dir, tmp_path / "corrupt_drop.zip")
    run_dir = _managed_run_dir(tmp_path, "corrupt_zip")

    rc, payload = _run(CLI, "evaluate", zip_path, "--profile", mutation.profile_id, "--out", run_dir, "--json")

    assert rc != 0
    assert payload["input_kind"] == "zip"
    assert payload["passed"] is False
    assert mutation.expected_rejection_reason in payload["rejection_reasons"]
    assert not (run_dir / "export" / "dataset.hdf5").exists()
