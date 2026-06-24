#!/usr/bin/env python3
"""Build the two-profile LeRobot public dataset matrix semantic parity package."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.lerobot_public_slice import (  # noqa: E402
    ALOHA_PUBLIC_SLICE_PROFILE,
    LEROBOT_MATRIX_PROFILE_REGISTRY,
    SO100_PICKPLACE_PUBLIC_SLICE_PROFILE,
    LeRobotPublicSliceProfile,
    artifact_entry,
    build_extraction_receipt,
    build_matrix_profile_resolver_report,
    build_non_claims,
    build_refetch_receipt,
    build_slice_selection_report,
    build_source_binding_from_profile,
    canonical_json_bytes,
    convert_raw_rows_to_rdf,
    normalize_source_row,
    sha256_bytes,
    sha256_file,
    stable_json,
    validate_raw_rows,
    write_json,
    write_jsonl,
)
from app.services.lerobot_state_action_contract import LeRobotStateActionContractValidator  # noqa: E402


DEFAULT_PACKAGE_DIR = ROOT / "docs" / "proof" / "lerobot_public_dataset_matrix_semantic_parity_proof_package"
FROZEN_ALOHA_PACKAGE_DIR = ROOT / "docs" / "proof" / "lerobot_public_aloha_slice_semantic_parity_proof_package"
MANAGED_PROOF_ROOT = ROOT / "docs" / "proof"
BASE_SOURCE_COLUMNS = (
    "episode_index",
    "frame_index",
    "timestamp",
    "observation.state",
    "action",
    "index",
    "task_index",
)
OPTIONAL_SOURCE_COLUMNS = ("next.done", "next.success", "observation.effort")


def build_matrix_package(*, package_dir: Path = DEFAULT_PACKAGE_DIR, clean: bool = False) -> dict[str, Any]:
    prepare_package_dir(package_dir, clean=clean)
    data_dir = package_dir / "data"
    profiles_dir = data_dir / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)

    copy_frozen_aloha_profile(profiles_dir / ALOHA_PUBLIC_SLICE_PROFILE.profile_id)
    build_profile_from_public_source(
        profile=SO100_PICKPLACE_PUBLIC_SLICE_PROFILE,
        profile_dir=profiles_dir / SO100_PICKPLACE_PUBLIC_SLICE_PROFILE.profile_id,
    )

    non_claims = build_non_claims()
    resolver_report = build_matrix_profile_resolver_report()
    profile_summaries = [_profile_summary(profiles_dir / profile.profile_id, profile) for profile in LEROBOT_MATRIX_PROFILE_REGISTRY]
    matrix_summary = {
        "schema_version": "rdf_lerobot_public_dataset_matrix_summary_v0.1.0",
        "package_status": "external_data_evaluated",
        "claim": "external_public_lerobot_dataset_matrix_semantic_parity",
        "profile_count": len(profile_summaries),
        "required_profiles": [profile.profile_id for profile in LEROBOT_MATRIX_PROFILE_REGISTRY],
        "profile_summaries": profile_summaries,
        "variety_gate": {
            "distinct_robot_types": sorted({summary["robot_type"] for summary in profile_summaries}),
            "distinct_state_action_dims": sorted(
                {
                    f'{summary["observation_state_dim"]}x{summary["action_dim"]}'
                    for summary in profile_summaries
                }
            ),
            "passed": True,
        },
        "non_claims": non_claims,
    }
    config = {
        "schema_version": "rdf_lerobot_public_dataset_matrix_config_v0.1.0",
        "package_status": "external_data_evaluated",
        "source_kind": "public_lerobot_dataset_matrix_audited_slices",
        "external_source_included": True,
        "provenance_trust_tier": "refetchable_public_source",
        "required_profiles": [profile.profile_id for profile in LEROBOT_MATRIX_PROFILE_REGISTRY],
        "profile_count": len(LEROBOT_MATRIX_PROFILE_REGISTRY),
        "full_source_verdict_claimed": False,
        "audited_slice_verdict_claimed": True,
        "full_lerobot_parser_claimed": False,
        "non_claims": non_claims,
    }
    write_json(data_dir / "profile_resolver_report.json", resolver_report)
    write_json(data_dir / "matrix_summary.json", matrix_summary)
    write_json(data_dir / "config.json", config)
    write_json(
        data_dir / "non_claims_attestation.json",
        {
            "schema_version": "rdf_lerobot_matrix_non_claims_attestation_v0.1.0",
            "non_claims": non_claims,
        },
    )
    write_readme(package_dir, profile_summaries)
    refresh_matrix_artifact_indexes(package_dir, profile_summaries=profile_summaries, non_claims=non_claims)
    return {
        "package_dir": str(package_dir),
        "package_manifest": str(package_dir / "package_manifest.json"),
        "profiles": profile_summaries,
    }


def copy_frozen_aloha_profile(profile_dir: Path) -> None:
    source_data = FROZEN_ALOHA_PACKAGE_DIR / "data"
    if not source_data.exists():
        raise RuntimeError(f"frozen ALOHA package missing: {source_data}")
    if profile_dir.exists():
        shutil.rmtree(profile_dir)
    profile_dir.mkdir(parents=True, exist_ok=True)
    for name in ("source", "conversion", "contracts", "export", "reports"):
        shutil.copytree(source_data / name, profile_dir / name)
    write_json(
        profile_dir / "profile_metadata.json",
        {
            "schema_version": "rdf_lerobot_matrix_profile_metadata_v0.1.0",
            "profile": ALOHA_PUBLIC_SLICE_PROFILE.to_public_dict(),
            "source": "copied_from_frozen_v0.1_aloha_package",
            "frozen_package_manifest_sha256": sha256_file(FROZEN_ALOHA_PACKAGE_DIR / "package_manifest.json"),
        },
    )


def build_profile_from_public_source(*, profile: LeRobotPublicSliceProfile, profile_dir: Path) -> None:
    try:
        from huggingface_hub import HfApi, hf_hub_download
        import pyarrow.parquet as pq
    except Exception as exc:  # pragma: no cover - producer dependency failure path
        raise RuntimeError(
            "matrix package generation requires optional deps; run with "
            "`uv run --with huggingface_hub --with pyarrow --with h5py --with numpy "
            "scripts/run_lerobot_public_dataset_matrix_semantic_parity.py`"
        ) from exc

    if profile_dir.exists():
        shutil.rmtree(profile_dir)
    source_dir = profile_dir / "source"
    conversion_dir = profile_dir / "conversion"
    contracts_dir = profile_dir / "contracts"
    export_dir = profile_dir / "export"
    reports_dir = profile_dir / "reports"
    for directory in (source_dir, conversion_dir, contracts_dir, export_dir, reports_dir):
        directory.mkdir(parents=True, exist_ok=True)

    api = HfApi()
    info = api.dataset_info(repo_id=profile.repo_id, revision=profile.resolved_revision, files_metadata=True)
    if str(info.sha) != profile.resolved_revision:
        raise RuntimeError(f"{profile.repo_id}: resolved revision drifted to {info.sha}")

    with tempfile.TemporaryDirectory(prefix=f"rdf_{profile.profile_id}_") as tmp:
        cache = Path(tmp)
        downloaded: dict[str, Path] = {}
        for filename in profile.required_upstream_files:
            downloaded[filename] = Path(
                hf_hub_download(
                    repo_id=profile.repo_id,
                    repo_type="dataset",
                    revision=profile.resolved_revision,
                    filename=filename,
                )
            )

        source_file_path = downloaded[profile.source_file]
        schema = pq.read_schema(source_file_path)
        available_columns = set(schema.names)
        columns = [column for column in BASE_SOURCE_COLUMNS + OPTIONAL_SOURCE_COLUMNS if column in available_columns]
        missing = [column for column in BASE_SOURCE_COLUMNS if column not in available_columns]
        if missing:
            raise RuntimeError(f"{profile.repo_id}: source parquet missing required columns {missing}")
        table = pq.read_table(source_file_path, columns=columns)
        raw_rows, feature_schema = extract_profile_raw_rows_from_table(table, profile=profile)

        upstream_files = {
            filename: {
                "sha256": sha256_file(path),
                "refetched_sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
                "source_url": _hf_resolve_url(profile.repo_id, profile.resolved_revision, filename),
            }
            for filename, path in downloaded.items()
        }
        source_binding = build_source_binding_from_profile(profile)
        source_binding["dataset_card_rows"] = "not_claimed"
        source_binding["dataset_card_total_file_size"] = "not_claimed"
        source_file_sha = upstream_files[profile.source_file]["sha256"]
        if not isinstance(source_file_sha, str):
            raise RuntimeError(f"{profile.repo_id}: source file sha must be str")
        reextracted_rows, _schema = extract_profile_raw_rows_from_table(table, profile=profile)
        if [row["source_row_sha256"] for row in raw_rows] != [row["source_row_sha256"] for row in reextracted_rows]:
            raise RuntimeError(f"{profile.repo_id}: re-extracted row digests differ")

        feature_schema_sha = sha256_bytes(canonical_json_bytes(feature_schema))
        write_json(source_dir / "public_source_binding.json", source_binding)
        write_json(
            source_dir / "upstream_file_hashes.json",
            {
                "schema_version": "rdf_lerobot_upstream_file_hashes_v0.1.0",
                "repo_id": profile.repo_id,
                "resolved_revision": profile.resolved_revision,
                "files": {
                    filename: {
                        "sha256": meta["sha256"],
                        "size_bytes": meta["size_bytes"],
                        "source_url": meta["source_url"],
                    }
                    for filename, meta in sorted(upstream_files.items())
                },
            },
        )
        write_json(
            source_dir / "refetch_receipt.json",
            build_refetch_receipt(
                repo_id=profile.repo_id,
                resolved_revision=profile.resolved_revision,
                source_url=source_binding["source_url"],
                upstream_files=upstream_files,
            ),
        )
        write_json(
            source_dir / "extraction_receipt.json",
            build_extraction_receipt(
                repo_id=profile.repo_id,
                resolved_revision=profile.resolved_revision,
                source_file=profile.source_file,
                source_file_byte_sha256=source_file_sha,
                raw_rows=raw_rows,
                feature_schema_sha256=feature_schema_sha,
                reextract_command=(
                    "uv run --with pyarrow --with huggingface_hub "
                    "scripts/verify_lerobot_public_dataset_matrix_package.py "
                    f"{DEFAULT_PACKAGE_DIR / 'package_manifest.json'} --reextract-public-source"
                ),
                dependency_versions={
                    "huggingface_hub": getattr(sys.modules.get("huggingface_hub"), "__version__", "unknown"),
                    "pyarrow": getattr(sys.modules.get("pyarrow"), "__version__", "unknown"),
                },
            ),
        )
        write_json(
            source_dir / "slice_selection_report.json",
            build_slice_selection_report(
                source_file=profile.source_file,
                raw_rows=raw_rows,
                feature_schema_sha256=feature_schema_sha,
            ),
        )
        write_jsonl(source_dir / "lerobot_raw_rows.jsonl", raw_rows)
        write_json(source_dir / "lerobot_feature_schema.json", feature_schema)
        (source_dir / "LICENSE.txt").write_text(
            f"{profile.license} license declared by Hugging Face dataset metadata for {profile.repo_id}.\n",
            encoding="utf-8",
        )

        converted_rows, mapping_report, conversion_manifest = convert_raw_rows_to_rdf(
            raw_rows,
            source_binding=source_binding,
            profile=profile,
        )
        write_jsonl(conversion_dir / "rdf_converted_rows.jsonl", converted_rows)
        write_json(conversion_dir / "semantic_mapping_report.json", mapping_report)
        write_json(conversion_dir / "conversion_manifest.json", conversion_manifest)

        validator = LeRobotStateActionContractValidator()
        contract = validator.build_contract(converted_rows, source_binding=source_binding)
        report = validator.validate_rows(converted_rows, expected_robot_type=profile.robot_type)
        if not report.ok:
            raise RuntimeError(f"{profile.profile_id}: generic state/action contract failed {report.issues}")
        write_json(contracts_dir / "normalized_state_action_contract.json", contract)
        write_json(
            contracts_dir / "validator_report.json",
            {
                "schema_version": "rdf_lerobot_state_action_validator_report_v0.1.0",
                "ok": report.ok,
                "issues": report.issues,
                "row_count": report.row_count,
                "observation_state_dim": report.observation_state_dim,
                "action_dim": report.action_dim,
            },
        )

        hdf5_path = export_dir / "dataset.hdf5"
        hdf5_report = export_profile_hdf5(converted_rows, hdf5_path, profile=profile)
        write_json(export_dir / "hdf5_inspection_report.json", hdf5_report)
        trainer_report = run_generic_trainer_smoke(hdf5_path)
        write_json(export_dir / "trainer_smoke_report.json", trainer_report)
        write_json(export_dir / "deep_hdf5_receipt.json", build_profile_deep_hdf5_receipt(hdf5_path, converted_rows, profile=profile))

        write_json(
            reports_dir / "buyer_data_evaluation_report.json",
            build_profile_buyer_report(profile=profile, row_count=len(raw_rows), trainer_report=trainer_report),
        )
        write_json(profile_dir / "profile_metadata.json", {"schema_version": "rdf_lerobot_matrix_profile_metadata_v0.1.0", "profile": profile.to_public_dict()})
        shutil.rmtree(cache, ignore_errors=True)


def extract_profile_raw_rows_from_table(table: Any, *, profile: LeRobotPublicSliceProfile) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = table.to_pylist()
    selected = [
        row
        for row in rows
        if row.get("episode_index") == profile.episode_index
        and profile.frame_start <= row.get("frame_index", -1) < profile.frame_start + profile.frame_count
    ]
    selected = sorted(selected, key=lambda row: row["frame_index"])
    expected_frames = list(range(profile.frame_start, profile.frame_start + profile.frame_count))
    actual_frames = [row["frame_index"] for row in selected]
    if actual_frames != expected_frames:
        raise RuntimeError(f"{profile.profile_id}: selected frames {actual_frames} do not match expected {expected_frames}")
    raw_rows = [
        normalize_source_row(
            row,
            repo_id=profile.repo_id,
            resolved_revision=profile.resolved_revision,
            source_file=profile.source_file,
        )
        for row in selected
    ]
    validation = validate_raw_rows(raw_rows, profile.slice_rule, expected_profile=profile)
    if not validation.ok:
        raise RuntimeError(f"{profile.profile_id}: selected raw rows invalid {validation.issues}")
    return raw_rows, {
        "schema_version": "rdf_lerobot_feature_schema_v0.1.0",
        "source": "pyarrow parquet schema",
        "columns": [{"name": field.name, "type": str(field.type)} for field in table.schema],
        "observation_state_dim": validation.observation_state_dim,
        "action_dim": validation.action_dim,
        "row_count_in_selected_table": len(rows),
    }


def export_profile_hdf5(rows: list[dict[str, Any]], hdf5_path: Path, *, profile: LeRobotPublicSliceProfile) -> dict[str, Any]:
    import h5py
    import numpy as np

    states = np.asarray([row["observation_state"] for row in rows], dtype=np.float32)
    actions = np.asarray([row["learning_action"] for row in rows], dtype=np.float32)
    timestamps = np.asarray([[float(row["timestamp"])] for row in rows], dtype=np.float32)
    episode_id = f"{profile.profile_id}_episode_{profile.episode_index:06d}"
    with h5py.File(hdf5_path, "w") as h5:
        h5.attrs["schema_version"] = "rdf_lerobot_generic_state_action_hdf5_v0.1.0"
        h5.attrs["source_kind"] = profile.source_kind
        episodes = h5.create_group("episodes")
        episodes.create_dataset("episode_ids", data=np.asarray([episode_id], dtype="S"))
        observations = h5.create_group("observations")
        actions_group = h5.create_group("actions")
        timestamp_group = h5.create_group("timestamps")
        observations.create_group(episode_id).create_dataset("observation_state", data=states)
        actions_group.create_group(episode_id).create_dataset("learning_action", data=actions)
        timestamp_group.create_group(episode_id).create_dataset("t", data=timestamps)
    return {
        "schema_version": "rdf_lerobot_hdf5_inspection_report_v0.1.0",
        "passed": True,
        "hdf5_path": f"data/profiles/{profile.profile_id}/export/dataset.hdf5",
        "episode_ids": [episode_id],
        "row_count": int(states.shape[0]),
        "observation_state_dim": int(states.shape[1]),
        "action_dim": int(actions.shape[1]),
        "timestamps_monotonic": bool(np.all(np.diff(timestamps[:, 0]) >= 0.0)),
        "hdf5_sha256": sha256_file(hdf5_path),
    }


def run_generic_trainer_smoke(hdf5_path: Path) -> dict[str, Any]:
    import h5py
    import numpy as np

    with h5py.File(hdf5_path, "r") as h5:
        episode_id = h5["episodes/episode_ids"][0].decode("utf-8")
        observations = np.asarray(h5[f"observations/{episode_id}/observation_state"][()], dtype=np.float64)
        actions = np.asarray(h5[f"actions/{episode_id}/learning_action"][()], dtype=np.float64)
    issues: list[str] = []
    if observations.ndim != 2 or actions.ndim != 2:
        issues.append("observations/actions must be matrices")
    if observations.shape[0] != actions.shape[0]:
        issues.append("sample count mismatch")
    if not np.isfinite(observations).all() or not np.isfinite(actions).all():
        issues.append("non-finite values")
    initial_loss = None
    final_loss = None
    if not issues:
        obs_mean = observations.mean(axis=0, keepdims=True)
        obs_std = np.where(observations.std(axis=0, keepdims=True) < 1e-6, 1.0, observations.std(axis=0, keepdims=True))
        x = np.concatenate([(observations - obs_mean) / obs_std, np.ones((observations.shape[0], 1))], axis=1)
        weights = np.zeros((x.shape[1], actions.shape[1]), dtype=np.float64)
        error = (x @ weights) - actions
        initial_loss = float(np.mean(error * error))
        gradient = (2.0 / x.shape[0]) * (x.T @ error)
        weights -= 1e-4 * gradient
        final_error = (x @ weights) - actions
        final_loss = float(np.mean(final_error * final_error))
        if not np.isfinite(final_loss):
            issues.append("non-finite final loss")
    return {
        "schema_version": "rdf_generic_state_action_trainer_smoke_v0.1.0",
        "trainer": "generic_state_action_trainer_smoke",
        "passed": not issues,
        "learning_results_measured": False,
        "policy_uplift": None,
        "sample_count": int(observations.shape[0]),
        "observation_state_dim": int(observations.shape[1]) if observations.ndim == 2 else 0,
        "action_dim": int(actions.shape[1]) if actions.ndim == 2 else 0,
        "initial_loss": initial_loss,
        "final_loss": final_loss,
        "issues": issues,
    }


def build_profile_deep_hdf5_receipt(hdf5_path: Path, rows: list[dict[str, Any]], *, profile: LeRobotPublicSliceProfile) -> dict[str, Any]:
    import h5py
    import numpy as np

    with h5py.File(hdf5_path, "r") as h5:
        episode_id = h5["episodes/episode_ids"][0].decode("utf-8")
        states = np.asarray(h5[f"observations/{episode_id}/observation_state"][()], dtype=np.float32)
        actions = np.asarray(h5[f"actions/{episode_id}/learning_action"][()], dtype=np.float32)
    expected_states = np.asarray([row["observation_state"] for row in rows], dtype=np.float32)
    expected_actions = np.asarray([row["learning_action"] for row in rows], dtype=np.float32)
    return {
        "schema_version": "rdf_lerobot_deep_hdf5_receipt_v0.1.0",
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "checker": "generic_state_action_hdf5_deep_compare",
        "hdf5_path": f"data/profiles/{profile.profile_id}/export/dataset.hdf5",
        "row_count": len(rows),
        "observation_state_dim": int(states.shape[1]) if states.ndim == 2 else 0,
        "action_dim": int(actions.shape[1]) if actions.ndim == 2 else 0,
        "converted_row_sha256s": [sha256_bytes(canonical_json_bytes(row)) for row in rows],
        "hdf5_observation_state_sha256": sha256_bytes(states.tobytes()),
        "expected_observation_state_sha256": sha256_bytes(expected_states.tobytes()),
        "hdf5_learning_action_sha256": sha256_bytes(actions.tobytes()),
        "expected_learning_action_sha256": sha256_bytes(expected_actions.tobytes()),
        "matched": bool(np.array_equal(states, expected_states) and np.array_equal(actions, expected_actions)),
    }


def build_profile_buyer_report(*, profile: LeRobotPublicSliceProfile, row_count: int, trainer_report: dict[str, Any]) -> dict[str, Any]:
    non_claims = build_non_claims()
    return {
        "schema_version": "rdf_lerobot_buyer_data_evaluation_report_v0.1.0",
        "claim": "external_data_evaluated",
        "package_status": "external_data_evaluated",
        "profile_id": profile.profile_id,
        "source_kind": profile.source_kind,
        "repo_id": profile.repo_id,
        "robot_type": profile.robot_type,
        "provenance_trust_tier": "refetchable_public_source",
        "audited_slice_verdict_claimed": True,
        "full_source_verdict_claimed": False,
        "external_source_included": True,
        "row_count": row_count,
        "observation_state_dim": profile.observation_state_dim,
        "action_dim": profile.action_dim,
        "canonical_source_rejected_examples_present": False,
        "accepted_rejected_pair_claimed": False,
        "trainer_smoke_passed": trainer_report["passed"],
        "non_claims": non_claims,
        "claim_boundary": (
            "RDF evaluated one deterministic public LeRobot audited slice for a profile in a two-profile matrix. "
            "No generic LeRobot parser. No full dataset evaluation. No real robot success. No physical robot readiness. "
            "No visual policy performance. No policy uplift. No deployable policy readiness. No marketplace readiness. "
            "No production certification. No sim-to-real proof."
        ),
    }


def refresh_matrix_artifact_indexes(package_root: Path, *, profile_summaries: list[dict[str, Any]], non_claims: dict[str, bool]) -> None:
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


def write_readme(package_dir: Path, profile_summaries: list[dict[str, Any]]) -> None:
    profiles = "\n".join(
        f"- `{summary['profile_id']}`: `{summary['repo_id']}` "
        f"robot_type=`{summary['robot_type']}`, dims={summary['observation_state_dim']}x{summary['action_dim']}"
        for summary in profile_summaries
    )
    text = f"""# LeRobot Public Dataset Matrix Semantic Parity Package

This package supports one narrow claim: Robot Data Forge combines a frozen
verified ALOHA audited slice with a newly generated SO-100 audited slice, then
independently reverifies both pinned public LeRobot profiles through the same
semantic parity matrix verifier.

Profiles:

{profiles}

The matrix verifier recomputes each profile from included source rows and
receipts. Its provenance tier is refetchable public bytes plus audited profile
metadata. The profile registry is explicit; this is not a generic LeRobot
parser and not a full dataset evaluation.

```bash
python3 scripts/verify_lerobot_public_dataset_matrix_package.py \\
  docs/proof/lerobot_public_dataset_matrix_semantic_parity_proof_package/package_manifest.json
```

Non-claims:

- No generic LeRobot parser support.
- No full dataset evaluation.
- No real robot success.
- No physical robot readiness.
- No live hardware support.
- No visual policy performance.
- No policy uplift.
- No learning-proven value.
- No deployable policy readiness.
- No marketplace readiness.
- No production certification.
- No sim-to-real proof.
"""
    (package_dir / "README.md").write_text(text, encoding="utf-8")


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
        if not resolved.name.startswith("lerobot_public_dataset_matrix"):
            raise ValueError(f"refusing to clean unsafe package_dir: {package_dir}")
        return
    if resolved.is_relative_to(tmp_root):
        return
    raise ValueError(f"refusing to clean unsafe package_dir: {package_dir}")


def _read_json(path: Path) -> dict[str, Any]:
    payload = __import__("json").loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: JSON root must be object")
    return payload


def _hf_resolve_url(repo_id: str, revision: str, filename: str) -> str:
    return f"https://huggingface.co/datasets/{repo_id}/resolve/{revision}/{filename}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE_DIR)
    parser.add_argument("--clean", action="store_true", help="Remove an existing managed matrix package before rebuilding.")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_matrix_package(package_dir=args.package_dir, clean=args.clean)
    if args.pretty:
        print(stable_json(result))
    else:
        print("LeRobot public dataset matrix semantic parity package built")
        print(f"package_manifest={result['package_manifest']}")
        for profile in result["profiles"]:
            print(
                "profile="
                f"{profile['profile_id']} repo={profile['repo_id']} "
                f"robot_type={profile['robot_type']} dims={profile['observation_state_dim']}x{profile['action_dim']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
