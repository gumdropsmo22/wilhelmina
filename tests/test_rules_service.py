from services.database import connect, initialize_database
from services import rules


def test_rules_version_activation_and_acceptance_are_idempotent(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)
    connection = connect(database_path)
    try:
        stored = rules.upsert_rules_version(
            connection,
            guild_id=123,
            version_tag="v1",
            title="The Covenant",
            intro_text="Read before crossing.",
            body_text="Be kind. No spam. No cruelty.",
            accept_label="I accept the covenant",
            actor_user_id=999,
        )
        assert stored.is_active is False

        active = rules.activate_rules_version(
            connection,
            guild_id=123,
            version_tag="v1",
            actor_user_id=999,
        )
        assert active.is_active is True

        first = rules.accept_active_rules(
            connection,
            guild_id=123,
            user_id=456,
            accepted_via="button",
        )
        second = rules.accept_active_rules(
            connection,
            guild_id=123,
            user_id=456,
            accepted_via="button",
        )

        assert first.already_accepted is False
        assert second.already_accepted is True
        assert first.acceptance.rules_version_id == active.id
        assert second.acceptance.rules_version_id == active.id

        summary = rules.summarize_acceptance(connection, guild_id=123)
        assert summary.version_tag == "v1"
        assert summary.accepted_count == 1
    finally:
        connection.close()


def test_only_one_rules_version_can_be_active(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)
    connection = connect(database_path)
    try:
        for version_tag in ("v1", "v2"):
            rules.upsert_rules_version(
                connection,
                guild_id=123,
                version_tag=version_tag,
                title=f"The Covenant {version_tag}",
                intro_text="Read before crossing.",
                body_text="Be kind.",
                accept_label="I accept",
                actor_user_id=999,
            )

        first = rules.activate_rules_version(
            connection,
            guild_id=123,
            version_tag="v1",
            actor_user_id=999,
        )
        second = rules.activate_rules_version(
            connection,
            guild_id=123,
            version_tag="v2",
            actor_user_id=999,
        )

        refreshed_first = rules.get_rules_version_by_id(connection, first.id)
        assert refreshed_first.is_active is False
        assert second.is_active is True
        assert rules.get_active_rules(connection, guild_id=123).version_tag == "v2"
    finally:
        connection.close()
