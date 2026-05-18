from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.evaluation import Evaluation
from app.models.human_review import HumanReview
from app.schemas.human_review import HumanReviewCreateRequest, HumanReviewCreateResponse

router = APIRouter(prefix="/api/human-reviews", tags=["human-reviews"])


@router.post("", response_model=HumanReviewCreateResponse)
def create_human_review(payload: HumanReviewCreateRequest, db: Session = Depends(get_db)) -> HumanReviewCreateResponse:
    evaluation = db.query(Evaluation).filter(Evaluation.trajectory_id == payload.trajectory_id).order_by(Evaluation.created_at.desc()).first()
    if evaluation is None:
        raise HTTPException(status_code=404, detail="Evaluation not found for trajectory")
    agreement = evaluation.success == payload.human_success_label
    evaluation.human_review_label = payload.human_success_label
    review = HumanReview(
        id=f"review_{uuid4().hex[:12]}",
        episode_id=payload.episode_id,
        trajectory_id=payload.trajectory_id,
        reviewer_id=payload.reviewer_id,
        human_success_label=payload.human_success_label,
        evaluator_success_label=evaluation.success,
        agreement=agreement,
        notes=payload.notes,
    )
    db.add(review)
    db.commit()
    return HumanReviewCreateResponse(review_id=review.id, agreement=agreement)
