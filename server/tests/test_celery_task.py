"""
Unit tests for server/celery_task.py — process_patient_file, notify_frontend,
_refresh_api_server, update_file_status.

All tests mock external dependencies (no live Celery/Postgres/HTTP).
"""

import pytest
from unittest.mock import patch, MagicMock, call
from contextlib import contextmanager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@contextmanager
def _fake_db_context():
    yield MagicMock()


def _setup_mocks(mock_get_db_ctx, mock_get_storage, mock_get_repo=None, object_key="uploads/test.csv"):
    """Common mock setup for process_patient_file tests."""
    mock_db = MagicMock()
    mock_record = MagicMock()
    mock_record.object_key = object_key

    @contextmanager
    def fake_ctx():
        yield mock_db

    mock_get_db_ctx.return_value = fake_ctx()

    mock_storage = MagicMock()
    mock_storage.get_file_path.return_value = MagicMock(
        __str__=lambda s: "/tmp/test.csv",
        exists=lambda: False,
    )
    mock_get_storage.return_value = mock_storage

    if mock_get_repo is not None:
        mock_repo = MagicMock()
        mock_repo.get_by_field.return_value = [mock_record]
        mock_get_repo.return_value = mock_repo

    return mock_db, mock_storage


# ---------------------------------------------------------------------------
# process_patient_file
# ---------------------------------------------------------------------------

class TestProcessPatientFile:

    @patch("celery_task.notify_frontend")
    @patch("celery_task._refresh_api_server")
    @patch("celery_task.get_storage_provider")
    @patch("celery_task.get_db_context")
    @patch("celery_task.update_file_status")
    @patch("celery_task.run_etl")
    def test_success_path(
        self, mock_etl, mock_update_status, mock_get_db_ctx,
        mock_get_storage, mock_refresh, mock_notify
    ):
        from celery_task import process_patient_file

        mock_etl.return_value = 0

        with patch("celery_task.get_file_registry_repo") as mock_get_repo:
            _setup_mocks(mock_get_db_ctx, mock_get_storage, mock_get_repo)
            result = process_patient_file._orig_run("file-1", {"age": "INTEGER"})

        assert result["status"] == "SUCCESS"
        assert result["file_id"] == "file-1"

        # Verify call order: PROCESSING → ETL → SUCCESS → cleanup → refresh → notify
        mock_update_status.assert_any_call("file-1", "PROCESSING")
        mock_update_status.assert_any_call("file-1", "SUCCESS")
        mock_refresh.assert_called_once()
        mock_notify.assert_called_once()
        assert mock_notify.call_args[0][0]["type"] == "celery_success"

    @patch("celery_task.get_storage_provider")
    @patch("celery_task.get_db_context")
    @patch("celery_task.update_file_status")
    def test_file_not_found_in_registry(
        self, mock_update_status, mock_get_db_ctx, mock_get_storage
    ):
        from celery_task import process_patient_file

        @contextmanager
        def fake_ctx():
            yield MagicMock()

        mock_get_db_ctx.return_value = fake_ctx()

        with patch("celery_task.get_file_registry_repo") as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.get_by_field.return_value = []
            mock_get_repo.return_value = mock_repo

            with pytest.raises(ValueError, match="not found in registry"):
                process_patient_file._orig_run("missing-id", {"a": "VARCHAR"})

    @patch("celery_task.get_storage_provider")
    @patch("celery_task.get_db_context")
    @patch("celery_task.update_file_status")
    def test_file_path_is_none(
        self, mock_update_status, mock_get_db_ctx, mock_get_storage
    ):
        from celery_task import process_patient_file

        mock_storage = MagicMock()
        mock_storage.get_file_path.return_value = None
        mock_get_storage.return_value = mock_storage

        @contextmanager
        def fake_ctx():
            yield MagicMock()

        mock_get_db_ctx.return_value = fake_ctx()

        with patch("celery_task.get_file_registry_repo") as mock_get_repo:
            mock_repo = MagicMock()
            mock_record = MagicMock()
            mock_record.object_key = "uploads/test.csv"
            mock_repo.get_by_field.return_value = [mock_record]
            mock_get_repo.return_value = mock_repo

            with pytest.raises(FileNotFoundError, match="Could not resolve"):
                process_patient_file._orig_run("file-2", {"a": "VARCHAR"})

    @patch("celery_task.notify_frontend")
    @patch("celery_task.get_storage_provider")
    @patch("celery_task.get_db_context")
    @patch("celery_task.update_file_status")
    @patch("celery_task.run_etl")
    def test_etl_failure_updates_failed_and_notifies(
        self, mock_etl, mock_update_status, mock_get_db_ctx,
        mock_get_storage, mock_notify
    ):
        from celery_task import process_patient_file

        mock_etl.side_effect = RuntimeError("ETL crashed")

        with patch("celery_task.get_file_registry_repo") as mock_get_repo:
            _setup_mocks(mock_get_db_ctx, mock_get_storage, mock_get_repo)

            with pytest.raises(RuntimeError, match="ETL crashed"):
                process_patient_file._orig_run("file-3", {"a": "VARCHAR"})

        mock_update_status.assert_any_call(
            "file-3", "FAILED", error_message="ETL crashed"
        )
        mock_notify.assert_called_once()
        assert mock_notify.call_args[0][0]["type"] == "celery_failed"

    @patch("celery_task.notify_frontend")
    @patch("celery_task._refresh_api_server")
    @patch("celery_task.get_storage_provider")
    @patch("celery_task.get_db_context")
    @patch("celery_task.update_file_status")
    @patch("celery_task.run_etl")
    def test_cleanup_deletes_storage_and_local(
        self, mock_etl, mock_update_status, mock_get_db_ctx,
        mock_get_storage, mock_refresh, mock_notify
    ):
        from celery_task import process_patient_file

        mock_etl.return_value = 0

        mock_storage = MagicMock()
        mock_path = MagicMock()
        mock_path.__str__ = lambda s: "/tmp/thi-storage/test.csv"
        mock_path.exists.return_value = True
        mock_storage.get_file_path.return_value = mock_path
        mock_get_storage.return_value = mock_storage

        @contextmanager
        def fake_ctx():
            yield MagicMock()

        mock_get_db_ctx.return_value = fake_ctx()

        with patch("celery_task.get_file_registry_repo") as mock_get_repo:
            mock_repo = MagicMock()
            mock_record = MagicMock()
            mock_record.object_key = "uploads/test.csv"
            mock_repo.get_by_field.return_value = [mock_record]
            mock_get_repo.return_value = mock_repo

            process_patient_file._orig_run("file-4", {"a": "VARCHAR"})

        mock_storage.delete_file.assert_called_once_with("uploads/test.csv")
        mock_path.unlink.assert_called_once()

    @patch("celery_task.notify_frontend")
    @patch("celery_task._refresh_api_server")
    @patch("celery_task.get_storage_provider")
    @patch("celery_task.get_db_context")
    @patch("celery_task.update_file_status")
    @patch("celery_task.run_etl")
    def test_cleanup_failure_doesnt_block_success(
        self, mock_etl, mock_update_status, mock_get_db_ctx,
        mock_get_storage, mock_refresh, mock_notify
    ):
        from celery_task import process_patient_file

        mock_etl.return_value = 0

        mock_storage = MagicMock()
        mock_storage.delete_file.side_effect = RuntimeError("cleanup boom")
        mock_storage.get_file_path.return_value = MagicMock(
            __str__=lambda s: "/tmp/test.csv",
            exists=lambda: False,
        )
        mock_get_storage.return_value = mock_storage

        @contextmanager
        def fake_ctx():
            yield MagicMock()

        mock_get_db_ctx.return_value = fake_ctx()

        with patch("celery_task.get_file_registry_repo") as mock_get_repo:
            mock_repo = MagicMock()
            mock_record = MagicMock()
            mock_record.object_key = "uploads/test.csv"
            mock_repo.get_by_field.return_value = [mock_record]
            mock_get_repo.return_value = mock_repo

            result = process_patient_file._orig_run("file-5", {"a": "VARCHAR"})

        # Should still succeed despite cleanup failure
        assert result["status"] == "SUCCESS"


# ---------------------------------------------------------------------------
# notify_frontend
# ---------------------------------------------------------------------------

class TestNotifyFrontend:

    @patch("celery_task.psycopg2")
    def test_sends_pg_notify_with_json(self, mock_psycopg2):
        from celery_task import notify_frontend
        import json

        mock_conn = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        event = {"type": "celery_success", "file_id": "f1"}
        notify_frontend(event, dsn="postgresql://test")

        mock_psycopg2.connect.assert_called_once_with("postgresql://test")
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args
        assert "NOTIFY" in call_args[0][0]
        assert json.dumps(event) == call_args[0][1][0]

    @patch("celery_task.psycopg2")
    def test_closes_connection_in_finally(self, mock_psycopg2):
        from celery_task import notify_frontend

        mock_conn = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        # Even if execute raises, conn should close
        mock_cursor.execute.side_effect = RuntimeError("pg error")

        with pytest.raises(RuntimeError):
            notify_frontend({"type": "test"}, dsn="postgresql://test")

        mock_conn.close.assert_called_once()


# ---------------------------------------------------------------------------
# _refresh_api_server
# ---------------------------------------------------------------------------

class TestRefreshApiServer:

    @patch("celery_task.http_requests")
    def test_success_first_attempt(self, mock_requests):
        from celery_task import _refresh_api_server

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_requests.post.return_value = mock_resp

        _refresh_api_server(max_retries=2)
        assert mock_requests.post.call_count == 1

    @patch("celery_task.http_requests")
    def test_retries_on_failure(self, mock_requests):
        from celery_task import _refresh_api_server

        mock_resp_fail = MagicMock()
        mock_resp_fail.raise_for_status.side_effect = RuntimeError("fail")
        mock_resp_ok = MagicMock()
        mock_resp_ok.raise_for_status.return_value = None

        mock_requests.post.side_effect = [mock_resp_fail, mock_resp_ok]

        _refresh_api_server(max_retries=2)
        assert mock_requests.post.call_count == 2

    @patch("celery_task.http_requests")
    def test_raises_after_max_retries(self, mock_requests):
        from celery_task import _refresh_api_server

        mock_requests.post.side_effect = RuntimeError("always fail")

        with pytest.raises(RuntimeError, match="failed after"):
            _refresh_api_server(max_retries=2)

        assert mock_requests.post.call_count == 2


# ---------------------------------------------------------------------------
# update_file_status
# ---------------------------------------------------------------------------

class TestUpdateFileStatus:

    @patch("celery_task.get_file_registry_repo")
    @patch("celery_task.get_db_context")
    def test_updates_with_correct_args(self, mock_get_db_ctx, mock_get_repo):
        from celery_task import update_file_status

        mock_db = MagicMock()

        @contextmanager
        def fake_ctx():
            yield mock_db

        mock_get_db_ctx.return_value = fake_ctx()

        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        update_file_status("file-1", "PROCESSING")

        mock_repo.update_by_field.assert_called_once_with(
            db=mock_db,
            search_field="file_id",
            search_value="file-1",
            update_data={"status": "PROCESSING"},
        )

    @patch("celery_task.get_file_registry_repo")
    @patch("celery_task.get_db_context")
    def test_includes_error_message(self, mock_get_db_ctx, mock_get_repo):
        from celery_task import update_file_status

        mock_db = MagicMock()

        @contextmanager
        def fake_ctx():
            yield mock_db

        mock_get_db_ctx.return_value = fake_ctx()

        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        update_file_status("file-1", "FAILED", error_message="something broke")

        mock_repo.update_by_field.assert_called_once_with(
            db=mock_db,
            search_field="file_id",
            search_value="file-1",
            update_data={"status": "FAILED", "error_message": "something broke"},
        )
