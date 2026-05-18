from __future__ import annotations

from fastapi import FastAPI

from app.routers import admin, collection_sessions, datasets, episodes, evaluations, human_reviews, learning_experiments, tasks, trajectories

app = FastAPI(title="Robot Data Forge API", version="0.1.0")

app.include_router(tasks.router)
app.include_router(episodes.router)
app.include_router(trajectories.router)
app.include_router(evaluations.router)
app.include_router(datasets.router)
app.include_router(collection_sessions.router)
app.include_router(human_reviews.router)
app.include_router(learning_experiments.router)
app.include_router(admin.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
