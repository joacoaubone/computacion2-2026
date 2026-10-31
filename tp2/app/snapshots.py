"""Atomic JSON snapshots of task state for orderly service shutdown."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from .tasks import TaskRegistry, TaskResponse


SNAPSHOT_PREFIX = "estado_"


def newest_snapshot(state_dir: Path) -> Path | None:
    """Return the newest prior task snapshot, if one exists."""
    snapshots = list(state_dir.glob(f"{SNAPSHOT_PREFIX}*.json"))
    if not snapshots:
        return None
    return max(snapshots, key=lambda path: path.stat().st_mtime_ns)


def write_snapshot(registry: TaskRegistry, state_dir: Path) -> Path:
    """Atomically write all current task records to a timestamped JSON file."""
    state_dir.mkdir(parents=True, exist_ok=True)
    saved_at = datetime.now(timezone.utc)
    timestamp = saved_at.strftime("%Y%m%dT%H%M%S%fZ")
    snapshot_path = state_dir / f"{SNAPSHOT_PREFIX}{timestamp}.json"
    temporary_path = state_dir / f".{snapshot_path.name}.tmp"
    payload = {
        "guardado_en": saved_at.isoformat(),
        "tareas": [
            TaskResponse.from_record(task).model_dump(mode="json")
            for task in registry.list()
        ],
    }

    try:
        with temporary_path.open("w", encoding="utf-8") as snapshot_file:
            json.dump(payload, snapshot_file, ensure_ascii=False, indent=2)
            snapshot_file.write("\n")
        os.replace(temporary_path, snapshot_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return snapshot_path
