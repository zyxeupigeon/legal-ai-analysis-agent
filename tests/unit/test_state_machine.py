from datetime import UTC, datetime

import pytest

from services.api.app.models import IdentityGate, Task, TaskStatus
from services.api.app.state_machine import InvalidTransition, transition


def make_task(status: TaskStatus) -> Task:
    now = datetime.now(UTC)
    return Task(
        task_id="test-task",
        submitted_product_name="测试产品",
        task_status=status,
        identity_gate=IdentityGate.UNREVIEWED,
        status_message="测试",
        created_at=now,
        updated_at=now,
    )


def test_valid_transition_records_event() -> None:
    task = make_task(TaskStatus.UNIDENTIFIED)
    transition(task, TaskStatus.AWAITING_PRODUCT_CONFIRMATION, "名称不明确")
    assert task.task_status == TaskStatus.AWAITING_PRODUCT_CONFIRMATION
    assert len(task.events) == 1
    assert task.events[0].reason == "名称不明确"


def test_invalid_transition_is_blocked() -> None:
    task = make_task(TaskStatus.TERMINATED)
    with pytest.raises(InvalidTransition):
        transition(task, TaskStatus.RESEARCHING, "不应恢复")
