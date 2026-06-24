from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[3]
GENERATOR = ROOT / "scripts" / "run_rdf_public_dataset_trustpack_generator.py"
MATRIX_VERIFIER = ROOT / "scripts" / "verify_lerobot_public_dataset_matrix_package.py"
HTML_SCANNER = ROOT / "scripts" / "scan_rdf_trustpack_html_claims.py"
COMPARATOR = ROOT / "scripts" / "compare_rdf_public_dataset_trustpack_regeneration.py"
BASELINE_PACKAGE = ROOT / "docs" / "proof" / "lerobot_public_dataset_matrix_semantic_parity_proof_package"
GENERATED_PACKAGE = ROOT / "docs" / "proof" / "rdf_public_dataset_trustpack_v0_lerobot_matrix_package"


def test_trustpack_generator_creates_verifier_clean_package(tmp_path: Path) -> None:
    package = _generate_package(tmp_path)

    assert (package / "buyer_report.html").is_file()
    assert (package / "data" / "reports" / "buyer_report.html").is_file()
    assert (package / "buyer_report.html").read_bytes() == (package / "data" / "reports" / "buyer_report.html").read_bytes()
    readme = (package / "README.md").read_text(encoding="utf-8")
    assert readme.startswith("# RDF Public Dataset TrustPack v0")
    assert "docs/proof/rdf_public_dataset_trustpack_v0_lerobot_matrix_package/package_manifest.json" in readme
    assert "scripts/scan_rdf_trustpack_html_claims.py" in readme
    assert "scripts/compare_rdf_public_dataset_trustpack_regeneration.py" in readme
    assert "# LeRobot Public Dataset Matrix Semantic Parity Package" not in readme
    assert _matrix_data_paths(package) >= {
        "data/reports/buyer_report.html",
        "data/profile_registry.json",
        "data/trustpack_artifact_index.json",
        "data/claim_scan_report.json",
        "data/regeneration_report.json",
    }
    assert "buyer_report.html" not in _matrix_data_paths(package)
    trustpack_index = _read_json(package / "data" / "trustpack_artifact_index.json")
    assert {entry["path"] for entry in trustpack_index["artifact_index"]} == {"README.md", "buyer_report.html"}
    assert _read_json(package / "data" / "claim_scan_report.json")["passed"] is True
    assert _read_json(package / "data" / "regeneration_report.json")["semantic_equivalent"] is True

    matrix = _run([sys.executable, str(MATRIX_VERIFIER), str(package / "package_manifest.json")])
    html = _run([sys.executable, str(HTML_SCANNER), "--package-dir", str(package)])
    compare = _run(
        [
            sys.executable,
            str(COMPARATOR),
            "--baseline-package-dir",
            str(BASELINE_PACKAGE),
            "--generated-package-dir",
            str(package),
        ]
    )

    assert matrix.returncode == 0, matrix.stdout + matrix.stderr
    assert "VERDICT: VERIFIED" in matrix.stdout
    assert html.returncode == 0, html.stdout + html.stderr
    assert "buyer_report_html_claim_scan=PASS" in html.stdout
    assert compare.returncode == 0, compare.stdout + compare.stderr
    assert "regeneration_comparison=PASS" in compare.stdout


def test_html_overclaim_tamper_fails(tmp_path: Path) -> None:
    package = _generate_package(tmp_path)
    for path in (package / "buyer_report.html", package / "data" / "reports" / "buyer_report.html"):
        path.write_text(path.read_text(encoding="utf-8") + "\n<p>This package demonstrates real robot success.</p>\n", encoding="utf-8")

    result = _run([sys.executable, str(HTML_SCANNER), "--package-dir", str(package)])

    assert result.returncode != 0
    assert "buyer_report_html_claim_scan=FAIL" in result.stdout


def test_html_tag_split_and_entity_overclaim_fails(tmp_path: Path) -> None:
    package = _generate_package(tmp_path)
    payload = "<p>This package demonstrates real&nbsp;<strong>robot</strong> success.</p>\n"
    for path in (package / "buyer_report.html", package / "data" / "reports" / "buyer_report.html"):
        path.write_text(path.read_text(encoding="utf-8") + payload, encoding="utf-8")

    result = _run([sys.executable, str(HTML_SCANNER), "--package-dir", str(package)])

    assert result.returncode != 0
    assert "buyer_report_html_claim_scan=FAIL" in result.stdout


def test_profile_registry_drift_fails_comparator(tmp_path: Path) -> None:
    package = _generate_package(tmp_path)
    registry_path = package / "data" / "profile_registry.json"
    registry = _read_json(registry_path)
    registry["profiles"][1]["action_dim"] = 14
    _write_json(registry_path, registry)
    _refresh_artifact_hashes(package)

    result = _run_comparator(package)

    assert result.returncode != 0
    assert "regeneration_comparison=FAIL" in result.stdout


def test_semantic_drift_with_refreshed_hashes_fails_comparator(tmp_path: Path) -> None:
    package = _generate_package(tmp_path)
    raw_path = package / "data" / "profiles" / "lerobot_svla_so100_pickplace" / "source" / "lerobot_raw_rows.jsonl"
    rows = _read_jsonl(raw_path)
    rows[0]["observation.state"][0] += 1.0
    _write_jsonl(raw_path, rows)
    _refresh_artifact_hashes(package)

    result = _run_comparator(package)

    assert result.returncode != 0
    assert "regeneration_comparison=FAIL" in result.stdout


def test_self_attested_regeneration_report_drift_still_fails(tmp_path: Path) -> None:
    package = _generate_package(tmp_path)
    raw_path = package / "data" / "profiles" / "lerobot_svla_so100_pickplace" / "source" / "lerobot_raw_rows.jsonl"
    rows = _read_jsonl(raw_path)
    rows[0]["action"][0] += 1.0
    _write_jsonl(raw_path, rows)
    report_path = package / "data" / "regeneration_report.json"
    report = _read_json(report_path)
    report["passed"] = True
    report["semantic_equivalent"] = True
    report["issue_count"] = 0
    _write_json(report_path, report)
    _refresh_artifact_hashes(package)

    result = _run_comparator(package)

    assert result.returncode != 0
    assert "regeneration_comparison=FAIL" in result.stdout


def test_generator_rejects_unsafe_clean_targets() -> None:
    for target in (ROOT, Path("/tmp"), BASELINE_PACKAGE):
        result = _run([sys.executable, str(GENERATOR), "--package-dir", str(target), "--clean"])
        assert result.returncode != 0
        assert "refusing to clean unsafe package_dir" in result.stderr


def test_auditor_scripts_do_not_import_producer_modules() -> None:
    forbidden_for_matrix = {"app", "apps", "datasets", "lerobot", "huggingface_hub"}
    forbidden_for_trustpack_auditors = forbidden_for_matrix | {"numpy", "h5py", "pyarrow", "pandas", "scripts"}

    assert not (_imports(MATRIX_VERIFIER) & forbidden_for_matrix)
    assert not (_imports(HTML_SCANNER) & forbidden_for_trustpack_auditors)
    assert not (_imports(COMPARATOR) & forbidden_for_trustpack_auditors)


def test_existing_matrix_and_generated_trustpack_verify() -> None:
    baseline = _run([sys.executable, str(MATRIX_VERIFIER), str(BASELINE_PACKAGE / "package_manifest.json")])
    generated = _run([sys.executable, str(MATRIX_VERIFIER), str(GENERATED_PACKAGE / "package_manifest.json")])

    assert baseline.returncode == 0, baseline.stdout + baseline.stderr
    assert generated.returncode == 0, generated.stdout + generated.stderr


def _generate_package(tmp_path: Path) -> Path:
    package = tmp_path / "rdf_public_dataset_trustpack_v0_lerobot_matrix_package_test"
    result = _run([sys.executable, str(GENERATOR), "--package-dir", str(package), "--clean"])
    assert result.returncode == 0, result.stdout + result.stderr
    return package


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)


def _run_comparator(package: Path) -> subprocess.CompletedProcess[str]:
    return _run(
        [
            sys.executable,
            str(COMPARATOR),
            "--baseline-package-dir",
            str(BASELINE_PACKAGE),
            "--generated-package-dir",
            str(package),
        ]
    )


def _matrix_data_paths(package: Path) -> set[str]:
    manifest = _read_json(package / "package_manifest.json")
    index = _read_json(package / "data" / "artifact_index.json")
    return {entry["data_path"] for entry in manifest["artifact_index"]} | {entry["data_path"] for entry in index["artifact_index"]}


def _refresh_artifact_hashes(package: Path) -> None:
    for relative in ("package_manifest.json", "data/artifact_index.json"):
        path = package / relative
        payload = _read_json(path)
        for entry in payload["artifact_index"]:
            artifact = package / entry["data_path"]
            entry["file_sha256"] = hashlib.sha256(artifact.read_bytes()).hexdigest()
            entry["byte_size"] = artifact.stat().st_size
        _write_json(path, payload)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    return imports


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
