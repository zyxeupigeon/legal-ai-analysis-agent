from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from .identity_provider import (
    IdentityResearchProvider,
    provider_from_env,
)
from .models import ClarificationCreate, HealthResponse, Task, TaskCreate
from .provider_errors import ProviderInvalidResponse, ProviderNotConfigured, ProviderUnavailable
from .service import ClarificationError, TaskNotFound, TaskService
from .store import InMemoryTaskStore


APP_VERSION = "0.2.1"


def create_app(
    provider: IdentityResearchProvider | None = None,
    task_store: InMemoryTaskStore | None = None,
) -> FastAPI:
    active_provider = provider or provider_from_env()
    active_store = task_store or InMemoryTaskStore()
    service = TaskService(active_store, active_provider)

    application = FastAPI(
        title="法律AI分析Agent API",
        version=APP_VERSION,
        description="P2.2单用户本地身份闸门与真实公开信息检索；不建库、不生成报告、不训练。",
    )
    application.state.task_store = active_store
    application.state.identity_provider = active_provider

    default_origins = "http://localhost:3000,http://127.0.0.1:3000"
    origins = [
        item.strip()
        for item in os.getenv("LEGAL_AGENT_CORS_ORIGINS", default_origins).split(",")
        if item.strip()
    ]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    def execute(operation):
        try:
            return operation()
        except ProviderNotConfigured as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ProviderUnavailable as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except ProviderInvalidResponse as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @application.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(
            status="ok" if active_provider.ready else "needs_configuration",
            app_version=APP_VERSION,
            storage_mode="memory_only",
            classifier_mode=active_provider.mode,
            provider_ready=active_provider.ready,
            model_name=active_provider.model_name,
            model_provider=active_provider.model_provider_name,
            search_provider=active_provider.search_provider_name,
            message=active_provider.readiness_message,
        )

    @application.post("/api/tasks", response_model=Task, status_code=status.HTTP_201_CREATED)
    def create_task(payload: TaskCreate) -> Task:
        return execute(lambda: service.create(payload.product_name))

    @application.get("/api/tasks", response_model=list[Task])
    def list_tasks() -> list[Task]:
        return active_store.list()

    @application.get("/api/tasks/{task_id}", response_model=Task)
    def get_task(task_id: str) -> Task:
        task = active_store.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        return task

    @application.post("/api/tasks/{task_id}/clarifications", response_model=Task)
    def clarify_task(task_id: str, payload: ClarificationCreate) -> Task:
        try:
            return execute(lambda: service.clarify(task_id, payload))
        except TaskNotFound as exc:
            raise HTTPException(status_code=404, detail="任务不存在") from exc
        except ClarificationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return application


app = create_app()
store: InMemoryTaskStore = app.state.task_store
