import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

# runtime imports
from app.infrastructure.db.models import Conversation, Message


class MessageRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        *,
        citations: list[dict] | None = None,
        latency_ms: int | None = None,
        cost_usd: float | None = None,
    ) -> Message:
        msg = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            citations=citations,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
        )
        self._db.add(msg)
        await self._db.commit()
        await self._db.refresh(msg)
        return msg

    async def get_last_n(self, conversation_id: uuid.UUID, n: int) -> list[Message]:
        result = await self._db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(n)
        )
        return list(reversed(result.scalars().all()))

    async def count_by_conversation(self, conversation_id: uuid.UUID) -> int:
        result = await self._db.execute(
            select(func.count())
            .select_from(Message)
            .where(Message.conversation_id == conversation_id)
        )
        return result.scalar_one()

    async def get_all_except_last_n(
        self, conversation_id: uuid.UUID, n: int
    ) -> list[Message]:
        total = await self.count_by_conversation(conversation_id)
        if total <= n:
            return []
        result = await self._db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .limit(total - n)
        )
        return list(result.scalars().all())

    async def list_by_conversation(self, conversation_id: uuid.UUID) -> list[Message]:
        result = await self._db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        return list(result.scalars().all())

    async def count_today(self, user_id: uuid.UUID) -> int:
        today_start = datetime.now(tz=UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        result = await self._db.execute(
            select(func.count())
            .select_from(Message)
            .join(Conversation, Message.conversation_id == Conversation.id)
            .where(
                Conversation.user_id == user_id,
                Message.role == "user",
                Message.created_at >= today_start,
            )
        )
        return result.scalar_one()
