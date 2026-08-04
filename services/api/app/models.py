from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaskStatus(StrEnum):
    UNIDENTIFIED = "待识别"
    AWAITING_PRODUCT_CONFIRMATION = "等待产品确认"
    RESEARCHING = "研究中"
    TERMINATED = "已终止"


class IdentityGate(StrEnum):
    UNREVIEWED = "unreviewed"
    CLEAR = "clear"
    AMBIGUOUS = "ambiguous"
    AWAITING_USER = "awaiting_user"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


class Candidate(BaseModel):
    id: str
    product_name: str
    operator_name: str
    product_type: str
    is_legal_ai: bool


class TaskEvent(BaseModel):
    event_type: str
    from_status: TaskStatus | None
    to_status: TaskStatus
    reason: str
    occurred_at: datetime


class TaskCreate(BaseModel):
    product_name: str = Field(max_length=120)

    @field_validator("product_name")
    @classmethod
    def normalize_product_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("请输入想分析的法律AI产品名称")
        return normalized


class ClarificationCreate(BaseModel):
    candidate_id: str | None = Field(default=None, max_length=80)
    confirmed_product_name: str | None = Field(default=None, max_length=120)

    @field_validator("confirmed_product_name")
    @classmethod
    def normalize_confirmed_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None


class Task(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    task_id: str
    submitted_product_name: str
    canonical_product_name: str | None = None
    operator_name: str | None = None
    product_type: str | None = None
    task_status: TaskStatus
    identity_gate: IdentityGate
    clarification_question: str | None = None
    candidates: list[Candidate] = Field(default_factory=list)
    related_product_hints: list[str] = Field(default_factory=list)
    status_message: str
    next_action: str | None = None
    phase_limit_reached: bool = False
    created_at: datetime
    updated_at: datetime
    events: list[TaskEvent] = Field(default_factory=list)
    core_version: str = "1.1"
    workflow_version: str = "1.1"
    skill_name: str = "legal-report-review-and-verification"
    storage_mode: str = "memory_only"
    classifier_mode: str = "deterministic_fixture"


class HealthResponse(BaseModel):
    status: str
    app_version: str
    storage_mode: str
    classifier_mode: str
