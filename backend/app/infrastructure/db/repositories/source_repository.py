import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

# runtime imports
from app.infrastructure.db.models import Source


class SourceRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        kb_id: uuid.UUID,
        source_type: str,
        url_or_path: str,
        chunking_strategy: str,
    ) -> Source:
        source = Source(
            kb_id=kb_id,
            type=source_type,
            url_or_path=url_or_path,
            status="pending",
            chunking_strategy=chunking_strategy,
        )
        self._db.add(source)
        await self._db.commit()
        await self._db.refresh(source)
        return source

    async def get(self, source_id: uuid.UUID, kb_id: uuid.UUID) -> Source | None:
        result = await self._db.execute(
            select(Source).where(Source.id == source_id, Source.kb_id == kb_id)
        )
        return result.scalar_one_or_none()

    async def list_by_kb(self, kb_id: uuid.UUID) -> list[Source]:
        result = await self._db.execute(
            select(Source).where(Source.kb_id == kb_id).order_by(Source.ingested_at.desc())
        )
        return list(result.scalars().all())

    async def count_by_kb(self, kb_id: uuid.UUID) -> int:
        result = await self._db.execute(
            select(func.count()).select_from(Source).where(Source.kb_id == kb_id)
        )
        return result.scalar_one()

    async def delete(self, source_id: uuid.UUID) -> None:
        result = await self._db.execute(select(Source).where(Source.id == source_id))
        source = result.scalar_one_or_none()
        if source is not None:
            await self._db.delete(source)
            await self._db.commit()

    async def update_status(
        self,
        source_id: uuid.UUID,
        status: str,
        chunk_count: int | None = None,
        error_message: str | None = None,
    ) -> None:
        result = await self._db.execute(select(Source).where(Source.id == source_id))
        source = result.scalar_one_or_none()
        if source is None:
            return
        source.status = status
        if chunk_count is not None:
            source.chunk_count = chunk_count
        if status == "completed":
            source.ingested_at = datetime.utcnow()
        if error_message is not None:
            source.error_message = error_message
        await self._db.commit()

    async def reset_stale_running(self) -> int:
        result = await self._db.execute(
            update(Source)
            .where(Source.status == "running")
            .values(status="failed", error_message="Server restarted during ingestion — please retry")
            .returning(Source.id)
        )
        await self._db.commit()
        return len(result.fetchall())
