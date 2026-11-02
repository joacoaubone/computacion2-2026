"""Deriva los registros de tareas a sus controladores asíncronos."""

import asyncio
from concurrent.futures import ProcessPoolExecutor
import hashlib

import httpx

from .handlers import download_urls
from .tasks import TaskKind, TaskRecord


def _hash_batch(digest: bytes, iterations: int) -> bytes:
    """Aplica SHA-256 repetidamente; se mantiene en el módulo para crear procesos."""
    for _ in range(iterations):
        digest = hashlib.sha256(digest).digest()
    return digest


class TaskExecutor:
    """Ejecuta los tipos de tarea con recursos compartidos gestionados por el ciclo de vida."""

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        process_pool: ProcessPoolExecutor,
        hash_batch_iterations: int,
    ) -> None:
        self.http_client = http_client
        self.process_pool = process_pool
        self.hash_batch_iterations = hash_batch_iterations

    async def __call__(self, task: TaskRecord) -> object:
        if task.kind is TaskKind.DOWNLOAD:
            return await download_urls(task.parameters["urls"], self.http_client)
        if task.kind is TaskKind.WAIT:
            seconds = float(task.parameters["segundos"])
            await asyncio.sleep(seconds)
            return {"segundos": seconds}
        if task.kind is TaskKind.HASH:
            return await self.hash_text(
                str(task.parameters["texto"]), int(task.parameters["iteraciones"])
            )
        raise ValueError(f"Tipo de tarea no compatible: {task.kind}")

    async def hash_text(self, text: str, iterations: int) -> str:
        """Calcula el hash de texto UTF-8 en lotes acotados y devuelve el resumen hexadecimal."""
        digest = text.encode("utf-8")
        remaining = iterations
        while remaining > 0:
            batch_size = min(remaining, self.hash_batch_iterations)
            batch = asyncio.create_task(self._run_hash_batch(digest, batch_size))
            try:
                digest = await asyncio.shield(batch)
            except asyncio.CancelledError:
                # Una llamada en curso al grupo de procesos no puede detenerse a mitad del lote.
                # Espera a que termine este lote acotado antes de propagar la cancelación.
                await batch
                raise
            remaining -= batch_size
        return digest.hex()

    async def _run_hash_batch(self, digest: bytes, iterations: int) -> bytes:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self.process_pool, _hash_batch, digest, iterations
        )
