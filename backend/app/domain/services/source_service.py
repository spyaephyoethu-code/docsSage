import uuid

# runtime imports
from app.core.quotas import MAX_SOURCES_PER_KB
from app.domain.exceptions import SourceLimitExceeded, SourceNotFound

# type-hint imports
from app.infrastructure.db.models import Source
from app.infrastructure.db.repositories.chunk_repository import ChunkRepository
from app.infrastructure.db.repositories.source_repository import SourceRepository
from app.infrastructure.vector_store.pinecone_client import PineconeClient

_STRATEGY_MAP = {
    "github": "markdown",
    "pdf": "fixed",
    "web": "semantic",
    "text": "fixed",
    "word": "semantic",
}


class SourceService:
    def __init__(
        self,
        source_repo: SourceRepository,
        chunk_repo: ChunkRepository,
        pinecone: PineconeClient,
    ) -> None:
        self._repo = source_repo
        self._chunk_repo = chunk_repo
        self._pinecone = pinecone

    async def create_source(
        self,
        kb_id: uuid.UUID,
        source_type: str,
        url: str,
    ) -> Source:
        count = await self._repo.count_by_kb(kb_id)
        if count >= MAX_SOURCES_PER_KB:
            raise SourceLimitExceeded(
                f"KB already has {count} sources (max {MAX_SOURCES_PER_KB})"
            )
        strategy = _STRATEGY_MAP.get(source_type, "fixed")
        return await self._repo.create(kb_id, source_type, url, strategy)

    async def list_sources(self, kb_id: uuid.UUID) -> list[Source]:
        return await self._repo.list_by_kb(kb_id)

    async def get_source(self, source_id: uuid.UUID, kb_id: uuid.UUID) -> Source:
        source = await self._repo.get(source_id, kb_id)
        if source is None:
            raise SourceNotFound(f"Source {source_id} not found.")
        return source

    async def delete_source(self, source_id: uuid.UUID, kb_id: uuid.UUID) -> None:
        source = await self._repo.get(source_id, kb_id)
        if source is None:
            raise SourceNotFound(f"Source {source_id} not found.")
        pinecone_ids = await self._chunk_repo.get_pinecone_ids_by_source(source_id)
        if pinecone_ids:
            self._pinecone.delete_by_ids(pinecone_ids)
        await self._repo.delete(source_id)
