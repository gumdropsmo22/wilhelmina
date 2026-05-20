from services.database import (
    CURRENT_SCHEMA_VERSION,
    connect,
    fetch_schema_versions,
    initialize_database,
)


def test_initialize_database_is_idempotent(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"

    initialize_database(database_path)
    initialize_database(database_path)

    connection = connect(database_path)
    try:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

        assert "schema_migrations" in tables
        assert "guild_config" in tables
        assert "audit_log" in tables
        assert fetch_schema_versions(connection) == [CURRENT_SCHEMA_VERSION]
    finally:
        connection.close()
