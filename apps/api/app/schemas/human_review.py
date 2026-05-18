from __future__ import annotations

from pydantic import BaseModel


class HumanReviewCreateRequest(BaseModel):
    episode_id: str
    trajectory_id: str
    reviewer_id: str
    human_success_label: bool
    notes: str = ""


class HumanReviewCreateResponse(BaseModel):
    review_id: str
    agreement: bool | None
