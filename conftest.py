import pytest
from playwright.sync_api import expect

LOGIN_URL = "https://celcomdigi.daythree.ai/daisy-uat/index.php"

USERNAME = "UAT Tester 15"
PASSWORD = "C3lc0mD!g123"
TEST_CALLER_NUMBER = "601131219974"


def pytest_addoption(parser):
    parser.addoption(
        "--brand",
        action="store",
        default=None,
        help="Run ticket scenarios only for this brand, for example: Digi",
    )


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

    page.goto(LOGIN_URL)
    page.fill("#username", username)
    page.fill("#password", password)
    page.get_by_role("button", name="Log In").click()

    expect(page).not_to_have_url(LOGIN_URL)

    return page
