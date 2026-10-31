"""HTTP routes for submitting and observing tasks."""

from statistics import fmean

from fastapi import APIRouter, FastAPI, HTTPException, Request, status

from .tasks import (
    TaskCapacityError,
    TaskNotFoundError,
    TaskRegistry,
    TaskResponse,
    TaskState,
    TaskSubmission,
)


router = APIRouter()


def _registry(request: Request) -> TaskRegistry:
    return request.app.state.task_registry


@router.post(
    "/tareas",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=TaskResponse,
)
async def submit_task(submission: TaskSubmission, request: Request) -> TaskResponse:
    if not request.app.state.accepting_tasks:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="El servicio está cerrando y no acepta tareas nuevas",
        )
    task_queue = request.app.state.task_queue
    if task_queue.full():
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="La cola está llena; intente enviar la tarea nuevamente más tarde",
        )

    try:
        task = _registry(request).create(
            submission,
            timeout_seconds=request.app.state.settings.task_timeout_seconds,
        )
    except TaskCapacityError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Se alcanzó el límite de tareas retenidas y no hay tareas "
                "terminales para liberar espacio"
            ),
        ) from error

    task_queue.put_nowait(task.id)
    return TaskResponse.from_record(task)


@router.get("/tareas", response_model=list[TaskResponse])
async def list_tasks(
    request: Request,
    estado: TaskState | None = None,
) -> list[TaskResponse]:
    tasks = _registry(request).list(estado)
    return [TaskResponse.from_record(task) for task in tasks]


@router.get("/tareas/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str, request: Request) -> TaskResponse:
    try:
        task = _registry(request).get_or_raise(task_id)
    except TaskNotFoundError as error:
        raise HTTPException(status_code=404, detail="Tarea no encontrada") from error
    return TaskResponse.from_record(task)


@router.delete("/tareas/{task_id}", response_model=TaskResponse)
async def cancel_task(task_id: str, request: Request) -> TaskResponse:
    registry = _registry(request)
    try:
        task = registry.get_or_raise(task_id)
    except TaskNotFoundError as error:
        raise HTTPException(status_code=404, detail="Tarea no encontrada") from error

    if task.status not in {TaskState.PENDING, TaskState.RUNNING}:
        raise HTTPException(
            status_code=409,
            detail={
                "mensaje": "La tarea ya está en un estado terminal",
                "estado": task.status.value,
            },
        )

    if task.status is TaskState.PENDING:
        registry.transition(task.id, TaskState.CANCELLED)
    else:
        if task.execution_task is None:
            raise HTTPException(
                status_code=409,
                detail={
                    "mensaje": "La ejecución activa no está disponible para cancelar",
                    "estado": task.status.value,
                },
            )
        task.execution_task.cancel()
        await task.completion_event.wait()

        if task.status is not TaskState.CANCELLED:
            raise HTTPException(
                status_code=409,
                detail={
                    "mensaje": "La tarea terminó antes de completar la cancelación",
                    "estado": task.status.value,
                },
            )

    return TaskResponse.from_record(task)


@router.get("/estadisticas")
async def get_statistics(request: Request) -> dict[str, object]:
    tasks = _registry(request).list()
    totals = {state.value: 0 for state in TaskState}
    durations: list[float] = []
    for task in tasks:
        totals[task.status.value] += 1
        if task.duration_seconds is not None:
            durations.append(task.duration_seconds)

    return {
        "por_estado": totals,
        "duracion_promedio_segundos": fmean(durations) if durations else None,
        "workers_ocupados": request.app.state.occupied_workers,
    }


def include_api(app: FastAPI) -> None:
    app.include_router(router)
