from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


def load_script(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def ur_adapter_proof(proof: dict[str, Any]) -> dict[str, Any]:
    for adapter_proof in proof["adapter_proofs"]:
        if adapter_proof["adapter_id"] == "universal_robots_ur_industrial_arm":
            return adapter_proof
    raise AssertionError("UR adapter proof missing")


def assert_rejected_by_lineage_gate(harness: Any, *, output_dir: Path, mvp1plus_output_dir: Path) -> None:
    try:
        harness.build_mvp2_ur_policy_ab_harness(
            output_dir=output_dir,
            mvp1plus_output_dir=mvp1plus_output_dir,
            clean=True,
            refresh_mvp1plus=False,
        )
    except ValueError as exc:
        assert "lineage gate" in str(exc).lower()
    else:
        raise AssertionError("expected UR lineage gate to reject tampered proof")


def test_mvp2_ur_harness_preserves_adapter_emitted_contract_lineage(tmp_path: Path) -> None:
    harness = load_script("run_mvp2_ur_policy_ab_harness")

    report = harness.build_mvp2_ur_policy_ab_harness(
        output_dir=tmp_path / "mvp2_policy_ab_harness",
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_mvp1plus=True,
    )

    assert report["passed"] is True
    assert report["proof_source"]["adapter_id"] == "universal_robots_ur_industrial_arm"
    assert report["proof_source"]["source_evidence_type"] == "file_backed_recorded_log_fixture"
    assert report["proof_source"]["contract_path"].endswith(
        "universal_robots_ur_industrial_arm_normalized_trajectory_contract.json"
    )
    assert report["proof_source"]["validator_backend"] == "NormalizedTrajectoryContractValidator"
    assert report["claim_boundary"]["policy_uplift_claimed"] is False
    assert report["claim_boundary"]["learning_results_measured"] is False
    assert report["claim_boundary"]["curated_vs_uncurated_uplift"] is None
    assert report["claim_boundary"]["learning_proven"] is False
    assert report["claim_boundary"]["proof_eligible"] is False


def test_mvp2_ur_harness_creates_mvp2_named_dataset_and_eval_artifacts(tmp_path: Path) -> None:
    harness = load_script("run_mvp2_ur_policy_ab_harness")
    output_dir = tmp_path / "mvp2_policy_ab_harness"

    report = harness.build_mvp2_ur_policy_ab_harness(
        output_dir=output_dir,
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_mvp1plus=True,
    )

    artifact_paths = report["artifact_paths"]
    expected_files = [
        output_dir / "mvp2_policy_ab_harness_report.json",
        output_dir / "mvp2_policy_eval_input_template.json",
        output_dir / "mvp2_heldout_suite_manifest.json",
        output_dir / "baseline_uncurated" / "baseline_uncurated_train.hdf5",
        output_dir / "candidate_curated" / "candidate_curated_train.hdf5",
        output_dir / "rollout_ingest_contract_fixture" / "baseline_rollouts.schema_fixture.json",
        output_dir / "rollout_ingest_contract_fixture" / "candidate_rollouts.schema_fixture.json",
        output_dir / "rollout_ingest_contract_fixture" / "ingest_contract_report.json",
    ]
    for path in expected_files:
        assert path.exists(), str(path)

    assert "mvp1c" not in json.dumps(artifact_paths, sort_keys=True).lower()
    assert read_json(output_dir / "mvp2_heldout_suite_manifest.json")["held_out"] is True
    template = read_json(output_dir / "mvp2_policy_eval_input_template.json")
    assert template["schema_version"] == "rdf_mvp2_policy_eval_input_v0.1.0"
    assert template["baseline"]["dataset_view"] == "baseline_uncurated_recorded_log_harness"
    assert template["candidate"]["dataset_view"] == "candidate_curated_accepted"
    assert template["baseline"]["rollout_results"] == []
    assert template["candidate"]["rollout_results"] == []


def test_mvp2_schema_only_rollout_ingest_is_not_policy_evidence(tmp_path: Path) -> None:
    harness = load_script("run_mvp2_ur_policy_ab_harness")

    report = harness.build_mvp2_ur_policy_ab_harness(
        output_dir=tmp_path / "mvp2_policy_ab_harness",
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_mvp1plus=True,
    )

    ingest = report["rollout_ingest_contract"]
    assert ingest["passed"] is True
    assert ingest["fixture_kind"] == "schema_only_rollout_ingest_contract"
    assert ingest["proof_eligible"] is False
    assert ingest["learning_results_measured"] is False
    assert ingest["curated_vs_uncurated_uplift"] is None
    assert ingest["baseline_rollout_count"] == 2
    assert ingest["candidate_rollout_count"] == 2
    assert ingest["baseline_success_rate"] == 0.5
    assert ingest["candidate_success_rate"] == 0.5
    assert ingest["schema_fixture_metrics"]["non_comparative"] is True
    assert ingest["schema_fixture_metrics"]["must_not_be_used_for_policy_uplift"] is True
    assert "schema fixture" in " ".join(ingest["limitations"]).lower()


def test_mvp2_harness_rejects_reused_ur_proof_without_file_backed_lineage(tmp_path: Path) -> None:
    harness = load_script("run_mvp2_ur_policy_ab_harness")
    mvp1plus_output_dir = tmp_path / "mvp1plus_embodiment_proof"
    proof = harness.build_mvp1plus_embodiment_proof(mvp1plus_output_dir, clean=True)
    ur_adapter_proof(proof)["lineage_evidence"]["source_evidence_type"] = "jsonl_plus_metadata_recorded_command_state_log"
    proof_path = mvp1plus_output_dir / "mvp1plus_embodiment_proof.json"
    write_json(proof_path, proof)

    assert_rejected_by_lineage_gate(
        harness,
        output_dir=tmp_path / "mvp2_policy_ab_harness",
        mvp1plus_output_dir=mvp1plus_output_dir,
    )


def test_mvp2_harness_rejects_incomplete_or_tampered_lineage(tmp_path: Path) -> None:
    harness = load_script("run_mvp2_ur_policy_ab_harness")
    cases = ("missing_source_key", "missing_projected_key", "projected_hash_mismatch", "projected_path_mismatch")

    for case in cases:
        case_dir = tmp_path / case
        mvp1plus_output_dir = case_dir / "mvp1plus_embodiment_proof"
        proof = harness.build_mvp1plus_embodiment_proof(mvp1plus_output_dir, clean=True)
        ur_proof = ur_adapter_proof(proof)
        lineage = ur_proof["lineage_evidence"]
        if case == "missing_source_key":
            del lineage["source_files"]["metadata_json"]
        elif case == "missing_projected_key":
            del lineage["projected_artifacts"]["accepted_trajectory"]
        elif case == "projected_hash_mismatch":
            lineage["projected_artifacts"]["accepted_trajectory"]["sha256"] = "0" * 64
        elif case == "projected_path_mismatch":
            ur_proof["projected_inputs"]["accepted_trajectory"] = ur_proof["projected_inputs"]["rejected_trajectory"]
        write_json(mvp1plus_output_dir / "mvp1plus_embodiment_proof.json", proof)

        assert_rejected_by_lineage_gate(
            harness,
            output_dir=case_dir / "mvp2_policy_ab_harness",
            mvp1plus_output_dir=mvp1plus_output_dir,
        )


def test_mvp2_harness_derives_readiness_from_hdf5_inspection(tmp_path: Path) -> None:
    harness = load_script("run_mvp2_ur_policy_ab_harness")
    original_inspect_hdf5 = harness.inspect_hdf5

    def dirty_inspection(output_path: Path) -> dict[str, Any]:
        inspection = original_inspect_hdf5(output_path)
        inspection["issues"] = ["forced dirty inspection"]
        return inspection

    harness.inspect_hdf5 = dirty_inspection
    try:
        report = harness.build_mvp2_ur_policy_ab_harness(
            output_dir=tmp_path / "mvp2_policy_ab_harness",
            mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
            clean=True,
            refresh_mvp1plus=True,
        )
    finally:
        harness.inspect_hdf5 = original_inspect_hdf5

    assert report["passed"] is False
    assert report["harness_ready"] is False
    assert report["gates"]["baseline_hdf5_inspection_clean"] is False
    assert report["gates"]["candidate_hdf5_inspection_clean"] is False


def test_mvp2_harness_no_clean_rerun_clears_managed_stale_outputs(tmp_path: Path) -> None:
    harness = load_script("run_mvp2_ur_policy_ab_harness")
    output_dir = tmp_path / "mvp2_policy_ab_harness"
    mvp1plus_output_dir = tmp_path / "mvp1plus_embodiment_proof"

    harness.build_mvp2_ur_policy_ab_harness(
        output_dir=output_dir,
        mvp1plus_output_dir=mvp1plus_output_dir,
        clean=True,
        refresh_mvp1plus=True,
    )
    stale_files = [
        output_dir / "baseline_uncurated" / "raw" / "trajectories" / "stale_trajectory.json",
        output_dir / "candidate_curated" / "raw" / "evaluations" / "stale_evaluation.json",
        output_dir / "rollout_ingest_contract_fixture" / "stale_rollout.json",
    ]
    for path in stale_files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")

    report = harness.build_mvp2_ur_policy_ab_harness(
        output_dir=output_dir,
        mvp1plus_output_dir=mvp1plus_output_dir,
        clean=False,
        refresh_mvp1plus=False,
    )

    assert report["passed"] is True
    for path in stale_files:
        assert not path.exists(), str(path)


def test_mvp2_harness_cli_writes_report_and_preserves_claim_boundary(tmp_path: Path) -> None:
    harness = load_script("run_mvp2_ur_policy_ab_harness")
    output_dir = tmp_path / "mvp2_policy_ab_harness"

    exit_code = harness.main(
        [
            "--output-dir",
            str(output_dir),
            "--mvp1plus-output-dir",
            str(tmp_path / "mvp1plus_embodiment_proof"),
            "--refresh-mvp1plus",
            "--clean",
            "--pretty",
        ]
    )

    assert exit_code == 0
    report = read_json(output_dir / "mvp2_policy_ab_harness_report.json")
    assert report["passed"] is True
    assert report["learning_results_measured"] is False
    assert report["learning_proven"] is False


def test_mvp2_harness_clean_guard_only_allows_managed_artifact_roots() -> None:
    harness = load_script("run_mvp2_ur_policy_ab_harness")

    assert harness._is_safe_clean_target(ROOT / "storage" / "mvp2_policy_ab_harness") is True
    assert harness._is_safe_clean_target(Path("/tmp") / "rdf_mvp2_policy_ab_harness") is True
    assert harness._is_safe_clean_target(ROOT / "scripts") is False
    assert harness._is_safe_clean_target(ROOT) is False
    assert harness._is_safe_clean_target(ROOT / "storage") is False
    assert harness._is_safe_clean_target(Path("/tmp")) is False
