import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# runtime imports
from app.infrastructure.db.models import ChunkMetadata, Source


class ChunkRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def bulk_create(
        self,
        source_id: uuid.UUID,
        chunks: list[dict],
    ) -> None:
        for chunk in chunks:
            self._db.add(
                ChunkMetadata(
                    source_id=source_id,
                    chunk_text=chunk["text"],
                    pinecone_id=chunk.get("pinecone_id"),
                    token_count=chunk.get("token_count"),
                    source_url=chunk.get("source_url"),
                    source_title=chunk.get("source_title"),
                )
            )
        await self._db.commit()

    async def get_pinecone_ids_by_source(self, source_id: uuid.UUID) -> list[str]:
        result = await self._db.execute(
            select(ChunkMetadata.pinecone_id).where(
                ChunkMetadata.source_id == source_id,
                ChunkMetadata.pinecone_id.is_not(None),
            )
        )
        return [r for r in result.scalars().all() if r is not None]

    async def get_all_by_kb(self, kb_id: uuid.UUID) -> list[ChunkMetadata]:
        result = await self._db.execute(
            select(ChunkMetadata)
            .join(Source, ChunkMetadata.source_id == Source.id)
            .where(Source.kb_id == kb_id, Source.status == "completed")
        )
        return list(result.scalars().all())

    async def get_pinecone_ids_by_kb(self, kb_id: uuid.UUID) -> list[str]:
        result = await self._db.execute(
            select(ChunkMetadata.pinecone_id)
            .join(Source, ChunkMetadata.source_id == Source.id)
            .where(
                Source.kb_id == kb_id,
                ChunkMetadata.pinecone_id.is_not(None),
            )
        )
        return [r for r in result.scalars().all() if r is not None]
