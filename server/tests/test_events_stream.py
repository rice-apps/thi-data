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


# ===========================================================================
# SSE Format Tests
# ===========================================================================

class TestFormatSSE:
    """Verify that _format_sse produces correct SSE wire format."""

    def test_with_event_type(self):
        from api.events import _format_sse
        result = _format_sse({"file_id": "abc"}, event="celery_success")
        lines = result.split("\n")
        assert lines[0] == "event: celery_success"
        assert lines[1].startswith("data: ")
        assert '"file_id": "abc"' in lines[1]
        # SSE requires double newline terminator
        assert result.endswith("\n\n")

    def test_without_event_type(self):
        from api.events import _format_sse
        result = _format_sse({"key": "val"})
        assert not result.startswith("event:")
        assert result.startswith("data: ")
        assert result.endswith("\n\n")

    def test_data_is_valid_json(self):
        import json
        from api.events import _format_sse
        result = _format_sse({"a": 1, "b": [2, 3]}, event="test")
        data_line = [l for l in result.split("\n") if l.startswith("data: ")][0]
        parsed = json.loads(data_line[len("data: "):])
        assert parsed == {"a": 1, "b": [2, 3]}


class TestTerminalPayloadMapping:
    """Verify _terminal_payload_from_registry maps statuses correctly."""

    def test_success_payload(self):
        from api.events import _terminal_payload_from_registry
        row = {
            "file_id": "f1",
            "status": "SUCCESS",
            "error_message": None,
            "target_table_name": "patient_records",
        }
        payload = _terminal_payload_from_registry(row)
        assert payload["type"] == "celery_success"
        assert payload["file_id"] == "f1"
        assert payload["target_table_name"] == "patient_records"

    def test_failed_payload(self):
        from api.events import _terminal_payload_from_registry
        row = {
            "file_id": "f2",
            "status": "FAILED",
            "error_message": "DuckDB crashed",
            "target_table_name": None,
        }
        payload = _terminal_payload_from_registry(row)
        assert payload["type"] == "celery_failed"
        assert payload["error"] == "DuckDB crashed"

    def test_non_terminal_payload(self):
        from api.events import _terminal_payload_from_registry
        row = {"file_id": "f3", "status": "PROCESSING"}
        payload = _terminal_payload_from_registry(row)
        assert payload["type"] == "file_status"
        assert payload["status"] == "PROCESSING"


class TestTerminalFailedImmediate:
    """Terminal FAILED status should return immediately without subscribing."""

    def test_failed_status_returns_immediately(self):
        from main import app

        file_id = "22222222-2222-2222-2222-222222222222"

        with patch("api.events._get_file_registry_status") as mock_get_status, patch(
            "api.events._broadcaster.subscribe"
        ) as mock_subscribe:
            mock_get_status.return_value = {
                "file_id": file_id,
                "status": "FAILED",
                "error_message": "something broke",
                "target_table_name": None,
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
        assert lines[0].startswith("event: celery_failed")
        assert "something broke" in lines[1]


@pytest.mark.asyncio
async def test_async_stream_keep_alive_on_timeout():
    """When no events arrive within 15s, a keep-alive comment should be yielded."""
    import api.events as events

    captured = {}

    def _subscribe(queue, file_id):
        captured["queue"] = queue

    with patch.object(events._broadcaster, "set_loop"), \
         patch.object(events._broadcaster, "subscribe", side_effect=_subscribe), \
         patch.object(events._broadcaster, "unsubscribe"):

        agen = events._async_event_stream("file-keep-alive")

        # Override wait_for timeout to 0.01s for fast testing
        original_wait_for = asyncio.wait_for

        async def fast_timeout(coro, timeout):
            return await original_wait_for(coro, timeout=0.01)

        with patch("api.events.asyncio.wait_for", side_effect=fast_timeout):
            task = asyncio.create_task(anext(agen))
            while "queue" not in captured:
                await asyncio.sleep(0)

            line = await task
            assert line == ": keep-alive\n\n"

        await agen.aclose()


@pytest.mark.asyncio
async def test_async_stream_ignores_other_file_ids():
    """Events for other file_ids are filtered by the broadcaster, not the stream."""
    import api.events as events

    captured = {}

    def _subscribe(queue, file_id):
        captured["queue"] = queue
        captured["file_id"] = file_id

    with patch.object(events._broadcaster, "set_loop"), \
         patch.object(events._broadcaster, "subscribe", side_effect=_subscribe), \
         patch.object(events._broadcaster, "unsubscribe"):

        agen = events._async_event_stream("my-file")

        task = asyncio.create_task(anext(agen))
        while "queue" not in captured:
            await asyncio.sleep(0)

        # Subscribe was called with our file_id
        assert captured["file_id"] == "my-file"

        # Push an event — the broadcaster is responsible for filtering
        captured["queue"].put_nowait({"type": "celery_success", "file_id": "my-file"})
        line = await task
        assert "celery_success" in line

        await agen.aclose()
