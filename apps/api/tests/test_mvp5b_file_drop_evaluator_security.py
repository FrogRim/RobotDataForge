from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import zipfile

from app.services.mvp5a_file_drop_rehearsal import build_fixture_canonical_trace, write_golden_profile_drop


ROOT = Path(__file__).resolve().parents[3]
CLI = ROOT / "scripts" / "rdf_file_drop_evaluator.py"


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


def test_preflight_zip_path_traversal_fails_closed(tmp_path: Path) -> None:
    zip_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("../metadata.json", "{}")

    rc, payload = _run_cli("preflight", zip_path, "--profile", "ur_rtde_csv_v0", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert payload["passed"] is False
    assert "path_traversal" in payload["rejection_reasons"]


def test_preflight_zip_absolute_path_fails_closed(tmp_path: Path) -> None:
    zip_path = tmp_path / "absolute.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("/tmp/metadata.json", "{}")

    rc, payload = _run_cli("preflight", zip_path, "--profile", "ur_rtde_csv_v0", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert payload["passed"] is False
    assert "path_traversal" in payload["rejection_reasons"]


def test_preflight_folder_symlink_escape_fails_closed(tmp_path: Path) -> None:
    drop_dir = tmp_path / "drop"
    write_golden_profile_drop("ur_rtde_csv_v0", build_fixture_canonical_trace(), drop_dir)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    (drop_dir / "escape_link").symlink_to(outside)

    rc, payload = _run_cli("preflight", drop_dir, "--profile", "ur_rtde_csv_v0", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert payload["passed"] is False
    assert "symlink_escape" in payload["rejection_reasons"]


def test_preflight_folder_internal_symlink_loop_fails_closed(tmp_path: Path) -> None:
    drop_dir = tmp_path / "drop"
    write_golden_profile_drop("ur_rtde_csv_v0", build_fixture_canonical_trace(), drop_dir)
    (drop_dir / "loop_link").symlink_to(drop_dir, target_is_directory=True)

    rc, payload = _run_cli("preflight", drop_dir, "--profile", "ur_rtde_csv_v0", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert payload["passed"] is False
    assert "symlink_escape" in payload["rejection_reasons"]


def test_preflight_folder_too_many_entries_fails_closed(tmp_path: Path) -> None:
    drop_dir = tmp_path / "drop"
    drop_dir.mkdir()
    for index in range(130):
        (drop_dir / f"row-{index}.json").write_text("{}\n", encoding="utf-8")

    rc, payload = _run_cli("preflight", drop_dir, "--profile", "ur_rtde_csv_v0", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert "folder_too_many_entries" in payload["rejection_reasons"]


def test_preflight_folder_oversized_file_fails_before_copy(tmp_path: Path) -> None:
    drop_dir = tmp_path / "drop"
    drop_dir.mkdir()
    (drop_dir / "metadata.json").write_text("x" * 2_000_001, encoding="utf-8")

    rc, payload = _run_cli("preflight", drop_dir, "--profile", "ur_rtde_csv_v0", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert "folder_entry_too_large" in payload["rejection_reasons"]


def test_preflight_folder_total_size_fails_before_copy(tmp_path: Path) -> None:
    drop_dir = tmp_path / "drop"
    drop_dir.mkdir()
    for index in range(6):
        (drop_dir / f"chunk-{index}.bin").write_text("x" * 1_800_000, encoding="utf-8")

    rc, payload = _run_cli("preflight", drop_dir, "--profile", "ur_rtde_csv_v0", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert "folder_total_too_large" in payload["rejection_reasons"]


def test_preflight_zip_too_many_entries_fails_closed(tmp_path: Path) -> None:
    zip_path = tmp_path / "too_many.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index in range(130):
            archive.writestr(f"row-{index}.json", "{}")

    rc, payload = _run_cli("preflight", zip_path, "--profile", "ur_rtde_csv_v0", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert "zip_too_many_entries" in payload["rejection_reasons"]


def test_preflight_zip_oversized_entry_fails_before_extract(tmp_path: Path) -> None:
    zip_path = tmp_path / "oversized.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("metadata.json", "x" * (2_000_001))

    rc, payload = _run_cli("preflight", zip_path, "--profile", "ur_rtde_csv_v0", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert "zip_entry_too_large" in payload["rejection_reasons"]


def test_preflight_zip_duplicate_normalized_target_fails_closed(tmp_path: Path) -> None:
    zip_path = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("metadata.json", "{}")
        archive.writestr("metadata.json", "{\"duplicate\": true}")

    rc, payload = _run_cli("preflight", zip_path, "--profile", "ur_rtde_csv_v0", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert "duplicate_zip_member" in payload["rejection_reasons"]


def test_evaluate_force_outside_artifact_root_fails_without_deleting(tmp_path: Path) -> None:
    drop_dir = tmp_path / "drop"
    write_golden_profile_drop("ur_rtde_csv_v0", build_fixture_canonical_trace(), drop_dir)
    protected = tmp_path / "protected"
    protected.mkdir()
    sentinel = protected / "sentinel.txt"
    sentinel.write_text("keep\n", encoding="utf-8")

    rc, payload = _run_cli("evaluate", drop_dir, "--profile", "ur_rtde_csv_v0", "--out", protected, "--force", "--json")

    assert rc != 0
    assert payload["ok"] is False
    assert "unsafe_output_path" in payload["rejection_reasons"]
    assert sentinel.read_text(encoding="utf-8") == "keep\n"
