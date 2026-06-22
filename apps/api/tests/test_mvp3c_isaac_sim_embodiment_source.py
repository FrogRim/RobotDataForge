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
RUNNER = ROOT / "scripts" / "run_mvp3c_isaac_sim_embodiment_source.py"
CAPTURE = ROOT / "scripts" / "capture_mvp3c_isaac_sim_embodiment_source.py"
VERIFIER = ROOT / "scripts" / "verify_mvp3c_isaac_sim_embodiment_source_package.py"
DEFAULT_PACKAGE = ROOT / "docs" / "proof" / "mvp3c_isaac_sim_embodiment_source_proof_package"

if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.robot_embodiment_adapters import RobotEmbodimentAdapterRegistry  # noqa: E402


REQUIRED_EMBODIMENTS = (
    "franka_panda_isaac_sim",
    "universal_robots_ur10e_isaac_sim",
)
EXACT_SPENT_NO_REUSE = [[40000, 40049], [42000, 42049]]


def _load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_runner():
    return _load_script("run_mvp3c_isaac_sim_embodiment_source", RUNNER)


def _load_verifier():
    return _load_script("verify_mvp3c_isaac_sim_embodiment_source_package", VERIFIER)


def _read_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _build_controlled_package(tmp_path: Path) -> tuple[dict, Path]:
    runner = _load_runner()
    output_dir = tmp_path / "mvp3c_package"
    report = runner.build_mvp3c_isaac_sim_embodiment_source(
        output_dir=output_dir,
        clean=True,
        evidence_kind="synthetic_verifier_fixture",
    )
    manifest_path = Path(report["package_manifest"])
    assert manifest_path == output_dir / "package_manifest.json"
    return report, manifest_path


def _runtime_capture_report() -> dict:
    runner = _load_runner()
    embodiments = {}
    for embodiment_id in REQUIRED_EMBODIMENTS:
        capture_id = runner._capture_id(embodiment_id)
        embodiments[embodiment_id] = {
            "runtime_metadata": {
                "schema_version": "rdf_mvp3c_runtime_metadata_v0.1.0",
                "embodiment_id": embodiment_id,
                "runtime_capture_id": capture_id,
                "runtime": "isaac_sim",
                "simulator": "isaac_sim",
                "platform": "linux",
                "source_kind": "isaac_sim_runtime_backed_command_state_log",
                "capture_origin": "isaac_sim_process",
                "asset_path": f"omniverse://fixture/{embodiment_id}.usd",
                "prim_path": f"/World/{embodiment_id}",
                "real_robot_success": False,
                "physical_robot_readiness": False,
                "live_runtime_support": False,
            },
            "preflight": {
                "schema_version": "rdf_mvp3c_preflight_v0.1.0",
                "embodiment_id": embodiment_id,
                "runtime_capture_id": capture_id,
                "asset_loaded": True,
                "articulation_detected": True,
                "joint_state_readable": True,
                "action_command_writable": True,
                "source_log_rows_emitted": 2,
                "runtime_metadata_recorded": True,
            },
            "source_rows": {
                "accepted": runner._source_rows(
                    RobotEmbodimentAdapterRegistry.get_mvp3c_source_ingress_profile(
                        embodiment_id
                    ),
                    accepted=True,
                ),
                "rejected": runner._source_rows(
                    RobotEmbodimentAdapterRegistry.get_mvp3c_source_ingress_profile(
                        embodiment_id
                    ),
                    accepted=False,
                ),
            },
        }
    return {
        "schema_version": "rdf_mvp3c_isaac_sim_runtime_capture_v0.1.0",
        "status": "runtime_evidence_captured",
        "evidence_kind": "isaac_sim_runtime_backed_source_log",
        "embodiments": embodiments,
    }


def test_runner_builds_controlled_package_that_verifies_only_as_synthetic(
    tmp_path: Path,
) -> None:
    report, manifest_path = _build_controlled_package(tmp_path)

    verifier_report = _load_verifier().verify_package(manifest_path)

    assert report["passed"] is True
    assert report["status"] == "synthetic_verifier_fixture"
    assert verifier_report.ok is True, verifier_report.failures()
    assert verifier_report.recomputed["status"] == "synthetic_verifier_fixture"
    assert verifier_report.recomputed["status"] != "isaac_sim_embodiment_source_closed"
    assert verifier_report.recomputed["embodiments"] == list(REQUIRED_EMBODIMENTS)


def test_runtime_capture_report_builds_runtime_evidence_without_closure(
    tmp_path: Path,
) -> None:
    runner = _load_runner()
    report_path = tmp_path / "runtime_capture.json"
    report_path.write_text(
        json.dumps(_runtime_capture_report(), ensure_ascii=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )

    report = runner.build_mvp3c_isaac_sim_embodiment_source(
        output_dir=tmp_path / "mvp3c_package",
        clean=True,
        runtime_capture_report=report_path,
    )
    verifier_report = _load_verifier().verify_package(Path(report["package_manifest"]))

    assert report["status"] == "runtime_evidence_captured"
    assert report["runtime_evidence_captured"] is True
    assert report["closure_asserted"] is False
    assert verifier_report.ok is True, verifier_report.failures()
    assert verifier_report.recomputed["status"] == "runtime_evidence_captured"
    assert verifier_report.recomputed["status"] != "isaac_sim_embodiment_source_closed"


def test_runtime_backed_closure_rejects_incomplete_capture_payload(tmp_path: Path) -> None:
    runner = _load_runner()
    report_path = tmp_path / "runtime_capture.json"
    forged = {
        "schema_version": "rdf_mvp3c_isaac_sim_runtime_capture_v0.1.0",
        "status": "runtime_evidence_captured",
        "evidence_kind": "isaac_sim_runtime_backed_source_log",
        "embodiments": {embodiment_id: {} for embodiment_id in REQUIRED_EMBODIMENTS},
    }
    report_path.write_text(
        json.dumps(forged, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing runtime_metadata"):
        runner.build_mvp3c_isaac_sim_embodiment_source(
            output_dir=tmp_path / "mvp3c_package",
            clean=True,
            runtime_capture_report=report_path,
            closure_assertion=True,
        )


def test_runner_calls_separate_mvp3c_source_ingress_registry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = _load_runner()
    calls: list[str] = []
    original_create = RobotEmbodimentAdapterRegistry.create_mvp3c_source_ingress_adapter
    original_project = runner.RobotEmbodimentAdapter.project_mvp3c_source_evidence
    projection_calls: list[str] = []

    def recording_create(embodiment_id: str, **kwargs):
        calls.append(embodiment_id)
        return original_create(embodiment_id, **kwargs)

    def recording_project(self, *, source_dir, output_dir, runtime_metadata_path, contract_path):
        projection_calls.append(self.profile.adapter_id)
        return original_project(
            self,
            source_dir=source_dir,
            output_dir=output_dir,
            runtime_metadata_path=runtime_metadata_path,
            contract_path=contract_path,
        )

    monkeypatch.setattr(
        RobotEmbodimentAdapterRegistry,
        "create_mvp3c_source_ingress_adapter",
        recording_create,
    )
    monkeypatch.setattr(
        runner.RobotEmbodimentAdapter,
        "project_mvp3c_source_evidence",
        recording_project,
    )

    report = runner.build_mvp3c_isaac_sim_embodiment_source(
        output_dir=tmp_path / "mvp3c_package",
        clean=True,
        evidence_kind="synthetic_verifier_fixture",
    )

    assert report["passed"] is True
    assert calls == list(REQUIRED_EMBODIMENTS)
    assert projection_calls == list(REQUIRED_EMBODIMENTS)


def test_runner_writes_required_data_files_and_manifest_hashes(tmp_path: Path) -> None:
    _report, manifest_path = _build_controlled_package(tmp_path)
    package_dir = manifest_path.parent
    data = package_dir / "data"
    manifest = _read_json(manifest_path)
    artifact_index = _read_json(data / "artifact_index.json")

    for embodiment_id in REQUIRED_EMBODIMENTS:
        assert (data / "runtime_metadata" / f"{embodiment_id}_runtime_metadata.json").exists()
        assert (data / "preflight" / f"{embodiment_id}_preflight.json").exists()
        assert (data / "source_logs" / embodiment_id / "metadata.json").exists()
        assert (data / "source_logs" / embodiment_id / "accepted_command_state.jsonl").exists()
        assert (data / "source_logs" / embodiment_id / "rejected_command_state.jsonl").exists()
        assert (data / "contracts" / f"{embodiment_id}_normalized_trajectory_contract.json").exists()
        assert (data / "adapter_results" / f"{embodiment_id}_adapter_result.json").exists()

    data_files = sorted(
        path.relative_to(package_dir).as_posix()
        for path in data.rglob("*")
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


def test_runner_package_has_claim_safe_ranges_and_no_storage_paths(tmp_path: Path) -> None:
    _report, manifest_path = _build_controlled_package(tmp_path)
    package_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in manifest_path.parent.rglob("*")
        if path.is_file() and path.suffix in {".json", ".jsonl", ".md"}
    ).lower()
    config = _read_json(manifest_path.parent / "data" / "config.json")

    assert config["spent_no_reuse"] == EXACT_SPENT_NO_REUSE
    assert config["opened_ranges"] == {
        "calibration": [],
        "heldout": [],
        "tuning": [],
        "closure": [],
    }
    assert config["synthetic_verifier_fixture"] is True
    assert config["requested_status"] == "synthetic_verifier_fixture"
    assert "storage/" not in package_text
    assert "quest3_handtracking" not in package_text
    assert "steamvr_openxr" not in package_text
    assert "alvr" not in package_text


def test_runner_refuses_unsafe_clean_paths(tmp_path: Path) -> None:
    runner = _load_runner()

    for output_dir in (ROOT, ROOT / "docs", ROOT / "docs" / "proof"):
        with pytest.raises(ValueError, match="refusing to clean unsafe output_dir"):
            runner.build_mvp3c_isaac_sim_embodiment_source(
                output_dir=output_dir,
                clean=True,
            )

    report = runner.build_mvp3c_isaac_sim_embodiment_source(
        output_dir=tmp_path / "safe_tmp_package",
        clean=True,
    )
    assert Path(report["package_dir"]) == tmp_path / "safe_tmp_package"


def test_runner_does_not_import_independent_verifier() -> None:
    source = RUNNER.read_text(encoding="utf-8")

    tree = ast.parse(source)
    imported_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
    assert "scripts.verify_mvp3c_isaac_sim_embodiment_source_package" not in imported_modules
    assert "verify_mvp3c_isaac_sim_embodiment_source_package" not in imported_modules


def test_capture_script_defers_isaac_imports_to_runtime_function() -> None:
    source = CAPTURE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_level_imports = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    top_level_imports.update(
        node.module or ""
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
    )

    assert all(not name.startswith("isaacsim") for name in top_level_imports)
    assert all(not name.startswith("omni") for name in top_level_imports)
    assert "numpy" not in top_level_imports


def test_capture_script_uses_asset_existing_ur10e_end_effector_path() -> None:
    capture = _load_script("capture_mvp3c_isaac_sim_embodiment_source", CAPTURE)
    specs = {spec["embodiment_id"]: spec for spec in capture.EMBODIMENT_SPECS}

    assert (
        specs["universal_robots_ur10e_isaac_sim"]["end_effector_prim_path"]
        == "/World/UR10e/ee_link"
    )
    assert "robotiq_base_link" not in specs["universal_robots_ur10e_isaac_sim"][
        "end_effector_prim_path"
    ]


def test_capture_script_fails_closed_when_eef_pose_is_unreadable() -> None:
    capture = _load_script("capture_mvp3c_isaac_sim_embodiment_source", CAPTURE)

    class BrokenEndEffector:
        def get_world_pose(self):
            raise RuntimeError("pose unavailable")

    class Robot:
        end_effector = BrokenEndEffector()

    with pytest.raises(RuntimeError, match="end effector pose unreadable"):
        capture._eef_pose(Robot())


def test_default_output_is_managed_mvp3c_proof_package() -> None:
    runner = _load_runner()

    assert runner.DEFAULT_OUTPUT_DIR == DEFAULT_PACKAGE
