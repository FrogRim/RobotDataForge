from __future__ import annotations

import importlib.util
import ast
import hashlib
import json
import shutil
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
PACKAGE_ROOT = ROOT / "docs/proof/lerobot_public_aloha_slice_semantic_parity_proof_package"
MANIFEST = PACKAGE_ROOT / "package_manifest.json"
VERIFIER_PATH = ROOT / "scripts/verify_lerobot_public_slice_package.py"


def _load_verifier():
    spec = importlib.util.spec_from_file_location("verify_lerobot_public_slice_package", VERIFIER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _refresh_hashes(package_dir: Path) -> None:
    data_dir = package_dir / "data"
    artifact_entries = []
    for path in sorted(data_dir.rglob("*")):
        if path.is_file() and path.name != "artifact_index.json":
            artifact_entries.append(
                {
                    "data_path": path.relative_to(package_dir).as_posix(),
                    "file_sha256": _sha256(path),
                    "byte_size": path.stat().st_size,
                    "hash_convention": "file_bytes",
                }
            )
    _write_json(
        data_dir / "artifact_index.json",
        {
            "schema_version": "rdf_lerobot_public_slice_artifact_index_v0.1.0",
            "artifact_index": artifact_entries,
        },
    )
    manifest = _read_json(package_dir / "package_manifest.json")
    manifest["artifact_index"] = [
        {
            "data_path": path.relative_to(package_dir).as_posix(),
            "file_sha256": _sha256(path),
            "byte_size": path.stat().st_size,
            "hash_convention": "file_bytes",
        }
        for path in sorted(data_dir.rglob("*"))
        if path.is_file()
    ]
    _write_json(package_dir / "package_manifest.json", manifest)


def _copy_package(tmp_path: Path) -> Path:
    target = tmp_path / "package"
    shutil.copytree(PACKAGE_ROOT, target)
    return target


def test_verifier_source_is_stdlib_only_by_default() -> None:
    source = VERIFIER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_level_imports = [
        node
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    forbidden_modules = {"app", "numpy", "h5py", "pyarrow", "pandas", "huggingface_hub"}
    for node in top_level_imports:
        if isinstance(node, ast.Import):
            names = {alias.name.split(".")[0] for alias in node.names}
        else:
            names = {str(node.module).split(".")[0]}
        assert names.isdisjoint(forbidden_modules)


def test_canonical_package_verifies() -> None:
    verifier = _load_verifier()

    report = verifier.verify_package(MANIFEST)

    assert report.ok, [check for check in report.checks if not check.passed]
    assert report.recomputed["row_count"] == 8
    assert report.recomputed["observation_state_dim"] == 14
    assert report.recomputed["action_dim"] == 14


def test_deep_hdf5_verifies() -> None:
    verifier = _load_verifier()

    report = verifier.verify_package(MANIFEST, deep_hdf5=True)

    assert report.ok
    assert any(check.name == "deep_hdf5" and check.passed for check in report.checks)


def test_hash_refreshed_raw_row_tamper_fails(tmp_path: Path) -> None:
    verifier = _load_verifier()
    package = _copy_package(tmp_path)
    raw_path = package / "data/source/lerobot_raw_rows.jsonl"
    rows = _read_jsonl(raw_path)
    rows[0]["action"][0] += 1.0
    _write_jsonl(raw_path, rows)
    _refresh_hashes(package)

    report = verifier.verify_package(package / "package_manifest.json")

    assert not report.ok
    assert any(check.name in {"raw_rows", "extraction_receipt", "conversion_parity"} and not check.passed for check in report.checks)


def test_hash_refreshed_conversion_fabrication_fails(tmp_path: Path) -> None:
    verifier = _load_verifier()
    package = _copy_package(tmp_path)
    converted_path = package / "data/conversion/rdf_converted_rows.jsonl"
    rows = _read_jsonl(converted_path)
    rows[0]["end_effector_position"] = [0.0, 0.0, 0.0]
    _write_jsonl(converted_path, rows)
    _refresh_hashes(package)

    report = verifier.verify_package(package / "package_manifest.json")

    assert not report.ok
    assert any(check.name in {"conversion_parity", "claim_and_spent_boundary"} and not check.passed for check in report.checks)


def test_hash_refreshed_hdf5_payload_drift_fails_default_verifier(tmp_path: Path) -> None:
    import h5py

    verifier = _load_verifier()
    package = _copy_package(tmp_path)
    hdf5_path = package / "data/export/dataset.hdf5"
    with h5py.File(hdf5_path, "r+") as h5:
        episode_id = h5["episodes/episode_ids"][0].decode("utf-8")
        dataset = h5[f"actions/{episode_id}/learning_action"]
        dataset[0, 0] = dataset[0, 0] + 1.0
    report_path = package / "data/export/hdf5_inspection_report.json"
    report_payload = _read_json(report_path)
    report_payload["hdf5_sha256"] = _sha256(hdf5_path)
    _write_json(report_path, report_payload)
    _refresh_hashes(package)

    report = verifier.verify_package(package / "package_manifest.json")

    assert not report.ok
    assert any(check.name == "hdf5_receipt_consistency" and not check.passed for check in report.checks)


def test_refetch_receipt_tamper_fails_after_hash_refresh(tmp_path: Path) -> None:
    verifier = _load_verifier()
    package = _copy_package(tmp_path)
    receipt_path = package / "data/source/refetch_receipt.json"
    receipt = _read_json(receipt_path)
    receipt["files_checked"][0]["refetched_sha256"] = "0" * 64
    receipt["files_checked"][0]["matched"] = False
    receipt["matched"] = False
    _write_json(receipt_path, receipt)
    _refresh_hashes(package)

    report = verifier.verify_package(package / "package_manifest.json")

    assert not report.ok
    assert any(check.name == "refetch_receipt" and not check.passed for check in report.checks)


def test_floating_revision_fails_after_hash_refresh(tmp_path: Path) -> None:
    verifier = _load_verifier()
    package = _copy_package(tmp_path)
    binding_path = package / "data/source/public_source_binding.json"
    binding = _read_json(binding_path)
    binding["resolved_revision"] = "main"
    _write_json(binding_path, binding)
    _refresh_hashes(package)

    report = verifier.verify_package(package / "package_manifest.json")

    assert not report.ok
    assert any(check.name == "public_source_binding" and not check.passed for check in report.checks)


def test_branch_like_revision_fails_after_hash_refresh(tmp_path: Path) -> None:
    verifier = _load_verifier()
    package = _copy_package(tmp_path)
    branch_like_revision = "not-a-commit-floating-branch-with-long-name"
    for relative_path in [
        "data/source/public_source_binding.json",
        "data/source/upstream_file_hashes.json",
        "data/source/refetch_receipt.json",
        "data/source/extraction_receipt.json",
        "data/config.json",
    ]:
        path = package / relative_path
        payload = _read_json(path)
        payload["resolved_revision"] = branch_like_revision
        if relative_path.endswith("refetch_receipt.json"):
            for item in payload["files_checked"]:
                item["revision"] = branch_like_revision
        _write_json(path, payload)
    _refresh_hashes(package)

    report = verifier.verify_package(package / "package_manifest.json")

    assert not report.ok
    assert any(check.name == "public_source_binding" and not check.passed for check in report.checks)


def test_artifact_index_traversal_path_fails(tmp_path: Path) -> None:
    verifier = _load_verifier()
    package = _copy_package(tmp_path)
    manifest_path = package / "package_manifest.json"
    manifest = _read_json(manifest_path)
    readme = package / "README.md"
    manifest["artifact_index"][0] = {
        "data_path": "data/../README.md",
        "file_sha256": _sha256(readme),
        "byte_size": readme.stat().st_size,
        "hash_convention": "file_bytes",
    }
    _write_json(manifest_path, manifest)

    report = verifier.verify_package(manifest_path)

    assert not report.ok
    assert any(check.name == "hash_integrity" and not check.passed for check in report.checks)


def test_positive_forbidden_prose_fails_but_negated_non_claims_pass(tmp_path: Path) -> None:
    verifier = _load_verifier()
    package = _copy_package(tmp_path)
    readme = package / "README.md"
    readme.write_text(readme.read_text(encoding="utf-8") + "\nThis proves real robot success.\n", encoding="utf-8")

    report = verifier.verify_package(package / "package_manifest.json")

    assert not report.ok
    assert any(check.name == "claim_and_spent_boundary" and not check.passed for check in report.checks)
    clean_report = verifier.verify_package(MANIFEST)
    assert clean_report.ok
