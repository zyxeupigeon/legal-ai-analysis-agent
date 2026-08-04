from __future__ import annotations

from datetime import UTC, datetime

from .models import Task, TaskEvent, TaskStatus


ALLOWED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.UNIDENTIFIED: {
        TaskStatus.AWAITING_PRODUCT_CONFIRMATION,
        TaskStatus.RESEARCHING,
        TaskStatus.TERMINATED,
    },
    TaskStatus.AWAITING_PRODUCT_CONFIRMATION: {
        TaskStatus.RESEARCHING,
        TaskStatus.TERMINATED,
    },
    TaskStatus.RESEARCHING: set(),
    TaskStatus.TERMINATED: set(),
}


class InvalidTransition(ValueError):
    pass


def transition(task: Task, target: TaskStatus, reason: str) -> None:
    current = TaskStatus(task.task_status)
    if target not in ALLOWED_TRANSITIONS[current]:
        raise InvalidTransition(f"不允许从“{current.value}”转为“{target.value}”")
    now = datetime.now(UTC)
    task.events.append(
        TaskEvent(
            event_type="task_status_changed",
            from_status=current,
            to_status=target,
            reason=reason,
            occurred_at=now,
        )
    )
    task.task_status = target
    task.updated_at = now
