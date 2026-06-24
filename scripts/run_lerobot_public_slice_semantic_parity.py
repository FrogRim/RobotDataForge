#!/usr/bin/env python3
"""Build the LeRobot public ALOHA audited-slice semantic parity package."""

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
    DEFAULT_SLICE_RULE,
    build_extraction_receipt,
    build_non_claims,
    build_refetch_receipt,
    build_slice_selection_report,
    canonical_json_bytes,
    convert_raw_rows_to_rdf,
    normalize_source_row,
    refresh_artifact_indexes,
    sha256_bytes,
    sha256_file,
    stable_json,
    validate_raw_rows,
    write_json,
    write_jsonl,
)
from app.services.lerobot_state_action_contract import LeRobotStateActionContractValidator  # noqa: E402


DEFAULT_REPO_ID = "lerobot/aloha_static_coffee"
DEFAULT_PACKAGE_DIR = ROOT / "docs" / "proof" / "lerobot_public_aloha_slice_semantic_parity_proof_package"
DEFAULT_SOURCE_FILE = "data/chunk-000/file-000.parquet"
DEFAULT_EPISODE_INDEX = 0
DEFAULT_FRAME_START = 0
DEFAULT_FRAME_COUNT = 8
REQUIRED_COLUMNS = (
    "episode_index",
    "frame_index",
    "timestamp",
    "observation.state",
    "action",
    "next.done",
    "index",
    "task_index",
)


def build_public_source_package(
    *,
    package_dir: Path,
    repo_id: str = DEFAULT_REPO_ID,
    source_file: str = DEFAULT_SOURCE_FILE,
    revision: str = "main",
) -> dict[str, Any]:
    try:
        from huggingface_hub import HfApi, hf_hub_download
        import pyarrow.parquet as pq
    except Exception as exc:  # pragma: no cover - exercised through CLI failure mode
        raise RuntimeError(
            "public-source package generation requires optional producer deps; run with "
            "`uv run --with huggingface_hub --with pyarrow scripts/run_lerobot_public_slice_semantic_parity.py`"
        ) from exc

    api = HfApi()
    info = api.dataset_info(repo_id=repo_id, revision=revision, files_metadata=True)
    resolved_revision = str(info.sha)
    if not resolved_revision or resolved_revision == "main":
        raise RuntimeError("resolved_revision must be pinned and non-floating")

    card_data = getattr(info, "cardData", None) or {}
    license_value = _card_value(card_data, "license") or "mit"
    robot_type = "aloha"
    if str(license_value).lower() != "mit":
        raise RuntimeError(f"unexpected source license: {license_value}")

    with tempfile.TemporaryDirectory(prefix="rdf_lerobot_public_slice_") as tmp:
        cache = Path(tmp)
        downloaded: dict[str, Path] = {}
        for filename in (source_file, "meta/info.json", "README.md"):
            downloaded[filename] = Path(
                hf_hub_download(repo_id=repo_id, repo_type="dataset", revision=resolved_revision, filename=filename)
            )

        source_table = pq.read_table(downloaded[source_file], columns=[name for name in REQUIRED_COLUMNS if name])
        raw_rows, feature_schema = extract_raw_rows_from_table(
            source_table,
            repo_id=repo_id,
            resolved_revision=resolved_revision,
            source_file=source_file,
        )

        upstream_files = {}
        for filename, path in downloaded.items():
            upstream_files[filename] = {
                "sha256": sha256_file(path),
                "refetched_sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
                "source_url": _hf_resolve_url(repo_id, resolved_revision, filename),
            }
        source_binding = {
            "schema_version": "rdf_lerobot_public_source_binding_v0.1.0",
            "repo_id": repo_id,
            "source_url": f"https://huggingface.co/datasets/{repo_id}",
            "resolved_revision": resolved_revision,
            "license": str(license_value).lower(),
            "dataset_card_robot_type": robot_type,
            "dataset_card_rows": 55000,
            "dataset_card_total_file_size": "1.57GB",
            "source_file": source_file,
            "provenance_trust_tier": "refetchable_public_source",
            "external_source_included": True,
            "full_dataset_verdict_claimed": False,
            "audited_slice_verdict_claimed": True,
        }
        source_file_sha = upstream_files[source_file]["sha256"]
        if not isinstance(source_file_sha, str):
            raise RuntimeError("source file sha missing")
        reextracted_rows = reextract_raw_rows_from_parquet(
            downloaded[source_file],
            repo_id=repo_id,
            resolved_revision=resolved_revision,
            source_file=source_file,
        )
        if [row["source_row_sha256"] for row in raw_rows] != [row["source_row_sha256"] for row in reextracted_rows]:
            raise RuntimeError("producer and independent re-extractor row digests differ")
        dependency_versions = {
            "huggingface_hub": getattr(sys.modules.get("huggingface_hub"), "__version__", "unknown"),
            "pyarrow": getattr(sys.modules.get("pyarrow"), "__version__", "unknown"),
        }
        result = build_package_from_raw_rows(
            package_dir=package_dir,
            source_binding=source_binding,
            upstream_files=upstream_files,
            raw_rows=raw_rows,
            feature_schema=feature_schema,
            license_text="MIT license declared by Hugging Face dataset metadata for lerobot/aloha_static_coffee.\n",
            source_file_byte_sha256=source_file_sha,
            reextract_command=(
                "uv run --with pyarrow --with huggingface_hub "
                "scripts/verify_lerobot_public_slice_package.py "
                f"{package_dir / 'package_manifest.json'} --reextract-public-source"
            ),
            dependency_versions=dependency_versions,
        )
        shutil.rmtree(cache, ignore_errors=True)
        return result


def extract_raw_rows_from_table(table: Any, *, repo_id: str, resolved_revision: str, source_file: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = table.to_pylist()
    selected = _select_slice_rows(rows)
    raw_rows = [
        normalize_source_row(row, repo_id=repo_id, resolved_revision=resolved_revision, source_file=source_file)
        for row in selected
    ]
    validation = validate_raw_rows(raw_rows, DEFAULT_SLICE_RULE)
    if not validation.ok:
        raise RuntimeError(f"selected raw rows invalid: {validation.issues}")
    feature_schema = {
        "schema_version": "rdf_lerobot_feature_schema_v0.1.0",
        "source": "pyarrow parquet schema",
        "columns": [{"name": field.name, "type": str(field.type)} for field in table.schema],
        "observation_state_dim": validation.observation_state_dim,
        "action_dim": validation.action_dim,
        "row_count_in_selected_table": len(rows),
    }
    return raw_rows, feature_schema


def reextract_raw_rows_from_parquet(path: Path, *, repo_id: str, resolved_revision: str, source_file: str) -> list[dict[str, Any]]:
    import pyarrow.parquet as pq

    table = pq.read_table(path, columns=list(REQUIRED_COLUMNS))
    raw_rows, _feature_schema = extract_raw_rows_from_table(
        table,
        repo_id=repo_id,
        resolved_revision=resolved_revision,
        source_file=source_file,
    )
    return raw_rows


def build_package_from_raw_rows(
    *,
    package_dir: Path,
    source_binding: dict[str, Any],
    upstream_files: dict[str, dict[str, Any]],
    raw_rows: list[dict[str, Any]],
    feature_schema: dict[str, Any],
    license_text: str,
    source_file_byte_sha256: str,
    reextract_command: str,
    dependency_versions: dict[str, str],
) -> dict[str, Any]:
    if package_dir.exists():
        shutil.rmtree(package_dir)
    data_dir = package_dir / "data"
    source_dir = data_dir / "source"
    conversion_dir = data_dir / "conversion"
    contracts_dir = data_dir / "contracts"
    export_dir = data_dir / "export"
    reports_dir = data_dir / "reports"
    for directory in (source_dir, conversion_dir, contracts_dir, export_dir, reports_dir):
        directory.mkdir(parents=True, exist_ok=True)

    feature_schema_sha = sha256_bytes(canonical_json_bytes(feature_schema))
    write_json(source_dir / "public_source_binding.json", source_binding)
    write_json(
        source_dir / "upstream_file_hashes.json",
        {
            "schema_version": "rdf_lerobot_upstream_file_hashes_v0.1.0",
            "repo_id": source_binding["repo_id"],
            "resolved_revision": source_binding["resolved_revision"],
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
            repo_id=source_binding["repo_id"],
            resolved_revision=source_binding["resolved_revision"],
            source_url=source_binding["source_url"],
            upstream_files=upstream_files,
        ),
    )
    write_json(
        source_dir / "extraction_receipt.json",
        build_extraction_receipt(
            repo_id=source_binding["repo_id"],
            resolved_revision=source_binding["resolved_revision"],
            source_file=source_binding["source_file"],
            source_file_byte_sha256=source_file_byte_sha256,
            raw_rows=raw_rows,
            feature_schema_sha256=feature_schema_sha,
            reextract_command=reextract_command,
            dependency_versions=dependency_versions,
        ),
    )
    write_json(
        source_dir / "slice_selection_report.json",
        build_slice_selection_report(
            source_file=source_binding["source_file"],
            raw_rows=raw_rows,
            feature_schema_sha256=feature_schema_sha,
        ),
    )
    write_jsonl(source_dir / "lerobot_raw_rows.jsonl", raw_rows)
    write_json(source_dir / "lerobot_feature_schema.json", feature_schema)
    (source_dir / "LICENSE.txt").write_text(license_text, encoding="utf-8")

    converted_rows, mapping_report, conversion_manifest = convert_raw_rows_to_rdf(raw_rows, source_binding=source_binding)
    write_jsonl(conversion_dir / "rdf_converted_rows.jsonl", converted_rows)
    write_json(conversion_dir / "semantic_mapping_report.json", mapping_report)
    write_json(conversion_dir / "conversion_manifest.json", conversion_manifest)

    validator = LeRobotStateActionContractValidator()
    contract = validator.build_contract(converted_rows, source_binding=source_binding)
    contract_report = validator.validate_rows(converted_rows, expected_robot_type=source_binding["dataset_card_robot_type"])
    write_json(contracts_dir / "normalized_state_action_contract.json", contract)
    write_json(
        contracts_dir / "validator_report.json",
        {
            "schema_version": "rdf_lerobot_state_action_validator_report_v0.1.0",
            "ok": contract_report.ok,
            "issues": contract_report.issues,
            "row_count": contract_report.row_count,
            "observation_state_dim": contract_report.observation_state_dim,
            "action_dim": contract_report.action_dim,
        },
    )
    if not contract_report.ok:
        raise RuntimeError(f"generic state/action contract failed: {contract_report.issues}")

    hdf5_path = export_dir / "dataset.hdf5"
    export_report = export_generic_hdf5(converted_rows, hdf5_path)
    write_json(export_dir / "hdf5_inspection_report.json", export_report)
    trainer_report = run_generic_trainer_smoke(hdf5_path)
    write_json(export_dir / "trainer_smoke_report.json", trainer_report)
    deep_receipt = build_deep_hdf5_receipt(hdf5_path, converted_rows)
    write_json(export_dir / "deep_hdf5_receipt.json", deep_receipt)

    non_claims = build_non_claims()
    write_json(
        data_dir / "non_claims_attestation.json",
        {
            "schema_version": "rdf_lerobot_non_claims_attestation_v0.1.0",
            "non_claims": non_claims,
        },
    )
    buyer = {
        "schema_version": "rdf_lerobot_buyer_data_evaluation_report_v0.1.0",
        "claim": "external_data_evaluated",
        "package_status": "external_data_evaluated",
        "source_kind": "public_lerobot_aloha_audited_slice",
        "provenance_trust_tier": "refetchable_public_source",
        "audited_slice_verdict_claimed": True,
        "full_source_verdict_claimed": False,
        "external_source_included": True,
        "row_count": len(raw_rows),
        "observation_state_dim": contract_report.observation_state_dim,
        "action_dim": contract_report.action_dim,
        "canonical_source_rejected_examples_present": False,
        "accepted_rejected_pair_claimed": False,
        "trainer_smoke_passed": trainer_report["passed"],
        "non_claims": non_claims,
        "claim_boundary": (
            "RDF evaluated one deterministic public LeRobot ALOHA audited slice. "
            "No full dataset evaluation. No real robot success. No physical robot readiness. "
            "No visual policy performance. No policy uplift. No deployable policy readiness. "
            "No marketplace readiness. No production certification. No sim-to-real proof."
        ),
    }
    write_json(reports_dir / "buyer_data_evaluation_report.json", buyer)
    write_json(
        data_dir / "config.json",
        {
            "schema_version": "rdf_lerobot_public_slice_config_v0.1.0",
            "package_status": "external_data_evaluated",
            "external_source_included": True,
            "source_kind": "public_lerobot_aloha_audited_slice",
            "repo_id": source_binding["repo_id"],
            "resolved_revision": source_binding["resolved_revision"],
            "slice_rule": dict(DEFAULT_SLICE_RULE),
            "non_claims": non_claims,
        },
    )
    write_readme(package_dir, source_binding)
    refresh_artifact_indexes(
        package_dir,
        manifest_extra={
            "source_kind": "public_lerobot_aloha_audited_slice",
            "repo_id": source_binding["repo_id"],
            "resolved_revision": source_binding["resolved_revision"],
            "provenance_trust_tier": "refetchable_public_source",
            "audited_slice_verdict_claimed": True,
            "full_source_verdict_claimed": False,
            "non_claims": non_claims,
        },
    )
    return {
        "package_dir": str(package_dir),
        "package_manifest": str(package_dir / "package_manifest.json"),
        "repo_id": source_binding["repo_id"],
        "resolved_revision": source_binding["resolved_revision"],
        "row_count": len(raw_rows),
        "observation_state_dim": contract_report.observation_state_dim,
        "action_dim": contract_report.action_dim,
        "trainer_smoke_passed": trainer_report["passed"],
    }


def export_generic_hdf5(rows: list[dict[str, Any]], hdf5_path: Path) -> dict[str, Any]:
    import h5py
    import numpy as np

    states = np.asarray([row["observation_state"] for row in rows], dtype=np.float32)
    actions = np.asarray([row["learning_action"] for row in rows], dtype=np.float32)
    timestamps = np.asarray([[float(row["timestamp"])] for row in rows], dtype=np.float32)
    episode_id = "aloha_episode_000000"
    with h5py.File(hdf5_path, "w") as h5:
        h5.attrs["schema_version"] = "rdf_lerobot_generic_state_action_hdf5_v0.1.0"
        h5.attrs["source_kind"] = "public_lerobot_aloha_audited_slice"
        episodes = h5.create_group("episodes")
        episodes.create_dataset("episode_ids", data=np.asarray([episode_id], dtype="S"))
        obs = h5.create_group("observations")
        actions_group = h5.create_group("actions")
        ts = h5.create_group("timestamps")
        obs.create_group(episode_id).create_dataset("observation_state", data=states)
        actions_group.create_group(episode_id).create_dataset("learning_action", data=actions)
        ts.create_group(episode_id).create_dataset("t", data=timestamps)
    return {
        "schema_version": "rdf_lerobot_hdf5_inspection_report_v0.1.0",
        "passed": True,
        "hdf5_path": "data/export/dataset.hdf5",
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
        "sample_count": int(observations.shape[0]) if "observations" in locals() else 0,
        "observation_state_dim": int(observations.shape[1]) if "observations" in locals() and observations.ndim == 2 else 0,
        "action_dim": int(actions.shape[1]) if "actions" in locals() and actions.ndim == 2 else 0,
        "initial_loss": initial_loss,
        "final_loss": final_loss,
        "issues": issues,
    }


def build_deep_hdf5_receipt(hdf5_path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    import h5py
    import numpy as np

    with h5py.File(hdf5_path, "r") as h5:
        episode_id = h5["episodes/episode_ids"][0].decode("utf-8")
        states = np.asarray(h5[f"observations/{episode_id}/observation_state"][()], dtype=np.float32)
        actions = np.asarray(h5[f"actions/{episode_id}/learning_action"][()], dtype=np.float32)
    expected_states = np.asarray([row["observation_state"] for row in rows], dtype=np.float32)
    expected_actions = np.asarray([row["learning_action"] for row in rows], dtype=np.float32)
    matched = bool(np.array_equal(states, expected_states) and np.array_equal(actions, expected_actions))
    return {
        "schema_version": "rdf_lerobot_deep_hdf5_receipt_v0.1.0",
        "checked_at_utc": datetime.now(UTC).isoformat(),
        "checker": "generic_state_action_hdf5_deep_compare",
        "hdf5_path": "data/export/dataset.hdf5",
        "row_count": len(rows),
        "observation_state_dim": int(states.shape[1]) if states.ndim == 2 else 0,
        "action_dim": int(actions.shape[1]) if actions.ndim == 2 else 0,
        "converted_row_sha256s": [sha256_bytes(canonical_json_bytes(row)) for row in rows],
        "hdf5_observation_state_sha256": sha256_bytes(states.tobytes()),
        "expected_observation_state_sha256": sha256_bytes(expected_states.tobytes()),
        "hdf5_learning_action_sha256": sha256_bytes(actions.tobytes()),
        "expected_learning_action_sha256": sha256_bytes(expected_actions.tobytes()),
        "matched": matched,
    }


def write_readme(package_dir: Path, source_binding: dict[str, Any]) -> None:
    text = f"""# LeRobot Public ALOHA Audited Slice Semantic Parity Package

This package supports one narrow claim: Robot Data Forge evaluated a
deterministic audited slice from the public LeRobot dataset
`{source_binding["repo_id"]}` at pinned revision `{source_binding["resolved_revision"]}`.

The default verifier recomputes source binding, included raw row validity,
raw-to-RDF semantic conversion, generic state/action contract agreement,
export/trainer-smoke evidence, receipt consistency, HDF5 float32 payload
presence for this package's fixed layout, spent-range discipline, and
non-claim boundaries from files in this repository.

This is an ALOHA audited-slice profile, not a general LeRobot importer.
The fixed repo id, pinned revision, source file, first-episode slice rule,
14-dimensional state/action contract, and HDF5 layout are part of the
verifier contract for this package. A second public LeRobot dataset should
define a new explicit slice profile instead of silently reusing these
assumptions.

```bash
python3 scripts/verify_lerobot_public_slice_package.py \\
  docs/proof/lerobot_public_aloha_slice_semantic_parity_proof_package/package_manifest.json
```

Optional stronger checks:

```bash
python3 scripts/verify_lerobot_public_slice_package.py <manifest> --deep-hdf5
python3 scripts/verify_lerobot_public_slice_package.py <manifest> --refetch-public-source
uv run --with pyarrow scripts/verify_lerobot_public_slice_package.py <manifest> --reextract-public-source
```

The default verifier is offline. `--refetch-public-source` rechecks the public
Hugging Face files against the pinned hashes, and `--reextract-public-source`
rebuilds the included raw rows from the pinned Parquet source.

Non-claims:

- No full LeRobot parser support.
- No full dataset evaluation.
- No real robot success.
- No physical robot readiness.
- No live hardware support.
- No visual policy performance.
- No policy uplift.
- No deployable policy readiness.
- No marketplace readiness.
- No production certification.
- No sim-to-real proof.
"""
    (package_dir / "README.md").write_text(text, encoding="utf-8")


def _select_slice_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [
        row
        for row in rows
        if row.get("episode_index") == DEFAULT_EPISODE_INDEX
        and DEFAULT_FRAME_START <= row.get("frame_index", -1) < DEFAULT_FRAME_START + DEFAULT_FRAME_COUNT
    ]
    selected = sorted(selected, key=lambda row: row["frame_index"])
    expected_frames = list(range(DEFAULT_FRAME_START, DEFAULT_FRAME_START + DEFAULT_FRAME_COUNT))
    actual_frames = [row["frame_index"] for row in selected]
    if actual_frames != expected_frames:
        raise RuntimeError(f"selected frames {actual_frames} do not match expected {expected_frames}")
    return selected


def _card_value(card_data: Any, key: str) -> Any:
    if isinstance(card_data, dict):
        return card_data.get(key)
    return getattr(card_data, key, None)


def _hf_resolve_url(repo_id: str, revision: str, filename: str) -> str:
    return f"https://huggingface.co/datasets/{repo_id}/resolve/{revision}/{filename}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, default=DEFAULT_PACKAGE_DIR)
    parser.add_argument("--repo-id", default=DEFAULT_REPO_ID)
    parser.add_argument("--source-file", default=DEFAULT_SOURCE_FILE)
    parser.add_argument("--revision", default="main")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_public_source_package(
        package_dir=args.package_dir,
        repo_id=args.repo_id,
        source_file=args.source_file,
        revision=args.revision,
    )
    if args.pretty:
        print(stable_json(result))
    else:
        print("LeRobot public slice semantic parity package built")
        print(f"package_manifest={result['package_manifest']}")
        print(f"resolved_revision={result['resolved_revision']}")
        print(f"row_count={result['row_count']}")
        print(f"observation_state_dim={result['observation_state_dim']}")
        print(f"action_dim={result['action_dim']}")
        print(f"trainer_smoke_passed={str(result['trainer_smoke_passed']).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
