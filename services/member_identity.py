from __future__ import annotations

from calendar import isleap
from dataclasses import dataclass
from datetime import date

MAX_PREFERRED_NAME_LENGTH = 80
MAX_DISPLAY_NAME_LENGTH = 100
ADULT_AGE = 18


class MemberIdentityError(ValueError):
    """Raised when member-supplied identity data is invalid."""


def _clean_name(value: str, *, field_name: str, max_length: int) -> str:
    normalized = " ".join((value or "").split())
    if not normalized:
        raise MemberIdentityError(f"{field_name} cannot be empty")
    if len(normalized) > max_length:
        raise MemberIdentityError(f"{field_name} must be {max_length} characters or fewer")
    return normalized


def parse_birth_date(value: str | date) -> date:
    """Parse an ISO birth date without calculating or storing a stale age."""

    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat((value or "").strip())
    except ValueError as exc:
        raise MemberIdentityError("birth_date must use YYYY-MM-DD") from exc


def _birthday_in_year(birth_date: date, year: int) -> date:
    """Return the birthday anniversary, treating Feb 29 as Feb 28 in non-leap years."""

    if birth_date.month == 2 and birth_date.day == 29 and not isleap(year):
        return date(year, 2, 28)
    return birth_date.replace(year=year)


def calculate_age(birth_date: date, *, on_date: date) -> int:
    """Calculate age locally from the full birth date for a specific server date."""

    if birth_date > on_date:
        raise MemberIdentityError("birth_date cannot be in the future")
    age = on_date.year - birth_date.year
    if on_date < _birthday_in_year(birth_date, on_date.year):
        age -= 1
    return age


@dataclass(frozen=True)
class TrustedIdentityContext:
    """Identity fields allowed in designated Wilhelmina chat and participating DMs."""

    discord_display_name: str
    preferred_name: str
    birth_date: str
    age: int


@dataclass(frozen=True)
class MemberIdentity:
    """Member-supplied identity plus the current Discord-visible name."""

    discord_display_name: str
    preferred_name: str
    birth_date: date

    @classmethod
    def create(
        cls,
        *,
        discord_display_name: str,
        preferred_name: str,
        birth_date: str | date,
        today: date,
        minimum_age: int = ADULT_AGE,
    ) -> "MemberIdentity":
        parsed_birth_date = parse_birth_date(birth_date)
        age = calculate_age(parsed_birth_date, on_date=today)
        if age < minimum_age:
            raise MemberIdentityError(
                f"member must be at least {minimum_age} years old for the adult server experience"
            )
        return cls(
            discord_display_name=_clean_name(
                discord_display_name,
                field_name="discord_display_name",
                max_length=MAX_DISPLAY_NAME_LENGTH,
            ),
            preferred_name=_clean_name(
                preferred_name,
                field_name="preferred_name",
                max_length=MAX_PREFERRED_NAME_LENGTH,
            ),
            birth_date=parsed_birth_date,
        )

    def age_on(self, on_date: date) -> int:
        return calculate_age(self.birth_date, on_date=on_date)

    def trusted_chat_context(self, *, on_date: date) -> TrustedIdentityContext:
        """Expose both names, full birth date, and current age to approved chat assembly."""

        return TrustedIdentityContext(
            discord_display_name=self.discord_display_name,
            preferred_name=self.preferred_name,
            birth_date=self.birth_date.isoformat(),
            age=self.age_on(on_date),
        )
