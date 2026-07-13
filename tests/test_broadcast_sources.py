from datetime import datetime
from zoneinfo import ZoneInfo

from services import broadcast_sources, broadcasts
from services.database import initialize_database, managed_connection


def test_rss_parser_normalizes_articles():
    xml = """
    <rss version="2.0">
      <channel>
        <title>Labor Wire</title>
        <item>
          <title>Workers approve a new contract</title>
          <description>Union members voted after negotiations.</description>
          <link>https://example.test/workers-contract</link>
          <pubDate>Sun, 12 Jul 2026 06:00:00 GMT</pubDate>
          <category>labor</category>
        </item>
      </channel>
    </rss>
    """

    articles = broadcast_sources.parse_rss_articles(xml, provider="test_rss")

    assert len(articles) == 1
    assert articles[0].title == "Workers approve a new contract"
    assert articles[0].source_name == "Labor Wire"
    assert articles[0].provider == "test_rss"
    assert articles[0].published_at == "2026-07-12T06:00:00+00:00"


def test_category_filter_prefers_matching_articles():
    articles = (
        broadcasts.Article(title="Celebrity opens restaurant", summary="A lifestyle item.", source_name="x"),
        broadcasts.Article(title="Workers approve contract", summary="Union vote passes.", source_name="x"),
    )

    filtered = broadcast_sources.filter_articles_for_categories(
        articles,
        "labor,economics",
        limit=1,
    )

    assert filtered[0].title == "Workers approve contract"


def test_computed_sky_packet_is_ready_for_riyadh(tmp_path):
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        settings = broadcasts.ensure_broadcast_settings(connection, 123)

    packet = broadcast_sources.build_computed_sky_packet(
        settings,
        now=datetime(2026, 7, 12, 21, 30, tzinfo=ZoneInfo("Asia/Riyadh")),
    )

    assert packet.status == "ready"
    assert packet.observer_name == "Riyadh"
    assert packet.moon_phase
    assert packet.moon_illumination.endswith("%")


def test_collect_evidence_without_rss_keeps_news_empty_but_sky_ready(tmp_path, monkeypatch):
    monkeypatch.delenv("BROADCAST_NEWS_RSS_URLS", raising=False)
    monkeypatch.delenv("BROADCAST_ASTRONOMY_RSS_URLS", raising=False)
    database_path = tmp_path / "wilhelmina.sqlite3"
    initialize_database(database_path)

    with managed_connection(database_path) as connection:
        settings = broadcasts.ensure_broadcast_settings(connection, 123)

    evidence = broadcast_sources.collect_broadcast_evidence(
        settings,
        "morning",
        now=datetime(2026, 7, 12, 8, 0, tzinfo=ZoneInfo("Asia/Riyadh")),
    )

    assert evidence.news_items == ()
    assert evidence.sky_packet.status == "ready"
    assert any("No rss_news RSS URLs" in note for note in evidence.source_notes)
