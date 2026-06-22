"""RED contract tests for the MVP-3B source-adapter proof package verifier.

Task 1 intentionally does not implement scripts/verify_mvp3b_source_adapter_package.py.
These tests define the verifier contract for Task 2: a stdlib-only auditor must
recompute package closure from a self-contained source-adapter matrix package, not from
producer services or cached summary files.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
VERIFIER = ROOT / "scripts" / "verify_mvp3b_source_adapter_package.py"

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
    "visual_policy_performance",
    "hmd_openxr_collection_readiness",
    "hmd_readiness",
    "hmd_readiness_claimed",
    "marketplace_readiness",
    "marketplace_readiness_claimed",
    "production_certification",
    "universal_robot_support",
    "universal_robot_support_claimed",
    "policy_uplift",
    "policy_uplift_claimed",
    "learning_proven_value",
    "live_runtime_support",
    "live_runtime_support_claimed",
    "live_ur_runtime_support",
    "live_ros2_dds_runtime_support",
    "franka_hardware_support",
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


def _load_verifier():
    name = "verify_mvp3b_source_adapter_package"
    spec = importlib.util.spec_from_file_location(name, VERIFIER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _stable_json(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_stable_json(payload) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(_stable_json(row) + "\n" for row in rows)
    path.write_text(body, encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_rows(adapter_id: str, *, accepted: bool) -> list[dict]:
    role_values = {
        role: [0.1, 0.2, 0.3, 0.4] for role in REQUIRED_ACTION_ROLES
    }
    return [
        {
            "adapter_id": adapter_id,
            "row_id": f"{adapter_id}_{'accepted' if accepted else 'rejected'}_0",
            "timestamp_ns": 1_000_000 if accepted else 2_000_000,
            "accepted": accepted,
            "command_state": {
                "eef_pose": [0.0, 0.0, 0.1, 0.0, 0.0, 0.0, 1.0],
                "gripper_width": 0.04,
                "actions_by_role": role_values,
            },
        }
    ]


def _contract(adapter_id: str, *, roles: tuple[str, ...] = REQUIRED_ACTION_ROLES) -> dict:
    frame_count = 2
    return {
        "schema_version": "mvp3b.normalized_trajectory_contract.v1",
        "adapter_id": adapter_id,
        "source": {
            "input_device": "recorded_command_state_fixture",
            "runtime": "generated_or_file_backed_recorded_log_fixture",
            "simulator": "none_recorded_log_projection",
            "robot": adapter_id,
            "task_name": "mvp3b_source_adapter_matrix",
        },
        "required_action_roles": list(roles),
        "frame_action_role_coverage": {
            role: {"present": True, "frames": frame_count} for role in roles
        },
        "learning_eligibility_gates": {
            "replay_action_contract": True,
            "trainer_export_smoke": "contract_smoke_only",
            "learning_results_measured": False,
            "policy_uplift": False,
            "learning_proven_value": False,
        },
    }


def _make_package(tmp_path: Path, *, adapters: tuple[str, ...] = REQUIRED_ADAPTERS) -> Path:
    pkg = tmp_path / "mvp3b_pkg"
    data = pkg / "data"
    forbidden_false = {key: False for key in CANONICAL_FORBIDDEN_CLAIMS}
    adapter_counts = {}

    _write_json(
        data / "config.json",
        {
            "proof_slice": "mvp3b_source_adapter_matrix",
            "claim_tier": "source_adapter_infrastructure",
            "changed_variable": "source_adapter_matrix",
            "required_adapters": list(REQUIRED_ADAPTERS),
            "source_evidence_level": "generated_or_file_backed_recorded_log_fixture",
            "spent_no_reuse": EXACT_SPENT_NO_REUSE,
            "opened_ranges": {
                "calibration": [],
                "heldout": [],
                "tuning": [],
                "closure": [],
            },
            "learning_proven_addendum": "absent",
            "non_claims": forbidden_false,
            "contract_smoke": {
                "trainer_export_smoke": True,
                "learning_results_measured": False,
                "policy_uplift": False,
                "learning_proven_value": False,
            },
        },
    )
    _write_json(
        data / "adapter_registry_snapshot.json",
        {
            "registry_source": "serialized_fixture_snapshot",
            "adapters": [
                {
                    "adapter_id": adapter_id,
                    "robot_family": adapter_id,
                    "runtime": "recorded_log_fixture",
                    "live_runtime_support": False,
                    "real_robot_success": False,
                    "physical_robot_readiness": False,
                }
                for adapter_id in adapters
            ],
        },
    )
    _write_json(
        data / "non_claims_attestation.json",
        {
            "scope": "mvp3b_source_adapter_matrix",
            "forbidden_claims": forbidden_false,
        },
    )

    for adapter_id in adapters:
        accepted_rows = _source_rows(adapter_id, accepted=True)
        rejected_rows = _source_rows(adapter_id, accepted=False)
        source_dir = data / "source_logs" / adapter_id
        accepted_path = source_dir / "accepted_command_state.jsonl"
        rejected_path = source_dir / "rejected_command_state.jsonl"
        _write_json(
            source_dir / "metadata.json",
            {
                "adapter_id": adapter_id,
                "robot_family": adapter_id,
                "runtime": "recorded_log_fixture",
                "source_profile": "generated_or_file_backed_recorded_log_fixture",
                "real_robot_success": False,
                "live_runtime_support": False,
                "physical_robot_readiness_claimed": False,
            },
        )
        _write_jsonl(accepted_path, accepted_rows)
        _write_jsonl(rejected_path, rejected_rows)

        projection_dir = data / "projections" / adapter_id
        _write_json(
            projection_dir / "trajectories" / "accepted.json",
            {"adapter_id": adapter_id, "frames": accepted_rows},
        )
        _write_json(
            projection_dir / "trajectories" / "rejected.json",
            {"adapter_id": adapter_id, "frames": rejected_rows},
        )
        _write_json(
            projection_dir / "evaluations" / "accepted.json",
            {"adapter_id": adapter_id, "accepted": True, "count": 1},
        )
        _write_json(
            projection_dir / "evaluations" / "rejected.json",
            {"adapter_id": adapter_id, "accepted": False, "count": 1},
        )
        _write_json(
            projection_dir / "curation_manifest.json",
            {
                "adapter_id": adapter_id,
                "accepted_count": 1,
                "rejected_count": 1,
                "accepted_reasons": ["contract_roles_present"],
                "rejected_reasons": ["fixture_negative_control"],
            },
        )
        _write_json(
            projection_dir / "projection_manifest.json",
            {
                "adapter_id": adapter_id,
                "source_logs": {
                    "accepted_command_state.jsonl": {
                        "sha256": _sha(accepted_path),
                        "rows": 1,
                    },
                    "rejected_command_state.jsonl": {
                        "sha256": _sha(rejected_path),
                        "rows": 1,
                    },
                },
                "projected_artifacts": {
                    "trajectories/accepted.json": _sha(
                        projection_dir / "trajectories" / "accepted.json"
                    ),
                    "trajectories/rejected.json": _sha(
                        projection_dir / "trajectories" / "rejected.json"
                    ),
                    "evaluations/accepted.json": _sha(
                        projection_dir / "evaluations" / "accepted.json"
                    ),
                    "evaluations/rejected.json": _sha(
                        projection_dir / "evaluations" / "rejected.json"
                    ),
                    "curation_manifest.json": _sha(projection_dir / "curation_manifest.json"),
                },
                "accepted_count": 1,
                "rejected_count": 1,
            },
        )
        _write_json(
            data / "contracts" / f"{adapter_id}_normalized_trajectory_contract.json",
            _contract(adapter_id),
        )
        _write_json(
            data / "adapter_results" / f"{adapter_id}_adapter_result.json",
            {
                "adapter_id": adapter_id,
                "status": "normalized_contract_passed",
                "accepted_count": 1,
                "rejected_count": 1,
                "required_action_roles_present": list(REQUIRED_ACTION_ROLES),
                "learning_results_measured": False,
                "policy_uplift": False,
                "learning_proven_value": False,
            },
        )
        _write_json(
            data
            / "generated_contract_smoke"
            / adapter_id
            / f"{adapter_id}.trainer_smoke.json",
            {
                "passed": True,
                "contract_smoke_only": True,
                "learning_results_measured": False,
                "policy_uplift": False,
                "learning_proven_value": False,
            },
        )
        adapter_counts[adapter_id] = {"accepted_count": 1, "rejected_count": 1}

    _write_json(
        data / "source_adapter_matrix_summary.json",
        {
            "status": "source_adapter_infrastructure_closed",
            "adapter_count": len(adapters),
            "required_adapter_count": len(REQUIRED_ADAPTERS),
            "accepted_count": sum(c["accepted_count"] for c in adapter_counts.values()),
            "rejected_count": sum(c["rejected_count"] for c in adapter_counts.values()),
            "adapters": adapter_counts,
            "cached_summary_only": True,
            "contract_smoke_only": True,
            "learning_results_measured": False,
            "policy_uplift": False,
            "learning_proven_value": False,
        },
    )
    (pkg / "README.md").write_text(
        "MVP-3B proves recorded-log source-profile projection through RDF "
        "infrastructure. It does not claim live robot support, real robot success, "
        "marketplace readiness, production certification, or learning-proven value.\n",
        encoding="utf-8",
    )

    artifact_entries = []
    for path in sorted(data.rglob("*")):
        if path.is_file() and path.name != "artifact_index.json":
            artifact_entries.append(
                {
                    "data_path": path.relative_to(pkg).as_posix(),
                    "hash_convention": "file_bytes",
                    "file_sha256": _sha(path),
                }
            )
    _write_json(data / "artifact_index.json", {"artifact_index": artifact_entries})
    artifact_entries.append(
        {
            "data_path": "data/artifact_index.json",
            "hash_convention": "file_bytes",
            "file_sha256": _sha(data / "artifact_index.json"),
        }
    )
    manifest = {
        "package_name": "mvp3b_source_adapter_matrix_proof_package",
        "claims": {"status": "source_adapter_infrastructure_closed"},
        "artifact_index": artifact_entries,
    }
    _write_json(pkg / "package_manifest.json", manifest)
    return pkg / "package_manifest.json"


def _tamper_json(path: Path, edit) -> None:
    payload = json.loads(path.read_text())
    edit(payload)
    _write_json(path, payload)


def _replace_index_hash(entry: dict, *, rel_path: str, file_sha256: str) -> bool:
    if entry.get("data_path") != rel_path:
        return False
    entry["file_sha256"] = file_sha256
    return True


def _refresh_indexed_hashes(manifest: Path, *changed_rel_paths: str) -> None:
    """Refresh package indexes after semantic tampering in hash-indexed files."""

    pkg = manifest.parent
    artifact_index_path = pkg / "data" / "artifact_index.json"
    artifact_index = json.loads(artifact_index_path.read_text(encoding="utf-8"))
    for rel_path in changed_rel_paths:
        refreshed = any(
            _replace_index_hash(
                entry,
                rel_path=rel_path,
                file_sha256=_sha(pkg / rel_path),
            )
            for entry in artifact_index["artifact_index"]
        )
        assert refreshed, f"{rel_path} is not indexed in data/artifact_index.json"
    _write_json(artifact_index_path, artifact_index)

    package_manifest = json.loads(manifest.read_text(encoding="utf-8"))
    manifest_rel_paths = set(changed_rel_paths) | {"data/artifact_index.json"}
    for rel_path in manifest_rel_paths:
        refreshed = any(
            _replace_index_hash(
                entry,
                rel_path=rel_path,
                file_sha256=_sha(pkg / rel_path),
            )
            for entry in package_manifest["artifact_index"]
        )
        assert refreshed, f"{rel_path} is not indexed in package_manifest.json"
    _write_json(manifest, package_manifest)


def _tamper_indexed_json(manifest: Path, rel_path: str, edit) -> None:
    _tamper_json(manifest.parent / rel_path, edit)
    _refresh_indexed_hashes(manifest, rel_path)


def _assert_only_check_failed(report, expected_check: str) -> None:
    checks = _checks(report)
    assert report.ok is False
    assert checks["hash_integrity"].passed is True
    assert checks[expected_check].passed is False
    failed_checks = {name for name, check in checks.items() if check.passed is False}
    assert failed_checks == {expected_check}


def _checks(report) -> dict:
    return {check.name: check for check in report.checks}


def test_green_package_returns_source_adapter_infrastructure_closed(tmp_path: Path):
    manifest = _make_package(tmp_path)
    report = _load_verifier().verify_package(manifest)

    assert report.ok is True, report.failures()
    assert report.exit_code == 0
    assert report.recomputed["status"] == "source_adapter_infrastructure_closed"
    assert report.recomputed["adapters"] == list(REQUIRED_ADAPTERS)


def test_missing_required_adapter_fails(tmp_path: Path):
    manifest = _make_package(tmp_path, adapters=REQUIRED_ADAPTERS[:-1])

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert _checks(report)["adapter_set_exactness"].passed is False


def test_extra_adapter_fails(tmp_path: Path):
    manifest = _make_package(tmp_path, adapters=REQUIRED_ADAPTERS + ("demo_extra_arm",))

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert _checks(report)["adapter_set_exactness"].passed is False


def test_source_log_hash_tamper_fails(tmp_path: Path):
    manifest = _make_package(tmp_path)
    source_log = (
        manifest.parent
        / "data"
        / "source_logs"
        / REQUIRED_ADAPTERS[0]
        / "accepted_command_state.jsonl"
    )
    source_log.write_text(source_log.read_text() + "\n", encoding="utf-8")

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert _checks(report)["hash_integrity"].passed is False


def test_unindexed_data_file_fails(tmp_path: Path):
    manifest = _make_package(tmp_path)
    _write_json(manifest.parent / "data" / "unindexed_verdict_file.json", {"must_fail": True})

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert _checks(report)["data_coverage"].passed is False


def test_truthy_top_level_forbidden_runtime_claims_fail(tmp_path: Path):
    for key in ("real_robot_success", "live_ur_runtime_support", "live_runtime_support_claimed"):
        manifest = _make_package(tmp_path / key)
        _tamper_indexed_json(
            manifest,
            "data/config.json",
            lambda payload, key=key: payload["non_claims"].update({key: True}),
        )

        report = _load_verifier().verify_package(manifest)

        _assert_only_check_failed(report, "forbidden_claims")


def test_truthy_producer_claim_keys_fail_recursively(tmp_path: Path):
    claim_surfaces = (
        (
            "physical_robot_readiness_claimed",
            "data/source_logs/franka_research_arm/metadata.json",
        ),
        (
            "real_robot_success_claimed",
            "data/adapter_results/robotis_sh5_ros2_dds_adapter_result.json",
        ),
        (
            "public_sample_evidence_claimed",
            "data/adapter_registry_snapshot.json",
        ),
        (
            "live_runtime_support",
            "data/source_adapter_matrix_summary.json",
        ),
    )
    for key, rel in claim_surfaces:
        manifest = _make_package(tmp_path / key)
        _tamper_indexed_json(
            manifest,
            rel,
            lambda payload, key=key: payload.update({key: True}),
        )

        report = _load_verifier().verify_package(manifest)

        _assert_only_check_failed(report, "forbidden_claims")


def test_trainer_smoke_learning_results_measured_true_fails_non_claims_false_only(
    tmp_path: Path,
):
    adapter_id = "franka_research_arm"
    rel_path = (
        "data/generated_contract_smoke/"
        f"{adapter_id}/{adapter_id}.trainer_smoke.json"
    )
    manifest = _make_package(tmp_path)
    _tamper_indexed_json(
        manifest,
        rel_path,
        lambda payload: payload.update({"learning_results_measured": True}),
    )

    report = _load_verifier().verify_package(manifest)

    _assert_only_check_failed(report, "non_claims_false")


def test_adapter_result_policy_uplift_or_learning_proven_value_true_fails_non_claims_false_only(
    tmp_path: Path,
):
    cases = ("policy_uplift", "learning_proven_value")
    for key in cases:
        adapter_id = "robotis_sh5_ros2_dds"
        rel_path = f"data/adapter_results/{adapter_id}_adapter_result.json"
        manifest = _make_package(tmp_path / key)
        _tamper_indexed_json(
            manifest,
            rel_path,
            lambda payload, key=key: payload.update({key: True}),
        )

        report = _load_verifier().verify_package(manifest)

        _assert_only_check_failed(report, "non_claims_false")


def test_summary_non_learning_contract_fields_fail_non_claims_false_only(
    tmp_path: Path,
):
    cases = (
        ("learning_results_measured", True),
        ("contract_smoke_only", False),
    )
    for key, value in cases:
        manifest = _make_package(tmp_path / key)
        _tamper_indexed_json(
            manifest,
            "data/source_adapter_matrix_summary.json",
            lambda payload, key=key, value=value: payload.update({key: value}),
        )

        report = _load_verifier().verify_package(manifest)

        _assert_only_check_failed(report, "non_claims_false")


def test_contract_learning_eligibility_gates_learning_claims_fail_non_claims_false_only(
    tmp_path: Path,
):
    cases = (
        ("learning_results_measured", True),
        ("policy_uplift", True),
        ("trainer_export_smoke", "full_training_run"),
    )
    for key, value in cases:
        adapter_id = "universal_robots_ur_industrial_arm"
        rel_path = f"data/contracts/{adapter_id}_normalized_trajectory_contract.json"
        manifest = _make_package(tmp_path / key)
        _tamper_indexed_json(
            manifest,
            rel_path,
            lambda payload, key=key, value=value: payload[
                "learning_eligibility_gates"
            ].update({key: value}),
        )

        report = _load_verifier().verify_package(manifest)

        _assert_only_check_failed(report, "non_claims_false")


def test_readme_unsupported_positive_support_wording_fails_forbidden_claims_only(
    tmp_path: Path,
):
    manifest = _make_package(tmp_path)
    (manifest.parent / "README.md").write_text(
        "MVP-3B claims real robot success and live UR runtime support.\n",
        encoding="utf-8",
    )

    report = _load_verifier().verify_package(manifest)

    _assert_only_check_failed(report, "forbidden_claims")


def test_readme_negated_limitation_does_not_mask_later_positive_claim(
    tmp_path: Path,
):
    manifest = _make_package(tmp_path)
    (manifest.parent / "README.md").write_text(
        "This package does not claim production certification. "
        "It claims real robot success.\n",
        encoding="utf-8",
    )

    report = _load_verifier().verify_package(manifest)

    _assert_only_check_failed(report, "forbidden_claims")


def test_readme_coordinate_positive_claim_clause_fails_forbidden_claims_only(
    tmp_path: Path,
):
    manifest = _make_package(tmp_path)
    (manifest.parent / "README.md").write_text(
        "This package does not claim production certification, "
        "and it claims real robot success.\n",
        encoding="utf-8",
    )

    report = _load_verifier().verify_package(manifest)

    _assert_only_check_failed(report, "forbidden_claims")


def test_readme_comma_spliced_positive_claim_clause_fails_forbidden_claims_only(
    tmp_path: Path,
):
    manifest = _make_package(tmp_path)
    (manifest.parent / "README.md").write_text(
        "This package does not claim production certification, "
        "it claims real robot success.\n",
        encoding="utf-8",
    )

    report = _load_verifier().verify_package(manifest)

    _assert_only_check_failed(report, "forbidden_claims")


def test_readme_no_comma_coordinate_positive_claim_clause_fails_forbidden_claims_only(
    tmp_path: Path,
):
    manifest = _make_package(tmp_path)
    (manifest.parent / "README.md").write_text(
        "This package does not claim production certification "
        "and it claims real robot success.\n",
        encoding="utf-8",
    )

    report = _load_verifier().verify_package(manifest)

    _assert_only_check_failed(report, "forbidden_claims")


def test_readme_no_comma_coordinate_positive_claim_without_subject_fails_forbidden_claims_only(
    tmp_path: Path,
):
    manifest = _make_package(tmp_path)
    (manifest.parent / "README.md").write_text(
        "This package does not claim production certification "
        "and claims real robot success.\n",
        encoding="utf-8",
    )

    report = _load_verifier().verify_package(manifest)

    _assert_only_check_failed(report, "forbidden_claims")


def test_missing_or_altered_exact_spent_no_reuse_fails(tmp_path: Path):
    for value in ([], [[40000, 40049]], [[40000, 40050], [42000, 42049]]):
        manifest = _make_package(tmp_path / str(len(value)))
        _tamper_indexed_json(
            manifest,
            "data/config.json",
            lambda payload, value=value: payload.update({"spent_no_reuse": value}),
        )

        report = _load_verifier().verify_package(manifest)

        _assert_only_check_failed(report, "spent_no_reuse_exact")


def test_any_non_empty_opened_calibration_heldout_tuning_or_closure_range_fails(
    tmp_path: Path,
):
    for range_name in ("calibration", "heldout", "tuning", "closure"):
        manifest = _make_package(tmp_path / range_name)
        _tamper_indexed_json(
            manifest,
            "data/config.json",
            lambda payload, range_name=range_name: payload["opened_ranges"].update(
                {range_name: [50000, 50009]}
            ),
        )

        report = _load_verifier().verify_package(manifest)

        _assert_only_check_failed(report, "opened_ranges_empty")


def test_learning_proven_addendum_without_fresh_range_evidence_fails(tmp_path: Path):
    manifest = _make_package(tmp_path)
    _tamper_indexed_json(
        manifest,
        "data/config.json",
        lambda payload: payload.update({"learning_proven_addendum": "present"}),
    )

    report = _load_verifier().verify_package(manifest)

    _assert_only_check_failed(report, "learning_proven_addendum_absent")


def test_missing_contract_action_role_fails(tmp_path: Path):
    manifest = _make_package(tmp_path)
    contract_path = (
        manifest.parent
        / "data"
        / "contracts"
        / "franka_research_arm_normalized_trajectory_contract.json"
    )
    _tamper_indexed_json(
        manifest,
        contract_path.relative_to(manifest.parent).as_posix(),
        lambda payload: (
            payload["required_action_roles"].remove("learning_action"),
            payload["frame_action_role_coverage"].pop("learning_action"),
        ),
    )

    report = _load_verifier().verify_package(manifest)

    _assert_only_check_failed(report, "contract_action_roles")


def test_inflated_contract_frame_action_role_coverage_fails_coverage_only(
    tmp_path: Path,
):
    manifest = _make_package(tmp_path)
    rel_path = (
        "data/contracts/"
        "franka_research_arm_normalized_trajectory_contract.json"
    )
    _tamper_indexed_json(
        manifest,
        rel_path,
        lambda payload: payload["frame_action_role_coverage"]["learning_action"].update(
            {"frames": 999}
        ),
    )

    report = _load_verifier().verify_package(manifest)

    _assert_only_check_failed(report, "frame_action_role_coverage")


def test_summary_count_override_fails(tmp_path: Path):
    manifest = _make_package(tmp_path)
    _tamper_indexed_json(
        manifest,
        "data/source_adapter_matrix_summary.json",
        lambda payload: payload.update({"adapter_count": 999, "accepted_count": 999}),
    )

    report = _load_verifier().verify_package(manifest)

    _assert_only_check_failed(report, "summary_cache_consistency")


def test_verifier_remains_stdlib_only_and_independent_from_producer_services():
    source = VERIFIER.read_text(encoding="utf-8")
    assert "app.services.robot_embodiment_adapters" not in source
    assert "app.services.normalized_trajectory_contract" not in source

    tree = ast.parse(source)
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module.split(".")[0])
    modules.discard("__future__")
    assert modules - set(sys.stdlib_module_names) == set()
