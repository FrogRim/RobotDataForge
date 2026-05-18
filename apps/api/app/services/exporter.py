from __future__ import annotations

from typing import Any

from app.services.storage import save_export


SUPPORTED_EXPORT_FORMATS = {"json", "hdf5", "lerobot_v3"}


def export_dataset(
    dataset_id: str,
    dataset_name: str,
    episodes: list[dict[str, Any]],
    export_format: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> str:
    if export_format not in SUPPORTED_EXPORT_FORMATS:
        raise ValueError(f"Unsupported export_format: {export_format}")
    metadata = metadata or {}
    export_payload = {
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        "schema_version": "0.1.0",
        "export_format": export_format,
        "export_status": "exported" if export_format == "json" else "placeholder",
        "episodes": episodes,
        "splits": {
            "train": 0.8,
            "validation": 0.1,
            "test": 0.1,
        },
        "metadata": metadata,
    }
    if export_format in {"hdf5", "lerobot_v3"}:
        export_payload["episodes"] = []
        export_payload["placeholder"] = {
            "requested_format": export_format,
            "actual_file_type": "json_manifest",
            "reason": "Live API export is metadata-ready only. Use offline HDF5 exporter for training datasets.",
        }
    return save_export(dataset_id, export_payload)
