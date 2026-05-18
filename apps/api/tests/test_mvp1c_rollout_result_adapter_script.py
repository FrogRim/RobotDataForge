from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]


def load_script(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


readiness = load_script("run_mvp1_offline_readiness")
headless_bundle = load_script("run_mvp1c_headless_eval_bundle")
adapter = load_script("run_mvp1c_rollout_result_adapter")
real_eval = load_script("run_mvp1c_real_policy_eval")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def prepare_template(tmp_path: Path) -> tuple[Path, Path]:
    readiness_dir = tmp_path / "mvp1_readiness"
    bundle_dir = tmp_path / "mvp1c_headless_eval"
    assert readiness.build_bundle(readiness_dir, clean=True)["passed"] is True
    assert headless_bundle.build_headless_eval_bundle(
        readiness_dir=readiness_dir,
        output_dir=bundle_dir,
        clean=True,
    )["passed"] is True
    return readiness_dir, bundle_dir / "policy_eval_input_template.json"


def test_rollout_result_adapter_converts_csv_and_json_to_policy_eval_input(tmp_path: Path) -> None:
    _, template_path = prepare_template(tmp_path)
    baseline_csv = tmp_path / "baseline_rollouts.csv"
    baseline_csv.write_text(
        "rollout_id,scenario_id,success,failure_reason\n"
        "b0,s0,true,\n"
        "b1,s1,false,missed_insert\n"
        "b2,s2,1,\n",
        encoding="utf-8",
    )
    candidate_json = tmp_path / "candidate_rollouts.json"
    write_json(
        candidate_json,
        {
            "rollout_results": [
                {"rollout_id": "c0", "scenario_id": "s0", "success": True},
                {"rollout_id": "c1", "scenario_id": "s1", "success": True},
                {"rollout_id": "c2", "scenario_id": "s2", "success": False},
            ]
        },
    )

    output_path = tmp_path / "policy_eval_input.json"
    report = adapter.build_policy_eval_input(
        template_path=template_path,
        baseline_results_path=baseline_csv,
        candidate_results_path=candidate_json,
        output_path=output_path,
        baseline_policy_id="policy_uncurated_test",
        candidate_policy_id="policy_curated_test",
        policy_class="ACT",
        trainer="headless_fixture_trainer",
    )

    assert report["passed"] is True
    assert output_path.exists()
    generated = read_json(output_path)
    assert generated["baseline"]["policy_id"] == "policy_uncurated_test"
    assert generated["candidate"]["policy_id"] == "policy_curated_test"
    assert generated["baseline"]["policy_class"] == "ACT"
    assert generated["candidate"]["trainer"] == "headless_fixture_trainer"
    assert len(generated["baseline"]["rollout_results"]) == 3
    assert len(generated["candidate"]["rollout_results"]) == 3
    assert generated["rollout_result_adapter"]["does_not_update_manifest"] is True
    assert generated["rollout_result_adapter"]["baseline_success_rate"] == 2 / 3
    assert generated["rollout_result_adapter"]["candidate_success_rate"] == 2 / 3


def test_adapter_output_can_be_ingested_by_real_eval_without_manifest_update(tmp_path: Path) -> None:
    _, template_path = prepare_template(tmp_path)
    baseline_json = tmp_path / "baseline_rollouts.json"
    candidate_json = tmp_path / "candidate_rollouts.json"
    write_json(
        baseline_json,
        [{"rollout_id": f"b{index}", "scenario_id": f"s{index}", "success": index < 2} for index in range(5)],
    )
    write_json(
        candidate_json,
        [{"rollout_id": f"c{index}", "scenario_id": f"s{index}", "success": index < 4} for index in range(5)],
    )
    output_path = tmp_path / "policy_eval_input.json"
    adapter.build_policy_eval_input(
        template_path=template_path,
        baseline_results_path=baseline_json,
        candidate_results_path=candidate_json,
        output_path=output_path,
        policy_class="ACT",
        trainer="headless_fixture_trainer",
    )

    eval_report = real_eval.run_real_policy_eval(
        input_path=output_path,
        output_path=tmp_path / "policy_uplift_real_eval_report.json",
        experiment_manifest_path=tmp_path / "unused_manifest.json",
        update_manifest=False,
        min_rollouts_per_policy=5,
        bootstrap_iterations=200,
    )

    assert eval_report["passed"] is True
    assert eval_report["proof_eligible"] is True
    assert eval_report["baseline_success_rate"] == 0.4
    assert eval_report["candidate_success_rate"] == 0.8


def test_rollout_result_adapter_supports_aggregate_counts(tmp_path: Path) -> None:
    _, template_path = prepare_template(tmp_path)
    baseline_json = tmp_path / "baseline_aggregate.json"
    candidate_json = tmp_path / "candidate_aggregate.json"
    write_json(baseline_json, {"rollout_count": 4, "success_count": 1})
    write_json(candidate_json, {"rollout_count": 4, "success_count": 3})

    output_path = tmp_path / "policy_eval_input.json"
    report = adapter.build_policy_eval_input(
        template_path=template_path,
        baseline_results_path=baseline_json,
        candidate_results_path=candidate_json,
        output_path=output_path,
    )

    assert report["adapter_metadata"]["baseline_rollout_count"] == 4
    assert report["adapter_metadata"]["candidate_rollout_count"] == 4
    generated = read_json(output_path)
    assert sum(row["success"] for row in generated["baseline"]["rollout_results"]) == 1
    assert sum(row["success"] for row in generated["candidate"]["rollout_results"]) == 3
