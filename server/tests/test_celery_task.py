"""
Unit tests for server/celery_task.py — process_patient_file, notify_frontend,
_refresh_api_server, update_file_status.

All tests mock external dependencies (no live Celery/Postgres/HTTP).
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from contextlib import contextmanager
from celery.exceptions import MaxRetriesExceededError


# Test helpers


@contextmanager
def _fake_db_context():
    yield MagicMock()


@contextmanager
def _mock_update_file_status():
    """Celery and orchestration each bind update_file_status at import time; mock both."""
    m = MagicMock()
    with patch("celery_task.update_file_status", m), patch(
        "services.etl_success_orchestration.update_file_status", m
    ):
        yield m


@contextmanager
def _patch_db_context(mock_get_db_ctx: MagicMock):
    """Bind the same DB context mock wherever get_db_context was imported."""
    with patch("celery_task.get_db_context", mock_get_db_ctx), patch(
        "core.deps.get_db_context", mock_get_db_ctx
    ), patch("services.etl_success_orchestration.get_db_context", mock_get_db_ctx):
        yield


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


# process_patient_file tests


class TestProcessPatientFile:

    @patch("services.etl_success_orchestration.publish_thi_event")
    @patch("services.etl_success_orchestration.refresh_api_server_schema")
    @patch("celery_task.get_storage_provider")
    @patch("celery_task.get_db_context")
    @patch("celery_task.run_etl")
    def test_success_path(
        self,
        mock_etl,
        mock_get_db_ctx,
        mock_get_storage,
        mock_refresh,
        mock_publish,
    ):
        from celery_task import process_patient_file

        mock_etl.return_value = 0

        with _mock_update_file_status() as mock_update_status, patch(
            "core.deps.get_file_registry_repo"
        ) as mock_get_repo:
            _setup_mocks(mock_get_db_ctx, mock_get_storage, mock_get_repo)
            result = process_patient_file.run("file-1", {"age": "INTEGER"})

        assert result["status"] == "SUCCESS"
        assert result["file_id"] == "file-1"

        mock_update_status.assert_any_call("file-1", "PROCESSING")
        mock_update_status.assert_any_call("file-1", "SUCCESS")
        mock_refresh.assert_called_once()
        mock_publish.assert_called_once()
        assert mock_publish.call_args[0][0]["type"] == "celery_success"

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

        with patch("core.deps.get_file_registry_repo") as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.get_by_field.return_value = []
            mock_get_repo.return_value = mock_repo

            with pytest.raises(ValueError, match="not found in registry"):
                process_patient_file.run("missing-id", {"a": "VARCHAR"})

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

        with patch("core.deps.get_file_registry_repo") as mock_get_repo:
            mock_repo = MagicMock()
            mock_record = MagicMock()
            mock_record.object_key = "uploads/test.csv"
            mock_repo.get_by_field.return_value = [mock_record]
            mock_get_repo.return_value = mock_repo

            with patch.object(
                process_patient_file,
                "retry",
                side_effect=MaxRetriesExceededError(),
            ):
                with pytest.raises(FileNotFoundError, match="Could not resolve"):
                    process_patient_file.run("file-2", {"a": "VARCHAR"})

    @patch("celery_task.publish_thi_event")
    @patch("celery_task.get_storage_provider")
    @patch("celery_task.get_db_context")
    @patch("celery_task.update_file_status")
    @patch("celery_task.run_etl")
    def test_etl_failure_updates_failed_and_notifies(
        self,
        mock_etl,
        mock_update_status,
        mock_get_db_ctx,
        mock_get_storage,
        mock_publish,
    ):
        from celery_task import process_patient_file

        mock_etl.side_effect = RuntimeError("ETL crashed")

        with patch("core.deps.get_file_registry_repo") as mock_get_repo:
            _setup_mocks(mock_get_db_ctx, mock_get_storage, mock_get_repo)

            with patch.object(
                process_patient_file,
                "retry",
                side_effect=MaxRetriesExceededError(),
            ):
                with pytest.raises(RuntimeError, match="ETL crashed"):
                    process_patient_file.run("file-3", {"a": "VARCHAR"})

        mock_update_status.assert_any_call(
            "file-3", "FAILED", error_message="ETL crashed"
        )
        mock_publish.assert_called_once()
        assert mock_publish.call_args[0][0]["type"] == "celery_failed"

    @patch("services.etl_success_orchestration.record_metadata_creation")
    @patch("services.etl_success_orchestration.publish_thi_event")
    @patch("services.etl_success_orchestration.refresh_api_server_schema")
    @patch("celery_task.get_storage_provider")
    @patch("celery_task.get_db_context")
    @patch("celery_task.run_etl")
    def test_cleanup_deletes_storage_and_local(
        self,
        mock_etl,
        mock_get_db_ctx,
        mock_get_storage,
        mock_refresh,
        mock_publish,
        mock_record_meta,
    ):
        from celery_task import process_patient_file

        mock_etl.return_value = 0

        tmp_root = Path("/tmp/thi-storage")
        tmp_root.mkdir(parents=True, exist_ok=True)
        local_file = tmp_root / "test-cleanup.csv"
        local_file.write_text("x", encoding="utf-8")

        mock_storage = MagicMock()
        mock_storage.get_file_path.return_value = local_file
        mock_get_storage.return_value = mock_storage

        @contextmanager
        def fake_ctx():
            yield MagicMock()

        mock_get_db_ctx.return_value = fake_ctx()

        with _mock_update_file_status(), patch("core.deps.get_file_registry_repo") as mock_get_repo:
            mock_repo = MagicMock()
            mock_record = MagicMock()
            mock_record.object_key = "uploads/test.csv"
            mock_record.target_table_name = "t"
            mock_record.uploaded_by = "u"
            mock_repo.get_by_field.return_value = [mock_record]
            mock_get_repo.return_value = mock_repo

            process_patient_file.run("file-4", {"a": "VARCHAR"})

        mock_storage.delete_file.assert_called_once_with("uploads/test.csv")
        assert not local_file.exists()

    @patch("services.etl_success_orchestration.record_metadata_creation")
    @patch("services.etl_success_orchestration.publish_thi_event")
    @patch("services.etl_success_orchestration.refresh_api_server_schema")
    @patch("celery_task.get_storage_provider")
    @patch("celery_task.get_db_context")
    @patch("celery_task.run_etl")
    def test_cleanup_failure_doesnt_block_success(
        self,
        mock_etl,
        mock_get_db_ctx,
        mock_get_storage,
        mock_refresh,
        mock_publish,
        mock_record_meta,
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

        with _mock_update_file_status(), patch("core.deps.get_file_registry_repo") as mock_get_repo:
            mock_repo = MagicMock()
            mock_record = MagicMock()
            mock_record.object_key = "uploads/test.csv"
            mock_record.target_table_name = "t"
            mock_record.uploaded_by = "u"
            mock_repo.get_by_field.return_value = [mock_record]
            mock_get_repo.return_value = mock_repo

            result = process_patient_file.run("file-5", {"a": "VARCHAR"})

        assert result["status"] == "SUCCESS"


# notify_frontend tests


class TestNotifyFrontend:

    @patch("services.pg_notify_events.psycopg2")
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

    @patch("services.pg_notify_events.psycopg2")
    def test_closes_connection_in_finally(self, mock_psycopg2):
        from celery_task import notify_frontend

        mock_conn = MagicMock()
        mock_psycopg2.connect.return_value = mock_conn
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)

        mock_cursor.execute.side_effect = RuntimeError("pg error")

        with pytest.raises(RuntimeError):
            notify_frontend({"type": "test"}, dsn="postgresql://test")

        mock_conn.close.assert_called_once()


# _refresh_api_server tests


class TestRefreshApiServer:

    @patch("services.api_reflection_client.requests")
    def test_success_first_attempt(self, mock_requests):
        from celery_task import _refresh_api_server

        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        mock_requests.post.return_value = mock_resp

        _refresh_api_server(max_retries=2)
        assert mock_requests.post.call_count == 1

    @patch("services.api_reflection_client.requests")
    def test_retries_on_failure(self, mock_requests):
        from celery_task import _refresh_api_server

        mock_resp_fail = MagicMock()
        mock_resp_fail.raise_for_status.side_effect = RuntimeError("fail")
        mock_resp_ok = MagicMock()
        mock_resp_ok.raise_for_status.return_value = None

        mock_requests.post.side_effect = [mock_resp_fail, mock_resp_ok]

        _refresh_api_server(max_retries=2)
        assert mock_requests.post.call_count == 2

    @patch("services.api_reflection_client.requests")
    def test_raises_after_max_retries(self, mock_requests):
        from celery_task import _refresh_api_server

        mock_requests.post.side_effect = RuntimeError("always fail")

        with pytest.raises(RuntimeError, match="failed after"):
            _refresh_api_server(max_retries=2)

        assert mock_requests.post.call_count == 2


# update_file_status tests


class TestUpdateFileStatus:

    @patch("core.deps.get_file_registry_repo")
    @patch("core.deps.get_db_context")
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

    @patch("core.deps.get_file_registry_repo")
    @patch("core.deps.get_db_context")
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


# Metadata creation persistence tests


class TestMetadataCreation:

    @patch("services.etl_success_orchestration.publish_thi_event")
    @patch("services.etl_success_orchestration.refresh_api_server_schema")
    @patch("celery_task.get_storage_provider")
    @patch("celery_task.run_etl")
    @patch("services.etl_success_orchestration.get_internal_model_class_raw")
    def test_metadata_creation_record_persisted(
        self,
        mock_get_model,
        mock_etl,
        mock_get_storage,
        mock_refresh,
        mock_publish,
    ):
        """After successful ETL, a metadata_creation record is inserted with
        the correct table_name and created_by values, and flush is called."""
        from celery_task import process_patient_file

        mock_etl.return_value = 0
        mock_meta_cls = MagicMock()
        mock_get_model.return_value = mock_meta_cls

        mock_record = MagicMock()
        mock_record.object_key = "uploads/test.csv"
        mock_record.target_table_name = "my_table"
        mock_record.uploaded_by = "alice"

        db_sessions = []

        @contextmanager
        def fake_ctx():
            db = MagicMock()
            db_sessions.append(db)
            yield db

        mock_get_db_ctx = MagicMock(side_effect=fake_ctx)

        with _mock_update_file_status(), _patch_db_context(mock_get_db_ctx), patch(
            "core.deps.get_file_registry_repo"
        ) as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.get_by_field.return_value = [mock_record]
            mock_get_repo.return_value = mock_repo

            result = process_patient_file.run("file-meta", {"a": "VARCHAR"})

        assert result["status"] == "SUCCESS"
        mock_get_model.assert_called_once_with("metadata_creation")
        mock_meta_cls.assert_called_once_with(table_name="my_table", created_by="alice")

        metadata_db = [s for s in db_sessions if s.add.called and s.flush.called]
        assert len(metadata_db) == 1

    @patch("services.etl_success_orchestration.publish_thi_event")
    @patch("services.etl_success_orchestration.refresh_api_server_schema")
    @patch("celery_task.get_storage_provider")
    @patch("celery_task.get_db_context")
    @patch("celery_task.run_etl")
    @patch("services.etl_success_orchestration.get_internal_model_class_raw")
    def test_metadata_failure_does_not_block_task(
        self,
        mock_get_model,
        mock_etl,
        mock_get_db_ctx,
        mock_get_storage,
        mock_refresh,
        mock_publish,
    ):
        """If metadata_creation insertion fails, the task still returns SUCCESS."""
        from celery_task import process_patient_file

        mock_etl.return_value = 0
        mock_get_model.side_effect = RuntimeError("model not found")

        with _mock_update_file_status(), patch("core.deps.get_file_registry_repo") as mock_get_repo:
            _setup_mocks(mock_get_db_ctx, mock_get_storage, mock_get_repo)

            result = process_patient_file.run("file-meta-fail", {"a": "VARCHAR"})

        assert result["status"] == "SUCCESS"
        mock_refresh.assert_called_once()

    @patch("services.etl_success_orchestration.publish_thi_event")
    @patch("services.etl_success_orchestration.refresh_api_server_schema")
    @patch("celery_task.get_storage_provider")
    @patch("celery_task.run_etl")
    @patch("services.etl_success_orchestration.get_internal_model_class_raw")
    def test_metadata_uses_uploaded_by_from_registry(
        self,
        mock_get_model,
        mock_etl,
        mock_get_storage,
        mock_refresh,
        mock_publish,
    ):
        """The created_by field in metadata_creation comes from file_registry.uploaded_by."""
        from celery_task import process_patient_file

        mock_etl.return_value = 0
        mock_meta_cls = MagicMock()
        mock_get_model.return_value = mock_meta_cls

        mock_record = MagicMock()
        mock_record.object_key = "uploads/data.csv"
        mock_record.target_table_name = "patient_data"
        mock_record.uploaded_by = None

        @contextmanager
        def fake_ctx():
            yield MagicMock()

        mock_get_db_ctx = MagicMock(side_effect=fake_ctx)

        with _mock_update_file_status(), _patch_db_context(mock_get_db_ctx), patch(
            "core.deps.get_file_registry_repo"
        ) as mock_get_repo:
            mock_repo = MagicMock()
            mock_repo.get_by_field.return_value = [mock_record]
            mock_get_repo.return_value = mock_repo

            mock_storage = MagicMock()
            mock_storage.get_file_path.return_value = MagicMock(
                __str__=lambda s: "/tmp/test.csv",
                exists=lambda: False,
            )
            mock_get_storage.return_value = mock_storage

            process_patient_file.run("file-anon", {"a": "VARCHAR"})

        mock_meta_cls.assert_called_once_with(
            table_name="patient_data", created_by="unknown"
        )
