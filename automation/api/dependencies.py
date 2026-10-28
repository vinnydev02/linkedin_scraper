"""FastAPI dependencies."""

from fastapi import Request

from automation.services.scrape_service import ScrapeService


def get_scrape_service(request: Request) -> ScrapeService:
    return request.app.state.scrape_service
