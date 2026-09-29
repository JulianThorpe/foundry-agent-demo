from agent import navigate_to_page, ALLOWED_PAGES, MAX_ITERATIONS


def test_allowed_page_succeeds():
    result = navigate_to_page("pricing")
    assert result["ok"] is True
    assert result["page"] == "pricing"


def test_unknown_page_is_rejected():
    result = navigate_to_page("admin")
    assert result["ok"] is False
    assert "unknown page" in result["error"]


def test_every_allowed_page_is_reachable():
    for page in ALLOWED_PAGES:
        assert navigate_to_page(page)["ok"] is True


def test_iteration_cap_is_bounded():
    assert 0 < MAX_ITERATIONS <= 10