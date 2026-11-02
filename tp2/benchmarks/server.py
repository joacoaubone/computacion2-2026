"""Endpoints ASGI locales utilizados por ``measurements.py``."""

import asyncio
from typing import Literal

from fastapi import Query, Request
from starlette.responses import Response

from tp2.app.application import create_app
from tp2.app.execution import _hash_batch


app = create_app()


@app.get("/__benchmark/download")
async def benchmark_download(delay_ms: int = Query(default=20, ge=0, le=1000)) -> Response:
    await asyncio.sleep(delay_ms / 1000)
    return Response(content=b"benchmark-payload", media_type="application/octet-stream")


@app.get("/__benchmark/hash")
async def benchmark_hash(
    request: Request,
    mode: Literal["inline", "executor"],
    iterations: int = Query(default=750_000, ge=1, le=5_000_000),
) -> dict[str, str]:
    payload = b"tp2-benchmark"
    if mode == "inline":
        digest = _hash_batch(payload, iterations)
    else:
        loop = asyncio.get_running_loop()
        digest = await loop.run_in_executor(
            request.app.state.process_pool, _hash_batch, payload, iterations
        )
    return {"digest": digest.hex()}
