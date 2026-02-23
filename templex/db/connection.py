"""KuzuDB connection manager — singleton pattern, disk-backed."""

import kuzu
from pathlib import Path
from templex.config import DB_DIR


class KuzuConnection:
    """Manages a single KuzuDB database instance and connection."""

    _db: kuzu.Database | None = None
    _conn: kuzu.Connection | None = None

    @classmethod
    def get_db(cls) -> kuzu.Database:
        if cls._db is None:
            # KuzuDB v0.11+ manages its own directory creation
            DB_DIR.parent.mkdir(parents=True, exist_ok=True)
            cls._db = kuzu.Database(str(DB_DIR))
        return cls._db

    @classmethod
    def get_connection(cls) -> kuzu.Connection:
        if cls._conn is None:
            cls._conn = kuzu.Connection(cls.get_db())
        return cls._conn

    @classmethod
    def execute(cls, query: str, params: dict | None = None):
        """Execute a Cypher query and return results."""
        conn = cls.get_connection()
        if params:
            return conn.execute(query, params)
        return conn.execute(query)

    @classmethod
    def reset(cls):
        """Close connection and database (for testing)."""
        cls._conn = None
        cls._db = None
