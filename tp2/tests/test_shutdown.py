"""Tests for lifespan shutdown, task snapshots, and previous-snapshot logging."""

import asyncio
import json
import logging
from pathlib import Path

import pytest

from tp2.app.application import create_app
from tp2.app.tasks import TaskState, WaitSubmission


@pytest.mark.asyncio
async def test_shutdown_drains_queue_and_logs_previous_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    previous = state_dir / "estado_20261029T120000000000Z.json"
    previous.write_text('{"tareas": []}\n', encoding="utf-8")
    monkeypatch.setenv("TP2_STATE_DIR", str(state_dir))
    monkeypatch.setenv("TP2_SHUTDOWN_TIMEOUT_SECONDS", "1")

    application = create_app()
    with caplog.at_level(logging.INFO):
        async with application.router.lifespan_context(application):
            assert application.state.task_registry.list() == []
            first = application.state.task_registry.create(
                WaitSubmission(tipo="esperar", segundos=0.02), timeout_seconds=1
            )
            second = application.state.task_registry.create(
                WaitSubmission(tipo="esperar", segundos=0.02), timeout_seconds=1
            )
            application.state.task_queue.put_nowait(first.id)
            application.state.task_queue.put_nowait(second.id)

    assert f"{previous}" in caplog.text
    assert first.status is TaskState.COMPLETED
    assert second.status is TaskState.COMPLETED
    snapshots = list(state_dir.glob("estado_*.json"))
    assert len(snapshots) == 2
    assert all(path.stat().st_size > 0 for path in snapshots)
    assert not list(state_dir.glob("*.tmp"))

    saved = json.loads(max(snapshots, key=lambda path: path.stat().st_mtime_ns).read_text())
    assert [task["estado"] for task in saved["tareas"]] == [
        TaskState.COMPLETED.value,
        TaskState.COMPLETED.value,
    ]


@pytest.mark.asyncio
async def test_shutdown_deadline_cancels_active_and_snapshots_pending(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_dir = tmp_path / "state"
    monkeypatch.setenv("TP2_STATE_DIR", str(state_dir))
    monkeypatch.setenv("TP2_SHUTDOWN_TIMEOUT_SECONDS", "0.02")
    monkeypatch.setenv("TP2_WORKERS", "1")

    application = create_app()
    async with application.router.lifespan_context(application):
        active = application.state.task_registry.create(
            WaitSubmission(tipo="esperar", segundos=60), timeout_seconds=90
        )
        pending = application.state.task_registry.create(
            WaitSubmission(tipo="esperar", segundos=60), timeout_seconds=90
        )
        application.state.task_queue.put_nowait(active.id)
        application.state.task_queue.put_nowait(pending.id)

        for _ in range(100):
            if active.status is TaskState.RUNNING:
                break
            await asyncio.sleep(0.001)
        assert active.status is TaskState.RUNNING

    assert active.status is TaskState.CANCELLED
    assert pending.status is TaskState.PENDING
    snapshots = list(state_dir.glob("estado_*.json"))
    assert len(snapshots) == 1
    saved = json.loads(snapshots[0].read_text(encoding="utf-8"))
    assert [task["estado"] for task in saved["tareas"]] == [
        TaskState.CANCELLED.value,
        TaskState.PENDING.value,
    ]
