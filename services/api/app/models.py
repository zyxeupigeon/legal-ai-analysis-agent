from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

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
    operator_name: str | None = None
    product_type: str | None = None
    is_legal_ai: bool | None = None
    source_urls: list[str] = Field(default_factory=list)


class EvidenceSource(BaseModel):
    url: str
    title: str
    source_type: Literal[
        "government",
        "regulator",
        "official_product",
        "official_docs",
        "official_terms",
        "official_company",
        "industry",
        "research",
        "media",
        "other",
    ]
    supports: list[Literal["identity", "operator", "legal_ai_scope", "ecosystem", "api", "mcp"]]


class RelatedProduct(BaseModel):
    name: str
    kind: Literal[
        "product",
        "api",
        "mcp",
        "model_platform",
        "developer_platform",
        "database",
        "knowledge_base",
        "agent",
        "plugin",
        "connector",
        "skill",
        "other",
    ]
    relationship: str
    verification_status: Literal["confirmed", "lead_only", "not_publicly_verified"]
    source_urls: list[str] = Field(default_factory=list)


class IdentityResearchResult(BaseModel):
    outcome: Literal["clear", "ambiguous", "rejected"]
    canonical_product_name: str | None
    operator_name: str | None
    product_type: str | None
    is_legal_ai: bool | None
    clarification_question: str | None
    candidates: list[Candidate]
    related_products: list[RelatedProduct]
    sources: list[EvidenceSource]
    summary: str
    limitations: list[str]
    web_search_used: bool = False


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
    related_products: list[RelatedProduct] = Field(default_factory=list)
    sources: list[EvidenceSource] = Field(default_factory=list)
    research_summary: str | None = None
    limitations: list[str] = Field(default_factory=list)
    web_search_used: bool = False
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
    classifier_mode: str = "openai_web_search"
    model_name: str | None = None


class HealthResponse(BaseModel):
    status: str
    app_version: str
    storage_mode: str
    classifier_mode: str
    provider_ready: bool
    model_name: str | None = None
    model_provider: str
    search_provider: str
    search_tier: str
    message: str
