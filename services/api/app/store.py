from __future__ import annotations

from threading import RLock

from .models import Task


class InMemoryTaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._lock = RLock()

    def add(self, task: Task) -> Task:
        with self._lock:
            self._tasks[task.task_id] = task
            return task.model_copy(deep=True)

    def get(self, task_id: str) -> Task | None:
        with self._lock:
            task = self._tasks.get(task_id)
            return task.model_copy(deep=True) if task else None

    def save(self, task: Task) -> Task:
        with self._lock:
            self._tasks[task.task_id] = task
            return task.model_copy(deep=True)

    def list(self) -> list[Task]:
        with self._lock:
            tasks = sorted(self._tasks.values(), key=lambda item: item.created_at, reverse=True)
            return [task.model_copy(deep=True) for task in tasks]

    def clear(self) -> None:
        with self._lock:
            self._tasks.clear()
