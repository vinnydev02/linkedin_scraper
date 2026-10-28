"""Application service that coordinates the scraper and tracks its job status."""

import asyncio
import logging

from automation.api.schemas import JobState, ScrapeStatusResponse
from automation.browser.manager import BrowserManager
from automation.config.settings import Settings
from automation.scraper.linkedin_scraper import LinkedInPostScraper
from automation.storage.csv_repository import CsvPostRepository

logger = logging.getLogger(__name__)


class ScrapeAlreadyRunningError(RuntimeError):
    """Raised when a scrape is requested while another one is in progress."""


class ScrapeService:
    def __init__(self, settings: Settings, repository: CsvPostRepository | None = None) -> None:
        self.settings = settings
        self.repository = repository or CsvPostRepository(settings.paths.output_csv)
        self._status = ScrapeStatusResponse()
        self._status_lock = asyncio.Lock()

    async def start_job(self) -> None:
        async with self._status_lock:
            if self._status.state == JobState.RUNNING:
                raise ScrapeAlreadyRunningError("A scrape is already running")
            self._status = ScrapeStatusResponse(state=JobState.RUNNING, saved=0, error=None)

    async def get_status(self) -> ScrapeStatusResponse:
        async with self._status_lock:
            return self._status.model_copy(deep=True)

    async def run_in_background(self) -> None:
        try:
            saved = await self.run_scrape()
            async with self._status_lock:
                self._status = ScrapeStatusResponse(state=JobState.DONE, saved=saved)
            logger.info("Scrape completed; saved %s new posts", saved)
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            logger.exception("Scrape failed: %s", message)
            async with self._status_lock:
                self._status = ScrapeStatusResponse(
                    state=JobState.FAILED,
                    saved=self._status.saved,
                    error=message,
                )

    async def run_scrape(self) -> int:
        seen_ids = self.repository.load_seen_ids()
        logger.info("Loaded %s previously saved post IDs", len(seen_ids))
        total_saved = 0

        async with BrowserManager(self.settings) as browser:
            scraper = LinkedInPostScraper(self.settings, browser)
            for index, keyword in enumerate(self.settings.keywords):
                records = await scraper.scrape_keyword(keyword, seen_ids)
                self.repository.append(records)
                seen_ids.update(record.post_id for record in records)
                total_saved += len(records)

                async with self._status_lock:
                    self._status = self._status.model_copy(update={"saved": total_saved})

                logger.info("Saved %s new posts for keyword %r", len(records), keyword)
                if index < len(self.settings.keywords) - 1:
                    await browser.pause(
                        self.settings.delays.keyword_gap_seconds,
                        "gap before next keyword",
                    )

        return total_saved
