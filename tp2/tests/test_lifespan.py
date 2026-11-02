"""Pruebas básicas de inicio y apagado de la aplicación."""

import asyncio
import subprocess
import sys

import pytest

from tp2.app.application import create_app


@pytest.mark.asyncio
async def test_lifespan_starts_and_stops_application() -> None:
    application = create_app()

    async with application.router.lifespan_context(application):
        assert application.state.runtime_started is True
        assert application.state.settings.worker_count > 0
        assert application.state.task_queue is not None
        assert application.state.worker_pool.running
        assert application.state.worker_pool.worker_count == (
            application.state.settings.worker_count
        )
        assert application.state.process_pool._max_workers == (
            application.state.settings.process_pool_workers
        )

    assert application.state.runtime_started is False
    assert not application.state.worker_pool.running


def test_application_import_does_not_spawn_child_processes() -> None:
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import multiprocessing; "
            "from tp2.app.application import app; "
            "assert multiprocessing.active_children() == []",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
