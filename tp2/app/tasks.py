"""Task request models, lifecycle state, and in-memory task registry."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field


class TaskKind(StrEnum):
    DOWNLOAD = "descargar"
    HASH = "hashear"
    WAIT = "esperar"


class TaskState(StrEnum):
    PENDING = "pendiente"
    RUNNING = "ejecutando"
    COMPLETED = "completada"
    FAILED = "fallida"
    CANCELLED = "cancelada"


class _TaskSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DownloadSubmission(_TaskSubmission):
    tipo: Literal["descargar"]
    urls: list[AnyHttpUrl] = Field(min_length=1)


class HashSubmission(_TaskSubmission):
    tipo: Literal["hashear"]
    texto: str
    iteraciones: int = Field(gt=0)


class WaitSubmission(_TaskSubmission):
    tipo: Literal["esperar"]
    segundos: float = Field(ge=0)


TaskSubmission = Annotated[
    DownloadSubmission | HashSubmission | WaitSubmission,
    Field(discriminator="tipo"),
]


class TaskResponse(BaseModel):
    """Public representation of a task record returned by the HTTP API."""

    id: str
    tipo: TaskKind
    estado: TaskState
    creado_en: datetime
    iniciado_en: datetime | None
    terminado_en: datetime | None
    duracion_segundos: float | None
    resultado: Any = None
    error: str | None = None

    @classmethod
    def from_record(cls, task: "TaskRecord") -> "TaskResponse":
        return cls(
            id=task.id,
            tipo=task.kind,
            estado=task.status,
            creado_en=task.created_at,
            iniciado_en=task.started_at,
            terminado_en=task.finished_at,
            duracion_segundos=task.duration_seconds,
            resultado=task.result,
            error=task.failure_reason,
        )


class TaskNotFoundError(LookupError):
    """Raised when a task identifier is not present in the registry."""


class InvalidTaskTransition(ValueError):
    """Raised when a task is moved to a state it cannot enter."""


class TaskCapacityError(RuntimeError):
    """Raised when no retained task can be evicted to accept a new task."""


_ALLOWED_TRANSITIONS: dict[TaskState, frozenset[TaskState]] = {
    TaskState.PENDING: frozenset({TaskState.RUNNING, TaskState.CANCELLED}),
    TaskState.RUNNING: frozenset(
        {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED}
    ),
    TaskState.COMPLETED: frozenset(),
    TaskState.FAILED: frozenset(),
    TaskState.CANCELLED: frozenset(),
}

_TERMINAL_STATES = frozenset(
    {
        TaskState.COMPLETED,
        TaskState.FAILED,
        TaskState.CANCELLED,
    }
)


@dataclass(slots=True)
class TaskRecord:
    """Mutable in-memory record for one submitted task."""

    id: str
    kind: TaskKind
    parameters: dict[str, Any]
    timeout_seconds: float
    status: TaskState = TaskState.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: Any = None
    failure_reason: str | None = None
    execution_task: asyncio.Task[Any] | None = field(
        default=None, repr=False, compare=False
    )
    completion_event: asyncio.Event = field(
        default_factory=asyncio.Event, repr=False, compare=False
    )

    @property
    def duration_seconds(self) -> float | None:
        """Return elapsed execution time once a task has started and finished."""
        if self.started_at is None or self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds()


class TaskRegistry:
    """Store a bounded task history and enforce allowed state transitions."""

    def __init__(self, max_retained_tasks: int = 1_000) -> None:
        if max_retained_tasks < 1:
            raise ValueError("max_retained_tasks must be positive")
        self._tasks: dict[str, TaskRecord] = {}
        self.max_retained_tasks = max_retained_tasks

    def create(
        self, submission: TaskSubmission, timeout_seconds: float
    ) -> TaskRecord:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._make_room()

        if isinstance(submission, DownloadSubmission):
            kind = TaskKind.DOWNLOAD
            parameters = {"urls": [str(url) for url in submission.urls]}
        elif isinstance(submission, HashSubmission):
            kind = TaskKind.HASH
            parameters = {
                "texto": submission.texto,
                "iteraciones": submission.iteraciones,
            }
        else:
            kind = TaskKind.WAIT
            parameters = {"segundos": submission.segundos}

        task = TaskRecord(
            id=str(uuid4()),
            kind=kind,
            parameters=parameters,
            timeout_seconds=timeout_seconds,
        )
        self._tasks[task.id] = task
        return task

    def _make_room(self) -> None:
        """Evict the oldest terminal record, or reject when all slots are live."""
        if len(self._tasks) < self.max_retained_tasks:
            return

        oldest_terminal = next(
            (
                task
                for task in self._tasks.values()
                if task.status in _TERMINAL_STATES
            ),
            None,
        )
        if oldest_terminal is None:
            raise TaskCapacityError("All retained task slots are in use")
        del self._tasks[oldest_terminal.id]

    def get(self, task_id: str) -> TaskRecord | None:
        return self._tasks.get(task_id)

    def get_or_raise(self, task_id: str) -> TaskRecord:
        task = self.get(task_id)
        if task is None:
            raise TaskNotFoundError(task_id)
        return task

    def list(self, status: TaskState | None = None) -> list[TaskRecord]:
        tasks = self._tasks.values()
        if status is not None:
            tasks = (task for task in tasks if task.status == status)
        return sorted(tasks, key=lambda task: task.created_at)

    def transition(
        self,
        task_id: str,
        new_state: TaskState,
        *,
        result: Any = None,
        failure_reason: str | None = None,
    ) -> TaskRecord:
        task = self.get_or_raise(task_id)
        if new_state not in _ALLOWED_TRANSITIONS[task.status]:
            raise InvalidTaskTransition(
                f"Cannot transition task from {task.status.value} "
                f"to {new_state.value}"
            )
        if new_state is TaskState.FAILED and not failure_reason:
            raise ValueError("failure_reason is required for a failed task")

        now = datetime.now(timezone.utc)
        task.status = new_state
        if new_state is TaskState.RUNNING:
            task.started_at = now
        elif new_state in {
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.CANCELLED,
        }:
            task.finished_at = now
            task.completion_event.set()

        if new_state is TaskState.COMPLETED:
            task.result = result
        elif new_state is TaskState.FAILED:
            task.failure_reason = failure_reason
        return task
