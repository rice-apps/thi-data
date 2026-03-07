import json
import select
from typing import Iterator, Optional

import psycopg2
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from core.config import settings


router = APIRouter(prefix="/api/events", tags=["events"])

PG_NOTIFY_CHANNEL = "thi_events"

def _format_sse(data: dict, event: Optional[str] = None) -> str:
    lines: list[str] = []
    if event:
        lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data)}")
    return "\n".join(lines) + "\n\n"


def _event_stream(file_id: Optional[str]) -> Iterator[str]:
    conn = psycopg2.connect(settings.DLT_CREDENTIALS)
    try:
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        cur.execute(f"LISTEN {PG_NOTIFY_CHANNEL};")

        while True:
            if select.select([conn], [], [], 15) == ([], [], []):
                yield ": keep-alive\n\n"
                continue

            conn.poll()
            while conn.notifies:
                notify = conn.notifies.pop(0)
                try:
                    payload = json.loads(notify.payload)
                except Exception:
                    payload = {"type": "unknown", "raw": notify.payload}

                if file_id and payload.get("file_id") != file_id:
                    continue

                event_type = payload.get("type")
                yield _format_sse(payload, event=event_type)
    finally:
        conn.close()


@router.get("/stream")
def stream_events(
    file_id: Optional[str] = Query(None, description="If provided, only stream events for this file_id")
):
    return StreamingResponse(_event_stream(file_id), media_type="text/event-stream")