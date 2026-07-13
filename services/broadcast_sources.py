from __future__ import annotations

import asyncio
import html
import math
import os
import re
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Iterable
from zoneinfo import ZoneInfo

from services import broadcasts

DEFAULT_FETCH_TIMEOUT_SECONDS = 10
DEFAULT_NEWS_MAX_ITEMS = 4
DEFAULT_ASTRONOMY_MAX_ITEMS = 2
USER_AGENT = "WilhelminaBot/0.1 (+https://github.com/gumdropsmo22/wilhelmina)"
SYNODIC_MONTH_DAYS = 29.53058867
REFERENCE_NEW_MOON_JD = 2451550.1

NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
}

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "labor": (
        "labor",
        "labour",
        "union",
        "strike",
        "worker",
        "workers",
        "wage",
        "wages",
        "layoff",
        "layoffs",
        "workforce",
        "collective bargaining",
    ),
    "economics": (
        "economy",
        "economic",
        "inflation",
        "recession",
        "debt",
        "rates",
        "central bank",
        "market",
        "markets",
        "tax",
        "tariff",
        "budget",
    ),
    "corporate": (
        "company",
        "corporate",
        "profits",
        "profit",
        "shareholder",
        "stock",
        "merger",
        "antitrust",
        "executive",
        "ceo",
        "bank",
        "banks",
    ),
    "geopolitics": (
        "geopolitics",
        "war",
        "conflict",
        "sanction",
        "sanctions",
        "election",
        "government",
        "state",
        "border",
        "trade",
        "diplomacy",
    ),
    "politics": (
        "politic",
        "election",
        "parliament",
        "minister",
        "president",
        "congress",
        "court",
        "law",
        "policy",
    ),
    "environment": (
        "climate",
        "environment",
        "pollution",
        "emissions",
        "heat",
        "flood",
        "wildfire",
        "energy",
        "oil",
        "gas",
    ),
    "world": (),
    "science": (
        "science",
        "research",
        "study",
        "space",
        "astronomy",
        "planet",
        "moon",
    ),
}


@dataclass(frozen=True)
class SourceResult:
    articles: tuple[broadcasts.Article, ...]
    notes: tuple[str, ...]


def env_csv(name: str) -> tuple[str, ...]:
    raw = os.getenv(name, "")
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def read_int_env(name: str, *, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(1, value)


def parse_rss_articles(
    xml_text: str,
    *,
    fallback_source_name: str = "RSS feed",
    provider: str = "rss",
) -> tuple[broadcasts.Article, ...]:
    root = ET.fromstring(xml_text)
    articles: list[broadcasts.Article] = []

    channel = root.find("channel")
    if channel is not None:
        source_name = clean_text(_find_text(channel, "title")) or fallback_source_name
        for item in channel.findall("item"):
            article = _article_from_rss_item(item, source_name=source_name, provider=provider)
            if article is not None:
                articles.append(article)
        return tuple(articles)

    source_name = clean_text(_find_text(root, "atom:title")) or fallback_source_name
    for entry in root.findall("atom:entry", NAMESPACES):
        article = _article_from_atom_entry(entry, source_name=source_name, provider=provider)
        if article is not None:
            articles.append(article)
    return tuple(articles)


def filter_articles_for_categories(
    articles: Iterable[broadcasts.Article],
    categories: str,
    *,
    limit: int,
) -> tuple[broadcasts.Article, ...]:
    article_list = list(articles)
    category_values = tuple(item.lower() for item in env_like_csv(categories))
    if not category_values or "world" in category_values:
        return tuple(article_list[:limit])

    matched: list[broadcasts.Article] = []
    for article in article_list:
        if article_matches_categories(article, category_values):
            matched.append(article)
        if len(matched) >= limit:
            return tuple(matched)

    seen = {article.evidence_key for article in matched}
    for article in article_list:
        if article.evidence_key in seen:
            continue
        matched.append(article)
        if len(matched) >= limit:
            break
    return tuple(matched)


def article_matches_categories(
    article: broadcasts.Article,
    categories: tuple[str, ...],
) -> bool:
    haystack = f"{article.title} {article.summary} {article.category}".lower()
    for category in categories:
        keywords = CATEGORY_KEYWORDS.get(category, (category,))
        if not keywords:
            return True
        if any(keyword in haystack for keyword in keywords):
            return True
    return False


def collect_rss_articles(
    *,
    urls: tuple[str, ...],
    categories: str,
    max_items: int,
    provider: str,
    fallback_source_name: str,
) -> SourceResult:
    if not urls:
        return SourceResult(articles=(), notes=(f"No {provider} RSS URLs are configured.",))

    notes: list[str] = []
    collected: list[broadcasts.Article] = []
    timeout = read_int_env("BROADCAST_SOURCE_TIMEOUT_SECONDS", default=DEFAULT_FETCH_TIMEOUT_SECONDS)

    for url in urls:
        try:
            xml_text = fetch_text(url, timeout_seconds=timeout)
            collected.extend(
                parse_rss_articles(
                    xml_text,
                    fallback_source_name=fallback_source_name,
                    provider=provider,
                )
            )
        except (ET.ParseError, OSError, UnicodeError, urllib.error.URLError) as exc:
            notes.append(f"{provider} fetch failed for {url}: {exc.__class__.__name__}")

    if not collected:
        notes.append(f"No usable {provider} articles were parsed.")
        return SourceResult(articles=(), notes=tuple(notes))

    filtered = filter_articles_for_categories(collected, categories, limit=max_items)
    if not filtered:
        notes.append(f"No {provider} articles matched configured categories.")
    return SourceResult(articles=filtered, notes=tuple(notes))


def collect_broadcast_evidence(
    settings: broadcasts.BroadcastSettings,
    segment: str,
    *,
    now: datetime | None = None,
) -> broadcasts.BroadcastEvidence:
    segment = broadcasts.validate_segment(segment)
    timezone = ZoneInfo(settings.timezone)
    local_now = now.astimezone(timezone) if now is not None else datetime.now(timezone)
    categories = settings.categories_for(segment)

    news_result = collect_rss_articles(
        urls=env_csv("BROADCAST_NEWS_RSS_URLS"),
        categories=categories,
        max_items=read_int_env("BROADCAST_NEWS_MAX_ITEMS", default=DEFAULT_NEWS_MAX_ITEMS),
        provider="rss_news",
        fallback_source_name="News RSS",
    )
    astronomy_result = collect_rss_articles(
        urls=env_csv("BROADCAST_ASTRONOMY_RSS_URLS"),
        categories="science,space,astronomy",
        max_items=read_int_env(
            "BROADCAST_ASTRONOMY_MAX_ITEMS",
            default=DEFAULT_ASTRONOMY_MAX_ITEMS,
        ),
        provider="rss_astronomy",
        fallback_source_name="Astronomy RSS",
    )
    sky_packet = build_computed_sky_packet(settings, now=local_now)

    source_notes = (
        f"news_provider={settings.news_provider}; rss_urls={len(env_csv('BROADCAST_NEWS_RSS_URLS'))}",
        f"astronomy_provider={settings.astronomy_provider}; "
        f"rss_urls={len(env_csv('BROADCAST_ASTRONOMY_RSS_URLS'))}",
        f"sky_provider={settings.sky_provider}; computed_moon=true",
        *news_result.notes,
        *astronomy_result.notes,
    )
    return broadcasts.BroadcastEvidence(
        segment=segment,
        logical_date=local_now.date().isoformat(),
        generated_for=local_now.isoformat(timespec="seconds"),
        news_items=news_result.articles,
        astronomy_items=astronomy_result.articles,
        sky_packet=sky_packet,
        source_notes=source_notes,
    )


async def collect_broadcast_evidence_async(
    settings: broadcasts.BroadcastSettings,
    segment: str,
    *,
    now: datetime | None = None,
) -> broadcasts.BroadcastEvidence:
    return await asyncio.to_thread(collect_broadcast_evidence, settings, segment, now=now)


def build_computed_sky_packet(
    settings: broadcasts.BroadcastSettings,
    *,
    now: datetime | None = None,
) -> broadcasts.SkyPacket:
    timezone = ZoneInfo(settings.timezone)
    local_now = now.astimezone(timezone) if now is not None else datetime.now(timezone)
    moon = compute_moon_phase(local_now)
    return broadcasts.SkyPacket(
        provider="computed_moon",
        status="ready",
        observer_name="Riyadh",
        timezone=settings.timezone,
        local_date=local_now.date().isoformat(),
        moon_phase=moon["phase"],
        moon_illumination=f"{moon['illumination_percent']}%",
        notable_events=(
            "Moon phase and illumination are computed from the current lunar cycle; "
            "provider-reported meteor showers, eclipses, and planetary visibility are added only when configured feeds report them.",
        ),
    )


def compute_moon_phase(moment: datetime) -> dict[str, str | int]:
    utc_moment = moment.astimezone(UTC)
    age = (julian_day(utc_moment) - REFERENCE_NEW_MOON_JD) % SYNODIC_MONTH_DAYS
    illumination = (1 - math.cos(2 * math.pi * age / SYNODIC_MONTH_DAYS)) / 2
    return {
        "phase": phase_name(age),
        "age_days": round(age, 2),
        "illumination_percent": round(illumination * 100),
    }


def phase_name(age: float) -> str:
    if age < 1.84566:
        return "New Moon"
    if age < 5.53699:
        return "Waxing Crescent"
    if age < 9.22831:
        return "First Quarter"
    if age < 12.91963:
        return "Waxing Gibbous"
    if age < 16.61096:
        return "Full Moon"
    if age < 20.30228:
        return "Waning Gibbous"
    if age < 23.99361:
        return "Last Quarter"
    if age < 27.68493:
        return "Waning Crescent"
    return "New Moon"


def julian_day(moment: datetime) -> float:
    utc_moment = moment.astimezone(UTC)
    year = utc_moment.year
    month = utc_moment.month
    day = utc_moment.day
    if month <= 2:
        year -= 1
        month += 12
    a = year // 100
    b = 2 - a + (a // 4)
    day_fraction = (
        utc_moment.hour + utc_moment.minute / 60 + utc_moment.second / 3600
    ) / 24
    return (
        int(365.25 * (year + 4716))
        + int(30.6001 * (month + 1))
        + day
        + b
        - 1524.5
        + day_fraction
    )


def fetch_text(url: str, *, timeout_seconds: int) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def _article_from_rss_item(
    item: ET.Element,
    *,
    source_name: str,
    provider: str,
) -> broadcasts.Article | None:
    title = clean_text(_find_text(item, "title"))
    if not title:
        return None
    summary = clean_text(
        _find_text(item, "description", "content:encoded", "summary")
    )
    link = clean_text(_find_text(item, "link", "guid"))
    published_at = clean_text(_find_text(item, "pubDate", "dc:date"))
    category = clean_text(_find_text(item, "category"))
    return broadcasts.Article(
        title=title,
        summary=summary or title,
        source_name=source_name,
        canonical_url=link,
        published_at=normalize_published_at(published_at),
        category=category,
        provider=provider,
    )


def _article_from_atom_entry(
    entry: ET.Element,
    *,
    source_name: str,
    provider: str,
) -> broadcasts.Article | None:
    title = clean_text(_find_text(entry, "atom:title"))
    if not title:
        return None
    summary = clean_text(_find_text(entry, "atom:summary", "atom:content"))
    link = ""
    for link_element in entry.findall("atom:link", NAMESPACES):
        href = link_element.attrib.get("href", "").strip()
        rel = link_element.attrib.get("rel", "alternate")
        if href and rel == "alternate":
            link = href
            break
    published_at = clean_text(_find_text(entry, "atom:published", "atom:updated"))
    return broadcasts.Article(
        title=title,
        summary=summary or title,
        source_name=source_name,
        canonical_url=link,
        published_at=normalize_published_at(published_at),
        provider=provider,
    )


def _find_text(element: ET.Element, *paths: str) -> str:
    for path in paths:
        found = element.find(path, NAMESPACES)
        if found is not None and found.text:
            return found.text
    return ""


def clean_text(value: str) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_published_at(value: str) -> str:
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).astimezone(UTC).isoformat(timespec="seconds")
    except (TypeError, ValueError, IndexError, AttributeError):
        return value


def env_like_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in (value or "").split(",") if item.strip())
