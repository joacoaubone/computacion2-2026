"""Ejecuta mediciones locales repetibles para el informe del TP2."""

import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
import platform
import socket
import subprocess
import sys
import time
from pathlib import Path
from statistics import median

import httpx

from tp2.app.handlers import download_urls


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TP2_DIRECTORY = Path(__file__).resolve().parents[1]


def available_port() -> int:
    with socket.socket() as server_socket:
        server_socket.bind(("127.0.0.1", 0))
        return int(server_socket.getsockname()[1])


def wait_until_ready(base_url: str, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("El servidor de benchmark se cerró antes de estar listo")
        try:
            response = httpx.get(f"{base_url}/tareas", timeout=1)
            if response.status_code == 200:
                return
        except httpx.HTTPError:
            time.sleep(0.1)
    raise TimeoutError("El servidor de benchmark no estuvo listo en 30 segundos")


async def measure_downloads(base_url: str, delay_ms: int) -> dict[str, float | int]:
    urls = [
        f"{base_url}/__benchmark/download?delay_ms={delay_ms}&item={index}"
        for index in range(20)
    ]
    async with httpx.AsyncClient(timeout=30) as client:
        started = time.perf_counter()
        for url in urls:
            await download_urls([url], client)
        sequential = time.perf_counter() - started

        started = time.perf_counter()
        results = await download_urls(urls, client)
        concurrent = time.perf_counter() - started

    return {
        "url_count": len(urls),
        "delay_ms_per_url": delay_ms,
        "sequential_seconds": sequential,
        "concurrent_seconds": concurrent,
        "speedup": sequential / concurrent,
        "responses": len(results),
    }


def measure_event_loop_latency(base_url: str, iterations: int) -> dict[str, dict[str, float]]:
    measurements: dict[str, dict[str, float]] = {}
    with ThreadPoolExecutor(max_workers=1) as requests:
        for mode in ("inline", "executor"):
            hash_request = requests.submit(
                httpx.get,
                f"{base_url}/__benchmark/hash",
                params={"mode": mode, "iterations": iterations},
                timeout=60,
            )
            # Permite que Uvicorn reciba la solicitud de hash antes de medir la ruta de la API.
            time.sleep(0.05)
            started = time.perf_counter()
            response = httpx.get(f"{base_url}/tareas", timeout=60)
            latency = time.perf_counter() - started
            response.raise_for_status()
            hash_response = hash_request.result(timeout=60)
            hash_response.raise_for_status()
            measurements[mode] = {
                "get_tareas_latency_seconds": latency,
                "hash_request_seconds": hash_response.elapsed.total_seconds(),
            }
    return measurements


def wait_for_tasks(client: httpx.Client, base_url: str, task_ids: list[str]) -> None:
    pending = set(task_ids)
    deadline = time.monotonic() + 120
    while pending and time.monotonic() < deadline:
        for task_id in tuple(pending):
            response = client.get(f"{base_url}/tareas/{task_id}")
            response.raise_for_status()
            if response.json()["estado"] in {
                "completada",
                "fallida",
                "cancelada",
            }:
                pending.remove(task_id)
        if pending:
            time.sleep(0.01)
    if pending:
        raise TimeoutError(f"Las tareas no finalizaron: {sorted(pending)}")


def measure_pool(base_url: str, iterations: int) -> list[dict[str, object]]:
    measurements: list[dict[str, object]] = []
    with httpx.Client(timeout=10) as client:
        warmup = client.post(
            f"{base_url}/tareas",
            json={
                "tipo": "hashear",
                "texto": "warmup",
                "iteraciones": min(iterations, 100_000),
            },
        )
        warmup.raise_for_status()
        wait_for_tasks(client, base_url, [warmup.json()["id"]])

        for task_count in (1, 2, 4, 8, 16):
            samples: list[float] = []
            for _ in range(3):
                started = time.perf_counter()
                task_ids: list[str] = []
                for _ in range(task_count):
                    response = client.post(
                        f"{base_url}/tareas",
                        json={
                            "tipo": "hashear",
                            "texto": "pool-benchmark",
                            "iteraciones": iterations,
                        },
                    )
                    response.raise_for_status()
                    task_ids.append(response.json()["id"])
                wait_for_tasks(client, base_url, task_ids)
                samples.append(time.perf_counter() - started)
            elapsed = median(samples)
            measurements.append(
                {
                    "task_count": task_count,
                    "iterations_per_task": iterations,
                    "median_elapsed_seconds": elapsed,
                    "samples_seconds": samples,
                    "tasks_per_second": task_count / elapsed,
                }
            )
    return measurements


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delay-ms", type=int, default=20)
    parser.add_argument("--hash-iterations", type=int, default=750_000)
    parser.add_argument("--pool-iterations", type=int, default=500_000)
    args = parser.parse_args()

    port = available_port()
    base_url = f"http://127.0.0.1:{port}"
    environment = os.environ.copy()
    environment["TP2_STATE_DIR"] = str(TP2_DIRECTORY / "data")
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "tp2.benchmarks.server:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=REPOSITORY_ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_until_ready(base_url, server)
        result = {
            "environment": {
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "worker_count": os.getenv("TP2_WORKERS", "4"),
                "process_pool_workers": os.getenv("TP2_PROCESS_POOL_WORKERS", "2"),
            },
            "io_20_downloads": asyncio.run(measure_downloads(base_url, args.delay_ms)),
            "event_loop_latency": measure_event_loop_latency(
                base_url, args.hash_iterations
            ),
            "pool_throughput": measure_pool(base_url, args.pool_iterations),
        }
        print(json.dumps(result, indent=2))
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=10)


if __name__ == "__main__":
    main()
