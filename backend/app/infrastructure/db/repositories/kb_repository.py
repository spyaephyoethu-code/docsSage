import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models import KnowledgeBase


class KBRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_by_user(self, user_id: uuid.UUID) -> list[KnowledgeBase]:
        result = await self.db.execute(
            select(KnowledgeBase)
            .where(KnowledgeBase.user_id == user_id)
            .order_by(KnowledgeBase.created_at.desc())
        )
        return list(result.scalars().all())

    async def count_by_user(self, user_id: uuid.UUID) -> int:
        result = await self.db.execute(
            select(func.count()).where(KnowledgeBase.user_id == user_id)
        )
        return result.scalar() or 0

    async def get_owned(
        self, kb_id: uuid.UUID, user_id: uuid.UUID
    ) -> KnowledgeBase | None:
        result = await self.db.execute(
            select(KnowledgeBase).where(
                KnowledgeBase.id == kb_id,
                KnowledgeBase.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self, user_id: uuid.UUID, name: str, description: str | None
    ) -> KnowledgeBase:
        kb = KnowledgeBase(user_id=user_id, name=name, description=description)
        self.db.add(kb)
        await self.db.commit()
        await self.db.refresh(kb)
        return kb

    async def update(
        self,
        kb: KnowledgeBase,
        name: str | None,
        description: str | None,
    ) -> KnowledgeBase:
        if name is not None:
            kb.name = name
        if description is not None:
            kb.description = description
        await self.db.commit()
        await self.db.refresh(kb)
        return kb

    async def delete(self, kb: KnowledgeBase) -> None:
        await self.db.delete(kb)
        await self.db.commit()
