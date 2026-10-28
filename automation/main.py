"""FastAPI application factory."""

import logging

from fastapi import FastAPI

from automation.api.routes import router
from automation.config.settings import Settings, load_settings
from automation.services.scrape_service import ScrapeService


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build an app instance; settings can be injected in tests or other environments."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    resolved_settings = settings or load_settings()
    app = FastAPI(
        title="LinkedIn Scraper API",
        description="Start a scrape job and query its status.",
        version="0.1.0",
    )
    app.state.scrape_service = ScrapeService(resolved_settings)
    app.include_router(router)
    return app


app = create_app()
