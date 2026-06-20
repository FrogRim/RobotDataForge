from __future__ import annotations

import ast
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SPINE_DIR = REPO_ROOT / "apps" / "api" / "app" / "services" / "proof"
SPINE_FILES = [
    SPINE_DIR / "__init__.py",
    SPINE_DIR / "closure.py",
    SPINE_DIR / "contracts.py",
    SPINE_DIR / "leakage_guard.py",
    SPINE_DIR / "seed_discipline.py",
]

FORBIDDEN_INJECTED_VALUES = [
    "isaac_runtime",
    "dedicated_isaac_connector_insertion_evaluator",
    "isaac_runtime_scripted_expert_rollout",
]

FROZEN_PATHS = [
    "scripts/run_mvp2c_isaac_training_calibration.py",
    "scripts/run_mvp2b_isaac_proof_evaluator.py",
    "scripts/verify_mvp2_package.py",
    "docs/proof/mvp2_learning_proven_evidence_package/package_manifest.json",
    "docs/proof/mvp2_learning_proven_evidence_package/data",
]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.add(node.module)
    return imported


def test_spine_does_not_import_independent_verifier():
    imported = {module for path in SPINE_FILES for module in _imports(path)}

    assert "scripts.verify_mvp2_package" not in imported
    assert "verify_mvp2_package" not in imported


def test_spine_implementation_does_not_hardcode_injected_runtime_values():
    implementation_text = "\n".join(path.read_text() for path in SPINE_FILES)

    for forbidden in FORBIDDEN_INJECTED_VALUES:
        assert forbidden not in implementation_text


def test_archive_verifier_and_frozen_proof_package_are_untouched():
    result = subprocess.run(
        ["git", "diff", "--quiet", "--", *FROZEN_PATHS],
        cwd=REPO_ROOT,
        check=False,
    )

    assert result.returncode == 0
