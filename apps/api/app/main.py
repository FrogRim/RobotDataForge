from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import admin, collection_sessions, datasets, episodes, evaluations, file_drop, human_reviews, learning_experiments, tasks, trajectories

app = FastAPI(title="Robot Data Forge API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

app.include_router(tasks.router)
app.include_router(episodes.router)
app.include_router(trajectories.router)
app.include_router(evaluations.router)
app.include_router(datasets.router)
app.include_router(collection_sessions.router)
app.include_router(human_reviews.router)
app.include_router(learning_experiments.router)
app.include_router(admin.router)
app.include_router(file_drop.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
