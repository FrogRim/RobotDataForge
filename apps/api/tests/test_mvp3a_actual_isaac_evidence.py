from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_verify_proof_package import _policy_artifact, _write_json


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "run_mvp3a_actual_isaac_evidence.py"


def _load_script():
    name = "run_mvp3a_actual_isaac_evidence"
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class FakeBackend:
    runtime_backend = "isaac_runtime"
    proof_runtime = "dedicated_isaac_connector_insertion_evaluator"

    def run_single_policy_probe(
        self,
        *,
        manifest,
        output_dir,
        policy_artifact,
        role,
        max_rollouts,
        stop_after_first_success,
    ):
        del max_rollouts, stop_after_first_success
        output_dir = Path(output_dir)
        trace_dir = output_dir / "isaac_runtime_heldout_rollout_traces"
        trace_dir.mkdir(parents=True, exist_ok=True)
        rollouts = []
        trace_paths = []
        for index, scenario in enumerate(manifest["scenarios"]):
            success = role == "candidate" or scenario["scenario_id"].startswith("train_")
            mask = [False, *([True] * 10 if success else [True, True, False])]
            trace_path = trace_dir / f"{role}_{index:04d}_{scenario['scenario_id']}_isaac_trace.json"
            _write_json(
                trace_path,
                {
                    "trace": [{"env_native_success": value} for value in mask],
                    "summary": {
                        "success": success,
                        "env_native_max_consecutive_success_steps": 10 if success else 2,
                    },
                },
            )
            trace_paths.append(str(trace_path))
            rollouts.append(
                {
                    "rollout_id": f"{role}_isaac_{index:04d}",
                    "scenario_id": scenario["scenario_id"],
                    "success": success,
                    "env_native_rollout_success": success,
                    "env_native_max_consecutive_success_steps": 10 if success else 2,
                    "rollout_log_ref": str(trace_path),
                }
            )
        return SimpleNamespace(
            runtime_gate={
                "passed": True,
                "runtime_backend": self.runtime_backend,
                "proof_runtime": self.proof_runtime,
            },
            baseline_rollouts=rollouts,
            candidate_rollouts=[],
            baseline_trace_paths=trace_paths,
            candidate_trace_paths=[],
        )


def test_collect_actual_evidence_writes_bound_rollouts_masks_and_config(tmp_path: Path):
    module = _load_script()
    baseline_policy = tmp_path / "baseline_policy.json"
    candidate_policy = tmp_path / "candidate_policy.json"
    _write_json(baseline_policy, _policy_artifact("baseline"))
    _write_json(candidate_policy, _policy_artifact("candidate"))

    result = module.collect_actual_evidence(
        output_dir=tmp_path / "evidence",
        package_dir=tmp_path / "package",
        baseline_policy_path=baseline_policy,
        candidate_policy_path=candidate_policy,
        backend=FakeBackend(),
        train_seeds=range(43000, 43001),
        calibration_seeds=range(41000, 41002),
        heldout_seeds=range(42000, 42003),
    )

    assert result.config_path.is_file()
    train_manifest = json.loads(
        (result.output_dir / "train_candidate_scenario_manifest.json").read_text()
    )
    assert train_manifest["success_metric"]["insertion_depth_m_min"] == 0.03
    assert train_manifest["success_metric"]["lateral_error_m_max"] == 0.006
    heldout_candidate = json.loads(
        (result.output_dir / "candidate_heldout_rollouts.json").read_text()
    )
    candidate_hash = json.loads(candidate_policy.read_text())["policy_artifact_sha256"]
    assert [row["seed"] for row in heldout_candidate["rollout_results"]] == [
        42000,
        42001,
        42002,
    ]
    assert {
        row["policy_artifact_sha256"] for row in heldout_candidate["rollout_results"]
    } == {candidate_hash}
    masks = json.loads((result.output_dir / "heldout_candidate_success_masks.json").read_text())
    assert len(masks["masks"]) == 3
    assert masks["masks"][0]["env_native_success_mask"].count(True) == 10
    config = json.loads(result.config_path.read_text())
    assert config["evidence_kind"] == "actual_isaac"
    assert config["package_policy"]["output_dir"] == str(tmp_path / "package")
    for path in config["evidence_paths"].values():
        assert Path(path).is_file()


def test_subprocess_split_backend_reads_child_result(tmp_path: Path, monkeypatch):
    module = _load_script()
    policy = _policy_artifact("candidate")

    def fake_run(cmd, **kwargs):
        del kwargs
        result_path = Path(cmd[cmd.index("--result") + 1])
        output_dir = Path(cmd[cmd.index("--output-dir") + 1])
        trace_path = output_dir / "trace.json"
        _write_json(trace_path, {"trace": [{"env_native_success": True}]})
        _write_json(
            result_path,
            {
                "runtime_gate": {
                    "passed": True,
                    "runtime_backend": "isaac_runtime",
                    "proof_runtime": "dedicated_isaac_connector_insertion_evaluator",
                },
                "rollouts": [{"scenario_id": "train_43000", "success": True}],
                "trace_paths": [str(trace_path)],
            },
        )
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    backend = module.SubprocessSplitBackend(
        isaac_python=Path("/tmp/isaac-python"),
        headless=True,
        device="cuda:0",
        max_steps=150,
    )

    result = backend.run_single_policy_probe(
        manifest={"scenarios": [{"scenario_id": "train_43000", "seed": 43000}]},
        output_dir=tmp_path / "runtime",
        policy_artifact=policy,
        role="candidate",
        max_rollouts=1,
        stop_after_first_success=False,
    )

    assert result.runtime_gate["passed"] is True
    assert result.baseline_rollouts[0]["success"] is True
    assert Path(result.baseline_trace_paths[0]).is_file()
