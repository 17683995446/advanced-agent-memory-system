"""Unit tests for the structured_store module."""
import pytest
import os
import tempfile
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from memory_system.storage.structured_sqlite_store import (
    StructuredStore,
    MemoryTable,
    StructuredRecord,
    QueryResult,
)


# ======================================================================
# TestStructuredStore
# ======================================================================


class TestStructuredStore:
    """Tests for the StructuredStore class."""

    def test_create_table(self):
        """create_table should make the table visible in list_tables."""
        store = StructuredStore(":memory:")
        store.create_table("users", {"name": "TEXT", "age": "INTEGER"})
        assert "users" in store.list_tables()

    def test_create_table_with_columns(self):
        """create_table with columns should show them in table_info."""
        store = StructuredStore(":memory:")
        store.create_table("users", {"name": "TEXT", "age": "INTEGER"})
        info = store.table_info("users")
        assert info is not None
        col_names = [c["name"] for c in info["columns"]]
        assert "name" in col_names
        assert "age" in col_names
        # Auto-managed columns should also be present
        assert "id" in col_names
        assert "created_at" in col_names
        assert "updated_at" in col_names

    def test_drop_table(self):
        """Dropping a table should remove it from list_tables."""
        store = StructuredStore(":memory:")
        store.create_table("users", {"name": "TEXT"})
        store.drop_table("users")
        assert "users" not in store.list_tables()

    def test_insert_and_select(self):
        """Inserting a row and selecting it should return the same data."""
        store = StructuredStore(":memory:")
        store.create_table("users", {"name": "TEXT", "age": "INTEGER"})
        record_id = store.insert("users", {"name": "Alice", "age": 30})
        result = store.select("users")
        assert result.total == 1
        row = result.records[0]
        assert row["name"] == "Alice"
        assert row["age"] == 30
        assert row["id"] == record_id

    def test_insert_does_not_mutate_caller(self):
        """insert should not mutate the caller's original dict."""
        store = StructuredStore(":memory:")
        store.create_table("users", {"name": "TEXT"})
        original = {"name": "test"}
        store.insert("users", original)
        assert "name" in original

    def test_insert_batch(self):
        """insert_batch with 3 rows should result in count 3."""
        store = StructuredStore(":memory:")
        store.create_table("users", {"name": "TEXT"})
        records = [
            {"name": "Alice"},
            {"name": "Bob"},
            {"name": "Charlie"},
        ]
        ids = store.insert_batch("users", records)
        assert len(ids) == 3
        assert store.count("users") == 3

    def test_update(self):
        """Updating a row should change its value in subsequent selects."""
        store = StructuredStore(":memory:")
        store.create_table("users", {"name": "TEXT", "age": "INTEGER"})
        store.insert("users", {"name": "Alice", "age": 30})
        store.update("users", {"age": 31}, where="name = ?", params=("Alice",))
        result = store.select("users", where="name = ?", params=("Alice",))
        assert result.records[0]["age"] == 31

    def test_delete(self):
        """Deleting all rows should leave count at 0."""
        store = StructuredStore(":memory:")
        store.create_table("users", {"name": "TEXT"})
        store.insert("users", {"name": "Alice"})
        store.delete("users")
        assert store.count("users") == 0

    def test_count(self):
        """count should return the number of rows in the table."""
        store = StructuredStore(":memory:")
        store.create_table("users", {"name": "TEXT"})
        store.insert_batch("users", [{"name": "A"}, {"name": "B"}, {"name": "C"}])
        assert store.count("users") == 3

    def test_select_with_where(self):
        """select with a WHERE clause should filter rows correctly."""
        store = StructuredStore(":memory:")
        store.create_table("users", {"name": "TEXT", "age": "INTEGER"})
        store.insert("users", {"name": "Alice", "age": 30})
        store.insert("users", {"name": "Bob", "age": 25})
        store.insert("users", {"name": "Charlie", "age": 30})
        result = store.select("users", where="age = ?", params=(30,))
        assert result.total == 2
        names = {r["name"] for r in result.records}
        assert names == {"Alice", "Charlie"}

    def test_select_with_order_by(self):
        """select with order_by should return rows in the specified order."""
        store = StructuredStore(":memory:")
        store.create_table("users", {"name": "TEXT", "age": "INTEGER"})
        store.insert("users", {"name": "Charlie", "age": 30})
        store.insert("users", {"name": "Alice", "age": 25})
        store.insert("users", {"name": "Bob", "age": 27})
        result = store.select("users", order_by="age ASC")
        ages = [r["age"] for r in result.records]
        assert ages == [25, 27, 30]

    def test_select_with_limit_offset(self):
        """select with limit=2 and offset=1 should return 2 rows starting from the second."""
        store = StructuredStore(":memory:")
        store.create_table("users", {"name": "TEXT", "age": "INTEGER"})
        for i in range(5):
            store.insert("users", {"name": f"user_{i}", "age": i})
        result = store.select("users", order_by="age ASC", limit=2, offset=1)
        assert len(result.records) == 2
        names = [r["name"] for r in result.records]
        assert names == ["user_1", "user_2"]

    def test_execute_sql(self):
        """execute_sql with raw SQL should work correctly."""
        store = StructuredStore(":memory:")
        store.create_table("users", {"name": "TEXT", "age": "INTEGER"})
        store.insert("users", {"name": "Alice", "age": 30})
        store.insert("users", {"name": "Bob", "age": 25})
        rows = store.execute_sql("SELECT name, age FROM users WHERE age > ?", (26,))
        assert len(rows) == 1
        assert rows[0]["name"] == "Alice"

    def test_search_fulltext(self):
        """search_fulltext should find rows matching the query string."""
        store = StructuredStore(":memory:")
        store.create_table("docs", {"title": "TEXT", "body": "TEXT"})
        store.insert("docs", {"title": "Python Guide", "body": "Learn Python programming"})
        store.insert("docs", {"title": "Java Guide", "body": "Learn Java programming"})
        result = store.search_fulltext("docs", "Python")
        assert result.total >= 1
        titles = [r["title"] for r in result.records]
        assert "Python Guide" in titles

    def test_add_column(self):
        """add_column should add a new column to an existing table."""
        store = StructuredStore(":memory:")
        store.create_table("users", {"name": "TEXT"})
        success = store.add_column("users", "age", "INTEGER")
        assert success is True
        info = store.table_info("users")
        col_names = [c["name"] for c in info["columns"]]
        assert "age" in col_names

    def test_ensure_table(self):
        """ensure_table should create the table if it does not exist, and not raise if it does."""
        store = StructuredStore(":memory:")
        result1 = store.ensure_table("users", {"name": "TEXT"})
        assert result1 is True
        assert "users" in store.list_tables()
        # Calling again should not raise and should still return True
        result2 = store.ensure_table("users", {"name": "TEXT"})
        assert result2 is True

    def test_vacuum(self):
        """vacuum should not raise an error."""
        store = StructuredStore(":memory:")
        store.create_table("users", {"name": "TEXT"})
        store.insert("users", {"name": "Alice"})
        store.vacuum()  # Should not raise

    def test_backup(self):
        """backup to a temp file should succeed."""
        store = StructuredStore(":memory:")
        store.create_table("users", {"name": "TEXT"})
        store.insert("users", {"name": "Alice"})

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            tmp_path = f.name

        try:
            success = store.backup(tmp_path)
            assert success is True
            assert os.path.exists(tmp_path)
            assert os.path.getsize(tmp_path) > 0
        finally:
            os.unlink(tmp_path)

    def test_close_and_reopen(self):
        """Closing and reopening with the same file path should preserve data."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            tmp_path = f.name

        try:
            store = StructuredStore(tmp_path)
            store.create_table("users", {"name": "TEXT"})
            store.insert("users", {"name": "Alice"})
            store.close()

            store2 = StructuredStore(tmp_path)
            result = store2.select("users")
            assert result.total == 1
            assert result.records[0]["name"] == "Alice"
            store2.close()
        finally:
            os.unlink(tmp_path)

    def test_transaction_commit(self):
        """A successful transaction should commit all operations."""
        store = StructuredStore(":memory:")
        store.create_table("users", {"name": "TEXT"})
        with store.begin_transaction():
            store.insert("users", {"name": "Alice"})
            store.insert("users", {"name": "Bob"})
        assert store.count("users") == 2

    def test_transaction_rollback(self):
        """An exception inside a transaction should roll back uncommitted operations.

        Note: The library's CRUD methods (insert, update, etc.) internally call
        conn.commit(), which commits any open transaction. To test rollback, we
        must use the raw connection directly so that operations remain uncommitted
        until the context manager's rollback is triggered.
        """
        store = StructuredStore(":memory:")
        store.create_table("users", {"name": "TEXT"})
        try:
            with store.begin_transaction():
                conn = store._ensure_connection()
                conn.execute(
                    "INSERT INTO users (id, created_at, updated_at, name) VALUES (?, ?, ?, ?)",
                    ("id-1", 0.0, 0.0, "Alice"),
                )
                conn.execute(
                    "INSERT INTO users (id, created_at, updated_at, name) VALUES (?, ?, ?, ?)",
                    ("id-2", 0.0, 0.0, "Bob"),
                )
                raise RuntimeError("Simulated failure")
        except RuntimeError:
            pass
        assert store.count("users") == 0

    def test_nonexistent_table_error(self):
        """Inserting into a nonexistent table should raise ValueError."""
        store = StructuredStore(":memory:")
        with pytest.raises(ValueError):
            store.insert("nonexistent_table", {"name": "test"})


# ======================================================================
# TestMemoryTable
# ======================================================================


class TestMemoryTable:
    """Tests for the MemoryTable class."""

    def test_init_tables(self):
        """init_tables should create interactions, preferences, and facts tables."""
        store = StructuredStore(":memory:")
        mt = MemoryTable(store)
        mt.init_tables()
        tables = store.list_tables()
        assert "interactions" in tables
        assert "preferences" in tables
        assert "facts" in tables

    def test_log_and_get_interactions(self):
        """Logging an interaction and retrieving it should return the same data."""
        store = StructuredStore(":memory:")
        mt = MemoryTable(store)
        mt.init_tables()
        mt.log_interaction("agent-1", "user", "Hello!")
        interactions = mt.get_interactions("agent-1")
        assert len(interactions) == 1
        assert interactions[0]["role"] == "user"
        assert interactions[0]["content"] == "Hello!"
        assert interactions[0]["agent_id"] == "agent-1"

    def test_store_and_get_preference(self):
        """Storing a preference and retrieving it should return the same value."""
        store = StructuredStore(":memory:")
        mt = MemoryTable(store)
        mt.init_tables()
        mt.store_preference("theme", "dark", "ui")
        pref = mt.get_preference("theme")
        assert pref is not None
        assert pref["value"] == "dark"
        assert pref["category"] == "ui"

    def test_store_fact(self):
        """Storing a fact and retrieving it should return the stored fact."""
        store = StructuredStore(":memory:")
        mt = MemoryTable(store)
        mt.init_tables()
        mt.store_fact("User prefers dark mode", "conversation", 0.9, "ui")
        facts = mt.get_facts(category="ui")
        assert len(facts) == 1
        assert facts[0]["fact"] == "User prefers dark mode"
        assert facts[0]["confidence"] == 0.9

    def test_upsert_preference(self):
        """Storing a preference with the same key twice should update, not duplicate."""
        store = StructuredStore(":memory:")
        mt = MemoryTable(store)
        mt.init_tables()
        mt.store_preference("theme", "dark", "ui")
        mt.store_preference("theme", "light", "ui")
        pref = mt.get_preference("theme")
        assert pref is not None
        assert pref["value"] == "light"
        # There should be only one record for this key
        result = store.select("preferences", where="key = ?", params=("theme",))
        assert result.total == 1
