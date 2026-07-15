import os
import pytest
from playwright.sync_api import expect

LOGIN_URL = os.getenv("PLAYWRIGHT_LOGIN_URL", "")
USERNAME = os.getenv("PLAYWRIGHT_USERNAME", "")
PASSWORD = os.getenv("PLAYWRIGHT_PASSWORD", "")
TEST_CALLER_NUMBER = os.getenv("PLAYWRIGHT_TEST_CALLER_NUMBER", "")


def pytest_addoption(parser):
    parser.addoption(
        "--brand",
        action="store",
        default=None,
        help="Run ticket scenarios only for this brand, for example: Digi",
    )


def pytest_collection_modifyitems(config, items):
    if LOGIN_URL and USERNAME and PASSWORD:
        return
    skip = pytest.mark.skip(reason="local browser credentials are not configured")
    for item in items:
        if item.path.name in {"test_login.py", "test_call.py"}:
            item.add_marker(skip)


@pytest.fixture
def brand_filter(request):
    brand = request.config.getoption("--brand")
    return brand.lower() if brand else None


@pytest.fixture
def login_credentials():
    assert USERNAME, "USERNAME not set"
    assert PASSWORD, "PASSWORD not set"

    return USERNAME, PASSWORD


@pytest.fixture
def logged_in_page(page, login_credentials):
    username, password = login_credentials

    assert LOGIN_URL, "PLAYWRIGHT_LOGIN_URL not set"
    page.goto(LOGIN_URL)
    page.fill("#username", username)
    page.fill("#password", password)
    page.get_by_role("button", name="Log In").click()

    expect(page).not_to_have_url(LOGIN_URL)

    return page
