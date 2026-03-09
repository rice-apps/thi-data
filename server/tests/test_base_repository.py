"""
Unit tests for server/crud/base.py — BaseRepository and model_to_dict.

Uses in-memory SQLite with a real SQLAlchemy model to test every
repository method without needing Postgres.
"""

import pytest
from datetime import date, timedelta
from sqlalchemy import create_engine, Column, Integer, String, Date
from sqlalchemy.orm import sessionmaker, DeclarativeBase


# ---------------------------------------------------------------------------
# Test model + database setup
# ---------------------------------------------------------------------------

class TestBase(DeclarativeBase):
    pass


class Item(TestBase):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100))
    category = Column(String(50))
    created_date = Column(Date)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database and yield a session."""
    engine = create_engine("sqlite:///:memory:")
    TestBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def repo():
    """BaseRepository instance for the Item model."""
    from crud.base import BaseRepository
    return BaseRepository(Item)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBaseRepository:

    def test_create_and_get_by_id(self, db_session, repo):
        item = repo.create(db_session, {"name": "Widget", "category": "A"})
        assert item.id is not None

        fetched = repo.get_by_id(db_session, item.id)
        assert fetched is not None
        assert fetched.name == "Widget"
        assert fetched.category == "A"

    def test_get_by_id_not_found(self, db_session, repo):
        assert repo.get_by_id(db_session, 9999) is None

    def test_get_all_pagination(self, db_session, repo):
        for i in range(5):
            repo.create(db_session, {"name": f"Item{i}", "category": "B"})

        items, total = repo.get_all(db_session, skip=1, limit=2)
        assert total == 5
        assert len(items) == 2

    def test_get_all_empty(self, db_session, repo):
        items, total = repo.get_all(db_session)
        assert items == []
        assert total == 0

    def test_get_by_field(self, db_session, repo):
        repo.create(db_session, {"name": "A", "category": "X"})
        repo.create(db_session, {"name": "B", "category": "Y"})
        repo.create(db_session, {"name": "C", "category": "X"})

        results = repo.get_by_field(db_session, "category", "X")
        assert len(results) == 2
        assert all(r.category == "X" for r in results)

    def test_update_with_dict(self, db_session, repo):
        item = repo.create(db_session, {"name": "Old", "category": "Z"})
        updated = repo.update(db_session, db_obj=item, obj_in={"name": "New"})
        assert updated.name == "New"
        assert updated.category == "Z"

    def test_delete_success(self, db_session, repo):
        item = repo.create(db_session, {"name": "ToDelete", "category": "D"})
        assert repo.delete(db_session, item.id) is True
        assert repo.get_by_id(db_session, item.id) is None

    def test_delete_not_found(self, db_session, repo):
        assert repo.delete(db_session, 9999) is False

    def test_update_by_field(self, db_session, repo):
        repo.create(db_session, {"name": "A", "category": "OLD"})
        repo.create(db_session, {"name": "B", "category": "OLD"})
        repo.create(db_session, {"name": "C", "category": "NEW"})

        count = repo.update_by_field(
            db_session, "category", "OLD", {"category": "UPDATED"}
        )
        assert count == 2

        results = repo.get_by_field(db_session, "category", "UPDATED")
        assert len(results) == 2

    def test_update_by_field_no_match(self, db_session, repo):
        count = repo.update_by_field(
            db_session, "category", "NONEXISTENT", {"name": "X"}
        )
        assert count == 0

    def test_delete_by_field(self, db_session, repo):
        repo.create(db_session, {"name": "A", "category": "DEL"})
        repo.create(db_session, {"name": "B", "category": "DEL"})
        repo.create(db_session, {"name": "C", "category": "KEEP"})

        count = repo.delete_by_field(db_session, "category", "DEL")
        assert count == 2

        _, total = repo.get_all(db_session)
        assert total == 1

    def test_get_by_date_range(self, db_session, repo):
        today = date.today()
        repo.create(db_session, {"name": "Yesterday", "created_date": today - timedelta(days=1)})
        repo.create(db_session, {"name": "Today", "created_date": today})
        repo.create(db_session, {"name": "Tomorrow", "created_date": today + timedelta(days=1)})
        repo.create(db_session, {"name": "Old", "created_date": today - timedelta(days=30)})

        results, total = repo.get_by_date_range(
            db_session, "created_date",
            today - timedelta(days=1), today
        )
        assert total == 2
        assert len(results) == 2

    def test_filter_text(self, db_session, repo):
        repo.create(db_session, {"name": "Alice Smith", "category": "A"})
        repo.create(db_session, {"name": "Bob Jones", "category": "B"})
        repo.create(db_session, {"name": "Alice Wong", "category": "C"})

        results, total = repo.filter_text(db_session, "name", "Alice")
        assert total == 2
        assert len(results) == 2

    def test_filter_text_pagination(self, db_session, repo):
        for i in range(10):
            repo.create(db_session, {"name": f"Test{i}", "category": "CAT"})

        results, total = repo.filter_text(
            db_session, "name", "Test", skip=2, limit=3
        )
        assert total == 10
        assert len(results) == 3


class TestModelToDict:

    def test_model_to_dict(self, db_session, repo):
        from crud.base import model_to_dict
        item = repo.create(db_session, {"name": "Widget", "category": "A"})
        d = model_to_dict(item)
        assert isinstance(d, dict)
        assert d["name"] == "Widget"
        assert d["category"] == "A"
        assert "id" in d

    def test_model_to_dict_none(self):
        from crud.base import model_to_dict
        assert model_to_dict(None) is None
