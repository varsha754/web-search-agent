"""Streaming chat endpoints."""

import asyncio
import json
import threading
from contextlib import suppress

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from api.dependencies import get_search_agent
from core.config import config


router = APIRouter()
STREAM_IDLE_TIMEOUT_SECONDS = 120


@router.get("/chat_stream")
async def chat_stream(
    query: str = Query(..., min_length=1),
    no_cache: bool = False,
    debug: bool = False,
):
    """Stream status messages and answer chunks as server-sent events."""

    async def event_generator():
        queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        yield f"data: {json.dumps({'type': 'status', 'content': 'Connected to search agent...'})}\n\n"

        def status_callback(message):
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"type": "status", "content": message},
            )

        def stream_callback(message):
            loop.call_soon_threadsafe(
                queue.put_nowait,
                {"type": "chunk", "content": message},
            )

        def run_search():
            try:
                agent = get_search_agent()
                result = agent.search(
                    query,
                    max_results=config.MAX_RESULTS_IN_RESPONSE,
                    use_cache=not no_cache,
                    status_callback=status_callback,
                    stream_callback=stream_callback,
                    debug_llm_payloads=debug,
                )
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {"type": "done", "result": result},
                )
            except Exception as exc:
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    {"type": "error", "content": str(exc)},
                )

        thread = threading.Thread(target=run_search, daemon=True)
        thread.start()

        try:
            while True:
                with suppress(asyncio.TimeoutError):
                    item = await asyncio.wait_for(
                        queue.get(),
                        timeout=STREAM_IDLE_TIMEOUT_SECONDS,
                    )
                    yield f"data: {json.dumps(item)}\n\n"
                    if item["type"] in {"done", "error"}:
                        break
                    continue

                timeout_item = {
                    "type": "error",
                    "content": "Search timed out before the agent returned a result.",
                }
                yield f"data: {json.dumps(timeout_item)}\n\n"
                break
        except asyncio.CancelledError:
            return

    return StreamingResponse(event_generator(), media_type="text/event-stream")
