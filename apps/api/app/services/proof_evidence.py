"""Proof evidence preservation helpers.

This module records a small, tracked manifest for generated proof artifacts
without changing the proof artifact contents or success criteria.
"""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any


EVIDENCE_MANIFEST_SCHEMA_VERSION = "rdf_proof_evidence_manifest_v0.1.0"
EVIDENCE_MANIFEST_NAME = "evidence_manifest.json"


def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_payload(payload: Any) -> str:
    return hashlib.sha256(stable_json(payload).encode("utf-8")).hexdigest()


def _iter_manifest_files(output_dir: Path) -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file() or path.name == EVIDENCE_MANIFEST_NAME:
            continue
        relative_path = path.relative_to(output_dir).as_posix()
        files.append(
            {
                "path": relative_path,
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return files


def write_evidence_manifest(
    *,
    output_dir: Path,
    proof_slice: str,
    reproducible_command: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write an evidence manifest for all current files under output_dir.

    The manifest intentionally excludes itself so its digest is stable and
    every listed sha256 refers to a concrete proof artifact.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema_version": EVIDENCE_MANIFEST_SCHEMA_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "proof_slice": proof_slice,
        "output_dir": str(output_dir),
        "reproducible_command": reproducible_command,
        "manifest_excludes": [EVIDENCE_MANIFEST_NAME],
        "large_artifact_policy": "large artifacts may remain gitignored under storage; this manifest records path, size, and sha256.",
        "files": _iter_manifest_files(output_dir),
    }
    if metadata:
        payload.update(metadata)
    payload["file_count"] = len(payload["files"])
    payload["evidence_manifest_sha256"] = sha256_payload(
        {key: value for key, value in payload.items() if key != "evidence_manifest_sha256"}
    )
    (output_dir / EVIDENCE_MANIFEST_NAME).write_text(stable_json(payload) + "\n", encoding="utf-8")
    return payload
