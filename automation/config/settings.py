"""Validated configuration loaded from config.json."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, PositiveInt, model_validator

DatePosted = Literal["past-24h", "past-week", "past-month"]
RangeFloat = tuple[float, float]
RangeInt = tuple[int, int]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config.json"


class PathsSettings(BaseModel):
    profile_dir: Path = Path("./linkedin_profile")
    output_csv: Path = Path("./linkedin_posts.csv")


class BrowserSettings(BaseModel):
    channel: str | None = "chrome"
    headless: bool = False
    viewport_width: PositiveInt = 1440
    viewport_height: PositiveInt = 900
    locale: str = "en-IN"
    timezone_id: str = "Asia/Kolkata"
    default_timeout_ms: PositiveInt = 15_000


class DelaySettings(BaseModel):
    short_pause_seconds: RangeFloat = (0.8, 1.8)
    load_pause_seconds: RangeFloat = (3.0, 5.0)
    wheel_tick_pause_ms: RangeFloat = (150.0, 350.0)
    scroll_pause_seconds: RangeFloat = (4.0, 7.0)
    keyword_gap_seconds: RangeFloat = (15.0, 30.0)
    wheel_ticks: RangeInt = (4, 7)
    wheel_delta_px: RangeInt = (250, 450)
    scroll_step_px: PositiveInt = 900

    @model_validator(mode="after")
    def validate_ranges(self) -> "DelaySettings":
        float_ranges = (
            self.short_pause_seconds,
            self.load_pause_seconds,
            self.wheel_tick_pause_ms,
            self.scroll_pause_seconds,
            self.keyword_gap_seconds,
        )
        int_ranges = (self.wheel_ticks, self.wheel_delta_px)
        for low, high in (*float_ranges, *int_ranges):
            if low < 0 or high < low:
                raise ValueError("Delay and scroll ranges must be non-negative and ordered")
        if self.wheel_ticks[0] < 1:
            raise ValueError("wheel_ticks must have a lower bound of at least 1")
        return self


class Settings(BaseModel):
    linkedin_base_url: str = "https://www.linkedin.com"
    keywords: list[str] = Field(min_length=1)
    max_posts_per_keyword: PositiveInt = 25
    date_posted: DatePosted = "past-24h"
    sortby:str ="relevance"
    blocked_paths: list[str] = Field(default_factory=lambda: ["/login", "/authwall", "/checkpoint"])
    login_timeout_ms: PositiveInt = 300_000
    max_stale_scrolls: PositiveInt = 6
    browser_close_delay_seconds: int = Field(default=30, ge=0)
    paths: PathsSettings = Field(default_factory=PathsSettings)
    browser: BrowserSettings = Field(default_factory=BrowserSettings)
    delays: DelaySettings = Field(default_factory=DelaySettings)


def _resolve_path(path: Path, base_dir: Path) -> Path:
    """Resolve relative config paths relative to the config file, not the shell cwd."""
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def load_settings(config_path: Path | None = None) -> Settings:
    """Load and validate settings; SCRAPER_CONFIG_FILE can point to another JSON file."""
    configured_path = os.getenv("SCRAPER_CONFIG_FILE")
    selected_path = Path(configured_path) if configured_path else config_path or DEFAULT_CONFIG_PATH
    if not selected_path.is_absolute():
        selected_path = (PROJECT_ROOT / selected_path).resolve()

    if not selected_path.exists():
        raise FileNotFoundError(f"Config file not found: {selected_path}")

    payload = json.loads(selected_path.read_text(encoding="utf-8"))
    settings = Settings.model_validate(payload)
    settings.paths.profile_dir = _resolve_path(settings.paths.profile_dir, selected_path.parent)
    settings.paths.output_csv = _resolve_path(settings.paths.output_csv, selected_path.parent)
    return settings
