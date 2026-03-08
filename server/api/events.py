import json
import asyncio
import threading
from typing import Optional, AsyncIterator

import psycopg2
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from core.config import settings
from core.enums import FileStatus


router = APIRouter(prefix="/api/events", tags=["events"])

PG_NOTIFY_CHANNEL = "thi_events"

_TERMINAL_FILE_STATUSES = {FileStatus.SUCCESS.value, FileStatus.FAILED.value}

def _format_sse(data: dict, event: Optional[str] = None) -> str:
    lines: list[str] = []
    if event:
        lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data)}")
    return "\n".join(lines) + "\n\n"


def _get_file_registry_status(file_id: str) -> Optional[dict]:
    """Fetch status info from file_registry.

    Returns a dict with at least {file_id, status} or None if not found.
    """
    conn = psycopg2.connect(settings.DLT_CREDENTIALS)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT file_id::text, status, error_message, target_table_name FROM file_registry WHERE file_id = %s",
                (file_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "file_id": row[0],
                "status": row[1],
                "error_message": row[2],
                "target_table_name": row[3],
            }
    finally:
        conn.close()


def _terminal_payload_from_registry(registry_row: dict) -> dict:
    status = registry_row.get("status")
    file_id = registry_row.get("file_id")
    if status == FileStatus.SUCCESS:
        return {
            "type": "celery_success",
            "file_id": file_id,
            "status": status,
            "target_table_name": registry_row.get("target_table_name"),
            "message": "Success",
        }
    if status == FileStatus.FAILED:
        return {
            "type": "celery_failed",
            "file_id": file_id,
            "status": status,
            "message": "Worker failed while processing file",
            "error": registry_row.get("error_message"),
        }
    return {
        "type": "file_status",
        "file_id": file_id,
        "status": status,
    }


class _PgNotifyBroadcaster:
    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._subscribers: set[tuple[asyncio.Queue, Optional[str]]] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        with self._lock:
            if self._loop is None:
                self._loop = loop

    def subscribe(self, queue: asyncio.Queue, file_id: Optional[str]) -> None:
        with self._lock:
            self._subscribers.add((queue, file_id))
        self._ensure_started()

    def unsubscribe(self, queue: asyncio.Queue, file_id: Optional[str]) -> None:
        with self._lock:
            self._subscribers.discard((queue, file_id))

    def _ensure_started(self) -> None:
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._run, name="pg-notify-broadcaster", daemon=True)
            self._thread.start()

    def _dispatch(self, payload: dict) -> None:
        with self._lock:
            loop = self._loop
            subscribers = list(self._subscribers)

        if loop is None:
            return

        def _enqueue() -> None:
            for q, wanted_file_id in subscribers:
                if wanted_file_id and payload.get("file_id") != wanted_file_id:
                    continue
                try:
                    q.put_nowait(payload)
                except Exception:
                    pass

        loop.call_soon_threadsafe(_enqueue)

    def _run(self) -> None:
        conn = psycopg2.connect(settings.DLT_CREDENTIALS)
        try:
            conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
            cur = conn.cursor()
            cur.execute(f"LISTEN {PG_NOTIFY_CHANNEL};")

            while not self._stop.is_set():
                if select.select([conn], [], [], 15) == ([], [], []):
                    continue

                conn.poll()
                while conn.notifies:
                    notify = conn.notifies.pop(0)
                    try:
                        payload = json.loads(notify.payload)
                    except Exception:
                        payload = {"type": "unknown", "raw": notify.payload}
                    self._dispatch(payload)
        finally:
            conn.close()


_broadcaster = _PgNotifyBroadcaster()




async def _async_event_stream(file_id: Optional[str]) -> AsyncIterator[str]:
    loop = asyncio.get_running_loop()
    _broadcaster.set_loop(loop)

    queue: asyncio.Queue = asyncio.Queue()
    _broadcaster.subscribe(queue, file_id)
    try:
        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=15)
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"
                continue

            event_type = payload.get("type")
            yield _format_sse(payload, event=event_type)
    finally:
        _broadcaster.unsubscribe(queue, file_id)


@router.get("/stream")
async def stream_events(
    file_id: Optional[str] = Query(None, description="If provided, only stream events for this file_id")
):
    if file_id:
        registry_row = _get_file_registry_status(file_id)
        if registry_row and registry_row.get("status") in _TERMINAL_FILE_STATUSES:
            payload = _terminal_payload_from_registry(registry_row)

            async def _immediate() -> AsyncIterator[str]:
                event_type = payload.get("type")
                yield _format_sse(payload, event=event_type)

            return StreamingResponse(_immediate(), media_type="text/event-stream")

    return StreamingResponse(_async_event_stream(file_id), media_type="text/event-stream")