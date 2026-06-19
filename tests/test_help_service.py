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
    assert "/tarot" in page.coming_soon


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
