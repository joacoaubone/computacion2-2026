"""Central configuration for the TP2 service.

Settings are read when ``get_settings`` is called so importing this module does
not start workers, create executors, or otherwise spawn child processes.
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
        raise ValueError(f"{name} must be a positive integer") from error

    if value < 1:
        raise ValueError(f"{name} must be a positive integer")
    return value


def _positive_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        value = float(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} must be a positive number") from error

    if value <= 0:
        raise ValueError(f"{name} must be a positive number")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings shared by the API and task execution service."""

    worker_count: int = 4
    process_pool_workers: int = 2
    task_timeout_seconds: float = 60.0
    shutdown_timeout_seconds: float = 10.0
    hash_batch_iterations: int = 10_000
    state_dir: Path = Path("data")

    @classmethod
    def from_env(cls) -> "Settings":
        """Build settings from TP2 environment variables and safe defaults."""
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
            state_dir=Path(os.getenv("TP2_STATE_DIR", str(defaults.state_dir))),
        )


def get_settings() -> Settings:
    """Return settings for the current process environment."""
    return Settings.from_env()
