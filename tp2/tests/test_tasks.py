"""Tests for task request validation and in-memory lifecycle state."""

import pytest
from pydantic import TypeAdapter, ValidationError

from tp2.app.tasks import (
    HashSubmission,
    InvalidTaskTransition,
    TaskKind,
    TaskRegistry,
    TaskState,
    TaskSubmission,
)


submission_adapter = TypeAdapter(TaskSubmission)


@pytest.mark.parametrize(
    ("payload", "expected_kind"),
    [
        (
            {"tipo": "descargar", "urls": ["https://example.com"]},
            TaskKind.DOWNLOAD,
        ),
        (
            {"tipo": "hashear", "texto": "hola", "iteraciones": 3},
            TaskKind.HASH,
        ),
        ({"tipo": "esperar", "segundos": 0}, TaskKind.WAIT),
    ],
)
def test_validates_each_task_kind(payload: dict[str, object], expected_kind: TaskKind) -> None:
    submission = submission_adapter.validate_python(payload)
    registry = TaskRegistry()

    task = registry.create(submission, timeout_seconds=12.0)

    assert task.kind is expected_kind
    assert task.status is TaskState.PENDING
    assert task.timeout_seconds == 12.0


@pytest.mark.parametrize(
    "payload",
    [
        {"tipo": "no-existe"},
        {"tipo": "descargar", "urls": []},
        {"tipo": "hashear", "texto": "hola", "iteraciones": 0},
        {"tipo": "esperar", "segundos": -1},
        {"tipo": "esperar", "segundos": 1, "extra": True},
    ],
)
def test_rejects_invalid_task_payloads(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        submission_adapter.validate_python(payload)


def test_registry_filters_and_tracks_valid_transitions() -> None:
    registry = TaskRegistry()
    submission = HashSubmission(tipo="hashear", texto="hola", iteraciones=2)
    task = registry.create(submission, timeout_seconds=10.0)

    assert registry.get(task.id) is task
    assert registry.list(TaskState.PENDING) == [task]

    registry.transition(task.id, TaskState.RUNNING)
    completed = registry.transition(task.id, TaskState.COMPLETED, result="digest")

    assert completed.result == "digest"
    assert completed.duration_seconds is not None
    assert registry.list(TaskState.COMPLETED) == [task]


def test_registry_rejects_terminal_state_changes() -> None:
    registry = TaskRegistry()
    task = registry.create(
        HashSubmission(tipo="hashear", texto="hola", iteraciones=2),
        timeout_seconds=10.0,
    )
    registry.transition(task.id, TaskState.CANCELLED)

    with pytest.raises(InvalidTaskTransition):
        registry.transition(task.id, TaskState.RUNNING)


def test_failed_task_requires_a_failure_reason() -> None:
    registry = TaskRegistry()
    task = registry.create(
        HashSubmission(tipo="hashear", texto="hola", iteraciones=2),
        timeout_seconds=10.0,
    )
    registry.transition(task.id, TaskState.RUNNING)

    with pytest.raises(ValueError, match="failure_reason is required"):
        registry.transition(task.id, TaskState.FAILED)
