from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from app.config import settings


SAFE_FILE_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


def _root() -> Path:
    root = settings.storage_root
    if not root.is_absolute():
        root = Path.cwd() / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_json(relative_dir: str, file_id: str, data: dict[str, Any]) -> str:
    directory = _root() / relative_dir
    directory.mkdir(parents=True, exist_ok=True)
    safe_id = safe_file_id(file_id)
    path = directory / f"{safe_id}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)


def safe_file_id(file_id: str) -> str:
    candidate = Path(file_id)
    if candidate.is_absolute() or len(candidate.parts) != 1:
        raise ValueError("file_id must be a single relative filename component")
    if file_id in {"", ".", ".."} or not SAFE_FILE_ID.fullmatch(file_id):
        raise ValueError("file_id contains unsafe characters")
    return file_id


def save_trajectory(trajectory_id: str, data: dict[str, Any]) -> str:
    return _write_json("trajectories", trajectory_id, data)


def load_trajectory(trajectory_id: str) -> dict[str, Any]:
    path = _root() / "trajectories" / f"{trajectory_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def save_evaluation(evaluation_id: str, data: dict[str, Any]) -> str:
    return _write_json("evaluations", evaluation_id, data)


def save_export(dataset_id: str, data: dict[str, Any]) -> str:
    return _write_json("exports", dataset_id, data)


def save_dataset_card(dataset_id: str, data: dict[str, Any]) -> str:
    return _write_json("dataset_cards", dataset_id, data)
