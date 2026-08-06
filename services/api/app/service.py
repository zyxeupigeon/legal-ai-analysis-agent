from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .identity_gate import candidate_by_id
from .identity_provider import IdentityResearchProvider
from .models import (
    ClarificationCreate,
    IdentityGate,
    IdentityResearchResult,
    ReportArtifact,
    ReportStatus,
    Task,
    TaskStatus,
)
from .report_document import build_report_docx, report_file_name
from .report_provider import ReportDraftProvider, report_provider_from_identity
from .state_machine import transition
from .store import InMemoryTaskStore


class TaskNotFound(LookupError):
    pass


class ClarificationError(ValueError):
    pass


class ReportGenerationError(ValueError):
    pass


class TaskService:
    def __init__(
        self,
        store: InMemoryTaskStore,
        provider: IdentityResearchProvider,
        *,
        report_provider: ReportDraftProvider | None = None,
        artifact_root: Path | None = None,
    ) -> None:
        self.store = store
        self.provider = provider
        self.report_provider = report_provider or report_provider_from_identity(provider)
        self.artifact_root = artifact_root or Path("artifacts/local")

    def create(self, product_name: str) -> Task:
        now = datetime.now(UTC)
        task = Task(
            task_id=str(uuid4()),
            submitted_product_name=product_name,
            task_status=TaskStatus.UNIDENTIFIED,
            identity_gate=IdentityGate.UNREVIEWED,
            status_message="正在通过公开信息执行产品身份闸门。",
            created_at=now,
            updated_at=now,
            classifier_mode=self.provider.mode,
            model_name=self.provider.model_name,
        )
        result = self.provider.research(product_name)
        self._apply_result(task, result)
        return self.store.add(task)

    def clarify(self, task_id: str, payload: ClarificationCreate) -> Task:
        task = self.store.get(task_id)
        if not task:
            raise TaskNotFound(task_id)
        if TaskStatus(task.task_status) is not TaskStatus.AWAITING_PRODUCT_CONFIRMATION:
            raise ClarificationError("当前任务不在等待产品确认状态")
        if bool(payload.candidate_id) == bool(payload.confirmed_product_name):
            raise ClarificationError("必须且只能选择一个候选项，或填写一个确切产品全称")

        operator_hint: str | None = None
        if payload.candidate_id:
            selected = candidate_by_id(task.candidates, payload.candidate_id)
            if not selected:
                raise ClarificationError("候选项不存在或已失效")
            confirmed_name = selected.product_name
            operator_hint = selected.operator_name
        else:
            assert payload.confirmed_product_name is not None
            confirmed_name = payload.confirmed_product_name

        result = self.provider.research(
            confirmed_name,
            confirmed_by_user=True,
            operator_hint=operator_hint,
        )
        task.candidates = []
        task.clarification_question = None
        self._apply_result(task, result, clarification_round=True)
        return self.store.save(task)

    def generate_report(self, task_id: str) -> ReportArtifact:
        task = self.store.get(task_id)
        if not task:
            raise TaskNotFound(task_id)
        if IdentityGate(task.identity_gate) is not IdentityGate.CONFIRMED:
            raise ReportGenerationError("只有通过身份闸门的法律AI产品才能生成报告")
        try:
            draft = self.report_provider.generate(task)
            generated_at = datetime.now(UTC)
            file_name = report_file_name(task, generated_at.date())
            output_path = self.report_path(task.task_id, file_name)
            build_report_docx(draft, task, output_path, generated_on=generated_at.date())
        except Exception:
            task.report_status = ReportStatus.FAILED
            task.status_message = "报告研究或Word生成失败，未产生可下载文件。"
            task.updated_at = datetime.now(UTC)
            self.store.save(task)
            raise
        task.report_status = ReportStatus.READY
        task.report_file_name = file_name
        task.report_version = "0.4-p2.3.4-test"
        task.report_generated_at = generated_at
        task.phase_limit_reached = True
        task.status_message = "已生成通过证据相关性审计与时间口径冲突处理的P2.3.4本地Word测试稿。"
        task.next_action = "请下载检查引用相关性和冲突说明；当前仍不建库、不部署、不训练。"
        task.updated_at = generated_at
        self.store.save(task)
        return ReportArtifact(
            task_id=task.task_id,
            report_status=ReportStatus.READY,
            file_name=file_name,
            version=task.report_version,
            generated_at=generated_at,
            download_url=f"/api/tasks/{task.task_id}/reports/latest/download",
        )

    def latest_report_path(self, task_id: str) -> tuple[Task, Path]:
        task = self.store.get(task_id)
        if not task:
            raise TaskNotFound(task_id)
        if ReportStatus(task.report_status) is not ReportStatus.READY or not task.report_file_name:
            raise ReportGenerationError("当前任务还没有可下载的Word报告")
        path = self.report_path(task.task_id, task.report_file_name)
        if not path.is_file():
            raise ReportGenerationError("本地报告文件不存在，可能已被移动或清理")
        return task, path

    def report_path(self, task_id: str, file_name: str) -> Path:
        return self.artifact_root / task_id / file_name

    def _apply_result(
        self,
        task: Task,
        result: IdentityResearchResult,
        *,
        clarification_round: bool = False,
    ) -> None:
        task.sources = result.sources
        task.related_products = result.related_products
        task.related_product_hints = [
            f"{item.name}（{item.kind} / {item.verification_status}）" for item in result.related_products
        ]
        task.research_summary = result.summary
        task.limitations = result.limitations
        task.web_search_used = result.web_search_used
        task.canonical_product_name = result.canonical_product_name
        task.operator_name = result.operator_name
        task.product_type = result.product_type

        if result.outcome == "clear":
            self._mark_confirmed(task, result.summary)
            return
        if result.outcome == "rejected":
            self._mark_rejected(task, result.summary)
            return

        task.identity_gate = IdentityGate.AWAITING_USER
        task.clarification_question = result.clarification_question or "请提供确切产品全称和运营企业。"
        task.candidates = result.candidates
        task.related_products = []
        task.related_product_hints = []
        task.status_message = "公开信息仍不足以唯一确认产品，已暂停后续识别。"
        task.next_action = "请确认确切产品；确认前不会扩展同企业生态、成稿、入库或训练。"
        task.phase_limit_reached = False
        if not clarification_round:
            transition(task, TaskStatus.AWAITING_PRODUCT_CONFIRMATION, result.summary)
        else:
            task.updated_at = datetime.now(UTC)

    @staticmethod
    def _mark_confirmed(task: Task, reason: str) -> None:
        task.identity_gate = IdentityGate.CONFIRMED
        task.candidates = []
        task.clarification_question = None
        task.status_message = "身份、运营主体与法律AI边界已完成公开核验；相关AI产品/API/MCP线索已识别。"
        task.next_action = "可以生成P2.3.4证据相关性审计Word测试稿。"
        task.phase_limit_reached = False
        transition(task, TaskStatus.RESEARCHING, reason)

    @staticmethod
    def _mark_rejected(task: Task, reason: str) -> None:
        task.identity_gate = IdentityGate.REJECTED
        task.candidates = []
        task.clarification_question = None
        task.related_products = []
        task.related_product_hints = []
        task.status_message = "公开信息确认该对象不属于法律AI产品，未执行后续分析。"
        task.next_action = None
        task.phase_limit_reached = False
        transition(task, TaskStatus.TERMINATED, reason)
