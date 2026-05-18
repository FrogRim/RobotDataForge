from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import settings
from app.services.exporter import export_dataset


def test_exporter_writes_json() -> None:
    with TemporaryDirectory() as tmp:
        settings.storage_root = Path(tmp)
        path = export_dataset("dataset_test", "peg_in_hole_validated_v0", [{"episode": {"id": "episode_001"}}], "json")
        assert Path(path).exists()
        assert "peg_in_hole_validated_v0" in Path(path).read_text(encoding="utf-8")


if __name__ == "__main__":
    test_exporter_writes_json()
