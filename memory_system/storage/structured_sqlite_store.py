"""
Structured Store Module - SQLite-based structured storage for Agent memory system.

Provides a thread-safe SQLite storage backend with CRUD operations, advanced queries,
transaction support, and a higher-level MemoryTable abstraction for common Agent
memory patterns such as interaction logging, preference storage, and fact management.
"""

import sqlite3
import time
import uuid
import shutil
import logging
from contextlib import contextmanager
from threading import RLock
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class StructuredRecord(BaseModel):
    """Represents a single structured record stored in the database.

    Attributes:
        id: Unique identifier for the record. Auto-generated via UUID4 if not provided.
        table_name: Name of the table this record belongs to.
        data: Dictionary containing the record's column-value pairs.
        created_at: Unix timestamp of when the record was created.
        updated_at: Unix timestamp of when the record was last updated.
    """

    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    table_name: str
    data: dict = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class QueryResult(BaseModel):
    """Encapsulates the result of a query operation.

    Attributes:
        records: List of dictionaries representing the matching rows.
        total: Total number of matching rows (may exceed len(records) if limit was applied).
        offset: The offset used in the query.
        limit: The limit used in the query.
    """

    records: list[dict] = Field(default_factory=list)
    total: int = 0
    offset: int = 0
    limit: int = 100


class StructuredStore:
    """Thread-safe SQLite-based structured storage engine.

    Supports both file-based and in-memory SQLite databases. All public methods
    are protected by a reentrant lock to ensure thread safety.

    Args:
        db_path: Path to the SQLite database file, or ":memory:" for an in-memory
                 database. Defaults to ":memory:".

    Example::

        store = StructuredStore("agent_memory.db")
        store.create_table("users", {"name": "TEXT", "age": "INTEGER"})
        user_id = store.insert("users", {"name": "Alice", "age": 30})
        result = store.select("users", where="name = ?", params=("Alice",))
        store.close()
    """

    def __init__(self, db_path: str = ":memory:") -> None:
        self._db_path = db_path
        self._lock = RLock()
        self._connection: Optional[sqlite3.Connection] = None
        self._connect()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _connect(self) -> None:
        """Establish a new SQLite connection with row factory and foreign keys enabled."""
        self._connection = sqlite3.connect(
            self._db_path, check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")

    def _ensure_connection(self) -> sqlite3.Connection:
        """Return the active connection, reconnecting if necessary."""
        if self._connection is None:
            self._connect()
        # Verify the connection is still alive
        try:
            self._connection.execute("SELECT 1")
        except sqlite3.Error:
            self._connect()
        return self._connection

    def _table_exists(self, table_name: str) -> bool:
        """Check whether a table exists in the database.

        Args:
            table_name: Name of the table to check.

        Returns:
            True if the table exists, False otherwise.
        """
        cursor = self._ensure_connection().execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return cursor.fetchone() is not None

    # ------------------------------------------------------------------
    # Table management
    # ------------------------------------------------------------------

    def create_table(self, table_name: str, columns: dict[str, str]) -> bool:
        """Create a new table with the specified columns.

        Every table automatically includes an ``id`` (TEXT PRIMARY KEY),
        ``created_at`` (REAL), and ``updated_at`` (REAL) column in addition
        to the user-specified columns.

        Args:
            table_name: Name of the table to create.
            columns: Mapping of column names to their SQLite type declarations,
                     e.g. ``{"name": "TEXT", "age": "INTEGER"}``.

        Returns:
            True if the table was created successfully, False otherwise.
        """
        with self._lock:
            try:
                col_defs = ["id TEXT PRIMARY KEY", "created_at REAL NOT NULL", "updated_at REAL NOT NULL"]
                for col_name, col_type in columns.items():
                    col_defs.append(f"{col_name} {col_type}")
                sql = f"CREATE TABLE IF NOT EXISTS [{table_name}] ({', '.join(col_defs)})"
                self._ensure_connection().execute(sql)
                self._ensure_connection().commit()
                return True
            except sqlite3.Error:
                return False

    def create_fts5_table(self, fts_table_name: str, source_table: str, columns: list[str], tokenize: str = "unicode61") -> bool:
        """创建 FTS5 全文搜索虚拟表

        Args:
            fts_table_name: FTS5 虚拟表名
            source_table: 源数据表名
            columns: 需要全文索引的列名列表
            tokenize: 分词器 (默认 "unicode61")

        Returns:
            是否创建成功
        """
        try:
            conn = self._ensure_connection()
            # Drop existing FTS table if exists
            conn.execute(f"DROP TABLE IF EXISTS [{fts_table_name}]")
            # Create FTS5 virtual table
            col_defs = ", ".join(columns)
            conn.execute(
                f"CREATE VIRTUAL TABLE [{fts_table_name}] USING fts5({col_defs}, content=[{source_table}], tokenize='{tokenize}')"
            )
            conn.commit()
            logger.info("Created FTS5 table '%s' for source '%s' with columns %s", fts_table_name, source_table, columns)
            return True
        except sqlite3.Error as e:
            logger.error("Failed to create FTS5 table: %s", e)
            return False

    def search_fts5(self, fts_table_name: str, query: str, limit: int = 20) -> list[dict]:
        """使用 FTS5 进行全文搜索

        Args:
            fts_table_name: FTS5 虚拟表名
            query: 搜索查询（支持 FTS5 语法）
            limit: 最大返回数量

        Returns:
            匹配的记录列表
        """
        try:
            conn = self._ensure_connection()
            cursor = conn.execute(
                f"SELECT * FROM [{fts_table_name}] WHERE [{fts_table_name}] MATCH ? ORDER BY rank LIMIT ?",
                (query, limit),
            )
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error("FTS5 search failed: %s", e)
            return []

    def drop_table(self, table_name: str) -> bool:
        """Drop a table from the database.

        Args:
            table_name: Name of the table to drop.

        Returns:
            True if the table was dropped successfully, False otherwise.
        """
        with self._lock:
            try:
                self._ensure_connection().execute(f"DROP TABLE IF EXISTS [{table_name}]")
                self._ensure_connection().commit()
                return True
            except sqlite3.Error:
                return False

    def list_tables(self) -> list[str]:
        """List all user tables in the database.

        Returns:
            A list of table names. Internal SQLite tables (e.g. sqlite_sequence)
            are excluded.
        """
        with self._lock:
            cursor = self._ensure_connection().execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
            return [row["name"] for row in cursor.fetchall()]

    def table_info(self, table_name: str) -> Optional[dict]:
        """Retrieve column information for a table.

        Args:
            table_name: Name of the table.

        Returns:
            A dictionary with the key ``"columns"`` mapping to a list of dicts
            each containing ``"name"``, ``"type"``, ``"notnull"``, ``"dflt_value"``,
            and ``"pk"``. Returns ``None`` if the table does not exist.
        """
        with self._lock:
            if not self._table_exists(table_name):
                return None
            cursor = self._ensure_connection().execute(f"PRAGMA table_info([{table_name}])")
            columns = [
                {
                    "name": row["name"],
                    "type": row["type"],
                    "notnull": bool(row["notnull"]),
                    "dflt_value": row["dflt_value"],
                    "pk": row["pk"],
                }
                for row in cursor.fetchall()
            ]
            return {"columns": columns}

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def insert(self, table_name: str, data: dict) -> str:
        """Insert a single record into a table.

        Args:
            table_name: Name of the target table.
            data: Dictionary of column-value pairs to insert. The ``id``,
                  ``created_at``, and ``updated_at`` fields are auto-generated
                  if not provided.

        Returns:
            The ``id`` of the newly inserted record.

        Raises:
            ValueError: If the table does not exist.
        """
        with self._lock:
            if not self._table_exists(table_name):
                raise ValueError(f"Table '{table_name}' does not exist.")

            row = dict(data)  # copy to avoid mutating caller's dict
            record_id = row.pop("id", str(uuid.uuid4()))
            now = time.time()
            created_at = row.pop("created_at", now)
            updated_at = row.pop("updated_at", now)

            columns = ["id", "created_at", "updated_at"] + list(row.keys())
            placeholders = ", ".join(["?"] * len(columns))
            col_str = ", ".join(f"[{c}]" for c in columns)
            values = [record_id, created_at, updated_at] + list(row.values())

            self._ensure_connection().execute(
                f"INSERT INTO [{table_name}] ({col_str}) VALUES ({placeholders})",
                values,
            )
            self._ensure_connection().commit()
            return record_id

    def insert_batch(self, table_name: str, records: list[dict]) -> list[str]:
        """Insert multiple records into a table in a single transaction.

        Args:
            table_name: Name of the target table.
            records: List of dictionaries, each representing a row to insert.

        Returns:
            A list of ``id`` values for the inserted records, in order.

        Raises:
            ValueError: If the table does not exist or ``records`` is empty.
        """
        with self._lock:
            if not self._table_exists(table_name):
                raise ValueError(f"Table '{table_name}' does not exist.")
            if not records:
                raise ValueError("records list must not be empty.")

            conn = self._ensure_connection()
            ids: list[str] = []
            now = time.time()

            try:
                for data in records:
                    row = dict(data)  # copy to avoid mutating caller's dict
                    record_id = row.pop("id", str(uuid.uuid4()))
                    created_at = row.pop("created_at", now)
                    updated_at = row.pop("updated_at", now)

                    columns = ["id", "created_at", "updated_at"] + list(row.keys())
                    placeholders = ", ".join(["?"] * len(columns))
                    col_str = ", ".join(f"[{c}]" for c in columns)
                    values = [record_id, created_at, updated_at] + list(row.values())

                    conn.execute(
                        f"INSERT INTO [{table_name}] ({col_str}) VALUES ({placeholders})",
                        values,
                    )
                    ids.append(record_id)
                conn.commit()
            except sqlite3.Error:
                conn.rollback()
                raise

            return ids

    def select(
        self,
        table_name: str,
        columns: list[str] = None,
        where: str = None,
        params: tuple = None,
        order_by: str = None,
        limit: int = 100,
        offset: int = 0,
    ) -> QueryResult:
        """Query records from a table.

        Args:
            table_name: Name of the table to query.
            columns: List of column names to return. ``None`` or empty list
                     means ``SELECT *``.
            where: Optional SQL WHERE clause (without the ``WHERE`` keyword).
            params: Parameters to bind to the WHERE clause.
            order_by: Optional SQL ORDER BY clause (without the ``ORDER BY`` keyword).
            limit: Maximum number of rows to return. Defaults to 100.
            offset: Number of rows to skip. Defaults to 0.

        Returns:
            A ``QueryResult`` containing the matching records and metadata.

        Raises:
            ValueError: If the table does not exist.
        """
        with self._lock:
            if not self._table_exists(table_name):
                raise ValueError(f"Table '{table_name}' does not exist.")

            conn = self._ensure_connection()

            # Build SELECT columns
            col_str = ", ".join(f"[{c}]" for c in columns) if columns else "*"

            # Build WHERE
            where_clause = f"WHERE {where}" if where else ""

            # Count total matching rows
            count_sql = f"SELECT COUNT(*) AS cnt FROM [{table_name}] {where_clause}"
            count_params = params or ()
            total = conn.execute(count_sql, count_params).fetchone()["cnt"]

            # Build ORDER BY
            order_clause = f"ORDER BY {order_by}" if order_by else ""

            # Fetch rows
            query_sql = f"SELECT {col_str} FROM [{table_name}] {where_clause} {order_clause} LIMIT ? OFFSET ?"
            query_params = (params or ()) + (limit, offset)
            cursor = conn.execute(query_sql, query_params)
            rows = [dict(row) for row in cursor.fetchall()]

            return QueryResult(records=rows, total=total, offset=offset, limit=limit)

    def update(
        self,
        table_name: str,
        data: dict,
        where: str = None,
        params: tuple = None,
    ) -> int:
        """Update records in a table.

        Args:
            table_name: Name of the table to update.
            data: Dictionary of column-value pairs to set.
            where: Optional SQL WHERE clause. If ``None``, all rows are updated.
            params: Parameters to bind to the WHERE clause.

        Returns:
            The number of rows affected.

        Raises:
            ValueError: If the table does not exist or ``data`` is empty.
        """
        with self._lock:
            if not self._table_exists(table_name):
                raise ValueError(f"Table '{table_name}' does not exist.")
            if not data:
                raise ValueError("data dictionary must not be empty.")

            conn = self._ensure_connection()
            now = time.time()

            # Always update the updated_at timestamp
            data["updated_at"] = now
            set_clause = ", ".join(f"[{k}] = ?" for k in data)
            values = list(data.values())

            where_clause = f"WHERE {where}" if where else ""
            sql = f"UPDATE [{table_name}] SET {set_clause} {where_clause}"
            final_params = tuple(values) + (params or ())

            cursor = conn.execute(sql, final_params)
            conn.commit()
            return cursor.rowcount

    def delete(
        self,
        table_name: str,
        where: str = None,
        params: tuple = None,
    ) -> int:
        """Delete records from a table.

        Args:
            table_name: Name of the table.
            where: Optional SQL WHERE clause. If ``None``, all rows are deleted.
            params: Parameters to bind to the WHERE clause.

        Returns:
            The number of rows deleted.

        Raises:
            ValueError: If the table does not exist.
        """
        with self._lock:
            if not self._table_exists(table_name):
                raise ValueError(f"Table '{table_name}' does not exist.")

            conn = self._ensure_connection()
            where_clause = f"WHERE {where}" if where else ""
            sql = f"DELETE FROM [{table_name}] {where_clause}"

            cursor = conn.execute(sql, params or ())
            conn.commit()
            return cursor.rowcount

    def count(
        self,
        table_name: str,
        where: str = None,
        params: tuple = None,
    ) -> int:
        """Count records in a table.

        Args:
            table_name: Name of the table.
            where: Optional SQL WHERE clause.
            params: Parameters to bind to the WHERE clause.

        Returns:
            The number of matching rows.

        Raises:
            ValueError: If the table does not exist.
        """
        with self._lock:
            if not self._table_exists(table_name):
                raise ValueError(f"Table '{table_name}' does not exist.")

            conn = self._ensure_connection()
            where_clause = f"WHERE {where}" if where else ""
            sql = f"SELECT COUNT(*) AS cnt FROM [{table_name}] {where_clause}"

            return conn.execute(sql, params or ()).fetchone()["cnt"]

    # ------------------------------------------------------------------
    # Advanced queries
    # ------------------------------------------------------------------

    def execute_sql(self, sql: str, params: tuple = None) -> list[dict]:
        """Execute a raw SQL statement and return the results as dictionaries.

        This method supports SELECT statements. For DDL/DML statements use
        the transaction context manager or individual CRUD methods.

        Args:
            sql: The SQL statement to execute.
            params: Optional parameters to bind.

        Returns:
            A list of dictionaries representing the result rows. Returns an
            empty list for non-SELECT statements.
        """
        with self._lock:
            conn = self._ensure_connection()
            cursor = conn.execute(sql, params or ())
            if cursor.description is None:
                conn.commit()
                return []
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def search_fulltext(
        self,
        table_name: str,
        query: str,
        columns: list[str] = None,
        limit: int = 20,
    ) -> QueryResult:
        """Perform a LIKE-based full-text search across columns of a table.

        Constructs a WHERE clause that searches for *query* (with ``%`` wildcards
        on both sides) in every text column of the table, combined with OR.

        Args:
            table_name: Name of the table to search.
            query: The search string.
            columns: Optional list of columns to search. If ``None``, all TEXT
                     columns of the table are searched.
            limit: Maximum number of results. Defaults to 20.

        Returns:
            A ``QueryResult`` containing the matching records.

        Raises:
            ValueError: If the table does not exist.
        """
        with self._lock:
            if not self._table_exists(table_name):
                raise ValueError(f"Table '{table_name}' does not exist.")

            conn = self._ensure_connection()

            # Determine which columns to search
            if columns is None:
                info = self.table_info(table_name)
                columns = [col["name"] for col in info["columns"] if "TEXT" in col["type"].upper()]
                # Always include the auto-managed columns that might hold text
                if not columns:
                    columns = [col["name"] for col in info["columns"]]

            # Build LIKE conditions
            like_pattern = f"%{query}%"
            conditions = []
            params: list = []
            for col in columns:
                conditions.append(f"CAST([{col}] AS TEXT) LIKE ?")
                params.append(like_pattern)

            where_clause = " OR ".join(conditions)

            # Count total matches
            count_sql = f"SELECT COUNT(*) AS cnt FROM [{table_name}] WHERE {where_clause}"
            total = conn.execute(count_sql, tuple(params)).fetchone()["cnt"]

            # Fetch results
            select_sql = f"SELECT * FROM [{table_name}] WHERE {where_clause} LIMIT ?"
            cursor = conn.execute(select_sql, tuple(params) + (limit,))
            rows = [dict(row) for row in cursor.fetchall()]

            return QueryResult(records=rows, total=total, offset=0, limit=limit)

    # ------------------------------------------------------------------
    # Transaction support
    # ------------------------------------------------------------------

    @contextmanager
    def begin_transaction(self):
        """Context manager for executing operations within a transaction.

        Commits on successful exit, rolls back on exception.

        Example::

            with store.begin_transaction():
                store.insert("users", {"name": "Alice"})
                store.insert("users", {"name": "Bob"})
            # Both inserts are committed atomically.
        """
        conn = self._ensure_connection()
        self._lock.acquire()
        try:
            conn.execute("BEGIN")
            yield self
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._lock.release()

    # ------------------------------------------------------------------
    # Schema management
    # ------------------------------------------------------------------

    def add_column(self, table_name: str, column_name: str, column_type: str) -> bool:
        """Add a new column to an existing table.

        Args:
            table_name: Name of the table.
            column_name: Name of the column to add.
            column_type: SQLite type declaration for the new column.

        Returns:
            True if the column was added successfully, False otherwise.
        """
        with self._lock:
            if not self._table_exists(table_name):
                return False
            try:
                self._ensure_connection().execute(
                    f"ALTER TABLE [{table_name}] ADD COLUMN [{column_name}] {column_type}"
                )
                self._ensure_connection().commit()
                return True
            except sqlite3.Error:
                return False

    def ensure_table(self, table_name: str, columns: dict[str, str]) -> bool:
        """Create a table if it does not already exist.

        This is a safe no-op when the table is already present.

        Args:
            table_name: Name of the table.
            columns: Mapping of column names to SQLite type declarations.

        Returns:
            True if the table exists (either already or after creation).
        """
        with self._lock:
            if self._table_exists(table_name):
                return True
            return self.create_table(table_name, columns)

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def vacuum(self) -> None:
        """Rebuild the database file, reclaiming unused space.

        This is a no-op for in-memory databases.
        """
        with self._lock:
            if self._db_path != ":memory:":
                self._ensure_connection().execute("VACUUM")

    def close(self) -> None:
        """Close the database connection and release resources."""
        with self._lock:
            if self._connection is not None:
                self._connection.close()
                self._connection = None

    def backup(self, destination: str) -> bool:
        """Create a backup of the database to *destination*.

        For file-based databases this uses SQLite's built-in backup API.
        For in-memory databases the backup is written to the specified file path.

        Args:
            destination: Path where the backup database file will be written.

        Returns:
            True if the backup succeeded, False otherwise.
        """
        with self._lock:
            try:
                source_conn = self._ensure_connection()
                dest_conn = sqlite3.connect(destination)
                source_conn.backup(dest_conn)
                dest_conn.close()
                return True
            except sqlite3.Error:
                return False


class MemoryTable:
    """Higher-level abstraction for common Agent memory patterns.

    Provides pre-configured tables and convenience methods for logging
    interactions, storing preferences, and managing facts.

    The following tables are created by :meth:`init_tables`:

    - **interactions**: ``agent_id (TEXT)``, ``role (TEXT)``, ``content (TEXT)``,
      ``metadata (TEXT)``
    - **preferences**: ``key (TEXT)``, ``value (TEXT)``, ``category (TEXT)``
    - **facts**: ``fact (TEXT)``, ``source (TEXT)``, ``confidence (REAL)``,
      ``category (TEXT)``

    Args:
        store: A :class:`StructuredStore` instance to use as the backend.

    Example::

        store = StructuredStore("agent.db")
        memory = MemoryTable(store)
        memory.init_tables()

        interaction_id = memory.log_interaction("agent-1", "user", "Hello!")
        pref_id = memory.store_preference("theme", "dark", "ui")
        fact_id = memory.store_fact("User prefers dark mode", "conversation", 0.9)
    """

    INTERACTIONS_TABLE = "interactions"
    PREFERENCES_TABLE = "preferences"
    FACTS_TABLE = "facts"

    def __init__(self, store: StructuredStore) -> None:
        self._store = store

    def init_tables(self) -> None:
        """Create all predefined tables if they do not already exist.

        Creates the *interactions*, *preferences*, and *facts* tables with
        their respective schemas.
        """
        self._store.ensure_table(
            self.INTERACTIONS_TABLE,
            {
                "agent_id": "TEXT NOT NULL",
                "role": "TEXT NOT NULL",
                "content": "TEXT NOT NULL",
                "metadata": "TEXT",
            },
        )
        self._store.ensure_table(
            self.PREFERENCES_TABLE,
            {
                "key": "TEXT NOT NULL",
                "value": "TEXT NOT NULL",
                "category": "TEXT NOT NULL DEFAULT 'general'",
            },
        )
        self._store.ensure_table(
            self.FACTS_TABLE,
            {
                "fact": "TEXT NOT NULL",
                "source": "TEXT NOT NULL",
                "confidence": "REAL NOT NULL DEFAULT 1.0",
                "category": "TEXT",
            },
        )

    def log_interaction(
        self,
        agent_id: str,
        role: str,
        content: str,
        metadata: dict = None,
    ) -> str:
        """Log an interaction to the interactions table.

        Args:
            agent_id: Identifier of the agent involved in the interaction.
            role: Role of the speaker (e.g. ``"user"``, ``"assistant"``).
            content: The text content of the interaction.
            metadata: Optional additional metadata. Will be serialised as a
                      JSON string if provided.

        Returns:
            The ``id`` of the inserted interaction record.
        """
        import json

        meta_str = json.dumps(metadata) if metadata is not None else None
        return self._store.insert(
            self.INTERACTIONS_TABLE,
            {
                "agent_id": agent_id,
                "role": role,
                "content": content,
                "metadata": meta_str,
            },
        )

    def get_interactions(
        self,
        agent_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Retrieve interactions for a given agent, ordered by creation time.

        Args:
            agent_id: Identifier of the agent.
            limit: Maximum number of records to return. Defaults to 50.
            offset: Number of records to skip. Defaults to 0.

        Returns:
            A list of interaction dictionaries.
        """
        result = self._store.select(
            self.INTERACTIONS_TABLE,
            where="agent_id = ?",
            params=(agent_id,),
            order_by="created_at DESC",
            limit=limit,
            offset=offset,
        )
        return result.records

    def store_preference(
        self,
        key: str,
        value: str,
        category: str = "general",
    ) -> str:
        """Store or update a user preference.

        If a preference with the same *key* already exists its value and
        category are updated; otherwise a new row is inserted.

        Args:
            key: Unique preference key.
            value: The preference value.
            category: Optional category for grouping preferences. Defaults to
                      ``"general"``.

        Returns:
            The ``id`` of the upserted preference record.
        """
        # Check if the key already exists
        existing = self._store.select(
            self.PREFERENCES_TABLE,
            where="key = ?",
            params=(key,),
            limit=1,
        )
        if existing.records:
            record = existing.records[0]
            self._store.update(
                self.PREFERENCES_TABLE,
                {"value": value, "category": category},
                where="key = ?",
                params=(key,),
            )
            return record["id"]

        return self._store.insert(
            self.PREFERENCES_TABLE,
            {"key": key, "value": value, "category": category},
        )

    def get_preference(self, key: str) -> Optional[dict]:
        """Retrieve a single preference by key.

        Args:
            key: The preference key to look up.

        Returns:
            A dictionary representing the preference row, or ``None`` if not found.
        """
        result = self._store.select(
            self.PREFERENCES_TABLE,
            where="key = ?",
            params=(key,),
            limit=1,
        )
        if result.records:
            return result.records[0]
        return None

    def store_fact(
        self,
        fact: str,
        source: str,
        confidence: float = 1.0,
        category: str = None,
    ) -> str:
        """Store a fact in the facts table.

        Args:
            fact: The factual statement to store.
            source: Provenance of the fact (e.g. ``"conversation"``, ``"document"``).
            confidence: Confidence score between 0.0 and 1.0. Defaults to 1.0.
            category: Optional category for grouping facts.

        Returns:
            The ``id`` of the inserted fact record.
        """
        data: dict = {
            "fact": fact,
            "source": source,
            "confidence": confidence,
        }
        if category is not None:
            data["category"] = category
        return self._store.insert(self.FACTS_TABLE, data)

    def get_facts(
        self,
        category: str = None,
        limit: int = 50,
    ) -> list[dict]:
        """Retrieve facts, optionally filtered by category.

        Results are ordered by confidence descending.

        Args:
            category: If provided, only facts in this category are returned.
            limit: Maximum number of facts to return. Defaults to 50.

        Returns:
            A list of fact dictionaries.
        """
        if category is not None:
            result = self._store.select(
                self.FACTS_TABLE,
                where="category = ?",
                params=(category,),
                order_by="confidence DESC",
                limit=limit,
            )
        else:
            result = self._store.select(
                self.FACTS_TABLE,
                order_by="confidence DESC",
                limit=limit,
            )
        return result.records


__all__ = [
    "StructuredRecord",
    "QueryResult",
    "StructuredStore",
    "MemoryTable",
]
