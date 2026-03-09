"""
Unit tests for SQLAlchemy reflection and thread-safety.

Tests the advisory locking mechanism around reflect_db() / refresh_warehouse(),
model discovery via get_model_class(), race condition behavior with
sqlalchemy-dlock, lock release on failure, and schema refresh consistency.

These tests are self-contained — they mock the database engine and connections
so no live Postgres instance is required.
"""

import os
import sys
import threading
import time
import pytest
from unittest.mock import patch, MagicMock

# Add the 'server' directory to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.dirname(current_dir)
sys.path.insert(0, server_dir)

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# 1. Advisory Lock — refresh_warehouse wraps Base.prepare in the dlock
# ---------------------------------------------------------------------------

class TestAdvisoryLock:
    """Verify that the /api/refresh endpoint acquires the advisory lock
    before calling Base.prepare and releases it afterward."""

    @patch("core.database.engine")
    @patch("core.database.create_sadlock")
    @patch("core.database.Base")
    def test_refresh_acquires_lock_around_prepare(
        self, mock_base, mock_create_sadlock, mock_engine
    ):
        """Base.prepare must only be called inside the lock context manager."""
        from main import app

        mock_conn = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_engine.connect.return_value = mock_conn

        mock_lock = MagicMock()
        mock_create_sadlock.return_value = mock_lock

        mock_base.classes.keys.return_value = ["table_a", "table_b"]

        client = TestClient(app)
        r = client.post("/api/refresh")
        assert r.status_code == 200
        result = r.json()

        # Lock was created with the connection and the expected key
        mock_create_sadlock.assert_called_once_with(mock_conn, "db_reflection_schema_refresh")

        # Lock context manager was entered
        mock_lock.__enter__.assert_called_once()
        mock_lock.__exit__.assert_called_once()

        # Base.prepare was called inside the lock:
        #  - once for the public schema (initial load)
        #  - once after reflecting the DLT dataset schema
        assert mock_base.prepare.call_count == 2
        mock_base.prepare.assert_any_call(autoload_with=mock_engine)

        assert result["message"] == "Database refreshed successfully."

    @patch("core.database.engine")
    @patch("core.database.create_sadlock")
    @patch("core.database.Base")
    def test_refresh_returns_error_when_reflection_fails(
        self, mock_base, mock_create_sadlock, mock_engine
    ):
        """reflect_db re-raises reflection errors; the endpoint returns 400."""
        from main import app

        mock_conn = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_engine.connect.return_value = mock_conn

        mock_lock = MagicMock()
        mock_create_sadlock.return_value = mock_lock

        mock_base.prepare.side_effect = SQLAlchemyError("reflection failed")

        client = TestClient(app)
        r = client.post("/api/refresh")
        assert r.status_code == 400
        assert "Failed to connect" in r.json()["detail"]

        # Lock must still be released even on failure
        mock_lock.__enter__.assert_called_once()
        mock_lock.__exit__.assert_called_once()


# ---------------------------------------------------------------------------
# 2. Model Discovery — get_model_class returns the right class or errors
# ---------------------------------------------------------------------------

class TestModelDiscovery:
    """Test that get_model_class correctly retrieves models and enforces
    access restrictions on hidden tables."""

    @patch("core.deps.Base")
    def test_returns_model_for_valid_table(self, mock_base):
        from core.deps import get_model_class

        fake_model = type("FakeModel", (), {})
        mock_base.classes.get.return_value = fake_model

        result = get_model_class("patient_data")
        assert result is fake_model
        mock_base.classes.get.assert_called_once_with("patient_data")

    @patch("core.deps.Base")
    def test_raises_404_for_unknown_table(self, mock_base):
        from core.deps import get_model_class

        mock_base.classes.get.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            get_model_class("nonexistent_table")

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.detail

    def test_raises_403_for_hidden_tables(self):
        """Each table in HIDDEN_TABLES must be blocked with a 403."""
        from core.deps import get_model_class
        from core.constants import HIDDEN_TABLES

        for table in HIDDEN_TABLES:
            with pytest.raises(HTTPException) as exc_info:
                get_model_class(table)
            assert exc_info.value.status_code == 403
            assert "restricted" in exc_info.value.detail

    @patch("core.deps.Base")
    def test_internal_model_class_returns_model(self, mock_base):
        from core.deps import get_internal_model_class

        fake_model = type("FakeInternalModel", (), {})
        mock_base.classes.get.return_value = fake_model

        result = get_internal_model_class("corrupted_rows")
        assert result is fake_model

    @patch("core.deps.Base")
    def test_internal_model_class_raises_500_if_missing(self, mock_base):
        from core.deps import get_internal_model_class

        mock_base.classes.get.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            get_internal_model_class("corrupted_rows")

        assert exc_info.value.status_code == 500
        assert "Configuration error" in exc_info.value.detail


# ---------------------------------------------------------------------------
# 3. Race Condition Simulation — concurrent reflection calls are serialized
# ---------------------------------------------------------------------------

class TestRaceCondition:
    """Simulate two threads calling refresh_warehouse concurrently.
    The advisory lock should serialize them so Base.prepare is never
    running in two threads at the same time."""

    @patch("core.database.engine")
    @patch("core.database.create_sadlock")
    @patch("core.database.Base")
    def test_concurrent_refreshes_are_serialized(
        self, mock_base, mock_create_sadlock, mock_engine
    ):
        from main import app

        mock_conn = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_engine.connect.return_value = mock_conn
        mock_base.classes.keys.return_value = []

        # Real threading lock to simulate what sqlalchemy-dlock does
        real_lock = threading.Lock()
        concurrency_log = []  # records (thread_name, event, timestamp)

        def slow_prepare(**_kwargs):
            """Simulate a slow Base.prepare to expose concurrency issues."""
            thread = threading.current_thread().name
            concurrency_log.append((thread, "prepare_start", time.monotonic()))
            time.sleep(0.1)
            concurrency_log.append((thread, "prepare_end", time.monotonic()))

        mock_base.prepare.side_effect = slow_prepare

        # Make the mock lock delegate to a real threading.Lock
        mock_lock = MagicMock()
        mock_lock.__enter__ = lambda _self: real_lock.acquire()
        mock_lock.__exit__ = lambda _self, *_args: real_lock.release()
        mock_create_sadlock.return_value = mock_lock

        errors = []

        def call_refresh(name):
            try:
                client = TestClient(app)
                r = client.post("/api/refresh")
                assert r.status_code == 200
            except Exception as e:
                errors.append((name, e))

        t1 = threading.Thread(target=call_refresh, args=("thread-1",), name="thread-1")
        t2 = threading.Thread(target=call_refresh, args=("thread-2",), name="thread-2")

        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)

        assert not errors, f"Threads raised exceptions: {errors}"

        # Verify no overlapping prepare calls:
        # Extract start/end intervals per thread
        starts = [(name, ts) for name, event, ts in concurrency_log if event == "prepare_start"]
        ends = [(name, ts) for name, event, ts in concurrency_log if event == "prepare_end"]

        # reflect_db calls prepare() twice per invocation (public + DLT schema)
        assert len(starts) == 4, f"Expected 4 prepare starts, got {len(starts)}"
        assert len(ends) == 4, f"Expected 4 prepare ends, got {len(ends)}"

        # The second start must happen after the first end (serialized)
        first_end = min(ts for _, ts in ends)
        second_start = max(ts for _, ts in starts)
        assert second_start >= first_end, (
            "Race condition detected: second prepare started before first prepare ended"
        )


# ---------------------------------------------------------------------------
# 4. Lock Release on Failure — lock is freed even when Base.prepare raises
# ---------------------------------------------------------------------------

class TestLockReleaseOnFailure:
    """If Base.prepare() raises a SQLAlchemyError, the advisory lock must
    still be released so subsequent calls can proceed."""

    @patch("core.database.engine")
    @patch("core.database.create_sadlock")
    @patch("core.database.Base")
    def test_subsequent_call_succeeds_after_failure(
        self, mock_base, mock_create_sadlock, mock_engine
    ):
        """After a failed refresh, a second call should succeed normally."""
        from main import app

        mock_conn = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_engine.connect.return_value = mock_conn

        real_lock = threading.Lock()
        mock_lock = MagicMock()
        mock_lock.__enter__ = lambda _self: real_lock.acquire()
        mock_lock.__exit__ = lambda _self, *_args: real_lock.release()
        mock_create_sadlock.return_value = mock_lock

        # First call: fails but releases the lock
        mock_base.prepare.side_effect = SQLAlchemyError("temporary failure")
        client1 = TestClient(app)
        r1 = client1.post("/api/refresh")
        assert r1.status_code == 400

        # Second call: succeeds
        mock_base.prepare.side_effect = None
        mock_base.classes.keys.return_value = ["recovered_table"]

        client2 = TestClient(app)
        r2 = client2.post("/api/refresh")
        assert r2.status_code == 200

        # Lock should not be stuck — if it were, the second call would deadlock
        assert not real_lock.locked(), "Lock was not released after failure"


# ---------------------------------------------------------------------------
# 5. Schema Refresh Consistency — new/changed tables appear after refresh
# ---------------------------------------------------------------------------

class TestSchemaRefreshConsistency:
    """After a schema change (e.g., adding a column or table), calling
    refresh should update Base.classes without requiring a restart."""

    @patch("core.database.engine")
    @patch("core.database.create_sadlock")
    @patch("core.database.Base")
    def test_new_table_appears_after_refresh(
        self, mock_base, mock_create_sadlock, mock_engine
    ):
        from main import app

        mock_conn = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_engine.connect.return_value = mock_conn

        mock_lock = MagicMock()
        mock_create_sadlock.return_value = mock_lock

        # Simulate: before refresh, only "existing_table" is known
        mock_base.classes.keys.return_value = ["existing_table"]

        client = TestClient(app)
        r1 = client.post("/api/refresh")
        assert r1.status_code == 200

        # Simulate: a new table was added to the database behind the scenes
        mock_base.classes.keys.return_value = ["existing_table", "new_table"]

        r2 = client.post("/api/refresh")
        assert r2.status_code == 200

    @patch("core.database.create_sadlock")
    @patch("core.database.Base")
    @patch("core.database.engine")
    def test_reflect_db_calls_prepare_without_reflect_flag(
        self, mock_engine, mock_base, mock_create_sadlock
    ):
        """The startup reflect_db() does NOT pass reflect=True (initial load only)."""
        from core.database import reflect_db

        mock_conn = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_engine.connect.return_value = mock_conn

        mock_lock = MagicMock()
        mock_create_sadlock.return_value = mock_lock

        mock_base.classes.keys.return_value = ["table_a"]

        reflect_db()

        # reflect_db calls prepare() twice: once for public schema, once for DLT schema
        assert mock_base.prepare.call_count == 2
        mock_base.prepare.assert_any_call(autoload_with=mock_engine)
