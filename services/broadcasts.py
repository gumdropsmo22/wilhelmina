from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from services.ai import generate_markdown_async
from services.database import utc_now_iso
from services.persona import BASE_VOICE, GLOBAL_LIMITS

BroadcastSegment = Literal["morning", "evening"]

VALID_SEGMENTS: tuple[BroadcastSegment, ...] = ("morning", "evening")
DEFAULT_TIMEZONE = "Asia/Riyadh"
DEFAULT_MORNING_TIME = "08:00"
DEFAULT_EVENING_TIME = "21:30"
DEFAULT_NEWS_PROVIDER = "tba"
DEFAULT_ASTRONOMY_PROVIDER = "tba"
DEFAULT_SKY_PROVIDER = "tba"
DEFAULT_MORNING_CATEGORIES = "labor,economics,corporate,geopolitics"
DEFAULT_EVENING_CATEGORIES = "corporate,environment,politics,world"
MAX_BROADCAST_CHARS = 1900

SETTING_FIELDS = frozenset(
    {
        "default_channel_id",
        "morning_channel_id",
        "evening_channel_id",
        "timezone",
        "morning_enabled",
        "evening_enabled",
        "morning_time",
        "evening_time",
        "news_provider",
        "astronomy_provider",
        "sky_provider",
        "morning_categories",
        "evening_categories",
    }
)

MORNING_TITLE = "The Vanguard Frequency"
EVENING_TITLE = "W.W.N. Broadcast"

MORNING_GENERATION_CONTRACT = """
DAILY GENERATION SKELETON: THE VANGUARD FREQUENCY

Tone: gritty, defiant, revolutionary socialist/communist, analytical, pro-worker,
and deeply critical of capitalist hegemony.

Content rules: no hallucinations. Do not invent fake sponsors, fake traffic,
fake scenarios, fake headlines, fake dates, fake statistics, fake celestial data,
or fake server context. All news and sky data must come from the evidence packet.

Anti-repetition protocol: avoid recurring morning tropes like coffee, waking up,
Monday blues, and generic sunrise chatter. Opening, transition, and sign-off must
be specific to the evidence packet and recent-history restrictions.

Required structure:
- TRANSMISSION INITIATION
- THE MATERIAL CONDITIONS
- THE TACTICAL SKY
- END OF TRANSMISSION
""".strip()

EVENING_GENERATION_CONTRACT = """
DAILY GENERATION SKELETON: W.W.N. BROADCAST

Tone: deadpan, dark, late-night irony. Anti-capitalist sarcasm blended with
supernatural dread.

Content rules: news and astronomical data must be factually accurate for the day
of generation. Commentary may be mystical and cynical, but factual claims must
come from the evidence packet.

Required structure:
- OPENING TRANSMISSION
- NEWS OF THE NIGHT
- PLANETARY FORECAST
- CLOSING INCANTATION
""".strip()


class BroadcastError(ValueError):
    """Raised when broadcast configuration or generation input is invalid."""


@dataclass(frozen=True)
class BroadcastSettings:
    guild_id: int
    default_channel_id: int | None
    morning_channel_id: int | None
    evening_channel_id: int | None
    timezone: str
    morning_enabled: bool
    evening_enabled: bool
    morning_time: str
    evening_time: str
    news_provider: str
    astronomy_provider: str
    sky_provider: str
    morning_categories: str
    evening_categories: str
    created_at: str
    updated_at: str

    def is_enabled(self, segment: str) -> bool:
        segment = validate_segment(segment)
        return self.morning_enabled if segment == "morning" else self.evening_enabled

    def time_for(self, segment: str) -> str:
        segment = validate_segment(segment)
        return self.morning_time if segment == "morning" else self.evening_time

    def channel_id_for(self, segment: str) -> int | None:
        segment = validate_segment(segment)
        if segment == "morning" and self.morning_channel_id is not None:
            return self.morning_channel_id
        if segment == "evening" and self.evening_channel_id is not None:
            return self.evening_channel_id
        return self.default_channel_id

    def categories_for(self, segment: str) -> str:
        segment = validate_segment(segment)
        return self.morning_categories if segment == "morning" else self.evening_categories


@dataclass(frozen=True)
class Article:
    title: str
    summary: str
    source_name: str
    canonical_url: str = ""
    published_at: str = ""
    category: str = ""
    provider: str = "manual"

    @property
    def evidence_key(self) -> str:
        raw = f"{self.provider}|{self.source_name}|{self.title}|{self.canonical_url}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class SkyPacket:
    provider: str
    status: str
    observer_name: str
    timezone: str
    local_date: str
    moon_phase: str | None = None
    moon_illumination: str | None = None
    notable_events: tuple[str, ...] = ()


@dataclass(frozen=True)
class BroadcastEvidence:
    segment: BroadcastSegment
    logical_date: str
    generated_for: str
    news_items: tuple[Article, ...]
    astronomy_items: tuple[Article, ...]
    sky_packet: SkyPacket
    source_notes: tuple[str, ...] = ()

    @property
    def has_publishable_facts(self) -> bool:
        return bool(self.news_items or self.astronomy_items or self.sky_packet.status == "ready")


@dataclass(frozen=True)
class BroadcastDraft:
    segment: BroadcastSegment
    content: str
    fallback_used: bool
    validation_errors: tuple[str, ...]
    evidence: BroadcastEvidence


@dataclass(frozen=True)
class BroadcastRun:
    id: int
    guild_id: int
    segment: str
    run_type: str
    logical_date: str
    scheduled_for: str | None
    status: str
    message_id: int | None
    fallback_used: bool
    error_code: str | None
    created_at: str
    updated_at: str


def validate_segment(segment: str) -> BroadcastSegment:
    normalized = (segment or "").strip().lower()
    if normalized not in VALID_SEGMENTS:
        raise BroadcastError(f"Unknown broadcast segment: {segment!r}")
    return normalized  # type: ignore[return-value]


def validate_time_string(value: str) -> str:
    raw = (value or "").strip()
    try:
        parsed = datetime.strptime(raw, "%H:%M")
    except ValueError as exc:
        raise BroadcastError("Broadcast time must use 24-hour HH:MM format.") from exc
    return parsed.strftime("%H:%M")


def validate_timezone_name(value: str) -> str:
    timezone = (value or "").strip()
    if not timezone:
        raise BroadcastError("Timezone must not be empty.")
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise BroadcastError(f"Unknown IANA timezone: {timezone!r}") from exc
    return timezone


def settings_to_audit_dict(settings: BroadcastSettings | None) -> dict[str, Any] | None:
    if settings is None:
        return None
    return asdict(settings)


def _bool_from_db(value: int | bool) -> bool:
    return bool(int(value))


def _row_to_settings(row: sqlite3.Row | None) -> BroadcastSettings | None:
    if row is None:
        return None
    return BroadcastSettings(
        guild_id=int(row["guild_id"]),
        default_channel_id=row["default_channel_id"],
        morning_channel_id=row["morning_channel_id"],
        evening_channel_id=row["evening_channel_id"],
        timezone=str(row["timezone"]),
        morning_enabled=_bool_from_db(row["morning_enabled"]),
        evening_enabled=_bool_from_db(row["evening_enabled"]),
        morning_time=str(row["morning_time"]),
        evening_time=str(row["evening_time"]),
        news_provider=str(row["news_provider"]),
        astronomy_provider=str(row["astronomy_provider"]),
        sky_provider=str(row["sky_provider"]),
        morning_categories=str(row["morning_categories"]),
        evening_categories=str(row["evening_categories"]),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def get_broadcast_settings(
    connection: sqlite3.Connection,
    guild_id: int | str,
) -> BroadcastSettings | None:
    row = connection.execute(
        "SELECT * FROM broadcast_settings WHERE guild_id = ?",
        (int(guild_id),),
    ).fetchone()
    return _row_to_settings(row)


def ensure_broadcast_settings(
    connection: sqlite3.Connection,
    guild_id: int | str,
    *,
    timezone: str = DEFAULT_TIMEZONE,
) -> BroadcastSettings:
    normalized_guild_id = int(guild_id)
    existing = get_broadcast_settings(connection, normalized_guild_id)
    if existing is not None:
        return existing

    now = utc_now_iso()
    connection.execute(
        """
        INSERT INTO broadcast_settings (
            guild_id,
            timezone,
            morning_time,
            evening_time,
            news_provider,
            astronomy_provider,
            sky_provider,
            morning_categories,
            evening_categories,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            normalized_guild_id,
            validate_timezone_name(timezone),
            DEFAULT_MORNING_TIME,
            DEFAULT_EVENING_TIME,
            DEFAULT_NEWS_PROVIDER,
            DEFAULT_ASTRONOMY_PROVIDER,
            DEFAULT_SKY_PROVIDER,
            DEFAULT_MORNING_CATEGORIES,
            DEFAULT_EVENING_CATEGORIES,
            now,
            now,
        ),
    )
    created = get_broadcast_settings(connection, normalized_guild_id)
    if created is None:
        raise RuntimeError("Failed to create broadcast settings row")
    return created


def update_broadcast_settings(
    connection: sqlite3.Connection,
    guild_id: int | str,
    changes: dict[str, int | str | bool | None],
) -> tuple[BroadcastSettings | None, BroadcastSettings]:
    normalized_guild_id = int(guild_id)
    before = get_broadcast_settings(connection, normalized_guild_id)
    ensure_broadcast_settings(connection, normalized_guild_id)

    if not changes:
        after = get_broadcast_settings(connection, normalized_guild_id)
        if after is None:
            raise RuntimeError("Failed to load broadcast settings row")
        return before, after

    normalized_changes: dict[str, int | str | None] = {}
    for field, value in changes.items():
        if field not in SETTING_FIELDS:
            raise BroadcastError(f"Unknown broadcast settings field: {field!r}")
        if field == "timezone":
            normalized_changes[field] = validate_timezone_name(str(value or ""))
        elif field.endswith("_time"):
            normalized_changes[field] = validate_time_string(str(value or ""))
        elif field.endswith("_enabled"):
            normalized_changes[field] = 1 if bool(value) else 0
        elif field.endswith("_channel_id") and value is not None:
            normalized_changes[field] = int(value)
        elif field.endswith("_provider"):
            normalized_changes[field] = str(value or DEFAULT_NEWS_PROVIDER).strip().lower() or "tba"
        elif field.endswith("_categories"):
            normalized_changes[field] = str(value or "").strip()
        else:
            normalized_changes[field] = value  # type: ignore[assignment]

    updated_at = utc_now_iso()
    assignments = ", ".join(f"{field} = ?" for field in normalized_changes)
    values = list(normalized_changes.values())
    values.extend([updated_at, normalized_guild_id])
    connection.execute(
        f"""
        UPDATE broadcast_settings
        SET {assignments}, updated_at = ?
        WHERE guild_id = ?
        """,
        values,
    )
    after = get_broadcast_settings(connection, normalized_guild_id)
    if after is None:
        raise RuntimeError("Failed to update broadcast settings row")
    return before, after


def set_segment_enabled(
    connection: sqlite3.Connection,
    guild_id: int | str,
    segment: str,
    enabled: bool,
) -> tuple[BroadcastSettings | None, BroadcastSettings]:
    segment = validate_segment(segment)
    return update_broadcast_settings(connection, guild_id, {f"{segment}_enabled": enabled})


def set_segment_time(
    connection: sqlite3.Connection,
    guild_id: int | str,
    segment: str,
    time_value: str,
) -> tuple[BroadcastSettings | None, BroadcastSettings]:
    segment = validate_segment(segment)
    return update_broadcast_settings(connection, guild_id, {f"{segment}_time": time_value})


def set_broadcast_channel(
    connection: sqlite3.Connection,
    guild_id: int | str,
    target: str,
    channel_id: int | str | None,
) -> tuple[BroadcastSettings | None, BroadcastSettings]:
    normalized = (target or "").strip().lower()
    if normalized == "default":
        field = "default_channel_id"
    elif normalized in VALID_SEGMENTS:
        field = f"{normalized}_channel_id"
    else:
        raise BroadcastError("Channel target must be default, morning, or evening.")
    return update_broadcast_settings(connection, guild_id, {field: channel_id})


def set_broadcast_timezone(
    connection: sqlite3.Connection,
    guild_id: int | str,
    timezone: str,
) -> tuple[BroadcastSettings | None, BroadcastSettings]:
    return update_broadcast_settings(connection, guild_id, {"timezone": timezone})


def _row_to_run(row: sqlite3.Row | None) -> BroadcastRun | None:
    if row is None:
        return None
    return BroadcastRun(
        id=int(row["id"]),
        guild_id=int(row["guild_id"]),
        segment=str(row["segment"]),
        run_type=str(row["run_type"]),
        logical_date=str(row["logical_date"]),
        scheduled_for=row["scheduled_for"],
        status=str(row["status"]),
        message_id=row["message_id"],
        fallback_used=_bool_from_db(row["fallback_used"]),
        error_code=row["error_code"],
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


def claim_scheduled_run(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    segment: str,
    logical_date: str,
    scheduled_for: str,
) -> BroadcastRun | None:
    segment = validate_segment(segment)
    now = utc_now_iso()
    try:
        cursor = connection.execute(
            """
            INSERT INTO broadcast_runs (
                guild_id,
                segment,
                run_type,
                logical_date,
                scheduled_for,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, 'scheduled', ?, ?, 'claimed', ?, ?)
            """,
            (guild_id, segment, logical_date, scheduled_for, now, now),
        )
    except sqlite3.IntegrityError:
        return None

    return _row_to_run(
        connection.execute("SELECT * FROM broadcast_runs WHERE id = ?", (cursor.lastrowid,)).fetchone()
    )


def record_test_run(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    segment: str,
    logical_date: str,
    message_id: int | None,
    fallback_used: bool,
    status: str = "posted",
    error_code: str | None = None,
) -> BroadcastRun:
    segment = validate_segment(segment)
    now = utc_now_iso()
    cursor = connection.execute(
        """
        INSERT INTO broadcast_runs (
            guild_id,
            segment,
            run_type,
            logical_date,
            status,
            message_id,
            fallback_used,
            error_code,
            created_at,
            updated_at
        )
        VALUES (?, ?, 'test', ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            guild_id,
            segment,
            logical_date,
            status,
            message_id,
            1 if fallback_used else 0,
            error_code,
            now,
            now,
        ),
    )
    run = _row_to_run(
        connection.execute("SELECT * FROM broadcast_runs WHERE id = ?", (cursor.lastrowid,)).fetchone()
    )
    if run is None:
        raise RuntimeError("Failed to record broadcast test run")
    return run


def record_broadcast_run_result(
    connection: sqlite3.Connection,
    run_id: int,
    *,
    status: str,
    message_id: int | None = None,
    fallback_used: bool = False,
    error_code: str | None = None,
) -> BroadcastRun:
    connection.execute(
        """
        UPDATE broadcast_runs
        SET status = ?, message_id = ?, fallback_used = ?, error_code = ?, updated_at = ?
        WHERE id = ?
        """,
        (status, message_id, 1 if fallback_used else 0, error_code, utc_now_iso(), run_id),
    )
    run = _row_to_run(connection.execute("SELECT * FROM broadcast_runs WHERE id = ?", (run_id,)).fetchone())
    if run is None:
        raise RuntimeError("Failed to update broadcast run")
    return run


def list_recent_runs(
    connection: sqlite3.Connection,
    guild_id: int | str,
    *,
    limit: int = 5,
) -> list[BroadcastRun]:
    rows = connection.execute(
        """
        SELECT * FROM broadcast_runs
        WHERE guild_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (int(guild_id), int(limit)),
    ).fetchall()
    return [run for row in rows if (run := _row_to_run(row)) is not None]


def record_text_history(
    connection: sqlite3.Connection,
    *,
    guild_id: int,
    segment: str,
    logical_date: str,
    content: str,
) -> None:
    segment = validate_segment(segment)
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    opener = lines[0] if lines else ""
    closer = lines[-1] if lines else ""
    connection.execute(
        """
        INSERT INTO broadcast_text_history (
            guild_id,
            segment,
            logical_date,
            opener_hash,
            closer_hash,
            full_hash,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            guild_id,
            segment,
            logical_date,
            _hash_text(opener),
            _hash_text(closer),
            _hash_text(content),
            utc_now_iso(),
        ),
    )


def list_recent_text_hashes(
    connection: sqlite3.Connection,
    guild_id: int | str,
    segment: str,
    *,
    limit: int = 14,
) -> list[str]:
    segment = validate_segment(segment)
    rows = connection.execute(
        """
        SELECT opener_hash, closer_hash, full_hash
        FROM broadcast_text_history
        WHERE guild_id = ? AND segment = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ?
        """,
        (int(guild_id), segment, int(limit)),
    ).fetchall()
    hashes: list[str] = []
    for row in rows:
        hashes.extend([str(row["opener_hash"]), str(row["closer_hash"]), str(row["full_hash"])])
    return hashes


def build_empty_evidence(
    settings: BroadcastSettings,
    segment: str,
    *,
    now: datetime | None = None,
) -> BroadcastEvidence:
    segment = validate_segment(segment)
    timezone = ZoneInfo(settings.timezone)
    generated_at = now.astimezone(timezone) if now is not None else datetime.now(timezone)
    sky_packet = SkyPacket(
        provider=settings.sky_provider,
        status="unavailable",
        observer_name="Riyadh",
        timezone=settings.timezone,
        local_date=generated_at.date().isoformat(),
    )
    notes = (
        "News provider is TBA; no headline facts were fetched.",
        "Astronomy provider is TBA; no verified sky facts were fetched.",
    )
    return BroadcastEvidence(
        segment=segment,
        logical_date=generated_at.date().isoformat(),
        generated_for=generated_at.isoformat(timespec="seconds"),
        news_items=(),
        astronomy_items=(),
        sky_packet=sky_packet,
        source_notes=notes,
    )


def build_broadcast_prompt(
    *,
    settings: BroadcastSettings,
    evidence: BroadcastEvidence,
    recent_hashes: list[str] | None = None,
) -> str:
    contract = MORNING_GENERATION_CONTRACT if evidence.segment == "morning" else EVENING_GENERATION_CONTRACT
    title = MORNING_TITLE if evidence.segment == "morning" else EVENING_TITLE
    recent_hashes = recent_hashes or []
    return (
        f"Base voice:\n{BASE_VOICE}\n\n"
        f"Global limits:\n{GLOBAL_LIMITS}\n\n"
        f"Broadcast title: {title}\n"
        f"Segment: {evidence.segment}\n"
        f"Generation target: {evidence.generated_for}\n"
        f"Guild timezone: {settings.timezone}\n"
        f"Categories: {settings.categories_for(evidence.segment)}\n\n"
        f"Segment contract:\n{contract}\n\n"
        f"Evidence packet:\n{_format_evidence(evidence)}\n\n"
        f"Recent text hashes to avoid repeating exactly: {', '.join(recent_hashes) or 'none'}\n\n"
        "Rules:\n"
        "- Every factual claim must appear in the evidence packet.\n"
        "- If a fact is missing, omit it instead of inventing it.\n"
        "- Preserve the required segment structure and markdown headings.\n"
        "- Do not include citations, source URLs, or internal validation notes in the final post.\n"
        "- Do not use recurring generic greetings.\n"
        f"- Stay under {MAX_BROADCAST_CHARS} characters.\n\n"
        "Return only the final Discord-ready markdown broadcast."
    )


async def generate_broadcast_draft(
    *,
    settings: BroadcastSettings,
    evidence: BroadcastEvidence,
    recent_hashes: list[str] | None = None,
) -> BroadcastDraft:
    prompt = build_broadcast_prompt(settings=settings, evidence=evidence, recent_hashes=recent_hashes)
    generated = await generate_markdown_async(prompt)
    validation_errors = validate_broadcast_output(generated, evidence=evidence)
    if generated and not validation_errors:
        return BroadcastDraft(
            segment=evidence.segment,
            content=generated.strip(),
            fallback_used=False,
            validation_errors=(),
            evidence=evidence,
        )

    fallback = render_deterministic_broadcast(evidence=evidence)
    return BroadcastDraft(
        segment=evidence.segment,
        content=fallback,
        fallback_used=True,
        validation_errors=tuple(validation_errors or ["ai_unavailable"]),
        evidence=evidence,
    )


def validate_broadcast_output(content: str, *, evidence: BroadcastEvidence) -> list[str]:
    errors: list[str] = []
    stripped = (content or "").strip()
    if not stripped:
        return ["empty_output"]
    if len(stripped) > MAX_BROADCAST_CHARS:
        errors.append("too_long")
    expected_title = MORNING_TITLE if evidence.segment == "morning" else EVENING_TITLE
    if expected_title not in stripped:
        errors.append("missing_segment_title")
    forbidden_placeholders = (
        "Current Real-World News Story",
        "Generate zinger",
        "Generate critique",
        "[",
        "]",
    )
    if any(placeholder in stripped for placeholder in forbidden_placeholders):
        errors.append("contains_template_placeholder")
    return errors


def render_deterministic_broadcast(*, evidence: BroadcastEvidence) -> str:
    if evidence.segment == "morning":
        return _render_morning_fallback(evidence)
    return _render_evening_fallback(evidence)


def has_publishable_evidence(evidence: BroadcastEvidence) -> bool:
    return evidence.has_publishable_facts


def _render_morning_fallback(evidence: BroadcastEvidence) -> str:
    news_lines = _format_article_bullets(evidence.news_items)
    sky_line = _format_sky_line(evidence.sky_packet)
    notes = " ".join(evidence.source_notes)
    return (
        f"## {MORNING_TITLE}\n"
        "**TRANSMISSION INITIATION**\n"
        f"The date is {evidence.logical_date}. The machine wants a bulletin; "
        "Wilhelmina refuses to fabricate one for its comfort.\n\n"
        "### THE MATERIAL CONDITIONS\n"
        f"{news_lines}\n\n"
        "### THE TACTICAL SKY\n"
        f"{sky_line}\n\n"
        "### END OF TRANSMISSION\n"
        f"Verified source coverage is incomplete. {notes} Configure providers, then run this again."
    )[:MAX_BROADCAST_CHARS]


def _render_evening_fallback(evidence: BroadcastEvidence) -> str:
    news_lines = _format_article_bullets(evidence.news_items)
    sky_line = _format_sky_line(evidence.sky_packet)
    notes = " ".join(evidence.source_notes)
    return (
        f"## {EVENING_TITLE}\n"
        "**OPENING TRANSMISSION**\n"
        f"Witch Watch Network is standing by on {evidence.logical_date}. "
        "The night may be dramatic; the facts are not available for decoration.\n\n"
        "### NEWS OF THE NIGHT\n"
        f"{news_lines}\n\n"
        "### PLANETARY FORECAST\n"
        f"{sky_line}\n\n"
        "### CLOSING INCANTATION\n"
        f"No unsupported prophecy will be issued. {notes} Configure providers, then let the dark little engine speak."
    )[:MAX_BROADCAST_CHARS]


def _format_article_bullets(articles: tuple[Article, ...]) -> str:
    if not articles:
        return "- No verified headline items were provided. No invention will be performed."
    return "\n".join(
        f"- **{article.title}** — {article.summary} ({article.source_name})" for article in articles
    )


def _format_sky_line(packet: SkyPacket) -> str:
    if packet.status != "ready":
        return "- Riyadh sky data is unavailable because no sky provider is configured."
    parts = [f"- Observer: {packet.observer_name}, {packet.local_date}."]
    if packet.moon_phase:
        moon = packet.moon_phase
        if packet.moon_illumination:
            moon = f"{moon}, {packet.moon_illumination} illuminated"
        parts.append(f"- Moon: {moon}.")
    for event in packet.notable_events:
        parts.append(f"- {event}")
    return "\n".join(parts)


def _format_evidence(evidence: BroadcastEvidence) -> str:
    lines = [
        f"logical_date: {evidence.logical_date}",
        f"generated_for: {evidence.generated_for}",
        "news_items:",
    ]
    if evidence.news_items:
        for item in evidence.news_items:
            lines.append(
                f"- title={item.title!r}; summary={item.summary!r}; source={item.source_name!r}; "
                f"published_at={item.published_at!r}; evidence_key={item.evidence_key}"
            )
    else:
        lines.append("- none")
    lines.append("astronomy_items:")
    if evidence.astronomy_items:
        for item in evidence.astronomy_items:
            lines.append(
                f"- title={item.title!r}; summary={item.summary!r}; source={item.source_name!r}; "
                f"published_at={item.published_at!r}; evidence_key={item.evidence_key}"
            )
    else:
        lines.append("- none")
    lines.append("sky_packet:")
    lines.append(f"- provider={evidence.sky_packet.provider!r}; status={evidence.sky_packet.status!r}")
    lines.append(f"- observer={evidence.sky_packet.observer_name!r}; date={evidence.sky_packet.local_date!r}")
    lines.append(f"- moon_phase={evidence.sky_packet.moon_phase!r}")
    lines.append(f"- moon_illumination={evidence.sky_packet.moon_illumination!r}")
    for event in evidence.sky_packet.notable_events:
        lines.append(f"- event={event!r}")
    if evidence.source_notes:
        lines.append("source_notes:")
        for note in evidence.source_notes:
            lines.append(f"- {note}")
    return "\n".join(lines)


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def local_broadcast_datetime(settings: BroadcastSettings, segment: str, day: date | None = None) -> datetime:
    segment = validate_segment(segment)
    timezone = ZoneInfo(settings.timezone)
    local_day = day or datetime.now(timezone).date()
    hour, minute = [int(part) for part in settings.time_for(segment).split(":")]
    return datetime(
        local_day.year,
        local_day.month,
        local_day.day,
        hour,
        minute,
        tzinfo=timezone,
    )


def current_local_date(settings: BroadcastSettings) -> str:
    return datetime.now(ZoneInfo(settings.timezone)).date().isoformat()


def utc_now() -> datetime:
    return datetime.now(UTC)
