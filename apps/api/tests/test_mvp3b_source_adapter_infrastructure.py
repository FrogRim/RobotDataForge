from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
API_ROOT = ROOT / "apps" / "api"
RUNNER = ROOT / "scripts" / "run_mvp3b_source_adapter_infrastructure.py"
VERIFIER = ROOT / "scripts" / "verify_mvp3b_source_adapter_package.py"
DEFAULT_PACKAGE = ROOT / "docs" / "proof" / "mvp3b_source_adapter_matrix_proof_package"

if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.robot_embodiment_adapters import RobotEmbodimentAdapterRegistry  # noqa: E402


REQUIRED_ADAPTERS = (
    "franka_research_arm",
    "robotis_sh5_ros2_dds",
    "universal_robots_ur_industrial_arm",
)
REQUIRED_ACTION_ROLES = (
    "teleop_intent",
    "executed_control",
    "learning_action",
    "retargeted_robot_action",
)
EXACT_SPENT_NO_REUSE = [[40000, 40049], [42000, 42049]]
CANONICAL_FORBIDDEN_CLAIMS = (
    "real_robot_success",
    "real_robot_success_claimed",
    "physical_robot_readiness",
    "physical_robot_readiness_claimed",
    "deployable_policy_readiness",
    "deployable_policy_readiness_claimed",
    "visual_policy_performance",
    "visual_policy_performance_claimed",
    "hmd_openxr_collection_readiness",
    "hmd_openxr_collection_readiness_claimed",
    "hmd_readiness",
    "hmd_readiness_claimed",
    "marketplace_readiness",
    "marketplace_readiness_claimed",
    "production_certification",
    "production_certification_claimed",
    "universal_robot_support",
    "universal_robot_support_claimed",
    "policy_uplift",
    "policy_uplift_claimed",
    "learning_proven_value",
    "learning_proven_value_claimed",
    "live_runtime_support",
    "live_runtime_support_claimed",
    "live_ur_runtime_support",
    "live_ur_runtime_support_claimed",
    "live_ros2_dds_runtime_support",
    "live_ros2_dds_runtime_support_claimed",
    "franka_hardware_support",
    "franka_hardware_support_claimed",
    "public_sample_import",
    "public_sample_import_claimed",
    "public_sample_evidence_claimed",
    "db_migration",
    "db_migration_claimed",
    "production_auth",
    "production_auth_claimed",
    "real_robot_readiness_claimed",
    "production_robot_support_claimed",
)


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_runner():
    return _load_script("run_mvp3b_source_adapter_infrastructure", RUNNER)


def _load_verifier():
    return _load_script("verify_mvp3b_source_adapter_package", VERIFIER)


def _read_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build_package(tmp_path: Path) -> tuple[dict, Path]:
    runner = _load_runner()
    output_dir = tmp_path / "mvp3b_package"
    report = runner.build_mvp3b_source_adapter_infrastructure(
        output_dir=output_dir,
        clean=True,
    )
    manifest_path = Path(report["package_manifest"])
    assert manifest_path == output_dir / "package_manifest.json"
    return report, manifest_path


def test_runner_builds_verifier_accepted_source_adapter_package(tmp_path: Path) -> None:
    report, manifest_path = _build_package(tmp_path)

    verifier_report = _load_verifier().verify_package(manifest_path)

    assert report["status"] == "source_adapter_infrastructure_closed"
    assert report["passed"] is True
    assert verifier_report.ok is True, verifier_report.failures()
    assert verifier_report.recomputed["adapters"] == list(REQUIRED_ADAPTERS)
    assert verifier_report.recomputed["accepted_count"] >= len(REQUIRED_ADAPTERS)
    assert verifier_report.recomputed["rejected_count"] == len(REQUIRED_ADAPTERS)


def test_runner_calls_existing_registry_adapter_projection_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _load_runner()
    calls: list[str] = []
    original_create = RobotEmbodimentAdapterRegistry.create

    def recording_create(adapter_id: str, **kwargs):
        calls.append(adapter_id)
        return original_create(adapter_id, **kwargs)

    monkeypatch.setattr(RobotEmbodimentAdapterRegistry, "create", recording_create)

    report = runner.build_mvp3b_source_adapter_infrastructure(
        output_dir=tmp_path / "mvp3b_package",
        clean=True,
    )

    assert report["passed"] is True
    assert calls == list(REQUIRED_ADAPTERS)
    for adapter_id in REQUIRED_ADAPTERS:
        adapter_result = _read_json(
            Path(report["package_dir"])
            / "data"
            / "adapter_results"
            / f"{adapter_id}_adapter_result.json"
        )
        assert adapter_result["adapter_call_evidence"]["registry_create_called"] is True
        assert adapter_result["adapter_call_evidence"]["project_source_evidence_called"] is True
        assert adapter_result["adapter_call_evidence"]["emit_contract_called"] is True


def test_runner_writes_required_source_logs_projection_contracts_and_results(
    tmp_path: Path,
) -> None:
    _report, manifest_path = _build_package(tmp_path)
    data = manifest_path.parent / "data"

    for adapter_id in REQUIRED_ADAPTERS:
        source_dir = data / "source_logs" / adapter_id
        projection_dir = data / "projections" / adapter_id
        contract = _read_json(data / "contracts" / f"{adapter_id}_normalized_trajectory_contract.json")
        adapter_result = _read_json(data / "adapter_results" / f"{adapter_id}_adapter_result.json")
        metadata = _read_json(source_dir / "metadata.json")
        accepted_rows = _read_jsonl(source_dir / "accepted_command_state.jsonl")
        rejected_rows = _read_jsonl(source_dir / "rejected_command_state.jsonl")
        projection_manifest = _read_json(projection_dir / "projection_manifest.json")

        assert metadata["adapter_id"] == adapter_id
        assert metadata["source_profile"] == "generated_or_file_backed_recorded_log_fixture"
        assert metadata["runtime"] == "recorded_log_fixture"
        assert accepted_rows
        assert rejected_rows
        assert all(row["adapter_id"] == adapter_id for row in accepted_rows + rejected_rows)
        assert all(
            role in row["command_state"]["actions_by_role"]
            for row in accepted_rows + rejected_rows
            for role in REQUIRED_ACTION_ROLES
        )
        assert (projection_dir / "trajectories").is_dir()
        assert (projection_dir / "evaluations").is_dir()
        assert (projection_dir / "curation_manifest.json").exists()
        assert projection_manifest["accepted_count"] == len(accepted_rows)
        assert projection_manifest["rejected_count"] == len(rejected_rows)
        assert contract["adapter_id"] == adapter_id
        assert contract["source"]["robot"] == adapter_id
        assert contract["source"]["simulator"] == "none_recorded_log_projection"
        assert contract["required_action_roles"] == list(REQUIRED_ACTION_ROLES)
        assert adapter_result["accepted_count"] == len(accepted_rows)
        assert adapter_result["rejected_count"] == len(rejected_rows)


def test_runner_writes_manifest_and_artifact_index_with_file_byte_hashes(
    tmp_path: Path,
) -> None:
    _report, manifest_path = _build_package(tmp_path)
    package_dir = manifest_path.parent
    manifest = _read_json(manifest_path)
    artifact_index = _read_json(package_dir / "data" / "artifact_index.json")

    data_files = sorted(
        path.relative_to(package_dir).as_posix()
        for path in (package_dir / "data").rglob("*")
        if path.is_file()
    )
    manifest_entries = {entry["data_path"]: entry for entry in manifest["artifact_index"]}
    artifact_entries = {entry["data_path"]: entry for entry in artifact_index["artifact_index"]}

    assert set(manifest_entries) == set(data_files)
    assert set(artifact_entries) == set(data_files) - {"data/artifact_index.json"}
    for rel_path in data_files:
        entry = manifest_entries[rel_path]
        assert entry["hash_convention"] == "file_bytes"
        assert entry["file_sha256"] == _sha256(package_dir / rel_path)
        assert entry["byte_size"] == (package_dir / rel_path).stat().st_size


def test_runner_rebuild_is_byte_stable_for_committed_package_manifest(
    tmp_path: Path,
) -> None:
    runner = _load_runner()
    output_dir = tmp_path / "mvp3b_package"

    first = runner.build_mvp3b_source_adapter_infrastructure(
        output_dir=output_dir,
        clean=True,
    )
    first_manifest = Path(first["package_manifest"]).read_bytes()
    second = runner.build_mvp3b_source_adapter_infrastructure(
        output_dir=output_dir,
        clean=True,
    )

    assert Path(second["package_manifest"]).read_bytes() == first_manifest


def test_runner_writes_non_claims_no_reuse_and_contract_smoke_only(
    tmp_path: Path,
) -> None:
    _report, manifest_path = _build_package(tmp_path)
    data = manifest_path.parent / "data"
    config = _read_json(data / "config.json")
    attestation = _read_json(data / "non_claims_attestation.json")
    summary = _read_json(data / "source_adapter_matrix_summary.json")

    assert config["spent_no_reuse"] == EXACT_SPENT_NO_REUSE
    assert config["opened_ranges"] == {
        "calibration": [],
        "heldout": [],
        "tuning": [],
        "closure": [],
    }
    assert config["learning_proven_addendum"] == "absent"
    assert config["non_claims"] == {key: False for key in CANONICAL_FORBIDDEN_CLAIMS}
    assert attestation["forbidden_claims"] == config["non_claims"]
    assert config["contract_smoke"] == {
        "trainer_export_smoke": True,
        "learning_results_measured": False,
        "policy_uplift": False,
        "learning_proven_value": False,
    }
    assert summary["cached_summary_only"] is True
    assert summary["learning_results_measured"] is False
    assert summary["policy_uplift"] is False
    assert summary["learning_proven_value"] is False


def test_runner_refuses_unsafe_clean_paths(tmp_path: Path) -> None:
    runner = _load_runner()

    for output_dir in (ROOT, ROOT / "docs", ROOT / "docs" / "proof"):
        with pytest.raises(ValueError, match="refusing to clean unsafe output_dir"):
            runner.build_mvp3b_source_adapter_infrastructure(
                output_dir=output_dir,
                clean=True,
            )

    safe_tmp_output = tmp_path / "safe_tmp_package"
    report = runner.build_mvp3b_source_adapter_infrastructure(
        output_dir=safe_tmp_output,
        clean=True,
    )
    assert Path(report["package_dir"]) == safe_tmp_output


def test_runner_does_not_import_or_call_independent_verifier() -> None:
    source = RUNNER.read_text(encoding="utf-8")
    assert "verify_mvp3b_source_adapter_package" not in source

    tree = ast.parse(source)
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    assert "scripts.verify_mvp3b_source_adapter_package" not in imported_modules
    assert "verify_mvp3b_source_adapter_package" not in imported_modules


def test_default_output_is_managed_mvp3b_proof_package() -> None:
    runner = _load_runner()

    assert runner.DEFAULT_OUTPUT_DIR == DEFAULT_PACKAGE
