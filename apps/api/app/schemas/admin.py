from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class AdminKpiResponse(BaseModel):
    collection: dict[str, Any]
    xr_runtime: dict[str, Any]
    evaluation: dict[str, Any]
    learning: dict[str, Any]
    curation: dict[str, Any] | None = None
    data_usability: dict[str, Any] | None = None
