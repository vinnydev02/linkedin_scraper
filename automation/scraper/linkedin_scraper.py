"""Search LinkedIn content and combine response-level and rendered-page extraction."""

import logging
import random
import re

from playwright.async_api import Response

from automation.browser.manager import BrowserManager
from automation.config.settings import Settings
from automation.models.post import PostRecord, PostReference
from automation.scraper.extractor import PostExtractor

logger = logging.getLogger(__name__)


class LinkedInPostScraper:
    def __init__(
        self,
        settings: Settings,
        browser: BrowserManager,
        extractor: PostExtractor | None = None,
    ) -> None:
        self.settings = settings
        self.browser = browser
        self.extractor = extractor or PostExtractor()

    def build_search_url(self, keyword: str) -> str:
        from urllib.parse import quote, quote_plus

        base_url = self.settings.linkedin_base_url.rstrip("/")
        date_param = quote(f'"{self.settings.date_posted}"')
        sort_param = quote(f'"{self.settings.sortby}"')
        return (
            f"{base_url}/search/results/content/"
            f"?keywords={quote_plus(keyword)}"
            f"&datePosted={date_param}"
            f"&sortBy={sort_param}"
            "&origin=FACETED_SEARCH"
        )

    async def scrape_keyword(self, keyword: str, seen_ids: set[str]) -> list[PostRecord]:
        page = self.browser.page
        logger.info("Searching for keyword %r | date filter: %s", keyword, self.settings.date_posted)
        network_captured: dict[str, PostReference] = {}

        async def on_response(response: Response) -> None:
            url = response.url
            if not any(part in url for part in ("/voyager/api/", "graphql", "/search/", "content")):
                return
            try:
                content_type = response.headers.get("content-type", "")
                if "json" not in content_type and "text" not in content_type and "graphql" not in url:
                    return
                body = await response.text()
                for item in self.extractor.extract_urns_from_text(body):
                    network_captured[item.id] = item
            except Exception:
                logger.debug("Could not parse one network response", exc_info=True)

        page.on("response", on_response)
        try:
            await page.goto(self.build_search_url(keyword), wait_until="domcontentloaded")
            await self.browser.pause(self.settings.delays.load_pause_seconds, "initial page load")
            self.browser.raise_if_blocked()

            records: dict[str, PostRecord] = {}
            stale_passes = 0
            while (
                len(records) < self.settings.max_posts_per_keyword
                and stale_passes < self.settings.max_stale_scrolls
            ):
                dom_items = await self.extractor.extract_from_page(page)
                combined = dict(network_captured)
                combined.update({item.id: item for item in dom_items})

                fresh = [
                    item
                    for post_id, item in combined.items()
                    if post_id not in seen_ids and post_id not in records
                ]
                for item in fresh:
                    data = self.extractor.to_record(
                        item, self.settings.linkedin_base_url
                    )
                    if data:
                        records[item.id] = data

                stale_passes = 0 if fresh else stale_passes + 1
                logger.info(
                    "Collected %s/%s (combined=%s, new=%s, stale=%s/%s)",
                    len(records),
                    self.settings.max_posts_per_keyword,
                    len(combined),
                    len(fresh),
                    stale_passes,
                    self.settings.max_stale_scrolls,
                )

                if len(records) >= self.settings.max_posts_per_keyword:
                    break
                await self._scroll_results_page()

            return list(records.values())[: self.settings.max_posts_per_keyword]
        finally:
            page.remove_listener("response", on_response)

    async def _scroll_results_page(self) -> None:
        page = self.browser.page
        delays = self.settings.delays
        await page.mouse.move(random.randint(500, 800), random.randint(350, 650), steps=8)
        for _ in range(random.randint(*delays.wheel_ticks)):
            await page.mouse.wheel(0, random.randint(*delays.wheel_delta_px))
            await page.wait_for_timeout(random.uniform(*delays.wheel_tick_pause_ms))

        scroll_step = delays.scroll_step_px
        await page.evaluate(
            """(scrollStep) => {
                window.scrollBy({ top: scrollStep, behavior: 'smooth' });
                const containers = document.querySelectorAll(
                    'main, .scaffold-layout__main, .search-results-container, [role="main"]'
                );
                for (const container of containers) {
                    if (container.scrollHeight > container.clientHeight) {
                        container.scrollBy({ top: scrollStep, behavior: 'smooth' });
                    }
                }
                const items = document.querySelectorAll(
                    'main li, main [data-view-name], main article, main > div div'
                );
                if (items.length > 0) {
                    items[items.length - 1].scrollIntoView({
                        behavior: 'smooth', block: 'end'
                    });
                }
            }""",
            scroll_step,
        )

        more_button = page.locator("button:visible").filter(
            has_text=re.compile(r"show more results|see more results", re.I)
        ).first
        if await more_button.count() > 0:
            try:
                await more_button.click(timeout=3_000)
            except Exception:
                logger.debug("'Show more results' button was not clickable")

        await self.browser.pause(delays.scroll_pause_seconds, "between-scroll pause")
