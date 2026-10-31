"""HTTP contract tests for task submission and inspection."""

import asyncio
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
import pytest
import httpx
from httpx import ASGITransport, AsyncClient

from tp2.app.application import create_app
from tp2.app.tasks import HashSubmission, TaskState, WaitSubmission


class HoldingStream(httpx.AsyncByteStream):
    def __init__(self, transport: "CancellationAwareTransport") -> None:
        self.transport = transport
        self.closed = False

    async def __aiter__(self):
        await self.transport.release_requests.wait()
        yield b"payload"

    async def aclose(self) -> None:
        if not self.closed:
            self.closed = True
            self.transport.closed_responses += 1
            self.transport.active_responses -= 1


class CancellationAwareTransport(httpx.AsyncBaseTransport):
    def __init__(self, expected_requests: int) -> None:
        self.expected_requests = expected_requests
        self.started_requests = 0
        self.active_responses = 0
        self.closed_responses = 0
        self.all_started = asyncio.Event()
        self.release_requests = asyncio.Event()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.started_requests += 1
        self.active_responses += 1
        if self.started_requests == self.expected_requests:
            self.all_started.set()
        return httpx.Response(
            status_code=200,
            stream=HoldingStream(self),
            request=request,
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"tipo": "descargar", "urls": ["https://example.com"]},
        {"tipo": "hashear", "texto": "hola", "iteraciones": 5},
        {"tipo": "esperar", "segundos": 0.01},
    ],
)
def test_post_accepts_task_and_returns_pending(payload: dict[str, object]) -> None:
    with TestClient(create_app(start_workers=False)) as client:
        response = client.post("/tareas", json=payload)

        assert response.status_code == 202
        body = response.json()
        assert body["id"]
        assert body["estado"] == TaskState.PENDING.value
        assert client.app.state.task_queue.qsize() == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"tipo": "otra", "algo": 1},
        {"tipo": "hashear", "texto": "falta iteraciones"},
    ],
)
def test_post_rejects_invalid_task_without_queueing(
    payload: dict[str, object],
) -> None:
    with TestClient(create_app(start_workers=False)) as client:
        response = client.post("/tareas", json=payload)

        assert response.status_code == 422
        assert client.app.state.task_queue.qsize() == 0


def test_post_rejects_new_tasks_after_shutdown_admission_closes() -> None:
    with TestClient(create_app(start_workers=False)) as client:
        client.app.state.accepting_tasks = False

        response = client.post(
            "/tareas", json={"tipo": "esperar", "segundos": 1}
        )

        assert response.status_code == 503
        assert client.app.state.task_registry.list() == []
        assert client.app.state.task_queue.qsize() == 0


def test_list_filters_and_get_returns_task_result() -> None:
    with TestClient(create_app(start_workers=False)) as client:
        first = client.post(
            "/tareas", json={"tipo": "esperar", "segundos": 1}
        ).json()
        second = client.post(
            "/tareas", json={"tipo": "hashear", "texto": "x", "iteraciones": 1}
        ).json()

        pending = client.get("/tareas", params={"estado": "pendiente"})
        assert pending.status_code == 200
        assert {task["id"] for task in pending.json()} == {
            first["id"],
            second["id"],
        }

        registry = client.app.state.task_registry
        registry.transition(second["id"], TaskState.RUNNING)
        registry.transition(second["id"], TaskState.COMPLETED, result="digest")

        completed = client.get("/tareas", params={"estado": "completada"})
        assert [task["id"] for task in completed.json()] == [second["id"]]

        detail = client.get(f"/tareas/{second['id']}")
        assert detail.status_code == 200
        assert detail.json()["resultado"] == "digest"

        assert client.get("/tareas/no-existe").status_code == 404
        assert client.get("/tareas", params={"estado": "no-existe"}).status_code == 422


def test_delete_cancels_queued_task_and_rejects_terminal_task() -> None:
    with TestClient(create_app(start_workers=False)) as client:
        created = client.post(
            "/tareas", json={"tipo": "esperar", "segundos": 5}
        ).json()

        cancelled = client.delete(f"/tareas/{created['id']}")
        assert cancelled.status_code == 200
        assert cancelled.json()["estado"] == TaskState.CANCELLED.value

        conflict = client.delete(f"/tareas/{created['id']}")
        assert conflict.status_code == 409
        assert conflict.json()["detail"]["estado"] == TaskState.CANCELLED.value

        assert client.delete("/tareas/no-existe").status_code == 404


@pytest.mark.parametrize(
    ("terminal_state", "failure_reason"),
    [
        (TaskState.COMPLETED, None),
        (TaskState.FAILED, "timeout after 0.01 seconds"),
    ],
)
def test_delete_returns_conflict_when_completion_or_timeout_wins(
    terminal_state: TaskState,
    failure_reason: str | None,
) -> None:
    with TestClient(create_app(start_workers=False)) as client:
        created = client.post(
            "/tareas", json={"tipo": "esperar", "segundos": 1}
        ).json()
        registry = client.app.state.task_registry
        registry.transition(created["id"], TaskState.RUNNING)
        if terminal_state is TaskState.COMPLETED:
            registry.transition(created["id"], terminal_state, result="finished")
        else:
            registry.transition(
                created["id"], terminal_state, failure_reason=failure_reason
            )

        response = client.delete(f"/tareas/{created['id']}")

        assert response.status_code == 409
        assert response.json()["detail"]["estado"] == terminal_state.value
        assert registry.get_or_raise(created["id"]).status is terminal_state


@pytest.mark.asyncio
async def test_delete_running_task_waits_for_cancellation_cleanup() -> None:
    application = create_app(start_workers=False)
    async with application.router.lifespan_context(application):
        registry = application.state.task_registry
        task = registry.create(
            WaitSubmission(tipo="esperar", segundos=60), timeout_seconds=90
        )
        registry.transition(task.id, TaskState.RUNNING)

        async def run_until_cancelled() -> None:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                await asyncio.sleep(0.01)
                registry.transition(task.id, TaskState.CANCELLED)
                raise

        task.execution_task = asyncio.create_task(run_until_cancelled())
        await asyncio.sleep(0)

        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete(f"/tareas/{task.id}")

        assert response.status_code == 200
        assert response.json()["estado"] == TaskState.CANCELLED.value
        with pytest.raises(asyncio.CancelledError):
            await task.execution_task


@pytest.mark.asyncio
async def test_wait_task_runs_and_delete_keeps_worker_available() -> None:
    application = create_app()
    async with application.router.lifespan_context(application):
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/tareas", json={"tipo": "esperar", "segundos": 60}
            )
            task_id = created.json()["id"]

            await asyncio.sleep(0.01)
            executing = await client.get(f"/tareas/{task_id}")
            assert executing.json()["estado"] == TaskState.RUNNING.value

            cancelled = await client.delete(f"/tareas/{task_id}")
            assert cancelled.status_code == 200
            assert cancelled.json()["estado"] == TaskState.CANCELLED.value

            next_task = await client.post(
                "/tareas", json={"tipo": "esperar", "segundos": 0}
            )
            next_id = next_task.json()["id"]
            await application.state.task_queue.join()

            completed = await client.get(f"/tareas/{next_id}")
            assert completed.json()["estado"] == TaskState.COMPLETED.value
            assert completed.json()["resultado"] == {"segundos": 0.0}


@pytest.mark.asyncio
async def test_delete_download_waits_until_all_response_streams_close() -> None:
    transport_impl = CancellationAwareTransport(expected_requests=3)
    application = create_app(http_transport=transport_impl)
    async with application.router.lifespan_context(application):
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/tareas",
                json={
                    "tipo": "descargar",
                    "urls": [
                        "https://test.local/one",
                        "https://test.local/two",
                        "https://test.local/three",
                    ],
                },
            )
            task_id = created.json()["id"]
            await asyncio.wait_for(transport_impl.all_started.wait(), timeout=1)

            cancelled = await client.delete(f"/tareas/{task_id}")

        task = application.state.task_registry.get_or_raise(task_id)
        assert cancelled.status_code == 200
        assert cancelled.json()["estado"] == TaskState.CANCELLED.value
        assert transport_impl.closed_responses == 3
        assert transport_impl.active_responses == 0
        assert task.execution_task is None
        assert not any(
            not running.done() and running.get_name().startswith("download-")
            for running in asyncio.all_tasks()
        )


def test_statistics_include_state_totals_duration_average_and_busy_workers() -> None:
    with TestClient(create_app(start_workers=False)) as client:
        registry = client.app.state.task_registry
        completed = registry.create(
            HashSubmission(tipo="hashear", texto="x", iteraciones=1),
            timeout_seconds=10,
        )
        registry.transition(completed.id, TaskState.RUNNING)
        registry.transition(completed.id, TaskState.COMPLETED, result="digest")
        completed.started_at = datetime.now(timezone.utc) - timedelta(seconds=2)

        failed = registry.create(
            HashSubmission(tipo="hashear", texto="y", iteraciones=1),
            timeout_seconds=10,
        )
        registry.transition(failed.id, TaskState.RUNNING)
        registry.transition(
            failed.id, TaskState.FAILED, failure_reason="test failure"
        )
        failed.started_at = datetime.now(timezone.utc) - timedelta(seconds=4)

        registry.create(
            WaitSubmission(tipo="esperar", segundos=1), timeout_seconds=10
        )
        running = registry.create(
            WaitSubmission(tipo="esperar", segundos=1), timeout_seconds=10
        )
        registry.transition(running.id, TaskState.RUNNING)
        registry.create(
            WaitSubmission(tipo="esperar", segundos=1), timeout_seconds=10
        )
        client.app.state.occupied_workers = 1

        response = client.get("/estadisticas")

        assert response.status_code == 200
        statistics = response.json()
        assert statistics["por_estado"] == {
            "pendiente": 2,
            "ejecutando": 1,
            "completada": 1,
            "fallida": 1,
            "cancelada": 0,
        }
        assert statistics["duracion_promedio_segundos"] == pytest.approx(3, abs=0.1)
        assert statistics["workers_ocupados"] == 1
