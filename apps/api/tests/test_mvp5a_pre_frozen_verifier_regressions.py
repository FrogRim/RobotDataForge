from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[3]


FROZEN_VERIFIER_CASES = (
    (
        "mvp2",
        "scripts/verify_mvp2_package.py",
        "docs/proof/mvp2_learning_proven_evidence_package/package_manifest.json",
    ),
    (
        "mvp3a",
        "scripts/verify_proof_package.py",
        "docs/proof/mvp3a_target_fixture_pose_variant_proof_package/package_manifest.json",
    ),
    (
        "mvp3b",
        "scripts/verify_mvp3b_source_adapter_package.py",
        "docs/proof/mvp3b_source_adapter_matrix_proof_package/package_manifest.json",
    ),
    (
        "mvp3c",
        "scripts/verify_mvp3c_isaac_sim_embodiment_source_package.py",
        "docs/proof/mvp3c_isaac_sim_embodiment_source_proof_package/package_manifest.json",
    ),
    (
        "external_ingest_contract",
        "scripts/verify_external_robot_data_ingest_package.py",
        "docs/proof/external_robot_data_ingest_eval_v0_proof_package/package_manifest.json",
    ),
    (
        "lerobot_public_slice",
        "scripts/verify_lerobot_public_slice_package.py",
        "docs/proof/lerobot_public_aloha_slice_semantic_parity_proof_package/package_manifest.json",
    ),
    (
        "lerobot_public_matrix",
        "scripts/verify_lerobot_public_dataset_matrix_package.py",
        "docs/proof/lerobot_public_dataset_matrix_semantic_parity_proof_package/package_manifest.json",
    ),
    (
        "rdf_trustpack_v0",
        "scripts/verify_lerobot_public_dataset_matrix_package.py",
        "docs/proof/rdf_public_dataset_trustpack_v0_lerobot_matrix_package/package_manifest.json",
    ),
    (
        "mvp5a_pre_contract_ready",
        "scripts/verify_mvp5a_pre_file_drop_chaos_rehearsal_package.py",
        "docs/proof/mvp5a_pre_digital_twin_file_drop_chaos_rehearsal_package/package_manifest.json",
        "--allow-contract-ready",
        "--deep-hdf5",
    ),
)


@pytest.mark.parametrize("case", FROZEN_VERIFIER_CASES, ids=lambda item: item[0])
def test_frozen_and_current_verifier_packages_still_verify(case: tuple[str, ...]) -> None:
    _name, script, manifest, *extra_args = case
    result = subprocess.run(
        [sys.executable, str(ROOT / script), str(ROOT / manifest), *extra_args],
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "VERDICT: VERIFIED" in result.stdout
