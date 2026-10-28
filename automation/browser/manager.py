"""Own the Playwright lifecycle and login/session interactions."""

from __future__ import annotations

import asyncio
import logging
import random
from pathlib import Path

from playwright.async_api import BrowserContext, Page, Playwright, async_playwright

from automation.config.settings import Settings

logger = logging.getLogger(__name__)


class BrowserManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._playwright: Playwright | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Browser has not been started. Use 'async with BrowserManager(...)'.")
        return self._page

    async def __aenter__(self) -> "BrowserManager":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await self.close()

    async def start(self) -> None:
        profile_dir: Path = self.settings.paths.profile_dir
        profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = await async_playwright().start()
        try:
            browser = self.settings.browser
            launch_options = {
                "user_data_dir": str(profile_dir),
                "headless": browser.headless,
                "viewport": {
                    "width": browser.viewport_width,
                    "height": browser.viewport_height,
                },
                "locale": browser.locale,
                "timezone_id": browser.timezone_id,
            }
            if browser.channel:
                launch_options["channel"] = browser.channel

            self._context = await self._playwright.chromium.launch_persistent_context(
                **launch_options
            )
            self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()
            self._page.set_default_timeout(browser.default_timeout_ms)
            await self.ensure_logged_in()
        except Exception:
            await self.close(wait_before_close=False)
            raise

    async def close(self, wait_before_close: bool = True) -> None:
        if self._context is not None:
            delay = self.settings.browser_close_delay_seconds if wait_before_close else 0
            if delay:
                logger.info("Keeping browser open for %s seconds before closing", delay)
                await asyncio.sleep(delay)
            await self._context.close()
            self._context = None
            self._page = None

        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    def is_logged_in(self) -> bool:
        url = self.page.url.lower()
        if any(path in url for path in self.settings.blocked_paths):
            return False
        return "linkedin.com" in url

    def raise_if_blocked(self) -> None:
        if not self.is_logged_in():
            raise RuntimeError(
                f"Login wall or checkpoint detected at {self.page.url}. "
                "Resolve it in the browser and rerun the job."
            )

    async def pause(self, bounds: tuple[float, float], label: str = "") -> None:
        delay_seconds = random.uniform(*bounds)
        if label:
            logger.info("Waiting %.2f seconds: %s", delay_seconds, label)
        await self.page.wait_for_timeout(delay_seconds * 1000)

    async def ensure_logged_in(self) -> None:
        await self.page.goto(
            f"{self.settings.linkedin_base_url.rstrip('/')}/feed/",
            wait_until="domcontentloaded",
        )
        await self.pause(self.settings.delays.short_pause_seconds, "checking login session")

        if self.is_logged_in() and "/feed" in self.page.url:
            logger.info("Existing LinkedIn session is valid")
            return

        logger.info("Manual login may be required in the opened browser window")
        await self.page.wait_for_url(
            "**/feed/**", timeout=self.settings.login_timeout_ms
        )
        logger.info("Login completed; browser profile is persisted")
