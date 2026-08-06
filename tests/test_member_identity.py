from datetime import date

import pytest

from services.member_identity import MemberIdentity, MemberIdentityError, calculate_age


def test_identity_preserves_both_names_and_full_birth_date() -> None:
    identity = MemberIdentity.create(
        discord_display_name="xXDarkSylveonXx",
        preferred_name="Jessica",
        birth_date="1991-10-31",
        today=date(2026, 8, 6),
    )

    context = identity.trusted_chat_context(on_date=date(2026, 8, 6))

    assert context.discord_display_name == "xXDarkSylveonXx"
    assert context.preferred_name == "Jessica"
    assert context.birth_date == "1991-10-31"
    assert context.age == 34


def test_age_changes_on_birthday() -> None:
    birth_date = date(1991, 10, 31)

    assert calculate_age(birth_date, on_date=date(2026, 10, 30)) == 34
    assert calculate_age(birth_date, on_date=date(2026, 10, 31)) == 35


def test_leap_day_birthday_uses_february_28_in_non_leap_year() -> None:
    birth_date = date(1992, 2, 29)

    assert calculate_age(birth_date, on_date=date(2025, 2, 27)) == 32
    assert calculate_age(birth_date, on_date=date(2025, 2, 28)) == 33


def test_future_birth_date_is_rejected() -> None:
    with pytest.raises(MemberIdentityError, match="future"):
        MemberIdentity.create(
            discord_display_name="Member",
            preferred_name="Member",
            birth_date="2027-01-01",
            today=date(2026, 8, 6),
        )


def test_underage_identity_is_rejected() -> None:
    with pytest.raises(MemberIdentityError, match="at least 18"):
        MemberIdentity.create(
            discord_display_name="Member",
            preferred_name="Member",
            birth_date="2010-01-01",
            today=date(2026, 8, 6),
        )


def test_names_are_normalized_but_remain_distinct() -> None:
    identity = MemberIdentity.create(
        discord_display_name="  Screen   Name  ",
        preferred_name="  Real   Name  ",
        birth_date="1990-01-01",
        today=date(2026, 8, 6),
    )

    assert identity.discord_display_name == "Screen Name"
    assert identity.preferred_name == "Real Name"
