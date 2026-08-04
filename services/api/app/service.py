from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from .identity_gate import candidate_by_id, evaluate_product_name
from .models import ClarificationCreate, IdentityGate, Task, TaskStatus
from .state_machine import transition
from .store import InMemoryTaskStore


class TaskNotFound(LookupError):
    pass


class ClarificationError(ValueError):
    pass


class TaskService:
    def __init__(self, store: InMemoryTaskStore) -> None:
        self.store = store

    def create(self, product_name: str) -> Task:
        now = datetime.now(UTC)
        task = Task(
            task_id=str(uuid4()),
            submitted_product_name=product_name,
            task_status=TaskStatus.UNIDENTIFIED,
            identity_gate=IdentityGate.UNREVIEWED,
            status_message="正在执行产品身份闸门。",
            created_at=now,
            updated_at=now,
        )
        decision = evaluate_product_name(product_name)
        self._apply_decision(task, decision)
        return self.store.add(task)

    def clarify(self, task_id: str, payload: ClarificationCreate) -> Task:
        task = self.store.get(task_id)
        if not task:
            raise TaskNotFound(task_id)
        if TaskStatus(task.task_status) is not TaskStatus.AWAITING_PRODUCT_CONFIRMATION:
            raise ClarificationError("当前任务不在等待产品确认状态")
        if bool(payload.candidate_id) == bool(payload.confirmed_product_name):
            raise ClarificationError("必须且只能选择一个候选项，或填写一个确切产品全称")

        if payload.candidate_id:
            selected = candidate_by_id(task.candidates, payload.candidate_id)
            if not selected:
                raise ClarificationError("候选项不存在或已失效")
            task.canonical_product_name = selected.product_name
            task.operator_name = selected.operator_name
            task.product_type = selected.product_type
            task.candidates = []
            task.clarification_question = None
            if selected.is_legal_ai:
                self._mark_confirmed(task, "用户从候选项中确认了法律AI产品。")
            else:
                self._mark_rejected(task, "用户确认的候选项不属于法律AI产品。")
            return self.store.save(task)

        assert payload.confirmed_product_name is not None
        task.canonical_product_name = payload.confirmed_product_name
        task.operator_name = None
        task.product_type = "用户确认的法律AI产品（待公开核验）"
        task.candidates = []
        task.clarification_question = None
        self._mark_confirmed(task, "用户明确确认了确切产品全称；主体与边界留待公开核验。")
        return self.store.save(task)

    def _apply_decision(self, task: Task, decision) -> None:
        if decision.outcome == "clear":
            assert decision.product is not None
            task.canonical_product_name = decision.product.product_name
            task.operator_name = decision.product.operator_name
            task.product_type = decision.product.product_type
            task.related_product_hints = list(decision.product.related_product_hints)
            self._mark_confirmed(task, decision.message)
            return
        if decision.outcome == "rejected":
            assert decision.product is not None
            task.canonical_product_name = decision.product.product_name
            task.operator_name = decision.product.operator_name
            task.product_type = decision.product.product_type
            self._mark_rejected(task, decision.message)
            return
        task.identity_gate = IdentityGate.AWAITING_USER
        task.clarification_question = decision.question
        task.candidates = decision.candidates
        task.status_message = decision.message
        task.next_action = "请确认确切产品；确认前不会研究、扩展生态、成稿或入库。"
        transition(task, TaskStatus.AWAITING_PRODUCT_CONFIRMATION, decision.message)

    @staticmethod
    def _mark_confirmed(task: Task, reason: str) -> None:
        task.identity_gate = IdentityGate.CONFIRMED
        task.status_message = "产品身份闸门已通过。P2.1在正式研究开始前暂停。"
        task.next_action = "进入后续公开研究与范围识别（本阶段未实现）。"
        task.phase_limit_reached = True
        transition(task, TaskStatus.RESEARCHING, reason)

    @staticmethod
    def _mark_rejected(task: Task, reason: str) -> None:
        task.identity_gate = IdentityGate.REJECTED
        task.status_message = "确认对象不属于法律AI产品，未执行后续分析。"
        task.next_action = None
        transition(task, TaskStatus.TERMINATED, reason)
