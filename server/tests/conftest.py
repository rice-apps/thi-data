"""
Shared test fixtures for all server tests.

Eliminates sys.path duplication and provides common mocking patterns.
"""

import os
import sys
import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

# sys.path setup — shared across all test files

current_dir = os.path.dirname(os.path.abspath(__file__))
server_dir = os.path.dirname(current_dir)
if server_dir not in sys.path:
    sys.path.insert(0, server_dir)

# Constants

API_URL = "http://localhost:8000"
TEST_CSV_PATH = os.path.join(current_dir, "test_data.csv")

# Fixtures


@pytest.fixture
def mock_db():
    """Yield a MagicMock SQLAlchemy Session."""
    return MagicMock()


@pytest.fixture
def mock_storage():
    """Yield a MagicMock StorageProvider."""
    from core.storage import StorageProvider
    return MagicMock(spec=StorageProvider)


@pytest.fixture
def mock_file_registry_repo():
    """Yield a MagicMock BaseRepository for file_registry."""
    return MagicMock()


def make_test_app(*routers):
    """Factory: create a FastAPI app with TestClient + get_db override.

    Usage:
        app, client = make_test_app(files.router, validation.router)
        app.dependency_overrides[get_db] = lambda: ...
    """
    from core.deps import get_db

    app = FastAPI()
    for r in routers:
        app.include_router(r)

    mock_db = MagicMock()

    async def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    return app, client, mock_db


@pytest.fixture
def uploaded_file():
    """Integration fixture: upload test_data.csv and yield file_id.

    Cleans up after test. Requires Docker stack running.
    """
    import requests

    test_csv = os.path.join(current_dir, "test_data.csv")
    if not os.path.exists(test_csv):
        pytest.skip("test_data.csv not found")

    with open(test_csv, "rb") as f:
        files = {"file": ("test_data.csv", f, "text/csv")}
        r = requests.post(f"{API_URL}/api/files/upload", files=files)

    if r.status_code != 200:
        pytest.skip(f"Upload failed: {r.status_code} {r.text}")

    data = r.json()
    file_id = data["file_id"]
    yield file_id

    try:
        requests.delete(f"{API_URL}/api/files", params={"file_id": file_id})
    except Exception:
        pass
