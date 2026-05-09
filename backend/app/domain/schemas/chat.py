import uuid

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    conversation_id: uuid.UUID | None = None


class CitationItem(BaseModel):
    index: int
    chunk_text: str
    source_name: str | None = None
    source_url: str | None = None
    source_type: str | None = None


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    answer: str
    citations: list[CitationItem]
    latency_ms: int
    cost_usd: float


class ConversationResponse(BaseModel):
    id: uuid.UUID
    kb_id: uuid.UUID
    title: str | None
    created_at: str


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    citations: list[CitationItem] | None
    created_at: str
