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
uplift_smoke = load_script("run_mvp1c_policy_uplift_smoke")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_mvp1c_policy_uplift_smoke_writes_proxy_measurement_without_claiming_proof(tmp_path: Path) -> None:
    output_dir = tmp_path / "mvp1_readiness"
    assert readiness.build_bundle(output_dir, clean=True)["passed"] is True

    report = uplift_smoke.run_policy_uplift_smoke(
        readiness_dir=output_dir,
        output_path=output_dir / "policy_uplift_smoke_report.json",
        experiment_manifest_path=output_dir / "curated_vs_uncurated_experiment_manifest.json",
    )

    assert report["passed"] is True
    assert report["proof_eligible"] is False
    assert report["evidence_tier"] == "offline_proxy_smoke"
    assert report["primary_metric"] == "action_prediction_score"
    assert report["learning_results_measured"] is False
    assert report["curated_vs_uncurated_uplift"] is None
    assert report["baseline"]["test_score"] is not None
    assert report["candidate"]["test_score"] is not None
    assert report["curated_vs_uncurated_proxy_delta"] is not None
    assert report["baseline"]["sample_count"]["train"] > report["candidate"]["sample_count"]["train"]

    manifest = read_json(output_dir / "curated_vs_uncurated_experiment_manifest.json")
    assert manifest["learning_results_measured"] is False
    assert manifest["curated_vs_uncurated_uplift"] is None
    assert manifest["policy_uplift_smoke"]["proof_eligible"] is False
    assert manifest["policy_uplift_smoke"]["evidence_tier"] == "offline_proxy_smoke"
    assert manifest["policy_uplift_smoke"]["report_path"] == str(output_dir / "policy_uplift_smoke_report.json")
