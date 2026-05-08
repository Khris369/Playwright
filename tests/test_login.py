import allure
from playwright.sync_api import expect

from conftest import PASSWORD, USERNAME

LOGIN_URL = "https://celcomdigi.daythree.ai/daisy-uat/index.php"


def test_login(page):
    assert USERNAME, "USERNAME not set"
    assert PASSWORD, "PASSWORD not set"

    with allure.step("Open login page"):
        page.goto(LOGIN_URL)
        expect(page).to_have_title("DAISY I Login v1.5.1")

    with allure.step("Enter credentials"):
        page.fill("#username", USERNAME)
        page.fill("#password", PASSWORD)

    with allure.step("Click login"):
        page.get_by_role("button", name="Log In").click()

    page.wait_for_timeout(2000)

    with allure.step("Validate login result"):
        if page.locator("#errorText1").is_visible():
            allure.attach(
                page.screenshot(),
                name="invalid_username",
                attachment_type=allure.attachment_type.PNG,
            )
            raise AssertionError("Invalid username")

        if page.locator("#errorText2").is_visible():
            allure.attach(
                page.screenshot(),
                name="empty_username",
                attachment_type=allure.attachment_type.PNG,
            )
            raise AssertionError("Username cannot be empty")

        if page.locator("#errorText3").is_visible():
            allure.attach(
                page.screenshot(),
                name="invalid_email",
                attachment_type=allure.attachment_type.PNG,
            )
            raise AssertionError("Invalid email format")

        expect(page).not_to_have_url(LOGIN_URL)
