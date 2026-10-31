"""Tests for CPU-bound task execution and cooperative cancellation."""

import asyncio
from concurrent.futures import ProcessPoolExecutor
import hashlib

import httpx
import pytest

from tp2.app.execution import TaskExecutor
from tp2.app.tasks import HashSubmission, TaskRegistry


@pytest.mark.asyncio
async def test_hash_task_applies_sha256_exactly_the_requested_iterations() -> None:
    text = "hash me"
    iterations = 37
    expected = text.encode("utf-8")
    for _ in range(iterations):
        expected = hashlib.sha256(expected).digest()

    async with httpx.AsyncClient() as client:
        with ProcessPoolExecutor(max_workers=1) as process_pool:
            executor = TaskExecutor(client, process_pool, hash_batch_iterations=8)
            task = TaskRegistry().create(
                HashSubmission(
                    tipo="hashear", texto=text, iteraciones=iterations
                ),
                timeout_seconds=5,
            )
            result = await executor(task)

    assert result == expected.hex()


@pytest.mark.asyncio
async def test_hash_cancellation_waits_for_current_batch_and_submits_no_more(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = asyncio.Event()
    release_batch = asyncio.Event()
    submitted_batches: list[int] = []

    async def delayed_batch(
        _executor: TaskExecutor, digest: bytes, iterations: int
    ) -> bytes:
        submitted_batches.append(iterations)
        started.set()
        await release_batch.wait()
        return hashlib.sha256(digest).digest()

    monkeypatch.setattr(TaskExecutor, "_run_hash_batch", delayed_batch)

    async with httpx.AsyncClient() as client:
        with ProcessPoolExecutor(max_workers=1) as process_pool:
            executor = TaskExecutor(client, process_pool, hash_batch_iterations=2)
            hashing = asyncio.create_task(executor.hash_text("cancel me", 20))
            await started.wait()
            hashing.cancel()
            release_batch.set()
            with pytest.raises(asyncio.CancelledError):
                await hashing

    assert submitted_batches == [2]
