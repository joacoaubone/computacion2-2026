"""Controladores para los distintos tipos de tarea."""

import asyncio
from time import perf_counter
from collections.abc import Sequence

import httpx


async def download_urls(
    urls: Sequence[str], client: httpx.AsyncClient
) -> list[dict[str, object]]:
    """Descarga URLs en paralelo y conserva en los resultados los errores de cada URL."""
    results: list[dict[str, object] | None] = [None] * len(urls)

    async def download_one(index: int, url: str) -> None:
        started_at = perf_counter()
        try:
            async with client.stream("GET", url) as response:
                content = await response.aread()
                results[index] = {
                    "url": url,
                    "status_code": response.status_code,
                    "size_bytes": len(content),
                    "elapsed_seconds": perf_counter() - started_at,
                }
        except httpx.HTTPError as error:
            results[index] = {
                "url": url,
                "status_code": None,
                "size_bytes": 0,
                "elapsed_seconds": perf_counter() - started_at,
                "error": str(error) or type(error).__name__,
            }

    async with asyncio.TaskGroup() as group:
        for index, url in enumerate(urls):
            group.create_task(download_one(index, url), name=f"download-{index}")

    return [result for result in results if result is not None]
