from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .models import ClarificationCreate, HealthResponse, Task, TaskCreate
from .service import ClarificationError, TaskNotFound, TaskService
from .store import InMemoryTaskStore


APP_VERSION = "0.1.0"

store = InMemoryTaskStore()
service = TaskService(store)

app = FastAPI(
    title="法律AI分析Agent API",
    version=APP_VERSION,
    description="P2.1单用户本地身份闸门；不建库、不调用模型、不生成报告。",
)

default_origins = "http://localhost:3000,http://127.0.0.1:3000"
origins = [item.strip() for item in os.getenv("LEGAL_AGENT_CORS_ORIGINS", default_origins).split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app_version=APP_VERSION,
        storage_mode="memory_only",
        classifier_mode="deterministic_fixture",
    )


@app.post("/api/tasks", response_model=Task, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate) -> Task:
    return service.create(payload.product_name)


@app.get("/api/tasks", response_model=list[Task])
def list_tasks() -> list[Task]:
    return store.list()


@app.get("/api/tasks/{task_id}", response_model=Task)
def get_task(task_id: str) -> Task:
    task = store.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@app.post("/api/tasks/{task_id}/clarifications", response_model=Task)
def clarify_task(task_id: str, payload: ClarificationCreate) -> Task:
    try:
        return service.clarify(task_id, payload)
    except TaskNotFound as exc:
        raise HTTPException(status_code=404, detail="任务不存在") from exc
    except ClarificationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
