"""Domain models for extracted LinkedIn post identifiers and stored records."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
PostType = Literal["activity", "ugcPost", "share"]


class PostReference(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: PostType
    id: str = Field(pattern=r"^\d{18,20}$")


class PostRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    post_id: str = Field(pattern=r"^\d{18,20}$")
    post_url: str
    post_content: str
    posted_date: datetime | None
