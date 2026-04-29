import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SourceCreate(BaseModel):
    type: Literal["github", "pdf", "web", "text", "word"]
    url: str = Field(..., min_length=1, max_length=2048)


class SourceResponse(BaseModel):
    id: uuid.UUID
    kb_id: uuid.UUID
    type: str
    url_or_path: str | None
    status: str
    chunk_count: int | None
    chunking_strategy: str | None
    ingested_at: datetime | None
    error_message: str | None

    model_config = {"from_attributes": True}
