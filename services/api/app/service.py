from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from .identity_gate import candidate_by_id
from .identity_provider import IdentityResearchProvider
from .models import ClarificationCreate, IdentityGate, IdentityResearchResult, Task, TaskStatus
from .state_machine import transition
from .store import InMemoryTaskStore


class TaskNotFound(LookupError):
    pass


class ClarificationError(ValueError):
    pass


class TaskService:
    def __init__(self, store: InMemoryTaskStore, provider: IdentityResearchProvider) -> None:
        self.store = store
        self.provider = provider

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
        task.next_action = "P2.2.1在正式报告生成前暂停。"
        task.phase_limit_reached = True
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
