from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
import shutil
import types


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "verify_lerobot_public_dataset_matrix_package.py"
MANIFEST = ROOT / "docs" / "proof" / "lerobot_public_dataset_matrix_semantic_parity_proof_package" / "package_manifest.json"


def test_canonical_matrix_package_verifies() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), str(MANIFEST)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "VERDICT: VERIFIED" in result.stdout
    assert "profile_count=2" in result.stdout
    assert "profiles=lerobot_aloha_static_coffee,lerobot_svla_so100_pickplace" in result.stdout


def test_matrix_verifier_is_stdlib_only_and_independent() -> None:
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])

    forbidden = {
        "app",
        "numpy",
        "h5py",
        "pyarrow",
        "pandas",
        "datasets",
        "lerobot",
        "huggingface_hub",
        "scripts",
    }
    assert not (imports & forbidden)


def test_hash_refreshed_raw_row_tamper_fails(tmp_path: Path) -> None:
    package = _copy_package(tmp_path)
    raw_path = package / "data" / "profiles" / "lerobot_svla_so100_pickplace" / "source" / "lerobot_raw_rows.jsonl"
    rows = _read_jsonl(raw_path)
    rows[0]["observation.state"][0] += 1.0
    rows[0]["source_row_sha256"] = _canonical_row_digest(rows[0])
    _write_jsonl(raw_path, rows)
    _refresh_artifact_hashes(package)

    result = _run_verifier(package)

    assert result.returncode != 0
    assert "VERDICT: FAILED" in result.stdout
    assert "conversion_parity" in result.stdout or "raw_rows" in result.stdout


def test_hash_refreshed_converted_row_tamper_fails(tmp_path: Path) -> None:
    package = _copy_package(tmp_path)
    converted_path = package / "data" / "profiles" / "lerobot_svla_so100_pickplace" / "conversion" / "rdf_converted_rows.jsonl"
    manifest_path = package / "data" / "profiles" / "lerobot_svla_so100_pickplace" / "conversion" / "conversion_manifest.json"
    rows = _read_jsonl(converted_path)
    rows[0]["learning_action"][0] += 1.0
    _write_jsonl(converted_path, rows)
    manifest = _read_json(manifest_path)
    manifest["converted_row_sha256s"] = [_sha256_bytes(_canonical_json_bytes(row)) for row in rows]
    _write_json(manifest_path, manifest)
    _refresh_artifact_hashes(package)

    result = _run_verifier(package)

    assert result.returncode != 0
    assert "conversion_parity" in result.stdout


def test_matrix_variety_tamper_fails_after_hash_refresh(tmp_path: Path) -> None:
    package = _copy_package(tmp_path)
    summary_path = package / "data" / "matrix_summary.json"
    summary = _read_json(summary_path)
    summary["profile_summaries"][1]["robot_type"] = "aloha"
    summary["variety_gate"]["distinct_robot_types"] = ["aloha"]
    _write_json(summary_path, summary)
    _refresh_artifact_hashes(package)

    result = _run_verifier(package)

    assert result.returncode != 0
    assert "matrix_variety" in result.stdout


def test_non_claim_and_forbidden_prose_tamper_fails(tmp_path: Path) -> None:
    package = _copy_package(tmp_path)
    non_claims_path = package / "data" / "non_claims_attestation.json"
    claims = _read_json(non_claims_path)
    claims["non_claims"]["real_robot_success"] = True
    _write_json(non_claims_path, claims)
    (package / "README.md").write_text(
        (package / "README.md").read_text(encoding="utf-8") + "\nThis package demonstrates real robot success.\n",
        encoding="utf-8",
    )
    _refresh_artifact_hashes(package)

    result = _run_verifier(package)

    assert result.returncode != 0
    assert "non_claims" in result.stdout or "claim_and_spent_boundary" in result.stdout


def test_forbidden_prose_after_unrelated_negation_fails_after_hash_refresh(tmp_path: Path) -> None:
    package = _copy_package(tmp_path)
    readme = package / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8")
        + "\nThis is not a generic benchmark. It demonstrates real robot success.\n",
        encoding="utf-8",
    )
    _refresh_artifact_hashes(package)

    result = _run_verifier(package)

    assert result.returncode != 0
    assert "claim_and_spent_boundary" in result.stdout
    assert "real robot success" in result.stdout


def test_spent_seed_tamper_fails_after_hash_refresh(tmp_path: Path) -> None:
    package = _copy_package(tmp_path)
    config_path = package / "data" / "config.json"
    config = _read_json(config_path)
    config["debug_seed"] = 42000
    _write_json(config_path, config)
    _refresh_artifact_hashes(package)

    result = _run_verifier(package)

    assert result.returncode != 0
    assert "spent seed" in result.stdout


def test_reextract_uses_recorded_feature_schema_column_projection(monkeypatch, tmp_path: Path) -> None:
    package = _copy_package(tmp_path)
    verifier = _load_verifier_module()
    raw_by_profile = {
        profile.profile_id: _read_jsonl(package / "data" / "profiles" / profile.profile_id / "source" / "lerobot_raw_rows.jsonl")
        for profile in verifier.PROFILES
    }
    raw_by_profile["lerobot_aloha_static_coffee"] = [
        {**row, "observation.effort": [0.0 for _ in row["observation.state"]]}
        for row in raw_by_profile["lerobot_aloha_static_coffee"]
    ]
    expected_columns = {
        profile.profile_id: [
            column["name"]
            for column in _read_json(package / "data" / "profiles" / profile.profile_id / "source" / "lerobot_feature_schema.json")["columns"]
        ]
        for profile in verifier.PROFILES
    }
    calls: list[tuple[str, list[str] | None]] = []

    class FakeTable:
        def __init__(self, profile_id: str, columns: list[str] | None) -> None:
            self.profile_id = profile_id
            self.columns = columns

        def to_pylist(self) -> list[dict]:
            rows = raw_by_profile[self.profile_id]
            if self.columns is None:
                return rows
            return [{key: value for key, value in row.items() if key in set(self.columns)} for row in rows]

    remaining_profiles = [profile.profile_id for profile in verifier.PROFILES]

    def fake_read_table(_path: Path, columns: list[str] | None = None) -> FakeTable:
        profile_id = remaining_profiles.pop(0)
        calls.append((profile_id, columns))
        return FakeTable(profile_id, columns)

    fake_pyarrow = types.ModuleType("pyarrow")
    fake_pyarrow.__path__ = []  # type: ignore[attr-defined]
    fake_parquet = types.ModuleType("pyarrow.parquet")
    fake_parquet.read_table = fake_read_table  # type: ignore[attr-defined]
    fake_pyarrow.parquet = fake_parquet  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pyarrow", fake_pyarrow)
    monkeypatch.setitem(sys.modules, "pyarrow.parquet", fake_parquet)
    monkeypatch.setattr(verifier, "_fetch_url", lambda _url: b"fake parquet bytes")

    report = verifier.Auditor(package / "package_manifest.json", reextract_public_source=True).run()

    assert report.ok, [check for check in report.checks if not check.passed]
    assert calls == [(profile_id, expected_columns[profile_id]) for profile_id in expected_columns]


def test_runner_requires_clean_for_existing_package_dir(tmp_path: Path) -> None:
    package_dir = tmp_path / "existing_package"
    package_dir.mkdir()

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_lerobot_public_dataset_matrix_semantic_parity.py"), "--package-dir", str(package_dir)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "exists; pass --clean" in result.stderr


def test_runner_rejects_unsafe_clean_target() -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "run_lerobot_public_dataset_matrix_semantic_parity.py"),
            "--package-dir",
            str(ROOT),
            "--clean",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "refusing to clean unsafe package_dir" in result.stderr


def test_frozen_and_prior_package_verifiers_still_pass() -> None:
    commands = [
        [
            "scripts/verify_lerobot_public_slice_package.py",
            "docs/proof/lerobot_public_aloha_slice_semantic_parity_proof_package/package_manifest.json",
        ],
        [
            "scripts/verify_external_robot_data_ingest_package.py",
            "docs/proof/external_robot_data_ingest_eval_v0_proof_package/package_manifest.json",
        ],
        [
            "scripts/verify_mvp2_package.py",
            "docs/proof/mvp2_learning_proven_evidence_package/package_manifest.json",
        ],
        [
            "scripts/verify_proof_package.py",
            "docs/proof/mvp3a_target_fixture_pose_variant_proof_package/package_manifest.json",
        ],
        [
            "scripts/verify_mvp3b_source_adapter_package.py",
            "docs/proof/mvp3b_source_adapter_matrix_proof_package/package_manifest.json",
        ],
        [
            "scripts/verify_mvp3c_isaac_sim_embodiment_source_package.py",
            "docs/proof/mvp3c_isaac_sim_embodiment_source_proof_package/package_manifest.json",
        ],
    ]
    for command in commands:
        result = subprocess.run(
            [sys.executable, *command],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        assert result.returncode == 0, command[0] + "\n" + result.stdout + result.stderr


def _copy_package(tmp_path: Path) -> Path:
    target = tmp_path / "matrix_package"
    shutil.copytree(MANIFEST.parent, target)
    return target


def _run_verifier(package: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(package / "package_manifest.json")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def _load_verifier_module():
    spec = importlib.util.spec_from_file_location("matrix_verifier_under_test", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _refresh_artifact_hashes(package: Path) -> None:
    data_root = package / "data"
    data_entries = [
        _artifact_entry(package, path)
        for path in sorted(data_root.rglob("*"))
        if path.is_file() and path.name != "artifact_index.json"
    ]
    _write_json(data_root / "artifact_index.json", {"schema_version": "rdf_lerobot_public_dataset_matrix_artifact_index_v0.1.0", "artifact_index": data_entries})
    manifest = _read_json(package / "package_manifest.json")
    manifest["artifact_index"] = [
        _artifact_entry(package, path)
        for path in sorted(data_root.rglob("*"))
        if path.is_file()
    ]
    _write_json(package / "package_manifest.json", manifest)


def _artifact_entry(package: Path, path: Path) -> dict:
    return {
        "data_path": path.relative_to(package).as_posix(),
        "file_sha256": _sha256_file(path),
        "byte_size": path.stat().st_size,
        "hash_convention": "file_bytes",
    }


def _read_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def _canonical_row_digest(row: dict) -> str:
    return _sha256_bytes(_canonical_json_bytes({key: value for key, value in row.items() if key != "source_row_sha256"}))


def _canonical_json_bytes(payload) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
