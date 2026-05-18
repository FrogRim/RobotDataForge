from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskRead, TaskSummary

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.post("", response_model=TaskSummary)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)) -> Task:
    existing = (
        db.query(Task)
        .filter(Task.name == payload.name, Task.task_type == payload.task_type)
        .order_by(Task.created_at.desc())
        .first()
    )
    if existing is not None:
        return existing
    task = Task(id=f"task_{uuid4().hex[:12]}", **payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("", response_model=list[TaskSummary])
def list_tasks(db: Session = Depends(get_db)) -> list[Task]:
    return list(db.query(Task).order_by(Task.created_at.desc()).all())


@router.get("/{task_id}", response_model=TaskRead)
def get_task(task_id: str, db: Session = Depends(get_db)) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
