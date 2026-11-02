"""Configuración central del servicio TP2.

La configuración se lee al llamar a ``get_settings`` para que importar este
módulo no inicie workers, cree ejecutores ni genere procesos secundarios.
"""

from dataclasses import dataclass
import os
from pathlib import Path


def _positive_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} debe ser un entero positivo") from error

    if value < 1:
        raise ValueError(f"{name} debe ser un entero positivo")
    return value


def _positive_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        value = float(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} debe ser un número positivo") from error

    if value <= 0:
        raise ValueError(f"{name} debe ser un número positivo")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    """Configuración de ejecución compartida por la API y el servicio de tareas."""

    worker_count: int = 4
    process_pool_workers: int = 2
    task_timeout_seconds: float = 60.0
    shutdown_timeout_seconds: float = 10.0
    hash_batch_iterations: int = 10_000
    max_retained_tasks: int = 1_000
    state_dir: Path = Path("data")

    @classmethod
    def from_env(cls) -> "Settings":
        """Crea la configuración a partir de variables de entorno y valores seguros."""
        defaults = cls()
        return cls(
            worker_count=_positive_int("TP2_WORKERS", defaults.worker_count),
            process_pool_workers=_positive_int(
                "TP2_PROCESS_POOL_WORKERS", defaults.process_pool_workers
            ),
            task_timeout_seconds=_positive_float(
                "TP2_TASK_TIMEOUT_SECONDS", defaults.task_timeout_seconds
            ),
            shutdown_timeout_seconds=_positive_float(
                "TP2_SHUTDOWN_TIMEOUT_SECONDS", defaults.shutdown_timeout_seconds
            ),
            hash_batch_iterations=_positive_int(
                "TP2_HASH_BATCH_ITERATIONS", defaults.hash_batch_iterations
            ),
            max_retained_tasks=_positive_int(
                "TP2_MAX_RETAINED_TASKS", defaults.max_retained_tasks
            ),
            state_dir=Path(os.getenv("TP2_STATE_DIR", str(defaults.state_dir))),
        )


def get_settings() -> Settings:
    """Devuelve la configuración correspondiente al entorno del proceso actual."""
    return Settings.from_env()
