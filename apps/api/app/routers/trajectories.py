from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.action_segment import ActionSegment
from app.models.trajectory import Trajectory
from app.schemas.quality import ActionSegmentRead
from app.schemas.trajectory import TrajectoryRead

router = APIRouter(prefix="/api/trajectories", tags=["trajectories"])


@router.get("/{trajectory_id}", response_model=TrajectoryRead)
def get_trajectory(trajectory_id: str, db: Session = Depends(get_db)) -> Trajectory:
    trajectory = db.get(Trajectory, trajectory_id)
    if trajectory is None:
        raise HTTPException(status_code=404, detail="Trajectory not found")
    return trajectory


@router.get("/{trajectory_id}/segments", response_model=list[ActionSegmentRead])
def get_trajectory_segments(trajectory_id: str, db: Session = Depends(get_db)) -> list[ActionSegment]:
    if db.get(Trajectory, trajectory_id) is None:
        raise HTTPException(status_code=404, detail="Trajectory not found")
    return list(
        db.query(ActionSegment)
        .filter(ActionSegment.trajectory_id == trajectory_id)
        .order_by(ActionSegment.start_frame.asc())
        .all()
    )
