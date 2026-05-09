import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# runtime imports
from app.infrastructure.db.models import Conversation


class ConversationRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(self, kb_id: uuid.UUID, user_id: uuid.UUID) -> Conversation:
        conv = Conversation(kb_id=kb_id, user_id=user_id)
        self._db.add(conv)
        await self._db.commit()
        await self._db.refresh(conv)
        return conv

    async def get(
        self,
        conversation_id: uuid.UUID,
        kb_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Conversation | None:
        result = await self._db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.kb_id == kb_id,
                Conversation.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_summary(
        self, conversation_id: uuid.UUID, summary: str
    ) -> None:
        result = await self._db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        if conv is not None:
            conv.summary = summary
            await self._db.commit()

    async def list_by_kb(
        self, kb_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[Conversation]:
        result = await self._db.execute(
            select(Conversation)
            .where(Conversation.kb_id == kb_id, Conversation.user_id == user_id)
            .order_by(Conversation.created_at.desc())
        )
        return list(result.scalars().all())
