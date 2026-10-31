"""FastAPI application factory and basic lifespan handling."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
import asyncio
from concurrent.futures import ProcessPoolExecutor
import logging

from fastapi import FastAPI
import httpx

from .api import include_api
from .config import get_settings
from .execution import TaskExecutor
from .snapshots import newest_snapshot, write_snapshot
from .tasks import TaskRegistry
from .workers import WorkerPool


logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Load runtime settings on startup and release app state on shutdown."""
    application.state.settings = get_settings()
    application.state.settings.state_dir.mkdir(parents=True, exist_ok=True)
    previous_snapshot = newest_snapshot(application.state.settings.state_dir)
    if previous_snapshot is not None:
        logger.info(
            "Previous task snapshot found at %s; it will not be restored",
            previous_snapshot,
        )
    application.state.task_registry = TaskRegistry(
        max_retained_tasks=application.state.settings.max_retained_tasks
    )
    application.state.task_queue = asyncio.Queue(
        maxsize=application.state.settings.max_retained_tasks
    )
    application.state.process_pool = ProcessPoolExecutor(
        max_workers=application.state.settings.process_pool_workers
    )
    application.state.occupied_workers = 0
    application.state.http_client = httpx.AsyncClient(
        transport=application.state.http_transport
    )
    application.state.task_executor = TaskExecutor(
        application.state.http_client,
        application.state.process_pool,
        application.state.settings.hash_batch_iterations,
    )
    application.state.worker_pool = WorkerPool(
        queue=application.state.task_queue,
        registry=application.state.task_registry,
        processor=application.state.task_executor,
        worker_count=application.state.settings.worker_count,
        on_worker_count_changed=lambda count: setattr(
            application.state, "occupied_workers", count
        ),
    )
    application.state.accepting_tasks = True
    application.state.runtime_started = True
    try:
        if application.state.start_workers:
            await application.state.worker_pool.start()
        yield
    finally:
        application.state.accepting_tasks = False
        application.state.runtime_started = False
        try:
            if application.state.worker_pool.running:
                try:
                    await asyncio.wait_for(
                        application.state.task_queue.join(),
                        timeout=application.state.settings.shutdown_timeout_seconds,
                    )
                except TimeoutError:
                    logger.warning(
                        "Shutdown grace period expired after %.3f seconds; "
                        "cancelling active tasks",
                        application.state.settings.shutdown_timeout_seconds,
                    )
            await application.state.worker_pool.close()
            try:
                snapshot_path = await asyncio.to_thread(
                    write_snapshot,
                    application.state.task_registry,
                    application.state.settings.state_dir,
                )
                logger.info("Task state snapshot written to %s", snapshot_path)
            except Exception:
                logger.exception("Failed to write task state snapshot")
        finally:
            await application.state.http_client.aclose()
            await asyncio.to_thread(
                application.state.process_pool.shutdown,
                wait=True,
                cancel_futures=True,
            )


def create_app(
    *,
    start_workers: bool = True,
    http_transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    """Create the API application without starting runtime resources."""
    application = FastAPI(
        title="Plataforma de Tareas Distribuidas",
        lifespan=lifespan,
    )
    application.state.start_workers = start_workers
    application.state.http_transport = http_transport
    include_api(application)
    return application


app = create_app()
