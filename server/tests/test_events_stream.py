import os
import sys
import asyncio
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# Add the 'server' directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.dirname(current_dir)
sys.path.insert(0, server_dir)


class TestEventStreamIdempotency:
    def test_terminal_status_returns_immediately_without_listen(self):
        from main import app

        file_id = "11111111-1111-1111-1111-111111111111"

        with patch("api.events._get_file_registry_status") as mock_get_status, patch(
            "api.events._broadcaster.subscribe"
        ) as mock_subscribe:
            mock_get_status.return_value = {
                "file_id": file_id,
                "status": "SUCCESS",
                "error_message": None,
                "target_table_name": "final_patient_records",
            }

            client = TestClient(app)
            with client.stream("GET", "/api/events/stream", params={"file_id": file_id}) as r:
                assert r.status_code == 200
                lines = []
                for line in r.iter_lines():
                    if line == "":
                        break
                    lines.append(line)

        mock_subscribe.assert_not_called()
        assert lines[0].startswith("event: celery_success")
        assert lines[1].startswith("data: ")
        assert file_id in lines[1]


@pytest.mark.asyncio
async def test_async_event_stream_filters_by_file_id_and_yields_event():
    import api.events as events

    captured = {}

    def _subscribe(queue, file_id):
        captured["queue"] = queue
        captured["file_id"] = file_id

    def _unsubscribe(queue, file_id):
        captured["unsubscribed"] = (queue, file_id)

    with patch.object(events._broadcaster, "set_loop") as _set_loop, patch.object(
        events._broadcaster, "subscribe", side_effect=_subscribe
    ) as _sub, patch.object(events._broadcaster, "unsubscribe", side_effect=_unsubscribe) as _unsub:
        agen = events._async_event_stream("file-1")

        # Let the generator run far enough to subscribe
        task = asyncio.create_task(anext(agen))
        while "queue" not in captured:
            await asyncio.sleep(0)

        captured["queue"].put_nowait({"type": "celery_success", "file_id": "file-1"})
        line = await task

        assert line.startswith("event: celery_success")

        await agen.aclose()
        assert captured["unsubscribed"][1] == "file-1"
