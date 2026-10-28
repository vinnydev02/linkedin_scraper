"""Request and response schemas exposed by the HTTP API."""

from enum import StrEnum

from pydantic import BaseModel, Field


class JobState(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class ScrapeResponse(BaseModel):
    message: str
    status: JobState


class ScrapeStatusResponse(BaseModel):
    state: JobState = JobState.IDLE
    saved: int = Field(default=0, ge=0)
    error: str | None = None


class HealthResponse(BaseModel):
    status: str = "active"
    endpoints: list[str] = Field(
        default_factory=lambda: ["POST /scrape to start", "GET /status to check progress"]
    )
