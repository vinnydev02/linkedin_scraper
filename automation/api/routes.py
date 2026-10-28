"""HTTP routes for triggering a scrape and reading job status."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from automation.api.dependencies import get_scrape_service
from automation.api.schemas import HealthResponse, JobState, ScrapeResponse, ScrapeStatusResponse
from automation.services.scrape_service import ScrapeAlreadyRunningError, ScrapeService

router = APIRouter()


@router.post(
    "/scrape",
    response_model=ScrapeResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_scrape(
    background_tasks: BackgroundTasks,
    service: ScrapeService = Depends(get_scrape_service),
) -> ScrapeResponse:
    try:
        await service.start_job()
    except ScrapeAlreadyRunningError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    background_tasks.add_task(service.run_in_background)
    return ScrapeResponse(
        message="LinkedIn scraper started successfully in the background.",
        status=JobState.RUNNING,
    )


@router.get("/status", response_model=ScrapeStatusResponse)
async def get_status(
    service: ScrapeService = Depends(get_scrape_service),
) -> ScrapeStatusResponse:
    return await service.get_status()


@router.get("/", response_model=HealthResponse)
async def root() -> HealthResponse:
    return HealthResponse()
