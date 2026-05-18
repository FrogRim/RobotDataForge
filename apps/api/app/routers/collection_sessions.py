from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.collection_session import CollectionSession
from app.schemas.collection_session import (
    CollectionSessionCompleteRequest,
    CollectionSessionCompleteResponse,
    CollectionSessionRead,
    CollectionSessionStartRequest,
    CollectionSessionStartResponse,
)
from app.services.session_manager import session_is_invalid

router = APIRouter(prefix="/api/collection-sessions", tags=["collection-sessions"])


@router.post("/start", response_model=CollectionSessionStartResponse)
def start_collection_session(
    payload: CollectionSessionStartRequest,
    db: Session = Depends(get_db),
) -> CollectionSessionStartResponse:
    session = CollectionSession(
        id=f"session_{uuid4().hex[:12]}",
        task_id=payload.task_id,
        contributor_id=payload.contributor_id,
        isaac_task_name=payload.isaac_task_name,
        input_device=payload.input_device,
        xr_runtime=payload.xr_runtime,
        streaming_stack=payload.streaming_stack,
        status="recording",
    )
    db.add(session)
    db.commit()
    return CollectionSessionStartResponse(session_id=session.id, status=session.status)


@router.post("/{session_id}/complete", response_model=CollectionSessionCompleteResponse)
def complete_collection_session(
    session_id: str,
    payload: CollectionSessionCompleteRequest,
    db: Session = Depends(get_db),
) -> CollectionSessionCompleteResponse:
    session = db.get(CollectionSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Collection session not found")
    invalid_reason = session_is_invalid(payload.runtime_metrics)
    session.status = "invalid" if invalid_reason else "completed"
    session.ended_at = datetime.now(timezone.utc)
    session.runtime_metrics = {**payload.runtime_metrics, "invalid_reason": invalid_reason}
    db.commit()
    return CollectionSessionCompleteResponse(session_id=session.id, status=session.status)


@router.get("/{session_id}", response_model=CollectionSessionRead)
def get_collection_session(session_id: str, db: Session = Depends(get_db)) -> CollectionSession:
    session = db.get(CollectionSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Collection session not found")
    return session
