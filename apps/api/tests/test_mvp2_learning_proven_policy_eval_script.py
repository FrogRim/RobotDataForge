from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[3]


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


def external_heldout_suite() -> dict[str, Any]:
    return {
        "id": "external_ur_heldout_policy_eval_suite",
        "held_out": True,
        "task_type": "connector_insertion",
        "scenario_ids": [f"scenario_{index}" for index in range(10)],
        "scenario_set_sha256": "external_scenario_set_sha256",
        "source_kind": "external_trainer_eval_suite",
        "proof_role": "external_policy_eval_suite",
    }


def write_external_rollouts(
    *,
    path: Path,
    role: str,
    success_count: int,
    policy_artifact_id: str,
    heldout_suite: dict[str, Any],
) -> None:
    write_json(
        path,
        {
            "source_kind": "external_heldout_policy_eval",
            "proof_role": "external_trainer_policy_eval",
            "policy_artifact_id": policy_artifact_id,
            "policy_artifact_sha256": f"{policy_artifact_id}_sha256",
            "training_artifact_sha256": f"{role}_training_artifact_sha256",
            "trainer": "external_eval_runner",
            "eval_runner": "external_heldout_eval_runner",
            "external_evaluator_run": {
                "run_id": f"{role}_external_eval_run",
                "runner_version": "external_eval_runner_v1",
                "run_log_uri": f"file:///external-eval/{role}.jsonl",
                "generated_outside_rdf_local_proxy": True,
            },
            "heldout_suite": heldout_suite,
            "rollout_results": [
                {
                    "rollout_id": f"{role}_{index}",
                    "scenario_id": f"scenario_{index}",
                    "success": index < success_count,
                    "rollout_log_ref": f"file:///external-eval/{role}_{index}.json",
                }
                for index in range(10)
            ],
        },
    )


def test_mvp2_local_offline_positive_proxy_does_not_close_mvp2(tmp_path: Path) -> None:
    script = load_script("run_mvp2_learning_proven_policy_eval")

    report = script.build_mvp2_learning_proven_policy_eval(
        output_dir=tmp_path / "mvp2_learning_proven_policy_eval",
        harness_output_dir=tmp_path / "mvp2_policy_ab_harness",
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_harness=True,
        refresh_mvp1plus=True,
        offline_profile="positive",
        min_rollouts_per_policy=10,
        bootstrap_iterations=200,
    )

    assert report["passed"] is True
    assert report["learning_results_measured"] is True
    assert report["learning_proven"] is False
    assert report["proof_eligible"] is False
    assert report["evidence_tier"] == "local_offline_policy_eval_proxy"
    assert report["validator_evidence_tier"] is None
    assert report["candidate_success_rate"] > report["baseline_success_rate"]
    assert report["curated_vs_uncurated_uplift"] > 0.0
    assert report["heldout_suite"]["proof_role"] == "local_offline_policy_eval_suite"
    assert report["heldout_suite"]["not_physical_or_isaac_evidence"] is True
    assert Path(report["artifact_paths"]["local_offline_heldout_suite"]).exists()
    assert report["artifact_paths"]["policy_eval_input"] is None
    assert report["artifact_paths"]["policy_eval_report"] is None
    assert report["rollout_generation_method"] == "quality_weighted_local_offline_runner"
    assert report["success_label_source"] == "deterministic_dataset_quality_signal"
    assert report["local_offline_evidence"]["baseline_quality_signal_rate"] == 0.5
    assert report["local_offline_evidence"]["candidate_quality_signal_rate"] == 1.0
    assert report["no_real_robot_evidence"] is True
    assert report["no_isaac_rollout_evidence"] is True
    assert report["proof_source"]["adapter_id"] == "universal_robots_ur_industrial_arm"
    assert Path(report["artifact_paths"]["report"]).exists()
    assert report["buyer_summary"]["mvp2_closed"] is False
    assert "local offline deterministic proxy cannot close mvp-2" in " ".join(report["blockers"]).lower()
    assert report["claim_boundary"]["real_robot_success_claimed"] is False
    assert report["claim_boundary"]["hmd_readiness_claimed"] is False


def test_mvp2_learning_proven_negative_result_is_measured_but_not_closed(tmp_path: Path) -> None:
    script = load_script("run_mvp2_learning_proven_policy_eval")

    report = script.build_mvp2_learning_proven_policy_eval(
        output_dir=tmp_path / "mvp2_learning_proven_policy_eval",
        harness_output_dir=tmp_path / "mvp2_policy_ab_harness",
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_harness=True,
        refresh_mvp1plus=True,
        offline_profile="negative",
        min_rollouts_per_policy=10,
        bootstrap_iterations=200,
    )

    assert report["passed"] is True
    assert report["learning_results_measured"] is True
    assert report["learning_proven"] is False
    assert report["proof_eligible"] is False
    assert report["candidate_success_rate"] < report["baseline_success_rate"]
    assert report["curated_vs_uncurated_uplift"] < 0.0
    assert report["buyer_summary"]["mvp2_closed"] is False


def test_mvp2_learning_proven_tie_result_is_not_closed(tmp_path: Path) -> None:
    script = load_script("run_mvp2_learning_proven_policy_eval")

    report = script.build_mvp2_learning_proven_policy_eval(
        output_dir=tmp_path / "mvp2_learning_proven_policy_eval",
        harness_output_dir=tmp_path / "mvp2_policy_ab_harness",
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_harness=True,
        refresh_mvp1plus=True,
        offline_profile="tie",
        min_rollouts_per_policy=10,
        bootstrap_iterations=200,
    )

    assert report["passed"] is True
    assert report["learning_results_measured"] is True
    assert report["learning_proven"] is False
    assert report["proof_eligible"] is False
    assert report["baseline_success_rate"] == report["candidate_success_rate"]
    assert report["curated_vs_uncurated_uplift"] == 0.0


def test_mvp2_learning_proven_rejects_schema_only_rollout_fixture(tmp_path: Path) -> None:
    script = load_script("run_mvp2_learning_proven_policy_eval")
    harness = load_script("run_mvp2_ur_policy_ab_harness")
    harness_dir = tmp_path / "mvp2_policy_ab_harness"
    harness.build_mvp2_ur_policy_ab_harness(
        output_dir=harness_dir,
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_mvp1plus=True,
    )

    report = script.build_mvp2_learning_proven_policy_eval(
        output_dir=tmp_path / "mvp2_learning_proven_policy_eval",
        harness_output_dir=harness_dir,
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_harness=False,
        refresh_mvp1plus=False,
        baseline_results_path=harness_dir / "rollout_ingest_contract_fixture" / "baseline_rollouts.schema_fixture.json",
        candidate_results_path=harness_dir / "rollout_ingest_contract_fixture" / "candidate_rollouts.schema_fixture.json",
        min_rollouts_per_policy=2,
        bootstrap_iterations=200,
    )

    assert report["passed"] is True
    assert report["learning_proven"] is False
    assert report["proof_eligible"] is False
    assert report["rollout_source"]["source_kind"] == "schema_only_rollout_ingest_contract"
    assert "schema-only rollout ingest fixture cannot close mvp-2" in " ".join(report["blockers"]).lower()


def test_mvp2_learning_proven_rejects_renamed_schema_only_rollout_fixture(tmp_path: Path) -> None:
    script = load_script("run_mvp2_learning_proven_policy_eval")
    harness = load_script("run_mvp2_ur_policy_ab_harness")
    harness_dir = tmp_path / "mvp2_policy_ab_harness"
    harness.build_mvp2_ur_policy_ab_harness(
        output_dir=harness_dir,
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_mvp1plus=True,
    )
    renamed_baseline = tmp_path / "baseline_rollouts_renamed.json"
    renamed_candidate = tmp_path / "candidate_rollouts_renamed.json"
    write_json(
        renamed_baseline,
        read_json(harness_dir / "rollout_ingest_contract_fixture" / "baseline_rollouts.schema_fixture.json"),
    )
    write_json(
        renamed_candidate,
        read_json(harness_dir / "rollout_ingest_contract_fixture" / "candidate_rollouts.schema_fixture.json"),
    )

    report = script.build_mvp2_learning_proven_policy_eval(
        output_dir=tmp_path / "mvp2_learning_proven_policy_eval",
        harness_output_dir=harness_dir,
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_harness=False,
        refresh_mvp1plus=False,
        baseline_results_path=renamed_baseline,
        candidate_results_path=renamed_candidate,
        min_rollouts_per_policy=2,
        bootstrap_iterations=200,
    )

    assert report["learning_proven"] is False
    assert report["proof_eligible"] is False
    assert report["rollout_source"]["source_kind"] == "schema_only_rollout_ingest_contract"
    assert "schema-only rollout ingest fixture cannot close mvp-2" in " ".join(report["blockers"]).lower()


def test_mvp2_learning_proven_rejects_marker_stripped_schema_like_rollouts(tmp_path: Path) -> None:
    script = load_script("run_mvp2_learning_proven_policy_eval")
    baseline_path = tmp_path / "baseline_schema_positive_shape.json"
    candidate_path = tmp_path / "candidate_schema_positive_shape.json"
    write_json(
        baseline_path,
        {
            "rollout_results": [
                {"rollout_id": f"schema_baseline_{index}", "scenario_id": f"scenario_{index}", "success": index < 2}
                for index in range(10)
            ],
        },
    )
    write_json(
        candidate_path,
        {
            "rollout_results": [
                {"rollout_id": f"schema_candidate_{index}", "scenario_id": f"scenario_{index}", "success": index < 9}
                for index in range(10)
            ],
        },
    )

    report = script.build_mvp2_learning_proven_policy_eval(
        output_dir=tmp_path / "mvp2_learning_proven_policy_eval",
        harness_output_dir=tmp_path / "mvp2_policy_ab_harness",
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_harness=True,
        refresh_mvp1plus=True,
        baseline_results_path=baseline_path,
        candidate_results_path=candidate_path,
        min_rollouts_per_policy=10,
        bootstrap_iterations=200,
    )

    assert report["passed"] is True
    assert report["learning_results_measured"] is False
    assert report["learning_proven"] is False
    assert report["proof_eligible"] is False
    assert report["validator_evidence_tier"] is None
    assert report["artifact_paths"]["policy_eval_report"] is None
    assert "schema-like rollout identifiers cannot close mvp-2" in " ".join(report["blockers"]).lower()


def test_mvp2_learning_proven_closes_with_external_trainer_rollout_metadata(tmp_path: Path) -> None:
    script = load_script("run_mvp2_learning_proven_policy_eval")
    baseline_path = tmp_path / "external_baseline_rollouts.json"
    candidate_path = tmp_path / "external_candidate_rollouts.json"
    heldout_suite = external_heldout_suite()
    write_external_rollouts(
        path=baseline_path,
        role="external_baseline",
        success_count=4,
        policy_artifact_id="external_uncurated_policy_artifact",
        heldout_suite=heldout_suite,
    )
    write_external_rollouts(
        path=candidate_path,
        role="external_candidate",
        success_count=7,
        policy_artifact_id="external_curated_policy_artifact",
        heldout_suite=heldout_suite,
    )

    report = script.build_mvp2_learning_proven_policy_eval(
        output_dir=tmp_path / "mvp2_learning_proven_policy_eval",
        harness_output_dir=tmp_path / "mvp2_policy_ab_harness",
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_harness=True,
        refresh_mvp1plus=True,
        baseline_results_path=baseline_path,
        candidate_results_path=candidate_path,
        baseline_policy_id="external_uncurated_policy",
        candidate_policy_id="external_curated_policy",
        policy_class="external_bc_policy",
        trainer="external_eval_runner",
        min_rollouts_per_policy=10,
        bootstrap_iterations=200,
    )

    policy_eval_input = read_json(Path(report["artifact_paths"]["policy_eval_input"]))
    policy_eval_report = read_json(Path(report["artifact_paths"]["policy_eval_report"]))
    assert report["learning_proven"] is True
    assert report["proof_eligible"] is True
    assert report["evidence_tier"] == "external_heldout_policy_eval"
    assert report["validator_evidence_tier"] == "heldout_policy_eval"
    assert report["buyer_summary"]["mvp2_closed"] is True
    assert report["rollout_source"]["source_kind"] == "external_heldout_policy_eval"
    assert policy_eval_input["eval_suite"]["id"] == "external_ur_heldout_policy_eval_suite"
    assert policy_eval_input["eval_suite"]["source_kind"] == "external_trainer_eval_suite"
    assert policy_eval_report["eval_suite"]["id"] == "external_ur_heldout_policy_eval_suite"
    assert "schema_only" not in policy_eval_input["eval_suite"]["id"]
    assert policy_eval_input["baseline"]["policy_id"] == "external_uncurated_policy"
    assert policy_eval_input["candidate"]["policy_id"] == "external_curated_policy"
    assert policy_eval_input["baseline"]["policy_class"] == "external_bc_policy"
    assert policy_eval_input["candidate"]["trainer"] == "external_eval_runner"
    assert report["policy_provenance"]["baseline"]["policy_id"] == "external_uncurated_policy"
    assert report["policy_provenance"]["candidate"]["policy_id"] == "external_curated_policy"
    assert report["policy_provenance"]["baseline"]["policy_class"] == "external_bc_policy"
    assert report["external_rollout_evidence"]["source_kind"] == "external_heldout_policy_eval"


def test_mvp2_learning_proven_blocks_locally_generated_phase_conditioned_rollouts(
    tmp_path: Path,
) -> None:
    script = load_script("run_mvp2_learning_proven_policy_eval")
    baseline_path = tmp_path / "external_baseline_rollouts.json"
    candidate_path = tmp_path / "external_candidate_rollouts.json"
    heldout_suite = external_heldout_suite()
    write_external_rollouts(
        path=baseline_path,
        role="external_baseline",
        success_count=4,
        policy_artifact_id="external_uncurated_policy_artifact",
        heldout_suite=heldout_suite,
    )
    write_external_rollouts(
        path=candidate_path,
        role="external_candidate",
        success_count=7,
        policy_artifact_id="external_curated_policy_artifact",
        heldout_suite=heldout_suite,
    )
    for path in (baseline_path, candidate_path):
        payload = read_json(path)
        payload["training_material_summary"] = {"policy_score": 0.8}
        for rollout in payload["rollout_results"]:
            rollout["success_label_source"] = "phase_conditioned_heldout_task_state_eval"
            rollout["policy_score"] = 0.8
        write_json(path, payload)

    report = script.build_mvp2_learning_proven_policy_eval(
        output_dir=tmp_path / "mvp2_learning_proven_policy_eval",
        harness_output_dir=tmp_path / "mvp2_policy_ab_harness",
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_harness=True,
        refresh_mvp1plus=True,
        baseline_results_path=baseline_path,
        candidate_results_path=candidate_path,
        min_rollouts_per_policy=10,
        bootstrap_iterations=200,
    )

    assert report["passed"] is True
    assert report["learning_results_measured"] is True
    assert report["learning_proven"] is False
    assert report["proof_eligible"] is False
    assert report["evidence_tier"] == "local_phase_conditioned_policy_eval_proxy"
    assert report["validator_evidence_tier"] is None
    assert report["candidate_success_rate"] > report["baseline_success_rate"]
    assert report["artifact_paths"]["policy_eval_report"] is None
    assert "phase-conditioned local evaluator proxy cannot close mvp-2" in " ".join(report["blockers"]).lower()


def test_mvp2_phase_conditioned_eval_records_proxy_without_closing_mvp2(
    tmp_path: Path,
) -> None:
    script = load_script("run_mvp2_phase_conditioned_external_eval")

    report = script.build_mvp2_phase_conditioned_external_eval(
        output_dir=tmp_path / "mvp2_phase_conditioned_external_eval",
        harness_output_dir=tmp_path / "mvp2_policy_ab_harness",
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_harness=True,
        refresh_mvp1plus=True,
        min_rollouts_per_policy=10,
        bootstrap_iterations=200,
    )

    assert report["passed"] is True
    assert report["learning_results_measured"] is True
    assert report["mvp2_closed"] is False
    assert report["proxy_results_measured"] is True
    assert report["proxy_uplift_positive"] is True
    assert report["learning_proven"] is False
    assert report["proof_eligible"] is False
    assert report["evidence_tier"] == "local_phase_conditioned_policy_eval_proxy"
    assert report["validator_evidence_tier"] is None
    assert report["candidate_success_rate"] > report["baseline_success_rate"]
    assert report["curated_vs_uncurated_uplift"] > 0.0
    assert report["selected_policy_class"] == "phase_conditioned_sequence_bc_policy_v0"
    assert report["selected_trainer"] == "rdf_phase_conditioned_sequence_bc_trainer_contract_v0"
    assert report["external_rollout_evidence"] is None
    assert report["local_phase_conditioned_evidence"]["source_kind"] == "local_phase_conditioned_policy_eval_proxy"
    assert report["claim_boundary"]["real_robot_success_claimed"] is False
    assert report["claim_boundary"]["physical_robot_readiness_claimed"] is False
    assert report["claim_boundary"]["hmd_readiness_claimed"] is False
    assert report["claim_boundary"]["schema_only_rollout_fixture_used_for_uplift"] is False
    assert report["claim_boundary"]["mvp2_learning_proven_claimed"] is False
    assert Path(report["artifact_paths"]["baseline_rollouts"]).exists()
    assert Path(report["artifact_paths"]["candidate_rollouts"]).exists()
    assert Path(report["artifact_paths"]["mvp2_learning_proven_report"]).exists()
    assert report["artifact_paths"]["policy_eval_report"] is None
    assert report["buyer_summary"]["mvp2_closed"] is False
    assert "phase-conditioned local evaluator proxy cannot close mvp-2" in " ".join(report["blockers"]).lower()

    baseline = read_json(Path(report["artifact_paths"]["baseline_rollouts"]))
    candidate = read_json(Path(report["artifact_paths"]["candidate_rollouts"]))
    assert baseline["source_kind"] == "local_phase_conditioned_policy_eval_proxy"
    assert candidate["source_kind"] == "local_phase_conditioned_policy_eval_proxy"
    assert baseline["proof_role"] == "local_phase_conditioned_policy_eval_proxy"
    assert candidate["proof_role"] == "local_phase_conditioned_policy_eval_proxy"
    assert baseline["heldout_suite"] == candidate["heldout_suite"]
    assert baseline["trainer"] == candidate["trainer"]
    assert "schema_only" not in json.dumps(baseline).lower()
    assert "schema_only" not in json.dumps(candidate).lower()
    assert "deterministic_dataset_quality_signal" not in json.dumps(baseline).lower()
    assert "deterministic_dataset_quality_signal" not in json.dumps(candidate).lower()
    assert "local_offline_policy_eval_proxy" not in json.dumps(baseline).lower()
    assert "local_offline_policy_eval_proxy" not in json.dumps(candidate).lower()


def test_mvp2_writes_external_proof_template_without_closing(tmp_path: Path) -> None:
    script = load_script("run_mvp2_learning_proven_policy_eval")
    template_dir = tmp_path / "mvp2_external_policy_eval_template"

    report = script.build_mvp2_external_policy_eval_template(
        output_dir=template_dir,
        harness_output_dir=tmp_path / "mvp2_policy_ab_harness",
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_harness=True,
        refresh_mvp1plus=True,
    )

    request = read_json(Path(report["artifact_paths"]["request"]))
    baseline_template = read_json(Path(report["artifact_paths"]["baseline_template"]))
    candidate_template = read_json(Path(report["artifact_paths"]["candidate_template"]))

    assert report["passed"] is True
    assert report["proof_ready"] is False
    assert report["mvp2_closed"] is False
    assert report["template_is_not_evidence"] is True
    assert report["required_final_source_kind"] == "external_heldout_policy_eval"
    assert request["template_is_not_evidence"] is True
    assert request["required_final_source_kind"] == "external_heldout_policy_eval"
    assert baseline_template["source_kind"] == "external_heldout_policy_eval_template"
    assert baseline_template["proof_role"] == "external_trainer_policy_eval_template"
    assert baseline_template["rollout_results"] == []
    assert candidate_template["source_kind"] == "external_heldout_policy_eval_template"
    assert candidate_template["proof_role"] == "external_trainer_policy_eval_template"
    assert candidate_template["rollout_results"] == []
    assert baseline_template["heldout_suite"]["source_kind"] == "external_trainer_eval_suite"
    assert baseline_template["heldout_suite"]["proof_role"] == "external_policy_eval_suite"
    assert candidate_template["heldout_suite"] == baseline_template["heldout_suite"]
    assert not any("schema_only" in item for item in baseline_template["heldout_suite"]["scenario_ids"])
    assert "template cannot close mvp-2" in " ".join(report["limitations"]).lower()


def test_mvp2_rejects_unfilled_external_proof_template_before_validator(tmp_path: Path) -> None:
    script = load_script("run_mvp2_learning_proven_policy_eval")
    template_report = script.build_mvp2_external_policy_eval_template(
        output_dir=tmp_path / "mvp2_external_policy_eval_template",
        harness_output_dir=tmp_path / "mvp2_policy_ab_harness",
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_harness=True,
        refresh_mvp1plus=True,
    )

    report = script.build_mvp2_learning_proven_policy_eval(
        output_dir=tmp_path / "mvp2_learning_proven_policy_eval",
        harness_output_dir=tmp_path / "mvp2_policy_ab_harness",
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_harness=False,
        refresh_mvp1plus=False,
        baseline_results_path=Path(template_report["artifact_paths"]["baseline_template"]),
        candidate_results_path=Path(template_report["artifact_paths"]["candidate_template"]),
        min_rollouts_per_policy=10,
        bootstrap_iterations=200,
    )

    assert report["passed"] is True
    assert report["learning_results_measured"] is False
    assert report["learning_proven"] is False
    assert report["proof_eligible"] is False
    assert report["validator_evidence_tier"] is None
    assert report["artifact_paths"]["policy_eval_report"] is None
    assert "external rollout results are missing proof-grade provenance" in " ".join(report["blockers"]).lower()
    assert "source_kind must be external_heldout_policy_eval" in " ".join(report["blockers"]).lower()
    assert "rollout_results are required" in " ".join(report["blockers"]).lower()


def test_mvp2_learning_proven_blocks_external_rollouts_without_proof_provenance(tmp_path: Path) -> None:
    script = load_script("run_mvp2_learning_proven_policy_eval")
    baseline_path = tmp_path / "external_baseline_rollouts.json"
    candidate_path = tmp_path / "external_candidate_rollouts.json"
    write_json(
        baseline_path,
        {
            "source_kind": "external_rollout_results",
            "rollout_results": [
                {"rollout_id": f"external_baseline_{index}", "scenario_id": f"scenario_{index}", "success": index < 4}
                for index in range(10)
            ],
        },
    )
    write_json(
        candidate_path,
        {
            "source_kind": "external_rollout_results",
            "rollout_results": [
                {"rollout_id": f"external_candidate_{index}", "scenario_id": f"scenario_{index}", "success": index < 7}
                for index in range(10)
            ],
        },
    )

    report = script.build_mvp2_learning_proven_policy_eval(
        output_dir=tmp_path / "mvp2_learning_proven_policy_eval",
        harness_output_dir=tmp_path / "mvp2_policy_ab_harness",
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_harness=True,
        refresh_mvp1plus=True,
        baseline_results_path=baseline_path,
        candidate_results_path=candidate_path,
        min_rollouts_per_policy=10,
        bootstrap_iterations=200,
    )

    assert report["learning_results_measured"] is False
    assert report["learning_proven"] is False
    assert report["proof_eligible"] is False
    assert report["artifact_paths"]["policy_eval_report"] is None
    assert "external rollout results are missing proof-grade provenance" in " ".join(report["blockers"]).lower()


def test_mvp2_learning_proven_blocks_external_rollouts_with_schema_only_scenario_ids(tmp_path: Path) -> None:
    script = load_script("run_mvp2_learning_proven_policy_eval")
    baseline_path = tmp_path / "external_baseline_rollouts.json"
    candidate_path = tmp_path / "external_candidate_rollouts.json"
    heldout_suite = external_heldout_suite()
    heldout_suite["scenario_ids"] = ["schema_only_scenario_for_fixture"]
    write_external_rollouts(
        path=baseline_path,
        role="external_baseline",
        success_count=4,
        policy_artifact_id="external_uncurated_policy_artifact",
        heldout_suite=heldout_suite,
    )
    write_external_rollouts(
        path=candidate_path,
        role="external_candidate",
        success_count=7,
        policy_artifact_id="external_curated_policy_artifact",
        heldout_suite=heldout_suite,
    )

    report = script.build_mvp2_learning_proven_policy_eval(
        output_dir=tmp_path / "mvp2_learning_proven_policy_eval",
        harness_output_dir=tmp_path / "mvp2_policy_ab_harness",
        mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
        clean=True,
        refresh_harness=True,
        refresh_mvp1plus=True,
        baseline_results_path=baseline_path,
        candidate_results_path=candidate_path,
        min_rollouts_per_policy=10,
        bootstrap_iterations=200,
    )

    assert report["passed"] is True
    assert report["learning_results_measured"] is False
    assert report["learning_proven"] is False
    assert report["proof_eligible"] is False
    assert report["validator_evidence_tier"] is None
    assert report["artifact_paths"]["policy_eval_report"] is None
    assert "heldout_suite.scenario_ids cannot be schema-only" in " ".join(report["blockers"]).lower()


def test_mvp2_learning_proven_blocks_when_harness_not_ready(tmp_path: Path) -> None:
    script = load_script("run_mvp2_learning_proven_policy_eval")
    harness_dir = tmp_path / "mvp2_policy_ab_harness"
    write_json(
        harness_dir / "mvp2_policy_ab_harness_report.json",
        {
            "schema_version": "rdf_mvp2_ur_policy_ab_harness_v0.1.0",
            "passed": False,
            "harness_ready": False,
            "artifact_paths": {},
            "proof_source": {},
            "limitations": ["forced not ready"],
        },
    )

    try:
        script.build_mvp2_learning_proven_policy_eval(
            output_dir=tmp_path / "mvp2_learning_proven_policy_eval",
            harness_output_dir=harness_dir,
            mvp1plus_output_dir=tmp_path / "mvp1plus_embodiment_proof",
            clean=True,
            refresh_harness=False,
            refresh_mvp1plus=False,
        )
    except ValueError as exc:
        assert "harness readiness gate failed" in str(exc).lower()
    else:
        raise AssertionError("expected harness readiness gate failure")
