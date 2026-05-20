from services.audit_log import (
    deserialize_payload,
    list_audit_events,
    record_audit_event,
)
from services.database import initialize_database, managed_connection


def test_record_and_list_audit_events(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        first = record_audit_event(
            connection,
            guild_id=123,
            actor_user_id=456,
            action="guild_config.set_role",
            target="admin_role_id",
            before={"admin_role_id": None},
            after={"admin_role_id": 789},
            created_at="2026-05-20T01:00:00+00:00",
        )
        second = record_audit_event(
            connection,
            guild_id=123,
            actor_user_id=456,
            action="guild_config.set_timezone",
            target="timezone",
            before={"timezone": "UTC"},
            after={"timezone": "Asia/Riyadh"},
            created_at="2026-05-20T02:00:00+00:00",
        )

        assert first.id != second.id

        events = list_audit_events(connection, 123, limit=10)
        assert [event.id for event in events] == [second.id, first.id]
        assert deserialize_payload(events[0].after_json) == {"timezone": "Asia/Riyadh"}


def test_audit_event_limit_is_bounded(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        for index in range(3):
            record_audit_event(
                connection,
                guild_id=123,
                actor_user_id=456,
                action="test",
                target=str(index),
            )

        assert len(list_audit_events(connection, 123, limit=0)) == 1
        assert len(list_audit_events(connection, 123, limit=500)) == 3
