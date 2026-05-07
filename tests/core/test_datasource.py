import pytest

from aurora_core.datasource.rdbms.sqlite import SQLiteConnector


def test_sqlite_connector_in_memory():
    conn = SQLiteConnector(":memory:")
    assert conn.db_type == "sqlite"
    # Create a table
    conn.run("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
    conn.run("INSERT INTO users (name) VALUES ('Alice')")
    tables = conn.get_table_names()
    assert "users" in tables
    schema = conn.get_table_schema("users")
    assert "id" in schema
    assert "name" in schema
    result = conn.query("SELECT * FROM users")
    assert len(result) == 1
    assert result[0]["name"] == "Alice"


def test_sqlite_connector_run():
    conn = SQLiteConnector(":memory:")
    success, result = conn.run("CREATE TABLE t (id INTEGER)")
    assert success is True
    success, result = conn.run("SELECT * FROM t")
    assert success is True
