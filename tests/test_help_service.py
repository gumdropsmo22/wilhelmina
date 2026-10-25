from services import help as help_service


def test_build_page_groups_public_commands():
    entries = (
        help_service.HelpEntry(path="about", description="About Wilhelmina.", category="core"),
        help_service.HelpEntry(path="roll", description="Roll a die.", category="divination"),
        help_service.HelpEntry(path="help", description="Open help.", category="server"),
    )

    categories = help_service.available_categories(entries)
    assert categories == ("core", "divination", "server")

    page = help_service.build_page(entries, category="divination")
    assert page.category == "divination"
    assert page.category_label == "Divination"
    assert [entry.path for entry in page.entries] == ["roll"]
    assert page.coming_soon == ("/tarot",)


def test_live_command_root_is_removed_from_coming_soon():
    entries = (
        help_service.HelpEntry(path="tarot single", description="Draw one card.", category="divination"),
        help_service.HelpEntry(path="tarot three", description="Draw three cards.", category="divination"),
    )

    page = help_service.build_page(entries, category="divination")
    assert "/tarot" not in page.coming_soon
    assert page.coming_soon == ()


def test_unknown_category_falls_back_to_first_available():
    entries = (
        help_service.HelpEntry(path="help", description="Open help.", category="server"),
    )

    page = help_service.build_page(entries, category="does-not-exist")
    assert page.category == "server"


def test_empty_entries_still_builds_page():
    page = help_service.build_page((), category=None)
    assert page.category == "misc"
    assert page.total_pages == 1
    assert page.entries == ()


def test_retired_standalone_commands_never_appear_as_future_doors():
    entries = (
        help_service.HelpEntry(path="fortune", description="Fortune.", category="divination"),
        help_service.HelpEntry(path="rules", description="Rules.", category="server"),
    )
    divination = help_service.build_page(entries, category="divination")
    server = help_service.build_page(entries, category="server")
    assert "/tarot" in divination.coming_soon
    for retired in ("/readings", "/rituals", "/broadcast"):
        assert retired not in divination.coming_soon
        assert retired not in server.coming_soon
    assert server.coming_soon == ()
