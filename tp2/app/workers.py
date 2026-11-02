"""Workers de corrutinas configurables que consumen IDs de una cola de asyncio."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from .tasks import TaskRecord, TaskRegistry, TaskState


TaskProcessor = Callable[[TaskRecord], Awaitable[Any]]
WorkerCountChanged = Callable[[int], None]


class WorkerPool:
    """Consume tareas encoladas mediante una cantidad fija de workers independientes."""

    def __init__(
        self,
        queue: asyncio.Queue[str],
        registry: TaskRegistry,
        processor: TaskProcessor,
        worker_count: int,
        on_worker_count_changed: WorkerCountChanged | None = None,
    ) -> None:
        if worker_count < 1:
            raise ValueError("La cantidad de workers debe ser un entero positivo")
        self.queue = queue
        self.registry = registry
        self.processor = processor
        self.worker_count = worker_count
        self.on_worker_count_changed = on_worker_count_changed
        self._workers: list[asyncio.Task[None]] = []
        self._occupied_workers = 0

    @property
    def occupied_workers(self) -> int:
        return self._occupied_workers

    @property
    def running(self) -> bool:
        return bool(self._workers)

    async def start(self) -> None:
        """Inicia las corrutinas worker configuradas una sola vez."""
        if self._workers:
            return
        self._workers = [
            asyncio.create_task(self._consume(), name=f"task-worker-{index + 1}")
            for index in range(self.worker_count)
        ]

    async def close(self) -> None:
        """Cancela y espera a las corrutinas worker, incluida su tarea activa."""
        workers, self._workers = self._workers, []
        for worker in workers:
            worker.cancel()
        if workers:
            await asyncio.gather(*workers, return_exceptions=True)

    async def _consume(self) -> None:
        while True:
            task_id = await self.queue.get()
            try:
                task = self.registry.get(task_id)
                if task is None or task.status is not TaskState.PENDING:
                    continue
                await self._execute(task)
            finally:
                self.queue.task_done()

    async def _execute(self, task: TaskRecord) -> None:
        self.registry.transition(task.id, TaskState.RUNNING)
        self._set_occupied(self._occupied_workers + 1)
        execution = asyncio.create_task(
            self.processor(task), name=f"task-execution-{task.id}"
        )
        task.execution_task = execution

        try:
            result = await asyncio.wait_for(
                asyncio.shield(execution), timeout=task.timeout_seconds
            )
        except TimeoutError:
            execution.cancel()
            await asyncio.gather(execution, return_exceptions=True)
            if task.status is TaskState.RUNNING:
                self.registry.transition(
                    task.id,
                    TaskState.FAILED,
                    failure_reason=(
                        f"Tiempo de espera agotado después de "
                        f"{task.timeout_seconds:g} segundos"
                    ),
                )
        except asyncio.CancelledError:
            worker = asyncio.current_task()
            if worker is not None and worker.cancelling():
                execution.cancel()
                await asyncio.gather(execution, return_exceptions=True)
                if task.status is TaskState.RUNNING:
                    self.registry.transition(task.id, TaskState.CANCELLED)
                raise
            if task.status is TaskState.RUNNING:
                self.registry.transition(task.id, TaskState.CANCELLED)
        except Exception as error:
            if task.status is TaskState.RUNNING:
                self.registry.transition(
                    task.id,
                    TaskState.FAILED,
                    failure_reason=str(error) or type(error).__name__,
                )
        else:
            if task.status is TaskState.RUNNING:
                self.registry.transition(task.id, TaskState.COMPLETED, result=result)
        finally:
            task.execution_task = None
            self._set_occupied(self._occupied_workers - 1)

    def _set_occupied(self, count: int) -> None:
        self._occupied_workers = count
        if self.on_worker_count_changed is not None:
            self.on_worker_count_changed(count)
