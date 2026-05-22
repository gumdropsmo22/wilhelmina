from services import audit_log, onboarding
from services.database import initialize_database, managed_connection


def test_start_onboarding_creates_pending_record_and_audit(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        before, after = onboarding.start_onboarding(
            connection,
            123,
            456,
            actor_user_id=9001,
            notes="arrived",
        )
        events = audit_log.list_audit_events(connection, 123)

    assert before is None
    assert after.guild_id == 123
    assert after.user_id == 456
    assert after.state == onboarding.PENDING
    assert after.notes == "arrived"
    assert len(events) == 1
    assert events[0].action == "onboarding.start"
    assert events[0].target == "456"


def test_approve_then_complete_onboarding(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        onboarding.start_onboarding(connection, 123, 456, actor_user_id=9001)
        before_approve, approved = onboarding.approve_onboarding(
            connection,
            123,
            456,
            actor_user_id=9002,
            notes="approved manually",
        )
        before_complete, completed = onboarding.complete_onboarding(
            connection,
            123,
            456,
            actor_user_id=9003,
        )
        events = audit_log.list_audit_events(connection, 123, limit=10)

    assert before_approve.state == onboarding.PENDING
    assert approved.state == onboarding.APPROVED
    assert approved.approved_by == 9002
    assert approved.notes == "approved manually"
    assert before_complete.state == onboarding.APPROVED
    assert completed.state == onboarding.COMPLETED
    assert completed.completed_at is not None
    assert completed.approved_by == 9002
    assert [event.action for event in reversed(events)] == [
        "onboarding.start",
        "onboarding.approve",
        "onboarding.complete",
    ]


def test_reject_onboarding_sets_rejected_state(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        onboarding.start_onboarding(connection, 123, 456, actor_user_id=9001)
        _, rejected = onboarding.reject_onboarding(
            connection,
            123,
            456,
            actor_user_id=9004,
            notes="not ready",
        )

    assert rejected.state == onboarding.REJECTED
    assert rejected.rejected_by == 9004
    assert rejected.approved_by is None
    assert rejected.notes == "not ready"


def test_terminal_state_requires_override_for_different_transition(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        onboarding.start_onboarding(connection, 123, 456, actor_user_id=9001)
        onboarding.reject_onboarding(connection, 123, 456, actor_user_id=9002)
        try:
            onboarding.approve_onboarding(connection, 123, 456, actor_user_id=9003)
        except onboarding.InvalidOnboardingTransition as exc:
            assert "terminal state" in str(exc)
        else:
            raise AssertionError("expected InvalidOnboardingTransition")


def test_complete_requires_approved_state(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        onboarding.start_onboarding(connection, 123, 456, actor_user_id=9001)
        try:
            onboarding.complete_onboarding(connection, 123, 456, actor_user_id=9003)
        except onboarding.InvalidOnboardingTransition as exc:
            assert "only approved" in str(exc)
        else:
            raise AssertionError("expected InvalidOnboardingTransition")


def test_override_state_creates_or_updates_record(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        before, after = onboarding.override_state(
            connection,
            123,
            456,
            state="approved",
            actor_user_id=9001,
            notes="manual correction",
        )
        fetched = onboarding.get_onboarding_record(connection, 123, 456)
        events = audit_log.list_audit_events(connection, 123)

    assert before is None
    assert after.state == onboarding.APPROVED
    assert after.approved_by == 9001
    assert after.notes == "manual correction"
    assert fetched == after
    assert events[0].action == "onboarding.override"


def test_list_onboarding_records_filters_by_state(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        onboarding.start_onboarding(connection, 123, 456, actor_user_id=9001)
        onboarding.start_onboarding(connection, 123, 789, actor_user_id=9001)
        onboarding.approve_onboarding(connection, 123, 789, actor_user_id=9002)

        all_records = onboarding.list_onboarding_records(connection, 123)
        approved_records = onboarding.list_onboarding_records(
            connection,
            123,
            state="approved",
        )

    assert {record.user_id for record in all_records} == {456, 789}
    assert [record.user_id for record in approved_records] == [789]


def test_summarize_onboarding_counts_records_by_state(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        onboarding.start_onboarding(connection, 123, 100, actor_user_id=9001)
        onboarding.start_onboarding(connection, 123, 200, actor_user_id=9001)
        onboarding.approve_onboarding(connection, 123, 200, actor_user_id=9002)
        onboarding.start_onboarding(connection, 123, 300, actor_user_id=9001)
        onboarding.reject_onboarding(connection, 123, 300, actor_user_id=9003)
        onboarding.start_onboarding(connection, 123, 400, actor_user_id=9001)
        onboarding.approve_onboarding(connection, 123, 400, actor_user_id=9002)
        onboarding.complete_onboarding(connection, 123, 400, actor_user_id=9004)

        summary = onboarding.summarize_onboarding(connection, 123)

    assert summary.guild_id == 123
    assert summary.total == 4
    assert summary.pending == 1
    assert summary.approved == 1
    assert summary.rejected == 1
    assert summary.completed == 1


def test_update_notes_preserves_state_and_records_audit(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        onboarding.start_onboarding(connection, 123, 456, actor_user_id=9001)
        before, after = onboarding.update_notes(
            connection,
            123,
            456,
            actor_user_id=9002,
            notes="  updated note  ",
        )
        events = audit_log.list_audit_events(connection, 123, limit=10)

    assert before.state == onboarding.PENDING
    assert after.state == onboarding.PENDING
    assert after.notes == "updated note"
    assert events[0].action == "onboarding.update_notes"
    assert events[0].target == "456"


def test_update_notes_requires_existing_record(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        try:
            onboarding.update_notes(
                connection,
                123,
                456,
                actor_user_id=9001,
                notes="no record yet",
            )
        except onboarding.InvalidOnboardingTransition as exc:
            assert "has not been started" in str(exc)
        else:
            raise AssertionError("expected InvalidOnboardingTransition")


def test_list_onboarding_history_returns_user_audit_events(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        onboarding.start_onboarding(connection, 123, 456, actor_user_id=9001)
        onboarding.update_notes(connection, 123, 456, actor_user_id=9002, notes="note")
        onboarding.start_onboarding(connection, 123, 789, actor_user_id=9001)

        history = onboarding.list_onboarding_history(connection, 123, 456, limit=10)

    assert [event.action for event in history] == [
        "onboarding.update_notes",
        "onboarding.start",
    ]
    assert all(event.target == "456" for event in history)


def test_invalid_state_is_rejected(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        try:
            onboarding.override_state(
                connection,
                123,
                456,
                state="banana",
                actor_user_id=9001,
            )
        except onboarding.InvalidOnboardingState as exc:
            assert "Unknown onboarding state" in str(exc)
        else:
            raise AssertionError("expected InvalidOnboardingState")


def test_notes_are_trimmed_and_limited(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        _, after = onboarding.start_onboarding(
            connection,
            123,
            456,
            actor_user_id=9001,
            notes="  hello  ",
        )
        try:
            onboarding.override_state(
                connection,
                123,
                456,
                state="pending",
                actor_user_id=9001,
                notes="x" * 1001,
            )
        except onboarding.OnboardingError as exc:
            assert "1000 characters" in str(exc)
        else:
            raise AssertionError("expected OnboardingError")

    assert after.notes == "hello"
