from __future__ import annotations

import os
from pathlib import Path


class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./storage/local_api.sqlite",
    )
    storage_root: Path = Path(os.getenv("STORAGE_ROOT", "storage"))
    isaac_handtracking_script: Path = Path(
        os.getenv("ISAAC_HANDTRACKING_SCRIPT", "/home/kangrim/run_isaac_handtracking.sh")
    )


settings = Settings()
