from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _load_verifier():
    name = "verify_proof_package"
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
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


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_payload_sha256(payload: dict, *, omit_key: str) -> str:
    canonical = dict(payload)
    canonical.pop(omit_key, None)
    return hashlib.sha256(_stable_json(canonical).encode("utf-8")).hexdigest()


def _policy_artifact(role: str) -> dict:
    payload = {
        "policy_id": f"mvp3a_{role}_policy",
        "policy_role": role,
        "policy_family": "synthetic_test_policy",
        "created_for": "mvp3a_target_fixture_pose_variant",
    }
    payload["policy_artifact_sha256"] = _canonical_payload_sha256(
        payload, omit_key="policy_artifact_sha256"
    )
    return payload


def _rehash_manifest_data_file(manifest: Path, rel: str) -> None:
    payload = json.loads(manifest.read_text())
    payload.setdefault("artifact_index", []).append(
        {
            "data_path": rel,
            "hash_convention": "file_bytes",
            "file_sha256": _sha(manifest.parent / rel),
        }
    )
    _write_json(manifest, payload)


def _rollout(seed: int, consecutive: int, *, policy_hash: str | None = None) -> dict:
    row = {
        "scenario_id": f"mvp3a_seed_{seed}",
        "seed": seed,
        "success": consecutive >= 10,
        "env_native_rollout_success": consecutive >= 10,
        "env_native_max_consecutive_success_steps": consecutive,
    }
    if policy_hash:
        row["policy_artifact_sha256"] = policy_hash
    return row


def _rollouts(
    seeds: range, success_count: int, *, policy_hash: str | None = None
) -> dict:
    rows = []
    for index, seed in enumerate(seeds):
        rows.append(
            _rollout(
                seed,
                10 if index < success_count else 3,
                policy_hash=policy_hash,
            )
        )
    return {"rollout_results": rows}


def _make_package(
    tmp_path: Path,
    *,
    positive: bool = True,
    evidence_kind: str = "synthetic_test_fixture",
    include_actual_provenance: bool = False,
) -> Path:
    pkg = tmp_path / "pkg"
    data = pkg / "data"
    heldout_candidate_successes = 40 if positive else 5
    actual_isaac = evidence_kind == "actual_isaac"
    baseline_policy = _policy_artifact("baseline")
    candidate_policy = _policy_artifact("candidate")
    baseline_policy_hash = (
        baseline_policy["policy_artifact_sha256"] if include_actual_provenance else None
    )
    candidate_policy_hash = (
        candidate_policy["policy_artifact_sha256"] if include_actual_provenance else None
    )

    files = {
        "data/config.json": {
            "proof_slice": "mvp3a_target_fixture_pose_variant",
            "evidence_kind": evidence_kind,
            "runtime_expectations": {
                "backend": "isaac_runtime",
                "proof_runtime": "dedicated_isaac_connector_insertion_evaluator",
                "training_source": "isaac_runtime",
            },
            "seed_ranges": {
                "train": [43000, 43049],
                "calibration": [41000, 41029],
                "heldout": [42000, 42049],
                "spent_no_reuse": [[40000, 40049]],
            },
            "thresholds": {
                "uplift_min": 0.2,
                "min_calibration_rollouts_per_policy": 30,
                "min_heldout_rollouts_per_policy": 50,
                "stable_steps_required": 10,
            },
            "audit_ci": {
                "method": "bootstrap_success_rate_difference",
                "iterations": 200,
                "seed": 20260620,
            },
        },
        "data/task_variant_attestation.json": {
            "family": "connector_insertion",
            "variant": "target_fixture_pose_variant",
            "source_variable_opened": False,
        },
        "data/non_claims_attestation.json": {
            "real_robot_success": False,
            "physical_robot_readiness": False,
            "deployable_policy_readiness": False,
            "visual_policy_performance": False,
            "hmd_openxr_collection_readiness": False,
            "universal_robot_support": False,
            "ur_adapter_support": False,
            "ros2_dds_adapter_support": False,
            "franka_hardware_support": False,
            "marketplace_readiness": False,
            "production_certification": False,
        },
        "data/gates/runtime_gate.json": {
            "passed": True,
            "runtime_backend": "isaac_runtime",
            "proof_runtime": "dedicated_isaac_connector_insertion_evaluator",
        },
        "data/gates/train_generation_runtime_gate.json": {
            "passed": True,
            "runtime_backend": "isaac_runtime",
            "actual_train_generation_evidence": True,
            "training_trajectory_source": "isaac_runtime",
        },
        "data/gates/calibration_selection_report.json": {
            "calibration_only_selection_passed": True,
            "heldout_excluded": True,
            "selected_adapter_frozen_before_heldout": True,
            "same_adapter_used_for_baseline_and_candidate": True,
        },
        "data/gates/train_trace_summary.json": {"actual_success_trace_count": 1},
        "data/gates/post_heldout_guard.json": {"passed": True},
        "data/rollouts/calibration_baseline_rollouts.json": _rollouts(
            range(41000, 41030), 5, policy_hash=baseline_policy_hash
        ),
        "data/rollouts/calibration_candidate_rollouts.json": _rollouts(
            range(41000, 41030), 26, policy_hash=candidate_policy_hash
        ),
        "data/rollouts/heldout_baseline_rollouts.json": _rollouts(
            range(42000, 42050), 5, policy_hash=baseline_policy_hash
        ),
        "data/rollouts/heldout_candidate_rollouts.json": _rollouts(
            range(42000, 42050),
            heldout_candidate_successes,
            policy_hash=candidate_policy_hash,
        ),
    }
    if include_actual_provenance:
        files["data/policies/baseline_policy_artifact.json"] = baseline_policy
        files["data/policies/candidate_policy_artifact.json"] = candidate_policy
        files["data/masks/heldout_baseline_success_masks.json"] = _mask_doc(
            range(42000, 42050), 5
        )
        files["data/masks/heldout_candidate_success_masks.json"] = _mask_doc(
            range(42000, 42050), heldout_candidate_successes
        )

    baseline_rate = 5 / 50
    candidate_rate = heldout_candidate_successes / 50
    uplift = candidate_rate - baseline_rate
    status = "positive_uplift" if positive else "non_closing"
    addendum = "present" if actual_isaac and positive else "absent"
    files["data/learning_result_summary.json"] = {
        "baseline_heldout_success_rate": baseline_rate,
        "candidate_heldout_success_rate": candidate_rate,
        "heldout_uplift": uplift,
        "learning_result": status,
        "learning_proven_addendum": addendum,
    }
    files["data/closure_verdict.json"] = {
        "package_status": "proof_infrastructure_closed"
        if actual_isaac
        else "synthetic_verifier_fixture",
        "learning_result": status,
        "learning_proven_addendum": addendum,
        "baseline_heldout_successes": 5,
        "candidate_heldout_successes": heldout_candidate_successes,
        "heldout_uplift": uplift,
        "closed": positive,
    }
    files["data/seed_discipline_report.json"] = {
        "passed": True,
        "spent_after_closure_attempt": [42000, 42049],
    }

    for rel, payload in files.items():
        _write_json(pkg / rel, payload)

    if addendum == "present":
        addendum_dir = pkg / "addenda" / "learning_proven"
        _write_json(
            addendum_dir / "learning_proven_report.json",
            {
                "learning_result": status,
                "heldout_uplift": uplift,
                "baseline_heldout_success_rate": baseline_rate,
                "candidate_heldout_success_rate": candidate_rate,
            },
        )
        _write_json(
            addendum_dir / "package_manifest.json",
            {
                "package_name": "mvp3a_learning_proven_addendum",
                "artifact_index": [
                    {
                        "data_path": "learning_proven_report.json",
                        "hash_convention": "file_bytes",
                        "file_sha256": _sha(addendum_dir / "learning_proven_report.json"),
                    }
                ],
            },
        )

    artifact_index = []
    for rel in sorted(files):
        artifact_index.append(
            {
                "data_path": rel,
                "hash_convention": "file_bytes",
                "file_sha256": _sha(pkg / rel),
            }
        )
    _write_json(data / "artifact_index.json", {"artifact_index": artifact_index})
    artifact_index.append(
        {
            "data_path": "data/artifact_index.json",
            "hash_convention": "file_bytes",
            "file_sha256": _sha(data / "artifact_index.json"),
        }
    )
    manifest = {
        "package_name": "mvp3a_target_fixture_pose_variant_proof_package",
        "artifact_index": artifact_index,
        "claims": {
            "package_status": "proof_infrastructure_closed"
            if actual_isaac
            else "synthetic_verifier_fixture",
            "learning_result": status,
            "learning_proven_addendum": addendum,
        },
    }
    _write_json(pkg / "package_manifest.json", manifest)
    return pkg / "package_manifest.json"


def _tamper_json(path: Path, edit) -> None:
    payload = json.loads(path.read_text())
    edit(payload)
    _write_json(path, payload)


def _mask_doc(seeds: range, success_count: int) -> dict:
    rows = []
    for index, seed in enumerate(seeds):
        if index < success_count:
            mask = [False, True, True, True, True, True, True, True, True, True, True]
        else:
            mask = [False, True, True, True, False, True]
        rows.append(
            {
                "scenario_id": f"mvp3a_seed_{seed}",
                "seed": seed,
                "env_native_success_mask": mask,
            }
        )
    return {"masks": rows}


def test_valid_positive_package_verifies_from_rollouts(tmp_path: Path):
    manifest = _make_package(tmp_path, positive=True)
    verifier = _load_verifier()

    report = verifier.verify_package(manifest)

    assert report.ok is True, report.failures()
    assert report.recomputed["heldout"]["baseline"]["successes"] == 5
    assert report.recomputed["heldout"]["candidate"]["successes"] == 40
    assert abs(report.recomputed["heldout"]["uplift"] - 0.70) < 1e-9
    assert report.recomputed["learning_result"] == "positive_uplift"


def test_valid_nonclosing_package_verifies_without_addendum(tmp_path: Path):
    manifest = _make_package(tmp_path, positive=False)
    verifier = _load_verifier()

    report = verifier.verify_package(manifest)

    assert report.ok is True, report.failures()
    assert report.recomputed["learning_result"] == "non_closing"
    assert report.recomputed["learning_proven_addendum"] == "absent"


def test_actual_isaac_package_requires_provenance_binding(tmp_path: Path):
    manifest = _make_package(
        tmp_path,
        positive=True,
        evidence_kind="actual_isaac",
        include_actual_provenance=False,
    )

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert any("actual_isaac_provenance" in failure for failure in report.failures())


def test_actual_isaac_package_verifies_with_policy_and_mask_binding(tmp_path: Path):
    manifest = _make_package(
        tmp_path,
        positive=True,
        evidence_kind="actual_isaac",
        include_actual_provenance=True,
    )

    report = _load_verifier().verify_package(manifest)

    assert report.ok is True, report.failures()
    assert report.recomputed["package_status"] == "proof_infrastructure_closed"
    assert report.recomputed["learning_proven_addendum"] == "present"
    assert report.recomputed["c_lite"]["checked"] == 100


def test_actual_isaac_gate_failure_recomputes_failed_package_status(tmp_path: Path):
    manifest = _make_package(
        tmp_path,
        positive=True,
        evidence_kind="actual_isaac",
        include_actual_provenance=True,
    )
    _tamper_json(
        manifest.parent / "data" / "gates" / "train_trace_summary.json",
        lambda p: p.update({"actual_success_trace_count": 0}),
    )
    _rehash_manifest_data_file(manifest, "data/gates/train_trace_summary.json")

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert report.recomputed["package_status"] == "proof_infrastructure_failed"
    assert any("gate_recompute" in failure for failure in report.failures())
    assert any("package_status_consistency" in failure for failure in report.failures())


def test_fake_actual_isaac_config_line_cannot_mint_closed_status(tmp_path: Path):
    manifest = _make_package(tmp_path, positive=True)
    _tamper_json(
        manifest.parent / "data" / "config.json",
        lambda p: p.update({"evidence_kind": "actual_isaac"}),
    )
    _tamper_json(
        manifest,
        lambda p: p["claims"].update(
            {
                "package_status": "proof_infrastructure_closed",
                "learning_proven_addendum": "present",
            }
        ),
    )
    _tamper_json(
        manifest.parent / "data" / "closure_verdict.json",
        lambda p: p.update(
            {
                "package_status": "proof_infrastructure_closed",
                "learning_proven_addendum": "present",
            }
        ),
    )
    _tamper_json(
        manifest.parent / "data" / "learning_result_summary.json",
        lambda p: p.update({"learning_proven_addendum": "present"}),
    )

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert any("actual_isaac_provenance" in failure for failure in report.failures())


def test_closure_verdict_cannot_override_rollout_recompute(tmp_path: Path):
    manifest = _make_package(tmp_path, positive=False)
    closure = manifest.parent / "data" / "closure_verdict.json"
    _tamper_json(
        closure,
        lambda p: p.update(
            {"learning_result": "positive_uplift", "learning_proven_addendum": "present"}
        ),
    )

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert any("closure_summary_consistency" in failure for failure in report.failures())


def test_synthetic_fixture_cannot_claim_proof_infrastructure_closed(tmp_path: Path):
    manifest = _make_package(tmp_path, positive=True)
    _tamper_json(
        manifest,
        lambda p: p["claims"].update({"package_status": "proof_infrastructure_closed"}),
    )
    _tamper_json(
        manifest.parent / "data" / "closure_verdict.json",
        lambda p: p.update({"package_status": "proof_infrastructure_closed"}),
    )

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert any("package_status_consistency" in failure for failure in report.failures())


def test_rollout_success_label_tamper_fails_level_b(tmp_path: Path):
    manifest = _make_package(tmp_path)
    rollout_path = (
        manifest.parent / "data" / "rollouts" / "heldout_candidate_rollouts.json"
    )
    _tamper_json(rollout_path, lambda p: p["rollout_results"][0].update({"success": False}))

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert any("label_recompute" in failure for failure in report.failures())


def test_non_claim_true_tamper_fails(tmp_path: Path):
    manifest = _make_package(tmp_path)
    claims_path = manifest.parent / "data" / "non_claims_attestation.json"
    _tamper_json(claims_path, lambda p: p.update({"real_robot_success": True}))

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert any("non_claims" in failure for failure in report.failures())


def test_gate_runtime_tamper_fails_closure_consistency(tmp_path: Path):
    manifest = _make_package(tmp_path)
    runtime_path = manifest.parent / "data" / "gates" / "runtime_gate.json"
    _tamper_json(runtime_path, lambda p: p.update({"proof_runtime": "wrong_runtime"}))

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert any("gate_recompute" in failure for failure in report.failures())


def test_heldout_spent_overlap_fails(tmp_path: Path):
    manifest = _make_package(tmp_path)
    config_path = manifest.parent / "data" / "config.json"
    _tamper_json(config_path, lambda p: p["seed_ranges"].update({"heldout": [40000, 40049]}))

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert any("spent_no_reuse" in failure for failure in report.failures())


def test_mvp3a_fixed_contract_is_enforced_by_verifier(tmp_path: Path):
    manifest = _make_package(tmp_path)
    config_path = manifest.parent / "data" / "config.json"
    task_path = manifest.parent / "data" / "task_variant_attestation.json"
    _tamper_json(
        config_path,
        lambda p: p["seed_ranges"].update(
            {"calibration": [41001, 41030], "spent_no_reuse": []}
        ),
    )
    _tamper_json(task_path, lambda p: p.update({"source_variable_opened": True}))

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert any("mvp3a_fixed_contract" in failure for failure in report.failures())


def test_missing_train_seed_range_fails_cleanly(tmp_path: Path):
    manifest = _make_package(tmp_path)
    config_path = manifest.parent / "data" / "config.json"
    _tamper_json(config_path, lambda p: p["seed_ranges"].pop("train"))

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert any("seed_contract" in failure for failure in report.failures())


def test_addendum_present_with_nonclosing_rollouts_fails(tmp_path: Path):
    manifest = _make_package(tmp_path, positive=False)
    summary_path = manifest.parent / "data" / "learning_result_summary.json"
    _tamper_json(summary_path, lambda p: p.update({"learning_proven_addendum": "present"}))

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert any("learning_result_consistency" in failure for failure in report.failures())


def test_learning_proven_addendum_artifact_tamper_fails(tmp_path: Path):
    manifest = _make_package(
        tmp_path,
        positive=True,
        evidence_kind="actual_isaac",
        include_actual_provenance=True,
    )
    addendum = (
        manifest.parent
        / "addenda"
        / "learning_proven"
        / "learning_proven_report.json"
    )
    _tamper_json(addendum, lambda p: p.update({"heldout_uplift": 0.99}))

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert any("learning_addendum_artifact" in failure for failure in report.failures())


def test_c_lite_masks_recompute_successes_when_present(tmp_path: Path):
    manifest = _make_package(tmp_path, positive=True)
    pkg = manifest.parent
    _write_json(
        pkg / "data" / "masks" / "heldout_baseline_success_masks.json",
        _mask_doc(range(42000, 42050), 5),
    )
    _rehash_manifest_data_file(manifest, "data/masks/heldout_baseline_success_masks.json")
    _write_json(
        pkg / "data" / "masks" / "heldout_candidate_success_masks.json",
        _mask_doc(range(42000, 42050), 40),
    )
    _rehash_manifest_data_file(manifest, "data/masks/heldout_candidate_success_masks.json")

    report = _load_verifier().verify_package(manifest)

    assert report.ok is True, report.failures()
    assert report.recomputed["c_lite"]["checked"] == 100


def test_c_lite_mask_contradiction_fails(tmp_path: Path):
    manifest = _make_package(tmp_path, positive=True)
    pkg = manifest.parent
    _write_json(
        pkg / "data" / "masks" / "heldout_baseline_success_masks.json",
        _mask_doc(range(42000, 42050), 5),
    )
    _rehash_manifest_data_file(manifest, "data/masks/heldout_baseline_success_masks.json")
    _write_json(
        pkg / "data" / "masks" / "heldout_candidate_success_masks.json",
        _mask_doc(range(42000, 42050), 39),
    )
    _rehash_manifest_data_file(manifest, "data/masks/heldout_candidate_success_masks.json")

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert any("c_lite_mask_consistency" in failure for failure in report.failures())


def test_c_lite_per_rollout_mask_mismatch_fails_even_when_success_count_matches(
    tmp_path: Path,
):
    manifest = _make_package(tmp_path, positive=True)
    pkg = manifest.parent
    _write_json(
        pkg / "data" / "masks" / "heldout_baseline_success_masks.json",
        _mask_doc(range(42000, 42050), 5),
    )
    _rehash_manifest_data_file(manifest, "data/masks/heldout_baseline_success_masks.json")
    candidate_masks = _mask_doc(range(42000, 42050), 40)
    candidate_masks["masks"][0]["env_native_success_mask"] = [False, True, False]
    candidate_masks["masks"][40]["env_native_success_mask"] = [
        False,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
        True,
    ]
    _write_json(pkg / "data" / "masks" / "heldout_candidate_success_masks.json", candidate_masks)
    _rehash_manifest_data_file(manifest, "data/masks/heldout_candidate_success_masks.json")

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert any("c_lite_mask_consistency" in failure for failure in report.failures())


def test_unindexed_data_file_fails_manifest_coverage(tmp_path: Path):
    manifest = _make_package(tmp_path, positive=True)
    _write_json(
        manifest.parent / "data" / "masks" / "heldout_baseline_success_masks.json",
        _mask_doc(range(42000, 42050), 5),
    )

    report = _load_verifier().verify_package(manifest)

    assert report.ok is False
    assert any("manifest_data_coverage" in failure for failure in report.failures())
