from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlparse

from playwright.async_api import Browser, BrowserContext, Page, async_playwright



def validate_navigation_url(url: str | None) -> str | None:
    if url is None:
        return None
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Only http and https navigation URLs are allowed")
    return url


class BrowserManager:
    def __init__(self, on_page: Callable[[Page], None] | None = None) -> None:
        self._playwright = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.pages: list[Page] = []
        self.on_page = on_page

    async def open(self, start_url: str | None) -> Page:
        start_url = validate_navigation_url(start_url)
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(headless=False)
        self.context = await self.browser.new_context()
        self.context.on("page", self._on_page)
        self.page = await self.context.new_page()
        self.pages.append(self.page)
        if start_url:
            await self.page.goto(start_url, wait_until="domcontentloaded")
        return self.page

    def _on_page(self, page: Page) -> None:
        self.page = page
        self.pages.append(page)
        if self.on_page:
            self.on_page(page)

    async def close(self) -> None:
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._playwright = self.browser = self.context = self.page = None
        self.pages.clear()
