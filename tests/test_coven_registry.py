from services import coven_registry as registry
from services.database import connect, initialize_database, managed_connection


def _bootstrap(path):
    initialize_database(path)
    with managed_connection(path) as connection:
        return registry.bootstrap_registry(
            connection,
            guild_id=1,
            wilhelmina_user_id=100,
            founder_user_id=200,
            founder_name="Founder",
            actor_user_id=200,
        )


def test_bootstrap_reserves_zero_and_one(tmp_path):
    path = tmp_path / "registry.sqlite3"
    result = _bootstrap(path)
    assert result.wilhelmina.canonical_id == "WTCH-0000"
    assert result.wilhelmina.display_mark == "⛧WTCH-0000⛧"
    assert result.founder.canonical_id == "WTCH-0001"
    assert result.settings.next_number == 2


def test_join_creates_pending_entry_and_profile_shell(tmp_path):
    path = tmp_path / "registry.sqlite3"
    _bootstrap(path)
    with managed_connection(path) as connection:
        result = registry.register_pending_member(
            connection,
            guild_id=1,
            user_id=300,
            display_name="New Witch",
            actor_user_id=300,
        )
        shell = registry.get_profile_shell(connection, guild_id=1, user_id=300)
    assert result.created is True
    assert result.entry.canonical_id == "WTCH-0002"
    assert result.entry.classification == "Pending"
    assert shell is not None
    assert shell.memory_opt_out is False


def test_duplicate_join_preserves_mark(tmp_path):
    path = tmp_path / "registry.sqlite3"
    _bootstrap(path)
    with managed_connection(path) as connection:
        first = registry.register_pending_member(
            connection,
            guild_id=1,
            user_id=300,
            display_name="First Name",
            actor_user_id=300,
        )
        second = registry.register_pending_member(
            connection,
            guild_id=1,
            user_id=300,
            display_name="Second Name",
            actor_user_id=300,
        )
    assert second.created is False
    assert second.entry.canonical_id == first.entry.canonical_id
    assert second.entry.display_name == "Second Name"


def test_covenant_acceptance_inducts_once(tmp_path):
    path = tmp_path / "registry.sqlite3"
    _bootstrap(path)
    with managed_connection(path) as connection:
        registry.register_pending_member(
            connection,
            guild_id=1,
            user_id=300,
            display_name="Initiate",
            actor_user_id=300,
        )
        first = registry.induct_member(
            connection,
            guild_id=1,
            user_id=300,
            covenant_version_id=7,
            actor_user_id=300,
        )
        second = registry.induct_member(
            connection,
            guild_id=1,
            user_id=300,
            covenant_version_id=7,
            actor_user_id=300,
        )
    assert first.entry.classification == "Initiate"
    assert first.newly_inducted is True
    assert first.notice_required is True
    assert second.newly_inducted is False


def test_decorated_mark_lookup(tmp_path):
    path = tmp_path / "registry.sqlite3"
    _bootstrap(path)
    with managed_connection(path) as connection:
        registry.register_pending_member(
            connection,
            guild_id=1,
            user_id=300,
            display_name="Marked",
            actor_user_id=300,
        )
        entry = registry.get_entry_by_mark(connection, guild_id=1, mark="⛧wtch-0002⛧")
    assert entry.user_id == 300


def test_backfill_is_deterministic(tmp_path):
    path = tmp_path / "registry.sqlite3"
    _bootstrap(path)
    with managed_connection(path) as connection:
        results = registry.backfill_members(
            connection,
            guild_id=1,
            members=[
                (302, "Later", "2026-02-01T00:00:00+00:00"),
                (301, "Earlier", "2026-01-01T00:00:00+00:00"),
            ],
            actor_user_id=200,
        )
    assert [item.entry.user_id for item in results] == [301, 302]
    assert [item.entry.canonical_id for item in results] == ["WTCH-0002", "WTCH-0003"]


def test_schema_version_and_tables_are_created(tmp_path):
    path = tmp_path / "registry.sqlite3"
    _bootstrap(path)
    connection = connect(path)
    try:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        versions = {
            int(row["version"])
            for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
        }
    finally:
        connection.close()
    assert "coven_registry_settings" in tables
    assert "coven_registry_entries" in tables
    assert "coven_profile_shells" in tables
    assert registry.REGISTRY_SCHEMA_VERSION in versions
