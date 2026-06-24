"""RDF Public Dataset TrustPack v0 package materialization helpers."""

from __future__ import annotations

from pathlib import Path
import html
import shutil
import tempfile
from typing import Any

from app.services.lerobot_public_slice import (
    LEROBOT_MATRIX_PROFILE_REGISTRY,
    LeRobotPublicSliceProfile,
    artifact_entry,
    build_non_claims,
    sha256_file,
    write_json,
)


ROOT = Path(__file__).resolve().parents[4]
MANAGED_PROOF_ROOT = ROOT / "docs" / "proof"
BASELINE_MATRIX_PACKAGE_DIR = MANAGED_PROOF_ROOT / "lerobot_public_dataset_matrix_semantic_parity_proof_package"
DEFAULT_TRUSTPACK_PACKAGE_DIR = MANAGED_PROOF_ROOT / "rdf_public_dataset_trustpack_v0_lerobot_matrix_package"
TRUSTPACK_PACKAGE_PREFIX = "rdf_public_dataset_trustpack_v0_lerobot_matrix_package"
PROFILE_REGISTRY_SCHEMA_VERSION = "rdf_public_dataset_profile_registry_v0.1.0"
TRUSTPACK_SOURCE_KIND = "public_dataset_trustpack_materialized_lerobot_matrix_v0"


def build_trustpack_package(
    *,
    package_dir: Path = DEFAULT_TRUSTPACK_PACKAGE_DIR,
    baseline_package_dir: Path = BASELINE_MATRIX_PACKAGE_DIR,
    clean: bool = False,
) -> dict[str, Any]:
    """Materialize the already-closed LeRobot matrix package as a TrustPack."""

    baseline_package_dir = baseline_package_dir.resolve()
    package_dir = package_dir.resolve()
    _validate_baseline_package(baseline_package_dir)
    prepare_package_dir(package_dir, clean=clean)

    shutil.copytree(baseline_package_dir, package_dir)

    data_dir = package_dir / "data"
    profile_summaries = [_profile_summary(data_dir / "profiles" / profile.profile_id, profile) for profile in LEROBOT_MATRIX_PROFILE_REGISTRY]
    non_claims = build_non_claims()
    write_json(data_dir / "profile_registry.json", build_profile_registry(profile_summaries=profile_summaries))
    write_buyer_report(package_dir, profile_summaries=profile_summaries)
    write_readme(package_dir, profile_summaries=profile_summaries)
    refresh_trustpack_matrix_indexes(package_dir, profile_summaries=profile_summaries, non_claims=non_claims)

    return {
        "package_dir": str(package_dir),
        "package_manifest": str(package_dir / "package_manifest.json"),
        "baseline_package_dir": str(baseline_package_dir),
        "profile_registry": str(data_dir / "profile_registry.json"),
        "buyer_report": str(package_dir / "buyer_report.html"),
        "canonical_buyer_report": str(data_dir / "reports" / "buyer_report.html"),
        "profiles": profile_summaries,
    }


def build_profile_registry(*, profile_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    profile_summary_by_id = {summary["profile_id"]: summary for summary in profile_summaries}
    profiles = []
    for profile in LEROBOT_MATRIX_PROFILE_REGISTRY:
        summary = profile_summary_by_id[profile.profile_id]
        profiles.append(
            {
                "profile_id": profile.profile_id,
                "repo_id": profile.repo_id,
                "resolved_revision": profile.resolved_revision,
                "source_file": profile.source_file,
                "robot_type": profile.robot_type,
                "license": profile.license,
                "slice_rule": {
                    "slice_rule": profile.slice_rule["slice_rule"],
                    "episode_index": profile.episode_index,
                    "frame_start": profile.frame_start,
                    "frame_count": profile.frame_count,
                },
                "observation_state_dim": profile.observation_state_dim,
                "action_dim": profile.action_dim,
                "row_count": summary["row_count"],
                "trainer_smoke_passed": summary["trainer_smoke_passed"],
                "projection_contract": "rdf_public_lerobot_state_action_row_v0.1.0",
                "materialization_source": "already_closed_matrix_package",
                "full_lerobot_parser_claimed": False,
                "full_dataset_evaluation_claimed": False,
            }
        )
    return {
        "schema_version": PROFILE_REGISTRY_SCHEMA_VERSION,
        "package_status": "external_data_evaluated",
        "source_kind": TRUSTPACK_SOURCE_KIND,
        "required_profiles": [profile.profile_id for profile in LEROBOT_MATRIX_PROFILE_REGISTRY],
        "profile_count": len(profiles),
        "profiles": profiles,
        "new_profile_added": False,
        "upstream_rederivation_claimed": False,
    }


def refresh_trustpack_matrix_indexes(
    package_root: Path,
    *,
    profile_summaries: list[dict[str, Any]],
    non_claims: dict[str, bool],
) -> None:
    data_root = package_root / "data"
    artifact_entries = [
        artifact_entry(package_root, path)
        for path in sorted(data_root.rglob("*"))
        if path.is_file() and path.name != "artifact_index.json"
    ]
    write_json(
        data_root / "artifact_index.json",
        {
            "schema_version": "rdf_lerobot_public_dataset_matrix_artifact_index_v0.1.0",
            "artifact_index": artifact_entries,
        },
    )
    manifest_entries = [
        artifact_entry(package_root, path)
        for path in sorted(data_root.rglob("*"))
        if path.is_file()
    ]
    write_json(
        package_root / "package_manifest.json",
        {
            "schema_version": "rdf_lerobot_public_dataset_matrix_package_manifest_v0.1.0",
            "package_status": "external_data_evaluated",
            "source_kind": "public_lerobot_dataset_matrix_audited_slices",
            "trustpack_source_kind": TRUSTPACK_SOURCE_KIND,
            "external_source_included": True,
            "provenance_trust_tier": "refetchable_public_source",
            "required_profiles": [profile.profile_id for profile in LEROBOT_MATRIX_PROFILE_REGISTRY],
            "profile_summaries": profile_summaries,
            "audited_slice_verdict_claimed": True,
            "full_source_verdict_claimed": False,
            "full_lerobot_parser_claimed": False,
            "non_claims": non_claims,
            "artifact_index": manifest_entries,
        },
    )


def write_buyer_report(package_dir: Path, *, profile_summaries: list[dict[str, Any]]) -> None:
    data_report = package_dir / "data" / "reports" / "buyer_report.html"
    top_level_report = package_dir / "buyer_report.html"
    profile_rows = "\n".join(
        "<tr>"
        f"<td>{_escape(summary['profile_id'])}</td>"
        f"<td>{_escape(summary['repo_id'])}</td>"
        f"<td><code>{_escape(summary['resolved_revision'])}</code></td>"
        f"<td>{_escape(summary['robot_type'])}</td>"
        f"<td>{summary['observation_state_dim']} x {summary['action_dim']}</td>"
        f"<td>{summary['row_count']}</td>"
        f"<td>{'PASS' if summary['trainer_smoke_passed'] else 'FAIL'}</td>"
        "</tr>"
        for summary in profile_summaries
    )
    report = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>RDF Public Dataset TrustPack v0</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; color: #17202a; line-height: 1.45; }}
    code {{ background: #eef2f4; padding: 0.1rem 0.25rem; border-radius: 3px; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th, td {{ border: 1px solid #c9d3dc; padding: 0.45rem; text-align: left; vertical-align: top; }}
    th {{ background: #edf4f7; }}
    .boundary {{ border-left: 4px solid #2364aa; padding-left: 1rem; }}
    .nonclaims {{ border-left: 4px solid #8a4b08; padding-left: 1rem; }}
  </style>
</head>
<body>
  <h1>RDF Public Dataset TrustPack v0</h1>
  <p class="boundary">
    This report is a buyer-readable surface for the already-closed ALOHA + SO-100
    public dataset matrix materialization. The proof source of truth is the
    verifier-backed package evidence, not this HTML report.
  </p>
  <h2>Source Profiles</h2>
  <table>
    <thead>
      <tr>
        <th>profile_id</th>
        <th>repo_id</th>
        <th>pinned revision</th>
        <th>robot_type</th>
        <th>state/action dims</th>
        <th>rows</th>
        <th>trainer smoke</th>
      </tr>
    </thead>
    <tbody>
{profile_rows}
    </tbody>
  </table>
  <h2>Verification</h2>
  <p>
    Run:
    <code>python3 scripts/verify_lerobot_public_dataset_matrix_package.py docs/proof/rdf_public_dataset_trustpack_v0_lerobot_matrix_package/package_manifest.json</code>
  </p>
  <p>
    Additional TrustPack gates scan this HTML for unnegated claim drift and compare
    baseline-vs-generated evidence digests.
  </p>
  <h2>Claim Boundary</h2>
  <p>
    RDF materializes the already-closed ALOHA + SO-100 audited slice matrix into
    a self-contained TrustPack surface. It does not rederive upstream data in this
    product claim and it does not add a new dataset profile.
  </p>
  <div class="nonclaims">
    <p>No generic LeRobot parser support.</p>
    <p>No full LeRobot parser support.</p>
    <p>No full dataset evaluation.</p>
    <p>No real robot success.</p>
    <p>No physical robot readiness.</p>
    <p>No live hardware support.</p>
    <p>No live ALOHA support.</p>
    <p>No live UR RTDE support.</p>
    <p>No live Franka hardware support.</p>
    <p>No live ROS2 DDS bridge readiness.</p>
    <p>No visual policy performance.</p>
    <p>No policy uplift.</p>
    <p>No learning-proven value.</p>
    <p>No deployable policy readiness.</p>
    <p>No marketplace readiness.</p>
    <p>No production certification.</p>
    <p>No sim-to-real proof.</p>
    <p>No general robot intelligence.</p>
  </div>
</body>
</html>
"""
    data_report.parent.mkdir(parents=True, exist_ok=True)
    data_report.write_text(report, encoding="utf-8")
    top_level_report.write_text(report, encoding="utf-8")


def write_trustpack_artifact_index(package_dir: Path) -> Path:
    buyer_report = package_dir / "buyer_report.html"
    if not buyer_report.is_file():
        raise FileNotFoundError(f"missing top-level buyer report: {buyer_report}")
    readme = package_dir / "README.md"
    if not readme.is_file():
        raise FileNotFoundError(f"missing package README: {readme}")
    index_path = package_dir / "data" / "trustpack_artifact_index.json"
    write_json(
        index_path,
        {
            "schema_version": "rdf_public_dataset_trustpack_artifact_index_v0.1.0",
            "artifact_index": [
                {
                    "path": "README.md",
                    "file_sha256": sha256_file(readme),
                    "byte_size": readme.stat().st_size,
                    "hash_convention": "file_bytes",
                    "matrix_artifact_index_entry": False,
                    "role": "reviewer_entrypoint",
                },
                {
                    "path": "buyer_report.html",
                    "file_sha256": sha256_file(buyer_report),
                    "byte_size": buyer_report.stat().st_size,
                    "hash_convention": "file_bytes",
                    "matrix_artifact_index_entry": False,
                    "role": "reviewer_convenience_copy",
                }
            ],
            "top_level_convenience_copy_count": 1,
            "reviewer_entrypoint_count": 1,
        },
    )
    return index_path


def write_readme(package_dir: Path, *, profile_summaries: list[dict[str, Any]]) -> None:
    profiles = "\n".join(
        f"- `{summary['profile_id']}`: `{summary['repo_id']}` "
        f"robot_type=`{summary['robot_type']}`, dims={summary['observation_state_dim']}x{summary['action_dim']}, "
        f"rows={summary['row_count']}"
        for summary in profile_summaries
    )
    readme = f"""# RDF Public Dataset TrustPack v0

This package supports one narrow productization claim: Robot Data Forge can
materialize the already-closed ALOHA + SO-100 public LeRobot dataset matrix
discipline into a self-contained TrustPack surface with a buyer-readable report,
existing matrix verifier compatibility, HTML claim scanning, and independent
baseline-vs-generated regeneration comparison.

Profiles:

{profiles}

The proof source of truth is the verifier-backed package evidence, not the
top-level HTML report or this README. This package does not add a new public
dataset profile and does not rederive upstream public data as a new proof claim.

Required verification gates:

```bash
python3 scripts/verify_lerobot_public_dataset_matrix_package.py \\
  docs/proof/rdf_public_dataset_trustpack_v0_lerobot_matrix_package/package_manifest.json

python3 scripts/scan_rdf_trustpack_html_claims.py \\
  --package-dir docs/proof/rdf_public_dataset_trustpack_v0_lerobot_matrix_package

python3 scripts/compare_rdf_public_dataset_trustpack_regeneration.py \\
  --baseline-package-dir docs/proof/lerobot_public_dataset_matrix_semantic_parity_proof_package \\
  --generated-package-dir docs/proof/rdf_public_dataset_trustpack_v0_lerobot_matrix_package
```

Non-claims:

- No generic LeRobot parser support.
- No full LeRobot parser support.
- No full dataset evaluation.
- No real robot success.
- No physical robot readiness.
- No live hardware support.
- No live ALOHA support.
- No live UR RTDE support.
- No live Franka hardware support.
- No live ROS2 DDS bridge readiness.
- No visual policy performance.
- No policy uplift.
- No learning-proven value.
- No deployable policy readiness.
- No marketplace readiness.
- No production certification.
- No sim-to-real proof.
- No general robot intelligence.
"""
    (package_dir / "README.md").write_text(readme, encoding="utf-8")


def prepare_package_dir(package_dir: Path, *, clean: bool) -> None:
    if not package_dir.exists():
        return
    if not clean:
        raise ValueError(f"{package_dir} exists; pass --clean to rebuild")
    assert_safe_clean_target(package_dir)
    shutil.rmtree(package_dir)


def assert_safe_clean_target(package_dir: Path) -> None:
    resolved = package_dir.resolve()
    dangerous = {
        Path("/").resolve(),
        ROOT.resolve(),
        ROOT.parent.resolve(),
        Path.home().resolve(),
        Path(tempfile.gettempdir()).resolve(),
        MANAGED_PROOF_ROOT.resolve(),
    }
    if resolved in dangerous:
        raise ValueError(f"refusing to clean unsafe package_dir: {package_dir}")
    managed_root = MANAGED_PROOF_ROOT.resolve()
    tmp_root = Path(tempfile.gettempdir()).resolve()
    if resolved.is_relative_to(managed_root):
        if resolved.name != TRUSTPACK_PACKAGE_PREFIX:
            raise ValueError(f"refusing to clean unsafe package_dir: {package_dir}")
        return
    if resolved.is_relative_to(tmp_root):
        if not resolved.name.startswith(TRUSTPACK_PACKAGE_PREFIX):
            raise ValueError(f"refusing to clean unsafe package_dir: {package_dir}")
        return
    raise ValueError(f"refusing to clean unsafe package_dir: {package_dir}")


def _validate_baseline_package(package_dir: Path) -> None:
    required = (
        "package_manifest.json",
        "data/config.json",
        "data/profile_resolver_report.json",
        "data/matrix_summary.json",
        "data/non_claims_attestation.json",
    )
    missing = [relative for relative in required if not (package_dir / relative).is_file()]
    if missing:
        raise FileNotFoundError(f"baseline matrix package missing required files: {missing}")


def _profile_summary(profile_dir: Path, profile: LeRobotPublicSliceProfile) -> dict[str, Any]:
    validator = _read_json(profile_dir / "contracts" / "validator_report.json")
    trainer = _read_json(profile_dir / "export" / "trainer_smoke_report.json")
    binding = _read_json(profile_dir / "source" / "public_source_binding.json")
    return {
        "profile_id": profile.profile_id,
        "repo_id": binding["repo_id"],
        "resolved_revision": binding["resolved_revision"],
        "source_file": binding["source_file"],
        "robot_type": binding["dataset_card_robot_type"],
        "license": binding["license"],
        "row_count": validator["row_count"],
        "observation_state_dim": validator["observation_state_dim"],
        "action_dim": validator["action_dim"],
        "trainer_smoke_passed": trainer["passed"],
    }


def _read_json(path: Path) -> dict[str, Any]:
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: JSON root must be object")
    return payload


def _escape(value: Any) -> str:
    return html.escape(str(value), quote=True)
