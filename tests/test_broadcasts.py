from datetime import date

from services import broadcasts
from services.database import initialize_database, managed_connection


def test_default_broadcast_settings_are_riyadh_and_disabled(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        settings = broadcasts.ensure_broadcast_settings(connection, 123)

    assert settings.timezone == "Asia/Riyadh"
    assert settings.morning_time == "08:00"
    assert settings.evening_time == "21:30"
    assert settings.morning_enabled is False
    assert settings.evening_enabled is False
    assert settings.news_provider == "tba"


def test_update_segment_time_and_enablement(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        broadcasts.ensure_broadcast_settings(connection, 123)
        _, settings = broadcasts.set_segment_time(connection, 123, "evening", "21:30")
        _, settings = broadcasts.set_segment_enabled(connection, 123, "evening", True)

    assert settings.evening_time == "21:30"
    assert settings.evening_enabled is True


def test_scheduled_run_claim_is_idempotent(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        first = broadcasts.claim_scheduled_run(
            connection,
            guild_id=123,
            segment="morning",
            logical_date="2026-07-12",
            scheduled_for="2026-07-12T08:00:00+03:00",
        )
        second = broadcasts.claim_scheduled_run(
            connection,
            guild_id=123,
            segment="morning",
            logical_date="2026-07-12",
            scheduled_for="2026-07-12T08:00:00+03:00",
        )

    assert first is not None
    assert second is None


def test_prompt_preserves_contract_and_evidence_boundaries(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        settings = broadcasts.ensure_broadcast_settings(connection, 123)

    evidence = broadcasts.build_empty_evidence(settings, "morning")
    prompt = broadcasts.build_broadcast_prompt(settings=settings, evidence=evidence)

    assert "The Vanguard Frequency" in prompt
    assert "Evidence packet" in prompt
    assert "Do not invent" in prompt or "omit it instead of inventing" in prompt
    assert "News provider is TBA" in prompt


def test_deterministic_fallback_refuses_to_fabricate(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        settings = broadcasts.ensure_broadcast_settings(connection, 123)

    evidence = broadcasts.build_empty_evidence(settings, "evening")
    fallback = broadcasts.render_deterministic_broadcast(evidence=evidence)

    assert "W.W.N. Broadcast" in fallback
    assert "No unsupported prophecy" in fallback
    assert "no factual headline rundown" not in fallback


def test_local_broadcast_datetime_uses_configured_segment_time(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        settings = broadcasts.ensure_broadcast_settings(connection, 123)

    scheduled = broadcasts.local_broadcast_datetime(settings, "morning", date(2026, 7, 12))

    assert scheduled.isoformat(timespec="minutes") == "2026-07-12T08:00+03:00"
