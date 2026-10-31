"""Tests for worker concurrency and failure isolation."""

import asyncio

import pytest

from tp2.app.tasks import HashSubmission, TaskRegistry, TaskState
from tp2.app.workers import WorkerPool


def make_task(registry: TaskRegistry, text: str = "work"):
    return registry.create(
        HashSubmission(tipo="hashear", texto=text, iteraciones=1),
        timeout_seconds=5,
    )


@pytest.mark.asyncio
async def test_worker_pool_respects_configured_concurrency() -> None:
    queue: asyncio.Queue[str] = asyncio.Queue()
    registry = TaskRegistry()
    tasks = [make_task(registry) for _ in range(5)]
    active = 0
    maximum_active = 0

    async def processor(_task):
        nonlocal active, maximum_active
        active += 1
        maximum_active = max(maximum_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return "done"

    pool = WorkerPool(queue, registry, processor, worker_count=2)
    await pool.start()
    for task in tasks:
        queue.put_nowait(task.id)
    await queue.join()
    await pool.close()

    assert maximum_active == 2
    assert pool.occupied_workers == 0
    assert all(task.status is TaskState.COMPLETED for task in tasks)
    assert all(task.result == "done" for task in tasks)


@pytest.mark.asyncio
async def test_worker_failure_does_not_stop_later_tasks() -> None:
    queue: asyncio.Queue[str] = asyncio.Queue()
    registry = TaskRegistry()
    broken = make_task(registry, "broken")
    following = make_task(registry, "following")

    async def processor(task):
        if task.parameters["texto"] == "broken":
            raise RuntimeError("processor failed")
        return "recovered"

    pool = WorkerPool(queue, registry, processor, worker_count=1)
    await pool.start()
    queue.put_nowait(broken.id)
    queue.put_nowait(following.id)
    await queue.join()
    await pool.close()

    assert broken.status is TaskState.FAILED
    assert broken.failure_reason == "processor failed"
    assert following.status is TaskState.COMPLETED
    assert following.result == "recovered"


@pytest.mark.asyncio
async def test_cancelled_execution_does_not_kill_worker() -> None:
    queue: asyncio.Queue[str] = asyncio.Queue()
    registry = TaskRegistry()
    cancelled = make_task(registry, "cancelled")
    following = make_task(registry, "following")
    started = asyncio.Event()

    async def processor(task):
        if task.id == cancelled.id:
            started.set()
            await asyncio.Event().wait()
        return "done"

    pool = WorkerPool(queue, registry, processor, worker_count=1)
    await pool.start()
    queue.put_nowait(cancelled.id)
    await started.wait()
    assert cancelled.execution_task is not None
    cancelled.execution_task.cancel()
    await cancelled.completion_event.wait()
    queue.put_nowait(following.id)
    await queue.join()
    await pool.close()

    assert cancelled.status is TaskState.CANCELLED
    assert cancelled.completion_event.is_set()
    assert cancelled.execution_task is None
    assert following.status is TaskState.COMPLETED
    assert not any(
        task.get_name().startswith("task-execution-")
        for task in asyncio.all_tasks()
    )


@pytest.mark.asyncio
async def test_timeout_marks_task_failed_and_worker_processes_next_task() -> None:
    queue: asyncio.Queue[str] = asyncio.Queue()
    registry = TaskRegistry()
    timed_out = registry.create(
        HashSubmission(tipo="hashear", texto="timeout", iteraciones=1),
        timeout_seconds=0.01,
    )
    following = registry.create(
        HashSubmission(tipo="hashear", texto="following", iteraciones=1),
        timeout_seconds=1,
    )

    async def processor(task):
        if task.id == timed_out.id:
            await asyncio.Event().wait()
        return "done"

    pool = WorkerPool(queue, registry, processor, worker_count=1)
    await pool.start()
    queue.put_nowait(timed_out.id)
    queue.put_nowait(following.id)
    await queue.join()
    await pool.close()

    assert timed_out.status is TaskState.FAILED
    assert "timeout" in (timed_out.failure_reason or "")
    assert timed_out.completion_event.is_set()
    assert timed_out.execution_task is None
    assert following.status is TaskState.COMPLETED
    assert not any(
        task.get_name().startswith("task-execution-")
        for task in asyncio.all_tasks()
    )
