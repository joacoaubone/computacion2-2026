"""Pruebas de los controladores asíncronos de tareas."""

import asyncio
import platform
from time import perf_counter
import sys

import httpx
import pytest

from tp2.app.handlers import download_urls


class DelayedTransport(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.active = 0
        self.maximum_active = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.active += 1
        self.maximum_active = max(self.maximum_active, self.active)
        try:
            await asyncio.sleep(0.01)
            if request.url.path == "/failure":
                raise httpx.ConnectError("unavailable", request=request)
            return httpx.Response(200, content=b"payload", request=request)
        finally:
            self.active -= 1


@pytest.mark.asyncio
async def test_download_urls_overlap_and_report_each_response() -> None:
    transport = DelayedTransport()
    urls = [f"https://test.local/{index}" for index in range(5)]
    async with httpx.AsyncClient(transport=transport) as client:
        results = await download_urls(urls, client)

    assert transport.maximum_active == len(urls)
    assert [result["url"] for result in results] == urls
    assert all(result["status_code"] == 200 for result in results)
    assert all(result["size_bytes"] == len(b"payload") for result in results)
    assert all(result["elapsed_seconds"] >= 0 for result in results)


@pytest.mark.asyncio
async def test_download_error_is_returned_without_losing_successful_results() -> None:
    transport = DelayedTransport()
    urls = ["https://test.local/ok", "https://test.local/failure"]
    async with httpx.AsyncClient(transport=transport) as client:
        results = await download_urls(urls, client)

    assert results[0]["status_code"] == 200
    assert results[0]["size_bytes"] == len(b"payload")
    assert results[1]["status_code"] is None
    assert results[1]["size_bytes"] == 0
    assert "error" in results[1]


@pytest.mark.asyncio
async def test_twenty_downloads_concurrent_faster_than_sequential(record_property) -> None:
    urls = [f"https://test.local/{index}" for index in range(20)]

    sequential_transport = DelayedTransport()
    async with httpx.AsyncClient(transport=sequential_transport) as client:
        started_at = perf_counter()
        for url in urls:
            await download_urls([url], client)
        sequential_seconds = perf_counter() - started_at

    concurrent_transport = DelayedTransport()
    async with httpx.AsyncClient(transport=concurrent_transport) as client:
        started_at = perf_counter()
        results = await download_urls(urls, client)
        concurrent_seconds = perf_counter() - started_at

    speedup = sequential_seconds / concurrent_seconds
    record_property("python_version", sys.version.split()[0])
    record_property("platform", platform.platform())
    record_property("sequential_seconds", sequential_seconds)
    record_property("concurrent_seconds", concurrent_seconds)
    record_property("speedup", speedup)

    assert len(results) == 20
    assert sequential_transport.maximum_active == 1
    assert concurrent_transport.maximum_active == 20
    assert speedup > 2, (
        f"expected concurrency speedup >2x, observed {speedup:.2f}x "
        f"(sequential={sequential_seconds:.3f}s, "
        f"concurrent={concurrent_seconds:.3f}s, "
        f"{platform.platform()}, Python {sys.version.split()[0]})"
    )
